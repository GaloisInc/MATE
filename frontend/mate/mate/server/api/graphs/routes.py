"""API routes for rendering (parts of) CPGs in FlowFinder.

These routes are **not** documented in Sphinx, since they aren't Python APIs.

See the OpenAPI or Swagger UI documentation.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import orm

import mate_query.db as db
from mate.server.api.common import has_cpg, has_db
from mate.server.api.graphs.queries import (
    _format_nodes_for_flowfinder,
    get_alias_graph,
    get_call_graph_slice,
    get_callees_graph,
    get_callers_graph,
    get_callsites_graph,
    get_control_dependence_slice,
    get_control_flow_slice,
    get_dataflow_slice,
    get_forward_allocation_graph,
    get_forward_control_dependence_graph,
    get_forward_control_flow_graph,
    get_forward_dataflow_graph,
    get_memory_subregion_graph,
    get_operand_graph,
    get_points_to_graph,
    get_points_to_reachable_graph,
    get_reverse_allocation_graph,
    get_reverse_control_dependence_graph,
    get_reverse_control_flow_graph,
    get_reverse_dataflow_graph,
    get_signatures_graph,
    get_use_graph,
)
from mate_common.models.graphs import (
    FlowfinderGraph,
    FlowfinderNode,
    GraphKind,
    GraphRequest,
    SliceRequest,
)
from mate_common.utils import unreachable

router = APIRouter()


@router.get("/graphs/{build_id}/nodes/{node_id}", response_model=FlowfinderGraph)
def _get_nodes(
    node_id: str,
    cpg: db.Graph = Depends(has_cpg),
    session: orm.Session = Depends(has_db),
) -> FlowfinderGraph:
    try:
        node = session.query(cpg.Node).filter(cpg.Node.uuid == node_id).one()
        flowfinder_nodes = _format_nodes_for_flowfinder([node])
        return FlowfinderGraph(nodes=flowfinder_nodes, edges=[])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"couldn't fetch nodes: {str(exc)}") from exc


@router.post("/graphs/{build_id}", response_model=FlowfinderGraph)
def _get_graph(
    params: GraphRequest,
    cpg: db.Graph = Depends(has_cpg),
    session: orm.Session = Depends(has_db),
) -> FlowfinderGraph:
    # TODO(AC): eventually consider moving to celery task
    if params.kind is GraphKind.ForwardDataflow:
        return get_forward_dataflow_graph(session, cpg, params.origin_node_ids)
    elif params.kind is GraphKind.ReverseDataflow:
        return get_reverse_dataflow_graph(session, cpg, params.origin_node_ids)
    elif params.kind is GraphKind.ForwardControlFlow:
        return get_forward_control_flow_graph(session, cpg, params.origin_node_ids)
    elif params.kind is GraphKind.ReverseControlFlow:
        return get_reverse_control_flow_graph(session, cpg, params.origin_node_ids)
    elif params.kind is GraphKind.ForwardControlDependence:
        return get_forward_control_dependence_graph(session, cpg, params.origin_node_ids)
    elif params.kind is GraphKind.ReverseControlDependence:
        return get_reverse_control_dependence_graph(session, cpg, params.origin_node_ids)
    elif params.kind is GraphKind.CallSites:
        return get_callsites_graph(session, cpg, params.origin_node_ids)
    elif params.kind is GraphKind.Callers:
        return get_callers_graph(session, cpg, params.origin_node_ids)
    elif params.kind is GraphKind.Callees:
        return get_callees_graph(session, cpg, params.origin_node_ids)
    elif params.kind is GraphKind.Signatures:
        return get_signatures_graph(session, cpg, params.origin_node_ids)
    elif params.kind is GraphKind.Operands:
        return get_operand_graph(session, cpg, params.origin_node_ids)
    elif params.kind is GraphKind.Uses:
        return get_use_graph(session, cpg, params.origin_node_ids)
    elif params.kind is GraphKind.Uses:
        return get_use_graph(session, cpg, params.origin_node_ids)
    elif params.kind is GraphKind.ForwardPointsTo:
        return get_points_to_graph(session, cpg, params.origin_node_ids, reverse=False)
    elif params.kind is GraphKind.ReversePointsTo:
        return get_points_to_graph(session, cpg, params.origin_node_ids, reverse=True)
    elif params.kind is GraphKind.ForwardPointsToReachable:
        return get_points_to_reachable_graph(session, cpg, params.origin_node_ids, reverse=False)
    elif params.kind is GraphKind.ReversePointsToReachable:
        return get_points_to_reachable_graph(session, cpg, params.origin_node_ids, reverse=True)
    elif params.kind is GraphKind.ForwardAllocation:
        return get_forward_allocation_graph(session, cpg, params.origin_node_ids)
    elif params.kind is GraphKind.ReverseAllocation:
        return get_reverse_allocation_graph(session, cpg, params.origin_node_ids)
    elif params.kind is GraphKind.ForwardMemorySubregion:
        return get_memory_subregion_graph(session, cpg, params.origin_node_ids, reverse=False)
    elif params.kind is GraphKind.ReverseMemorySubregion:
        return get_memory_subregion_graph(session, cpg, params.origin_node_ids, reverse=True)
    elif params.kind is GraphKind.AliasedMemory:
        return get_alias_graph(session, cpg, params.origin_node_ids)
    else:
        unreachable(params.kind)


@router.post("/graphs/{build_id}/slices", response_model=FlowfinderGraph)
def _get_slice(
    params: SliceRequest,
    cpg: db.Graph = Depends(has_cpg),
    session: orm.Session = Depends(has_db),
) -> FlowfinderGraph:
    # TODO(AC): eventually consider moving to celery task
    if params.kind == GraphKind.ForwardDataflow:
        return get_dataflow_slice(
            session,
            cpg,
            params.source_id,
            params.sink_id,
            params.avoid_node_ids,
            params.focus_node_ids,
        )
    elif params.kind == GraphKind.ForwardControlFlow:
        return get_control_flow_slice(session, cpg, params.source_id, params.sink_id)
    elif params.kind == GraphKind.ReverseControlDependence:
        return get_control_dependence_slice(session, cpg, params.source_id, params.sink_id)
    elif params.kind == GraphKind.Callees:
        return get_call_graph_slice(session, cpg, params.source_id, params.sink_id)
    else:
        raise HTTPException(
            status_code=400, detail=f"unsupported GraphKind request for slice: {params.kind}"
        )


@router.get("/graphs/{build_id}/function-nodes", response_model=List[FlowfinderNode])
def _get_function_nodes(
    cpg: db.Graph = Depends(has_cpg),
    session: orm.Session = Depends(has_db),
) -> List[FlowfinderNode]:
    """Return a list of function-nodes for given build."""
    try:
        results = session.query(cpg.Function).all()
        return _format_nodes_for_flowfinder(results)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"couldn't fetch functions: {str(exc)}"
        ) from exc


@router.get("/graphs/{build_id}/machine-function-nodes", response_model=List[FlowfinderNode])
def _get_machine_function_nodes(
    cpg: db.Graph = Depends(has_cpg),
    session: orm.Session = Depends(has_db),
) -> List[FlowfinderNode]:
    """Return a list of machine-function nodes for given build."""
    try:
        results = session.query(cpg.MachineFunction).all()
        return _format_nodes_for_flowfinder(results)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"couldn't fetch functions: {str(exc)}"
        ) from exc
