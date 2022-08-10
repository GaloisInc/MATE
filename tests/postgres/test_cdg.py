"""Test that the control dependence analysis is working as expected."""

import pytest

from mate_common.models.cpg_types import Opcode
from mate_query import db


def all_reachable(session, cpg, name):
    function = session.query(cpg.Function).filter_by(name=name).one()
    instruction_count = sum([len(b.instructions) for b in function.blocks])
    cdg_reachable = (
        db.PathBuilder()
        .starting_at(lambda Node: Node.uuid == function.uuid)
        .build(cpg.cdg, keep_start=False)
    )
    reachable_count = (
        session.query(cdg_reachable)
        .join(cpg.Instruction, cpg.Instruction.uuid == cdg_reachable.target)
        .with_entities(cpg.Instruction)
        .count()
    )
    return reachable_count == instruction_count


@pytest.mark.skip(reason="TODO(#1711)")
@pytest.mark.parametrize("cflags", [("-O0",)])
def test_example_1_cdg(session, cpg_db_v2, cflags):
    cpg = cpg_db_v2(
        "example_1.c",
        compile_options=dict(extra_compiler_flags=cflags),
        build_options=dict(machine_code_mapping=False),
    )

    callAuthenticatedFunction = (
        session.query(cpg.CallSite).filter(cpg.CallSite.calls("authenticatedFunction")).one()
    )

    sendFlag = (
        session.query(cpg.CallSite)
        .filter(
            cpg.CallSite.calls("send"),
            cpg.CallSite.attributes["location"]["line"].as_integer() == 103,
        )
        .one()
    )

    sendHello = (
        session.query(cpg.CallSite)
        .filter(
            cpg.CallSite.calls("send"),
            cpg.CallSite.attributes["location"]["line"].as_integer() == 77,
        )
        .one()
    )

    sendFailed = (
        session.query(cpg.CallSite)
        .filter(
            cpg.CallSite.calls("send"),
            cpg.CallSite.attributes["location"]["line"].as_integer() == 113,
        )
        .one()
    )

    doAuth = (
        session.query(cpg.Instruction)
        .filter(
            cpg.Instruction.opcode == Opcode.STORE,
            cpg.Instruction.attributes["location"]["line"].as_integer() == 93,
        )
        .one()
    )

    authCheck = (
        session.query(cpg.Instruction)
        .filter(
            cpg.Instruction.opcode == Opcode.BR,
            cpg.Instruction.attributes["location"]["line"].as_integer() == 92,
        )
        .one()
    )

    accessCheck = (
        session.query(cpg.Instruction)
        .filter(
            cpg.Instruction.opcode == Opcode.BR,
            cpg.Instruction.attributes["location"]["line"].as_integer() == 96,
        )
        .one()
    )

    def get_controlled(source_uuid):
        controlled = (
            db.PathBuilder()
            .starting_at(lambda Node: Node.uuid == source_uuid)
            .continuing_while(lambda _, Edge: Edge.attributes["controls"].as_boolean() == True)
            .build(cpg.cdg, keep_start=False)
        )
        return {c.target for c in session.query(controlled)}

    # The access control check controls the send flag, send failed and authenticatedFunction calls
    accessCheckControlled = get_controlled(accessCheck.uuid)
    assert callAuthenticatedFunction.uuid in accessCheckControlled
    assert sendFlag.uuid in accessCheckControlled
    assert sendFailed.uuid in accessCheckControlled
    # But nothing else
    assert doAuth.uuid not in accessCheckControlled
    assert sendHello.uuid not in accessCheckControlled

    # The authentication check controls the 'req.authenticated = TRUE;' statement
    authCheckControlled = get_controlled(authCheck.uuid)
    assert doAuth.uuid in authCheckControlled
    # But nothing else
    assert callAuthenticatedFunction.uuid not in authCheckControlled
    assert sendFlag.uuid not in authCheckControlled
    assert sendFailed not in authCheckControlled
    assert sendHello not in authCheckControlled

    for f in session.query(cpg.Function):
        assert all_reachable(session, cpg, f.name)


@pytest.mark.parametrize("cflags", [("-O0",)])
def test_cdg_reachability(session, cpg_db_v2, cflags):
    cpg = cpg_db_v2(
        "cdg-test.c",
        compile_options=dict(extra_compiler_flags=cflags),
        build_options=dict(machine_code_mapping=False),
    )

    assert all_reachable(session, cpg, "simple")
    assert all_reachable(session, cpg, "loop")
    assert all_reachable(session, cpg, "infinite")
    assert all_reachable(session, cpg, "diamond")
    # NOTE(sm): would assert not all_reachable(session, cpg, "unreachable")
    # but clang is too smart and omits the unreachable
