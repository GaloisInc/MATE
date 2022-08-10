"""Test that Param Binding & cpg.Call cpg.Return nodes are correctly inserted into CPG."""
import pytest
from sqlalchemy.orm import aliased

from mate_common.models.cpg_types import EdgeKind, NodeKind


@pytest.mark.parametrize("cflags", [("-O0",)])
def test_param_binding_and_call_return(session, cpg_db_v2, cflags):
    """Some invariants:

    Each cpg.ParamBinding has 3 edges Each cpg.CallReturn node has 2 or 3 edges, depending on
    whether there is a return value Every cpg.ParamBinding & cpg.CallReturn node corresponding to
    the same call has the same call_id Multiple calls to the same function have their own
    cpg.ParamBinding & cpg.CallReturn nodes cpg.Callsites correspond to cpg.ParamBinding nodes iff
    they have arguments cpg.Returns from function calls correspond to cpg.CallReturn nodes iff they
    return a value
    """
    cpg = cpg_db_v2(
        "param-binding-and-return.cpp",
        compile_options=dict(extra_compiler_flags=cflags),
        build_options=dict(machine_code_mapping=False),
    )

    param_bindings = session.query(cpg.Node).filter_by(kind=NodeKind.PARAM_BINDING).all()
    call_returns = session.query(cpg.Node).filter_by(kind=NodeKind.CALL_RETURN).all()

    assert len(param_bindings) == 10
    assert len(call_returns) == 8

    for param_binding in param_bindings:
        incoming = {e.kind for e in param_binding.incoming}
        assert EdgeKind.CALL_TO_PARAM_BINDING in incoming
        assert EdgeKind.OPERAND_TO_PARAM_BINDING in incoming
        outgoing = {e.kind for e in param_binding.outgoing}
        assert EdgeKind.PARAM_BINDING_TO_ARG in outgoing

    for call_return in call_returns:
        incoming = {e.kind for e in call_return.incoming}
        assert EdgeKind.RETURN_INSTRUCTION_TO_CALL_RETURN in incoming
        outgoing = {e.kind for e in call_return.outgoing}
        assert EdgeKind.CALL_RETURN_TO_CALLER in outgoing

        # If a return instruction has a value, the corresponding
        # cpg.CallReturn node should have a RETURN_VALUE_TO_CALL_RETURN
        # edge from the value
        for ret in [
            e.source_node
            for e in call_return.incoming
            if e.kind == EdgeKind.RETURN_INSTRUCTION_TO_CALL_RETURN
        ]:
            for use in [e for e in ret.incoming if e.kind == EdgeKind.VALUE_DEFINITION_TO_USE]:
                assert call_return in [
                    e.target_node
                    for e in use.source_node.outgoing
                    if e.kind == EdgeKind.RETURN_VALUE_TO_CALL_RETURN
                ]

    # The cpp program we're examining has a duplicate call to a function with
    # two arguments and a return value. Therefore, we should see 4 cpg.ParamBinding nodes,
    # and 2 cpg.CallReturn nodes corresponding to those callsites. Each pair of cpg.ParamBinding
    # nodes should have the same call_id as each cpg.CallReturn node.
    multi_calls = (
        session.query(cpg.CallSite).filter(cpg.CallSite.calls("_Z19two_args_int_returniPb")).all()
    )
    param_binding_nodes = []
    call_return_nodes = []

    for call in multi_calls:
        for edge in call.outgoing:
            if edge.kind == EdgeKind.CALL_TO_PARAM_BINDING:
                param_binding_nodes.append(edge.target)
                assert EdgeKind.SAME_CALL in {e.kind for e in edge.target_node.outgoing}
        for edge in call.incoming:
            if edge.kind == EdgeKind.CALL_RETURN_TO_CALLER:
                call_return_nodes.append(edge.source)
                assert EdgeKind.SAME_CALL in {e.kind for e in edge.source_node.incoming}

    assert len(param_binding_nodes) == 4
    assert len(call_return_nodes) == 2


def test_unused_argument(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "unused_argument.c", compile_options=dict(extra_compiler_flags=optimization_flags)
    )
    cpg.CallSite2 = aliased(cpg.CallSite)
    binders = [
        n.uuid
        for n in (
            session.query(cpg.Node)
            .join(
                cpg.Edge,
                (cpg.Edge.kind == EdgeKind.CALL_TO_PARAM_BINDING)
                & (cpg.Edge.target == cpg.Node.uuid),
            )
            .join(
                cpg.CallSite2,
                (cpg.Edge.source == cpg.CallSite2.uuid)
                & (cpg.CallSite2.calls("noargs", "withargs")),
            )
            .all()
        )
    ]
    assert len(binders) == 2

    assert (
        session.query(cpg.Edge)
        .filter(cpg.Edge.kind == EdgeKind.CALL_TO_PARAM_BINDING, cpg.Edge.target.in_(binders))
        .count()
    ) == 2
    assert (
        session.query(cpg.Edge)
        .filter(cpg.Edge.kind == EdgeKind.OPERAND_TO_PARAM_BINDING, cpg.Edge.target.in_(binders))
        .count()
    ) == 2
    # the param binding node for the call to noargs has no cpg.ParamBindingToArg edge because noargs
    # has no parameters
    assert (
        session.query(cpg.Edge)
        .filter(cpg.Edge.kind == EdgeKind.PARAM_BINDING_TO_ARG, cpg.Edge.source.in_(binders))
        .count()
    ) == 1
