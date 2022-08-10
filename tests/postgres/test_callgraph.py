"""Test the points-to analysis callgraph construction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from itertools import chain
from typing import TYPE_CHECKING, NamedTuple, Set

import pytest

from mate_common.models.cpg_types import CALL_NODES, EdgeKind

if TYPE_CHECKING:
    from mate_query.cpg.models.node.ast.llvm import Function


class CallgraphEdge(NamedTuple):
    actx: str
    caller: str
    ctx: str
    callee: str


class Callgraph(ABC):
    @abstractmethod
    def list_functions(self) -> Set[str]:
        pass


class DatalogCallgraph(Callgraph):
    def __init__(self, callgraph_edge):
        self._edges: Set[CallgraphEdge] = {
            CallgraphEdge(
                actx=actx, caller=caller.split(":")[1], ctx=ctx, callee=callee.split(":")[1]
            )
            for (actx, callee, ctx, caller) in callgraph_edge
        }

    def list_functions(self) -> Set[str]:
        return set(chain.from_iterable((edge.caller, edge.callee) for edge in self._edges))

    def callers(self, function: str) -> Set[str]:
        return set(e.caller for e in self._edges if e.callee == function)

    def callees(self, function: str) -> Set[str]:
        return set(e.callee for e in self._edges if e.caller == function)


class CPGCallgraph(Callgraph):
    def __init__(self, cpg, session):
        self._cpg = cpg
        self._session = session

    def list_functions(self) -> Set[str]:
        return {f.name for f in self._session.query(self._cpg.Function).all()}

    def callsite_callers(self, function: Function) -> Set[str]:
        return {call.parent_block.parent_function.name for call in function.callsites}

    def callers(self, function: Function) -> Set[str]:
        return {caller.name for caller in function.callers}

    def callgraph_callers(self, function: Function) -> Set[str]:
        return {
            tup[0]
            for tup in self._session.query(self._cpg.Function.name)
            .join(self._cpg.Edge, self._cpg.Edge.source == self._cpg.Function.uuid)
            .filter(
                self._cpg.Edge.kind == EdgeKind.CALLGRAPH,
                self._cpg.Edge.target == function.uuid,
                self._cpg.Function.uuid != function.uuid,
            )
            .all()
        }

    def callsite_callees(self, function: Function) -> Set[str]:
        return set(
            callee.name
            for block in function.blocks
            for instr in block.instructions
            if instr.kind in CALL_NODES
            for callee in instr.callees
        )

    def callees(self, function: Function) -> Set[str]:
        return {callee.name for callee in function.callees}

    def callgraph_callees(self, function: Function) -> Set[str]:
        return {
            tup[0]
            for tup in self._session.query(self._cpg.Function.name)
            .join(self._cpg.Edge, self._cpg.Edge.target == self._cpg.Function.uuid)
            .filter(
                self._cpg.Edge.kind == EdgeKind.CALLGRAPH,
                self._cpg.Edge.source == function.uuid,
                self._cpg.Function.uuid != function.uuid,
            )
            .all()
        }


# TODO(lb): parameterize over context sensitivity?
@pytest.mark.parametrize("program", ["notes.c", "exceptions.cpp"])
def test_callgraph_consistency(
    pointer_analysis_results_v2, session, cpg_db_v2, program, optimization_flags
):
    """Walk the callgraphs from the Datalog analysis and the CPG.

    Checks that they are consistent with one another.
    """
    cpg = cpg_db_v2(
        program,
        compile_options=dict(extra_compiler_flags=optimization_flags),
        build_options=dict(debug_pointer_analysis=True),
    )
    dl_results = pointer_analysis_results_v2(session, cpg)
    dl_callgraph = DatalogCallgraph(dl_results.get("subset.callgraph.callgraph_edge.csv.gz"))
    cpg_callgraph = CPGCallgraph(cpg, session)

    to_visit = ["main"]
    while to_visit:
        visiting = to_visit.pop()
        print("VISITING", visiting)  # only printed when this test fails
        dl_successors = dl_callgraph.callees(visiting)
        dl_predecessors = dl_callgraph.callers(visiting)
        cpg_fun = session.query(cpg.Function).filter_by(name=visiting).one()
        cpg_successors = cpg_callgraph.callees(cpg_fun)
        cpg_predecessors = cpg_callgraph.callers(cpg_fun)
        cpg_call_successors = cpg_callgraph.callsite_callees(cpg_fun)
        cpg_call_predecessors = cpg_callgraph.callsite_callers(cpg_fun)
        cpg_callgraph_successors = cpg_callgraph.callgraph_callees(cpg_fun)
        cpg_callgraph_predecessors = cpg_callgraph.callgraph_callers(cpg_fun)
        assert dl_successors == cpg_successors
        assert dl_successors == cpg_call_successors
        assert dl_successors == cpg_callgraph_successors
        assert dl_predecessors == cpg_predecessors
        assert dl_predecessors == cpg_call_predecessors
        assert dl_predecessors == cpg_callgraph_predecessors
        to_visit += dl_successors


def test_callgraph_functiontable(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "functiontable.c", compile_options=dict(extra_compiler_flags=optimization_flags)
    )
    main = session.query(cpg.Function).filter_by(name="main").one()
    assert {f.name for f in main.callees} >= {"foo", "bar", "baz", "srand", "time"}


def test_callgraph_virtual(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2("virtual.cpp", compile_options=dict(extra_compiler_flags=optimization_flags))
    everyone_eats = (
        session.query(cpg.Function)
        .filter_by(demangled_name="everyone_eats(Animal**, unsigned int)")
        .one()
    )
    assert {f.demangled_name for f in everyone_eats.callees} >= {
        "Llama::eat() const",
        "Dog::eat() const",
        "Poodle::eat() const",
    }

    someone_eats = (
        session.query(cpg.Function).filter_by(demangled_name="someone_eats(Animal&)").one()
    )
    someone_callees = {f.demangled_name for f in someone_eats.callees}
    assert "Llama::eat() const" not in someone_callees
    # In unoptimized code the lack of strong update confuses the vtables
    # of the Poodle class and its superclass, Dog
    if len(set(optimization_flags).intersection({"-O0", "-O1"})) == 0:
        assert "Dog::eat() const" not in someone_callees
    assert "Poodle::eat() const" in someone_callees
