"""Test points-to."""
import pytest
from sqlalchemy.orm import aliased

from mate_common.models.builds import PointerAnalysis


def assert_memory_locations_have_aliases(cpg, session):
    """Some memory location should have at least one instruction pointing to it.

    TODO: Why doesn't every?
    """
    mem_locations = session.query(cpg.MemoryLocation).all()
    assert len(mem_locations) > 0
    assert any(len(list(loc.pointers)) > 0 for loc in mem_locations)


@pytest.mark.parametrize("cflags", [("-O0",)])
def test_llvm_points_to_context(session, cpg_db_v2, cflags):

    cpg = cpg_db_v2(
        "points-to_context.c",
        compile_options=dict(extra_compiler_flags=cflags),
        build_options=dict(
            llvm_memory_dependence=True,
            machine_code_mapping=False,
        ),
    )

    a_alloca = (
        session.query(cpg.Alloca)
        .filter(
            cpg.Alloca.attributes["pretty_string"].as_string().like("%t2 = alloca i32, align 4%")
        )
        .one()
    )

    b_alloca = (
        session.query(cpg.Alloca)
        .filter(
            cpg.Alloca.attributes["pretty_string"].as_string().like("%t4 = alloca i32, align 4%")
        )
        .one()
    )

    pa = (
        session.query(cpg.Instruction)
        .filter(
            cpg.Instruction.attributes["pretty_string"]
            .as_string()
            .like("%t5 = load i32*, i32** %%t1, align 8%")
        )
        .one()
    )

    pb = (
        session.query(cpg.Instruction)
        .filter(
            cpg.Instruction.attributes["pretty_string"]
            .as_string()
            .like("%t7 = load i32*, i32** %%t3, align 8%")
        )
        .one()
    )

    assert_memory_locations_have_aliases(cpg, session)
    assert len(a_alloca.points_to) == 1
    assert len(b_alloca.points_to) == 1
    assert b_alloca.points_to[0] in pb.points_to
    assert a_alloca.points_to[0] in pa.points_to


@pytest.mark.parametrize("cflags", [("-O0",)])
def test_llvm_points_to_malloc_context(session, cpg_db_v2, cflags):
    cpg = cpg_db_v2(
        "points-to_malloc-context.c",
        compile_options=dict(extra_compiler_flags=cflags),
        build_options=dict(
            machine_code_mapping=False,
        ),
    )

    a = (
        session.query(cpg.CallSite)
        .filter(
            cpg.CallSite.attributes["pretty_string"]
            .as_string()
            .like("%t5 = call %%struct.obj* @fun1()%")
        )
        .one()
    )
    b = (
        session.query(cpg.CallSite)
        .filter(
            cpg.CallSite.attributes["pretty_string"]
            .as_string()
            .like("%t6 = call %%struct.obj* @fun2()%")
        )
        .one()
    )
    c = (
        session.query(cpg.CallSite)
        .filter(
            cpg.CallSite.attributes["pretty_string"]
            .as_string()
            .like("%t7 = call %%struct.obj* @fun3()%")
        )
        .one()
    )
    d = (
        session.query(cpg.CallSite)
        .filter(
            cpg.CallSite.attributes["pretty_string"]
            .as_string()
            .like("%t8 = call %%struct.obj* @fun4()%")
        )
        .one()
    )

    assert_memory_locations_have_aliases(cpg, session)
    assert a.points_to
    assert b.points_to
    assert set() == set(a.points_to) & set(b.points_to)
    assert set() == set(a.points_to) & set(c.points_to)
    assert set() == set(a.points_to) & set(c.points_to)
    assert set(c.points_to) == set(d.points_to)


@pytest.mark.parametrize("cflags", [("-O0",)])
def test_llvm_points_to_new_context(session, cpg_db_v2, cflags):
    cpg = cpg_db_v2(
        "points-to_new-context.cpp",
        compile_options=dict(extra_compiler_flags=cflags),
        build_options=dict(
            llvm_memory_dependence=False,
            machine_code_mapping=False,
        ),
    )

    a = (
        session.query(cpg.CallSite)
        .filter(
            cpg.CallSite.attributes["pretty_string"]
            .as_string()
            .like("%t5 = call %%struct.obj* @_Z4fun1v()%")
        )
        .one()
    )
    b = (
        session.query(cpg.CallSite)
        .filter(
            cpg.CallSite.attributes["pretty_string"]
            .as_string()
            .like("%t6 = call %%struct.obj* @_Z4fun2v()%")
        )
        .one()
    )
    c = (
        session.query(cpg.CallSite)
        .filter(
            cpg.CallSite.attributes["pretty_string"]
            .as_string()
            .like("%t7 = call %%struct.obj* @_Z4fun3v()%")
        )
        .one()
    )
    d = (
        session.query(cpg.CallSite)
        .filter(
            cpg.CallSite.attributes["pretty_string"]
            .as_string()
            .like("%t8 = call %%struct.obj* @_Z4fun4v()%")
        )
        .one()
    )

    assert_memory_locations_have_aliases(cpg, session)
    assert a.points_to
    assert b.points_to
    assert set() == set(a.points_to) & set(b.points_to)
    assert set() == set(a.points_to) & set(c.points_to)
    assert set() == set(a.points_to) & set(c.points_to)
    assert set(c.points_to) == set(d.points_to)


