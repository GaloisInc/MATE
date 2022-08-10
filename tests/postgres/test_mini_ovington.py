"""Test the points-to analysis callgraph construction."""

from __future__ import annotations

from sqlalchemy.orm import aliased


def test_minimal_callgraph(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "ovington-minimal.cpp",
        compile_options=dict(extra_compiler_flags=optimization_flags),
    )

    def check_callee_by_name(caller_name, callee_name):
        Caller = aliased(cpg.Function)
        Callee = aliased(cpg.Function)
        return (
            session.query(Caller)
            .filter_by(demangled_name=caller_name)
            .join(Callee, Caller.callees)
            .filter(Callee.demangled_name == callee_name)
            .count()
        ) > 0

    assert check_callee_by_name("hardcoded_stack_notvirtual()", "FakeLambda::notvirtual() const")
    assert check_callee_by_name("hardcoded_ptr_notvirtual()", "FakeLambda::notvirtual() const")
    assert check_callee_by_name("hardcoded_shared_notvirtual()", "FakeLambda::notvirtual() const")

    assert check_callee_by_name("hardcoded_stack()", "FakeLambda::inspect() const")
    assert check_callee_by_name("hardcoded_ptr()", "FakeLambda::inspect() const")
    assert check_callee_by_name("hardcoded_shared()", "FakeLambda::inspect() const")


def test_extra_minimal_callgraph(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "ovington-extra-minimal.cpp",
        compile_options=dict(extra_compiler_flags=optimization_flags),
    )

    def check_callee_by_name(caller_name, callee_name):
        Caller = aliased(cpg.Function)
        Callee = aliased(cpg.Function)
        return (
            session.query(Caller)
            .filter_by(demangled_name=caller_name)
            .join(Callee, Caller.callees)
            .filter(Callee.demangled_name == callee_name)
            .count()
        ) > 0

    assert check_callee_by_name("hardcoded_shared()", "FakeLambda::inspect() const")
