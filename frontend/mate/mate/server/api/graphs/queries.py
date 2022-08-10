from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session, aliased
from sqlalchemy.sql.expression import func, literal

import mate_query.db as db
from mate.logging import logger
from mate_common.models.cpg_types import (
    DATA_FLOW_FORWARD,
    DATA_FLOW_FORWARD_THIN,
    EdgeKind,
    NodeKind,
)
from mate_common.models.graphs import FlowfinderEdge, FlowfinderGraph, FlowfinderNode
from mate_query.cfl import CallGraphPath, CSThinDataflowPath
from mate_query.config import MATE_SERVER_EXPLORATION_BOUND
from mate_query.db import BOT

if TYPE_CHECKING:
    from sqlalchemy.sql.expression import CTE

    from mate_query.db import DWARFType
    from mate_query.db import Graph as CPG
    from mate_query.db import MachineFunction, Node, Path


def _unique_edges(
    edges: Iterable[Tuple[str, EdgeKind, str, str]]
) -> Iterable[Tuple[str, EdgeKind, str, str]]:
    """Deduplicate kind/source/target triples, choosing a representative edge arbitrarily."""
    uniqued = dict()
    for (uuid, kind, source, target) in edges:
        uniqued[(kind, source, target)] = (uuid, kind, source, target)

    return uniqued.values()


###################### dataflow ################################################


def get_reverse_dataflow_graph(
    session: Session, cpg: db.Graph, origin_ids: List[str]
) -> FlowfinderGraph:
    """Computes the dataflow graph reaching each of the origin nodes."""
    # Tell postgres to respect join orders as written
    dataflow_query = (
        db.PathBuilder(CSThinDataflowPath)
        .reverse()
        .stopping_at(lambda Node: Node.uuid.in_(origin_ids))
        .build(
            cpg,
            keep_start=False,
            keep_edge=True,
            exploration_bound=MATE_SERVER_EXPLORATION_BOUND,
        )
    )

    dataflow_edges = _unique_edges(
        session.query(dataflow_query)
        .join(cpg.Edge, cpg.Edge.uuid == dataflow_query.edge)
        .with_entities(
            cpg.Edge.uuid,
            cpg.Edge.kind,
            cpg.Edge.source,
            cpg.Edge.target,
        )
        .union(
            session.query(cpg.Edge)
            .filter(cpg.Edge.kind.in_(DATA_FLOW_FORWARD), cpg.Edge.target.in_(origin_ids))
            .with_entities(
                cpg.Edge.uuid,
                cpg.Edge.kind,
                cpg.Edge.source,
                cpg.Edge.target,
            )
        )
        .all()
    )

    dataflow_node_uuids = set(origin_ids)
    for e in dataflow_edges:
        dataflow_node_uuids.add(e[2])
        dataflow_node_uuids.add(e[3])

    dataflow_nodes = session.query(cpg.Node).filter(cpg.Node.uuid.in_(dataflow_node_uuids)).all()

    flowfinder_nodes = _format_nodes_for_flowfinder(dataflow_nodes)
    flowfinder_edges = _format_edges_for_flowfinder(dataflow_edges)

    logger.debug(
        f"Returning flowfinder graph with {len(flowfinder_nodes)} nodes and {len(flowfinder_edges)} edges"
    )

    return FlowfinderGraph(nodes=flowfinder_nodes, edges=flowfinder_edges)


def get_forward_dataflow_graph(
    session: Session, cpg: db.Graph, origin_ids: List[str]
) -> FlowfinderGraph:
    """Computes the dataflow graph from each of the origin nodes."""
    # Tell postgres to respect join orders as written
    dataflow_query = (
        db.PathBuilder(CSThinDataflowPath)
        .starting_at(lambda Node: Node.uuid.in_(origin_ids))
        .build(
            cpg,
            keep_start=False,
            keep_edge=True,
            exploration_bound=MATE_SERVER_EXPLORATION_BOUND,
        )
    )

    dataflow_edges = _unique_edges(
        session.query(dataflow_query)
        .join(cpg.Edge, cpg.Edge.uuid == dataflow_query.edge)
        .with_entities(
            cpg.Edge.uuid,
            cpg.Edge.kind,
            cpg.Edge.source,
            cpg.Edge.target,
        )
        .union(
            session.query(cpg.Edge)
            .filter(cpg.Edge.kind.in_(DATA_FLOW_FORWARD), cpg.Edge.source.in_(origin_ids))
            .with_entities(
                cpg.Edge.uuid,
                cpg.Edge.kind,
                cpg.Edge.source,
                cpg.Edge.target,
            )
        )
        .all()
    )

    dataflow_node_uuids = set(origin_ids)
    for e in dataflow_edges:
        dataflow_node_uuids.add(e[2])
        dataflow_node_uuids.add(e[3])

    dataflow_nodes = session.query(cpg.Node).filter(cpg.Node.uuid.in_(dataflow_node_uuids)).all()

    flowfinder_nodes = _format_nodes_for_flowfinder(dataflow_nodes)
    flowfinder_edges = _format_edges_for_flowfinder(dataflow_edges)

    logger.debug(
        f"Returning flowfinder graph with {len(flowfinder_nodes)} nodes and {len(flowfinder_edges)} edges"
    )

    return FlowfinderGraph(nodes=flowfinder_nodes, edges=flowfinder_edges)


