import pytest


def test_vtable_basic(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2("virtual.cpp", compile_options=dict(extra_compiler_flags=optimization_flags))

    # Each derived class has a vtable, and each vtable contains just the overridden function.
    for name in {"Llama", "Dog", "Poodle"}:
        vtable = session.query(cpg.VTable).filter_by(class_name=name).one()

        assert len(vtable.members) == len(vtable.machine_functions) == 1
        assert vtable.machine_functions[0].demangled_name == f"{name}::eat() const"

        # The backwards edge (MachineFunction -> [VTable]) also works.
        assert vtable.machine_functions[0].vtables[0] == vtable

    # Depending on the optimization level the base class might also have vtable.
    # If present, its single member is a PLTStub pointing to __cxa_pure_virtual.
    animal_vtable = session.query(cpg.VTable).filter_by(class_name="Animal").one_or_none()
    if animal_vtable is not None:
        assert len(animal_vtable.members) == 1
        assert len(animal_vtable.machine_functions) == 0
        assert len(animal_vtable.plt_stubs) == 1

        cxa_pure_virtual = session.query(cpg.PLTStub).filter_by(va=animal_vtable.members[0]).one()
        assert cxa_pure_virtual == animal_vtable.plt_stubs[0]
        assert cxa_pure_virtual.symbol == "__cxa_pure_virtual"


@pytest.mark.xfail(reason="not fully implemented")
def test_vtable(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "virtual-multiple-inheritance.cpp",
        compile_options=dict(extra_compiler_flags=optimization_flags),
    )

    # Every member of the vtable should be mapped to some CPG-level feature,
    # whether it's a MachineFunction, PLTStub, member field, etc.
    # This currently fails since we don't map member fields.
    for vtable in session.query(cpg.VTable).all():
        assert len(vtable.members) == len(vtable.machine_functions) + len(vtable.plt_stubs)
