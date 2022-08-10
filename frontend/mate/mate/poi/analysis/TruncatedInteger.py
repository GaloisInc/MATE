from __future__ import annotations

import logging
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, NewType, Tuple

from sqlalchemy.orm import aliased

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

InputSignatureUUID = NewType("InputSignatureUUID", str)
MallocUUID = NewType("MallocUUID", str)
TruncatedOpUUID = NewType("TruncatedOpUUID", str)


class TruncatedIntegerPOI(POI):
    user_input: str
    malloc: str
    trunc_op: str


class TruncatedInteger(Analysis):
    _background: str = dedent(
        """
        A common vulnerability occurs when a user controllable value is supplied as the size argument to
        `malloc` and used elsewhere as a signed integer.

        If the size argument is manipulated to exceed 2GB, the conversion to a signed integer will truncate
        the value and result in an extremely negative value (-2GB). If this signed integer is used to
        control reads/writes to the allocated memory, it can result in an attacker being able to write to
        unexpected portions of the heap.

        MATE finds execution paths in the program that take user input (such as a call to `scanf()`), use it
        to control the size of a dynamic memory allocation and then later convert the size to a signed
        integer of equal or smaller width. The initial graph loaded for this point of interest shows:

        * The call that supplies user input
        * The argument to `malloc` that is controllable by user input
        * The conversion of the user input to a signed integer
        """
    )

    def run(self, session: Session, graph: CPG, _inputs: Dict[str, Any]) -> Iterator[POIGraphsPair]:
        logger.debug("Running truncated integer analysis...")

        for (user_input, malloc, trunc_op) in compute_truncated_integers(session, graph):
            input_callsite = user_input.signature_for
            input_callsite_loc = input_callsite.location_string
            malloc_loc = malloc.location_string
            trunc_op_loc = trunc_op.location_string

            poi = TruncatedIntegerPOI(
                source=input_callsite_loc,
                sink=trunc_op_loc,
                user_input=user_input.uuid,
                malloc=malloc.uuid,
                trunc_op=trunc_op.uuid,
                insight=(
                    f"A user controllable argument is supplied to `malloc` at `{malloc_loc}` and also "
                    f"truncated at `{trunc_op_loc}`. Users can control this value by a call to "
                    f"`{user_input.signature_for_function.demangled_name}` at `{input_callsite_loc}`."
                ),
                salient_functions=list(
                    {
                        input_callsite.parent_block.parent_function.as_salient(),
                        malloc.parent_block.parent_function.as_salient(),
                        trunc_op.parent_block.parent_function.as_salient(),
                    }
                ),
            )

            yield (
                poi,
                [
                    SliceRequest(
                        build_id=graph.build,
                        source_id=user_input.uuid,
                        sink_id=malloc.uuid,
                        kind=GraphKind.ForwardDataflow,
                        avoid_node_ids=[],
                        focus_node_ids=[],
                    ),
                    SliceRequest(
                        build_id=graph.build,
                        source_id=user_input.uuid,
                        sink_id=trunc_op.uuid,
                        kind=GraphKind.ForwardDataflow,
                        avoid_node_ids=[],
                        focus_node_ids=[],
                    ),
                    NodeRequest(
                        build_id=graph.build,
                        node_id=user_input.uuid,
                    ),
                    NodeRequest(
                        build_id=graph.build,
                        node_id=malloc.uuid,
                    ),
                    NodeRequest(
                        build_id=graph.build,
                        node_id=trunc_op.uuid,
                    ),
                ],
            )


def compute_truncated_integers(
    session: Session, cpg: db.Graph
) -> Iterator[Tuple[InputSignature, Node, Instruction]]:
    # Our sources are all functions that take user input
    input_uuids = [
        n[0]
        for n in (
            session.query(cpg.InputSignature.uuid)
            .filter(cpg.InputSignature.tags.contains(["user_input"]))
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

    # Find user controllable `malloc`s
    malloc_df = (
        db.PathBuilder(cfl.CSThinDataflowPath)
        .starting_at(lambda Node: Node.uuid.in_(input_uuids))
        .stopping_at(lambda Node: Node.uuid.in_(malloc_uuids))
        .build(cpg)
    )

    input_to_malloc: List[Tuple[InputSignature, Node]] = []

    for (user_input, malloc) in (
        session.query(malloc_df)
        .join(cpg.InputSignature, cpg.InputSignature.uuid == malloc_df.source)
        .join(MallocArgument, MallocArgument.uuid == malloc_df.target)
        .with_entities(cpg.InputSignature, MallocArgument)
        .all()
    ):
        input_to_malloc.append((user_input, malloc))

    # Our sources are the inputs that end up being passed into `malloc`
    filtered_input_uuids = [n[0].uuid for n in input_to_malloc]

    TruncateOp = aliased(cpg.Instruction)

    # Our sinks are truncate operations
    trunc_uuids = [
        n[0] for n in (session.query(TruncateOp.uuid).filter_by(opcode=Opcode.TRUNC).all())
    ]

    # Find paths from the filtered set of user inputs to truncate operations
    truncate_df = (
        db.PathBuilder(cfl.CSThinDataflowPath)
        .starting_at(lambda Node: Node.uuid.in_(filtered_input_uuids))
        .stopping_at(lambda Node: Node.uuid.in_(trunc_uuids))
        .build(cpg)
    )

    input_truncate_mapping: Dict[InputSignature, Instruction] = {}

    for (user_input, truncate_op) in (
        session.query(truncate_df)
        .join(cpg.InputSignature, cpg.InputSignature.uuid == truncate_df.source)
        .join(TruncateOp, TruncateOp.uuid == truncate_df.target)
        .with_entities(cpg.InputSignature, TruncateOp)
        .all()
    ):
        input_truncate_mapping[user_input] = truncate_op

    # Assemble the two data flows to get both the argument to `malloc` and the truncation operation
    # for each user input
    for (user_input, malloc) in input_to_malloc:
        if user_input in input_truncate_mapping:
            yield user_input, malloc, input_truncate_mapping[user_input]
