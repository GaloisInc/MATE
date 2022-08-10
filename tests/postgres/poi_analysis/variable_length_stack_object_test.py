from mate.poi.analysis.VariableLengthStackObject import compute_cfl_variable_length_stack_object


def test_poi_variable_length_stack_object(cpg_db_v2):
    cpg = cpg_db_v2("dangerous-vla.c")

    results = {
        (input_callsite.location["line"], alloca.location["line"])
        for (input_callsite, alloca, _) in compute_cfl_variable_length_stack_object(
            cpg.session, cpg
        )
    }

    expected = {(21, 12)}

    assert results == expected
