import pytest

from mate.poi.analysis.OverflowableAllocations import compute_overflowable_allocations


@pytest.mark.parametrize(
    "cflags",
    [
        ("-O0",),
        ("-O1",),
        ("-O2",),
        ("-O3",),
    ],
)
def test_poi_overflowable_allocations(cpg_db_v2, cflags):
    cpg = cpg_db_v2("overflowable-allocations.c", compile_options=dict(extra_compiler_flags=cflags))

    results = {
        (
            cpg.session.query(cpg.Instruction).get(arith_op).location["line"],
            input_callsite.location["line"],
            malloc_arg.location["line"],
        )
        for (input_callsite, malloc_arg, flows) in compute_overflowable_allocations(
            cpg.session, cpg
        )
        for (_, arith_op) in flows
    }

    # NOTE(ac): There seems to be some DWARF oddity on higher optimization levels, which causes the
    # POI to point at the allocation helper function rather than the `malloc` call within.
    expected = {(7, 26, 7), (39, 38, 13) if cflags == ("-O0",) else (39, 38, 12)}

    assert results == expected


@pytest.mark.xfail(reason="#1500")
@pytest.mark.parametrize(
    "cflags",
    [
        ("-O0",),
        ("-O1",),
        ("-O2",),
        ("-O3",),
    ],
)
def test_poi_forcedentry_overflowable_allocation(cpg_db_v2, cflags):
    cpg = cpg_db_v2("forcedentry.cpp", compile_options=dict(extra_compiler_flags=cflags))

    results = {
        (
            cpg.session.query(cpg.Instruction).get(arith_op).location["line"],
            input_callsite.location["line"],
            malloc_arg.location["line"],
        )
        for (input_callsite, malloc_arg, flows) in compute_overflowable_allocations(
            cpg.session, cpg
        )
        for (_, arith_op) in flows
    }

    # TODO(ac): Enhance the overflowable allocations checker to detect the FORCEDENTRY example
    assert results


@pytest.mark.parametrize(
    "cflags",
    [
        ("-O0",),
        ("-O1",),
        ("-O2",),
        ("-O3",),
    ],
)
def test_poi_overflowable_allocations_new(cpg_db_v2, cflags):
    cpg = cpg_db_v2(
        "overflowable-allocations.cpp", compile_options=dict(extra_compiler_flags=cflags)
    )

    results = {
        (
            cpg.session.query(cpg.Instruction).get(arith_op).location["line"],
            input_callsite.location["line"],
            malloc_arg.location["line"],
        )
        for (input_callsite, malloc_arg, flows) in compute_overflowable_allocations(
            cpg.session, cpg
        )
        for (_, arith_op) in flows
    }

    expected = {(14, 26, 14)}

    assert results == expected
