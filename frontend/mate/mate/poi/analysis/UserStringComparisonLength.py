from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from textwrap import dedent
from typing import TYPE_CHECKING, Tuple

from sqlalchemy.dialects.postgresql import ARRAY, array
from sqlalchemy.orm import Query, aliased
from sqlalchemy.sql.expression import literal, tuple_
from sqlalchemy.types import String

from mate.poi.poi_types import Analysis, POIGraphsPair
from mate_common.models.analyses import POI
from mate_common.models.cpg_types import EdgeKind
from mate_common.models.graphs import GraphKind, GraphRequest, NodeRequest, SliceRequest
from mate_query import cfl, db
from mate_query.db import BOT

if TYPE_CHECKING:
    from typing import Any, Dict, Iterator

    from mate_query.cpg.models.node.analysis import InputSignature
    from mate_query.db import Session

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Source:
    len_input: InputSignature
    mem_input: InputSignature


@dataclass(frozen=True)
class Sink:
    call_uuid: str
    str_ptr_arg_uuid: str
    str_ptr_arg_op_number: int
    str_mem_loc_uuid: str
    str_len_arg_uuid: str
    str_len_arg_bind_uuid: str
    context: str


class UserStringComparisonLengthPOI(POI):
    pass


class UserStringComparisonLength(Analysis):
    _background: str = dedent(
        """
        Some string and memory comparison functions such as `strncmp` and `memcmp` take
        an argument that limits the length of the strings that get compared. For
        example, `strcmp("password", "pass") == 0` is false, but `strncmp("password",
        "pass", 4) == 0` is true. If a length-limited comparison function is used in an
        authentication check (e.g., to check a user-provided password) and an attacker
        can control both the length argument and one of the string arguments, they may
        be able to bypass the authentication check.
        """
    )

    def run(
        self, session: Session, cpg: db.Graph, _inputs: Dict[str, Any]
    ) -> Iterator[POIGraphsPair]:
        logger.debug("Running user-controlled string comparison length analysis...")

        to_output = defaultdict(list)
        for (source, sink) in compute_user_controlled_string_comparison_length(session, cpg):
            source_str = " and ".join(
                {
                    source.len_input.signature_for.location_string,
                    source.mem_input.signature_for.location_string,
                }
            )
            sink_callsite = session.query(cpg.CallSite).get(sink.call_uuid)
            sink_location = sink_callsite.location_string
            insight_str = f"Possible string comparison at `{sink_location}` with user-controlled length and string."
            to_output[(source_str, sink_location, insight_str)].append((source, sink))

        for ((source_str, sink_location, insight_str), entries) in to_output.items():
            node_requests = set()
            operand_requests = set()
            points_to_requests = set()
            slice_requests = set()
            for (source, sink) in entries:
                node_requests.update(
                    [
                        sink.call_uuid,
                        sink.str_ptr_arg_uuid,
                        sink.str_mem_loc_uuid,
                        sink.str_len_arg_uuid,
                        source.len_input.uuid,
                        source.mem_input.uuid,
                    ]
                )
                operand_requests.add(sink.call_uuid)
                points_to_requests.add(sink.str_ptr_arg_uuid)
                slice_requests.update(
                    [
                        (source.len_input.uuid, sink.str_len_arg_uuid),
                        (source.mem_input.uuid, sink.str_mem_loc_uuid),
                    ]
                )

            logger.debug(f"Reporting UserStringComparisonLengthPOI: {insight_str}")
            logger.debug(
                f"{len(node_requests)=} {len(operand_requests)=} {len(points_to_requests)=} {len(slice_requests)=}"
            )

            yield (
                UserStringComparisonLengthPOI(
                    source=source_str,
                    sink=sink_location,
                    insight=insight_str,
                    salient_functions=[sink_callsite.parent_block.parent_function.as_salient()],
                ),
                (
                    [
                        SliceRequest(
                            build_id=cpg.build,
                            source_id=source_uuid,
                            sink_id=sink_uuid,
                            kind=GraphKind.ForwardDataflow,
                            avoid_node_ids=[],
                            focus_node_ids=[],
                        )
                        for (source_uuid, sink_uuid) in slice_requests
                    ]
                    + [
                        GraphRequest(
                            build_id=cpg.build,
                            origin_node_ids=[uuid],
                            kind=GraphKind.Operands,
                        )
                        for uuid in operand_requests
                    ]
                    + [
                        GraphRequest(
                            build_id=cpg.build,
                            origin_node_ids=[uuid],
                            kind=GraphKind.ForwardPointsTo,
                        )
                        for uuid in points_to_requests
                    ]
                    + [NodeRequest(build_id=cpg.build, node_id=uuid) for uuid in node_requests]
                ),
            )


