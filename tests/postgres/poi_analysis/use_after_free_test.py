from mate.poi.analysis.UseAfterFree import compute_use_after_free


def test_poi_use_after_free_read(cpg_db_v2):
    cpg = cpg_db_v2("simple-uaf-read.c")

    results = {
        (
            free.location["line"],
            usage.location["line"],
        )
        for (free, usage, _, _) in compute_use_after_free(cpg.session, cpg)
    }

    expected = {(20, 24)}
    assert results == expected


def test_poi_use_after_free_write(cpg_db_v2):
    cpg = cpg_db_v2("simple-uaf-write.c")

    results = {
        (
            free.location["line"],
            usage.location["line"],
        )
        for (free, usage, _, _) in compute_use_after_free(cpg.session, cpg)
    }

    expected = {(23, 27)}
    assert results == expected


def test_poi_use_after_free_cpp(cpg_db_v2):
    cpg = cpg_db_v2("simple-uaf.cpp")

    results = {
        (
            free.location["line"],
            usage.location["line"],
        )
        for (free, usage, _, _) in compute_use_after_free(cpg.session, cpg)
    }

    expected = {(17, 21)}
    assert results == expected
