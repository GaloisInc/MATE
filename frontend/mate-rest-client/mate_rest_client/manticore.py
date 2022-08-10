"""Python API bindings for Manticore endpoints in the MATE REST API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Iterator, Optional

from mate_common.models.manticore import MantiserveTaskInformation, MantiserveTaskState
from mate_rest_client.common import APIModel, Routes

if TYPE_CHECKING:
    import mate_rest_client
    from mate_rest_client import artifacts, builds


class ManticoreRoutes(Routes):
    """An adapter for interactions with Manticore endpoints."""

    def maybe_get(self, id_: str) -> Optional[ManticoreTask]:
        """Return an Manticore task by ID, or ``None`` if the Manticore task does not exist."""
        info = self._client.get_as_maybe(MantiserveTaskInformation, f"/api/v1/compilations/{id_}")
        if info is not None:
            return ManticoreTask(self._client, info)
        return None

    def get(self, id_: str) -> ManticoreTask:
        """Retrieves a particular Manticore task by its unique identifier."""
        info = self._client.get_as(MantiserveTaskInformation, f"/api/v1/manticore/tasks/{id_}")
        return ManticoreTask(self._client, info)

    def stop(self, id_: str) -> ManticoreTask:
        """Instructs the server to stop the given Manticore task ID."""
        info = self._client.patch_as(
            MantiserveTaskInformation, f"/api/v1/manticore/tasks/{id_}/stop"
        )
        return ManticoreTask(self._client, info)

    def iter(self, **kwargs: Dict[str, Any]) -> Iterator[ManticoreTask]:
        """Yields each `ManticoreTask` currently available."""
        resp = self._client.get("/api/v1/manticore/tasks", params=dict(**kwargs, detail=True))
        infos = resp.json()
        for info in infos:
            yield ManticoreTask(self._client, MantiserveTaskInformation(**info))

    def __iter__(self) -> Iterator[ManticoreTask]:
        """Yields each `ManticoreTask` currently available."""
        yield from self.iter()


class ManticoreTask(APIModel):
    """Represents a Manticore ("Mantiserve") task retrieved from MATE."""

    def __init__(self, client: mate_rest_client.Client, info: MantiserveTaskInformation):
        self._client = client
        self._info = info

    def refresh(self) -> None:
        """Refresh the internal state of this Manticore task."""
        refreshed = self._client.manticore.get(self.id_)
        self._info = refreshed._info

    def stop(self) -> None:
        """Attempt to stop this task, refreshing the state in the process."""
        refreshed = self._client.manticore.stop(self.id_)
        self._info = refreshed._info

    @property
    def id_(self) -> str:
        """Returns a unique ID for this Manticore task."""
        return self._info.task_id

    @property
    def state(self) -> MantiserveTaskState:
        """Returns the state that this Manticore task is in."""
        return self._info.state

    @property
    def build(self) -> builds.Build:
        """Returns the build associated with this Manticore task."""
        return self._client.builds.get(self._info.build_id)

    @property
    def artifacts(self) -> Iterator[artifacts.Artifact]:
        """Yields each artifact associated with this Manticore task."""
        for artifact_id in self._info.artifact_ids:
            yield self._client.artifacts.get(artifact_id)