def get_dataflow_slice(
    session: Session,
    cpg: db.Graph,
    source_id: str,
    sink_id: str,
    avoid_node_ids: Optional[List[str]],
    focus_node_ids: Optional[List[str]],
) -> FlowfinderGraph:
    """Computes the dataflow slice between source_id and sink_id."""
    # Tell postgres to respect join orders as written
    to_avoid = [] if avoid_node_ids is None else avoid_node_ids
    focus_on = [] if focus_node_ids is None else focus_node_ids

    from_input = (
        db.PathBuilder(CSThinDataflowPath)
        .starting_at(lambda Node: Node.uuid == source_id)
        .continuing_while(lambda _, Edge: Edge.target.notin_(to_avoid), edge_detail=False)
        .build(
            cpg,
            keep_start=False,
            exploration_bound=MATE_SERVER_EXPLORATION_BOUND,
        )
    )

    to_output = (
        db.PathBuilder(CSThinDataflowPath)
        .reverse()
        .stopping_at(lambda Node: Node.uuid == sink_id)
        .continuing_while(lambda _, Edge: Edge.source.notin_(to_avoid), edge_detail=False)
        .build(
            cpg,
            keep_start=False,
            exploration_bound=MATE_SERVER_EXPLORATION_BOUND,
        )
    )

    dataflow_node_uuids = {
        n[0]
        for n in (
            session.query(from_input)
            .join(
                to_output,
                (from_input.target == to_output.source)
                & (
                    (from_input.stack_top == BOT)
                    | (to_output.stack_top == BOT)
                    | (from_input.stack_top == to_output.stack_top)
                    | (
                        func.split_part(from_input.stack_top, literal("-->"), 2)
                        == to_output.stack_top
                    )
                    | (
                        from_input.stack_top
                        == func.split_part(to_output.stack_top, literal("-->"), 2)
                    )
                    | (
                        func.split_part(from_input.stack_top, literal("-->"), 2)
                        == func.split_part(to_output.stack_top, literal("-->"), 2)
                    )
                ),
            )
            .with_entities(from_input.target)
            .all()
        )
    }

    logger.debug(f"Pre-focused slice has {len(dataflow_node_uuids)} nodes")

    for focused in focus_on:
        from_input = (
            db.PathBuilder(CSThinDataflowPath)
            .starting_at(lambda Node: Node.uuid == source_id)
            .continuing_while(
                lambda _, Edge: Edge.target.in_(dataflow_node_uuids), edge_detail=False
            )
            .build(
                cpg,
                keep_start=False,
                exploration_bound=MATE_SERVER_EXPLORATION_BOUND,
            )
        )

        to_focused = (
            db.PathBuilder(CSThinDataflowPath)
            .reverse()
            .stopping_at(lambda Node: Node.uuid == focused)
            .continuing_while(
                lambda _, Edge: Edge.source.in_(dataflow_node_uuids), edge_detail=False
            )
            .build(
                cpg,
                keep_start=False,
                exploration_bound=MATE_SERVER_EXPLORATION_BOUND,
            )
        )

        from_focused = (
            db.PathBuilder(CSThinDataflowPath)
            .starting_at(lambda Node: Node.uuid == focused)
            .continuing_while(
                lambda _, Edge: Edge.target.in_(dataflow_node_uuids), edge_detail=False
            )
            .build(
                cpg,
                keep_start=False,
                exploration_bound=MATE_SERVER_EXPLORATION_BOUND,
            )
        )

        to_output = (
            db.PathBuilder(CSThinDataflowPath)
            .reverse()
            .stopping_at(lambda Node: Node.uuid == sink_id)
            .continuing_while(
                lambda _, Edge: Edge.source.in_(dataflow_node_uuids), edge_detail=False
            )
            .build(
                cpg,
                keep_start=False,
                exploration_bound=MATE_SERVER_EXPLORATION_BOUND,
            )
        )

        dataflow_node_uuids = {
            n[0]
            for n in (
                session.query(from_input)
                .join(
                    to_focused,
                    (from_input.target == to_focused.source)
                    & (
                        (from_input.stack_top == BOT)
                        | (to_focused.stack_top == BOT)
                        | (from_input.stack_top == to_focused.stack_top)
                        | (
                            func.split_part(from_input.stack_top, literal("-->"), 2)
                            == to_focused.stack_top
                        )
                        | (
                            from_input.stack_top
                            == func.split_part(to_focused.stack_top, literal("-->"), 2)
                        )
                        | (
                            func.split_part(from_input.stack_top, literal("-->"), 2)
                            == func.split_part(to_focused.stack_top, literal("-->"), 2)
                        )
                    ),
                )
                .with_entities(from_input.target)
                .union(
                    session.query(from_focused)
                    .join(
                        to_output,
                        (from_focused.target == to_output.source)
                        & (
                            (from_focused.stack_top == BOT)
                            | (to_output.stack_top == BOT)
                            | (from_focused.stack_top == to_output.stack_top)
                            | (
                                func.split_part(from_focused.stack_top, literal("-->"), 2)
                                == to_output.stack_top
                            )
                            | (
                                from_focused.stack_top
                                == func.split_part(to_output.stack_top, literal("-->"), 2)
                            )
                            | (
                                func.split_part(from_focused.stack_top, literal("-->"), 2)
                                == func.split_part(to_output.stack_top, literal("-->"), 2)
                            )
                        ),
                    )
                    .with_entities(from_focused.target)
                )
                .all()
            )
        }

    logger.debug(f"After focusing slice has {len(dataflow_node_uuids)} nodes")

    dataflow_edges = _unique_edges(
        session.query(cpg.Edge)
        .filter(
            cpg.Edge.kind.in_(DATA_FLOW_FORWARD_THIN | {EdgeKind.VALUE_DEFINITION_TO_USE}),
            cpg.Edge.source.in_(dataflow_node_uuids),
            cpg.Edge.target.in_(dataflow_node_uuids),
        )
        .with_entities(
            cpg.Edge.uuid,
            cpg.Edge.kind,
            cpg.Edge.source,
            cpg.Edge.target,
        )
        .all()
    )
    dataflow_nodes = session.query(cpg.Node).filter(cpg.Node.uuid.in_(dataflow_node_uuids)).all()

    flowfinder_nodes = _format_nodes_for_flowfinder(dataflow_nodes)
    flowfinder_edges = _format_edges_for_flowfinder(dataflow_edges)

    logger.debug(
        f"Returning flowfinder graph with {len(flowfinder_nodes)} nodes and {len(flowfinder_edges)} edges"
    )

    return FlowfinderGraph(nodes=flowfinder_nodes, edges=flowfinder_edges)


def get_operand_graph(session: Session, cpg: db.Graph, origin_ids: List[str]) -> FlowfinderGraph:
    """Computes the operands graph from each of the origin nodes."""
    edges = (
        session.query(cpg.Edge)
        .filter(cpg.Edge.kind == EdgeKind.VALUE_DEFINITION_TO_USE, cpg.Edge.target.in_(origin_ids))
        .with_entities(
            cpg.Edge.uuid,
            cpg.Edge.kind,
            cpg.Edge.source,
            cpg.Edge.target,
        )
        .all()
    )

    node_uuids = set(
        itertools.chain(
            (edge[2] for edge in edges),
            (edge[3] for edge in edges),
        )
    )

    nodes = session.query(cpg.Node).filter(cpg.Node.uuid.in_(node_uuids)).all()

    flowfinder_nodes = _format_nodes_for_flowfinder(nodes)
    flowfinder_edges = _format_edges_for_flowfinder(edges)

    return FlowfinderGraph(nodes=flowfinder_nodes, edges=flowfinder_edges)


def get_use_graph(session: Session, cpg: db.Graph, origin_ids: List[str]) -> FlowfinderGraph:
    """Computes the use graph from each of the origin nodes."""
    edges = (
        session.query(cpg.Edge)
        .filter(cpg.Edge.kind == EdgeKind.VALUE_DEFINITION_TO_USE, cpg.Edge.source.in_(origin_ids))
        .with_entities(
            cpg.Edge.uuid,
            cpg.Edge.kind,
            cpg.Edge.source,
            cpg.Edge.target,
        )
        .all()
    )

    node_uuids = set(
        itertools.chain(
            (edge[2] for edge in edges),
            (edge[3] for edge in edges),
        )
    )

    nodes = session.query(cpg.Node).filter(cpg.Node.uuid.in_(node_uuids)).all()

    flowfinder_nodes = _format_nodes_for_flowfinder(nodes)
    flowfinder_edges = _format_edges_for_flowfinder(edges)

    return FlowfinderGraph(nodes=flowfinder_nodes, edges=flowfinder_edges)


###################### points-to graph  ########################################


def get_points_to_graph(
    session: Session, cpg: db.Graph, origin_ids: List[str], reverse: bool = False
) -> FlowfinderGraph:
    """Computes the points_to graph from each of the origin nodes."""
    edges = (
        session.query(cpg.Edge)
        .filter(
            cpg.Edge.kind == EdgeKind.POINTS_TO,
            cpg.Edge.target.in_(origin_ids) if reverse else cpg.Edge.source.in_(origin_ids),
        )
        .with_entities(
            cpg.Edge.uuid,
            cpg.Edge.kind,
            cpg.Edge.source,
            cpg.Edge.target,
        )
        .all()
    )

    node_uuids = set(
        itertools.chain(
            (edge[2] for edge in edges),
            (edge[3] for edge in edges),
        )
    )

    nodes = session.query(cpg.Node).filter(cpg.Node.uuid.in_(node_uuids)).all()

    flowfinder_nodes = _format_nodes_for_flowfinder(nodes)
    flowfinder_edges = _format_edges_for_flowfinder(edges)

    return FlowfinderGraph(nodes=flowfinder_nodes, edges=flowfinder_edges)


