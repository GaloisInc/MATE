from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.orm import Session

from mate_common.models.cpg_types import EdgeKind
from mate_query import db

if TYPE_CHECKING:
    from mate_query.cpg.models.core.node import Node
    from mate_query.cpg.models.node.ast.llvm import ConstantString
    from mate_query.db import Graph as CPG


def constant_substrings(cpg: CPG, session: Session, target: str) -> ConstantString:
    """Returns a list of Nodes which are constant strings, whose string value contains the target
    substring.

    This is useful for looking for target keywords like SELECT.
    """
    return (
        session.query(cpg.ConstantString)
        .filter(cpg.ConstantString.string_value.contains(target))
        .first()
    )


def printf_which_use_format_string(cpg: CPG, session: Session, str_to_print_node: Node):
    """Find the call to ``printf`` with the given format string."""
    funs = ["printf", "puts", "__printf_chk"]
    neighborhood = (
        db.PathBuilder()
        .starting_at(lambda Node: Node.uuid == str_to_print_node.uuid)
        .build(cpg.dfg, keep_start=False)
    )
    return (
        session.query(neighborhood)
        .join(cpg.CallSite, cpg.CallSite.uuid == neighborhood.target)
        .filter(cpg.CallSite.calls(*funs))
        .with_entities(cpg.CallSite)
        .first()
    )


@pytest.mark.parametrize("cflags", [("-O1",), ("-O2",), ("-O3",)])
def test_guessing_game(session, cpg_db_v2, cflags):
    cpg = cpg_db_v2(
        "guessing-game.c",
        compile_options=dict(extra_compiler_flags=cflags),
    )

    # We'll grab the nodes that are constant strings
    # with the keywords "win" & "lose".
    secret_str_node = constant_substrings(cpg, session, "win")
    public_str_node = constant_substrings(cpg, session, "lose")

    secret_printf_node = printf_which_use_format_string(cpg, session, secret_str_node)
    public_printf_node = printf_which_use_format_string(cpg, session, public_str_node)

    # there should be exactly one call to rand
    rand_node = session.query(cpg.CallSite).filter(cpg.CallSite.calls("rand")).one()

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # First let's check the control flow

    cfg_neighborhood = (
        db.PathBuilder()
        .starting_at(lambda Node: Node.uuid == rand_node.uuid)
        .build(cpg.cfg, keep_start=False)
    )
    control_reachable_uuids = {n.target for n in session.query(cfg_neighborhood.target).all()}

    # double-check that we can in fact reach both prints after the rand call
    assert public_printf_node.uuid in control_reachable_uuids
    assert secret_printf_node.uuid in control_reachable_uuids

    # sanity check: Constants aren't control-flow reachable
    assert secret_str_node.uuid not in control_reachable_uuids
    assert public_str_node.uuid not in control_reachable_uuids

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # That all seems good, now let's look at data flow:

    # A complication: we'd like to be able to ask for the dataflow from rand,
    # but since we currently don't know anything about the implementations of
    # printf & scanf (& any other externally defined functions) we conservatively
    # assume that there might be dataflow between them wherever they're defined.
    # So, instead, we're running a modified dataflow query, where we only look for
    # VALUE_DEFINITION_TO_USE edges. This gets us the answer we want when we compile
    # with O2.
    use_view = cpg.subgraph(db.SubgraphBuilder().with_edge_kinds(EdgeKind.VALUE_DEFINITION_TO_USE))
    dfg_neighborhood = (
        db.PathBuilder()
        .starting_at(lambda Node: Node.uuid == rand_node.uuid)
        .build(use_view, keep_start=False)
    )
    data_reachable_uuids = {n.target for n in session.query(dfg_neighborhood).all()}

    # The data from the rand() call goes to the secret printf
    assert secret_printf_node.uuid in data_reachable_uuids
    # but not to the public printf
    assert public_printf_node.uuid not in data_reachable_uuids

    # That's really good, that corroborates that the dataflow is secure.

    # sanity check: Constants aren't data-flow reachable from rand()
    assert secret_str_node.uuid not in data_reachable_uuids
    assert public_str_node.uuid not in data_reachable_uuids
