"""Python API bindings for build endpoints in the MATE REST API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional

import mate_rest_client
from mate_common.models.analyses import AnalysisTaskInfo, POIResultInfo
from mate_common.models.builds import BuildInformation, BuildOptions, BuildState
from mate_rest_client import artifacts
from mate_rest_client.common import APIModel, Routes
from mate_rest_client.pois import POI

if TYPE_CHECKING:
    from mate_rest_client import compilations


@dataclass(frozen=False, init=False)
class Build(APIModel):
    """Represents a build retrieved from MATE."""

    def __init__(self, client: mate_rest_client.Client, info: BuildInformation) -> None:
        self._client = client
        self._info = info

    def refresh(self) -> None:
        """Refresh the internal state of this build."""
        refreshed = self._client.builds.get(self.id_)
        self._info = refreshed._info

    @property
    def id_(self) -> str:
        """Returns a unique identifier for this build."""
        return self._info.build_id

    @property
    def state(self) -> BuildState:
        """Returns the state that this build is in."""
        return self._info.state

    @property
    def compilation(self) -> compilations.Compilation:
        """Returns the compilation that this build was produced from."""
        return compilations.Compilation(self._client, self._info.compilation)

    @property
    def bitcode_artifact(self) -> artifacts.Artifact:
        """Returns the bitcode artifact that this build was started with."""
        return artifacts.Artifact(self._client, self._info.bitcode_artifact)

    @property
    def artifacts(self) -> Iterator[artifacts.Artifact]:
        """Yields each artifact associated with this build."""
        for artifact_id in self._info.artifact_ids:
            yield self._client.artifacts.get(artifact_id)

    @property
    def tasks(self) -> Iterator[AnalysisTaskInfo]:
        """Yields each analysis task associated with this build."""
        try:
            resp = self._client.get(f"/api/v1/analyses/tasks/{self.id_}", params=dict(detail=True))
        except mate_rest_client.RestError as re:
            if re.status_code == 404:
                return
            else:
                raise
        infos = resp.json()
        for info in infos:
            yield AnalysisTaskInfo(**info)

    @property
    def pois(self) -> Iterator[POI]:
        """Yields each POI associated with this build."""
        try:
            resp = self._client.get(f"/api/v1/pois/build/{self.id_}")
        except mate_rest_client.RestError as re:
            if re.status_code == 404:
                return
            else:
                raise
        infos = resp.json()
        for info in infos:
            yield POI(self._client, POIResultInfo(**info))


class BuildRoutes(Routes):
    """An adapter for interactions with build endpoints."""

    def create_from_compilation(
        self,
        compilation: compilations.Compilation,
        options: BuildOptions,
        *,
        target: Optional[str] = None,
        run_all_pois: bool = False,
    ) -> List[Build]:
        """Create one or more builds from a compilation.

        If ``target`` is passed and matches a binary produced by the compilation,
        creates a build only for that binary.

        All created builds are returned in a list.
        """
        if target is None:
            resp = self._client.post(
                f"/api/v1/builds/{compilation.id_}/build",
                params=dict(run_all_pois=run_all_pois),
                data=options.json(),
            )
            build_ids = resp.json()
            return [self.get(id_) for id_ in build_ids]
        else:
            info = self._client.post_as(
                BuildInformation,
                f"/api/v1/builds/{compilation.id_}/build/single",
                params=dict(target=target),
                data=options.json(),
            )
            return [Build(self._client, info)]

    def maybe_get(self, id_: str) -> Optional[Build]:
        """Return an build by ID, or ``None`` if the build does not exist."""
        info = self._client.get_as_maybe(BuildInformation, f"/api/v1/builds/{id_}")
        if info is not None:
            return Build(self._client, info)
        return None

    def get(self, id_: str) -> Build:
        """Retrieves a particular ``Build`` by its unique identifier."""
        info = self._client.get_as(BuildInformation, f"/api/v1/builds/{id_}")
        return Build(self._client, info)

    def iter(self, **kwargs: Dict[str, Any]) -> Iterator[Build]:
        """Yield each ``Build`` currently available.

        Any additional filters can be supplied via keyword arguments.
        """
        resp = self._client.get("/api/v1/builds", params=dict(**kwargs, detail=True))
        infos = resp.json()
        for info in infos:
            yield Build(self._client, BuildInformation(**info))

    def __iter__(self) -> Iterator[Build]:
        """Yields each ``Build`` currently available, regardless of state."""
        yield from self.iter()
