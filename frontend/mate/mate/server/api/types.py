"""API routes for enumerating MATE types.

These routes are **not** documented in Sphinx, since they aren't Python APIs.

See the OpenAPI or Swagger UI documentation.
"""

from typing import List

from fastapi import APIRouter

from mate_common.models.cpg_types.mate import EdgeKind, NodeKind

router = APIRouter()


# TODO: Additional routes for relationships, etc?


@router.get("/node-kinds", response_model=List[NodeKind])
def _get_node_kinds() -> List[NodeKind]:
    """Return a list of node kinds known to this MATE server."""
    return list(NodeKind)


@router.get("/edge-kinds", response_model=List[EdgeKind])
def _get_edge_kinds() -> List[EdgeKind]:
    """Return a list of edge kinds known to this MATE server."""
    return list(EdgeKind)
