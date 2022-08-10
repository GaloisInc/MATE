"""This file tests various cpg.DWARFType properties."""
import pytest


def assert_common_properties(dwarf_type):
    assert dwarf_type.common is not None
    assert dwarf_type.common.align is not None
    assert dwarf_type.common.artificial is not None
    assert dwarf_type.common.forward_decl is not None
    assert dwarf_type.common.name is not None
    assert dwarf_type.common.size is not None
    assert dwarf_type.common.offset is not None
    assert dwarf_type.common.tag is not None
    assert dwarf_type.common.virtual is not None

    # Convenient aliases.
    assert dwarf_type.name == dwarf_type.common.name
    assert dwarf_type.tag == dwarf_type.common.tag


@pytest.mark.parametrize(
    "cflags",
    [
        ("-O0",),
        # TODO: The following flags optimize out the variable req
        # ("-O1",),
        # ("-O2",),
        # ("-O3",),
    ],
)
def test_dwarf_node_properties(session, cpg_db_v2, cflags):
    cpg = cpg_db_v2("dwarf_properties.cpp", compile_options=dict(extra_compiler_flags=cflags))
    main = session.query(cpg.Function).filter_by(name="main").one()
    main_mf = main.machine_functions[0]

    # TODO(ww): Re-write these without the MachineFunction indirection
    # once we fix Argument -> DWARFArgument relationships.
    # See: https://gitlab-ext.galois.com/mate/MATE/-/issues/1053
    # Test Basic Properties
    argc = main_mf.arguments[0].dwarf_type
    assert argc.is_basic
    assert_common_properties(argc)

    # Test Derived Properties
    # argv is a `char[] const *`, so has three levels of derived types before the
    # "char" base type.
    argv = main_mf.arguments[1].dwarf_type
    assert argv.is_derived
    assert argv.is_pointer
    assert argv.base_type.is_pointer
    assert argv.base_type.base_type.is_const
    assert argv.base_type.base_type.base_type.is_basic
    assert argv.base_type.base_type.base_type.common.name == "char"
    assert_common_properties(argv)

    # # Test all_derived_types
    base0 = argv.base_type.deriving_types
    base1 = argv.base_type.base_type.deriving_types
    all_dtypes = argv.base_type.base_type.all_derived_types
    assert len(all_dtypes) == (len(base0) + len(base1))
    assert set(base0).issubset(set(all_dtypes))
    assert set(base1).issubset(set(all_dtypes))

    # Test Class Properties
    a = session.query(cpg.DWARFLocalVariable).filter_by(name="a").one().dwarf_type
    assert a.is_class
    assert a.name == "Animal"
    assert a.base_type is None
    assert_common_properties(a)

    # Test Enum Properties
    jan = session.query(cpg.DWARFLocalVariable).filter_by(name="jan").one().dwarf_type
    assert jan.is_enum
    assert len(jan.enumerators) == 12
    assert_common_properties(jan)

    # Test Union Properties
    c = session.query(cpg.DWARFLocalVariable).filter_by(name="color").one().dwarf_type
    assert c.is_union
    assert c.name == "Color"
    assert all([f.is_member for f in c.members])
    assert [f.name for f in c.members] == ["red", "green", "blue"]
    assert_common_properties(c)

    # Test Structure Properties
    head = session.query(cpg.DWARFLocalVariable).filter_by(name="head").one().dwarf_type
    assert head.is_structure
    assert head.name == "ListNode"
    assert all([f.is_member for f in c.members])
    assert [f.name for f in head.members] == ["val", "next"]
    assert head == head.members[1].base_type.base_type.recursive_type
    assert_common_properties(head)

    # Test Array Properties
    months = session.query(cpg.DWARFLocalVariable).filter_by(name="months").one().dwarf_type
    assert months.is_array
    assert months.base_type.name == "int"
    assert_common_properties(months)

    # Test Subroutine Properties
    fp = session.query(cpg.DWARFLocalVariable).filter_by(name="fp").one().dwarf_type
    assert fp.is_pointer
    assert fp.base_type.is_subroutine
    assert fp.base_type.return_type.is_void
    assert len(fp.base_type.param_types) == 2
    assert_common_properties(fp)


