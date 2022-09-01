from __future__ import annotations

import logging
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Dict, Iterable, List

from mate.poi.poi_types import Analysis, POIGraphsPair
from mate_common.models.analyses import POI
from mate_common.models.cpg_types import EdgeKind
from mate_query import db
from mate_query.cpg.query.known_function_whitelist import (
    formatted_output_function_names,
    sql_keywords,
)

if TYPE_CHECKING:
    from mate_query.db import Session


logger = logging.getLogger(__name__)


class CommandInjectionPOI(POI):
    """This POI represents a possible command injection site.

    It consists of a string which uses a known SQL keyword, and the uuid of a callsite to a printf-
    like function which uses that string. The uuids are relative to the graph which was provided
    when the analysis ran.
    """

    keyword_string: str
    keyword_string_id: str
    suspicious_callsite_ids: List[str]


class CommandInjection(Analysis):
    """This analysis looks for potential command injection sites.

    This analysis looks for constants which contain SQL keywords, and functions in the printf family
    which take those constant strings as arguments.
    """

    _background: str = dedent(
        """
        Programs frequently interact with other programs by building up sequences
        of commands and then sending those commands to the target. Common examples
        include SQL queries, HTTP requests, and "system" commands.

        When command sequences are built up using string functions, command injection
        can occur: a malicious user can provide inputs that the target interprets
        as instructions, rather than as data.

        For example, the following pseudocode to query a user by ID:

        ```
        query = "SELECT * FROM users WHERE id = " + user_id;
        ```

        can be manipulated by an attacker to return all rows by providing:

        ```
        user_id = "1234 OR 1=1"
        ```

        making the final query:

        ```sql
        SELECT * FROM users WHERE id = 1234 OR 1=1;
        ```

        which is always true, and therefore returns all users instead
        of the intended behavior of just one.

        MATE looks for constants that contain keywords associated with command construction,
        followed by uses of those constants in string or output formatting functions that
        are likely sources of command injection.
        """
    )

    def run(
        self, session: Session, graph: db.Graph, _inputs: Dict[str, Any]
    ) -> Iterable[POIGraphsPair]:
        return find_command_injection_sites(session, graph)


def find_command_injection_sites(session: Session, cpg: db.Graph) -> Iterable[POIGraphsPair]:
    logger.debug("Checking for potential command injection sites")

    # TODO: Why are we searching for only SQLi here? What about the other keywords
    # defined in `known_function_whitelist`?
    for keyword in sql_keywords():
        suspicious_nodes = (
            session.query(cpg.ConstantString)
            .filter(cpg.ConstantString.string_value.contains(keyword))
            .all()  # Issue 1131
        )
        for suspicious_node in suspicious_nodes:
            keyword_string_location = suspicious_node.location_string

            local_uses_of_suspicious_string = (
                db.PathBuilder()
                .starting_at(lambda Node: Node.uuid == suspicious_node.uuid)
                .continuing_while(lambda _, Edge: Edge.kind == EdgeKind.VALUE_DEFINITION_TO_USE)
                .build(cpg.dfg, keep_start=False)
            )

            local_use_output_calls = (
                session.query(local_uses_of_suspicious_string)
                .join(cpg.CallSite, cpg.CallSite.uuid == local_uses_of_suspicious_string.target)
                .filter(
                    cpg.CallSite.callees.any(
                        cpg.Function.name.in_(formatted_output_function_names())
                    )
                )
                .with_entities(cpg.CallSite)
                .all()
            )
            if len(local_use_output_calls) > 0:
                # NOTE(ww): We arbitrarily choose the first use as our
                # POI sink, to avoiding harrying the user with `N`
                # results for `N` uses of the same string.
                use_location = local_use_output_calls[0].location_string

                yield (
                    CommandInjectionPOI(
                        insight=(
                            f"Suspicious keyword `{keyword}` in string declared at "
                            f"`{keyword_string_location}` is subsequently used in "
                            f"`{use_location}`"
                        ),
                        source=keyword_string_location,
                        sink=use_location,
                        keyword_string=suspicious_node.string_value.decode(errors="replace"),
                        keyword_string_id=suspicious_node.uuid,
                        suspicious_callsite_ids=[call.uuid for call in local_use_output_calls],
                        salient_functions=list(
                            {
                                call.parent_block.parent_function.as_salient()
                                for call in local_use_output_calls
                            }
                        ),
                    ),
                    [],
                )
