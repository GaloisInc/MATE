from __future__ import annotations

import itertools
import logging
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Tuple

from sqlalchemy.dialects.postgresql import ARRAY, array, array_agg
from sqlalchemy.orm import aliased
from sqlalchemy.types import String

from mate.poi.poi_types import Analysis, POIGraphsPair
from mate_common.models.analyses import POI
from mate_common.models.cpg_types import CONSTANT_NODES, Opcode
from mate_common.models.graphs import GraphKind, NodeRequest, SliceRequest
from mate_query import cfl, db
from mate_query.db import Session

if TYPE_CHECKING:
    from mate_query.cpg.models.core.node import Node
    from mate_query.cpg.models.node.analysis import InputSignature
    from mate_query.cpg.models.node.ast.llvm import Instruction
    from mate_query.db import Graph as CPG


logger = logging.getLogger(__name__)


class OverflowableAllocationsPOI(POI):
    pass


class OverflowableAllocations(Analysis):
    _background: str = dedent(
        """
        C programs can dynamically allocate memory using the `malloc` function.

        A common vulnerability occurs when a user controlled value is supplied as the size argument to
        `malloc` as part of an arithmetic expression. Consider the following example:
        ```
        int *dest = malloc(size + 1);
        memcpy(dest, src, size);
        ```
        If `size` can be controlled to `0xFFFFFFFF`, the argument to `malloc` will evaluate to 0 and an
        attacker will be able to write `0xFFFFFFFF` bytes of data from `src` into the heap at whatever address `malloc` returns.

        MATE finds execution paths in the program that take user input (such as a call to `scanf()`), use it
        as part of an arithmetic operation that is susceptible to integer over/under flow and use the result
        to control the size of a dynamic memory allocation. The initial graph loaded for this point of
        interest shows:

        * The call that supplies user input
        * The arithmetic operation applied to the user input
        * The argument to `malloc` that is controlled by user input
        """
    )

    def run(self, session: Session, graph: CPG, _inputs: Dict[str, Any]) -> Iterable[POIGraphsPair]:
        logger.debug("Running overflowable allocations analysis...")

        for input_callsite, malloc_arg, flows in compute_overflowable_allocations(session, graph):
            malloc_loc = malloc_arg.location_string
            input_callsite_loc = input_callsite.location_string

            input_names = " or ".join(
                {
                    session.query(graph.InputSignature)
                    .get(user_input)
                    .signature_for_function.demangled_name
                    for (user_input, _) in flows
                }
            )

            poi = OverflowableAllocationsPOI(
                source=input_callsite_loc,
                sink=malloc_loc,
                insight=f"The argument to `malloc` computed at `{malloc_loc}` may be subject to integer overflow"
                f" and may be controllable by a user in a call to `{input_names}` at `{input_callsite_loc}`",
                salient_functions=list(
                    {
                        input_callsite.parent_block.parent_function.as_salient(),
                        malloc_arg.parent_block.parent_function.as_salient(),
                        input_callsite.parent_block.parent_function.as_salient(),
                    }
                ),
            )

            flow_requests = list(
                itertools.chain.from_iterable(
                    [
                        SliceRequest(
                            build_id=graph.build,
                            source_id=user_input,
                            sink_id=arithmetic_op,
                            kind=GraphKind.ForwardDataflow,
                            avoid_node_ids=[],
                            focus_node_ids=[],
                        ),
                        SliceRequest(
                            build_id=graph.build,
                            source_id=arithmetic_op,
                            sink_id=malloc_arg.uuid,
                            kind=GraphKind.ForwardDataflow,
                            avoid_node_ids=[],
                            focus_node_ids=[],
                        ),
                    ]
                    for (user_input, arithmetic_op) in flows
                )
            )

            input_requests = [
                NodeRequest(
                    build_id=graph.build,
                    node_id=input_uuid,
                )
                for input_uuid in {input_uuid for (input_uuid, _) in flows}
            ]

            op_requests = [
                NodeRequest(
                    build_id=graph.build,
                    node_id=op_uuid,
                )
                for op_uuid in {op_uuid for (_, op_uuid) in flows}
            ]

            yield (
                poi,
                (
                    flow_requests
                    + input_requests
                    + op_requests
                    + [
                        NodeRequest(
                            build_id=graph.build,
                            node_id=malloc_arg.uuid,
                        ),
                    ]
                ),
            )


