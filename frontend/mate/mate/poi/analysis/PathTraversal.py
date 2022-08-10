from __future__ import annotations

import logging
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Tuple

from sqlalchemy.dialects.postgresql import ARRAY, array, array_agg
from sqlalchemy.orm import aliased
from sqlalchemy.types import String

from mate.poi.poi_types import Analysis, POIGraphsPair
from mate_common.models.analyses import POI
from mate_common.models.cpg_types import DATA_FLOW_FORWARD_THIN, EdgeKind
from mate_common.models.graphs import GraphKind, NodeRequest, SliceRequest
from mate_query import cfl, db
from mate_query.db import Session

if TYPE_CHECKING:
    from mate_query.cpg.models.node.analysis import InputSignature, OutputSignature
    from mate_query.cpg.models.node.llvm import Instruction


logger = logging.getLogger(__name__)


class PathTraversalPOI(POI):
    """This POI represents a potential pointer address leak to a public output.

    It consists of an LLVM pointer value and an output signature where that pointer might be leaked
    to the user.
    """

    pass


class PathTraversal(Analysis):
    _background: str = dedent(
        """
        A path traversal (also known as directory traversal) vulnerability occurs when
        user-provided input is used in way that causes a program to access a file path
        that is not intended to be accessible. Path traversal exploits often include
        input that causes unexpected relative path resolution, such as `'../'`, which
        navigates to the enclosing directory, `'//'`, which may restart path resolution
        at the root directory, or `'~'`, which may resolve to the current user's home
        directory. An example attack might include a file path like
        `'mallory/../../../../path/to/secret.txt'`, which "escapes" from the current
        directory and accesses a secret file.

        Sometimes you can insert `'../'` directly into some input that is used to
        generate a filename - try it! But often programs include some logic to identify
        and replace patterns like `'..'`. In these cases, you can sometimes provide
        encoded input that makes it past these checks, but nevertheless ends up being
        treated like `'../'` when it is used later in the program.

        For example:

        * `'%2e%2e%2f'`, `'%2e%2e/'`, and `'%2e.%2f'` may all be decoded to `'../'`
        * URL encoding `'..%c0%af'` may also be interpreted as `'../'`

        Path traversal may be useful to:

        * *read* secret files (e.g. authentication tokens)
        * *write* over important files

        The initial graph loaded for this point of interest shows:

        * a source location where attacker-controlled input may enter the target program

        * a source location where user-controlled data related the the input may be used
        a filesystem-related function

        * the dataflow slice showing how user-controlled data is processed before
        reaching the filesystem-related function

        Using MATE, you may want to explore the following questions:

        * How is user input used in the construction of the filepath used by the
        program? Can it take a relative path? Absolute path?

        * What functions perform checks and substitutions intended to prevent path
        traversal? What do they check (and what might they miss)?

        * What functions encode/decode input (e.g. URL encoding)? What might they miss:
        double-encoded values, invalid encodings, etc.?

        * Does the program check path data before or after the path has been
        canonicalized?

        * What part of the user input is/isn't checked? Whole path? Filename? Extension?
        """
    )

    def run(
        self, session: Session, graph: db.Graph, _inputs: Dict[str, Any]
    ) -> Iterable[POIGraphsPair]:
        logger.debug("Running path traversal analysis...")

        for (input_callsite, output_callsite, flows) in compute_cfl_path_traversal(session, graph):
            input_callsite_loc = input_callsite.location_string
            output_callsite_loc = output_callsite.location_string

            input_names = " or ".join(
                {user_input.signature_for_function.demangled_name for (user_input, _) in flows}
            )

            output_names = " or ".join(
                {user_output.signature_for_function.demangled_name for (_, user_output) in flows}
            )

            poi = PathTraversalPOI(
                source=input_callsite_loc,
                sink=output_callsite_loc,
                insight=(
                    f"User input from a call to `{input_names}` at `{input_callsite_loc}` is "
                    f"used in a call to `{output_names}` at `{output_callsite_loc}` that may be "
                    "vulnerable to path traversal."
                ),
                salient_functions=list(
                    {
                        input_callsite.parent_block.parent_function.as_salient(),
                        output_callsite.parent_block.parent_function.as_salient(),
                    }
                ),
            )

            yield (
                poi,
                [
                    request
                    for requests in [
                        [
                            SliceRequest(
                                build_id=graph.build,
                                source_id=user_input.uuid,
                                sink_id=user_output.uuid,
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
                                node_id=user_output.uuid,
                            ),
                        ]
                        for (user_input, user_output) in flows
                    ]
                    for request in requests
                ],
            )


