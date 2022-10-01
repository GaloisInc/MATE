from __future__ import annotations

import dataclasses
import enum
import json
import logging
import os
import shutil
import subprocess
import tarfile
import uuid
import zipfile
from contextlib import contextmanager
from os.path import relpath
from pathlib import Path
from resource import RLIM_INFINITY, RLIMIT_AS, setrlimit
from tempfile import NamedTemporaryFile as TF
from tempfile import TemporaryDirectory as TD
from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    Dict,
    Final,
    Iterable,
    Iterator,
    List,
    Optional,
    Tuple,
    Type,
)

import jsonlines
import jsonschema
import yaml
from elftools.elf.elffile import ELFFile
from sqlalchemy import orm
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import text

from mate.assertions import BuildAssertionError, build_assert
from mate.build import signatures
from mate.build.common import llvm_wedlock_environment, run
from mate.build.tob_chess_utils.elf import all_vtables
from mate.build.tob_chess_utils.tools import quotidian
from mate.config import (
    LLVM_LINK,
    LLVM_OPT,
    MATE_BDIST_DEFAULT_SIGNATURES,
    MATE_BDIST_LIB_PATH,
    MATE_BDIST_ROOT,
)
from mate_common.config import MATE_ASSERTIONS
from mate_common.error import MateError, process_error_to_message
from mate_common.models.artifacts import ArtifactKind
from mate_common.models.builds import BuildOptions, BuildState
from mate_common.models.bytes import Bytes, Gibibytes, gb_to_bytes, mb_to_bytes
from mate_common.models.cpg_types import EdgeKind, NodeKind
from mate_common.schemata import EDGE_SCHEMA, NODE_SCHEMA, NODE_SCHEMA_BY_KIND, SIGNATURES_SCHEMA
from mate_common.utils import grouper, stateless_io
from mate_query import cfl, db

if TYPE_CHECKING:
    from mate_query.cpg.models import Edge, Node
    from mate_query.db import Graph as CPG


logger = logging.getLogger(__name__)

_MAX_VIRTUAL_MEMORY: Final[Bytes] = gb_to_bytes(Gibibytes(32))

# The number of rows to insert into the CPG per bulk update.
# NOTE(ww): This number was derived experimentally on my laptop, and is probably
# not optimal (either on a server or more generally). However, the are probably
# other bottlenecks (like all of the dictionary accessing we do to build each
# mapped object) that need to be eliminated before we determine an actually
# optimal value here.
_CPG_INSERTION_CHUNK_SIZE: Final[int] = 2_048


@dataclasses.dataclass(frozen=True)
class CPGBuildError(MateError):
    """An exception denoting a CPG build-specific error during a MATE build."""

    build_id: str
    message: str

    @classmethod
    def from_process_error(cls, cpe: subprocess.CalledProcessError, build_id: str) -> CPGBuildError:
        return cls(build_id, process_error_to_message(cpe))


def limit_virtual_memory(max_virtual_memory: Bytes = _MAX_VIRTUAL_MEMORY) -> None:
    # The tuple below is of the form (soft limit, hard limit). Limit only
    # the soft part so that the limit can be increased later (setting also
    # the hard limit would prevent that).
    # When the limit cannot be changed, setrlimit() raises ValueError.
    setrlimit(RLIMIT_AS, (max_virtual_memory, RLIM_INFINITY))


# NOTE(ww): Subclassing Path doesn't work here, unlike subclassing str. Why?
@enum.unique
class _MateBuildLibrary(enum.Enum):
    """An enumeration of native shared objects that are called explicitly during one or more parts
    of a MATE build."""

    Nomina: Path = MATE_BDIST_LIB_PATH / "LLVMNomina.so"
    SoufflePA: Path = MATE_BDIST_LIB_PATH / "libSoufflePA.so"
    PAPass: Path = MATE_BDIST_LIB_PATH / "libPAPass.so"
    Mate: Path = MATE_BDIST_LIB_PATH / "libMATE.so"


