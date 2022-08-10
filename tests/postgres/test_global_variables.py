def test_global_variables(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "globalvars.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
    )

    assert {"bar", "baz", "x", "y", "z"} <= {
        g.name
        for g in session.query(cpg.GlobalVariable).filter(~cpg.GlobalVariable.is_declaration).all()
    }

    for g in session.query(cpg.GlobalVariable).all():
        assert g.llvm_type.is_pointer_type
