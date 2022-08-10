import pytest

from mate.poi.analysis.IteratorInvalidation import compute_iterator_invalidations


@pytest.mark.parametrize(
    "cflags",
    [
        ("-O0",),
        ("-O1",),
        # TODO(ac): Figure out a way to detect this POI after inlining has taken place.
        # ("-O2",),
        # ("-O3",),
    ],
)
def test_poi_iterator_invalidation(cpg_db_v2, cflags):
    cpg = cpg_db_v2("iterator-invalidation.cpp", compile_options=dict(extra_compiler_flags=cflags))

    results = {
        (
            iterator_ctor.location["line"],
            invalidation_op.location["line"],
            usage_op.location["line"],
        )
        for (iterator_ctor, invalidation_op, usage_op) in compute_iterator_invalidations(
            cpg.session, cpg
        )
    }

    expected = {(42, 45, 43), (58, 60, 59), (72, 74, 73)}
    assert results == expected