class _Builder:
    """An abstraction for the internal steps in a CPG build."""

    # NOTE(ww): I don't like builder-style object patterns, but in this case
    # I think it's the cleanest way to wrangle the multiple steps that a CPG
    # build jumps through.

    def __init__(self, build: db.Build, options: BuildOptions) -> None:
        # Our caller should put us into the building state, so check here.
        build_assert(
            build.state == BuildState.Building,
            f"bad build state (expected building, got {build.state})",
            build_id=build.uuid,
        )
        self._build = build
        self._options = options
        self._new_artifacts: List[db.Artifact] = []

    def _sanitizer_environment(self) -> Dict[str, str]:
        """Set LLVM sanitizer-relevant environment variables for C(++) subprocesses."""
        # LD_PRELOAD is the official way to use sanitizers on shared libraries
        # invoked via non-asan-enabled executables (`opt`, in this case).
        #
        # https://github.com/google/sanitizers/wiki/AddressSanitizer
        env = dict(os.environ)
        sanitizers_env = env.get("MATE_SANITIZERS")
        if sanitizers_env is None:
            return env

        logger.debug(f"Running calls to `opt` with sanitizers: {sanitizers_env}.")
        sanitizers = sanitizers_env.split(",")

        # Raises false alarms in third-party libraries
        if "address" in sanitizers:
            env["ASAN_OPTIONS"] = "detect_leaks=0:new_delete_type_mismatch=0"

        _LD_PRELOAD_SO = {
            "address": Path("/usr/lib/x86_64-linux-gnu/libasan.so.5"),
            "thread": Path("/usr/lib/x86_64-linux-gnu/libtsan.so.0"),
            "undefined": Path("/usr/lib/x86_64-linux-gnu/libubsan.so.1"),
        }
        for path in _LD_PRELOAD_SO.values():
            build_assert(
                path.exists(),
                f"Unexpected operating environment! Couldn't find {path}.",
                build_id=self._build.uuid,
            )

        ld_preloads = [
            _LD_PRELOAD_SO[sanitizer]
            for sanitizer in sanitizers
            if _LD_PRELOAD_SO.get(sanitizer) is not None
        ]
        build_assert(
            len(ld_preloads) == 1,
            f"Can't load multiple libraries in LD_PRELOAD: {ld_preloads}",
            build_id=self._build.uuid,
        )

        env["LD_PRELOAD"] = str(ld_preloads[0])
        return env

    def _dynamic_linkages_for_binary(self, binary_artifact: db.Artifact) -> List[str]:
        """Returns a list of dynamic linkages for the given binary artifact, extracted from the
        underlying ELF's ``PT_DYNAMIC`` segment."""
        binary = binary_artifact.persist_locally(suffix=".bin")
        with binary.open("rb") as io:
            elf = ELFFile(io)

            # Fully static ELFs don't have a PT_DYNAMIC, so do nothing if we don't have one.
            dynamic_segment = next(
                (s for s in elf.iter_segments() if s["p_type"] == "PT_DYNAMIC"), None
            )
            if dynamic_segment is None:
                return []

            return [d.needed for d in dynamic_segment.iter_tags(type="DT_NEEDED")]

    def _merge_library_bitcode(self, input_bc: Path) -> IO[bytes]:
        """Given a path to some LLVM bitcode, search our current build's compilation stage for other
        bitcode artifacts corresponding to static and dynamic linkages. Merge these bitcode
        artifacts into the input bitcode using ``llvm-link``, producing a "merged" result bitcode
        that doesn't require those linkages.

        Returns the merged bitcode as a temporary file. The caller is responsible for cleanup.
        """
        merged_bc = TF(suffix=".bc")

        # Collect all artifacts for the build's compilation that correspond to
        # shared and static libraries produced during the compilation.
        compilation = self._build.compilation
        library_bitcode_map = {
            a.attributes["library_filename"]: a
            for a in compilation.artifacts
            if a.kind
            in [
                ArtifactKind.CompileOutputSharedLibraryBitcode,
                ArtifactKind.CompileOutputStaticLibraryBitcode,
            ]
        }

        # If we don't have bitcode for any libraries, then we have nothing to merge.
        # Just copy the input bitcode and return. Observe that this circumvents
        # recording a `BuildOutputMergedBitcode`, which is intentional.
        if len(library_bitcode_map) == 0:
            logger.debug("bitcode merge requested, but no libraries to merge")
            with stateless_io(merged_bc) as merged_bc, input_bc.open("rb") as io:
                shutil.copyfileobj(io, merged_bc)
            return merged_bc

        logger.debug(f"{library_bitcode_map=}")

        # Filter the collected bitcodes to just those needed for linking the
        # current build's target. This part is *extremely* error-prone:
        # we get the binary that the current target bitcode was generated from,
        # and collect its linkages from its `PT_DYNAMIC` segment.
        # We then loosely match those linkages against the basenames of all
        # of the libraries that we have bitcode modules for.
        # TODO(ww): This handling could be much, much more intelligent.
        # Maybe re-use some blight APIs here.
        target_binary_artifact = next(
            a
            for a in compilation.artifacts
            if a.uuid == self._build.bitcode_artifact.attributes["compile_output"]
        )
        linkages = self._dynamic_linkages_for_binary(target_binary_artifact)

        to_be_linked_bc_artifacts = {}
        for linkage in linkages:
            resolved_lib = next(
                (lib for lib in library_bitcode_map.keys() if lib.startswith(linkage)), None
            )
            if resolved_lib is not None:
                logger.debug(f"paired {linkage} to {resolved_lib}")
                candidate = library_bitcode_map[resolved_lib]
                content_hash = candidate.attributes["compile_output_content_hash"]
                # NOTE(ww): We have to deduplicate multiple linkages of the same library
                # here, since llvm-link is more strict about merging duplicate bitcodes
                # than the system linker is about redundant linkages.
                if content_hash not in to_be_linked_bc_artifacts:
                    to_be_linked_bc_artifacts[content_hash] = candidate

        logger.debug(f"bitcode merge: identified dependencies: {to_be_linked_bc_artifacts}")

        # Similar to above: if we have library bitcodes but this particular binary
        # doesn't need any of them, return early without doing a (no-op) merge or
        # recording a redundant artifact.
        if len(to_be_linked_bc_artifacts) == 0:
            logger.debug("bitcode merge requested but this binary doesn't need any libraries")
            with stateless_io(merged_bc) as merged_bc, input_bc.open("rb") as io:
                shutil.copyfileobj(io, merged_bc)
            return merged_bc

        # Persist each of the to-be-linked library bitcodes locally, so that
        # we can actually perform the merge step.
        to_be_linked_bcs = [
            a.persist_locally(suffix=".bc") for a in to_be_linked_bc_artifacts.values()
        ]

        llvm_link_args: List[str] = []
        if self._options.merge_bitcode_only_needed:
            llvm_link_args.append("-only-needed")
        if self._options.merge_bitcode_internalize:
            llvm_link_args.append("-internalize")

        # Finally, merge.
        try:
            run(
                [
                    LLVM_LINK,
                    *llvm_link_args,
                    "-o",
                    merged_bc.name,
                    input_bc,
                    *to_be_linked_bcs,
                ],
                env={**os.environ, **llvm_wedlock_environment()},
                shell=False,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            raise CPGBuildError.from_process_error(e, build_id=self._build.uuid)

        with stateless_io(merged_bc) as merged_bc:
            self._new_artifacts.append(
                db.Artifact.create_with_object(
                    kind=ArtifactKind.BuildOutputMergedBitcode,
                    fileobj=merged_bc,
                    attributes={"filename": "merged.bc"},
                )
            )

        return merged_bc

    def _canonicalize_bitcode(self, input_bc: Path) -> IO[bytes]:
        """Given a path to some LLVM bitcode, attempt to canonicalize it using our "Nomina" LLVM
        pass.

        Returns the canonicalized version as a temporary file. The caller is responsible for
        cleanup.
        """

        canonical_bc = TF(suffix=".bc")
        try:
            run(
                [
                    LLVM_OPT,
                    "-load",
                    _MateBuildLibrary.Nomina.value,
                    "-nomina",
                    input_bc,
                    "-o",
                    canonical_bc.name,
                ],
                env={
                    **os.environ,
                    **llvm_wedlock_environment(),
                    **self._sanitizer_environment(),
                },
                shell=False,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            raise CPGBuildError.from_process_error(e, build_id=self._build.uuid)

        with stateless_io(canonical_bc) as canonical_bc:
            # Add our canonicalized bitcode as an artifact, and rewind it so that we can reuse it.
            self._new_artifacts.append(
                db.Artifact.create_with_object(
                    kind=ArtifactKind.BuildOutputCanonicalBitcode,
                    fileobj=canonical_bc,
                    attributes={"filename": "canonical.bc"},
                )
            )

        return canonical_bc

    @contextmanager
    def _build_pts_signatures(self) -> Iterator[IO[str]]:
        """Convert both the default and user-supplied points-to signatures to JSON for ingestion by
        the fact generator.

        Yields the JSON-formatted signatures as a temporary file. The caller is **not** responsible
        for cleanup.
        """
        with open(MATE_BDIST_DEFAULT_SIGNATURES) as yaml_signatures, TF(
            mode="w+", suffix=".json"
        ) as json_signatures:
            try:
                default_sigs = yaml.safe_load(yaml_signatures)
            except yaml.YAMLError as e:
                raise CPGBuildError(self._build.uuid, str(e))

            try:
                jsonschema.validate(instance=default_sigs, schema=SIGNATURES_SCHEMA)
            except jsonschema.exceptions.ValidationError as e:
                raise CPGBuildError(self._build.uuid, str(e))

            signatures = {sig["name"]: sig["signatures"] for sig in default_sigs}

            if self._options.signatures:
                try:
                    jsonschema.validate(instance=self._options.signatures, schema=SIGNATURES_SCHEMA)
                except jsonschema.exceptions.ValidationError as e:
                    raise CPGBuildError(self._build.uuid, str(e))

                signatures.update(
                    {sig["name"]: sig["signatures"] for sig in self._options.signatures}
                )

            json_signatures.write(json.dumps(signatures))
            json_signatures.flush()

            with stateless_io(json_signatures) as json_signatures:
                self._new_artifacts.append(
                    db.Artifact.create_with_object(
                        kind=ArtifactKind.BuildOutputSignatures,
                        fileobj=json_signatures,
                        attributes={"filename": "signatures.json"},
                    )
                )

            yield json_signatures

    def _build_mate_jsonl(self, canonical_bc: Path) -> IO[str]:
        """Given a path to some canonicalized LLVM bitcode, attempt to run the MATE JSONL phase of
        CPG construction.

        Returns the MATE JSONL as a temporary file. The caller is responsible for cleanup.
        """
        mate_jsonl = TF(mode="w+", suffix=".jsonl")
        with TD() as datalog_debug_dir_base, self._build_pts_signatures() as signatures:
            datalog_debug_dir = Path(datalog_debug_dir_base) / "pa_results"
            try:
                run(
                    [
                        LLVM_OPT,
                        "-load",
                        _MateBuildLibrary.SoufflePA.value,
                        "-load",
                        _MateBuildLibrary.PAPass.value,
                        "-load",
                        _MateBuildLibrary.Mate.value,
                        "-disable-output",
                        "-signatures={}".format(signatures.name),
                        "-time-passes={}".format(str(self._options.time_llvm_passes).lower()),
                        "-ast-graph-writer",
                        "-pretty-llvm-value={}".format(
                            str(self._options.llvm_pretty_strings).lower()
                        ),
                        "-datalog-pointer-analysis={}".format(
                            str(self._options.do_pointer_analysis).lower()
                        ),
                        "-mem-dep-edges={}".format(
                            str(self._options.llvm_memory_dependence).lower()
                        ),
                        "-control-dep-edges={}".format(
                            str(self._options.control_dependence).lower()
                        ),
                        "-datalog-analysis={}".format(str(self._options.pointer_analysis).lower()),
                        "-debug-datalog={}".format(
                            str(self._options.debug_pointer_analysis).lower()
                        ),
                        "-debug-datalog-dir={}".format(datalog_debug_dir),
                        "-check-datalog-assertions={}".format(str(MATE_ASSERTIONS).lower()),
                        "-context-sensitivity={}".format(self._options.context_sensitivity.value),
                        "-cpg-file",
                        mate_jsonl.name,
                        canonical_bc,
                    ],
                    env={
                        **os.environ,
                        **llvm_wedlock_environment(),
                        **self._sanitizer_environment(),
                    },
                    shell=False,
                    check=True,
                    capture_output=True,
                    preexec_fn=lambda: limit_virtual_memory(
                        mb_to_bytes(self._options.memory_limit_mb)
                    ),
                )
            except subprocess.CalledProcessError as e:
                raise CPGBuildError.from_process_error(e, build_id=self._build.uuid)
            finally:
                if self._options.debug_pointer_analysis:
                    with TD() as archive_dir:
                        shutil.make_archive(
                            # base_name
                            f"{archive_dir}/debug_pointer_analysis",
                            # format
                            "gztar",
                            # root_dir
                            datalog_debug_dir_base,
                            # base_dir
                            "pa_results",
                            logger=logger,
                        )
                        with stateless_io(
                            open(f"{archive_dir}/debug_pointer_analysis.tar.gz", "rb"),
                        ) as archive:
                            self._new_artifacts.append(
                                db.Artifact.create_with_object(
                                    kind=ArtifactKind.BuildOutputDebugPointerAnalysis,
                                    fileobj=archive,
                                    attributes={"filename": "debug_pointer_analysis.tar.gz"},
                                )
                            )

        if self._options.debug_mate_jsonl:
            with stateless_io(mate_jsonl) as mate_jsonl:
                self._new_artifacts.append(
                    db.Artifact.create_with_object(
                        kind=ArtifactKind.BuildOutputMateJSONL,
                        fileobj=mate_jsonl,
                        attributes={"filename": "mate.jsonl"},
                    )
                )

        return mate_jsonl

    def _build_quotidian_jsonl(self, artifact: db.Artifact, canonical_bc: Path) -> IO[str]:
        """Given a path to some canonicalized LLVM bitcode, attempt to run the "quotidian" (i.e.,
        ToB) JSONL phase of CPG generation.

        Returns the quotidian JSONL as a temporary file. The caller is responsible for cleanup.
        """

        options = quotidian.QuotidianOptions(
            build=self._build,
            image=artifact.attributes.get("image"),
            line_program=self._options.line_program_source_info,
            extra_linker_flags=self._options.extra_linker_flags,
        )

        try:
            # TODO(ww): This temporary file can definitely be avoided.
            # We should just yield each quotidian record directly.
            quotidian_jsonl = TF(mode="w+", suffix=".jsonl")
            (records, quotidian_artifacts) = quotidian.quotidian(
                canonical_bc,
                bdist_root=MATE_BDIST_ROOT,
                options=options,
                margin_options={
                    "omit_translation_unit_nodes": not self._options.translation_unit_nodes,
                    "omit_arg_edges": not self._options.argument_edges,
                    "sanity_checks": MATE_ASSERTIONS,
                },
            )
        except quotidian.QuotidianError as e:
            raise CPGBuildError(options.build.uuid, str(e))

        with stateless_io(quotidian_jsonl) as quotidian_jsonl:
            for record in records:
                print(json.dumps(record), file=quotidian_jsonl)

        self._new_artifacts.extend(quotidian_artifacts)

        if self._options.debug_quotidian_jsonl:
            with stateless_io(quotidian_jsonl) as quotidian_jsonl:
                self._new_artifacts.append(
                    db.Artifact.create_with_object(
                        kind=ArtifactKind.BuildOutputQuotidianJSONL,
                        fileobj=quotidian_jsonl,
                        attributes={"filename": "quotidian.jsonl"},
                    )
                )

        return quotidian_jsonl

    def _build_cpg_jsonl(self, mate_jsonl: IO[str], quotidian_jsonl: Optional[IO[str]]) -> IO[str]:
        """Merge the given MATE and quotidian JSONL fileobjs into a single CPG JSONL, storing it as
        an artifact.

        Returns the CPG JSONL as a temporary file. The caller is responsible for cleanup.
        """
        cpg_jsonl = TF(mode="w+", suffix=".jsonl")

        with stateless_io(cpg_jsonl) as cpg_jsonl:
            shutil.copyfileobj(mate_jsonl, cpg_jsonl)

            if quotidian_jsonl is not None:
                shutil.copyfileobj(quotidian_jsonl, cpg_jsonl)

        if self._options.debug_cpg_jsonl:
            with stateless_io(cpg_jsonl) as cpg_jsonl:
                self._new_artifacts.append(
                    db.Artifact.create_with_object(
                        kind=ArtifactKind.BuildOutputCpgJSONL,
                        fileobj=cpg_jsonl,
                        attributes={"filename": "cpg.jsonl"},
                    )
                )

        return cpg_jsonl

    def _process_cpg_signatures(self, graph: db.Graph, session: orm.Session) -> None:
        """Processes the previously loaded signatures for this ``db.Graph``, adding any appropriate
        nodes and edges."""
        signature_artifact = next(
            (a for a in self._new_artifacts if a.kind == ArtifactKind.BuildOutputSignatures),
            None,
        )

        # NOTE(ww): This can only fail if `_process_cpg_signatures` is called
        # before `_build_mate_jsonl`, since that's where we generate the artifact
        # we're looking for.
        if signature_artifact is None:
            raise CPGBuildError(
                self._build.uuid, "unlikely: ran a build but didn't produce a signature artifact?"
            )

        with signature_artifact.get_object() as io:
            try:
                signature_list = signatures.load_signatures(json.load(io))
            except (signatures.InvalidSignature, signatures.UnknownSignature) as e:
                raise CPGBuildError(self._build.uuid, e.message)

            signatures.process_cpg_signatures(signature_list, self._build, graph, session, False)

    def build_artifact(
        self, artifact: db.Artifact, session: orm.Session
    ) -> Tuple[List[db.Artifact], db.Graph]:
        build_assert(
            artifact in self._build.artifacts,
            f"incorrect build ({self._build.uuid}) for this artifact ({artifact.uuid})",
            build_id=self._build.uuid,
        )
        build_assert(
            artifact.kind == ArtifactKind.CompileOutputBitcode,
            f"artifact is {artifact.kind}, which wasn't expected here",
            build_id=self._build.uuid,
        )

        local_bc = artifact.persist_locally(suffix=".bc")

        if self._options.merge_library_bitcode:
            merged_bc = self._merge_library_bitcode(local_bc)
            canonicalized_bc = self._canonicalize_bitcode(Path(merged_bc.name))
        else:
            canonicalized_bc = self._canonicalize_bitcode(local_bc)

        mate_jsonl = self._build_mate_jsonl(Path(canonicalized_bc.name))

        quotidian_jsonl = None
        if self._options.machine_code_mapping:
            quotidian_jsonl = self._build_quotidian_jsonl(artifact, Path(canonicalized_bc.name))

        cpg_jsonl = self._build_cpg_jsonl(mate_jsonl, quotidian_jsonl)

        if self._options.schema_validation:
            logger.debug("verifying CPG JSONL against the JSON schemata")

        self._build.transition_to_state(BuildState.Inserting)
        session.add(self._build)
        session.commit()

        graph = populate_graph(
            jsonlines.Reader(cpg_jsonl),
            session,
            self._build,
            validate=self._options.schema_validation,
        )

        self._update_statistics(graph, session)
        self._process_cpg_signatures(graph, session)

        self._attach_source_lines_to_nodes(session)

        self._process_plt_stubs(graph, session)

        # NOTE(ww): This step requires the recompiled canonical binary, so we
        # only run it if we've also run the "machine code mapping"
        # (i.e., quotidian) step above.
        if self._options.machine_code_mapping:
            self._process_vtables(graph, session)

        self._update_statistics(graph, session)
        self._precompute_cfl_tables(graph, session)

        return (self._new_artifacts, graph)

    def _attach_source_lines_to_nodes(self, session: orm.Session) -> None:
        logger.info("Attempting to attach source code to nodes...")
        source_artifact = next(
            a for a in self._build.compilation.artifacts if a.kind.is_compile_target()
        )

        # TODO(AC): the decompression code below needs to be refactored and shared with
        # the compilation pipeline. Currently inline because of bug where calling it
        # in a function was causing the directory to be empty-- maybe garbage collection?
        # Maybe a generator being consumed?
        temp_source_dir = TD()
        try:
            if source_artifact.kind == ArtifactKind.CompileTargetTarball:
                # TODO(ww): Maybe support other kinds of tarballs/archives? Worth it?
                local_artifact = source_artifact.persist_locally(suffix=".tar.gz")
                with tarfile.open(local_artifact, "r:gz") as tar:
                    def is_within_directory(directory, target):
                        
                        abs_directory = os.path.abspath(directory)
                        abs_target = os.path.abspath(target)
                    
                        prefix = os.path.commonprefix([abs_directory, abs_target])
                        
                        return prefix == abs_directory
                    
                    def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
                    
                        for member in tar.getmembers():
                            member_path = os.path.join(path, member.name)
                            if not is_within_directory(path, member_path):
                                raise Exception("Attempted Path Traversal in Tar File")
                    
                        tar.extractall(path, members, numeric_owner) 
                        
                    
                    safe_extract(tar, path=temp_source_dir.name)
                source_dir = Path(temp_source_dir.name)
            elif source_artifact.kind == ArtifactKind.CompileTargetBrokeredChallenge:
                local_artifact = source_artifact.persist_locally(suffix=".zip")
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
                        local_member = zip_.extract(member, path=temp_source_dir.name)
                        if member.create_system == 3:
                            Path(local_member).chmod(member.external_attr >> 16)
                        else:
                            logger.debug(
                                f"unexpected (non-UNIX) ZIP member disposition: {member.create_system}"
                            )
                source_dir = Path(temp_source_dir.name)
            elif source_artifact.kind == ArtifactKind.CompileTargetSingle:
                local_artifact = source_artifact.persist_locally()
                source_dir = local_artifact.parent
            else:
                logger.info("Cannot add source code: unsupported compilation type.")
                return
        except tarfile.TarError as _e:
            logger.info("Cannot add source code: encountered tar error.")
            return
        # end decompression code ^

        # look for top level src dir:
        top_level_src_dir = self._find_toplevel_dir(source_dir, session)
        if top_level_src_dir is None:
            logger.info("Cannot add source code: source code not found.")
            return

        cpg = session.graph_from_build(self._build)

        # iterate over all the files of source code
        for file in list(top_level_src_dir.rglob("*.*")):
            try:
                logger.info(f"iterating, currently on file: {file}")
                relative_filename = relpath(file, top_level_src_dir)
                # for each file, map line-no to actual source code string
                lines_to_source = dict()
                with open(file) as f:
                    for line_no, line in enumerate(f):
                        lines_to_source[line_no + 1] = line.strip()

                # iterate over all nodes w/ matching filename, add the source code string
                all_nodes_in_file = (
                    session.query(cpg.Node)
                    .filter(cpg.Node.attributes["location"]["file"].astext == relative_filename)
                    .all()
                )
                for node in all_nodes_in_file:
                    line_no = node.attributes["location"].get("line")
                    source_code = lines_to_source.get(line_no)
                    if source_code is not None:
                        session.query(cpg.Node).filter(cpg.Node.uuid == node.uuid).update(
                            {
                                cpg.Node.attributes: cpg.Node.attributes.concat(
                                    {"source_code": source_code}
                                )
                            },
                            synchronize_session="fetch",
                        )
                session.commit()
            except Exception as e:
                logger.warning(f"could not process source file {file}: {e}")

    def _process_plt_stubs(self, cpg: db.Graph, session: orm.Session) -> None:
        """Process each `PLTStub` in the CPG, connecting it to its LLVM-level ``Function`` where
        possible."""

        # Select all LLVM-level functions that are declarations (i.e., external to the translation
        # unit) and have names that match symbols in the compiled program's PLT (if it has any).

        PLTStub = aliased(cpg.PLTStub)
        query = (
            session.query(cpg.Function)
            .filter(cpg.Function.is_declaration)
            .join(PLTStub, PLTStub.symbol == cpg.Function.name)
            .with_entities(cpg.Function, PLTStub)
        )

        for func, plt_stub in query.yield_per(100):
            session.add(
                cpg.Edge(
                    uuid=f"{func.uuid}-plt-stub-{plt_stub.uuid}",
                    kind=EdgeKind.FUNCTION_TO_PLT_STUB,
                    source=func.uuid,
                    target=plt_stub.uuid,
                    attributes={},
                )
            )
        session.commit()

    def _process_vtables(self, cpg: db.Graph, session: orm.Session) -> None:
        """Add virtual table information to the CPG, connecting each vtable to its constituent
        ``MachineFunction``s where possible."""

        canonical_binary_artifact = next(
            (
                a
                for a in self._new_artifacts
                if a.kind == ArtifactKind.BuildOutputQuotidianCanonicalBinary
            ),
            None,
        )
        if canonical_binary_artifact is None:
            logger.error("no canonical binary found for vtable pairing")
            return None

        # First pass: add the VTable nodes.
        canonical_binary = canonical_binary_artifact.persist_locally(suffix=".bin")
        with canonical_binary.open("rb") as io:
            elf = ELFFile(io)
            for vtable in all_vtables(elf):
                vtable_uuid = uuid.uuid4().hex
                session.add(
                    cpg.Node(
                        uuid=vtable_uuid,
                        kind=NodeKind.VTABLE,
                        attributes=dataclasses.asdict(vtable),
                    )
                )

                query = (
                    session.query(cpg.MachineFunction)
                    .filter(cpg.MachineFunction.va_start.in_(vtable.members))
                    .with_entities(cpg.MachineFunction.uuid)
                )
                for (mf_uuid,) in query.yield_per(100):
                    session.add(
                        cpg.Edge(
                            uuid=f"{mf_uuid}-vtable-{vtable_uuid}",
                            kind=EdgeKind.MI_FUNCTION_TO_VTABLE,
                            source=mf_uuid,
                            target=vtable_uuid,
                            attributes={},
                        )
                    )

                query = (
                    session.query(cpg.PLTStub)
                    .filter(cpg.PLTStub.va.in_(vtable.members))
                    .with_entities(cpg.PLTStub.uuid)
                )
                for (plt_stub_uuid,) in query.yield_per(100):
                    session.add(
                        cpg.Edge(
                            uuid=f"{plt_stub_uuid}-vtable-{vtable_uuid}",
                            kind=EdgeKind.PLT_STUB_TO_VTABLE,
                            source=plt_stub_uuid,
                            target=vtable_uuid,
                            attributes={},
                        )
                    )

        session.commit()

    def _precompute_cfl_tables(self, graph: db.Graph, session: orm.Session) -> None:
        """Precompute and cache commonly used CFL-reachability datastructures."""
        logger.info("Precomputing commonly used CFL-reachability query datastructures...")
        # Trigger the creation of transition and edge symbol tables for commonly used
        # CFL path queries by issuing forward and reverse queries that will return quickly
        # but cause the tables to be generated and cached.

        # If these type annotations are removed, Mypy infers Tuple[object, ...]
        # and throws an error.
        thin: Type[db.Path] = cfl.CSThinDataflowPath
        paths: Tuple[Type[db.Path], ...] = (thin, cfl.CallGraphPath)
        for cls in paths:
            session.query(
                db.PathBuilder(cls).build(graph, keep_start=False, exploration_bound=1)
            ).all()
            session.query(
                db.PathBuilder(cls).reverse().build(graph, keep_start=False, exploration_bound=1)
            ).all()

    def _update_statistics(self, graph: db.Graph, session: orm.Session) -> None:
        """Update postgres statistics on the node and edge tables."""
        logger.info("Updating statistics on the node and edge tables")
        session.execute(text(f"ANALYZE {graph.BaseNode.__table__.name}"))
        session.execute(text(f"ANALYZE {graph.BaseEdge.__table__.name}"))

    def _find_toplevel_dir(self, download_path: Path, session: orm.Session) -> Optional[Path]:
        """Helper to find the root src directory in the temporary directory + challenge tarball."""

        def _find_path(search: Path, target: Path) -> Optional[Path]:
            for dirpath, _dirnames, _filenames in os.walk(search):
                if os.path.isfile(Path(dirpath / target)):
                    return Path(dirpath)
            return None

        # Guess where the source is
        cpg = session.graph_from_build(self._build)
        F = aliased(cpg.Function)
        B = aliased(cpg.Block)
        I = aliased(cpg.Instruction)
        (source_target,) = (
            session.query(F)
            .filter_by(name="main")
            .join(B, F.blocks)
            .join(I, B.instructions)
            .filter(I.location != None)
            .with_entities(I.location["file"])
            .limit(1)
            .one_or_none()
        )
        logger.debug(f"Searching for source path: {source_target}")
        if source_target is not None:
            startpath = _find_path(download_path, Path(source_target))
            if startpath is not None:
                logger.debug(f"Found path to top of challenge source as: {startpath}")
                return startpath
        logger.debug(f"Couldn't find top of challenge source")
        return None


def _validate_against_schemata(cpg_row: Dict[Any, Any]) -> None:
    """Validates a single CPG row against the JSON schema, raising if validation fails.

    Callers of this function are responsible for propagating validation and other errors as an
    appropriate ``CPGBuildError``.
    """
    if cpg_row["entity"] == "node":
        try:
            jsonschema.validate(instance=cpg_row["attributes"], schema=NODE_SCHEMA)
        except jsonschema.exceptions.ValidationError as e1:
            msg = f"Node doesn't match schema:\n    {cpg_row['attributes']}"
            # NOTE(lb): Because the schema is a big oneOf disjunction,
            # we get irrelevant schema validation errors. We can work
            # around this by trying to validate a node on just the
            # slice of the schema that's relevant to it's kind to get a
            # better message.
            #
            # To avoid compounding an already confusing issue, this
            # part of the code should be especially resilient to
            # errors, hence the "except Exception".
            try:
                attrs = cpg_row["attributes"]
                by_kind = NODE_SCHEMA_BY_KIND[attrs["node_kind"]]
                by_kind["definitions"] = NODE_SCHEMA["definitions"]

                try:
                    jsonschema.validate(attrs, by_kind)
                except jsonschema.exceptions.ValidationError as e2:
                    msg += f"\n\nHint: the following message may be more specific: {e2}"
            except Exception:
                pass
            raise e1

    if cpg_row["entity"] == "edge":
        jsonschema.validate(instance=cpg_row["attributes"], schema=EDGE_SCHEMA)


def populate_graph(
    cpg_jsonl: Iterable[Dict[Any, Any]],
    session: orm.Session,
    build: db.Build,
    *,
    validate: bool = False,
) -> db.Graph:
    """Given an iterable of CPG records and a ``db.Build``, attempt to construct a ``db.Graph`` for
    those records and associate it with the build."""
    cpg = session.graph_from_build(build)
    for chunk in grouper(_CPG_INSERTION_CHUNK_SIZE, enumerate(cpg_jsonl)):
        nodes = []
        edges = []
        for idx, row in chunk:
            if validate:
                try:
                    _validate_against_schemata(row)
                except Exception as e:
                    raise CPGBuildError(build.uuid, str(e)) from e

            entity = row.pop("entity")
            if entity == "edge":
                row["kind"] = row["attributes"].pop("edge_kind")
                edges.append(row)
            else:
                row["kind"] = row["attributes"].pop("node_kind")
                nodes.append(row)

            if idx % 100_000 == 0:
                logger.debug(f"Inserted {idx} entities...")

        session.bulk_insert_mappings(cpg.Node, nodes)
        session.bulk_insert_mappings(cpg.Edge, edges)
        session.commit()
    return cpg


def build_artifact(
    artifact: db.Artifact, build: db.Build, session: orm.Session, options: BuildOptions
) -> None:
    """Run the MATE CPG build pipeline for the given artifact, which is assumed to be the bitcode
    output of the compilation pipeline.

    The CPG build pipeline produces a series of artifacts, each of which is associated with the
    given build.
    """

    logger.debug(
        f"running a CPG build on artifact {artifact.uuid} for build {build.uuid} with {options=}"
    )

    build.transition_to_state(BuildState.Building)
    build.artifacts.append(artifact)
    session.add(build)
    session.commit()

    try:
        builder = _Builder(build, options)
        (_new_artifacts, _graph) = builder.build_artifact(artifact, session)
        build.transition_to_state(BuildState.Built)
    except (BuildAssertionError, CPGBuildError) as e:
        # TODO(ww): Add some kind of artifact here to track the CPGBuildError's
        # failure message, so that clients can retrieve it and display it intelligibly
        # to the user.
        # NOTE(ww): We don't handle this exception anywhere in the server; propagate
        # it here merely to ensure that the task is marked as a failure rather than
        # a success.
        build.transition_to_state(BuildState.Failed)
        raise e
    finally:
        new_artifacts = builder._new_artifacts
        build.artifacts.extend(new_artifacts)
        session.add_all(new_artifacts)
        session.add(build)
        session.commit()
