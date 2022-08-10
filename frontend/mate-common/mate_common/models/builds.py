from __future__ import annotations

import enum
from functools import lru_cache
from typing import Any, Dict, FrozenSet, List, Optional

from pydantic import BaseModel, Field, validator

from mate_common.config import MATE_DEFAULT_MEMORY_LIMIT_GB
from mate_common.models.artifacts import ArtifactInformation
from mate_common.models.bytes import Gibibytes, Mebibytes, gb_to_mb
from mate_common.models.compilations import CompilationInformation
from mate_common.state_machine import StateMachineMixin


@enum.unique
class PointerAnalysis(str, enum.Enum):
    """Valid variants of the pointer analysis.

    This should be kept in sync with:
    - ``llvm/PointerAnalysis/PointerAnalysis.cpp``
    - ``llvm/PointerAnalysis/test/conftest.py``
    """

    DEBUG = "debug"
    SUBSET_AND_UNIFICATION = "subset-and-unification"
    SUBSET = "subset"
    UNIFICATION = "unification"

    def __str__(self) -> str:
        """For inclusion in --help."""
        return self.value


@enum.unique
class ContextSensitivity(str, enum.Enum):
    """Valid context sensitivity settings for the pointer analysis.

    This should be kept in sync with:
    - ``llvm/PointerAnalysis/PointerAnalysis.cpp``
    - ``llvm/PointerAnalysis/test/conftest.py``
    - ``llvm/PointerAnalysis/FactGenerator/include/ContextSensitivity.hpp``
    - ``llvm/PointerAnalysis/datalog/options/user-options.dl``
    - ``llvm/PointerAnalysis/datalog/context/interface.dl``
    """

    INSENSITIVE = "insensitive"
    CALLSITE1 = "1-callsite"
    CALLSITE2 = "2-callsite"
    CALLSITE3 = "3-callsite"
    CALLSITE4 = "4-callsite"
    CALLSITE5 = "5-callsite"
    CALLSITE6 = "6-callsite"
    CALLSITE7 = "7-callsite"
    CALLSITE8 = "8-callsite"
    CALLSITE9 = "9-callsite"
    CALLER1 = "1-caller"
    CALLER2 = "2-caller"
    CALLER3 = "3-caller"
    CALLER4 = "4-caller"
    CALLER5 = "5-caller"
    CALLER6 = "6-caller"
    CALLER7 = "7-caller"
    CALLER8 = "8-caller"
    CALLER9 = "9-caller"
    FILE1 = "1-file"
    FILE2 = "2-file"
    FILE3 = "3-file"
    FILE4 = "4-file"
    FILE5 = "5-file"
    FILE6 = "6-file"
    FILE7 = "7-file"
    FILE8 = "8-file"
    FILE9 = "9-file"

    def __str__(self) -> str:
        """For inclusion in --help."""
        return self.value


@enum.unique
class BuildState(StateMachineMixin, str, enum.Enum):
    """An enumeration of the different states that a ``build`` can be in."""

    Created = "created"
    Building = "building"
    Inserting = "inserting"
    Built = "built"
    Failed = "failed"

    @lru_cache
    def _valid_transitions(self) -> Dict[BuildState, FrozenSet[BuildState]]:
        return {
            BuildState.Created: frozenset({BuildState.Building}),
            BuildState.Building: frozenset({BuildState.Inserting, BuildState.Failed}),
            BuildState.Inserting: frozenset({BuildState.Built, BuildState.Failed}),
            BuildState.Built: frozenset(),
            BuildState.Failed: frozenset(),
        }

    def __str__(self) -> str:
        return self.value


def get_default_memory_limit_gb() -> Gibibytes:
    return Gibibytes(MATE_DEFAULT_MEMORY_LIMIT_GB)


