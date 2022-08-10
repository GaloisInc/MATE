from mate.poi.analysis.UninitializedStackMemory import alloca_to_localvar, compute_uninit_stack_mem


# NOTE(bd): this test expects -O0 (so variables are not optimized out) and
# -Werror disabled (since we have intentionally-uninitialized variables), so
# the test program has also been added to '_IGNORE_WERROR_PROGRAMS' in conftest.py
def test_poi_uninit(cpg_db_v2):
    cpg = cpg_db_v2(
        "poi-uninit.c",
        compile_options=dict(
            compiler_flags=("-O0",),
        ),
        build_options=dict(
            do_pointer_analysis=True,
        ),
    )

    # structure: (variable name, file path, line # of uninitialized use)
    expected = {
        # true positives
        ("tp_maybe", "frontend/test/programs/poi-uninit.c", 24),
        ("tp_zs", "frontend/test/programs/poi-uninit.c", 43),
        ("tp_src", "frontend/test/programs/poi-uninit.c", 56),
        ("tp_dst", "frontend/test/programs/poi-uninit.c", 57),
        ("tp_indir_buf", "frontend/test/programs/poi-uninit.c", 185),
        ("tp_partialstruct", "frontend/test/programs/poi-uninit.c", 202),
        ("txc", "frontend/test/programs/poi-uninit.c", 310),
        # false positives
        ("fp_msg", "frontend/test/programs/poi-uninit.c", 181),
        ("txc", "frontend/test/programs/poi-uninit.c", 290),
        ("txc", "frontend/test/programs/poi-uninit.c", 291),
        ("txc", "frontend/test/programs/poi-uninit.c", 292),
        ("txc", "frontend/test/programs/poi-uninit.c", 293),
        ("txc", "frontend/test/programs/poi-uninit.c", 294),
        ("txc", "frontend/test/programs/poi-uninit.c", 295),
        ("txc", "frontend/test/programs/poi-uninit.c", 296),
        ("txc", "frontend/test/programs/poi-uninit.c", 297),
        ("txc", "frontend/test/programs/poi-uninit.c", 298),
        ("txc", "frontend/test/programs/poi-uninit.c", 299),
        ("txc", "frontend/test/programs/poi-uninit.c", 300),
        ("txc", "frontend/test/programs/poi-uninit.c", 301),
        ("txc", "frontend/test/programs/poi-uninit.c", 302),
        ("txc", "frontend/test/programs/poi-uninit.c", 303),
        ("txc", "frontend/test/programs/poi-uninit.c", 304),
        ("txc", "frontend/test/programs/poi-uninit.c", 305),
        ("txc", "frontend/test/programs/poi-uninit.c", 306),
        ("txc", "frontend/test/programs/poi-uninit.c", 307),
        ("txc", "frontend/test/programs/poi-uninit.c", 308),
        ("txc", "frontend/test/programs/poi-uninit.c", 309),
    }

    results = {
        (
            alloca_to_localvar(cpg, alloca.uuid).name,
            use.location["file"],
            use.location["line"],
        )
        for (alloca, _, use, _) in compute_uninit_stack_mem(cpg.session, cpg)
    }

    assert {(name, line) for (name, file, line) in results} == {
        (name, line) for (name, file, line) in expected
    }
