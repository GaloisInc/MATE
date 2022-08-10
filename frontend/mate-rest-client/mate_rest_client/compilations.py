"""Python API bindings for compilation endpoints in the MATE REST API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Iterator, Optional

from mate_common.models.compilations import (
    CompilationInformation,
    CompilationState,
    CompileOptions,
    TargetKind,
    TargetSpecification,
)
from mate_rest_client import artifacts
from mate_rest_client.common import APIModel, Routes

if TYPE_CHECKING:
    import mate_rest_client
    from mate_rest_client import builds


@dataclass(frozen=False, init=False)
class Compilation(APIModel):
    """Represents a compilation retrieved from MATE."""

    def __init__(self, client: mate_rest_client.Client, info: CompilationInformation) -> None:
        self._client = client
        self._info = info

    def refresh(self) -> None:
        """Refresh the internal state of this compilation."""
        refreshed = self._client.compilations.get(self.id_)
        self._info = refreshed._info

    @property
    def id_(self) -> str:
        """Returns a unique identifier for this compilation."""
        return self._info.compilation_id

    @property
    def state(self) -> CompilationState:
        """Returns the state that this compilation is in."""
        return self._info.state

    @property
    def builds(self) -> Iterator[builds.Build]:
        """Yields each build created from this compilation."""
        for build_id in self._info.build_ids:
            yield self._client.builds.get(build_id)

    @property
    def log_artifact(self) -> Optional[artifacts.Artifact]:
        """Returns the compilation log artifact for this compilation, if it has a log."""
        if self._info.log_artifact:
            return artifacts.Artifact(self._client, self._info.log_artifact)
        else:
            return None

    @property
    def source_artifact(self) -> artifacts.Artifact:
        """Returns the source artifact that this compilation was started with."""
        return artifacts.Artifact(self._client, self._info.source_artifact)

    @property
    def artifacts(self) -> Iterator[artifacts.Artifact]:
        """Yields each artifact associated with this compilation."""
        for artifact_id in self._info.artifact_ids:
            yield self._client.artifacts.get(artifact_id)


class CompilationRoutes(Routes):
    """An adapter for interactions with compilation endpoints."""

    def _create(self, spec: TargetSpecification) -> Compilation:
        """Create a compilation directly from a ``TargetSpecification``."""
        info = self._client.post_as(
            CompilationInformation, "/api/v1/compilations", data=spec.json()
        )
        return Compilation(self._client, info)

    def create_from_challenge(
        self,
        options: CompileOptions = CompileOptions(),
        *,
        challenge_name: Optional[str] = None,
        challenge_id: Optional[str] = None,
        target_id: Optional[str] = None,
    ) -> Compilation:
        """Create a new compilation from a challenge, supplied by a CHESS challenge broker.

        Challenges can be identified through one of three mutually exclusive identifiers:

        - ``challenge_name``: the human-friendly "name" of the challenge, like ``example_1``
        - ``challenge_id``: the broker-assigned unique identifier for the challenge
        - ``target_id``: the broker-assigned unique identifier for a particular challenge target

        When ``challenge_name`` or ``challenge_id`` is used, MATE selects the "root"
        target for the specified challenge. When ``target_id`` is used, MATE selects
        that particular target instead. This can be used to specialize the compilation
        pipeline on a particular version of a brokered challenge, e.g. one that's
        been patched to make compilation simpler within MATE.
        """
        if challenge_name is not None:
            kind = TargetKind.BrokeredChallengeName
            handle = challenge_name
        elif challenge_id is not None:
            kind = TargetKind.BrokeredChallengeID
            handle = challenge_id
        elif target_id is not None:
            kind = TargetKind.BrokeredChallengeTargetID
            handle = target_id
        else:
            raise ValueError(
                "exactly one of challenge_name, challenge_id, or target_id must be supplied"
            )

        spec = TargetSpecification(kind=kind, handle=handle, options=options)
        return self._create(spec)

    def create_from_artifact(
        self, artifact: artifacts.Artifact, options: CompileOptions = CompileOptions()
    ) -> Compilation:
        """Create a new compilation from a source artifact.

        The artifact can be any source artifact that MATE knows how to accept. The server will
        reject compilations that are started with a non-source artifact.
        """
        spec = TargetSpecification(kind=TargetKind.Artifact, handle=artifact.id_, options=options)
        return self._create(spec)

    def maybe_get(self, id_: str) -> Optional[Compilation]:
        """Return an compilation by ID, or ``None`` if the compilation does not exist."""
        info = self._client.get_as_maybe(CompilationInformation, f"/api/v1/compilations/{id_}")
        if info is not None:
            return Compilation(self._client, info)
        return None

    def get(self, id_: str) -> Compilation:
        """Retrieves a particular compilation by its unique identifier."""
        info = self._client.get_as(CompilationInformation, f"/api/v1/compilations/{id_}")
        return Compilation(self._client, info)

    def iter(self, **kwargs: Dict[str, Any]) -> Iterator[Compilation]:
        """Yield each compilation currently available.

        Any additional filters can be supplied via keyword arguments.
        """
        resp = self._client.get("/api/v1/compilations", params=dict(**kwargs, detail=True))
        infos = resp.json()
        for info in infos:
            yield Compilation(self._client, CompilationInformation(**info))

    def __iter__(self) -> Iterator[Compilation]:
        """Yields each compilation currently available, regardless of state."""
        yield from self.iter()
