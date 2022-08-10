from __future__ import annotations

import logging
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Dict, Iterable, Iterator, List, Tuple

from sqlalchemy.dialects.postgresql import array_agg
from sqlalchemy.orm import aliased

from mate.poi.poi_types import Analysis, POIGraphsPair
from mate_common.models.analyses import POI
from mate_common.models.cpg_types import DATA_FLOW_FORWARD_THIN, EdgeKind
from mate_common.models.graphs import GraphKind, NodeRequest, SliceRequest
from mate_query import cfl, db

if TYPE_CHECKING:
    from mate_query.cpg.models.node.analysis import OutputSignature
    from mate_query.cpg.models.node.ast.llvm import Instruction
    from mate_query.db import Session


logger = logging.getLogger(__name__)


class PointerDisclosurePOI(POI):
    """This POI represents a potential pointer address leak to a public output.

    It consists of an LLVM pointer value and an output signature where that pointer might be leaked
    to the user.
    """

    pass


class PointerDisclosure(Analysis):
    _background: str = dedent(
        """
        Security mechanisms like Address Space Layout Randomization (ASLR) aim to make
        it more difficult for attackers to predict where key code and data can be found
        in memory. Vulnerabilities that reveal information about the live layout of a
        program in memory can enable attacks that bypass these security mechanisms.

        Pointer disclosure vulnerabilities generally involve programming errors that
        result in program output that includes the memory address of a value rather than
        the value itself. For example, `printf` and related string functions take a
        [format string](https://en.wikipedia.org/wiki/Printf_format_string) and a set of
        parameters as input. The format string tells the string function how to
        interpret the parameters in order to render them appropriately (e.g. as an
        integer, as a string, etc.). This can cause a pointer disclosure vulnerability
        if a pointer is provided as a parameter when the format string was expecting an
        integer (e.g., calling `printf("%d", pointer_to_int)` instead of
        `printf("%d", *pointer_to_int)`).

        The initial graph loaded for this point of interest shows:

        * a source location where a pointer is computed

        * a source location where that pointer may be output to the user

        * the dataflow slice showing how the pointer is propogated from its definition
        to the output

        A common source of false positives in this analysis results from MATE being
        unable to distinguish between code that prints (or writes to the network) an
        entire struct or printing the first field of a struct. This causes may cause
        false positives when the struct contains pointers after the first element, such
        as `struct { char msg[8]; void *ptr; }`. To rule out these kinds of false
        positives, you can check the type of object being written to the user using the
        MATE Notebook interface or by viewing the source code directly.
        """
    )

    def run(
        self, session: Session, graph: db.Graph, _inputs: Dict[str, Any]
    ) -> Iterator[POIGraphsPair]:
        logger.debug("Running pointer disclosure analysis...")

        for (pointer, output_callsite, user_outputs) in compute_cfl_pointer_disclosure(
            session, graph
        ):
            pointer_loc = pointer.location_string
            output_callsite_loc = output_callsite.location_string

            output_name = " or ".join(
                {user_output.signature_for_function.demangled_name for user_output in user_outputs}
            )

            poi = PointerDisclosurePOI(
                source=pointer_loc,
                sink=output_callsite_loc,
                insight=(
                    f"A pointer computed at `{pointer_loc}` is potentially output to the user "
                    f"in a call to `{output_name}` at `{output_callsite_loc}`."
                ),
                salient_functions=list(
                    {
                        pointer.parent_block.parent_function.as_salient(),
                        output_callsite.parent_block.parent_function.as_salient(),
                    }
                ),
            )

            yield (
                poi,
                [
                    SliceRequest(
                        build_id=graph.build,
                        source_id=pointer.uuid,
                        sink_id=user_output.uuid,
                        kind=GraphKind.ForwardDataflow,
                        avoid_node_ids=[],
                        focus_node_ids=[],
                    )
                    for user_output in user_outputs
                ]
                + [
                    NodeRequest(
                        build_id=graph.build,
                        node_id=pointer.uuid,
                    ),
                ]
                + [
                    NodeRequest(
                        build_id=graph.build,
                        node_id=user_output.uuid,
                    )
                    for user_output in user_outputs
                ],
            )


