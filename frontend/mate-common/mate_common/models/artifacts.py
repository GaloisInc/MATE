from __future__ import annotations

import enum
from typing import Any, Dict, List

from pydantic import BaseModel


@enum.unique
class ArtifactKind(str, enum.Enum):
    """An enumeration of valid artifact kinds."""

    CompileTargetSingle = "compile-target:single"
    CompileTargetTarball = "compile-target:tarball"
    CompileTargetBitcode = "compile-target:bitcode"
    CompileTargetBrokeredChallenge = "compile-target:brokered-challenge"
    BlightJournal = "blight:journal"
    CompileOutputBinary = "compile-output:binary"
    CompileOutputBitcode = "compile-output:bitcode"
    CompileOutputSharedLibrary = "compile-output:shared-library"
    CompileOutputSharedLibraryBitcode = "compile-output:shared-library:bitcode"
    CompileOutputStaticLibrary = "compile-output:static-library"
    CompileOutputStaticLibraryBitcode = "compile-output:static-library:bitcode"
    CompileOutputCompileLog = "compile-output:compile-log"
    BuildOutputMergedBitcode = "build-output:merged-bitcode"
    BuildOutputCanonicalBitcode = "build-output:canonical-bitcode"
    BuildOutputSignatures = "build-output:signatures"
    BuildOutputMateJSONL = "build-output:mate-jsonl"
    BuildOutputQuotidianHeadacheLog = "build-output:quotidian-headache-log"
    BuildOutputQuotidianWedlockLog = "build-output:quotidian-wedlock-log"
    BuildOutputQuotidianCanonicalBinary = "build-output:quotidian-canonical-binary"
    BuildOutputQuotidianJSONL = "build-output:quotidian-jsonl"
    BuildOutputCpgJSONL = "build-output:cpg-jsonl"
    BuildOutputDebugPointerAnalysis = "build-output:debug-pointer-analysis"
    BuildOutputTaskLog = "build-output:task-log"

    # Mantiserve enum begin
    MantiserveTaskLog = "mantiserve-task:log"

    def is_compile_target(self) -> bool:
        """Returns whether the artifact is a compile target."""
        return self.value.startswith("compile-target")

    def is_build_output(self) -> bool:
        """Returns whether the artifact is a build output."""
        return self.value.startswith("build-output")

    def __str__(self) -> str:
        return self.value


class ArtifactSpecification(BaseModel):
    kind: ArtifactKind
    attributes: Dict[str, Any]


class ArtifactInformation(BaseModel):
    artifact_id: str
    kind: ArtifactKind
    has_object: bool
    attributes: Dict[str, Any]
    build_ids: List[str]
    compilation_ids: List[str]
