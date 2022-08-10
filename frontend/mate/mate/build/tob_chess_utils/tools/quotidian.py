#!/usr/bin/env python3

# quotidian.py: Take a binary compiled with gllvm, extract its bitcode,
# pass that bitcode to our various instrumentation passes, and output
# nodes and edges files suitable for CPG ingestion. If bitcode is given
# directly instead of a compiled binary, skip the extraction steps.

import json
import os
import re
import shlex
import shutil
import subprocess
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile as T
from tempfile import TemporaryDirectory as TD
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

import docker
import jsonlines
from elftools.dwarf import constants as dw_constants

from mate.build.common import docker_bind, docker_image, docker_volume_by_label, mate_environment
from mate.build.tob_chess_utils.logging import make_logger
from mate.build.tob_chess_utils.tools import aspirin, margin, migraine
from mate.build.tob_chess_utils.tools.margin import MarginWalkerOptions
from mate.config import (
    CLANG,
    CLANGXX,
    DOCKER_SOCKET,
    LLVM_LLC,
    LLVM_OPT,
    MATE_BDIST_DOCKER_VOLUME,
    MATE_BDIST_ROOT,
    MATE_SCRATCH,
    MATE_SCRATCH_DOCKER_VOLUME,
)
from mate_common.error import MateError
from mate_common.models.artifacts import ArtifactKind
from mate_query import db

_SOURCE_ID_COMPILERS = {
    dw_constants.DW_LANG_C89: CLANG,
    dw_constants.DW_LANG_C: CLANG,
    dw_constants.DW_LANG_C_plus_plus: CLANGXX,
    dw_constants.DW_LANG_C99: CLANG,
    dw_constants.DW_LANG_C_plus_plus_03: CLANGXX,
    dw_constants.DW_LANG_C_plus_plus_11: CLANGXX,
    dw_constants.DW_LANG_C11: CLANG,
    dw_constants.DW_LANG_C_plus_plus_14: CLANGXX,
}

# NOTE(ww): This mapping is *not* intended for general-purpose linker flag
# recovery (e.g., infering that we should link to libpng),
# It's meant for inferring standard runtime linkages that are implicitly
# provided by the compiler frontend in C/C++ mode but that are dropped
# during recompilation in bitcode or assembly mode.
_INFERRABLE_LINKER_FLAGS = {
    "std::__codecvt": {"-lstdc++"},
    "std::experimental::filesystem": {"-lstdc++fs", "-lstdc++"},
    "std::filesystem": {"-lstdc++fs", "-lstdc++"},
    "pthread_": {"-lpthread"},
    "dlopen": {"-ldl"},
    "dlerror": {"-ldl"},
    "dlsym": {"-ldl"},
    "dlclose": {"-ldl"},
    "pow": {"-lm"},
    "sqrt": {"-lm"},
    "crypt": {"-lcrypt"},
    "__muloti4": {"-rtlib=compiler-rt"},
}


_TOB_CHESS_PASSES = ["Headache"]

_COMPILER_FLAG_PATTERN = re.compile(
    "|".join(
        [
            # Preprocessor/macro flags
            # TODO(ww): Maybe not required here, since we're dealing with assembly?
            r"^-D.+$",
            r"^-U.+$",
            # Linker arguments
            r"^-Wl,.+$",
            # Compiler warnings
            r"^-W(?!l,).*$",
            # Sanitizers
            r"^-fsanitize=.+$",
            # Compilation/optimization behavior
            r"^-f.+$",
            # Compiler and C/C++ runtime configuration
            r"^-rtlib=.+$",
            r"^-stdlib=.+$",
            # TODO(ww): Debugger, optimization flags?
        ]
    )
)

# NOTE(ww): `-Wl,`-type arguments go to the linker via
# the compiler driver so we don't include them here.
_LINKER_FLAG_PATTERN = re.compile(
    "|".join(
        [
            # Linker paths/libraries
            r"^-(l|L).+$",
            # Compiler and C/C++ runtime configuration
            # NOTE(ww): These are included in the compiler flags, but are also handled
            # here because they can imply additional linkage for some C++ versions.
            r"^-rtlib=.+$",
            r"^-stdlib=.+$",
            # Sanitizers
            # NOTE(ww): Like above; handled in the compiler flags, but also need to
            # be passed to the linker to make sure the appropriate sanitizer(s) are
            # actually linked to.
            r"^-fsanitize=.+$",
        ]
    )
)

