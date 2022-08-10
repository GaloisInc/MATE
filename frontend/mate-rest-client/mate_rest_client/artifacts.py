"""Python API bindings for artifact endpoints in the MATE REST API."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterator, Optional

from mate_common.models.artifacts import ArtifactInformation, ArtifactKind, ArtifactSpecification
from mate_rest_client.common import APIModel, Routes

if TYPE_CHECKING:
    import mate_rest_client
    from mate_rest_client import builds, compilations


@dataclass(frozen=False, init=False)
class Artifact(APIModel):
    """Represents an artifact retrieved from MATE."""

    def __init__(self, client: mate_rest_client.Client, info: ArtifactInformation) -> None:
        self._client = client
        self._info = info

    def refresh(self) -> None:
        """Refresh the internal state of this artifact."""
        refreshed = self._client.artifacts.get(self.id_)
        self._info = refreshed._info

    @property
    def id_(self) -> str:
        """Return the artifact's unique ID."""
        return self._info.artifact_id

    @property
    def kind(self) -> ArtifactKind:
        """Return the artifact's kind."""
        return self._info.kind

    @property
    def has_object(self) -> bool:
        """Return whether or not this artifact has any data currently associated with it."""
        return self._info.has_object

    @property
    def attributes(self) -> Dict[str, Any]:
        """Return all unstructured attributes associated with this artifact."""
        return self._info.attributes

    @property
    def compilations(self) -> Iterator[compilations.Compilation]:
        """Yield each compilation associated with this artifact.

        Most artifacts are only associated with a single compilation but some, like source
        artifacts, can be associated with multiple.
        """
        for compilation_id in self._info.compilation_ids:
            yield self._client.compilations.get(compilation_id)

    @property
    def builds(self) -> Iterator[builds.Build]:
        """Yield each build associated with this artifact.

        Most artifacts are only associated with a single build but some, like bitcode artifacts, can
        be associated with multiple.
        """
        for build_id in self._info.build_ids:
            yield self._client.builds.get(build_id)

    def contents(self) -> bytes:
        """Return the contents of this artifact, as bytes."""
        resp = self._client.get(f"/api/v1/artifacts/{self.id_}/object")
        return resp.content


class ArtifactRoutes(Routes):
    """An adapter for interactions with artifact endpoints."""

    def create(
        self,
        kind: ArtifactKind,
        *,
        filename: Path,
        attributes: Dict[str, Any] = {},
    ) -> Artifact:
        """Create a new artifact on the server and return it."""
        spec = ArtifactSpecification(kind=kind, attributes=attributes)

        # Create the artifact itself.
        info = self._client.post_as(ArtifactInformation, "/api/v1/artifacts", data=spec.json())

        # Upload the given file and associate it with the artifact.
        with filename.open("rb") as io:
            info = self._client.post_as(
                ArtifactInformation,
                f"/api/v1/artifacts/{info.artifact_id}/object",
                files={"file": io},
            )

        return Artifact(self._client, info)

    def maybe_get(self, id_: str) -> Optional[Artifact]:
        """Return an artifact by ID, or ``None`` if the artifact does not exist."""
        info = self._client.get_as_maybe(ArtifactInformation, f"/api/v1/artifacts/{id_}")
        if info is not None:
            return Artifact(self._client, info)
        return None

    def get(self, id_: str) -> Artifact:
        """Return an artifact by ID, raising on any error."""
        info = self._client.get_as(ArtifactInformation, f"/api/v1/artifacts/{id_}")
        return Artifact(self._client, info)

    def iter(self, **kwargs: Dict[str, Any]) -> Iterator[Artifact]:
        """Iterate over all artifacts currently known to MATE.

        Any additional filters can be supplied via keyword arguments.
        """
        resp = self._client.get("/api/v1/artifacts", params=dict(**kwargs, detail=True))
        infos = resp.json()
        for info in infos:
            yield Artifact(self._client, ArtifactInformation(**info))

    def __iter__(self) -> Iterator[Artifact]:
        """Iterate over all artifacts currently known to MATE."""
        yield from self.iter()
