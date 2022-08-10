def test_issue_1058(session, cpg_db_v2):
    cpg = cpg_db_v2("issue_1058.cpp", compile_options=dict(extra_compiler_flags=("-O2",)))

    # We're able to query for got_fd and its corresponding DWARF local variable
    got_fd = session.query(cpg.LocalVariable).filter_by(name="got_fd").one()
    assert got_fd.as_dwarf is not None