logger = make_logger(__name__)


class QuotidianError(MateError):
    """A generic error, internal to ``quotidian``."""

    pass


# TODO(ww): Migrate `quotidian.quotidian()`'s mess of kwargs into this structure.
@dataclass(eq=True, frozen=True)
class QuotidianOptions:
    """A collection of behavioral settings and metadata for ``quotidian.quotidian``."""

    build: db.Build
    """
    The ``mate.db.Build`` associated with the Quotidian run.
    """

    image: Optional[str] = None
    """
    The Docker image to use for containerized recompilation, if any.
    """

    line_program: bool = False
    """
    Whether to emit line program information.
    """

    extra_linker_flags: List[str] = field(default_factory=list)
    """
    Any additional flags to pass to the linker during recompilation.
    """


@dataclass(eq=True)
class QuotidianContext:
    options: QuotidianOptions
    """
    The options that this run of Quotidian was started with.
    """

    new_artifacts: List[db.Artifact] = field(default_factory=list)
    """
    A list of new artifacts created through Quotidian's internal steps.
    """


def run(*argv, env: Optional[Dict[str, str]] = None, **kwargs: Any) -> subprocess.CompletedProcess:
    """Run the given command, updating the environment with a mapping supplied by ``env``, if
    any."""
    logger.debug(f"Running: {argv}")

    if env:
        env = {**os.environ, **env}
    try:
        return subprocess.run(argv, env=env, check=True, **kwargs)
    except subprocess.CalledProcessError as e:
        logger.error(f"Execution failed: {e}\nstderr={e.stderr}")
        raise QuotidianError from e


def container_run(
    client: docker.DockerClient, image: docker.models.images.Image, *, command: List[str]
) -> None:
    """Run the given command in a container created from the given image, using the supplied Docker
    client."""
    mate_bdist_volume = docker_volume_by_label(client, MATE_BDIST_DOCKER_VOLUME)
    if mate_bdist_volume is None:
        raise QuotidianError(
            f"failed to locate a bdist volume for container use: {MATE_BDIST_DOCKER_VOLUME}",
        )
    mate_scratch_volume = docker_volume_by_label(client, MATE_SCRATCH_DOCKER_VOLUME)
    if mate_scratch_volume is None:
        raise QuotidianError(
            f"failed to locate a scratch volume for container use {MATE_SCRATCH_DOCKER_VOLUME}",
        )

    logger.debug(f"Beginning container run for {image=}; {command=}")

    logstream = client.containers.run(
        image,
        name=f"mate-quotidian-recompile-{str(uuid.uuid4())}",
        remove=True,
        volumes={
            mate_bdist_volume.name: docker_bind(MATE_BDIST_ROOT, mode="ro"),
            mate_scratch_volume.name: docker_bind(MATE_SCRATCH),
        },
        working_dir=str(MATE_SCRATCH),
        detach=False,
        environment=mate_environment(llvm_wedlock=True),
        user=0,
        command=command,
        stream=True,
        stdout=True,
        stderr=True,
    )

    for line in logstream:
        logger.info(f"Container run: {line}")


def build_common_compiler_flags(
    all_cu_flags: Set[str], target_triple: str
) -> Tuple[List[str], Set[str], List[str]]:
    """Given a set containing all unique compiler flags used by all compilation units in the input,
    attempts to construct a (minimal) list of flags for recompilation and relinking."""
    compiler_flags = [flag for flag in all_cu_flags if _COMPILER_FLAG_PATTERN.search(flag)]
    # NOTE(ww): Treating linker_flags as a set is *probably* safe, but should be revisited:
    # dynamically linked objects shouldn't care about their link-flag order, but static
    # objects might.
    linker_flags = {flag for flag in all_cu_flags if _LINKER_FLAG_PATTERN.search(flag)}
    return compiler_flags, {"-L.", *linker_flags}, ["-target", target_triple]


