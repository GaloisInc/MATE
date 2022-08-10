"""Test that function arguments are properly detected."""


def assert_argument_names(session, cpg, function_name, expected_argument_names, filename=None):
    function = session.query(cpg.Function).filter_by(name=function_name).one()
    mf = function.machine_functions[0]

    for arg in function.arguments:
        loc = arg.attributes.get("location")
        assert loc is not None
        if filename is not None:
            assert filename in loc.get("file")
        assert loc.get("line") is not None
        assert loc.get("dir") is not None

        assert arg.llvm_type is not None

        # TODO(ww): Test as_dwarf here once we fix Argument -> DWARFArgument
        # relationships.
        # See: https://gitlab-ext.galois.com/mate/MATE/-/issues/1053

    for arg in mf.arguments:
        assert arg.dwarf_type is not None
        assert arg.machine_function == mf
        assert arg.machine_function.ir_function == function

    assert expected_argument_names == {str(arg.name) for arg in function.arguments}


def test_function_arguments(session, cpg_db_v2, optimization_flags):
    """Basic correctness."""
    cpg = cpg_db_v2("notes.c", compile_options=dict(extra_compiler_flags=optimization_flags))

    assert_argument_names(session, cpg, "handle", {"req"}, filename="notes.c")


def test_stack_arguments(session, cpg_db_v2, optimization_flags):
    """A test where some arguments are passed on the stack."""
    cpg = cpg_db_v2("stack-args.c", compile_options=dict(extra_compiler_flags=optimization_flags))
    assert_argument_names(session, cpg, "main", {"argc", "argv"})
    assert_argument_names(
        session, cpg, "f", {"a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n"}
    )
