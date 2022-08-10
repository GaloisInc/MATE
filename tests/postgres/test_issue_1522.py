def test_issue_1522(session, cpg_db_v2):
    cpg = cpg_db_v2("issue_1522.cpp")

    Value_ = session.query(cpg.DWARFType).filter_by(name="Value").one()

    Abstract_ = session.query(cpg.DWARFType).filter_by(name="Abstract").one()

    # correct behavior: Abstract contains a `_vptr$Abstract` member
    assert "_vptr$Abstract" in [m.name for m in Abstract_.members]

    # incorrect behavior: Value is missing a `_vptr$Value` member
    # we assert the bug here, to trip this test case in case we fix it.
    assert "_vptr$Value" not in [m.name for m in Value_.members]
