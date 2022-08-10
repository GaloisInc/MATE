def test_exception_cf(session, cpg_db_v2):
    cpg = cpg_db_v2(
        "exception-driven-control-flow.cpp",
        compile_options=dict(extra_compiler_flags=("-std=c++17",)),
    )

    assert cpg is not None
    assert session.query(cpg.Node).count() > 0

    # TODO - once exception introspection is added to the CPG, check that we identified the
    # exception-driven control flow correctly.
