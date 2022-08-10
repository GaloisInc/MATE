from __future__ import annotations

import logging
from collections import defaultdict
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Tuple

from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import join, select, tuple_

from mate.poi.poi_types import Analysis, POIGraphsPair
from mate_common.models.analyses import POI
from mate_common.models.cpg_types import EdgeKind
from mate_common.models.graphs import GraphKind, GraphRequest, NodeRequest, SliceRequest
from mate_query import db
from mate_query.cpg.query.cfg_avoiding import control_flow_avoiding

if TYPE_CHECKING:
    from mate_query.cpg.models.node.ast.llvm import Instruction
    from mate_query.db import Session


logger = logging.getLogger(__name__)


class UseAfterFreePOI(POI):
    """This POI represents a potential place where a heap allocation is used after being freed."""

    free: str
    use: str
    free_contexts: List[str]
    use_contexts: List[str]


class UseAfterFree(Analysis):
    _background: str = dedent(
        """
        Programs can allocate memory dynamically on the heap using functions like
        `malloc` in C.

        Normally, correct programs:

        * **allocate** memory with `malloc()` or similar
        * **use** that memory
        * **free** that memory with `free()` or similar

        A Use After Free vulnerability occurs when memory is referenced (used) after
        it has been freed. This may be useful to an attacker in a variety of ways,
        particularly if the attacker can control the data at the **use** site by
        previously having filled the memory location with desirable values.

        MATE finds execution paths through the program that pass through a `free`,
        reaching a **use** site for a variable without having first passed through a
        (re)allocation function.

        The initial graph loaded for this point of interest shows:

        * the call that frees a memory location
        * the instruction that potentially uses the freed memory

        and either

        * the control flow between these two instructions, if they appear in the same
        function,

        or, if the free and the use are not in the same function:

        * the portion of the call graph that must be traversed between the free and
        potential use site,
        * the control flow of the function containing the free, starting from the free,
        and
        * the control flow of the function containing the potential use, leading up to
        the use site.

        Using MATE, you may try to:

        * Determine whether the use after free is feasible.
        * Determine how a control of the content of that variable could be useful.
        * Identify how to control the content of that variable. Will the content at the
        use site point to the previously used content? Can you cause/control a large
        number of allocations elsewhere so the free memory will likely contain useful
        values?

        Common source of false positives in this analysis include:

        * If an external function performs the proper (re)allocation between the free
        and the use site, MATE may not be able to determine this (as MATE only analyzes
        the code in the challenge binary).
        * Explicit checks that make the potentially vulnerable control flow impossible,
        such as an explicit null pointer check guarding the use site.
        """
    )

    def run(
        self, session: Session, graph: db.Graph, _inputs: Dict[str, Any]
    ) -> Iterable[POIGraphsPair]:
        logger.debug("Running use after free analysis...")

        for free, use, free_contexts, use_contexts in compute_use_after_free(session, graph):
            free_location = free.location_string
            use_location = use.location_string

            poi = UseAfterFreePOI(
                free=free.uuid,
                use=use.uuid,
                free_contexts=free_contexts,
                use_contexts=use_contexts,
                source=free_location,
                sink=use_location,
                insight=(
                    f"Memory deallocated by call to free at `{free_location}` may be "
                    f"subsequently used at `{use_location}`."
                ),
                salient_functions=list(
                    {
                        free.parent_block.parent_function.as_salient(),
                        use.parent_block.parent_function.as_salient(),
                    }
                ),
            )

            from_source = (
                db.PathBuilder(db.Path)
                .starting_at(lambda Node: Node.uuid == free.uuid)
                .continuing_while(
                    lambda _, Edge: Edge.kind == EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION
                )
                .build(graph, keep_start=False)
            )

            to_sink = (
                db.PathBuilder(db.Path)
                .stopping_at(lambda Node: Node.uuid == use.uuid)
                .continuing_while(
                    lambda _, Edge: Edge.kind == EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION
                )
                .reverse()
                .build(graph, keep_start=False)
            )

            is_intraprocedural = (
                session.query(from_source)
                .join(to_sink, from_source.target == to_sink.source)
                .first()
            ) is not None

            if is_intraprocedural:
                graphs = [
                    SliceRequest(
                        build_id=graph.build,
                        source_id=free.uuid,
                        sink_id=use.uuid,
                        kind=GraphKind.ForwardControlFlow,
                        avoid_node_ids=[],
                        focus_node_ids=[],
                    ),
                    NodeRequest(
                        build_id=graph.build,
                        node_id=free.uuid,
                    ),
                    NodeRequest(
                        build_id=graph.build,
                        node_id=use.uuid,
                    ),
                ]
            else:
                graphs = [
                    SliceRequest(
                        build_id=graph.build,
                        source_id=free.parent_block.parent_function.uuid,
                        sink_id=use.parent_block.parent_function.uuid,
                        kind=GraphKind.Callees,
                        avoid_node_ids=[],
                        focus_node_ids=[],
                    ),
                    GraphRequest(
                        build_id=graph.build,
                        origin_node_ids=[free.uuid],
                        kind=GraphKind.ForwardControlFlow,
                    ),
                    GraphRequest(
                        build_id=graph.build,
                        origin_node_ids=[use.uuid],
                        kind=GraphKind.ReverseControlFlow,
                    ),
                    NodeRequest(
                        build_id=graph.build,
                        node_id=free.uuid,
                    ),
                    NodeRequest(
                        build_id=graph.build,
                        node_id=use.uuid,
                    ),
                ]

            yield (poi, graphs)


