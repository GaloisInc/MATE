import base64
from argparse import Namespace
from os import getenv

import manticore.utils.log
import pytest

from mantiserve.logging import configure
from mantiserve.mantireach import manticore_reach, validate_reachability_msg
from mate_common.models.integration import (
    Addr,
    Assertion,
    Constraint,
    Detector,
    Reachability,
    Register,
    SMTIdentifier,
    VariableBoundsAccessOptions,
    Waypoint,
)


@pytest.mark.skipif(getenv("MATE_SANITIZERS") is not None, reason="Weird failure.")
def test_reachability(session, dc_cpg_v2, tmp_path):
    (cpg, bin_name) = dc_cpg_v2("hello.c")

    msg = Reachability(
        command_line_flags=[],
        constraint_vars=[],
        # The start and end of the first instruction in main
        waypoints=[Waypoint(start=Addr(va=0x401140), end=Addr(va=0x401144))],
    )

    validation_errs = validate_reachability_msg(msg)
    assert len(validation_errs) == 0, f"Found validation errors: {validation_errs}"

    ctxt = Namespace(verbose=2, m_verbose=2)  # logging.DEBUG
    configure(ctxt)
    manticore.utils.log.init_logging()
    ret_msg = manticore_reach(bin_name, session, cpg, ctxt, msg, manticore_workspace=str(tmp_path))
    assert ret_msg.success
    assert len(ret_msg.cases) == 1
    assert ret_msg.cases[0].detector_triggered is None


@pytest.mark.skipif(getenv("MATE_SANITIZERS") is not None, reason="Weird failure.")
def test_reachability_detector(session, dc_cpg_v2, tmp_path):
    (cpg, bin_name) = dc_cpg_v2("oob-condition.c")

    msg = Reachability(
        command_line_flags=[],
        constraint_vars=[],
        detector_options=[VariableBoundsAccessOptions(detector=Detector.VariableBoundsAccess)],
        # The start and end of the first basic block in main
        # The one path where a == 'f'
        # Has out of bounds access
        waypoints=[
            Waypoint(
                start=Addr(va=0x401140),
                end=Addr(va=0x40119D),
                asserts=[
                    Assertion(
                        location=Addr(va=0x40119D),
                        constraint=[
                            Constraint(
                                expr=f"(assert (= $replace#0 {0x4011A9:d}))",
                                id=[SMTIdentifier(identifier=Register.RIP)],
                            )
                        ],
                    )
                ],
            ),
            Waypoint(start=Addr(va=0x4011A9), end=Addr(va=0x4011BD)),
        ],
    )

    validation_errs = validate_reachability_msg(msg)
    assert len(validation_errs) == 0, f"Found validation errors: {validation_errs}"

    ctxt = Namespace(verbose=2, m_verbose=2)  # logging.DEBUG
    configure(ctxt)
    manticore.utils.log.init_logging()
    ret_msg = manticore_reach(bin_name, session, cpg, ctxt, msg, manticore_workspace=str(tmp_path))
    assert ret_msg.success
    stdin_val = next(
        base64.b64decode(sym.concrete_value_base64)
        for v in ret_msg.cases[0].symbolic_inputs
        for sym in v.symbolic_values
        if v.name == "STDIN"
    )
    # Assert we've gone down the path that requires 'f'
    assert chr(stdin_val[0]) == "f"
    # Make sure that all returned results are from the VariableBoundsAccess
    # detector because we didn't technically finish out all of the waypoint
    # following
    assert all(t.detector_triggered == Detector.VariableBoundsAccess for t in ret_msg.cases)
