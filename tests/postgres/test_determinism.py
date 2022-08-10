def test_cpg_determinism(session, cpg_db_v2, optimization_flags):
    # Two identical CPG builds should have the same number of nodes and edges.
    # We inject a dummy flag into `cpg2` to prevent our unit test caching mechanism
    # from giving us a false positive on this test.

    cpg1 = cpg_db_v2("notes.c", compile_options=dict(extra_compiler_flags=optimization_flags))
    cpg2 = cpg_db_v2(
        "notes.c",
        compile_options=dict(extra_compiler_flags=optimization_flags + ("-Wconversion",)),
    )

    assert session.query(cpg1.Node).count() == session.query(cpg2.Node).count()
    assert session.query(cpg1.Edge).count() == session.query(cpg2.Edge).count()

    # TODO(ww): Come up with more determinism tests here. The old SQLite based CPGs
    # could be tested by file contents, but we can't do that here because the CPGs
    # now live in an independent database process.
