def test_symbol_aliases(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2("symbol-alias.c", compile_options=dict(extra_compiler_flags=optimization_flags))

    foo = session.query(cpg.MachineFunction).filter_by(name="foo").one()
    assert set(foo.symbols) == {"foo", "bar"}
