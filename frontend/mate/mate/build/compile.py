from __future__ import annotations

import io
import logging
import os
import shlex
import shutil
import subprocess
import tarfile
import uuid
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile as TF
from tempfile import TemporaryDirectory as TD
from typing import IO, Any, AnyStr, Dict, Final, Iterator, List, Literal, NoReturn, Optional, Tuple

import docker
import dockerfile
import jsonlines
from blight.actions.find_outputs import Output
from blight.enums import OutputKind
from docker import DockerClient
from docker.models.images import Image as DockerImage
from docker.models.volumes import Volume as DockerVolume
from sqlalchemy import orm

from mate.assertions import CompilationAssertionError, compilation_assert
from mate.build.common import (
    Environment,
    docker_bind,
    docker_image,
    docker_volume_by_label,
    format_run_log,
    gllvm_environment,
    llvm_wedlock_environment,
    mate_environment,
    run,
)
from mate.config import (
    CLANG,
    CLANGXX,
    DOCKER_SOCKET,
    LLVM_OBJCOPY,
    MATE_BDIST_DOCKER_VOLUME,
    MATE_BDIST_LIBEXEC_PATH,
    MATE_BDIST_ROOT,
    MATE_SCRATCH,
    MATE_SCRATCH_DOCKER_VOLUME,
)
from mate.logging import logger
from mate_common.error import MateError, process_error_to_message
from mate_common.models.artifacts import ArtifactKind
from mate_common.models.compilations import CompilationState, CompileOptions
from mate_query import db

REQUIRED_CFLAGS: Final[Tuple[str, ...]] = ("-g3", "-grecord-gcc-switches")

# NOTE(ww): The order and contents of this list reflect GNU Make's order of
# preference when searching for a Makefile. "MAKEFILE" is not listed in the
# GNU docs, but experimentally also works.
# See: https://www.gnu.org/software/make/manual/make.html#Makefile-Names
KNOWN_MAKEFILES: Final[List[str]] = ["GNUmakefile", "makefile", "Makefile", "MAKEFILE"]

# NOTE(ww): We use --guess-wrapped here to provide reasonable wrappers for tools
# that we don't particularly care about instrumenting for the time being
# (like `as`, `ld`, etc.). That flag respects any wrappers that we explicitly
# set in the environment, so our explicit `BLIGHT_WRAPPED_{CC,CXX}` in
# `_blight_environment` is preserved.
BLIGHT_EXEC: Final[List[str]] = [
    "blight-exec",
    "--swizzle-path",
    "--guess-wrapped",
    "--",
]

BLIGHT_EXEC_MAKE: Final[List[str]] = [
    *BLIGHT_EXEC,
    "make",
]

GCLANG: Final[Path] = MATE_BDIST_LIBEXEC_PATH / "gclang"
GCLANGXX: Final[Path] = MATE_BDIST_LIBEXEC_PATH / "gclang++"
GET_BC: Final[Path] = MATE_BDIST_LIBEXEC_PATH / "get-bc"


_BASELINE_BLIGHT_ACTIONS = ["IgnoreWerror", "InjectFlags", "Record", "FindOutputs", "SkipStrip"]

_CHALLENGE_HOME: Final[Path] = Path("/home/challenge/")


@dataclass(frozen=True)
class CompilationError(MateError):
    """An exception denoting a compilation-phase-specific error."""

    compilation_id: str
    message: str
    challenge_id: Optional[str] = None

    @classmethod
    def from_process_error(
        cls,
        cpe: subprocess.CalledProcessError,
        compilation_id: str,
        challenge_id: Optional[str] = None,
    ) -> CompilationError:
        return cls(compilation_id, process_error_to_message(cpe), challenge_id)


@dataclass(frozen=True)
class _DockerCompileContext:
    """Encapsulates the state necessary to perform compilation steps in a Docker container."""

    client: DockerClient
    mate_bdist: DockerVolume
    mate_scratch: DockerVolume


@dataclass(frozen=True)
class _BlightContext:
    """Encapsulates the state necessary to perform ``blight``-instrumented compilations."""

    journal: Path
    outputs_store: Path


def _dir_has_makefile(dir_: Path) -> bool:
    """Given the path to a directory, return whether or not that directory contains a Make-based
    build that ``make`` recognizes by default."""
    return any((dir_ / mf).is_file() for mf in KNOWN_MAKEFILES)