def infer_linker_flags_from_externals(externals: Set[str]) -> Set[str]:
    """Given a set of all external symbols that appear in all compilation units of the program,
    attempts to infer linker flags that would be implicit during the normal compilation pipeline."""
    linker_flags: Set[str] = set()
    for prefix, flags in _INFERRABLE_LINKER_FLAGS.items():
        if flags - linker_flags and any(external.startswith(prefix) for external in externals):
            linker_flags.update(flags)
    return linker_flags


def infer_compiler(source_ids: Set[int]) -> Path:
    """Given a set of DWARF language IDs, infer an appropriate compiler frontend (i.e., ``clang`` or
    ``clang++``) to invoke for recompilation."""
    compiler = None
    if len(source_ids) == 1:
        compiler = _SOURCE_ID_COMPILERS.get(next(iter(source_ids)))
    elif len(source_ids) > 1:
        logger.warning(
            f"Weird: More than one unique DWARF language ID: {', '.join(map(str, source_ids))};"
            " defaulting to clang++..."
        )
        compiler = CLANGXX
    elif len(source_ids) == 0:
        # NOTE(ww): This is a user error; fail unconditionally.
        raise QuotidianError("No DWARF language ID; recompile with -g")

    if compiler is None:
        logger.error(
            f"No known compiler for DWARF language ID: {hex(next(iter(source_ids)))}, "
            f"trying {CLANGXX} and praying..."
        )
        compiler = CLANGXX

    return compiler


def extract_compiler_and_flags(
    cu_dict: Dict[str, Any]
) -> Tuple[Path, List[str], List[str], List[str]]:
    """Given a Headache-extracted compilation unit information file, returns a tuple of (compiler,
    compiler_flags, linker_flags, target_flags) suitable for recompiling the bitcode.

    Note: The results of this function are later augmented by
    ``infer_linker_flags_from_externals`` and ``linker_flags_from_build_record``.
    """
    all_cu_flags = set()
    source_ids = set()
    target_triples = set()
    all_externals = set()
    for cu in cu_dict["cus"]:
        all_cu_flags.update(shlex.split(cu["flags"]))
    source_ids.update([cu["source_language_id"] for cu in cu_dict["cus"]])
    target_triples.add(cu_dict["target_triple"])

    if len(target_triples) != 1:
        logger.error(f"Weird: Expected exactly one target triple, but got {len(target_triples)}")

    cu_externals = set()
    for external in cu_dict["externals"]:
        if external["is_mangled"]:
            external = external["demangled_name"]
        else:
            external = external["name"]
        cu_externals.add(external)
    all_externals.update(cu_externals)

    compiler = infer_compiler(source_ids)

    compiler_flags, linker_flags, target_flags = build_common_compiler_flags(
        all_cu_flags, next(iter(target_triples))
    )
    linker_flags.update(infer_linker_flags_from_externals(all_externals))

    return (compiler, compiler_flags, list(linker_flags), target_flags)


def linker_flags_from_build_record(build_record: List[Dict[str, Any]]) -> List[str]:
    """Given a "build record" (i.e., a list of individual compile tool invocations), attempt to suss
    out additional flags that look like they belong to the linker."""
    linker_flags = []

    for record in build_record:
        if record["name"] not in ["CC", "CXX", "LD"]:
            continue

        # NOTE(ww): Unnecessarily inefficient; we could *probably* get away with
        # using a set internally here.
        linker_flags += [
            flag
            for flag in record["args"]
            if _LINKER_FLAG_PATTERN.search(flag) and flag not in linker_flags
        ]

    return linker_flags


@contextmanager
def _temporary_libdir(context: QuotidianContext, *, base: Optional[Path] = None) -> Iterator[Path]:
    # HACK(ww): There are still a few linkage scenarios that we can't handle
    # cleanly during recompilation due to our isolation, including relative
    # linkages that use the `-L./local/path -llib` syntax instead of passing
    # the library in directly. To "fix" these, we copy all of the libraries
    # produced by the build into a temporary directory and put that directory
    # first on the library search path.
    with TD(dir=base) as libdir:
        libdir_path = Path(libdir)
        for artifact in context.options.build.compilation.artifacts:
            if artifact.kind not in [
                ArtifactKind.CompileOutputSharedLibrary,
                ArtifactKind.CompileOutputStaticLibrary,
            ]:
                continue

            with artifact.get_object() as src:
                library = libdir_path / artifact.attributes["filename"]
                with library.open("wb") as dst:
                    shutil.copyfileobj(src, dst)

        yield libdir_path


