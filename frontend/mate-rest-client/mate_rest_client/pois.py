"""Python API bindings for POI endpoints in the MATE REST API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional

from mate_common.models.analyses import POIResultComplexity, POIResultInfo
from mate_rest_client.common import APIModel, Routes

if TYPE_CHECKING:
    import mate_rest_client


@dataclass(frozen=False, init=False)
class POI(APIModel):
    """Represents a POI in MATE."""

    def __init__(self, client: mate_rest_client.Client, info: POIResultInfo) -> None:
        self._client = client
        self._info = info

    def refresh(self) -> None:
        """Refresh the internal state of this POI."""
        for refreshed in self._client.pois:
            if refreshed.id_ == self.id_:
                self._info = refreshed._info
                break

    @property
    def id_(self) -> str:
        """Returns a unique identifier for this POI."""
        return self._info.poi_result_id

    @property
    def build_id(self) -> str:
        """Returns the identifier of the build associated with this POI."""
        return self._info.build_id

    @property
    def task_id(self) -> str:
        """Returns the identifier of the analysis task associated with this POI."""
        return self._info.analysis_task_id

    @property
    def analysis_id(self) -> str:
        """Returns the identifier of the analysis that produced this POI."""
        return self._info.analysis_id

    @property
    def analysis_name(self) -> str:
        """Returns the name of the analysis that produced this POI."""
        return self._info.analysis_name

    @property
    def raw_data(self) -> Dict[str, Any]:
        """Returns the raw POI result."""
        return self._info.poi

    @property
    def flagged(self) -> bool:
        """Returns whether the POI has been marked as ``flagged``."""
        return self._info.flagged

    @flagged.setter
    def flagged(self, val: bool) -> None:
        """Sets the ``flagged`` marker on the POI."""
        self._client.put(f"/api/v1/pois/{self.id_}", params={"flagged": val})
        self.refresh()

    @property
    def done(self) -> bool:
        """Returns whether the POI has been marked as ``done``"""
        return self._info.done

    @done.setter
    def done(self, val: bool) -> None:
        """Sets the ``done`` marker on the POI."""
        self._client.put(f"/api/v1/pois/{self.id_}", params={"done": val})
        self.refresh()

    @property
    def complexity(self) -> POIResultComplexity:
        """Returns the estimated complexity of the POI."""
        return self._info.complexity

    @property
    def parent_id(self) -> Optional[str]:
        """Returns the identifier of the parent POI if the POI was created from a parent."""
        return self._info.parent_result_id

    @property
    def child_ids(self) -> List[str]:
        """Returns any child POIs that were produced as a result of this POI."""
        return self._info.child_result_ids

    @property
    def detail(self) -> POIResultInfo:
        """Returns a struct containing extra details about the POI."""
        return self._client.get_as(POIResultInfo, f"/api/v1/pois/{self.id_}/detail")


class POIRoutes(Routes):
    """An adapter for interactions with POI endpoints."""

    def __iter__(self) -> Iterator[POI]:
        """Yields each `POI` currently available."""
        resp = self._client.get("/api/v1/pois")
        infos = resp.json()
        for info in infos:
            yield POI(self._client, POIResultInfo(**info))
