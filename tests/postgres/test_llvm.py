import pytest

from mate_common.models.cpg_types import Opcode


def test_direct_call(session, cpg_db_v2):
    cpg = cpg_db_v2("functiontable.c")
    assert not session.query(cpg.Call).filter(cpg.Call.calls("foo")).one().is_direct
    assert session.query(cpg.Call).filter(cpg.Call.calls("rand")).one().is_direct


@pytest.mark.skip(reason="TODO(#1711)")
def test_llvm_nodes(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "example_1.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
    )

    load = session.query(cpg.Load).first()
    assert load.pointer_operand.llvm_type.is_pointer_type

    store = session.query(cpg.Store).first()
    pointer_operand_type = store.pointer_operand.llvm_type
    assert pointer_operand_type.is_pointer_type
    value_operand_type = store.value_operand.llvm_type
    assert value_operand_type.definition == pointer_operand_type.get("pointer")

    add = session.query(cpg.Instruction).filter_by(opcode=Opcode.ADD).first()
    assert add.operand0 is not None
    assert add.operand1 is not None

    call_to_listen = session.query(cpg.Call).filter(cpg.Call.calls("listen")).one()
    assert not call_to_listen.argument0.llvm_type.is_function_type
    # The second argument is of kind 'cpg.Constant', which has no specialized model as of yet.
    #
    # assert not call_to_listen.argument1.llvm_type.is_function_type
    assert call_to_listen.argument2 is None
    assert call_to_listen.callee_operand.llvm_type.is_function_type

    globs = [glob for glob in session.query(cpg.GlobalVariable).all() if "str" not in glob.name]
    assert len(globs) == 5
    assert all(glob.has_initializer for glob in globs)
    assert {"server_fd", "address", "new_client", "pswd", "FLAG"} == {g.name for g in globs}

    constant_int = session.query(cpg.ConstantInt).first()
    assert constant_int.constant_int_value is not None

    function_decls = {
        f.name for f in session.query(cpg.Function).filter(cpg.Function.is_declaration).all()
    }
    assert {"fclose", "fopen", "fputs", "strcpy", "strlen", "strncmp"} <= function_decls
    assert "setupServer" not in function_decls

    assert (
        session.query(cpg.Function)
        .filter_by(name="main")
        .one()
        .attributes["location"]["file"]
        .endswith("example_1.c")
    )
    loc = session.query(cpg.GlobalVariable).filter_by(name="FLAG").one().attributes["location"]
    assert loc["file"].endswith("example_1.c")
    assert loc["line"] == 26