class _Compiler:
    def __init__(self, compilation: db.Compilation, options: CompileOptions):
        # Our caller should put us into the compiling state, so check here.
        compilation_assert(
            compilation.state == CompilationState.Compiling,
            f"bad compilation state (expected compiling, got {compilation.state})",
            compilation_id=compilation.uuid,
        )

        self._compilation = compilation
        self._options = options
        self._new_artifacts: List[db.Artifact] = []

    def _register_artifact(
        self, *, kind: ArtifactKind, fileobj: IO[AnyStr], attributes: Dict[str, Any]
    ) -> db.Artifact:
        """Creates a new artifact and registers it with this compilation."""
        artifact = db.Artifact.create_with_object(kind, fileobj=fileobj, attributes=attributes)
        self._new_artifacts.append(artifact)
        return artifact

    def _raise(self, msg: str, *, cause: Optional[Exception] = None) -> NoReturn:
        """Raise an exception for this compilation, with an optional cause."""
        raise CompilationError(
            self._compilation.uuid,
            msg,
            self._compilation.challenge_id,
        ) from cause

    def _raise_from_process_error(self, cpe: subprocess.CalledProcessError) -> NoReturn:
        """Raise an exception for this compilation from the given ``CalledProcessError``."""
        raise CompilationError.from_process_error(
            cpe,
            self._compilation.uuid,
            self._compilation.challenge_id,
        )

    def _make_command(self) -> List[str]:
        """For ``make``-based builds: return a command line suitable for running ``make``, replete
        with various layers of instrumentation."""
        if self._options.make_targets is None:
            return BLIGHT_EXEC_MAKE
        else:
            make_steps = [
                shlex.join([*BLIGHT_EXEC_MAKE, target]) for target in self._options.make_targets
            ]
            return ["sh", "-c", "&& ".join(make_steps)]

    def _challenge_dockerfile_infer_compile_steps(self, target_dir: Path) -> List[str]:
        """Given a path to a CHESS-challenge-structured directory, detect the ``Dockerfile.build``
        (if any) and attempt to extract the steps necessary for a complete compilation from it."""
        logger.debug("attempting to infer individual build steps")

        # Check to see whether our challenge has a Dockerfile.build. It should,
        # but older ones might not; if it doesn't, fall back to the default
        # naive Makefile build (or custom targets, if supplied.)
        target_dockerfile = target_dir / "Dockerfile.build"
        if not target_dockerfile.is_file():
            logger.warning(f"no Dockerfile.build in {target_dir}; falling back")
            return self._make_command()

        # If we have a Dockerfile, parse it. We do this in two ways: we first
        # look for a special `ARG CONTAINER_PATH=...` that we use during command
        # translation, and then we look for the block of Docker commands between
        # `# CHESS BUILD START` and `# CHESS BUILD END` that we'll subsequently
        # translate.
        dockerfile_text = target_dockerfile.read_text()

        # Do our little `ARG CONTAINER_PATH=...` search.
        challenge_root = None
        try:
            dockerfile_cmds = dockerfile.parse_string(dockerfile_text)
            for docker_cmd in dockerfile_cmds:
                if docker_cmd.cmd != "arg":
                    continue

                if docker_cmd.value[0].startswith("CONTAINER_PATH"):
                    try:
                        _, challenge_root = docker_cmd.value[0].split("=", 1)
                    except ValueError:
                        self._raise(
                            "Dockerfile contains ARG CONTAINER_PATH, but without a default? "
                            f"raw={docker_cmd.original}"
                        )
                    break
        except dockerfile.GoParseError as e:
            self._raise(
                f"Dockerfile parse failed; body was: {dockerfile_text}",
                cause=e,
            )

        if challenge_root is not None:
            challenge_root = Path(challenge_root)
        else:
            logger.warning(
                "couldn't find a CONTAINER_PATH setting in the Dockerfile.build, "
                f"defaulting to {_CHALLENGE_HOME}"
            )
            challenge_root = _CHALLENGE_HOME

        logger.info(f"using {challenge_root=} to rebase all WORKDIR commands")

        # We're looking for the block of Docker commands between the `# CHESS BUILD START`
        # and `# CHESS BUILD END` markers. Use an explicit iterator to maintain our state.
        dockerfile_build_steps = ""
        lines = iter(dockerfile_text.splitlines(keepends=True))
        for line in lines:
            if line.startswith("# CHESS BUILD START"):
                break

        for line in lines:
            if line.startswith("# CHESS BUILD END"):
                break
            dockerfile_build_steps += line

        # Once we have our block of build steps, we need to reinterpret them as
        # shell commands. For the time being, we do this by parsing them with a
        # real Dockerfile parser, and then attempting to translate them.
        try:
            dockerfile_build_cmds = dockerfile.parse_string(dockerfile_build_steps)
        except dockerfile.GoParseError as e:
            self._raise(f"Dockerfile parse failed; fragment was: {dockerfile_build_steps}", cause=e)

        # For translation to shell commands, we only support two kinds of Docker
        # commands: RUN and WORKDIR.
        #
        # For RUN: RUNs can be either in shell-form or JSON form. We turn both
        # into a `blight exec`-wrapped command, with appropriate splitting/joining.
        #
        # For WORKDIR: These are a little hairy. Our copy of the challenge is in
        # a temporary directory, while the Dockerfile expects the challenge **source**
        # root to be `/home/challenge`. To handle these, we treat `/home/challenge`
        # as a sentinel prefix and rebase each WORKDIR on top of our temporary
        # directory's `challenge_src` instead. If the WORKDIR specified isn't in
        # `/home/challenge`, we treat that as an error for the time being.
        commands = []
        for docker_cmd in dockerfile_build_cmds:
            if docker_cmd.cmd == "run":
                # "JSON" form means that the command is written as a JSON array.
                # Otherwise, it's a shell-style string that we need to split.
                if docker_cmd.json:
                    cmd_args = docker_cmd.value
                else:
                    cmd_args = shlex.split(docker_cmd.value[0])

                commands.append(shlex.join([*BLIGHT_EXEC, *cmd_args]))
            elif docker_cmd.cmd == "workdir":
                workdir = Path(docker_cmd.value[0])
                if workdir == challenge_root:
                    effective_workdir = target_dir / "challenge_src"
                elif challenge_root in workdir.parents:
                    effective_workdir = (
                        target_dir / "challenge_src" / workdir.relative_to(challenge_root)
                    )
                else:
                    self._raise(
                        f"WORKDIR doesn't start with {challenge_root}: {workdir}",
                    )

                logger.debug(f"rebased WORKDIR: {workdir} -> {effective_workdir}")

                # The Dockerfile might be using `WORKDIR` to implicitly create directories,
                # so we have to explicitly create them on our end as well.
                commands.append(shlex.join(["mkdir", "-p", str(effective_workdir)]))
                commands.append(shlex.join(["cd", str(effective_workdir)]))
            else:
                logger.error(f"unsupported Docker command: {docker_cmd}; skipping")

        logger.debug(f"{commands=}")
        return ["sh", "-c", "&& ".join(commands)]

    def _find_challenge_src_dir(self, target_dir: Path) -> Path:
        """Given a directory that a CHESS-style challenge has been loaded into (via unarchiving or
        whatever other means), return the path to the challenge's ``challenge_src`` subdirectory."""

        # Same as _find_top_makefile_dir: strip off the first directory layer
        # if present, to handle the case where someone has submitted a challenge
        # directory itself rather than the contents of a challenge directory.
        target_children = list(target_dir.iterdir())
        if len(target_children) == 0:
            self._raise(f"empty archive expanded at {target_dir}; nothing to compile")
        elif len(target_children) == 1 and target_children[0].is_dir():
            target_dir /= target_children[0]

        target_dir /= "challenge_src"
        if not target_dir.is_dir():
            self._raise(
                f"{target_dir} is not a directory; malformed challenge?",
            )

        return target_dir

    def _find_top_makefile_dir(self, target_dir: Path) -> Path:
        """Given a directory that a compilation target has been loaded into (via unarchiving or
        whatever other means), return the path to the top-most directory that contains the target's
        Makefile."""

        # Start by assuming that our target directory is the makefile directory.
        makefile_dir = target_dir

        # Mild annoyance: it's common for people to archive a directory itself,
        # rather than all items within a directory. If our `target_dir`
        # has only a single entry and that entry is a directory, then we drill
        # down into it for the (presumed) build directory.
        target_children = list(target_dir.iterdir())
        if len(target_children) == 0:
            self._raise(
                f"empty archive expanded at {target_dir}; nothing to compile",
            )
        elif len(target_children) == 1 and target_children[0].is_dir():
            makefile_dir = target_children[0]

        logger.debug(f"starting at {makefile_dir}; searching {list(makefile_dir.iterdir())}")

        # Next, our two kinds of supported source trees: either with a top-level
        # Makefile, or with a `challenge_src` subdirectory that itself contains
        # a Makefile.
        if (makefile_dir / "challenge_src").is_dir():
            makefile_dir /= "challenge_src"

        # Do a sanity check for the presence of the Makefile itself.
        if _dir_has_makefile(makefile_dir):
            return makefile_dir

        # If we fail the sanity check above, then we're probably in a slightly
        # messed up challenge tree that contains at least one directory that in turn
        # contains a Makefile. We only go one level deep.
        logger.debug(f"{makefile_dir} does not contain a Makefile; checking the next layer")
        for dir_ in makefile_dir.iterdir():
            if _dir_has_makefile(dir_):
                logger.debug(f"found a makefile in {dir_}")
                return dir_

        self._raise(
            f"{makefile_dir} does not contain a Makefile or a child directory "
            f"with a Makefile: {list(makefile_dir.iterdir())}",
        )

    @contextmanager
    def _extract_bitcode(self, compile_output: Path) -> Iterator[IO[bytes]]:
        """Given the result of a ``blight``-instrumented compilation, attempt to extract the
        corresponding bitcode module.

        Handles both "embedded bitcode" and GLLVM-style bitcode instrumentation.

        Yields the contents of the module as a temporary file.
        """

        with TF() as bitcode:
            try:
                if self._options.experimental_embed_bitcode:
                    result = run(
                        [
                            LLVM_OBJCOPY,
                            f"--dump-section=.llvmbc={bitcode.name}",
                            str(compile_output),
                        ],
                        env={
                            **os.environ,
                            **llvm_wedlock_environment(),
                        },
                        shell=False,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    logger.debug(f"llvm-objcopy produced {result.stdout=} and {result.stderr=}")
                else:
                    # NOTE(ww): The -b switch is important here; without it, `get-bc`
                    # will attempt to produce a bitcode archive for static libraries
                    # instead of a unified bitcode module.
                    result = run(
                        [GET_BC, "-b", "-o", bitcode.name, str(compile_output)],
                        env={
                            **os.environ,
                            **llvm_wedlock_environment(),
                            **gllvm_environment(),
                        },
                        shell=False,
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    logger.debug(f"get-bc produced {result.stdout=} and {result.stderr=}")

                # NOTE(ww): Annoying: `bitcode` is a file-like here, but we can't yield
                # it directly because Python (incorrectly) thinks that its empty despite
                # being written to. Calling `seek` doesn't fix it, so we hack around it
                # by opening a separate handle.
                with open(bitcode.name, "rb") as io:
                    yield io
            except subprocess.CalledProcessError as e:
                self._raise_from_process_error(e)

    def _blight_environment(self, ctxt: _BlightContext) -> Environment:
        """Returns a mapping suitable for loading into the environment of a build process that
        should be instrumented by blight.

        ``ctxt`` provides appropriate destination filenames for the various actions run within
        blight.
        """
        injected_flags = list(REQUIRED_CFLAGS) + self._options.extra_compiler_flags

        cflags = " ".join(injected_flags)
        cxxflags = cflags

        cppflags = ""
        # If we're running a containerized compilation and the user hasn't
        # explicitly disabled the testbed, do it for them. This is intentionally
        # different from the non-container default, which is to not modify any
        # testbed-related macros at all unless explicitly requested.
        if self._options.containerized and self._options.testbed is None:
            cppflags = "-DNO_TESTBED"
        elif self._options.testbed is not None:
            if self._options.testbed:
                cppflags = "-UNO_TESTBED"
            else:
                cppflags = "-DNO_TESTBED"

        if self._options.experimental_embed_bitcode:
            cc, cxx = (CLANG, CLANGXX)
            extra_environment = Environment({})
            actions = ["EmbedBitcode", *_BASELINE_BLIGHT_ACTIONS]
        else:
            cc, cxx = (GCLANG, GCLANGXX)
            extra_environment = gllvm_environment()
            actions = _BASELINE_BLIGHT_ACTIONS

        return Environment(
            {
                "BLIGHT_WRAPPED_CC": str(cc),
                "BLIGHT_WRAPPED_CXX": str(cxx),
                "BLIGHT_JOURNAL_PATH": str(ctxt.journal),
                "BLIGHT_ACTIONS": ":".join(actions),
                "BLIGHT_ACTION_INJECTFLAGS": f"CFLAGS='{cflags}' CXXFLAGS='{cxxflags}' CPPFLAGS='{cppflags}'",
                "BLIGHT_ACTION_FINDOUTPUTS": f"store={ctxt.outputs_store}",
                "BLIGHT_LOGLEVEL": logging.getLevelName(logger.getEffectiveLevel()),
                **extra_environment,
            }
        )

    def _blight_tool(self, tool: Literal["blight-cc", "blight-c++"], artifact: db.Artifact) -> None:
        """Run the given individual blight tool (e.g., ``blight-cc``) with an appropriate
        environment on the given source file, returning a list of artifacts that are produced."""

        # NOTE(ww): We store the source file as a tempfile immediately below,
        # so grab its "real" (upload) name from the artifact's attributes here.
        # We'll use this "real" name to give the resultant bitcode and binary
        # artifacts more reasonable attributes, in turn.
        real_source_filename = Path(artifact.attributes["filename"])
        if tool == "blight-cc":
            source = artifact.persist_locally(suffix=".c")
        else:
            source = artifact.persist_locally(suffix=".cpp")

        with self._blight_context() as blight_ctxt, TF() as compile_output:
            try:
                result = run(
                    [tool, source.name, "-o", compile_output.name],
                    env={
                        **os.environ,
                        **self._blight_environment(blight_ctxt),
                        **llvm_wedlock_environment(),
                    },
                    shell=False,
                    cwd=source.parent,
                    capture_output=True,
                )

                self._register_artifact(
                    kind=ArtifactKind.CompileOutputCompileLog,
                    fileobj=io.StringIO(format_run_log(result)),
                    attributes={"filename": "compile.log"},
                )

                result.check_returncode()
            except subprocess.CalledProcessError as e:
                self._raise_from_process_error(e)

            compile_output_artifact = self._register_artifact(
                kind=ArtifactKind.CompileOutputBinary,
                fileobj=compile_output,
                attributes={"filename": real_source_filename.with_suffix(".bin").name},
            )

            with self._extract_bitcode(Path(compile_output.name)) as bitcode:
                self._register_artifact(
                    kind=ArtifactKind.CompileOutputBitcode,
                    fileobj=bitcode,
                    attributes={
                        "compile_output": compile_output_artifact.uuid,
                        "binary_filename": real_source_filename.with_suffix(".bin").name,
                        "filename": real_source_filename.with_suffix(".bc").name,
                    },
                )

    def _collect_blight_executable_output(self, output: Output) -> List[db.Artifact]:
        """Given an executable output from blight's ``FindOutputs`` action, collect artifacts for
        the executable itself and its corresponding bitcode."""
        artifacts = []
        logger.debug(f"recording a binary artifact for {output=}")
        with open(output.store_path, "rb") as io:
            compile_output_artifact = self._register_artifact(
                kind=ArtifactKind.CompileOutputBinary,
                fileobj=io,
                attributes={
                    "filename": output.path.name,
                },
            )
            artifacts.append(compile_output_artifact)

        logger.debug(f"recording a bitcode artifact for {output=}")
        with self._extract_bitcode(output.store_path) as bitcode:
            compile_output_bitcode_artifact = self._register_artifact(
                kind=ArtifactKind.CompileOutputBitcode,
                fileobj=bitcode,
                attributes={
                    "compile_output": compile_output_artifact.uuid,
                    "binary_filename": output.path.name,
                    "filename": output.path.with_suffix(".bc").name,
                },
            )
            artifacts.append(compile_output_bitcode_artifact)
        return artifacts

    def _collect_blight_library_output(self, output: Output) -> List[db.Artifact]:
        """Given a shared or static library from blight's ``FindOutputs`` action, collect artifacts
        for the library itself and its corresponding bitcode."""

        kind_map = {
            OutputKind.SharedLibrary: (
                ArtifactKind.CompileOutputSharedLibrary,
                ArtifactKind.CompileOutputSharedLibraryBitcode,
            ),
            OutputKind.StaticLibrary: (
                ArtifactKind.CompileOutputStaticLibrary,
                ArtifactKind.CompileOutputStaticLibraryBitcode,
            ),
        }

        binary_kind, bitcode_kind = kind_map[output.kind]

        artifacts = []
        logger.debug(f"recording a library artifact for {output=}")
        with open(output.store_path, "rb") as io:
            shared_library_artifact = self._register_artifact(
                kind=binary_kind,
                fileobj=io,
                attributes={
                    "filename": output.path.name,
                    "content_hash": output.content_hash,
                },
            )
            artifacts.append(shared_library_artifact)

        logger.debug(f"recording a bitcode artifact for {output=}")
        with self._extract_bitcode(output.store_path) as bitcode:
            shared_library_bitcode_artifact = self._register_artifact(
                kind=bitcode_kind,
                fileobj=bitcode,
                attributes={
                    "compile_output": shared_library_artifact.uuid,
                    "compile_output_content_hash": output.content_hash,
                    "library_filename": output.path.name,
                    "filename": output.path.with_suffix(".bc").name,
                },
            )
            artifacts.append(shared_library_bitcode_artifact)
        return artifacts

    def _collect_blight_outputs(self, journal: Path) -> List[db.Artifact]:
        """Given an path to a ``blight`` journal that contains results from the ``FindOutputs``
        action, collect all of the relevant binary and bitcode outputs into a list of artifacts."""

        # NOTE(ww): Observe that this method returns artifacts, unlike the other
        # methods on `_Compiler` (which add their artifacts to _new_artifacts directly).
        # This is intentional: callers of this method way want to add additional
        # attributes to each artifact before formally adding them to the artifact
        # list for the overall compilation.

        # An arbitrary build can produce multiple executables, so we collect all of them as
        # `CompileOutputBinary` artifacts. Each `CompileOutputBinary` then has a corresponding
        # `CompileOutputBitcode`, which we extract and associate with its `CompileOutputBinary`.
        # The user is responsible for selecting a particular executable to run the CPG build with.
        # Arbitrary builds can also produce multiple shared and static libraries; we collect
        # all of these and handle their corresponding bitcodes in a similar fashion.
        all_output_artifacts = []
        with journal.open() as io:
            for line in jsonlines.Reader(io):
                if "FindOutputs" not in line:
                    logger.debug("weird: blight journal entry is missing FindOutputs")
                    tool = line.get("Record")
                    if tool is not None:
                        logger.debug(f"entry's command: {tool['wrapped_tool']} {tool['args']}")
                    continue

                outputs = [Output(**o) for o in line["FindOutputs"]["outputs"]]
                output_artifacts_for_tool = []
                for output in outputs:
                    if output.store_path is None:
                        logger.debug(f"skipping {output=} because it doesn't have a store path")
                        continue

                    if output.kind == OutputKind.Executable:
                        executable_artifacts = self._collect_blight_executable_output(output)
                        output_artifacts_for_tool.extend(executable_artifacts)
                    elif output.kind in [OutputKind.SharedLibrary, OutputKind.StaticLibrary]:
                        library_artifacts = self._collect_blight_library_output(output)
                        output_artifacts_for_tool.extend(library_artifacts)
                    else:
                        continue
                all_output_artifacts.extend(output_artifacts_for_tool)

        return all_output_artifacts

    def _compile_single_target(self, artifact: db.Artifact) -> None:
        """Compile a single source file (C or C++), referenced within ``artifact``."""
        if artifact.attributes["filename"].endswith(".c"):
            self._blight_tool("blight-cc", artifact)
        else:
            self._blight_tool("blight-c++", artifact)

    def _copy_bitcode_target(self, artifact: db.Artifact) -> None:
        """Copy the input bitcode, referenced within ``artifact``, into an output artifact."""
        try:
            local_artifact = artifact.persist_locally()
            with local_artifact.open("rb") as io:
                self._register_artifact(
                    kind=ArtifactKind.CompileOutputBitcode,
                    fileobj=io,
                    attributes={"filename": local_artifact.name},
                )
        finally:
            local_artifact.unlink()

    def _makefile_build_with_blight(self, makefile_dir: Path) -> None:
        """Run a ``make``-based build, instrumented with blight.

        ``makefile_dir`` is assumed to be a directory that contains a ``Makefile`` or other filename
        that ``make`` recognizes.
        """
        with self._blight_context() as blight_ctxt:
            try:
                result = run(
                    self._make_command(),
                    env={
                        **os.environ,
                        **self._blight_environment(blight_ctxt),
                        **llvm_wedlock_environment(),
                    },
                    shell=False,
                    cwd=makefile_dir,
                    capture_output=True,
                )

                self._register_artifact(
                    kind=db.ArtifactKind.CompileOutputCompileLog,
                    fileobj=io.StringIO(format_run_log(result)),
                    attributes={"filename": "compile.log"},
                )

                result.check_returncode()
            except subprocess.CalledProcessError as e:
                self._raise_from_process_error(e)

            self._collect_blight_outputs(blight_ctxt.journal)

    def _compile_tarball_local(self, artifact: db.Artifact) -> None:
        """Run a ``make``-based program build stored within a tarball, referenced within
        ``artifact``.

        The build is performed locally, i.e. in the currently running ``mate-dist`` container.
        """
        local_target = artifact.persist_locally(suffix=".tar.gz")
        local_target_dir = TD()

        try:
            # TODO(ww): Maybe support other kinds of tarballs/archives? Worth it?
            with tarfile.open(local_target, "r:gz") as tar:
                tar.extractall(path=local_target_dir.name)
        except tarfile.TarError as e:
            self._raise(
                f"failed to open/extract tarball: {e}",
            )

        self._makefile_build_with_blight(self._find_top_makefile_dir(Path(local_target_dir.name)))

        local_target_dir.cleanup()
        local_target.unlink()

    def _compile_containerized(
        self,
        docker_ctxt: _DockerCompileContext,
        blight_ctxt: _BlightContext,
        image: str,
        compile_command: List[str],
        compile_dir: Path,
    ) -> List[db.Artifact]:
        # NOTE(ww): Docker's REST endpoint for waiting on a container can fail with
        # a 404 if the container completely explodes on startup, e.g. if the exec*()
        # syscall itself fails due to an irrecoverable dynamic linker error.
        try:
            logstream = self._docker_container_run(
                client=docker_ctxt.client,
                image=image,
                volumes={
                    docker_ctxt.mate_bdist.name: docker_bind(MATE_BDIST_ROOT, mode="ro"),
                    docker_ctxt.mate_scratch.name: docker_bind(MATE_SCRATCH),
                },
                command=compile_command,
                working_dir=compile_dir,
                environment=Environment(
                    {
                        **mate_environment(llvm_wedlock=True),
                        **self._blight_environment(blight_ctxt),
                    }
                ),
            )

            logs = b"\n".join(line for line in logstream)
            self._register_artifact(
                kind=ArtifactKind.CompileOutputCompileLog,
                fileobj=io.BytesIO(logs),
                attributes={"filename": "containerized-compile.log"},
            )
        except Exception as e:
            self._raise(f"containerized run failed: {e}", cause=e)

        logger.debug(f"Container exited; {logs=}")

        return self._collect_blight_outputs(blight_ctxt.journal)

    def _compile_tarball_containerized(self, artifact: db.Artifact) -> None:
        """Run a ``make``-based program build stored within a tarball, referenced within
        ``artifact``.

        The build is performed in an ephemeral container whose image name is specified in
        ``self._options.docker_image``.
        """

        scratch_dir = Path(TD(dir=MATE_SCRATCH).name)

        scratch_src = scratch_dir / "src"
        # Copy our target into the scratch volume, which we'll mount into the
        # target container for compilation. We'll mount the volume at the same
        # path as MATE_SCRATCH, so any paths under it will remain correct.
        # N.B.: Observe that we use temporary directories and files throughout
        # here, including on the scratch volume. **This is intentional**:
        # these files and directories are deleted once the surrounding task
        # exits, meaning that we never keep intermediate state on the scratch
        # volume for longer than absolutely necessary.
        local_target = artifact.persist_locally(suffix=".tar.gz")
        try:
            with tarfile.open(local_target, "r:gz") as tar:
                tar.extractall(path=scratch_src)
        except tarfile.TarError as e:
            self._raise(
                "failed to open/extract tarball",
                cause=e,
            )

        blight_dir = scratch_dir / "_blight"
        blight_dir.mkdir()

        with self._docker_context() as docker_ctxt, self._blight_context(
            base=blight_dir
        ) as blight_ctxt:
            try:
                image = docker_ctxt.client.images.get(self._options.docker_image)
            except docker.errors.ImageNotFound as e:
                self._raise(
                    f"No Docker image named {self._options.docker_image} is available",
                    cause=e,
                )
            except docker.errors.DockerException as e:
                self._raise(
                    "unexpected error response from docker",
                    cause=e,
                )

            compile_outputs = self._compile_containerized(
                docker_ctxt,
                blight_ctxt,
                image,
                self._make_command(),
                self._find_top_makefile_dir(scratch_src),
            )

            # Add some additional attributes to each compilation output;
            # the CPG build pipeline will check these to special-case its behavior
            # for containerized runs of the recompilation components.
            for compile_output in compile_outputs:
                compile_output.attributes.update(
                    {
                        "containerized": True,
                        "image": self._options.docker_image,
                    }
                )

    def _compile_tarball(self, artifact: db.Artifact) -> None:
        """Run a ``make``-based program build stored within a tarball, referenced within
        ``artifact``."""

        if self._options.containerized:
            self._compile_tarball_containerized(artifact)
        else:
            self._compile_tarball_local(artifact)

    @contextmanager
    def _explode_zip_artifact(self, artifact: db.Artifact) -> Iterator[Path]:
        """Given an artifact that contains a ZIP archive, explode said archive into a local
        temporary directory and yield it.

        Destroys the temporary directory on cleanup.
        """
        local_artifact = artifact.persist_locally(suffix=".zip")
        local_dir = TD()

        try:
            with zipfile.ZipFile(local_artifact, mode="r") as zip_:
                for member in zip_.infolist():
                    # NOTE(ww): Python's zipfile doesn't preserve member permissions. Our workaround
                    # is to extract each member individually, confirm that they came from a
                    # UNIX system (see 4.4.4.2 in the APPNOTE.TXT linked below), and then use
                    # the mode_t stored in the member's external attributes to reconstruct the
                    # permissions. This is tedious, but without it we end up stripping
                    # executable and other permissions that archive's members have.
                    # See: https://bugs.python.org/issue15795
                    # See: https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT
                    local_member = zip_.extract(member, path=local_dir.name)
                    if member.create_system == 3:
                        Path(local_member).chmod(member.external_attr >> 16)
                    else:
                        logger.debug(
                            f"unexpected (non-UNIX) ZIP member disposition: {member.create_system}"
                        )

            yield Path(local_dir.name)
        except zipfile.BadZipFile as e:
            self._raise(
                "failed to open/extract zipfile",
                cause=e,
            )
        finally:
            local_dir.cleanup()
            local_artifact.unlink()

    @contextmanager
    def _blight_context(self, *, base: Optional[Path] = None) -> Iterator[_BlightContext]:
        with TF(suffix=".jsonl", dir=base) as journal, TD(dir=base) as outputs_store:
            journal_path = Path(journal.name)
            outputs_store_path = Path(outputs_store)

            ctxt = _BlightContext(journal=journal_path, outputs_store=outputs_store_path)
            yield ctxt
            self._register_artifact(
                kind=ArtifactKind.BlightJournal,
                fileobj=journal,
                attributes={"filename": "blight-journal.jsonl"},
            )

    @contextmanager
    def _docker_context(self) -> Iterator[_DockerCompileContext]:
        if not DOCKER_SOCKET.is_socket():
            self._raise(
                "containerized compilation specified but the Docker socket is not available",
            )

        client = DockerClient(base_url=f"unix://{DOCKER_SOCKET}")

        try:
            bdist_volume = docker_volume_by_label(client, MATE_BDIST_DOCKER_VOLUME)
            if bdist_volume is None:
                self._raise(
                    f"failed to locate a bdist volume for container use: {MATE_BDIST_DOCKER_VOLUME}",
                )
            scratch_volume = docker_volume_by_label(client, MATE_SCRATCH_DOCKER_VOLUME)
            if scratch_volume is None:
                self._raise(
                    f"failed to locate a scratch volume for container use {MATE_SCRATCH_DOCKER_VOLUME}",
                )
        except docker.errors.DockerException as e:
            self._raise(
                "unexpected error response from docker",
                cause=e,
            )

        try:
            yield _DockerCompileContext(
                client=client, mate_bdist=bdist_volume, mate_scratch=scratch_volume
            )
        finally:
            client.close()

    def _docker_container_run(
        self,
        *,
        client: DockerClient,
        image: DockerImage,
        volumes: Dict[str, Dict[str, str]],
        command: List[str],
        working_dir: Path,
        environment: Environment,
    ) -> Iterator[bytes]:
        return client.containers.run(
            image,
            name=f"mate-compile-{uuid.uuid4().hex}",
            remove=True,
            volumes=volumes,
            working_dir=str(working_dir),
            detach=False,
            environment=environment,
            user=0,  # root
            command=command,
            stream=True,
            stdout=True,
            stderr=True,
        )

    def _compile_brokered_challenge_containerized(self, artifact: db.Artifact) -> None:
        """Run a program build for a brokered challenge within a dedicated Docker container."""

        scratch_dir = Path(TD(dir=MATE_SCRATCH).name)

        # Copy our target into the scratch volume, which we'll mount into the
        # target container for compilation. We'll mount the volume at the same
        # path as MATE_SCRATCH, so any paths under it will remain correct.
        # N.B.: Observe that we use temporary directories and files throughout
        # here, including on the scratch volume. **This is intentional**:
        # these files and directories are deleted once the surrounding task
        # exits, meaning that we never keep intermediate state on the scratch
        # volume for longer than absolutely necessary.
        with self._explode_zip_artifact(artifact) as local_target_dir:
            shutil.copytree(local_target_dir, scratch_dir)

        blight_dir = scratch_dir / "_blight"
        blight_dir.mkdir()

        with self._docker_context() as docker_ctxt, self._blight_context(
            base=blight_dir
        ) as blight_ctxt:
            # NOTE(ww): The `image` key is always present in this case, but can be
            # `None` if the challenge broker doesn't give us a suitable Docker image.
            if artifact.attributes["image"] is None:
                self._raise(
                    f"requested containerized challenge compilation for {artifact.uuid=}, "
                    "but no associated Docker image; probably an error in the metadata supplied "
                    "by the challenge broker",
                )
            try:
                image = docker_image(docker_ctxt.client, artifact.attributes["image"])
            except docker.errors.DockerException as e:
                self._raise(
                    "unexpected error response from docker",
                    cause=e,
                )

            if self._options.containerized_infer_build:
                # If we're inferring our individual build steps from the challenge's
                # ``Dockerfile.build``, then we need to be in the challenge's
                # ``challenge_src`` subdirectory in order for those steps to run
                # correctly.
                compile_dir = self._find_challenge_src_dir(scratch_dir)
                compile_command = self._challenge_dockerfile_infer_compile_steps(scratch_dir)
            else:
                # Otherwise, we're looking for the first Makefile we find and
                # running it in the directory we find it in.
                compile_dir = self._find_top_makefile_dir(scratch_dir)
                compile_command = self._make_command()

            compile_outputs = self._compile_containerized(
                docker_ctxt, blight_ctxt, image, compile_command, compile_dir
            )

            # Add some additional attributes to each compilation output;
            # the CPG build pipeline will check these to special-case its behavior
            # for containerized runs of the recompilation components.
            for compile_output in compile_outputs:
                compile_output.attributes.update(
                    {
                        "containerized": True,
                        "image": artifact.attributes["image"],
                        "target_id": artifact.attributes["target_id"],
                    }
                )

    def _compile_brokered_challenge_local(self, artifact: db.Artifact) -> None:
        """Run a program build locally for a brokered challenge.

        **IMPORTANT**: This is a vestigial workflow; most brokered challenges should go through
        the "containerized" challenge compilation pipeline.
        """

        with self._explode_zip_artifact(artifact) as local_target_dir:
            self._makefile_build_with_blight(self._find_top_makefile_dir(local_target_dir))

    def _compile_brokered_challenge(self, artifact: db.Artifact) -> None:
        """Run a program build for a brokered challenge.

        The underlying build may be performed locally or in a dedicated container, depending on the
        compilation options.
        """

        if self._options.containerized:
            self._compile_brokered_challenge_containerized(artifact)
        else:
            self._compile_brokered_challenge_local(artifact)

    def compile_artifact(self, artifact: db.Artifact) -> None:
        if artifact.kind == ArtifactKind.CompileTargetSingle:
            self._compile_single_target(artifact)
        elif artifact.kind == ArtifactKind.CompileTargetBitcode:
            # CompileTargetBitcode artifacts are essentially phony compilation targets,
            # since they've already been compiled. The only thing we do here is
            # make a copy of our input artifact and turn it into the output.
            self._copy_bitcode_target(artifact)
        elif artifact.kind == ArtifactKind.CompileTargetTarball:
            self._compile_tarball(artifact)
        elif artifact.kind == ArtifactKind.CompileTargetBrokeredChallenge:
            self._compile_brokered_challenge(artifact)
        else:
            compilation_assert(
                False,
                f"asked to compile {artifact.kind=}, which wasn't expected here",
                compilation_id=self._compilation.uuid,
            )


def compile_artifact(
    artifact: db.Artifact,
    compilation: db.Compilation,
    session: orm.Session,
    options: CompileOptions,
) -> None:
    """Run the MATE compilation pipeline for the given artifact, which is assumed to be one of the
    "source" compile targets (i.e., any except for JSONL).

    The compilation pipeline produces a series of artifacts, each of which is associated with the
    given ``db.Compilation`` via the supplied session.
    """

    compilation.transition_to_state(CompilationState.Compiling)
    compilation.artifacts.append(artifact)
    session.add(compilation)
    session.commit()

    compiler = _Compiler(compilation, options)
    try:
        compiler.compile_artifact(artifact)

        compilation.transition_to_state(CompilationState.Compiled)
    except (CompilationError, CompilationAssertionError) as e:
        compilation.transition_to_state(CompilationState.Failed)
        # NOTE(ww): We don't handle this exception anywhere in the server; propagate
        # it here merely to ensure that the task is marked as a failure rather than
        # a success.
        raise e
    finally:
        compilation.artifacts.extend(compiler._new_artifacts)
        session.add_all(compiler._new_artifacts)
        session.add(compilation)
        session.commit()
