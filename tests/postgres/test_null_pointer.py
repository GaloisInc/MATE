def test_null_pointers(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "allocation-sizes.c", compile_options=dict(extra_compile_flags=optimization_flags)
    )
    assert session.query(cpg.Instruction).filter(cpg.Instruction.might_be_null).first() is not None
    assert session.query(cpg.Instruction).filter(~cpg.Instruction.might_be_null).first() is not None