def compute_user_controlled_string_comparison_length(
    session: Session, cpg: db.Graph
) -> Iterator[Tuple[Source, Sink]]:
    # Our sources are all input functions that take user input.
    source_uuids = [
        n[0]
        for n in (
            session.query(cpg.InputSignature.uuid)
            .filter(cpg.InputSignature.tags.contains(["user_input"]))
            .all()
        )
    ]
    if len(source_uuids) == 0:
        return

    func_names = ["memcmp", "strncmp", "strncasecmp"]

    # Index of the argument that controls the length. Conveniently,
    # this is the same for each function in func_names.
    length_arg = 2

    # Our sinks are arguments of length-limited string comparison functions.
    Call = aliased(cpg.Call, name="call")
    StrLenArgBinding = aliased(cpg.ParamBinding, name="str_len_arg_binding")
    StrPtrArgBinding = aliased(cpg.ParamBinding, name="str_ptr_arg_binding")
    StrLenBindEdge = aliased(cpg.Edge, name="str_len_bind_edge")
    StrPtrBindEdge = aliased(cpg.Edge, name="str_ptr_bind_edge")
    StrLenArg = aliased(cpg.Node, name="str_len_arg")
    StrPtrArg = aliased(cpg.Node, name="str_ptr_arg")
    PointsTo = aliased(cpg.Edge, name="points_to")
    StrMemLoc = aliased(cpg.MemoryLocation, name="str_mem_loc")

    SinkCTE = (
        session.query(Call)
        .join(
            StrLenBindEdge,
            StrLenBindEdge.source == Call.uuid,
        )
        .join(StrLenArgBinding, StrLenBindEdge.target == StrLenArgBinding.uuid)
        .join(StrLenArg, StrLenArgBinding.operand)
        .join(
            StrPtrBindEdge,
            StrPtrBindEdge.source == Call.uuid,
        )
        .join(StrPtrArgBinding, StrPtrBindEdge.target == StrPtrArgBinding.uuid)
        .join(StrPtrArg, StrPtrArgBinding.operand)
        .join(PointsTo, PointsTo.source == StrPtrArg.uuid)
        .join(StrMemLoc, PointsTo.target == StrMemLoc.uuid)
        .filter(
            Call.calls(*func_names),
            StrLenArgBinding.arg_op_number == length_arg,
            StrPtrArgBinding.arg_op_number != length_arg,
            PointsTo.kind == EdgeKind.POINTS_TO,
            StrPtrBindEdge.kind == EdgeKind.CALL_TO_PARAM_BINDING,
            StrPtrBindEdge.attributes["caller_context"].astext
            == PointsTo.attributes["context"].astext,
            StrPtrBindEdge.attributes["caller_context"].astext
            == StrLenBindEdge.attributes["caller_context"].astext,
        )
        .with_entities(
            Call.uuid.label("call_uuid"),
            StrPtrArg.uuid.label("str_ptr_arg_uuid"),
            StrPtrArgBinding.arg_op_number.label("arg_op_number"),
            StrMemLoc.uuid.label("str_mem_loc_uuid"),
            StrLenArg.uuid.label("str_len_arg_uuid"),
            StrLenArgBinding.uuid.label("str_len_arg_bind_uuid"),
            PointsTo.attributes["context"].astext.label("context"),
        )
        .cte()
    )

    sinks = [
        Sink(
            call_uuid,
            str_ptr_arg_uuid,
            str_ptr_arg_op_number,
            str_mem_loc_uuid,
            str_len_arg_uuid,
            str_len_arg_bind_uuid,
            context,
        )
        for (
            call_uuid,
            str_ptr_arg_uuid,
            str_ptr_arg_op_number,
            str_mem_loc_uuid,
            str_len_arg_uuid,
            str_len_arg_bind_uuid,
            context,
        ) in (session.query(SinkCTE).all())
    ]
    if len(sinks) == 0:
        logger.debug("No sinks were found for user-controlled string comparison length analysis...")
        return

    logger.debug(
        f"{len(sinks)} potential sinks were found for user-controlled string comparison length analysis..."
    )

    # The dataflow query will retrieve (length arg binding, memory
    # location) ID pairs, we can use those to lookup the rest of the
    # information about the call.
    info = defaultdict(list)
    for sink in sinks:
        key = (sink.str_len_arg_bind_uuid, sink.str_mem_loc_uuid)
        info[key].append(sink)

    InitialConfiguration = (
        cpg.session.query(SinkCTE)
        .with_entities(
            literal("").cast(String).label("info"),
            SinkCTE.c.str_len_arg_bind_uuid.label("uuid"),
            array([SinkCTE.c.context, BOT]).cast(ARRAY(String)).label("stack"),
        )
        .union(
            cpg.session.query(SinkCTE).with_entities(
                literal("").cast(String).label("info"),
                SinkCTE.c.str_mem_loc_uuid.label("uuid"),
                array([BOT]).cast(ARRAY(String)).label("stack"),
            )
        )
        .cte()
    )

    user_input_reaches = (
        db.PathBuilder(cfl.CSThinDataflowPath)
        .starting_at(lambda Node: Node.uuid.in_(source_uuids))
        .initial_configuration(InitialConfiguration)
        .reverse()
        .build(
            cpg,
            keep_start=True,  # needed for reaches.source below
            keep_trace=False,
        )
    )

    LenISig = aliased(cpg.InputSignature, name="user_input_to_len")
    StrISig = aliased(cpg.InputSignature, name="user_input_to_str")
    DataflowPathToLenBinding = aliased(user_input_reaches, name="dataflow_path_to_len")
    DataflowPathToMem = aliased(user_input_reaches, name="dataflow_path_to_mem")

    # Look for paths from user input to *both* the length *and* memory pointed
    # to by a string-pointer argument of a length-delimited string comparison
    # function *in the same context*. Context-sensitivity is taken care of
    # by the above query that gathers the sinks, each pair in
    # sink_uuid_pairs is in the same context.
    #
    # The sources of user input need not be the same between both
    # paths/dataflows.
    sink_uuid_pairs = [(sink.str_len_arg_bind_uuid, sink.str_mem_loc_uuid) for sink in sinks]
    query = (
        Query(StrLenArgBinding, session=session)
        .join(StrMemLoc, tuple_(StrLenArgBinding.uuid, StrMemLoc.uuid).in_(sink_uuid_pairs))
        .join(
            DataflowPathToLenBinding,
            StrLenArgBinding.uuid == DataflowPathToLenBinding.target,
        )
        .join(DataflowPathToMem, StrMemLoc.uuid == DataflowPathToMem.target)
        .join(LenISig, LenISig.uuid == DataflowPathToLenBinding.source)
        .join(StrISig, StrISig.uuid == DataflowPathToMem.source)
        .filter(tuple_(StrLenArgBinding.uuid, StrMemLoc.uuid).in_(sink_uuid_pairs))
        .with_entities(StrLenArgBinding.uuid, LenISig, StrMemLoc.uuid, StrISig)
    )

    # Useful for debugging:
    # print(query.statement.compile(compile_kwargs={"literal_binds": True}))

    for (len_binding, len_user_input, mem_loc, str_user_input) in query.all():
        # TODO(sm): possibly could be more precise here by linking these results
        # directly to call and context...
        for sink in info[(len_binding, mem_loc)]:
            # logger.debug(
            #     " ".join(
            #         (
            #             "Found dataflow from user input at",
            #             len_user_input.signature_for.location_string,
            #             "to length argument and from",
            #             str_user_input.signature_for.location_string,
            #             "to string argument number",
            #             str(sink.str_ptr_arg_op_number),
            #             "of call",
            #             session.query(cpg.Node).get(sink.call_uuid).location_string,
            #         )
            #     )
            # )
            yield (Source(len_user_input, str_user_input), sink)
