def test_extra_args(cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2("extra-args.c", compile_options=dict(extra_compiler_flags=optimization_flags))
    assert cpg is not None
