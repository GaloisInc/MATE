"""Python API bindings for analyses endpoints in the MATE REST API."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

from mate_common.models.analyses import AnalysisInfo, AnalysisTaskInfo
from mate_rest_client.common import APIModel, Routes

if TYPE_CHECKING:
    import mate_rest_client
    from mate_rest_client import builds


@dataclass(frozen=False, init=False)
class Analysis(APIModel):
    """Represents an analysis in MATE."""

    def __init__(self, client: mate_rest_client.Client, info: AnalysisInfo) -> None:
        self._client = client
        self._info = info

    @property
    def id_(self) -> str:
        return self._info.analysis_id

    @property
    def filepath(self) -> str:
        return self._info.filepath

    @property
    def name(self) -> str:
        return self._info.name

    @property
    def background(self) -> str:
        return self._info.background

    def run(self, build: builds.Build) -> AnalysisTaskInfo:
        return self._client.post_as(
            AnalysisTaskInfo, f"/api/v1/analyses/{self._info.analysis_id}/run/{build.id_}"
        )


class AnalysisRoutes(Routes):
    """An adapter for interactions with analysis endpoints."""

    def create(self, filename: Path) -> Analysis:
        with filename.open() as io:
            info = self._client.post_as(
                AnalysisInfo,
                "/api/v1/analyses",
                files={"analysis": io},
            )

        return Analysis(self._client, info)

    def run(self, build: builds.Build) -> Iterator[AnalysisTaskInfo]:
        resp = self._client.post(f"/api/v1/analyses/run/{build.id_}")
        infos = resp.json()
        for info in infos:
            yield AnalysisTaskInfo(**info)

    def iter(self) -> Iterator[Analysis]:
        """Yield each `Analysis` currently available."""
        resp = self._client.get("/api/v1/analyses")
        infos = resp.json()
        for info in infos:
            yield Analysis(self._client, AnalysisInfo(**info))

    def __iter__(self) -> Iterator[Analysis]:
        """Yields each `Analysis` currently available."""
        yield from self.iter()

    @property
    def tasks(self) -> Iterator[AnalysisTaskInfo]:
        resp = self._client.get("/api/v1/analyses/tasks", params=dict(detail=True))
        infos = resp.json()
        for info in infos:
            yield AnalysisTaskInfo(**info)