def get_points_to_reachable_graph(
    session: Session, cpg: db.Graph, origin_ids: List[str], reverse: bool = False
) -> FlowfinderGraph:
    """Computes the pointers graph from each of the origin nodes."""
    base_step = (
        session.query(cpg.Edge)
        .filter(
            cpg.Edge.kind.in_([EdgeKind.POINTS_TO, EdgeKind.MAY_ALIAS, EdgeKind.CONTAINS]),
            cpg.Edge.target.in_(origin_ids) if reverse else cpg.Edge.source.in_(origin_ids),
            (cpg.Edge.kind != EdgeKind.MAY_ALIAS) | (cpg.Edge.source != cpg.Edge.target),
        )
        .with_entities(
            cpg.Edge.uuid.label("uuid"),
            cpg.Edge.kind.label("kind"),
            cpg.Edge.source.label("source"),
            cpg.Edge.target.label("target"),
        )
        .cte("base", recursive=True)
    )

    recursive_step = (
        session.query(cpg.Edge)
        .join(
            base_step,
            (
                (cpg.Edge.target == base_step.c.source)
                if reverse
                else (cpg.Edge.source == base_step.c.target)
            )
            & cpg.Edge.kind.in_([EdgeKind.POINTS_TO, EdgeKind.MAY_ALIAS, EdgeKind.CONTAINS])
            & ((cpg.Edge.kind != EdgeKind.MAY_ALIAS) | (cpg.Edge.source != cpg.Edge.target)),
        )
        .with_entities(
            cpg.Edge.uuid.label("uuid"),
            cpg.Edge.kind.label("kind"),
            cpg.Edge.source.label("source"),
            cpg.Edge.target.label("target"),
        )
    )

    edges = session.query(base_step.union(recursive_step)).all()

    node_uuids = set(
        itertools.chain(
            (edge[2] for edge in edges),
            (edge[3] for edge in edges),
        )
    )

    nodes = session.query(cpg.Node).filter(cpg.Node.uuid.in_(node_uuids)).all()

    flowfinder_nodes = _format_nodes_for_flowfinder(nodes)
    flowfinder_edges = _format_edges_for_flowfinder(edges)

    return FlowfinderGraph(nodes=flowfinder_nodes, edges=flowfinder_edges)


def get_forward_allocation_graph(
    session: Session, cpg: db.Graph, origin_ids: List[str]
) -> FlowfinderGraph:
    """Computes the allocation graph from each of the origin nodes."""
    base_step = (
        session.query(cpg.Edge)
        .filter(
            cpg.Edge.kind == EdgeKind.ALLOCATES,
            cpg.Edge.source.in_(origin_ids),
        )
        .join(
            cpg.Node,
            (cpg.Node.uuid == cpg.Edge.target) & (cpg.Node.kind == NodeKind.MEMORY_LOCATION),
        )
        .with_entities(
            cpg.Edge.uuid.label("uuid"),
            cpg.Edge.kind.label("kind"),
            cpg.Edge.source.label("source"),
            cpg.Edge.target.label("target"),
        )
        .cte("base", recursive=True)
    )

    recursive_step = (
        session.query(cpg.Edge)
        .join(
            base_step,
            (cpg.Edge.source == base_step.c.target) & (cpg.Edge.kind == EdgeKind.CONTAINS),
        )
        .with_entities(
            cpg.Edge.uuid.label("uuid"),
            cpg.Edge.kind.label("kind"),
            cpg.Edge.source.label("source"),
            cpg.Edge.target.label("target"),
        )
    )

    edges = session.query(base_step.union(recursive_step)).all()

    node_uuids = set(
        itertools.chain(
            (edge[2] for edge in edges),
            (edge[3] for edge in edges),
        )
    )

    nodes = session.query(cpg.Node).filter(cpg.Node.uuid.in_(node_uuids)).all()

    flowfinder_nodes = _format_nodes_for_flowfinder(nodes)
    flowfinder_edges = _format_edges_for_flowfinder(edges)

    return FlowfinderGraph(nodes=flowfinder_nodes, edges=flowfinder_edges)


def get_reverse_allocation_graph(
    session: Session, cpg: db.Graph, origin_ids: List[str]
) -> FlowfinderGraph:
    """Computes the allocation graph from each of the origin nodes."""
    base_step = (
        session.query(cpg.Edge)
        .filter(
            cpg.Edge.kind.in_([EdgeKind.ALLOCATES, EdgeKind.CONTAINS]),
            cpg.Edge.target.in_(origin_ids),
        )
        .with_entities(
            cpg.Edge.uuid.label("uuid"),
            cpg.Edge.kind.label("kind"),
            cpg.Edge.source.label("source"),
            cpg.Edge.target.label("target"),
        )
        .cte("base", recursive=True)
    )

    recursive_step = (
        session.query(cpg.Edge)
        .join(
            base_step,
            (cpg.Edge.target == base_step.c.source)
            & cpg.Edge.kind.in_([EdgeKind.ALLOCATES, EdgeKind.CONTAINS]),
        )
        .with_entities(
            cpg.Edge.uuid.label("uuid"),
            cpg.Edge.kind.label("kind"),
            cpg.Edge.source.label("source"),
            cpg.Edge.target.label("target"),
        )
    )

    edges = session.query(base_step.union(recursive_step)).all()

    node_uuids = set(
        itertools.chain(
            (edge[2] for edge in edges),
            (edge[3] for edge in edges),
        )
    )

    nodes = session.query(cpg.Node).filter(cpg.Node.uuid.in_(node_uuids)).all()

    flowfinder_nodes = _format_nodes_for_flowfinder(nodes)
    flowfinder_edges = _format_edges_for_flowfinder(edges)

    return FlowfinderGraph(nodes=flowfinder_nodes, edges=flowfinder_edges)


def get_memory_subregion_graph(
    session: Session, cpg: db.Graph, origin_ids: List[str], reverse: bool = False
) -> FlowfinderGraph:
    """Computes the memory containment graph from each of the origin nodes."""
    base_step = (
        session.query(cpg.Edge)
        .filter(
            cpg.Edge.kind == EdgeKind.CONTAINS,
            cpg.Edge.target.in_(origin_ids) if reverse else cpg.Edge.source.in_(origin_ids),
        )
        .with_entities(
            cpg.Edge.uuid.label("uuid"),
            cpg.Edge.kind.label("kind"),
            cpg.Edge.source.label("source"),
            cpg.Edge.target.label("target"),
        )
        .cte("base", recursive=True)
    )

    recursive_step = (
        session.query(cpg.Edge)
        .join(
            base_step,
            (cpg.Edge.kind == EdgeKind.CONTAINS)
            & (
                (cpg.Edge.target == base_step.c.source)
                if reverse
                else (cpg.Edge.target == base_step.c.source)
            ),
        )
        .with_entities(
            cpg.Edge.uuid.label("uuid"),
            cpg.Edge.kind.label("kind"),
            cpg.Edge.source.label("source"),
            cpg.Edge.target.label("target"),
        )
    )

    edges = session.query(base_step.union(recursive_step)).all()

    node_uuids = set(
        itertools.chain(
            (edge[2] for edge in edges),
            (edge[3] for edge in edges),
        )
    )

    nodes = session.query(cpg.Node).filter(cpg.Node.uuid.in_(node_uuids)).all()

    flowfinder_nodes = _format_nodes_for_flowfinder(nodes)
    flowfinder_edges = _format_edges_for_flowfinder(edges)

    return FlowfinderGraph(nodes=flowfinder_nodes, edges=flowfinder_edges)