@pytest.mark.parametrize("pointer_analysis", list(PointerAnalysis))
def test_points_to_variants(cpg_db_v2, pointer_analysis):
    cpg_db_v2(
        "hello.c",
        build_options=dict(
            pointer_analysis=pointer_analysis,
            machine_code_mapping=False,
        ),
    )


@pytest.mark.parametrize(
    "sensitivity", ["insensitive", "1-caller", "2-caller", "1-callsite", "2-callsite"]
)
def test_type_backpropagation(session, cpg_db_v2, sensitivity):
    cpg = cpg_db_v2(
        "type-backprop.c",
        compile_options=dict(extra_compiler_flags=["-O0"]),
        build_options=dict(
            llvm_memory_dependence=False,
            machine_code_mapping=False,
            context_sensitivity=sensitivity,
        ),
    )

    def get_printed(fun):
        CallToPrint = aliased(cpg.CallSite)
        Block = aliased(cpg.Block)
        Function = aliased(cpg.Function)
        Load = aliased(cpg.Load)
        Location = aliased(cpg.MemoryLocation)
        return (
            session.query(CallToPrint)
            .filter(CallToPrint.calls("printf"))
            .join(Block, CallToPrint.parent_block)
            .join(Function, Block.parent_function)
            .filter(Function.name == fun)
            .join(Load, CallToPrint.uses)
            .join(Location, Load.loads_from)
            .with_entities(Location)
            .all()
        )

    printed_ints = get_printed("print_int")
    printed_doubles = get_printed("print_double")

    assert len(get_printed("print_int")) > 0
    assert len(get_printed("print_double")) > 0

    aliases = {ml.uuid for ml in printed_ints}.intersection({ml.uuid for ml in printed_doubles})

    if sensitivity == "insensitive":
        assert len(aliases) > 0
    else:
        assert len(aliases) == 0

    def get_containers(fun):
        CallToPrint = aliased(cpg.CallSite)
        Block = aliased(cpg.Block)
        Function = aliased(cpg.Function)
        Load1 = aliased(cpg.Load)
        Load2 = aliased(cpg.Load)
        Location = aliased(cpg.MemoryLocation)
        return (
            session.query(CallToPrint)
            .filter(CallToPrint.calls("printf"))
            .join(Block, CallToPrint.parent_block)
            .join(Function, Block.parent_function)
            .filter(Function.name == fun)
            .join(Load1, CallToPrint.uses)
            .join(Load2, Load1.uses)
            .join(Location, Load2.loads_from)
            .with_entities(Location)
            .all()
        )

    int_structs = get_containers("print_int")
    double_structs = get_containers("print_double")

    aliases = {ml.uuid for ml in int_structs}.intersection({ml.uuid for ml in double_structs})

    if sensitivity == "insensitive":
        assert len(aliases) > 0
    else:
        assert len(aliases) == 0

    if sensitivity != "insensitive":
        # We shouldn't create double_struct-typed allocations when using an allocation as an int_struct
        assert (
            len([s for s in int_structs if "double_struct" in s.attributes["pretty_string"]]) == 0
        )
        # But we should create int_struct-typed allocations
        assert len([s for s in int_structs if "int_struct" in s.attributes["pretty_string"]]) > 0
        # We shouldn't create int_struct-typed allocations when using an allocation as an double_struct
        assert (
            len([s for s in double_structs if "int_struct" in s.attributes["pretty_string"]]) == 0
        )
        # But we should create double_struct-typed allocations
        assert (
            len([s for s in double_structs if "double_struct" in s.attributes["pretty_string"]]) > 0
        )

    assert (
        session.query(cpg.MemoryLocation)
        .filter(
            cpg.MemoryLocation.attributes["allocation_context"].astext.contains("int"),
            cpg.MemoryLocation.attributes["alias_set_identifier"].astext.contains("double_struct"),
        )
        .count()
    ) == 0

    assert (
        session.query(cpg.MemoryLocation)
        .filter(
            cpg.MemoryLocation.attributes["allocation_context"].astext.contains("double"),
            cpg.MemoryLocation.attributes["alias_set_identifier"].astext.contains("int_struct"),
        )
        .count()
    ) == 0

    if sensitivity != "insensitive":
        assert (
            session.query(cpg.MemoryLocation)
            .filter(cpg.MemoryLocation.attributes["allocation_context"].astext.contains("int"))
            .count()
        ) > 0

        assert (
            session.query(cpg.MemoryLocation)
            .filter(
                cpg.MemoryLocation.attributes["allocation_context"].astext.contains("int"),
                cpg.MemoryLocation.attributes["alias_set_identifier"].astext.contains("int_struct"),
            )
            .count()
        ) > 0

        assert (
            session.query(cpg.MemoryLocation)
            .filter(cpg.MemoryLocation.attributes["allocation_context"].astext.contains("double"))
            .count()
        ) > 0

        assert (
            session.query(cpg.MemoryLocation)
            .filter(
                cpg.MemoryLocation.attributes["allocation_context"].astext.contains("double"),
                cpg.MemoryLocation.attributes["alias_set_identifier"].astext.contains(
                    "double_struct"
                ),
            )
            .count()
        ) > 0
