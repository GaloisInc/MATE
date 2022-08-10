from __future__ import annotations

import logging
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Tuple

from sqlalchemy.dialects.postgresql import array_agg
from sqlalchemy.orm import aliased

from mate.poi.poi_types import Analysis, POIGraphsPair
from mate_common.models.analyses import POI
from mate_common.models.cpg_types import CONSTANT_NODES
from mate_common.models.graphs import GraphKind, NodeRequest, SliceRequest
from mate_query import cfl, db
from mate_query.cpg.models.node.ast.llvm import Alloca, Instruction
from mate_query.db import Session

if TYPE_CHECKING:
    from mate_query.cpg.models.node.ast.llvm import Alloca, Instruction
    from mate_query.db import Session


logger = logging.getLogger(__name__)


class VariableLengthStackObjectPOI(POI):
    """This POI represents a variable length stack object whose size is potentially controllable
    from user input.

    It consists of an input signature and an LLVM alloca value that may be controlled by the input
    signature (and hence the user).
    """

    pass


class VariableLengthStackObject(Analysis):
    _background: str = dedent(
        """
        In most programs, variable-sized objects are dynamically allocated on the heap,
        and stack objects are fixed in size. There are two exceptions to this:

        1. In C99, programmers may use Variable-Length Arrays (VLAs) to create dynamic
        stack objects
        1. In some runtimes, the [`alloca()`](https://man7.org/linux/man-pages/man3/alloca.3.html)
        library routine can dynamically allocate stack memory

        Dynamic stack objects are inherently dangerous because of the stack's limited space:
        if a user can add arbitrarily sized objects to the stack, then they can potentially
        clash the stack with other memory regions in the program (like the heap) or even
        potentially write backwards from the current stack pointer.

        MATE finds execution paths in the program that take user input (such as a call to `scanf()`)
        and use that input to control the size of a stack object. The initial graph loaded for
        this point of interest shows:

        * the call that supplies user input
        * the LLVM `alloca` instruction that is controlled by user input

        If the input and `alloca` are in the same function, then the control flow is shown.
        Otherwise, the portion of the call graph between the functions is shown, along with
        the relevant control flow within each function.
        """
    )

    def run(
        self, session: Session, graph: db.Graph, _inputs: Dict[str, Any]
    ) -> Iterator[POIGraphsPair]:
        logger.debug("Running variable length stack object analysis...")

        for input_callsite, alloca, input_sigs in compute_cfl_variable_length_stack_object(
            session, graph
        ):
            alloca_loc = alloca.location_string
            input_callsite_loc = input_callsite.location_string

            input_names = " or ".join(
                {
                    session.query(graph.InputSignature)
                    .get(user_input)
                    .signature_for_function.demangled_name
                    for user_input in input_sigs
                }
            )

            poi = VariableLengthStackObjectPOI(
                source=input_callsite_loc,
                sink=alloca_loc,
                insight=(
                    f"The size of a stack object allocated at `{alloca_loc}` might be "
                    f"controllable by the user in a call to `{input_names}` at `{input_callsite_loc}`"
                ),
                salient_functions=list(
                    {
                        input_callsite.parent_block.parent_function.as_salient(),
                        alloca.parent_block.parent_function.as_salient(),
                    }
                ),
            )

            yield (
                poi,
                [
                    SliceRequest(
                        build_id=graph.build,
                        source_id=user_input,
                        sink_id=alloca.uuid,
                        kind=GraphKind.ForwardDataflow,
                        avoid_node_ids=[],
                        focus_node_ids=[],
                    )
                    for user_input in input_sigs
                ]
                + [
                    NodeRequest(
                        build_id=graph.build,
                        node_id=user_input,
                    )
                    for user_input in input_sigs
                ]
                + [
                    NodeRequest(
                        build_id=graph.build,
                        node_id=alloca.uuid,
                    ),
                ],
            )


def compute_cfl_variable_length_stack_object(
    session: Session, cpg: db.Graph
) -> Iterator[Tuple[Instruction, Alloca, List[str]]]:
    # Our sources are all input functions that take user input.
    source_uuids = [
        n[0]
        for n in (
            session.query(cpg.InputSignature.uuid)
            .filter(cpg.InputSignature.tags.contains(["user_input"]))
            .all()
        )
    ]

    # Our sinks are all `alloca` instructions that take a non-constant value for
    # their allocation size.
    sink_uuids = [
        n[0]
        for n in (
            session.query(cpg.Alloca.uuid)
            .filter(cpg.Alloca.operand0.has(cpg.Node.kind.notin_(CONSTANT_NODES)))
            .all()
        )
    ]

    reaches = (
        db.PathBuilder(cfl.CSThinDataflowPath)
        .starting_at(lambda Node: Node.uuid.in_(source_uuids))
        .stopping_at(lambda Node: Node.uuid.in_(sink_uuids))
        .build(cpg)
    )

    IS = aliased(cpg.InputSignature)
    A = aliased(cpg.Alloca)
    CS = aliased(cpg.CallSite)
    for (input_callsite, alloca, input_sigs) in (
        session.query(reaches)
        .join(IS, IS.uuid == reaches.source)
        .join(A, A.uuid == reaches.target)
        .join(CS, IS.signature_for)
        .group_by(CS, A)
        .with_entities(CS, A, array_agg(IS.uuid))
        .all()
    ):
        yield (input_callsite, alloca, input_sigs)
