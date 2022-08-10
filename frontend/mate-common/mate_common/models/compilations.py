from __future__ import annotations

import enum
from functools import lru_cache
from typing import Any, Dict, FrozenSet, List, Optional

from pydantic import BaseModel, Field, validator

from mate_common.models.artifacts import ArtifactInformation
from mate_common.state_machine import StateMachineMixin


class CompilationState(StateMachineMixin, str, enum.Enum):
    """An enumeration of the different states that a compilation can be in."""

    Created = "created"
    Compiling = "compiling"
    Compiled = "compiled"
    Failed = "failed"
    Rejected = "rejected"

    @lru_cache
    def _valid_transitions(self) -> Dict[CompilationState, FrozenSet[CompilationState]]:
        return {
            CompilationState.Created: frozenset(
                {CompilationState.Compiling, CompilationState.Rejected}
            ),
            CompilationState.Compiling: frozenset(
                {CompilationState.Compiled, CompilationState.Failed, CompilationState.Rejected}
            ),
            CompilationState.Compiled: frozenset(),
            CompilationState.Failed: frozenset(),
            CompilationState.Rejected: frozenset(),
        }

    def __str__(self) -> str:
        return self.value


@enum.unique
class TargetKind(str, enum.Enum):
    """Valid targets for the compilation phase."""

    Artifact = "artifact"
    """
    A source artifact, either a single file or a tarball containing a source tree.
    """

    BrokeredChallengeName = "brokered-challenge:name"
    """
    The name of a challenge, brokered by the CHESS system challenge broker.
    """

    BrokeredChallengeID = "brokered-challenge:id"
    """
    The unique ID of a challenge, brokered by the CHESS system challenge broker.
    """

    BrokeredChallengeTargetID = "brokered-challenge-target:id"
    """
    The unique ID of a target within a challenge, brokered by the CHESS system challenge broker.
    """

    def is_brokered(self) -> bool:
        """Returns whether this is a brokered compilation target."""
        return self in [
            TargetKind.BrokeredChallengeName,
            TargetKind.BrokeredChallengeID,
            TargetKind.BrokeredChallengeTargetID,
        ]


class CompileOptions(BaseModel):
    """Options the control the behavior of the compilation pipeline."""

    testbed: Optional[bool] = None
    """
    Controls whether ``-DNO_TESTBED`` is passed to the compilation.

    ``testbed`` has three states:

    * ``None`` indicates that the testbed setting is irrelevant, e.g.
      for a non-CHESS-style target.
    * ``True`` indicates that the target should be compiled with ``-UNO_TESTBED``,
      i.e. with any testbed code explicitly enabled.
    * ``False`` indicates that the target should be compiled with ``-DNO_TESTBED``,
      i.e. with any testbed code explicitly disabled.
    """

    containerized: bool = False
    """
    Controls whether or not the compilation is attempted within a Docker container.

    If the source of this compilation is a brokered target, then the container image used
    is the one supplied by the broker. Otherwise, the container is created from
    the image specified in the ``docker_image`` option.
    """

    experimental_embed_bitcode: bool = False
    """
    Instrument the compilation to use ``-fembed-bitcode`` instead of using GLLVM.

    This option is experimental, and is unlikely to work on compilations larger
    than a single file.
    """

    docker_image: Optional[str] = None
    """
    The Docker image to use for a non-brokered containerized compilation.

    Ignored if ``containerized`` is ``false``.
    """

    containerized_infer_build: bool = True
    """
    When compiling with ``containerized``: attempt to reproduce the discrete build
    steps from the ``Dockerfile.build`` supplied by the brokered target.

    Only relevant for brokered challenges.
    """

    make_targets: Optional[List[str]] = Field(None, example=["clean", "all"])
    """
    A list of ``make`` targets to run sequentially instead of a vanilla ``make`` build.
    If not supplied, the default ``make`` target is run.

    These should be formatted as **just** target names, e.g. ``["depend", "all"]``
    for ``make depend`` followed by ``make all``.

    This option is primarily useful for vexatious builds that require multiple
    independent steps to happen in sequence for a successful compilation.
    The ``cornhill`` challenge is a straightforward example: a successful
    compilation must run ``make depend`` before ``make``.

    This option overrides the behavior of ``containerized_infer_build``.
    """

    extra_compiler_flags: List[str] = Field([], example=[])
    """
    A list of extra flags to pass to the underlying compiler with each invocation.

    These flags are supplied to the compiler regardless of its type or mode, i.e.
    both ``CC`` and ``CXX`` receive them.
    """


class TargetSpecification(BaseModel):
    """A descriptor, identifier, and additional options for a compilation target."""

    kind: TargetKind
    """
    The kind of target being compiled.
    """

    handle: str = Field(..., example="replace this with an actual handle, such as an artifact ID")
    """
    The ``TargetKind``-specific handle or other identifying information.
    """

    options: CompileOptions
    """
    Additional options for configuring the compilation.
    """

    @validator("options")
    def validate_options(cls, options: CompileOptions, values: Dict[str, Any]) -> CompileOptions:
        kind: TargetKind = values["kind"]

        # If the target *isn't* a brokered one but does request containerization,
        # then `options.docker_image` *must* be present.
        # If the target *is* brokered, then we explicitly forbid `options.docker_image`
        # since the broker supplies the image and its presence indicates that
        # the user is confused about how their target is being compiled.
        if not kind.is_brokered():
            if options.containerized and options.docker_image is None:
                raise ValueError("`containerized` requires `docker_image` for non-brokered targets")
            elif not options.containerized and options.docker_image is not None:
                raise ValueError("`docker_image` has no effect without `containerized`")
        else:
            if options.docker_image is not None:
                raise ValueError("`docker_image` has no effect on brokered targets")

        return options


class CompilationInformation(BaseModel):
    """Metadata about a compilation."""

    compilation_id: str
    """The ID of the compilation."""

    build_ids: List[str]
    """The IDs of any builds created from this compilation."""

    state: CompilationState
    """The compilation's current state."""

    source_artifact: ArtifactInformation
    """Artifact detail for the source artifact that this compilation was created from."""

    log_artifact: Optional[ArtifactInformation]
    """Artifact detail for the compilation log recorded with this compilation, if available."""

    artifact_ids: List[str]
    """The IDs of any artifacts currently associated with the compilation."""

    options: CompileOptions
    """The ``CompileOptions`` used to configure this compilation."""
