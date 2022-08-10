"""Dataflow helpers."""

from sqlalchemy.orm import Query, aliased

from mate_common.models.cpg_types import EdgeKind, Opcode
from mate_query.cpg.models.core import Edge, Node
from mate_query.db import Graph as CPG


def memory_location_of_pointer_arg(
    Node_: Node, Edge_: Edge, call_uuid: str, argument_no: int
) -> Node:
    """Returns the Memory Location node pointed to by the argument_number'th argument of a function.

    If a function takes pointer arguments and modifies the memory those arguments point to
    then data flows through those pointers. To allow you to trace that dataflow, you need
    to find the memory locations of those pointer arguments, and then perform a dataflow query
    from there. This function returns the memory location of the operand_no'th pointer argument.

    Args:
        Node_: the Node sql object
        Edge_: the Edge sql object
        call_uuid (string)
        argument_no (int)

    Returns:
        Node_: the memory location from which to trace dataflow
    """
    e1 = aliased(Edge_)  # ValueDefinitionToUse
    e2 = aliased(Edge_)  # LoadMemory
    return (
        Query(Node_)
        .join(e2, Node_.uuid == e2.target)  # MemoryLocation -> load
        .join(e1, e1.source == e2.source)  # load -> call
        .filter(
            (e1.kind == EdgeKind.VALUE_DEFINITION_TO_USE)
            & (e2.kind == EdgeKind.POINTS_TO)
            & e1.target_node.has(Node_.attributes["opcode"].as_string() == Opcode.CALL.value)
            & (e1.target == call_uuid)
            & (e1.attributes["operand_number"].as_integer() == argument_no)
        )
    )


def get_pointer_arguments(cpg: CPG, function_name: str) -> Query:
    """Returns a query for all Argument nodes which are pointers.

    Args:
        Argument: the sql Argument object
        function_name (string)
    Returns:
        Query which can be evaluated for Argument node(s)
    """
    return Query(cpg.Argument).filter(
        cpg.Argument.parent_function.has(cpg.Function.name == function_name),
        cpg.Argument.llvm_type.has(cpg.LLVMType.is_pointer_type),
    )
