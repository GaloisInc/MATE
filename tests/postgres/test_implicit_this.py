"""Test that we're able to traverse the implicit *this parameter provided by C++ member
functions."""


def test_implicit_this(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "customclassinheritance.cpp",
        compile_options=dict(extra_compiler_flags=optimization_flags),
    )

    # TODO(ww): Re-write this without the MachineFunction indirection
    # once we fix Argument -> DWARFArgument relationships.
    # See: https://gitlab-ext.galois.com/mate/MATE/-/issues/1053
    dog_act = session.query(cpg.Function).filter_by(demangled_name="Dog::act()").one()
    dog_act_mf = dog_act.machine_functions[0]

    # Dog::act() "takes" exactly one argument: the implicit *this back to its containing
    # object.
    arguments = dog_act_mf.arguments
    assert len(arguments) == 1

    implicit_this = arguments[0]
    assert implicit_this.name == "this"
    assert implicit_this.dwarf_location is not None
    assert implicit_this.dwarf_scope is not None
    assert implicit_this.dwarf_scope.va_start is not None
    assert implicit_this.dwarf_scope.va_end is not None
    assert implicit_this.dwarf_type is not None

    # Our type is a pointer type, deriving a Dog class.
    this_type = implicit_this.dwarf_type
    assert this_type.is_derived
    assert this_type.is_pointer

    base_type = this_type.base_type
    assert base_type.name == "Dog"
    assert base_type.tag == "DW_TAG_class_type"
    assert base_type.is_class
