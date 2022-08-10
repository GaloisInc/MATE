from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Optional, Tuple

from sqlalchemy.dialects.postgresql import ARRAY, array
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import CTE, case, func, literal, true, tuple_
from sqlalchemy.types import String

import mate_query.db as db
from mate_query.cfl import CSCFGPath
from mate_query.db import BOT

if TYPE_CHECKING:
    from mate_query.cpg.models.node.ast.llvm import Instruction
    from mate_query.db import Graph as CPG


def control_flow_avoiding(
    cpg: CPG,
    start_cte: CTE,
    avoid_map_cte: CTE,
    stop_map_cte: CTE,
    stack_bound: Optional[int] = None,
    limit: Optional[int] = None,
) -> Iterable[Tuple[Optional[str], Instruction, str, Instruction, str]]:
    """Finds pairs of instruction/contexts from ``start_cte`` and ``stop_map_cte`` that are
    reachable in the control-flow graph without passing through the designated nodes in
    ``avoid_map_cte``.

    start_cte must be a CTE with columns ``info``, ``start_uuid`` and ``start_context``.
    avoid_map_cte must be a CTE with columns ``info``, ``start_uuid``, ``start_context``,
    ``avoid_uuid``, and ``avoid_context``. stop_map_cte must be a CTE with columns ``info``,
    ``start_uuid``, ``start_context``, ``stop_uuid``, and ``stop_context``.
    """
    InitialConfiguration = (
        cpg.session.query(start_cte)
        .with_entities(
            start_cte.c.info.label("info"),
            start_cte.c.uuid.label("uuid"),
            array([start_cte.c.context, BOT]).cast(ARRAY(String)).label("stack"),
        )
        .cte()
    )

    AvoidMap = (
        cpg.session.query(avoid_map_cte)
        .with_entities(
            avoid_map_cte.c.info,
            avoid_map_cte.c.start_context,
            avoid_map_cte.c.start_uuid,
            avoid_map_cte.c.avoid_context,
            avoid_map_cte.c.avoid_uuid,
        )
        .cte()
    )

    StopMap = (
        cpg.session.query(stop_map_cte)
        .with_entities(
            stop_map_cte.c.info,
            stop_map_cte.c.start_context,
            stop_map_cte.c.start_uuid,
            stop_map_cte.c.stop_context,
            stop_map_cte.c.stop_uuid,
        )
        .cte()
    )

    PathQuery = (
        db.PathBuilder(PathBase=CSCFGPath)
        .initial_configuration(InitialConfiguration)
        .continuing_while(
            lambda PDA, Edge: (
                (
                    tuple_(
                        PDA.c.info,
                        func.split_part(PDA.c.source_stack[1], literal("-->"), 2),
                        PDA.c.source,
                        func.split_part(PDA.c.stack_top, literal("-->"), 2),
                        Edge.source,
                    ).notin_(AvoidMap)
                )
                & (
                    tuple_(
                        PDA.c.info,
                        PDA.c.source_stack[1],
                        PDA.c.source,
                        func.split_part(PDA.c.stack_top, literal("-->"), 2),
                        Edge.source,
                    ).notin_(AvoidMap)
                )
                & (
                    tuple_(
                        PDA.c.info,
                        func.split_part(PDA.c.source_stack[1], literal("-->"), 2),
                        PDA.c.source,
                        PDA.c.stack_top,
                        Edge.source,
                    ).notin_(AvoidMap)
                )
                & (
                    tuple_(
                        PDA.c.info,
                        PDA.c.source_stack[1],
                        PDA.c.source,
                        PDA.c.stack_top,
                        Edge.target,
                    ).notin_(AvoidMap)
                )
                & (~(PDA.c.stack[2 : func.cardinality(PDA.c.stack)].any(PDA.c.stack_top)))
                & (
                    (func.cardinality(PDA.c.stack) <= stack_bound)
                    if stack_bound is not None
                    else true()
                )
            )
        )
        .build(cpg)
    )

    StartInst = aliased(cpg.Instruction)
    StopInst = aliased(cpg.Instruction)

    query = (
        cpg.session.query(PathQuery)
        .filter(
            (
                tuple_(
                    PathQuery.info,
                    PathQuery.source_stack[1],
                    PathQuery.source,
                    func.split_part(PathQuery.stack_top, literal("-->"), 2),
                    PathQuery.target,
                ).in_(StopMap)
            )
            | (
                tuple_(
                    PathQuery.info,
                    PathQuery.source_stack[1],
                    PathQuery.source,
                    PathQuery.stack_top,
                    PathQuery.target,
                ).in_(StopMap)
            )
        )
        .join(StartInst, PathQuery.source == StartInst.uuid)
        .join(StopInst, PathQuery.target == StopInst.uuid)
        .with_entities(
            PathQuery.info,
            StartInst,
            PathQuery.source_stack[1],
            StopInst,
            case(
                [
                    (
                        PathQuery.stack_top.contains("-->"),
                        func.split_part(PathQuery.stack_top, literal("-->"), 2),
                    )
                ],
                else_=PathQuery.stack_top,
            ),
        )
        .distinct()
    )

    findings = query.all() if limit is None else query.limit(limit).all()

    return findings
