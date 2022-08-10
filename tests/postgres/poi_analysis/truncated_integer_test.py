import pytest

from mate.poi.analysis.TruncatedInteger import compute_truncated_integers


@pytest.mark.parametrize(
    "cflags",
    [
        ("-O0",),
        ("-O1",),
        ("-O2",),
        ("-O3",),
    ],
)
def test_poi_truncated_integer(cpg_db_v2, cflags):
    cpg = cpg_db_v2("truncated-integer.c", compile_options=dict(extra_compiler_flags=cflags))

    results = {
        (
            input_.signature_for.location["line"],
            malloc_arg.location["line"],
            truncate_op.location["line"],
        )
        for (input_, malloc_arg, truncate_op) in compute_truncated_integers(cpg.session, cpg)
    }

    # NOTE(ac): There seems to be some DWARF oddity on higher optimization levels, which causes the
    # POI to point at the allocation helper function rather than the `malloc` call within.
    expected = {(24, 8, 26), (44, 8, 47)} if cflags == ("-O0",) else {(24, 7, 26), (44, 7, 47)}

    assert results == expected


@pytest.mark.parametrize(
    "cflags",
    [
        ("-O0",),
        ("-O1",),
        ("-O2",),
        ("-O3",),
    ],
)
def test_poi_truncated_integer_new(cpg_db_v2, cflags):
    cpg = cpg_db_v2("truncated-integer.cpp", compile_options=dict(extra_compiler_flags=cflags))

    results = {
        (
            input_.signature_for.location["line"],
            malloc_arg.location["line"],
            truncate_op.location["line"],
        )
        for (input_, malloc_arg, truncate_op) in compute_truncated_integers(cpg.session, cpg)
    }

    # NOTE(ac): There seems to be some DWARF oddity on higher optimization levels, which causes the
    # POI to point at the allocation helper function rather than the `new` call within.
    expected = {(14, 5, 16)} if cflags == ("-O0",) else {(14, 4, 16)}

    assert results == expected
