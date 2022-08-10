import pytest

from mate.poi.analysis.PathTraversal import compute_cfl_path_traversal


@pytest.mark.parametrize(
    "cflags",
    [
        ("-O0",),
        ("-O1",),
        ("-O2",),
        ("-O3",),
    ],
)
def test_poi_path_traversal(cpg_db_v2, cflags):
    cpg = cpg_db_v2("poi-path-traversal.c", compile_options=dict(extra_compiler_flags=cflags))

    results = {
        (inp.location["line"], out.location["line"])
        for (inp, out, _) in compute_cfl_path_traversal(cpg.session, cpg)
    }

    assert {(20, 34), (20, 26)} == results


@pytest.mark.parametrize(
    "cflags",
    [
        ("-O0",),
        ("-O1",),
        ("-O2",),
        ("-O3",),
    ],
)
def test_poi_path_traversal_recv(cpg_db_v2, cflags):
    cpg = cpg_db_v2("poi-path-traversal-recv.c", compile_options=dict(extra_compiler_flags=cflags))

    results = {
        (inp.location["line"], out.location["line"])
        for (inp, out, _) in compute_cfl_path_traversal(cpg.session, cpg)
    }

    assert {(56, 57)} == results


@pytest.mark.parametrize(
    "cflags",
    [
        ("-O0",),
        ("-O2",),
        ("-O3",),
    ],
)
def test_poi_path_traversal_notes(cpg_db_v2, cflags):
    cpg = cpg_db_v2("notes.c", compile_options=dict(extra_compiler_flags=cflags))

    results = {
        (inp.location["line"], out.location["line"])
        for (inp, out, _) in compute_cfl_path_traversal(cpg.session, cpg)
    }

    assert results == {(217, 169)}
