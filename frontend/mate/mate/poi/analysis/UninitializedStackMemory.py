from __future__ import annotations

import logging
from collections import defaultdict
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import aliased
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql.expression import select, tuple_

from mate.poi.poi_types import Analysis, POIGraphsPair
from mate_common.models.analyses import POI
from mate_common.models.cpg_types import EdgeKind
from mate_common.models.graphs import GraphKind, GraphRequest, NodeRequest, SliceRequest
from mate_query import db
from mate_query.cpg.query.cfg_avoiding import control_flow_avoiding

if TYPE_CHECKING:
    from mate_query.cpg.models.node.ast.llvm import Instruction, LocalVariable
    from mate_query.db import Graph as CPG
    from mate_query.db import Session

logger = logging.getLogger(__name__)


class UninitializedStackMemPOI(POI):
    """This POI represents a potential place where a stack variable is accessed before
    initialization."""

    local_variable: str
    alloc_contexts: List[str]
    use: str
    use_contexts: List[str]


def alloca_to_localvar(cpg: db.Graph, alloca: str) -> Optional[LocalVariable]:
    """Return the LocalVariable associated with a given Alloca uuid, if found."""
    CreatesVarEdge = aliased(cpg.Edge)
    try:
        return (
            cpg.session.query(cpg.LocalVariable)
            .join(
                CreatesVarEdge,
                (CreatesVarEdge.target == cpg.LocalVariable.uuid)
                & (CreatesVarEdge.kind == EdgeKind.CREATES_VAR),
            )
            .filter(CreatesVarEdge.source == alloca)
            .one()
        )
    except NoResultFound:
        return None


class UninitializedStackMemory(Analysis):
    _background: str = dedent(
        """
        In C and C++ programs, stack variables are not initialized by default.
        If a program reads a newly-allocated stack variable before it has been written
        to, the program will generally contain "junk" data from whatever was last stored
        at the memory location. Sometimes junk data is already useful to an adversary
        (e.g. to easily pass a "check if not `0`" test), while other times an adversary
        may be able to control what data is at that location (e.g. content leftover
        from previous function invocations).

        Normally, correct programs have the sequence:

        1. **allocation:** reserve space on the stack for the variable near the start
        of the function

        1. **initialization:** write some data to the variable

        1. **use:** read data from that variable

        MATE's uninitialized stack memory analysis detects execution paths such that a
        **use** of a variable may be reached without passing through an
        **initialization** of that variable. The initial graph loaded for this point of
        interest shows:

        * the instruction that allocates the stack memory
        * the instruction that potentially uses the stack memory without initialization

        and either

        * the control flow between these two instructions, if they appear in the same
        function,

        or, if the allocation and use are not in the same function:

        * the portion of the call graph that must be traversed between the allocation
        and potential use site,
        * the control flow of the function containing the allocation, starting from the
        allocation, and
        * the control flow of the function containing the potential use, leading up to
        the use site

        Using MATE, should validate that the control flow between the allocation and
        use site can be followed during a valid execution of the program, and that
        there are no indirect ways for the variable to be initialized along the control
        flow path. An example of unrealizable control flow is where there is an
        explicit check guarding the use site that must evaluate to false if the
        variable has not been initialized yet.

        A common source of false positives in this analysis is calls to external (e.g.
        library) functions that initialize the variable. MATE can only analyze code
        included in the challenge, so relies on *signatures* to determine whether
        external library code is capable of initializing variables or not. If MATE is
        missing a signature for a library call or the signature is incomplete, MATE will
        miss the initialization and report a false positive.
        """
    )

    def run(self, session: Session, graph: CPG, _inputs: Dict[str, Any]) -> Iterable[POIGraphsPair]:
        logger.debug("Running uninitialized stack memory analysis...")

        grouped = defaultdict(list)
        for (local_variable, alloca, alloca_context, use, use_context) in {
            (alloca_to_localvar(graph, alloca.uuid), alloca, alloca_context, use, use_context)
            for (alloca, alloca_context, use, use_context) in compute_uninit_stack_mem(
                session, graph
            )
        }:
            if local_variable is None:
                continue
            grouped[(local_variable, alloca, use)].append((alloca_context, use_context))

        for ((local_variable, alloca, use), contexts) in grouped.items():
            alloca_contexts, use_contexts = zip(*contexts)
            local_variable_location = local_variable.location_string
            use_location = use.location_string
            poi = UninitializedStackMemPOI(
                source=local_variable_location,
                sink=use_location,
                local_variable=local_variable.uuid,
                alloc_contexts=list(alloca_contexts),
                use=use.uuid,
                use_contexts=list(use_contexts),
                insight=(
                    f"Stack variable `{local_variable.name}` allocated at "
                    f"`{local_variable_location}` may be used at `{use_location}` without having "
                    "been initialized."
                ),
                salient_functions=list(
                    {
                        local_variable.parent_function.as_salient(),
                        alloca.parent_block.parent_function.as_salient(),
                        use.parent_block.parent_function.as_salient(),
                    }
                ),
            )

            from_source = (
                db.PathBuilder(db.Path)
                .starting_at(lambda Node: Node.uuid == alloca.uuid)
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
                        source_id=alloca.uuid,
                        sink_id=use.uuid,
                        kind=GraphKind.ForwardControlFlow,
                        avoid_node_ids=[],
                        focus_node_ids=[],
                    ),
                    NodeRequest(
                        build_id=graph.build,
                        node_id=alloca.uuid,
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
                        source_id=alloca.parent_block.parent_function.uuid,
                        sink_id=use.parent_block.parent_function.uuid,
                        kind=GraphKind.Callees,
                        avoid_node_ids=[],
                        focus_node_ids=[],
                    ),
                    GraphRequest(
                        build_id=graph.build,
                        origin_node_ids=[alloca.uuid],
                        kind=GraphKind.ForwardControlFlow,
                    ),
                    GraphRequest(
                        build_id=graph.build,
                        origin_node_ids=[use.uuid],
                        kind=GraphKind.ReverseControlFlow,
                    ),
                    NodeRequest(
                        build_id=graph.build,
                        node_id=alloca.uuid,
                    ),
                    NodeRequest(
                        build_id=graph.build,
                        node_id=use.uuid,
                    ),
                ]

            yield (poi, graphs)


