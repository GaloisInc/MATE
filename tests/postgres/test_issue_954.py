def test_nonutf8_string_constants(session, cpg_db_v2):
    cpg = cpg_db_v2("issue_954.c")

    # We're able to successfully query for cpg.ConstantStrings that
    # have non-UTF8 bytes in them.
    cs = (
        session.query(cpg.ConstantString)
        .filter_by(string_value=b"this\xffstring\xffis\xffnot\xffutf8\xff")
        .one_or_none()
    )

    assert cs is not None
    assert cs.string_value == b"this\xffstring\xffis\xffnot\xffutf8\xff"