@pytest.mark.parametrize(
    "cflags",
    [
        ("-O0",),
        # TODO: The following flags optimize out the variable req
        # ("-O1",),
        # ("-O2",),
        # ("-O3",),
    ],
)
def test_dwarf_type_queries(session, cpg_db_v2, cflags):
    cpg = cpg_db_v2("dwarf_properties.cpp", compile_options=dict(extra_compiler_flags=cflags))

    # dwarf_properties has a void type because it contains a function pointer that returns void
    voids = session.query(cpg.DWARFType).filter(cpg.DWARFType.is_void).all()
    assert len(voids) == 1

    basics = session.query(cpg.DWARFType).filter(cpg.DWARFType.is_basic).all()
    assert {b.name for b in basics} == {
        "int",
        "bool",
        "unsigned int",
        "char",
        "long unsigned int",
        "void",
    }

    composites = session.query(cpg.CompositeType).all()
    assert composites == []

    structs = session.query(cpg.StructureType).all()
    assert {"ListNode"} == {s.name for s in structs}

    arrays = session.query(cpg.ArrayType).all()
    assert len(arrays) == 1

    enums = session.query(cpg.EnumType).all()
    assert {"Month"} == {e.name for e in enums}

    unions = session.query(cpg.UnionType).all()
    assert {"Color"} == {u.name for u in unions}

    # NOTE(ww): We don't check for an exact set here, since we're in C++ land and
    # including C++ headers brings in some other classes.
    classes = session.query(cpg.ClassType).all()
    assert {"Animal", "Dolphin"}.issubset({c.name for c in classes})

    # There are 7 functions with 6 unique signatures
    #  - 2 global/setup functions with no return/params
    #  - 1 unique signature each for main, printMonth, setMonths, Animal::act, Dolphin::act
    subroutines = session.query(cpg.DWARFType).filter(cpg.DWARFType.is_subroutine).all()
    assert len(subroutines) == 6


@pytest.mark.parametrize(
    "cflags",
    [
        ("-O0",),
        ("-O1",),
        ("-O2",),
        ("-O3",),
    ],
)
def test_machine_function_dwarf_types(session, cpg_db_v2, cflags):
    cpg = cpg_db_v2("cfg-test.c", compile_options=dict(extra_compiler_flags=cflags))

    # map function names to their expected dwarf type_id
    expected = {
        "main": "(<anon> 0 0 (f (int 4 0 (b)) [(int 4 0 (b)) (<anon> 8 0 (d (DW_TAG_pointer_type (<anon> 8 0 (d (DW_TAG_pointer_type (char 1 0 (b))))))))]))",
        "foo": "(<anon> 0 0 (f (int 4 0 (b)) [(int 4 0 (b))]))",
        "bar": "(<anon> 0 0 (f (int 4 0 (b)) [(int 4 0 (b))]))",
        "baz": "(<anon> 0 0 (f (<void>) []))",
    }

    for func_name, type_id in expected.items():
        mi_func = (
            session.query(cpg.MachineFunction).filter(cpg.MachineFunction.name == func_name).one()
        )
        assert mi_func.dwarf_type.pretty_string == type_id


@pytest.mark.parametrize(
    "cflags",
    [
        ("-O0",),
        # TODO: The following flags optimize out the variable req
        # ("-O1",),
        # ("-O2",),
        # ("-O3",),
    ],
)
def test_inheritance(session, cpg_db_v2, cflags):
    cpg = cpg_db_v2("dwarf_properties.cpp", compile_options=dict(extra_compiler_flags=cflags))

    animal = session.query(cpg.ClassType).filter_by(name="Animal").one()
    dolphin = session.query(cpg.ClassType).filter_by(name="Dolphin").one()

    assert animal.parents == []
    assert animal.children == [dolphin]
    assert dolphin.parents == [animal]
    assert dolphin.children == []


def test_multiple_inheritance(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "dwarf_properties2.cpp", compile_options=dict(extra_compiler_flags=optimization_flags)
    )

    base1 = session.query(cpg.StructureType).filter_by(name="BaseStruct1").one()
    base2 = session.query(cpg.StructureType).filter_by(name="BaseStruct2").one()

    child1 = session.query(cpg.StructureType).filter_by(name="ChildStruct1").one()
    child2 = session.query(cpg.StructureType).filter_by(name="ChildStruct2").one()
    child3 = session.query(cpg.StructureType).filter_by(name="ChildStruct3").one()

    assert set(base1.children) == {child1, child2}
    assert set(base2.children) == {child2}

    assert set(child1.children) == {child3}
    assert set(child1.parents) == {base1}

    assert set(child2.children) == {child3}
    assert set(child2.parents) == {base1, base2}

    assert set(child3.children) == set()
    assert set(child3.parents) == {child1, child2}


def test_varargs(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2("varargs.c", compile_options=dict(extra_compiler_flags=optimization_flags))

    add_em_up_ptr = (
        session.query(cpg.DWARFLocalVariable).filter_by(name="add_em_up_ptr").one().dwarf_type
    )
    assert add_em_up_ptr.is_pointer
    assert add_em_up_ptr.base_type.is_subroutine

    add_em_up = add_em_up_ptr.base_type
    assert add_em_up.has_varargs
    assert add_em_up.param_types[-1].is_varargs
