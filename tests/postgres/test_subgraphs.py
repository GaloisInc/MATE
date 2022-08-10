_SMALL_CPG_NODE_COUNT = 8


def test_small_cfg(small_graph, session):
    cfg = small_graph.cfg
    assert session.query(cfg.Node).count() == _SMALL_CPG_NODE_COUNT
    assert session.query(cfg.Edge).count() == 1


def test_small_cg(small_graph, session):
    cg = small_graph.cg
    assert session.query(cg.Node).count() == 3
    assert session.query(cg.Edge).count() == 2


def test_small_ast(small_graph, session):
    ast = small_graph.ast
    assert session.query(ast.Node).count() == _SMALL_CPG_NODE_COUNT
    assert session.query(ast.Edge).count() == 2


def test_small_dfg(small_graph, session):
    dfg = small_graph.dfg
    assert session.query(dfg.Node).count() == _SMALL_CPG_NODE_COUNT
    assert session.query(dfg.Edge).count() == 1


def test_small_ifg(small_graph, session):
    ifg = small_graph.ifg
    assert session.query(ifg.Node).count() == _SMALL_CPG_NODE_COUNT
    assert session.query(ifg.Edge).count() == 2


def test_small_cdg(small_graph, session):
    cdg = small_graph.cdg
    assert session.query(cdg.Node).count() == _SMALL_CPG_NODE_COUNT
    assert session.query(cdg.Edge).count() == 1


def test_small_ptg(small_graph, session):
    ptg = small_graph.ptg
    assert session.query(ptg.Node).count() == _SMALL_CPG_NODE_COUNT
    assert session.query(ptg.Edge).count() == 3
