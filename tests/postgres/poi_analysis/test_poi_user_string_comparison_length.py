import pytest

from mate.poi.analysis.UserStringComparisonLength import (
    compute_user_controlled_string_comparison_length,
)


@pytest.mark.parametrize(
    "cflags",
    [
        ("-O0",),
        ("-O1",),
        ("-O2",),
        ("-O3",),
    ],
)
def test_poi_user_string_comparison_length(cpg_db_v2, cflags):
    cpg = cpg_db_v2(
        "poi-user-controlled-string-comparison-length.c",
        compile_options=dict(extra_compiler_flags=cflags),
    )

    results = {
        (
            source.len_input.signature_for.location["line"],
            cpg.session.query(cpg.Node).get(sink.call_uuid).location["line"],
        )
        for (source, sink) in compute_user_controlled_string_comparison_length(cpg.session, cpg)
    }

    expected = {(9, 15), (49, 63)}
    if "-O0" in cflags:
        # TODO(lb): Not sure why this is a false negative at other optimization
        # levels. Maybe worth a look?
        expected.add((79, 95))
    assert results == expected
