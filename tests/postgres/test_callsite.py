"""Test the points-to analysis callgraph construction."""


def test_callsites(session, cpg_db_v2, optimization_flags):
    """Validate that cpg.Call, cpg.Invoke, and cpg.CallSite models retreive the expected nodes."""
    cpg = cpg_db_v2(
        "exceptions.cpp",
        compile_options=dict(extra_compiler_flags=optimization_flags),
        build_options=dict(
            do_pointer_analysis=True,
            machine_code_mapping=False,
        ),
    )

    may_throw_name = "_Z9may_throwii"
    must_throw_name = "_Z10must_throwv"

    assert session.query(cpg.CallSite).filter(cpg.CallSite.calls(may_throw_name)).count() == 2
    if optimization_flags == ("-O0",):
        assert session.query(cpg.Call).filter(cpg.Call.calls(may_throw_name)).count() == 0
        assert session.query(cpg.Invoke).filter(cpg.Invoke.calls(may_throw_name)).count() == 2
    else:
        assert session.query(cpg.Call).filter(cpg.Call.calls(may_throw_name)).count() == 2
        assert session.query(cpg.Invoke).filter(cpg.Invoke.calls(may_throw_name)).count() == 0

    assert session.query(cpg.CallSite).filter(cpg.CallSite.calls(must_throw_name)).count() == 1
    assert session.query(cpg.Call).filter(cpg.Call.calls(must_throw_name)).count() == 0
    assert session.query(cpg.Invoke).filter(cpg.Invoke.calls(must_throw_name)).count() == 1
