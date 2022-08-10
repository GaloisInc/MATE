"""Test that local variables are properly detected."""
import pytest

from mate_common.models.cpg_types import EdgeKind


# TODO(lb): At -O1, some extra local variables are added to setupServer, namely
# "__v" and "__x". What on earth...?
@pytest.mark.skip(reason="TODO(#1711)")
@pytest.mark.parametrize("cflags", [("-O0",)])
def test_local_variables(session, cpg_db_v2, cflags):
    cpg = cpg_db_v2("example_1.c", compile_options=dict(extra_compiler_flags=cflags))

    def assert_variable_names(function_name, expected_variable_names):
        function = session.query(cpg.Function).filter_by(name=function_name).one()
        variables = function.local_variables
        assert len(variables) > 0
        for var in variables:
            loc = var.attributes.get("location")
            assert loc is not None
            assert "example_1.c" in loc.get("file")
            assert loc.get("line") is not None
            assert loc.get("dir") is not None

            if "-O0" in cflags:
                assert var.llvm_type is not None
                session.query(cpg.Edge).filter(
                    cpg.Edge.kind == EdgeKind.CREATES_VAR, cpg.Edge.target == var.uuid
                ).one()

        actual_variable_names = {str(var.name) for var in variables}

        assert expected_variable_names == actual_variable_names

    assert_variable_names("setupServer", {"opt"})
    assert_variable_names("authenticatedFunction", {"file_p"})
    assert_variable_names("runServer", {"addrlen", "req"})

    # Check that we're generating accessors for all the various fields
    # specified in the JSON schema
    var = session.query(cpg.LocalVariable).first()
    assert var.location is not None
    assert var.name is not None
    # ...and that the docs are being set
    assert len(var.name.__doc__) > 0

    dwarf_var = var.as_dwarf
    assert dwarf_var.artificial is not None
    assert dwarf_var.dwarf_location is not None
    assert dwarf_var.dwarf_scope is not None
    assert dwarf_var.source_location is not None
    assert dwarf_var.source_scope is not None
    assert dwarf_var.type_id is not None
    assert len(dwarf_var.name.__doc__) > 0


@pytest.mark.skip(reason="TODO(#1711)")
@pytest.mark.parametrize("cflags", [("-O0",)])
def test_machine_local_variables(session, cpg_db_v2, cflags):
    cpg = cpg_db_v2("example_1.c", compile_options=dict(extra_compiler_flags=cflags))

    function = session.query(cpg.MachineFunction).filter_by(name="setupServer").one()
    assert len(function.local_variables) == 1
    assert function.local_variables[0].name == "opt"
