from mate.poi.analysis.PointerDisclosure import compute_cfl_pointer_disclosure


# NOTE(bd): this test expects -O0 (so variables are not optimized out) and
# -Werror disabled (since we have intentionally-uninitialized variables), so
# the test program has also been added to '_IGNORE_WERROR_PROGRAMS' in conftest.py
def test_poi_pointer_disclosure(cpg_db_v2):
    cpg = cpg_db_v2(
        "poi-pointer-disclosure.c",
        compile_options=dict(
            compiler_flags=("-O0",),
        ),
        build_options=dict(
            do_pointer_analysis=True,
        ),
    )

    results = {
        (pointer.location["line"], output.location["line"])
        for (pointer, output, _) in compute_cfl_pointer_disclosure(cpg.session, cpg)
    }

    expected = {
        (28, 30),
        (41, 41),
        (52, 52),
        (61, 63),
    }

    assert results == expected
