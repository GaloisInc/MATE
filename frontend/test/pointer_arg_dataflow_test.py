"""Tests functions related to tracing dataflow through pointer arguments."""
import pytest
from sqlalchemy.orm import Query, aliased

from mate_common.models.cpg_types import EdgeKind
from mate_query.cpg.query.dataflow import get_pointer_arguments, memory_location_of_pointer_arg


# TODO(lb): Try marking does_not_modify_memory as noinline
# At -O1, "does_not_modify_memory" gets inlined.
@pytest.mark.skip(reason="#621")
@pytest.mark.parametrize("cflags", [("-O0",)])
def test_pointer_arg_and_user_data(cpg_db, cflags):
    (session, cpg) = cpg_db(
        "pointer_arg_dataflow_test.c",
        additional_cflags=cflags,
        do_pointer_analysis=True,
        machine_code_mapping=False,
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def test_get_pointer_arguments(cpg, function_name, expected_arg_numbers):
        actual_arg_nodes = (
            get_pointer_arguments(cpg.Argument, function_name).with_session(cpg.session).all()
        )

        assert all(str(arg.parent_function.name) == function_name for arg in actual_arg_nodes)
        assert {arg.argument_number for arg in actual_arg_nodes} == expected_arg_numbers

    test_get_pointer_arguments(cpg, "modifies_memory", {0, 2})
    test_get_pointer_arguments(cpg, "does_not_modify_memory", {0, 2})
    test_get_pointer_arguments(cpg, "sanity_check", set())

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def test_memory_location_of_pointer_arg(cpg, function_name, argument_numbers):
        # This is another way to trace to the same memory location nodes
        # using a different set of edges through the CPG
        def alternate_computation_memory_location_of_pointer_arg(function_name, argument_number):
            cpg.Node2 = aliased(cpg.Node)
            return (
                Query(cpg.Argument)
                .join(cpg.Edge, cpg.Argument.uuid == cpg.Edge.source)
                .join(cpg.Node2, cpg.Edge.target == cpg.Node2.uuid)
                .filter(
                    cpg.Argument.parent_function.has(cpg.Function.name == function_name),
                    cpg.Argument.argument_number.as_string() == argument_number,
                    cpg.Edge.kind == EdgeKind.POINTS_TO,
                )
                .with_entities(cpg.Node2)
            )

        callsite = session.query(cpg.CallSite).filter(cpg.CallSite.calls(function_name)).one()
        for arg_number in argument_numbers:
            memory_locations = (
                memory_location_of_pointer_arg(cpg.Node, cpg.Edge, callsite.uuid, arg_number)
                .with_session(cpg.session)
                .all()
            )
            alternate_computation_memory_locations = (
                alternate_computation_memory_location_of_pointer_arg(function_name, arg_number)
                .with_session(cpg.session)
                .all()
            )
            assert set(memory_locations) == set(alternate_computation_memory_locations)

    test_memory_location_of_pointer_arg(cpg, "modifies_memory", [0, 2])
    test_memory_location_of_pointer_arg(cpg, "does_not_modify_memory", [0, 2])
    test_memory_location_of_pointer_arg(cpg, "test_ptr_aliasing", [0])
    # In this one, the call to `memory_location_of_pointer_arg` returns 3 memory locations.
    # One of these is a PointsTocpg.Edge away from the array_not_a_pointer node,
    # the other two are aliases of the same location.
    test_memory_location_of_pointer_arg(cpg, "test_array_arg", [0])