def compute_use_after_free(
    session: Session, cpg: db.Graph
) -> Iterable[Tuple[Instruction, Instruction, List[str], List[str]]]:
    ## Find Points of Interest
    #
    # We find POIs by querying:
    #
    # - for inter-procedural control flow paths...
    # - that start with calls to free...
    # - that reach an instruction that uses the free'd memory location...
    # - without passing through an instruction that re-allocates that memory location
    #   or checks it against null

    FreeFunction = aliased(cpg.Function)
    CallEdge = aliased(cpg.Edge)
    CallToFree = aliased(cpg.CallSite)
    FreedPointer = aliased(cpg.Node)
    FreedMemoryEdge = aliased(cpg.Edge)
    AliasEdge = aliased(cpg.Edge)
    LoadEdge = aliased(cpg.Edge)
    StoreEdge = aliased(cpg.Edge)
    AllocatesEdge = aliased(cpg.Edge)
    DataflowEdge = aliased(cpg.Edge)
    DataflowSigEdge = aliased(cpg.Edge)
    BaseAllocationEdge = aliased(cpg.Edge)
    BaseAllocation = aliased(cpg.MemoryLocation)

    null_uuids = {
        n[0]
        for n in (
            session.query(cpg.MemoryLocation)
            .filter(cpg.MemoryLocation.attributes["alias_set_identifier"].astext == "*null*")
            .with_entities(cpg.MemoryLocation.uuid)
            .all()
        )
    }

    stop_map_cte = (
        session.query(cpg.DataflowSignature)
        .filter(cpg.DataflowSignature.is_allocator)
        .join(FreeFunction, FreeFunction.name == cpg.DataflowSignature.deallocator)
        .join(
            CallEdge,
            (CallEdge.target == FreeFunction.uuid) & (CallEdge.kind == EdgeKind.CALL_TO_FUNCTION),
        )
        .join(CallToFree, CallToFree.uuid == CallEdge.source)
        .join(FreedPointer, CallToFree.argument0)
        .join(
            FreedMemoryEdge,
            (FreedMemoryEdge.source == FreedPointer.uuid)
            & (FreedMemoryEdge.kind == EdgeKind.POINTS_TO)
            & (FreedMemoryEdge.target.notin_(null_uuids))
            & (
                FreedMemoryEdge.attributes["context"].astext
                == CallEdge.attributes["caller_context"].astext
            ),
        )
        .join(
            BaseAllocationEdge,
            (BaseAllocationEdge.source == FreedMemoryEdge.target)
            & (BaseAllocationEdge.kind == EdgeKind.MAY_ALIAS),
        )
        .join(
            BaseAllocation,
            (BaseAllocationEdge.target == BaseAllocation.uuid)
            & ~BaseAllocation.incoming.any(cpg.Edge.kind == EdgeKind.SUBREGION),
        )
        .join(
            AliasEdge,
            (AliasEdge.source == BaseAllocation.uuid) & (AliasEdge.kind == EdgeKind.MAY_ALIAS),
        )
        .join(
            LoadEdge,
            (LoadEdge.source == AliasEdge.target) & (LoadEdge.kind == EdgeKind.LOAD_MEMORY),
        )
        .with_entities(
            BaseAllocation.uuid.label("info"),
            CallToFree.uuid.label("start_uuid"),
            CallEdge.attributes["caller_context"].astext.label("start_context"),
            LoadEdge.target.label("stop_uuid"),
            LoadEdge.attributes["context"].astext.label("stop_context"),
        )
        .union(
            session.query(cpg.DataflowSignature)
            .filter(cpg.DataflowSignature.is_allocator)
            .join(FreeFunction, FreeFunction.name == cpg.DataflowSignature.deallocator)
            .join(
                CallEdge,
                (CallEdge.target == FreeFunction.uuid)
                & (CallEdge.kind == EdgeKind.CALL_TO_FUNCTION),
            )
            .join(CallToFree, CallToFree.uuid == CallEdge.source)
            .join(FreedPointer, CallToFree.argument0)
            .join(
                FreedMemoryEdge,
                (FreedMemoryEdge.source == FreedPointer.uuid)
                & (FreedMemoryEdge.kind == EdgeKind.POINTS_TO)
                & (FreedMemoryEdge.target.notin_(null_uuids))
                & (
                    FreedMemoryEdge.attributes["context"].astext
                    == CallEdge.attributes["caller_context"].astext
                ),
            )
            .join(
                BaseAllocationEdge,
                (BaseAllocationEdge.source == FreedMemoryEdge.target)
                & (BaseAllocationEdge.kind == EdgeKind.MAY_ALIAS),
            )
            .join(
                BaseAllocation,
                (BaseAllocationEdge.target == BaseAllocation.uuid)
                & ~BaseAllocation.incoming.any(cpg.Edge.kind == EdgeKind.SUBREGION),
            )
            .join(
                AliasEdge,
                (AliasEdge.source == BaseAllocation.uuid) & (AliasEdge.kind == EdgeKind.MAY_ALIAS),
            )
            .join(
                StoreEdge,
                (StoreEdge.target == AliasEdge.target) & (StoreEdge.kind == EdgeKind.STORE_MEMORY),
            )
            .with_entities(
                BaseAllocation.uuid.label("info"),
                CallToFree.uuid.label("start_uuid"),
                CallEdge.attributes["caller_context"].astext.label("start_context"),
                StoreEdge.source.label("stop_uuid"),
                StoreEdge.attributes["context"].astext.label("stop_context"),
            ),
            session.query(cpg.DataflowSignature)
            .filter(cpg.DataflowSignature.is_allocator)
            .join(FreeFunction, FreeFunction.name == cpg.DataflowSignature.deallocator)
            .join(
                CallEdge,
                (CallEdge.target == FreeFunction.uuid)
                & (CallEdge.kind == EdgeKind.CALL_TO_FUNCTION),
            )
            .join(CallToFree, CallToFree.uuid == CallEdge.source)
            .join(FreedPointer, cpg.CallSite.argument0)
            .join(
                FreedMemoryEdge,
                (FreedMemoryEdge.source == FreedPointer.uuid)
                & (FreedMemoryEdge.kind == EdgeKind.POINTS_TO)
                & (FreedMemoryEdge.target.notin_(null_uuids))
                & (
                    FreedMemoryEdge.attributes["context"].astext
                    == CallEdge.attributes["caller_context"].astext
                ),
            )
            .join(
                BaseAllocationEdge,
                (BaseAllocationEdge.source == FreedMemoryEdge.target)
                & (BaseAllocationEdge.kind == EdgeKind.MAY_ALIAS),
            )
            .join(
                BaseAllocation,
                (BaseAllocationEdge.target == BaseAllocation.uuid)
                & ~BaseAllocation.incoming.any(cpg.Edge.kind == EdgeKind.SUBREGION),
            )
            .join(
                AliasEdge,
                (AliasEdge.source == BaseAllocation.uuid) & (AliasEdge.kind == EdgeKind.MAY_ALIAS),
            )
            .join(
                DataflowEdge,
                (DataflowEdge.source == AliasEdge.target)
                & (DataflowEdge.kind == EdgeKind.DATAFLOW_SIGNATURE),
            )
            .join(
                DataflowSigEdge,
                (DataflowSigEdge.source == DataflowEdge.target)
                & (DataflowSigEdge.kind == EdgeKind.DATAFLOW_SIGNATURE_FOR_CALLSITE),
            )
            .with_entities(
                BaseAllocation.uuid.label("info"),
                CallToFree.uuid.label("start_uuid"),
                CallEdge.attributes["caller_context"].astext.label("start_context"),
                DataflowSigEdge.target.label("stop_uuid"),
                DataflowSigEdge.attributes["context"].astext.label("stop_context"),
            ),
        )
        .cte()
    )

    start_cte = (
        session.query(cpg.DataflowSignature)
        .filter(cpg.DataflowSignature.is_allocator)
        .join(FreeFunction, FreeFunction.name == cpg.DataflowSignature.deallocator)
        .join(
            CallEdge,
            (CallEdge.target == FreeFunction.uuid) & (CallEdge.kind == EdgeKind.CALL_TO_FUNCTION),
        )
        .join(CallToFree, CallToFree.uuid == CallEdge.source)
        .join(FreedPointer, CallToFree.argument0)
        .join(
            FreedMemoryEdge,
            (FreedMemoryEdge.source == FreedPointer.uuid)
            & (FreedMemoryEdge.kind == EdgeKind.POINTS_TO)
            & (FreedMemoryEdge.target.notin_(null_uuids))
            & (
                FreedMemoryEdge.attributes["context"].astext
                == CallEdge.attributes["caller_context"].astext
            ),
        )
        .join(
            BaseAllocationEdge,
            (BaseAllocationEdge.source == FreedMemoryEdge.target)
            & (BaseAllocationEdge.kind == EdgeKind.MAY_ALIAS),
        )
        .join(
            BaseAllocation,
            (BaseAllocationEdge.target == BaseAllocation.uuid)
            & ~BaseAllocation.incoming.any(cpg.Edge.kind == EdgeKind.SUBREGION),
        )
        .filter(
            tuple_(
                BaseAllocation.uuid,
                CallToFree.uuid,
                CallEdge.attributes["caller_context"].astext,
            ).in_(
                select(
                    [stop_map_cte.c.info, stop_map_cte.c.start_uuid, stop_map_cte.c.start_context]
                ).select_from(stop_map_cte)
            ),
        )
        .with_entities(
            BaseAllocation.uuid.label("info"),
            CallToFree.uuid.label("uuid"),
            CallEdge.attributes["caller_context"].astext.label("context"),
        )
        .distinct()
        .cte()
    )

    stop_map_cte2 = aliased(stop_map_cte)

    allocation_sets = (
        select(
            [
                stop_map_cte.c.info.label("info"),
                stop_map_cte.c.start_uuid.label("start_uuid"),
                stop_map_cte.c.start_context.label("start_context"),
                stop_map_cte2.c.info.label("allocation"),
            ]
        )
        .select_from(
            join(
                stop_map_cte,
                stop_map_cte2,
                (stop_map_cte.c.stop_uuid == stop_map_cte2.c.stop_uuid)
                & (stop_map_cte.c.stop_context == stop_map_cte2.c.stop_context),
            )
        )
        .cte()
    )

    avoid_map_cte = (
        select(
            [
                allocation_sets.c.info.label("info"),
                allocation_sets.c.start_uuid.label("start_uuid"),
                allocation_sets.c.start_context.label("start_context"),
                AllocatesEdge.source.label("avoid_uuid"),
                AllocatesEdge.attributes["context"].astext.label("avoid_context"),
            ]
        )
        .select_from(
            join(
                allocation_sets,
                AllocatesEdge,
                (AllocatesEdge.target == allocation_sets.c.allocation)
                & (AllocatesEdge.kind == EdgeKind.ALLOCATES),
            )
        )
        .distinct()
        .cte()
    )

    free_contexts = defaultdict(list)
    use_contexts = defaultdict(list)
    for (_, free, free_ctx, use, use_ctx) in control_flow_avoiding(
        cpg, start_cte, avoid_map_cte, stop_map_cte, stack_bound=5, limit=100
    ):
        free_contexts[(free, use)].append(free_ctx)
        use_contexts[(free, use)].append(use_ctx)

    return [
        (free, use, free_contexts[(free, use)], use_contexts[(free, use)])
        for (free, use) in free_contexts.keys()
    ]