def compute_path_traversal(
    session: Session, cpg: db.Graph
) -> Iterable[Tuple[InputSignature, OutputSignature]]:
    # For each potential path traversal sink:
    for user_output in (
        session.query(cpg.OutputSignature)
        .filter(cpg.OutputSignature.tags.contains(["path_traversal"]))
        .all()
    ):
        logger.debug(
            f"Checking for user input that could cause path traversal in call to {user_output.signature_for_function.demangled_name}"
        )
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
            )
            .build(cpg.dfg, keep_start=False)
        )

        for user_input in (
            session.query(cpg.InputSignature)
            .filter(cpg.InputSignature.tags.contains(["user_input"]))
            .join(reaches_output, cpg.InputSignature.uuid == reaches_output.target)
            .all()
        ):
            logger.debug(
                f"Found potential flow from user input at call to {user_input.signature_for_function.demangled_name}"
            )
            yield (user_input, user_output)


def compute_cfl_path_traversal(
    session: Session, cpg: db.Graph
) -> Iterable[Tuple[Instruction, Instruction, List[Tuple[InputSignature, OutputSignature]]]]:
    sources = (
        session.query(cpg.InputSignature)
        .filter(cpg.InputSignature.tags.contains(["user_input"]))
        .all()
    )
    sinks = (
        session.query(cpg.OutputSignature)
        .filter(cpg.OutputSignature.tags.contains(["path_traversal"]))
        .all()
    )

    source_uuids = [n.uuid for n in sources]
    sink_uuids = [n.uuid for n in sinks]

    reaches = (
        db.PathBuilder(cfl.CSThinDataflowPath)
        .starting_at(lambda Node: Node.uuid.in_(source_uuids))
        .stopping_at(lambda Node: Node.uuid.in_(sink_uuids))
        .reverse()
        .build(cpg)
    )

    InputEdge = aliased(cpg.Edge)
    OutputEdge = aliased(cpg.Edge)
    InputCallSite = aliased(cpg.CallSite)
    OutputCallSite = aliased(cpg.CallSite)

    for (input_callsite, output_callsite, flow_uuids) in (
        session.query(reaches)
        .join(
            InputEdge,
            (InputEdge.kind == EdgeKind.DATAFLOW_SIGNATURE_FOR_CALLSITE)
            & (InputEdge.source == reaches.source),
        )
        .join(
            OutputEdge,
            (OutputEdge.kind == EdgeKind.DATAFLOW_SIGNATURE_FOR_CALLSITE)
            & (OutputEdge.source == reaches.target),
        )
        .join(InputCallSite, InputEdge.target == InputCallSite.uuid)
        .join(OutputCallSite, OutputEdge.target == OutputCallSite.uuid)
        .group_by(InputCallSite, OutputCallSite)
        .with_entities(
            InputCallSite,
            OutputCallSite,
            array_agg(array([InputEdge.source, OutputEdge.source])).cast(ARRAY(String)),
        )
        .all()
    ):
        flows = [
            (
                session.query(cpg.InputSignature).get(input_uuid),
                session.query(cpg.OutputSignature).get(output_uuid),
            )
            for (input_uuid, output_uuid) in flow_uuids
        ]
        for user_input, user_output in flows:
            logger.debug(
                f"Found potential flow from user input at call to {user_input.signature_for_function.demangled_name} to {user_output.signature_for_function.demangled_name}"
            )
        yield (input_callsite, output_callsite, flows)
