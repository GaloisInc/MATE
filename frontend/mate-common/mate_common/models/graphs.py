from __future__ import annotations

import enum
from typing import List, Optional, Union

from pydantic import BaseModel


class FlowfinderNode(BaseModel):
    """Data representing a CPG node needed by flowfinder."""

    node_id: str
    """The ID of the node in the CPG."""

    node_kind: str
    """The node's node_kind."""

    opcode: Optional[str]
    """If the node is an instruction, the node's opcode."""

    source_id: Optional[str]
    """If the node is an instruction, the line of source code corresponding to this instruction."""

    function_id: Optional[str]
    """If the node is an instruction, the demangled name of it's parent function."""

    label: str
    """A human readable string representation of this node."""


class FlowfinderEdge(BaseModel):
    """Data representing a CPG edge needed by flowfinder."""

    edge_id: str
    """The ID of the edge in the CPG."""

    edge_kind: str
    """The edge's edge_kind."""

    source_id: str
    """The edge's source_id."""

    target_id: str
    """The edge's target_id."""


class FlowfinderGraph(BaseModel):
    """A nodelist and edgelist graph representation, with info needed by flowfinder."""

    nodes: List[FlowfinderNode]
    """The nodes in this graph."""

    edges: List[FlowfinderEdge]
    """The edges in this graph."""


###############################################################################


@enum.unique
class GraphKind(str, enum.Enum):
    """Valid kinds of graphs to request."""

    ForwardDataflow = "forward_dataflow"

    ReverseDataflow = "reverse_dataflow"

    ForwardControlFlow = "forward_control_flow"

    ReverseControlFlow = "reverse_control_flow"

    ForwardControlDependence = "forward_control_dependence"

    ReverseControlDependence = "reverse_control_dependence"

    CallSites = "callsites"

    Callers = "callers"

    Callees = "callees"

    Operands = "operands"

    Uses = "uses"

    ForwardPointsTo = "forward_points_to"

    ReversePointsTo = "reverse_points_to"

    ForwardPointsToReachable = "forward_points_to_reachable"

    ReversePointsToReachable = "reverse_points_to_reachable"

    ForwardAllocation = "forward_allocation"

    ReverseAllocation = "reverse_allocation"

    ForwardMemorySubregion = "forward_memory_subregion"

    ReverseMemorySubregion = "reverse_memory_subregion"

    AliasedMemory = "aliased_memory_locations"

    Signatures = "signatures"

    def __str__(self) -> str:
        return self.value


class GraphRequestKind(str, enum.Enum):
    """These should correspond to the /graphs endpoints."""

    Node = "node"
    Graph = "graph"
    Slice = "slice"


class NodeRequest(BaseModel):
    """Parameters to request a node."""

    request_kind = GraphRequestKind.Node

    build_id: str
    """The CPG to query within."""

    node_id: str
    """The Node to query for."""


class GraphRequest(BaseModel):
    """Parameters to request a graph."""

    request_kind = GraphRequestKind.Graph

    build_id: str
    """The CPG to query within."""

    origin_node_ids: List[str]
    """Nodes around which to run the query."""

    kind: GraphKind
    """Choose from available GraphKinds."""


class SliceRequest(BaseModel):
    """Parameters to request a slice."""

    request_kind = GraphRequestKind.Slice

    build_id: str
    """The CPG to query within."""

    source_id: str
    """ID of the node at which to start the slice."""

    sink_id: str
    """ID of the node at which to end the slice."""

    kind: GraphKind
    """Choose from: dataflow, control_flow, reverse_control_dependence, call_graph."""

    avoid_node_ids: Optional[List[str]]
    """The slice will exclude paths through these nodes."""

    focus_node_ids: Optional[List[str]]
    """The slice will include only paths through these nodes."""


GraphServerRequest = Union[NodeRequest, GraphRequest, SliceRequest]