def get_alias_graph(session: Session, cpg: db.Graph, origin_ids: List[str]) -> FlowfinderGraph:
    """Computes the memory aliasing graph from each of the origin nodes."""
    base_step = (
        session.query(cpg.Edge)
        .filter(
            cpg.Edge.kind == EdgeKind.MAY_ALIAS,
            cpg.Edge.source.in_(origin_ids),
            cpg.Edge.source != cpg.Edge.target,
        )
        .with_entities(
            cpg.Edge.uuid.label("uuid"),
            cpg.Edge.kind.label("kind"),
            cpg.Edge.source.label("source"),
            cpg.Edge.target.label("target"),
        )
        .cte("base", recursive=True)
    )

    recursive_step = (
        session.query(cpg.Edge)
        .join(
            base_step,
            (cpg.Edge.kind == EdgeKind.MAY_ALIAS)
            & (cpg.Edge.source == base_step.c.target)
            & (cpg.Edge.source != cpg.Edge.target),
        )
        .with_entities(
            cpg.Edge.uuid.label("uuid"),
            cpg.Edge.kind.label("kind"),
            cpg.Edge.source.label("source"),
            cpg.Edge.target.label("target"),
        )
    )

    edges = session.query(base_step.union(recursive_step)).all()

    node_uuids = set(
        itertools.chain(
            (edge[2] for edge in edges),
            (edge[3] for edge in edges),
        )
    )

    nodes = session.query(cpg.Node).filter(cpg.Node.uuid.in_(node_uuids)).all()

    flowfinder_nodes = _format_nodes_for_flowfinder(nodes)
    flowfinder_edges = _format_edges_for_flowfinder(edges)

    return FlowfinderGraph(nodes=flowfinder_nodes, edges=flowfinder_edges)


###################### control flow ############################################


# Note: cfg_nodes is a List of targets
def _add_entry_blocks_to_cfnodes(session: Session, cpg: db.Graph, cfg_uuids: CTE) -> Iterable[Node]:
    EntryInstruction = aliased(cpg.Edge)
    EntryBlock = aliased(cpg.Edge)
    cfg_with_entry_blocks_uuids = (
        session.query(cfg_uuids)
        .union(
            session.query(cfg_uuids)
            .join(
                EntryInstruction,
                (EntryInstruction.kind == EdgeKind.BLOCK_TO_ENTRY_INSTRUCTION)
                & (EntryInstruction.target == cfg_uuids.c.uuid),
            )
            .join(
                EntryBlock,
                (EntryBlock.kind == EdgeKind.FUNCTION_TO_ENTRY_BLOCK)
                & (EntryBlock.target == EntryInstruction.source),
            )
            .with_entities(EntryBlock.source.label("uuid"))
        )
        .cte()
    )
    return session.query(cpg.Node).filter(cpg.Node.uuid.in_(cfg_with_entry_blocks_uuids))


def _get_control_flow_flowfinder_graph(
    session: Session, cpg: db.Graph, control_flow_nodes: Iterable[Node]
) -> FlowfinderGraph:
    control_flow_uuids = [node.uuid for node in control_flow_nodes]

    BlockToEntryEdge = aliased(cpg.Edge)

    flowfinder_nodes = _format_nodes_for_flowfinder(control_flow_nodes)
    flowfinder_edges = [
        FlowfinderEdge(
            edge_id=edge_id,
            edge_kind=edge_kind.value,
            source_id=source_id,
            target_id=target_id,
        )
        for (edge_id, edge_kind, source_id, target_id) in (
            session.query(cpg.Edge)
            .filter(
                cpg.Edge.kind == EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION,
                cpg.Edge.source.in_(control_flow_uuids),
                cpg.Edge.target.in_(control_flow_uuids),
            )
            .with_entities(
                cpg.Edge.uuid,
                cpg.Edge.kind,
                cpg.Edge.source,
                cpg.Edge.target,
            )
            .all()
        )
    ]

    flowfinder_edges.extend(
        [
            FlowfinderEdge(
                edge_id=edge_id,
                edge_kind="FunctionToEntryInstruction",
                source_id=source_id,
                target_id=target_id,
            )
            for (edge_id, source_id, target_id) in (
                session.query(cpg.Edge)
                .join(BlockToEntryEdge, cpg.Edge.target == BlockToEntryEdge.source)
                .filter(
                    cpg.Edge.kind == EdgeKind.FUNCTION_TO_ENTRY_BLOCK,
                    BlockToEntryEdge.kind == EdgeKind.BLOCK_TO_ENTRY_INSTRUCTION,
                    cpg.Edge.source.in_(control_flow_uuids),
                    BlockToEntryEdge.target.in_(control_flow_uuids),
                )
                .with_entities(
                    func.concat(cpg.Edge.uuid, "-->", BlockToEntryEdge.uuid),
                    cpg.Edge.source,
                    BlockToEntryEdge.target,
                )
                .all()
            )
        ]
    )

    return FlowfinderGraph(nodes=flowfinder_nodes, edges=flowfinder_edges)


def get_control_flow_slice(
    session: Session, cpg: db.Graph, source_id: str, sink_id: str
) -> FlowfinderGraph:
    """Computes the dataflow slice between source_id and sink_id."""
    from_source = (
        db.PathBuilder(db.Path)
        .starting_at(lambda Node: Node.uuid == source_id)
        .continuing_while(
            lambda _, Edge: Edge.kind == EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION
        )
        .build(
            cpg,
            keep_start=False,
            exploration_bound=MATE_SERVER_EXPLORATION_BOUND,
        )
    )

    to_sink = (
        db.PathBuilder(db.Path)
        .stopping_at(lambda Node: Node.uuid == sink_id)
        .continuing_while(
            lambda _, Edge: Edge.kind == EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION
        )
        .reverse()
        .build(
            cpg,
            keep_start=False,
            exploration_bound=MATE_SERVER_EXPLORATION_BOUND,
        )
    )

    control_flow_nodes = (
        session.query(from_source)
        .join(to_sink, from_source.target == to_sink.source)
        .join(cpg.Node, from_source.target == cpg.Node.uuid)
        .with_entities(cpg.Node)
        .all()
    )

    control_flow_uuids = {n.uuid for n in control_flow_nodes}

    flowfinder_nodes = _format_nodes_for_flowfinder(control_flow_nodes)
    flowfinder_edges = [
        FlowfinderEdge(
            edge_id=edge_id,
            edge_kind=edge_kind.value,
            source_id=source_id,
            target_id=target_id,
        )
        for (edge_id, edge_kind, source_id, target_id) in (
            session.query(cpg.Edge)
            .filter(
                cpg.Edge.kind == EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION,
                cpg.Edge.source.in_(control_flow_uuids),
                cpg.Edge.target.in_(control_flow_uuids),
            )
            .with_entities(
                cpg.Edge.uuid,
                cpg.Edge.kind,
                cpg.Edge.source,
                cpg.Edge.target,
            )
            .all()
        )
    ]

    return FlowfinderGraph(nodes=flowfinder_nodes, edges=flowfinder_edges)