class BuildOptions(BaseModel):
    """Options that control the behavior of a CPG build."""

    # Options that affect emitted nodes and edges.
    do_pointer_analysis: bool = True
    """Whether to include pointer analysis results in the CPG."""

    machine_code_mapping: bool = True
    """Whether to include machine code mapping results in the CPG."""

    control_dependence: bool = True
    """Whether to include control dependence analysis results in the CPG."""

    llvm_memory_dependence: bool = False
    """Whether to include LLVM memory dependence analysis results in the CPG."""

    llvm_pretty_strings: bool = True
    """Whether to include pretty-printed LLVM strings in the CPG."""

    translation_unit_nodes: bool = True
    """Whether to include translation unit information in the CPG."""

    argument_edges: bool = False
    """Whether to include edges between Arguments and DWARFArguments in the CPG."""

    line_program_source_info: bool = False
    """Whether to include DWARF line program entry information in the CPG."""

    pointer_analysis: PointerAnalysis = PointerAnalysis.SUBSET
    """Which pointer analysis variant to run."""

    context_sensitivity: ContextSensitivity = Field(
        ContextSensitivity.CALLSITE2, example=ContextSensitivity.CALLSITE2.value
    )
    """The context sensitivity level."""

    memory_limit_mb: Mebibytes = Field(
        gb_to_mb(get_default_memory_limit_gb()), example=gb_to_mb(get_default_memory_limit_gb())
    )
    """Memory limit for CPG generation, in MB"""

    signatures: Optional[List[dict]] = Field(None, example=[])
    """Optional additional points-to and dataflow signatures."""

    extra_linker_flags: List[str] = Field([], example=[])
    """Additional linker flags to introduce when recompiling."""

    # Debug, assertion, and logging options.
    time_llvm_passes: bool = False
    """Emit timing information for each LLVM pass."""

    schema_validation: bool = False
    """Validate each node and edge against the JSON schema before insertion."""

    merge_library_bitcode: bool = True
    """For compilations that produce libraries and then link to them: attempt
    to statically merge library bitcode into the "canonical" bitcode instead
    of linking at the binary level.
    """

    merge_bitcode_only_needed: bool = False
    """With ``merge_library_bitcode``: tell ``llvm-link`` to only include referenced
    symbols when merging bitcode modules. This can help reduce bitcode size
    (and subsequently analysis time).
    """

    merge_bitcode_internalize: bool = False
    """With `merge_library_bitcode`: tell ``llvm-link`` to attempt to internalize
    any public symbols that aren't explicitly referenced by another other modules.
    This can help avoid unintentional symbol clashes, at the risk of deviating
    significantly from the system linker's normal behavior.
    """

    debug_pointer_analysis: bool = False
    """Save intermediate pointer analysis results for debugging."""

    debug_mate_jsonl: bool = False
    """Save the intermediate MATE JSONL file for debugging."""

    debug_quotidian_jsonl: bool = False
    """Save the intermediate Quotidian JSONL file for debugging."""

    debug_cpg_jsonl: bool = False
    """Save the intermediate CPG JSONL file for debugging."""

    @validator("merge_bitcode_only_needed")
    def _validate_merge_bitcode_only_needed(
        cls, merge_bitcode_only_needed: bool, values: Dict[str, Any]
    ) -> bool:
        if merge_bitcode_only_needed and not values["merge_library_bitcode"]:
            raise ValueError(
                "The `merge_bitcode_only_needed` param must be used in conjunction with `merge_library_bitcode`"
            )
        return merge_bitcode_only_needed

    @validator("merge_bitcode_internalize")
    def _validate_merge_bitcode_internalize(
        cls, merge_bitcode_internalize: bool, values: Dict[str, Any]
    ) -> bool:
        if merge_bitcode_internalize and not values["merge_library_bitcode"]:
            raise ValueError(
                "The `merge_bitcode_internalize` param must be used in conjunction with `merge_library_bitcode`"
            )
        return merge_bitcode_internalize


class BuildInformation(BaseModel):
    """Metadata about a build."""

    build_id: str
    """The ID of the build."""

    compilation: CompilationInformation
    """
    Compilation detail for the compilation task that this build was created from.
    """

    state: BuildState
    """The build's current state."""

    bitcode_artifact: ArtifactInformation
    """
    Artifact detail for the bitcode artifact that this build was created from.

    This artifact is present both here and in the ``artifacts`` list, if
    the latter is populated.
    """

    artifact_ids: List[str] = []
    """The IDs of any artifacts currently associated with the build."""

    artifacts: List[ArtifactInformation]
    """
    Artifact detail for any artifacts currently associated with the build, *if*
    this ``BuildInformation`` was populated with artifact detail.
    """

    analysis_task_ids: List[str]
    """The IDs of any analysis tasks currently associated with the build."""

    mantiserve_task_ids: List[str]
    """The IDs of any mantiserve tasks currently associated with the build."""

    options: BuildOptions
    """The ``BuildOptions`` used to configure this build."""

    attributes: Dict[str, Any]
    """Free-form information attached to this build."""
