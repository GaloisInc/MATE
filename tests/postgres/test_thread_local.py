def test_thread_locals(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "symbol-menagerie.c", compile_options=dict(extra_compiler_flags=optimization_flags)
    )

    quux = session.query(cpg.ASMGlobalVariable).filter_by(name="quux").one()
    quux2 = session.query(cpg.ASMGlobalVariable).filter_by(name="quux2").one()
    quux3 = session.query(cpg.ASMGlobalVariable).filter_by(name="quux3").one()

    # quux and quux2 are TLVs, but quux3 is not.
    assert quux.thread_local is True
    assert quux2.thread_local is True
    assert quux3.thread_local is False

    # Consequently, quux and quux2 have nontrivial dwarf_locations, while quux3
    # has a trivial DW_OP_addr.
    assert len(quux.dwarf_location[0]["location_expression"]) == 2
    assert len(quux2.dwarf_location[0]["location_expression"]) == 2
    assert len(quux3.dwarf_location[0]["location_expression"]) == 1
