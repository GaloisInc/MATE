"""A test for the basic correctness of our PLT stub information."""


def test_plt_stubs(session, cpg_db_v2):
    cpg = cpg_db_v2("mini-fenway-uaf.c", build_options=dict(do_pointer_analysis=True))

    # mini-fenway-uaf references `malloc`, so we have a Function node for it.
    # But it's an external function, so it's marked as is_declaration and has
    # no MachineFunction nodes. Instead, it has a PLTStub node.
    malloc = session.query(cpg.Function).filter_by(name="malloc").one()
    assert malloc.is_declaration
    assert malloc.machine_functions == []
    assert malloc.plt_stub is not None

    malloc_plt = malloc.plt_stub
    assert malloc_plt.symbol == "malloc"

    # By contrast, mini-fenway-uaf also has `create_ppm`, which has a Function
    # node *and* one or more MachineFunction nodes. But, because it has those,
    # it has no PLTStub node for `create_ppm`.
    create_ppm = session.query(cpg.Function).filter_by(name="create_ppm").one()
    assert not create_ppm.is_declaration
    assert len(create_ppm.machine_functions) >= 1
    assert create_ppm.plt_stub is None