def _recompile_containerized(
    context: QuotidianContext,
    image: str,
    compiler: Path,
    asm_file: Path,
    *,
    target_flags: List[str],
    compiler_flags: List[str],
    linker_flags: List[str],
) -> Path:
    # NOTE(ww): Is re-checking the socket here too paranoid? Someone could
    # conceivably stand MATE up for compilation with Docker mounted, then
    # re-stand it without Docker. But is that likely?
    if not DOCKER_SOCKET.is_socket():
        raise QuotidianError(
            "required containerized quotidian CPG phase, but the Docker socket is not available",
        )

    client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET}")
    try:
        image = docker_image(client, image)
    except docker.errors.DockerException as e:
        raise QuotidianError(str(e))

    compiled_object_scratch = Path(T(dir=MATE_SCRATCH, suffix=".o").name)
    compiled_binary_scratch = Path(T(dir=MATE_SCRATCH, suffix=".bin").name)
    asm_file_scratch = Path(T(dir=MATE_SCRATCH, suffix=".s").name)
    shutil.copyfile(asm_file, asm_file_scratch)

    container_run(
        client,
        image,
        command=[
            str(compiler),
            *target_flags,
            *compiler_flags,
            "-c",
            str(asm_file_scratch),
            "-o",
            str(compiled_object_scratch),
        ],
    )

    with _temporary_libdir(context, base=MATE_SCRATCH) as library_dir:
        container_run(
            client,
            image,
            command=[
                str(compiler),
                *target_flags,
                str(compiled_object_scratch),
                f"-L{library_dir}",
                *linker_flags,
                "-o",
                str(compiled_binary_scratch),
            ],
        )

    return compiled_binary_scratch