def get_reverse_control_flow_graph(
    session: Session, cpg: db.Graph, origin_ids: List[str]
) -> FlowfinderGraph:
    """Computes the control flow graph from each of the origin nodes."""

    control_flow_nodes = (
        db.PathBuilder()
        .reverse()
        .stopping_at(lambda Node: Node.uuid.in_(origin_ids))
        .continuing_while(
            lambda _, Edge: Edge.kind == EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION
        )
        .build(cpg, keep_start=False)
    )
    control_flow_uuids = (
        session.query(control_flow_nodes)
        .with_entities(control_flow_nodes.source.label("uuid"))
        .cte()
    )
    control_flow_plus_entry_nodes = _add_entry_blocks_to_cfnodes(session, cpg, control_flow_uuids)
    return _get_control_flow_flowfinder_graph(session, cpg, control_flow_plus_entry_nodes)


def get_forward_control_flow_graph(
    session: Session, cpg: db.Graph, origin_ids: List[str]
) -> FlowfinderGraph:
    """Computes the control flow graph from each of the origin nodes."""

    FunctionToEntry = aliased(cpg.Edge)
    EntryToInstruction = aliased(cpg.Edge)

    origin_ids.extend(
        [
            n[0]
            for n in (
                session.query(FunctionToEntry)
                .filter(
                    FunctionToEntry.kind == EdgeKind.FUNCTION_TO_ENTRY_BLOCK,
                    FunctionToEntry.source.in_(origin_ids),
                )
                .join(
                    EntryToInstruction,
                    (EntryToInstruction.kind == EdgeKind.BLOCK_TO_ENTRY_INSTRUCTION)
                    & (FunctionToEntry.target == EntryToInstruction.source),
                )
                .with_entities(EntryToInstruction.target)
                .all()
            )
        ]
    )

    control_flow_nodes = (
        db.PathBuilder()
        .starting_at(lambda Node: Node.uuid.in_(origin_ids))
        .continuing_while(
            lambda _, Edge: Edge.kind == EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION
        )
        .build(cpg, keep_start=False)
    )
    control_flow_uuids = (
        session.query(control_flow_nodes)
        .with_entities(control_flow_nodes.target.label("uuid"))
        .cte()
    )
    control_flow_plus_entry_nodes = _add_entry_blocks_to_cfnodes(session, cpg, control_flow_uuids)
    return _get_control_flow_flowfinder_graph(session, cpg, control_flow_plus_entry_nodes)


###################### control dependence ######################################


def get_forward_control_dependence_graph(
    session: Session, cpg: db.Graph, origin_ids: List[str]
) -> FlowfinderGraph:
    control_dependence_query = (
        db.PathBuilder(db.Path)
        .starting_at(lambda Node: Node.uuid.in_(origin_ids))
        .continuing_while(
            lambda _, Edge: Edge.kind.in_(
                [
                    EdgeKind.TERMINATOR_INSTRUCTION_TO_CONTROL_DEPENDENT_INSTRUCTION,
                    EdgeKind.FUNCTION_ENTRY_TO_CONTROL_DEPENDENT_INSTRUCTION,
                ]
            )
        )
        .build(
            cpg,
            keep_start=False,
            keep_edge=True,
            exploration_bound=MATE_SERVER_EXPLORATION_BOUND,
        )
    )

    control_dependence_edges = (
        session.query(control_dependence_query)
        .join(cpg.Edge, cpg.Edge.uuid == control_dependence_query.edge)
        .with_entities(cpg.Edge.uuid, cpg.Edge.kind, cpg.Edge.source, cpg.Edge.target)
        .all()
    )

    node_uuids = set()
    for edge in control_dependence_edges:
        node_uuids.add(edge[2])
        node_uuids.add(edge[3])

    control_dependence_nodes = session.query(cpg.Node).filter(cpg.Node.uuid.in_(node_uuids)).all()

    flowfinder_nodes = _format_nodes_for_flowfinder(control_dependence_nodes)
    flowfinder_edges = _format_edges_for_flowfinder(control_dependence_edges)

    return FlowfinderGraph(nodes=flowfinder_nodes, edges=flowfinder_edges)


def get_reverse_control_dependence_graph(
    session: Session, cpg: db.Graph, origin_ids: List[str]
) -> FlowfinderGraph:
    control_dependence_query = (
        db.PathBuilder(db.Path)
        .stopping_at(lambda Node: Node.uuid.in_(origin_ids))
        .continuing_while(
            lambda _, Edge: Edge.kind.in_(
                [
                    EdgeKind.TERMINATOR_INSTRUCTION_TO_CONTROL_DEPENDENT_INSTRUCTION,
                    EdgeKind.FUNCTION_ENTRY_TO_CONTROL_DEPENDENT_INSTRUCTION,
                ]
            )
        )
        .reverse()
        .build(
            cpg,
            keep_start=False,
            keep_edge=True,
            exploration_bound=MATE_SERVER_EXPLORATION_BOUND,
        )
    )

    control_dependence_edges = (
        session.query(control_dependence_query)
        .join(cpg.Edge, cpg.Edge.uuid == control_dependence_query.edge)
        .with_entities(cpg.Edge.uuid, cpg.Edge.kind, cpg.Edge.source, cpg.Edge.target)
        .all()
    )

    node_uuids = set()
    for edge in control_dependence_edges:
        node_uuids.add(edge[2])
        node_uuids.add(edge[3])

    control_dependence_nodes = session.query(cpg.Node).filter(cpg.Node.uuid.in_(node_uuids)).all()

    flowfinder_nodes = _format_nodes_for_flowfinder(control_dependence_nodes)
    flowfinder_edges = _format_edges_for_flowfinder(control_dependence_edges)

    return FlowfinderGraph(nodes=flowfinder_nodes, edges=flowfinder_edges)


