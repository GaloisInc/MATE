"""Python API bindings for POI endpoints in the MATE REST API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from mate_common.models.graphs import FlowfinderGraph, FlowfinderNode, GraphRequest, SliceRequest
from mate_rest_client.common import Routes

if TYPE_CHECKING:
    import mate_rest_client
    from mate_rest_client import builds


class GraphRoutes(Routes):
    """An adapter for interactions with Graph endpoints."""

    def get_graph(self, build: builds.Build, req: GraphRequest) -> FlowfinderGraph:
        return self._client.post_as(FlowfinderGraph, f"/api/v1/graphs/{build.id_}", data=req.json())

    def get_node(self, build: builds.Build, node_id: str) -> FlowfinderGraph:
        return self._client.get_as(FlowfinderGraph, f"/api/v1/graphs/{build.id_}/nodes/{node_id}")

    def get_slice(self, build: builds.Build, req: SliceRequest) -> FlowfinderGraph:
        return self._client.post_as(
            FlowfinderGraph, f"/api/v1/graphs/{build.id_}/slices", data=req.json()
        )

    def get_function_nodes(self, build: builds.Build) -> Iterator[FlowfinderNode]:
        resp = self._client.get(f"/api/v1/graphs/{build.id_}/function-nodes")
        infos = resp.json()
        for info in infos:
            yield FlowfinderNode(**info)