def compute_uninit_stack_mem(
    session: Session, cpg: db.Graph
) -> Iterable[Tuple[Instruction, str, Instruction, str]]:
    ## Find Points of Interest
    #
    # We find POIs by querying:
    #
    # - for inter-procedural control flow paths...
    # - that start with Alloca nodes...
    # - that reach an instruction that use that memory location...
    # - without passing through an instruction that initializes that memory location

    AllocEdge = aliased(cpg.Edge)
    AliasEdge = aliased(cpg.Edge)
    AliasEdge2 = aliased(cpg.Edge)
    LoadEdge = aliased(cpg.Edge)
    StoreEdge = aliased(cpg.Edge)
    DataflowEdge = aliased(cpg.Edge)
    DataflowSigEdge = aliased(cpg.Edge)

    stop_map_cte = (
        ## Use via Load
        #
        # The most obvious use is via Load Instruction
        #
        #     [Alloca]
        #        |
        #     Allocates
        #        |
        #        v
        #     [MemoryLocation]----\
        #              |   ^      | MayAlias itself and other MemLocs
        #              |   \------/
        #              |
        #              | LoadMemory
        #              v
        #            [Load]
        session.query(cpg.Alloca)
        .join(
            AllocEdge,
            (AllocEdge.source == cpg.Alloca.uuid) & (AllocEdge.kind == EdgeKind.ALLOCATES),
        )
        .join(
            AliasEdge,
            (AliasEdge.source == AllocEdge.target)
            & (AliasEdge.kind.in_([EdgeKind.MAY_ALIAS, EdgeKind.CONTAINS])),
        )
        .join(
            LoadEdge,
            (LoadEdge.source == AliasEdge.target) & (LoadEdge.kind == EdgeKind.LOAD_MEMORY),
        )
        .with_entities(
            AliasEdge.target.label("info"),
            cpg.Alloca.uuid.label("start_uuid"),
            AllocEdge.attributes["context"].astext.label("start_context"),
            LoadEdge.target.label("stop_uuid"),
            LoadEdge.attributes["context"].astext.label("stop_context"),
        )
        .union(
            ## Use via Dataflow
            #
            # Similarly, external code may use memory. Use our signatures to consider
            # dataflow into an external function as a use of that memory.
            #
            #                ---(uses)--\
            #               /           | DataflowSignature
            #               |           v
            #     [Alloca]  |    [DataflowSignature]
            #        |      |                   | DataflowSignatureForCallsite
            #     Allocates |                   v
            #        |      |                 [Instruction: e.g. call read()]
            #        v      |
            #     [MemoryLocation]----\
            #                  ^      | MayAlias itself and other MemLocs
            #                  \------/
            session.query(cpg.Alloca)
            .join(
                AllocEdge,
                (AllocEdge.source == cpg.Alloca.uuid) & (AllocEdge.kind == EdgeKind.ALLOCATES),
            )
            .join(
                AliasEdge,
                (AliasEdge.source == AllocEdge.target)
                & (AliasEdge.kind.in_([EdgeKind.MAY_ALIAS, EdgeKind.CONTAINS])),
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
                AliasEdge.target.label("info"),
                cpg.Alloca.uuid.label("start_uuid"),
                AllocEdge.attributes["context"].astext.label("start_context"),
                DataflowSigEdge.target.label("stop_uuid"),
                DataflowSigEdge.attributes["context"].astext.label("stop_context"),
            )
        )
        .cte()
    )

    start_cte = (
        session.query(AllocEdge)
        .join(
            AliasEdge,
            (AllocEdge.kind == EdgeKind.ALLOCATES)
            & (AliasEdge.source == AllocEdge.target)
            & (AliasEdge.kind.in_([EdgeKind.MAY_ALIAS, EdgeKind.CONTAINS]))
            & tuple_(
                AliasEdge.target,
                AllocEdge.source,
                AllocEdge.attributes["context"].astext,
            ).in_(
                select(
                    [stop_map_cte.c.info, stop_map_cte.c.start_uuid, stop_map_cte.c.start_context]
                ).select_from(stop_map_cte)
            ),
        )
        .with_entities(
            AliasEdge.target.label("info"),
            AllocEdge.source.label("uuid"),
            AllocEdge.attributes["context"].astext.label("context"),
        )
        .cte()
    )

    avoid_map_cte = (
        ## Initialization via Store
        #
        # Alloca Instructions allocate MemoryLocation nodes. The following query
        # identifies Stores to those MemoryLocations. Note that we follow MayAlias
        # edges to collect the relevant MemoryLocations.
        #
        #     [Alloca]
        #        |
        #     Allocates
        #        |
        #        v
        #     [MemoryLocation]----\
        #       ^          ^      | MayAlias itself and other MemLocs
        #       |          \------/
        #       |
        #       | StoreMemory
        #       |
        #     [Store]
        session.query(AllocEdge)
        .join(
            AliasEdge,
            (AllocEdge.kind == EdgeKind.ALLOCATES)
            & (AliasEdge.source == AllocEdge.target)
            & (AliasEdge.kind.in_([EdgeKind.MAY_ALIAS, EdgeKind.CONTAINS]))
            & tuple_(
                AliasEdge.target,
                AllocEdge.source,
                AllocEdge.attributes["context"].astext,
            ).in_(
                select([start_cte.c.info, start_cte.c.uuid, start_cte.c.context]).select_from(
                    start_cte
                )
            ),
        )
        .join(
            AliasEdge2,
            (AliasEdge2.source == AliasEdge.target)
            & (AliasEdge2.kind.in_([EdgeKind.MAY_ALIAS, EdgeKind.CONTAINS])),
        )
        .join(
            StoreEdge,
            (StoreEdge.target == AliasEdge2.target) & (StoreEdge.kind == EdgeKind.STORE_MEMORY),
        )
        .with_entities(
            AliasEdge.target.label("info"),
            AllocEdge.source.label("start_uuid"),
            AllocEdge.attributes["context"].astext.label("start_context"),
            StoreEdge.source.label("avoid_uuid"),
            StoreEdge.attributes["context"].astext.label("avoid_context"),
        )
        .union(
            ## Initialization via Dataflow from external source (assumed to initialize)
            #
            # If memory is initialized in external code, we won't see the relevant Store
            # instructions. We model data flow in external code via DataflowSignature
            # nodes and edges. DataflowSignatureForCallsite edges associate the dataflow
            # with the instruction (e.g. call to external function) responsible for the
            # dataflow.
            #
            #     [Alloca]       [{Dataflow,Input}Signature]
            #        |             /                     | DataflowSignatureForCallsite
            #     Allocates       / DataflowSignature    v
            #        |           / (initializes)       [Instruction: e.g. call read()]
            #        v          v
            #     [MemoryLocation]----\
            #                  ^      | MayAlias itself and other MemLocs
            #                  \------/
            session.query(AllocEdge)
            .join(
                AliasEdge,
                (AllocEdge.kind == EdgeKind.ALLOCATES)
                & (AliasEdge.source == AllocEdge.target)
                & (AliasEdge.kind.in_([EdgeKind.MAY_ALIAS, EdgeKind.CONTAINS]))
                & tuple_(
                    AliasEdge.target,
                    AllocEdge.source,
                    AllocEdge.attributes["context"].astext,
                ).in_(
                    select([start_cte.c.info, start_cte.c.uuid, start_cte.c.context]).select_from(
                        start_cte
                    )
                ),
            )
            .join(
                AliasEdge2,
                (AliasEdge2.source == AliasEdge.target)
                & (AliasEdge2.kind.in_([EdgeKind.MAY_ALIAS, EdgeKind.CONTAINS])),
            )
            .join(
                DataflowEdge,
                (DataflowEdge.target == AliasEdge2.target)
                & (DataflowEdge.kind == EdgeKind.DATAFLOW_SIGNATURE),
            )
            .join(
                DataflowSigEdge,
                (DataflowSigEdge.source == DataflowEdge.source)
                & (DataflowSigEdge.kind == EdgeKind.DATAFLOW_SIGNATURE_FOR_CALLSITE),
            )
            .with_entities(
                AliasEdge.target.label("info"),
                AllocEdge.source.label("start_uuid"),
                AllocEdge.attributes["context"].astext.label("start_context"),
                DataflowSigEdge.target.label("avoid_uuid"),
                DataflowSigEdge.attributes["context"].astext.label("avoid_context"),
            )
        )
        .cte()
    )

    return {
        (alloca, alloca_ctx, use, use_ctx)
        for (_, alloca, alloca_ctx, use, use_ctx) in control_flow_avoiding(
            cpg, start_cte, avoid_map_cte, stop_map_cte, stack_bound=5, limit=100
        )
    }