def get_control_dependence_slice(
    session: Session, cpg: db.Graph, source_id: str, sink_id: str
) -> FlowfinderGraph:
    """Computes the mutual control dependence between source_id and sink_id."""
    to_source = (
        db.PathBuilder(db.Path)
        .stopping_at(lambda Node: Node.uuid == source_id)
        .continuing_while(
            lambda _, Edge: (
                (
                    Edge.kind.in_(
                        [
                            EdgeKind.TERMINATOR_INSTRUCTION_TO_CONTROL_DEPENDENT_INSTRUCTION,
                            EdgeKind.FUNCTION_ENTRY_TO_CONTROL_DEPENDENT_INSTRUCTION,
                        ]
                    )
                    & (Edge.target != sink_id)
                )
            )
        )
        .reverse()
        .build(
            cpg,
            keep_start=False,
            keep_edge=True,
            exploration_bound=MATE_SERVER_EXPLORATION_BOUND,
        )
    )

    to_sink = (
        db.PathBuilder(db.Path)
        .stopping_at(lambda Node: Node.uuid == sink_id)
        .continuing_while(
            lambda _, Edge: (
                Edge.kind.in_(
                    [
                        EdgeKind.TERMINATOR_INSTRUCTION_TO_CONTROL_DEPENDENT_INSTRUCTION,
                        EdgeKind.FUNCTION_ENTRY_TO_CONTROL_DEPENDENT_INSTRUCTION,
                    ]
                )
                & (Edge.target != source_id)
            )
        )
        .reverse()
        .build(
            cpg,
            keep_start=False,
            keep_edge=True,
            exploration_bound=MATE_SERVER_EXPLORATION_BOUND,
        )
    )

    mutual_controls = {
        n[0]
        for n in (
            session.query(to_source)
            .join(to_sink, to_source.source == to_sink.source)
            .with_entities(to_source.source)
            .all()
        )
    }

    logger.debug(f"Found {len(mutual_controls)} mutual control dependencies")

    from_controls = (
        db.PathBuilder(db.Path)
        .starting_at(lambda Node: Node.uuid.in_(mutual_controls))
        .continuing_while(
            lambda _, Edge: (
                Edge.kind.in_(
                    [
                        EdgeKind.TERMINATOR_INSTRUCTION_TO_CONTROL_DEPENDENT_INSTRUCTION,
                        EdgeKind.FUNCTION_ENTRY_TO_CONTROL_DEPENDENT_INSTRUCTION,
                    ]
                )
                & (Edge.target.notin_(mutual_controls))
            )
        )
        .build(
            cpg,
            keep_start=False,
            keep_edge=True,
            exploration_bound=MATE_SERVER_EXPLORATION_BOUND,
        )
    )

    control_edge_uuids = {
        e[0]
        for e in (
            session.query(from_controls)
            .join(to_source, from_controls.edge == to_source.edge)
            .with_entities(from_controls.edge)
            .union(
                session.query(from_controls)
                .join(to_sink, from_controls.edge == to_sink.edge)
                .with_entities(from_controls.edge)
            )
            .all()
        )
    }

    logger.debug(f"{len(control_edge_uuids)} control dependency edges")

    edges = _unique_edges(
        session.query(cpg.Edge)
        .filter(cpg.Edge.uuid.in_(control_edge_uuids))
        .with_entities(
            cpg.Edge.uuid,
            cpg.Edge.kind,
            cpg.Edge.source,
            cpg.Edge.target,
        )
        .all()
    )

    node_uuids = set()
    for edge in edges:
        node_uuids.add(edge[2])
        node_uuids.add(edge[3])

    nodes = session.query(cpg.Node).filter(cpg.Node.uuid.in_(node_uuids)).all()

    flowfinder_nodes = _format_nodes_for_flowfinder(nodes)
    flowfinder_edges = _format_edges_for_flowfinder(edges)

    logger.debug(
        f"Returning flowfinder graph with {len(flowfinder_nodes)} nodes and {len(flowfinder_edges)} edges"
    )

    return FlowfinderGraph(nodes=flowfinder_nodes, edges=flowfinder_edges)


########################### call graph #########################################


def get_callsites_graph(session: Session, cpg: db.Graph, origin_ids: List[str]) -> FlowfinderGraph:
    """Computes the callsites graph from each of the origin nodes."""
    callgraph_edges = (
        session.query(cpg.Edge)
        .filter(cpg.Edge.kind == EdgeKind.CALL_TO_FUNCTION, cpg.Edge.target.in_(origin_ids))
        .with_entities(
            cpg.Edge.uuid,
            cpg.Edge.kind,
            cpg.Edge.source,
            cpg.Edge.target,
        )
        .all()
    )

    signature_edges = (
        session.query(cpg.Edge)
        .filter(
            cpg.Edge.kind == EdgeKind.DATAFLOW_SIGNATURE_FOR_CALLSITE,
            cpg.Edge.source.in_(origin_ids),
        )
        .with_entities(
            cpg.Edge.uuid,
            cpg.Edge.kind,
            cpg.Edge.source,
            cpg.Edge.target,
        )
        .all()
    )

    # TODO(sm): kludge to avoid drawing multiple edges due to differing contexts (not displayed in UI)
    edges = _unique_edges(itertools.chain(callgraph_edges, signature_edges))
    node_uuids = set(
        itertools.chain(
            (edge[2] for edge in edges),
            (edge[3] for edge in edges),
        )
    )

    nodes = session.query(cpg.Node).filter(cpg.Node.uuid.in_(node_uuids)).all()

    flowfinder_nodes = _format_nodes_for_flowfinder(nodes)
    flowfinder_edges = _format_edges_for_flowfinder(edges)

    return FlowfinderGraph(nodes=flowfinder_nodes, edges=flowfinder_edges)


def get_callers_graph(session: Session, cpg: db.Graph, origin_ids: List[str]) -> FlowfinderGraph:
    """Computes the callers graph from each of the origin nodes."""
    callgraph_edges = (
        session.query(cpg.Edge)
        .filter(cpg.Edge.kind == EdgeKind.CALLGRAPH, cpg.Edge.target.in_(origin_ids))
        .with_entities(
            cpg.Edge.uuid,
            cpg.Edge.kind,
            cpg.Edge.source,
            cpg.Edge.target,
        )
        .all()
    )

    BlockEdge = aliased(cpg.Edge)
    FunEdge = aliased(cpg.Edge)
    signature_edges = (
        session.query(cpg.Edge)
        .filter(
            cpg.Edge.kind == EdgeKind.DATAFLOW_SIGNATURE_FOR_CALLSITE,
            cpg.Edge.source.in_(origin_ids),
        )
        .join(
            BlockEdge,
            (BlockEdge.kind == EdgeKind.INSTRUCTION_TO_PARENT_BLOCK)
            & (cpg.Edge.source == BlockEdge.source),
        )
        .join(
            FunEdge,
            (FunEdge.kind == EdgeKind.BLOCK_TO_PARENT_FUNCTION)
            & (BlockEdge.target == FunEdge.source),
        )
        .with_entities(
            cpg.Edge.uuid,
            literal(EdgeKind.CALLGRAPH.value).label("kind"),
            cpg.Edge.source,
            cpg.Edge.target,
        )
        .all()
    )

    # TODO(sm): kludge to avoid drawing multiple edges due to differing contexts (not displayed in UI)
    edges = _unique_edges(itertools.chain(callgraph_edges, signature_edges))
    node_uuids = set(
        itertools.chain(
            (edge[2] for edge in edges),
            (edge[3] for edge in edges),
        )
    )

    nodes = session.query(cpg.Node).filter(cpg.Node.uuid.in_(node_uuids)).all()

    flowfinder_nodes = _format_nodes_for_flowfinder(nodes)
    flowfinder_edges = _format_edges_for_flowfinder(edges)

    return FlowfinderGraph(nodes=flowfinder_nodes, edges=flowfinder_edges)


def get_callees_graph(session: Session, cpg: db.Graph, origin_ids: List[str]) -> FlowfinderGraph:
    """Computes the callees graph from each of the origin nodes."""
    callgraph_edges = (
        session.query(cpg.Edge)
        .filter(cpg.Edge.kind == EdgeKind.CALLGRAPH, cpg.Edge.source.in_(origin_ids))
        .with_entities(
            cpg.Edge.uuid,
            cpg.Edge.kind,
            cpg.Edge.source,
            cpg.Edge.target,
        )
        .all()
    )

    call_to_function_edges = (
        session.query(cpg.Edge)
        .filter(cpg.Edge.kind == EdgeKind.CALL_TO_FUNCTION, cpg.Edge.source.in_(origin_ids))
        .with_entities(
            cpg.Edge.uuid,
            cpg.Edge.kind,
            cpg.Edge.source,
            cpg.Edge.target,
        )
        .all()
    )

    # TODO(sm): kludge to avoid drawing multiple edges due to differing contexts (not displayed in UI)
    edges = _unique_edges(itertools.chain(callgraph_edges, call_to_function_edges))
    node_uuids = set(
        itertools.chain(
            (edge[2] for edge in edges),
            (edge[3] for edge in edges),
        )
    )

    nodes = session.query(cpg.Node).filter(cpg.Node.uuid.in_(node_uuids)).all()

    flowfinder_nodes = _format_nodes_for_flowfinder(nodes)
    flowfinder_edges = _format_edges_for_flowfinder(edges)

    return FlowfinderGraph(nodes=flowfinder_nodes, edges=flowfinder_edges)