def quotidian(
    bitcode_file: Path,
    *,
    bdist_root: Path,
    options: QuotidianOptions,
    margin_options: Dict[str, Any] = {},
) -> Tuple[Iterator[Dict[str, Any]], List[db.Artifact]]:
    context = QuotidianContext(options)

    logger.debug("We're running quotidian under the Postgres server!")

    opt_load_args = []
    for opt_pass in _TOB_CHESS_PASSES:
        opt_load_args += ["-load", os.path.join(bdist_root, "local/lib", f"LLVM{opt_pass}.so")]

    logger.info("Headache: instrumentation")
    with T(suffix=".cu") as cu, T(suffix=".vi") as vi, T(suffix=".ti") as ti, T(
        suffix=".log"
    ) as log:
        run(
            LLVM_OPT,
            "-disable-opt",
            *opt_load_args,
            "-headache",
            "-headache-logging-output",
            log.name,
            "-headache-cu-info",
            "-headache-cu-info-output",
            cu.name,
            "-headache-var-type-info",
            "-headache-var-info-output",
            vi.name,
            "-headache-type-info-output",
            ti.name,
            bitcode_file,
            "-o",
            "/dev/null",
        )

        # NOTE(ww): The headache log file contains a record of weird things
        # encountered when doing variable/type extraction; print a small warning message
        # encouraging someone to read it if it's nonempty.
        # TODO(ww): Will need to be replaced with a different check for the object store.
        if os.path.getsize(log.name) > 0:
            with open(log.name) as io:
                artifact = db.Artifact.create_with_object(
                    kind=ArtifactKind.BuildOutputQuotidianHeadacheLog,
                    fileobj=io,
                    attributes={"filename": "headache.log"},
                )
                context.new_artifacts.append(artifact)

                logger.warning(
                    "Headache encountered some interesting conditions "
                    f"and logged them in artifact {artifact.uuid}"
                )

        vi_dicts = []
        with open(vi.name) as vi_file:
            for jsonl in vi_file:
                vi_dicts.append(json.loads(jsonl))

        ti_map = {}
        with open(ti.name) as ti_file:
            for jsonl in ti_file:
                ti_record = json.loads(jsonl)
                ti_map[ti_record["type_id"]] = ti_record["type"]

        with open(cu.name) as cu_file:
            cu_dict = json.loads(cu_file.read())

    build_record = []
    journal_artifact = next(
        (a for a in options.build.compilation.artifacts if a.kind == ArtifactKind.BlightJournal),
        None,
    )
    if journal_artifact is not None:
        journal_file = journal_artifact.persist_locally()
        with journal_file.open() as io:
            for line in jsonlines.Reader(io):
                record = line.get("Record")
                if record is not None:
                    build_record.append(record)
        journal_file.unlink()
    else:
        logger.info(
            "Postgres-based build's compilation has no blight journal; probably bitcode-only"
        )

    logger.info("Wedlock: IR and MI pairing")
    with T(mode="w", suffix=".s") as asm_file, T(mode="w+", suffix=".wed.jsonl") as wed, T(
        suffix=".log"
    ) as log:
        # TODO(ww): LLCFLAGS.
        run(
            LLVM_LLC,
            "-O0",
            "-wedlock",
            "-wedlock-logging-output",
            log.name,
            "-wedlock-output",
            wed.name,
            bitcode_file,
            "-o",
            asm_file.name,
        )

        # NOTE(ww): The Wedlock log file contains a record of weird things
        # encountered when performing IR/MI pairing; print a small warning message
        # encoraging someone to read it if it's nonempty.
        if os.path.getsize(log.name) > 0:
            with open(log.name) as io:
                artifact = db.Artifact.create_with_object(
                    kind=ArtifactKind.BuildOutputQuotidianWedlockLog,
                    fileobj=io,
                    attributes={"filename": "wedlock.log"},
                )
                context.new_artifacts.append(artifact)

                logger.warning(
                    "Wedlock encountered some interesting conditions "
                    f"and logged them in artifact {artifact.uuid}"
                )

        wed_dicts = []
        for jsonl in wed:
            wed_dicts.append(json.loads(jsonl))

        logger.info("Migraine: Generation of address anchors")
        asm_file.seek(0, os.SEEK_END)
        for line in migraine.migraine(wed_dicts):
            print(line, file=asm_file)
        asm_file.flush()

        logger.info("Recompilation")
        compiler, compiler_flags, linker_flags, target_flags = extract_compiler_and_flags(cu_dict)
        linker_flags += linker_flags_from_build_record(build_record)
        linker_flags += options.extra_linker_flags

        if options.image is not None:
            compiled_binary = _recompile_containerized(
                context,
                options.image,
                compiler,
                Path(asm_file.name),
                target_flags=target_flags,
                compiler_flags=compiler_flags,
                linker_flags=linker_flags,
            )
        else:
            compiled_binary = Path(T(suffix=".quotidian.bin").name)
            with T(suffix=".quotidian.o") as compiled_object:
                run(
                    compiler,
                    *target_flags,
                    *compiler_flags,
                    "-c",
                    asm_file.name,
                    "-o",
                    compiled_object.name,
                )

                with _temporary_libdir(context) as library_dir:
                    run(
                        compiler,
                        *target_flags,
                        compiled_object.name,
                        f"-L{library_dir}",
                        *linker_flags,
                        "-o",
                        compiled_binary,
                    )

        with compiled_binary.open(mode="rb") as bin_io:
            context.new_artifacts.append(
                db.Artifact.create_with_object(
                    kind=ArtifactKind.BuildOutputQuotidianCanonicalBinary,
                    fileobj=bin_io,
                    # TODO(ww): Something less generic here?
                    attributes={"filename": "quotidian.bin"},
                )
            )

    with compiled_binary.open("rb") as binary:
        asp_dicts = list(aspirin.aspirin(binary, vi_dicts, line_program=options.line_program))

    logger.info("margin-walker: Node and edge generation")
    return (
        margin.margin(
            wed_dicts, asp_dicts, ti_map, cu_dict, options=MarginWalkerOptions(**margin_options)
        ),
        context.new_artifacts,
    )
