"""A regression test for MATE#1137."""


def test_issue_1137(session, cpg_db_v2):
    # Running a CPG build for this sample doesn't cause a floating-point exception.
    cpg = cpg_db_v2("issue_1137.c", build_options=dict(do_pointer_analysis=True))

    assert session.query(cpg.Node).count() > 0
    assert session.query(cpg.Edge).count() > 0