def get_signatures_graph(session: Session, cpg: db.Graph, origin_ids: List[str]) -> FlowfinderGraph:
    """Computes the signatures graph from each of the origin nodes."""
    callsite_edges = (
        session.query(cpg.Edge)
        .filter(
            cpg.Edge.kind == EdgeKind.DATAFLOW_SIGNATURE_FOR_CALLSITE,
            cpg.Edge.target.in_(origin_ids),
        )
        .with_entities(
            cpg.Edge.uuid,
            cpg.Edge.kind,
            cpg.Edge.source,
            cpg.Edge.target,
        )
        .all()
    )

    function_edges = (
        session.query(cpg.Edge)
        .filter(
            cpg.Edge.kind == EdgeKind.DATAFLOW_SIGNATURE_FOR_FUNCTION,
            cpg.Edge.target.in_(origin_ids),
        )
        .with_entities(
            cpg.Edge.uuid,
            cpg.Edge.kind,
            cpg.Edge.source,
            cpg.Edge.target,
        )
        .all()
    )

    node_uuids = set(
        itertools.chain(
            (edge[2] for edge in callsite_edges),
            (edge[3] for edge in callsite_edges),
            (edge[2] for edge in function_edges),
            (edge[3] for edge in function_edges),
        )
    )

    nodes = session.query(cpg.Node).filter(cpg.Node.uuid.in_(node_uuids)).all()

    flowfinder_nodes = _format_nodes_for_flowfinder(nodes)
    # Don't draw DATAFLOW_SIGNATURE_FOR_FUNCTION edges since they are already captured by nesting
    flowfinder_edges = _format_edges_for_flowfinder(callsite_edges)

    return FlowfinderGraph(nodes=flowfinder_nodes, edges=flowfinder_edges)


def get_call_graph_slice(
    session: Session, cpg: db.Graph, source_id: str, sink_id: str
) -> FlowfinderGraph:
    calls_source = (
        db.PathBuilder(CallGraphPath)
        .stopping_at(lambda Node: Node.uuid == source_id)
        .reverse()
        .continuing_while(
            lambda Config, Edge: (
                (Config.c.edge.is_(None)) | Edge.target.notin_([source_id, sink_id])
            ),
            edge_detail=False,
        )
        .build(
            cpg,
            keep_start=False,
            exploration_bound=MATE_SERVER_EXPLORATION_BOUND,
        )
    )

    source_callers = {f[0] for f in session.query(calls_source.source).distinct().all()}

    to_sink = (
        db.PathBuilder(CallGraphPath)
        .stopping_at(lambda Node: Node.uuid == sink_id)
        .reverse()
        .continuing_while(
            lambda Config, Edge: (
                (Config.c.edge.is_(None))
                | (Edge.target.notin_(source_callers) & Edge.target.notin_([source_id, sink_id]))
            ),
            edge_detail=False,
        )
        .build(
            cpg,
            keep_start=False,
            keep_edge=True,
            exploration_bound=MATE_SERVER_EXPLORATION_BOUND,
        )
    )

    sink_callers = set()
    sink_edges = set()
    for caller, edge in session.query(to_sink.source, to_sink.edge).all():
        sink_callers.add(caller)
        sink_edges.add(edge)

    to_source = (
        db.PathBuilder(CallGraphPath)
        .stopping_at(lambda Node: Node.uuid == source_id)
        .reverse()
        .continuing_while(
            lambda Config, Edge: (
                (Config.c.edge.is_(None))
                | (Edge.target.notin_(sink_callers) & Edge.target.notin_([source_id, sink_id]))
            ),
            edge_detail=False,
        )
        .build(
            cpg,
            keep_start=False,
            keep_edge=True,
            exploration_bound=MATE_SERVER_EXPLORATION_BOUND,
        )
    )

    source_callers = set()
    source_edges = set()
    for caller, edge in session.query(to_source.source, to_source.edge).all():
        source_callers.add(caller)
        source_edges.add(edge)

    mutual_callers = source_callers.intersection(sink_callers)
    potential_edges = sink_edges.union(source_edges)

    from_callers = (
        db.PathBuilder(CallGraphPath)
        .starting_at(lambda Node: Node.uuid.in_(mutual_callers))
        .continuing_while(lambda _, Edge: Edge.uuid.in_(potential_edges), edge_detail=False)
        .build(
            cpg,
            keep_start=False,
            keep_edge=True,
            exploration_bound=MATE_SERVER_EXPLORATION_BOUND,
        )
    )

    callgraph_edge_uuids = {
        e[0] for e in (session.query(from_callers).with_entities(from_callers.edge).all())
    }

    edges = _unique_edges(
        session.query(cpg.Edge)
        .filter(cpg.Edge.uuid.in_(callgraph_edge_uuids))
        .with_entities(
            cpg.Edge.uuid,
            cpg.Edge.kind,
            cpg.Edge.source,
            cpg.Edge.target,
        )
        .all()
    )
    node_uuids = set()
    for edge in edges:
        node_uuids.add(edge[2])
        node_uuids.add(edge[3])

    nodes = session.query(cpg.Node).filter(cpg.Node.uuid.in_(node_uuids)).all()

    flowfinder_nodes = _format_nodes_for_flowfinder(nodes)
    flowfinder_edges = _format_edges_for_flowfinder(edges)

    return FlowfinderGraph(nodes=flowfinder_nodes, edges=flowfinder_edges)


################ formatting ######################################################


def _format_edges_for_flowfinder(
    edges: Iterable[Tuple[str, EdgeKind, str, str]]
) -> List[FlowfinderEdge]:
    return [
        FlowfinderEdge(
            edge_id=edge_id,
            edge_kind=edge_kind.value,
            source_id=source_id,
            target_id=target_id,
        )
        for (edge_id, edge_kind, source_id, target_id) in edges
    ]


def _source_for_node(node: Node) -> Tuple[Optional[str], Optional[str]]:
    source_location = node.attributes.get("location")
    source_code = node.attributes.get("source_code")
    source_label = None
    if source_location is None:
        source_id = None
    else:
        file = source_location.get("file")
        line = source_location.get("line")
        if (file is None) or (line is None):
            source_id = None
        else:
            source_id = f"Source: {file}:{line}"
            if source_code is not None:
                source_label = f"{file}:{line}: {source_code}"
    return source_id, source_label


def _pretty_print_dwarf_type(t: DWARFType) -> str:
    """Pretty print a DWARFType node in a C-like syntax."""
    if t.tag == "DW_TAG_unspecified_parameters":
        return "..."
    elif not t.is_derived:
        return t.name
    else:
        tmp = _pretty_print_dwarf_type(t.base_type)
        if t.is_pointer:
            return f"{tmp}*"
        elif t.is_reference:
            return f"{tmp}&"
        elif t.is_array:
            try:
                return f"{tmp}[{t.subrange.count}]"
            except:
                return f"{tmp}[]"
        else:
            return tmp


def _pretty_print_machine_function(func: MachineFunction) -> str:
    """Pretty print a function signature in a C-like syntax."""
    try:
        res = func.demangled_name.split("(")[0] + "("
        for i, arg in enumerate(func.arguments):
            if i > 0:
                res += ", "
            res += f"{_pretty_print_dwarf_type(arg.dwarf_type)} {arg.name}"
        res += ")"
        return res
    except:
        return func.demangled_name


