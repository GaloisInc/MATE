import logging
from types import SimpleNamespace

import pytest

from mantiserve.logging import configure
from mantiserve.mantireach import manticore_reach, validate_reachability_msg
from mate_common.models.integration import Reachability
from mate_query import cfl, db
from mate_query.cpg.query.control_flow import cfg_path_to_waypoints


@pytest.mark.parametrize("cflags", [("-O0",)])
def test_reachability_cfg_test(session, dc_cpg_v2, cflags, tmp_path):
    (cpg, bin_name) = dc_cpg_v2("cfg-test.c", compile_options=dict(extra_compiler_flags=cflags))

    main = session.query(cpg.Function).filter(cpg.Function.name == "main").one()
    bar = session.query(cpg.Function).filter(cpg.Function.name == "bar").one()
    path = session.query(
        db.PathBuilder(PathBase=cfl.CSCFGPath)
        .starting_at(lambda Node: Node.uuid == main.entry_block.entry.uuid)
        .stopping_at(lambda Node: Node.uuid == bar.entry_block.entry.uuid)
        .limited_to(100)
        .build(cpg, keep_edge=True, keep_trace=True)
    ).first()
    assert len(path.trace) > 0
    waypoints = list(cfg_path_to_waypoints(cpg, session, path))
    assert (
        len(waypoints) > 0
    ), f"No waypoints for trace: {[session.query(cpg.Node).get(n) for n in path.trace]}"
    reach_msg = Reachability(waypoints=waypoints)

    validation_errs = validate_reachability_msg(reach_msg)
    assert len(validation_errs) == 0, f"Found validation errors: {validation_errs}"

    ctxt = SimpleNamespace(verbose=2, m_verbose=2)  # logging.DEBUG
    configure(ctxt)
    # We don't assert success because we're not solving for anything
    manticore_reach(bin_name, session, cpg, ctxt, reach_msg, manticore_workspace=str(tmp_path))


@pytest.mark.parametrize("cflags", [("-O1",)])
def test_reachability_multi_recv(session, dc_cpg_v2, cflags, tmp_path):
    (cpg, bin_name) = dc_cpg_v2("multi_recv.c", compile_options=dict(extra_compiler_flags=cflags))

    main = session.query(cpg.Function).filter(cpg.Function.name == "main").one()
    call = session.query(cpg.Call).filter(cpg.Call.calls("puts")).one()
    path = session.query(
        db.PathBuilder(PathBase=cfl.CSCFGPath)
        .starting_at(lambda Node: Node.uuid == main.entry_block.entry.uuid)
        .stopping_at(lambda Node: Node.uuid == call.uuid)
        .limited_to(100)
        .build(cpg, keep_edge=True, keep_trace=True)
    ).first()
    assert len(path.trace) > 0
    waypoints = list(cfg_path_to_waypoints(cpg, session, path))
    assert len(waypoints) > 0, f"No waypoints for trace: {path.node_trace}"
    reach_msg = Reachability(waypoints=waypoints)

    validation_errs = validate_reachability_msg(reach_msg)
    assert len(validation_errs) == 0, f"Found validation errors: {validation_errs}"

    ctxt = SimpleNamespace(verbose=2, m_verbose=2)  # logging.DEBUG
    logger = configure(ctxt)
    logger.setLevel(logging.DEBUG)
    ret_message = manticore_reach(
        bin_name, session, cpg, ctxt, reach_msg, manticore_workspace=str(tmp_path)
    )
    assert ret_message.success