def compute_overflowable_allocations(
    session: Session, cpg: db.Graph
) -> Iterable[Tuple[Instruction, Instruction, List[Tuple[str, str]]]]:
    # This computation is composed of two data flows.
    #
    # Initially, we find all results of over/under flowable arithmetic operations that end up being
    # passed to `malloc`.
    #
    # We then use these results to constrain the search for paths from user input to those same
    # arithmetic operations.
    #
    # When combined, this gives us a list of user inputs that can potentially be used to over/under
    # flow a given dynamic memory allocation.

    ArithmeticOp = aliased(cpg.Instruction)

    # Our sources are all arithmetic operations
    arithmetic_uuids = [
        n[0]
        for n in (
            session.query(ArithmeticOp.uuid)
            .filter(ArithmeticOp.opcode.in_([Opcode.ADD, Opcode.SUB, Opcode.MUL]))
            .all()
        )
    ]

    CallToMalloc = aliased(cpg.CallSite)
    MallocArgument = aliased(cpg.Node)

    # Our sinks are all non-constant arguments to `malloc`
    malloc_uuids = [
        n[0]
        for n in (
            session.query(cpg.DataflowSignature)
            .filter(cpg.DataflowSignature.is_allocator)
            .join(CallToMalloc, cpg.DataflowSignature.signature_for)
            .filter(CallToMalloc.argument0.has(cpg.Node.kind.notin_(CONSTANT_NODES)))
            .join(MallocArgument, CallToMalloc.argument0)
            .with_entities(MallocArgument.uuid)
            .all()
        )
    ]

    # Find paths from arithmetic operations to `malloc`
    arithmetic_malloc_df = (
        db.PathBuilder(cfl.CSThinDataflowPath)
        .reverse()
        .starting_at(lambda Node: Node.uuid.in_(arithmetic_uuids))
        .stopping_at(lambda Node: Node.uuid.in_(malloc_uuids))
        .build(cpg)
    )

    # Our sources are all input functions that take user input.
    input_uuids = [
        n[0]
        for n in (
            session.query(cpg.InputSignature.uuid)
            .filter(cpg.InputSignature.tags.contains(["user_input"]))
            .all()
        )
    ]

    # Find paths from user input to previously calculated arithmetic operations
    input_arithmetic_df = (
        db.PathBuilder(cfl.CSThinDataflowPath)
        .starting_at(lambda Node: Node.uuid.in_(input_uuids))
        .stopping_at(lambda Node: Node.uuid.in_(arithmetic_uuids))
        .build(cpg)
    )

    IS = aliased(cpg.InputSignature)
    CS = aliased(cpg.CallSite)

    for (callsite, malloc_arg, flows) in (
        session.query(input_arithmetic_df)
        .join(arithmetic_malloc_df, input_arithmetic_df.target == arithmetic_malloc_df.source)
        .join(IS, input_arithmetic_df.source == IS.uuid)
        .join(CS, IS.signature_for)
        .join(ArithmeticOp, arithmetic_malloc_df.source == ArithmeticOp.uuid)
        .join(MallocArgument, arithmetic_malloc_df.target == MallocArgument.uuid)
        .group_by(CS, MallocArgument)
        .with_entities(
            CS,
            MallocArgument,
            array_agg(array([IS.uuid, ArithmeticOp.uuid])).cast(ARRAY(String, dimensions=2)),
        )
        .all()
    ):
        yield (callsite, malloc_arg, flows)
