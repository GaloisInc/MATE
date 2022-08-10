def test_fake_strtol(cpg_db_v2, optimization_flags):
    # Just check that there's no exception when a function is declared with the
    # same name as, but a different signature than, a standard function.
    _ = cpg_db_v2(
        "fake-strtol.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
    )


def test_pts_signature_dynamic_cast(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "dynamic-cast.cpp",
        compile_options=dict(extra_compiler_flags=optimization_flags),
    )
    call = (
        session.query(cpg.CallSite)
        .filter(cpg.CallSite.callees.any(cpg.Function.name == "__dynamic_cast"))
        .one()
    )
    # TODO(lb): Why aren't these '=='?
    assert set(call.points_to) <= set(call.argument0.points_to)