def compute_pointer_disclosure(
    session: Session, cpg: db.Graph
) -> Iterable[Tuple[Instruction, OutputSignature]]:
    # Useful aliases
    I = aliased(cpg.Instruction)
    T = aliased(cpg.LLVMType)

    # Create a subquery with the UUIDs of pointer-typed values
    pointer_uuid_subquery = (
        session.query(I)
        .join(T, I.llvm_type)
        .filter(T.is_pointer_type)
        .with_entities(I.uuid)
        .subquery()
    )

    # For each potential user_output:
    for user_output in (
        session.query(cpg.OutputSignature)
        .filter(cpg.OutputSignature.tags.contains(["user_output"]))
        .all()
    ):
        # Do a reverse dataflow "thin slice" (direct dataflow only) to
        # see what reaches the output
        reaches_output = (
            db.PathBuilder()
            .reverse()
            .stopping_at(lambda Node: Node.uuid == user_output.uuid)
            .continuing_while(
                lambda _, Edge: (
                    (Edge.kind == EdgeKind.VALUE_DEFINITION_TO_USE)
                    # VALUE_DEFINITION_TO_USE edges to load instructions are
                    # pointer operands, so would be indirect dataflow...
                    # VALUE_DEFINITION_TO_USE edges for call instructions are
                    # either function pointers (indirect) or arguments, which
                    # are more accurately handled by inter-procedural edges
                    & (
                        Edge.target_node.has(
                            Edge.cpg.Instruction.opcode.notin_(["load", "call", "invoke"])
                        )
                    )
                    # VALUE_DEFINITION_TO_USE edges to store instructions include
                    # both pointer operands and the value being stored... skip
                    # the pointer operand
                    & (
                        (Edge.target_node.has(Edge.cpg.Instruction.opcode != "store"))
                        | (Edge.attributes["operand_number"].as_integer() != 1)
                    )
                )
                # Subset to "thin slice" edges
                | Edge.kind.in_(DATA_FLOW_FORWARD_THIN)
                # Don't continue past the first pointer value you find
                # to reduce how many results about the same thing we produce
                & (Edge.target.notin_(pointer_uuid_subquery))
            )
            .build(cpg.dfg, keep_start=False)
        )

        # Report results...
        PointerInstruction = aliased(cpg.Instruction)
        PointerType = aliased(cpg.LLVMType)
        for pointer in (
            session.query(reaches_output)
            .join(PointerInstruction, reaches_output.target == PointerInstruction.uuid)
            .join(PointerType, PointerInstruction.llvm_type)
            .filter(PointerType.is_pointer_type)
            .with_entities(PointerInstruction)
            .all()
        ):
            logger.debug(
                f"Found potential flow from pointer value to {user_output.signature_for_function.demangled_name}"
            )
            yield (pointer, user_output)


def compute_cfl_pointer_disclosure(
    session: Session, cpg: db.Graph
) -> Iterable[Tuple[Instruction, Instruction, List[OutputSignature]]]:
    # Useful aliases
    I = aliased(cpg.Instruction)
    T = aliased(cpg.LLVMType)

    sinks = (
        session.query(cpg.OutputSignature)
        .filter(cpg.OutputSignature.tags.contains(["user_output"]))
        .all()
    )

    sink_uuids = [n.uuid for n in sinks]

    # Create a subquery with the UUIDs of pointer-typed values
    pointer_uuid_subquery = (
        session.query(I)
        .join(T, I.llvm_type)
        .filter(T.is_pointer_type)
        .with_entities(I.uuid)
        .subquery()
    )

    reaches = (
        db.PathBuilder(cfl.CSThinDataflowPath)
        .starting_at(lambda Node: Node.uuid.in_(pointer_uuid_subquery))
        .stopping_at(lambda Node: Node.uuid.in_(sink_uuids))
        .continuing_while(lambda _, Edge: Edge.target.notin_(pointer_uuid_subquery))
        .reverse()
        .build(cpg)
    )

    # Report results...
    PointerInstruction = aliased(cpg.Instruction)
    CallSite = aliased(cpg.CallSite)
    for (pointer, output_callsite, user_output_uuids) in (
        session.query(reaches)
        .join(PointerInstruction, reaches.source == PointerInstruction.uuid)
        .join(
            cpg.Edge,
            (cpg.Edge.kind == EdgeKind.DATAFLOW_SIGNATURE_FOR_CALLSITE)
            & (cpg.Edge.source == reaches.target),
        )
        .join(CallSite, cpg.Edge.target == CallSite.uuid)
        .group_by(PointerInstruction, CallSite)
        .with_entities(PointerInstruction, CallSite, array_agg(reaches.target))
        .all()
    ):
        user_outputs = [
            session.query(cpg.OutputSignature).get(user_output_uuid)
            for user_output_uuid in user_output_uuids
        ]

        for user_output in user_outputs:
            logger.debug(
                f"Found potential flow from pointer value to {user_output.signature_for_function.demangled_name}"
            )

        yield (pointer, output_callsite, user_outputs)