def _format_nodes_for_flowfinder(nodes: Iterable[Node]) -> List[FlowfinderNode]:
    nodes_formatted_for_flowfinder = []
    known_functions = set()
    known_source_code_lines = set()
    for node in nodes:
        try:  # this try will succeed for nodes that subclass Instruction
            function = node.parent_block.parent_function
            function_id = function.uuid
            source_id, source_label = _source_for_node(node)
            if source_id is not None:
                known_source_code_lines.add((source_id, source_label, function_id))
            nodes_formatted_for_flowfinder.append(
                FlowfinderNode(
                    node_id=node.uuid,
                    node_kind=node.kind.value,
                    opcode=node.opcode.value,
                    source_id=source_id,
                    function_id=function_id,
                    label=node.pretty_string.strip(),
                )
            )
            known_functions.add(function)
        except:
            if node.kind == NodeKind.FUNCTION:
                known_functions.add(node)
            elif node.kind == NodeKind.MACHINE_FUNCTION:
                nodes_formatted_for_flowfinder.append(
                    FlowfinderNode(
                        node_id=node.name,
                        node_kind=node.kind.value,
                        opcode="None",
                        source_id="None",
                        function_id="None",
                        label=_pretty_print_machine_function(node),
                    )
                )
            elif node.kind == NodeKind.MEMORY_LOCATION:
                function_id = "None"
                nodes_formatted_for_flowfinder.append(
                    FlowfinderNode(
                        node_id=node.uuid,
                        node_kind=node.kind.value,
                        opcode="None",
                        source_id="None",
                        function_id=function_id,
                        label=f"{node.attributes['pretty_string']}",
                    )
                )
            elif node.kind in [
                NodeKind.INPUT_SIGNATURE,
                NodeKind.DATAFLOW_SIGNATURE,
                NodeKind.OUTPUT_SIGNATURE,
            ]:
                callsite = node.signature_for
                function = node.signature_for_function
                known_functions.add(function)
                source_id, source_label = _source_for_node(callsite)
                if node.kind == NodeKind.INPUT_SIGNATURE:
                    kind = "Input"
                elif node.kind == NodeKind.OUTPUT_SIGNATURE:
                    kind = "Output"
                else:
                    kind = "Dataflow"
                if source_id is not None:
                    label = (
                        f"{kind} signature for\n{source_id}\n{callsite.attributes['pretty_string']}"
                    )
                else:
                    label = f"{kind} signature for\n{callsite.attributes['pretty_string']}"
                nodes_formatted_for_flowfinder.append(
                    FlowfinderNode(
                        node_id=node.uuid,
                        node_kind=node.kind.value,
                        opcode="None",
                        source_id="None",
                        function_id=function.uuid,
                        label=label,
                    )
                )
            elif node.kind == NodeKind.ARGUMENT:
                function = node.parent_function
                known_functions.add(function)
                nodes_formatted_for_flowfinder.append(
                    FlowfinderNode(
                        node_id=node.uuid,
                        node_kind=node.kind.value,
                        opcode="None",
                        source_id="None",
                        function_id=function.uuid,
                        label=f"Argument: {node.attributes['name']}",
                    )
                )
            elif node.kind == NodeKind.LOCAL_VARIABLE:
                function = node.parent_function
                known_functions.add(function)
                nodes_formatted_for_flowfinder.append(
                    FlowfinderNode(
                        node_id=node.uuid,
                        node_kind=node.kind.value,
                        opcode="None",
                        source_id="None",
                        function_id=function.uuid,
                        label=f"Local: {node.attributes['name']}",
                    )
                )
            elif node.kind in [NodeKind.PARAM_BINDING, NodeKind.CALL_RETURN]:
                callsite = node.callsite
                function = callsite.parent_block.parent_function
                source_id, source_label = _source_for_node(callsite)
                if source_id is not None:
                    known_source_code_lines.add((source_id, source_label, function.uuid))
                nodes_formatted_for_flowfinder.append(
                    FlowfinderNode(
                        node_id=node.uuid,
                        node_kind=node.kind.value,
                        opcode="None",
                        source_id=source_id,
                        function_id=function.uuid,
                        label=node.kind.value,
                    )
                )
                known_functions.add(function)
            elif node.kind == NodeKind.GLOBAL_VARIABLE:
                source_id, source_label = _source_for_node(node)
                if source_id is not None:
                    known_source_code_lines.add((source_id, source_label, "None"))
                nodes_formatted_for_flowfinder.append(
                    FlowfinderNode(
                        node_id=node.uuid,
                        node_kind=node.kind.value,
                        opcode="None",
                        source_id=source_id,
                        function_id="None",
                        label=f"{node.attributes['name']}",
                    )
                )
            elif node.kind == NodeKind.CONSTANT:
                nodes_formatted_for_flowfinder.append(
                    FlowfinderNode(
                        node_id=node.uuid,
                        node_kind=node.kind.value,
                        opcode="None",
                        source_id="None",
                        function_id="None",
                        label="Constant",
                    )
                )
            elif node.kind == NodeKind.CONSTANT_FP:
                nodes_formatted_for_flowfinder.append(
                    FlowfinderNode(
                        node_id=node.uuid,
                        node_kind=node.kind.value,
                        opcode="None",
                        source_id="None",
                        function_id="None",
                        label="Floating point constant",
                    )
                )
            elif node.kind == NodeKind.CONSTANT_INT:
                nodes_formatted_for_flowfinder.append(
                    FlowfinderNode(
                        node_id=node.uuid,
                        node_kind=node.kind.value,
                        opcode="None",
                        source_id="None",
                        function_id="None",
                        label=f"Constant: {node.attributes['constant_int_value']}",
                    )
                )
            elif node.kind == NodeKind.CONSTANT_UNDEF:
                nodes_formatted_for_flowfinder.append(
                    FlowfinderNode(
                        node_id=node.uuid,
                        node_kind=node.kind.value,
                        opcode="None",
                        source_id="None",
                        function_id="None",
                        label="Constant: undefined",
                    )
                )
            elif node.kind == NodeKind.CONSTANT_STRING:
                nodes_formatted_for_flowfinder.append(
                    FlowfinderNode(
                        node_id=node.uuid,
                        node_kind=node.kind.value,
                        opcode="None",
                        source_id="None",
                        function_id="None",
                        label=f"Constant: {node.string_value}",
                    )
                )
            else:
                nodes_formatted_for_flowfinder.append(
                    FlowfinderNode(
                        node_id=node.uuid,
                        node_kind=node.kind.value,
                        opcode="None",
                        source_id="None",
                        function_id="None",
                        label=f"{node.kind.value}",
                    )
                )
    # create Function and Source nodes
    for function in known_functions:
        nodes_formatted_for_flowfinder.append(
            FlowfinderNode(
                node_id=function.uuid,
                node_kind=function.kind.value,
                opcode="None",
                source_id="None",
                function_id="None",
                label=function.demangled_name,
            )
        )
    for (source_id, source_code_label, function_id) in known_source_code_lines:
        if source_code_label is None:
            nodes_formatted_for_flowfinder.append(
                FlowfinderNode(
                    node_id=source_id,
                    node_kind="Source",
                    opcode="None",
                    source_id="None",
                    function_id=function_id,
                    label=source_id,
                )
            )
        else:
            nodes_formatted_for_flowfinder.append(
                FlowfinderNode(
                    node_id=source_id,
                    node_kind="Source",
                    opcode="None",
                    source_id="None",
                    function_id=function_id,
                    label=source_code_label,
                )
            )
    return nodes_formatted_for_flowfinder
