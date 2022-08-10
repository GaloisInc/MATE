def test_mmap(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "mmap.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
        build_options=dict(machine_code_mapping=False, llvm_pretty_strings=False),
    )
    assert (
        list(
            session.query(cpg.CallSite)
            .filter(cpg.CallSite.callees.any(cpg.Function.name == "mmap"))
            .one()
            .points_to
        )
        != []
    )
