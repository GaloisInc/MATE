"""Tests to ensure that the test harness itself is working correctly."""


def test_new_build(build, session):
    assert build is not None

    cpg = session.graph_from_build(build)

    node_count = session.query(cpg.Node).count()
    assert node_count == 0

    edge_count = session.query(cpg.Edge).count()
    assert edge_count == 0


def test_diamond_graph(session, diamond_graph):
    node_count = session.query(diamond_graph.Node).count()
    assert node_count == 4

    edge_count = session.query(diamond_graph.Edge).count()
    assert edge_count == 4


def test_cpg_db_v2(session, cpg_db_v2):
    cpg = cpg_db_v2(
        "hello.c",
        build_options=dict(
            machine_code_mapping=False, do_pointer_analysis=False, llvm_memory_dependence=False
        ),
    )

    assert session.query(cpg.Node).count() == 149
    assert session.query(cpg.Edge).count() == 544
