from mate.poi.analysis.CommandInjection import find_command_injection_sites


def test_poi_command_injection(session, cpg_db_v2, optimization_flags):
    """Testing compilation and basic results."""
    # Note: the `-D _GNU_SOURCE` is needed to compile `asprintf`
    cpg = cpg_db_v2(
        "sql_injection.c",
        compile_options=dict(extra_compiler_flags=optimization_flags + ("-D", "_GNU_SOURCE")),
        build_options=dict(machine_code_mapping=False),
    )
    results = list(find_command_injection_sites(session, cpg))

    select_string = b"SELECT username FROM users WHERE username = '%s';"
    select_node = session.query(cpg.ConstantString).filter_by(string_value=select_string).one()

    assert select_string.decode() in [poi[0].keyword_string for poi in results]
    assert select_node.uuid in [poi[0].keyword_string_id for poi in results]

    drop_string = b"DROP user WHERE username = '\xff%s\xff';"
    drop_node = session.query(cpg.ConstantString).filter_by(string_value=drop_string).one()

    assert drop_string.decode(errors="replace") in [poi[0].keyword_string for poi in results]
    assert drop_node.uuid in [poi[0].keyword_string_id for poi in results]
