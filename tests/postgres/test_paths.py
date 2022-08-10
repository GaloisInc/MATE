from mate_query import db


def test_diamond_paths(session, diamond_graph):
    p = db.PathBuilder().build(diamond_graph, keep_edge=True, keep_trace=True)
    all_paths = session.query(p).all()
    assert {path.trace for path in all_paths} == {
        (),
        ("AB",),
        ("AC",),
        ("BD",),
        ("CD",),
        ("AB", "BD"),
        ("AC", "CD"),
    }


def test_diamond_sources_all(session, diamond_graph):
    p = db.PathBuilder().build(diamond_graph)
    all_paths = session.query(p).all()
    assert {path.source for path in all_paths} == {"A", "B", "C", "D"}


def test_diamond_sources_starting_at(session, diamond_graph):
    for node in ("A", "B", "C", "D"):
        p = db.PathBuilder().starting_at(lambda Node: Node.uuid == node).build(diamond_graph)
        all_paths = session.query(p).all()
        assert {path.source for path in all_paths} == {node}


def test_diamond_targets(session, diamond_graph):
    p = db.PathBuilder().build(diamond_graph)
    all_paths = session.query(p).all()
    # The path queries always assume the presence of self-edges.
    assert {path.target for path in all_paths} == {"A", "B", "C", "D"}


def test_diamond_source_stack_no_cfl(session, diamond_graph):
    p = db.PathBuilder().build(diamond_graph)
    all_paths = session.query(p).all()
    assert {path.source_stack for path in all_paths} == {None}


def test_diamond_state_no_cfl(session, diamond_graph):
    p = db.PathBuilder().build(diamond_graph)
    all_paths = session.query(p).all()
    assert {path.state for path in all_paths} == {None}


def test_diamond_edge_no_keep(session, diamond_graph):
    p = db.PathBuilder().build(diamond_graph)
    all_paths = session.query(p).all()
    assert {path.edge for path in all_paths} == {None}


def test_diamond_edge_all(session, diamond_graph):
    p = db.PathBuilder().build(diamond_graph, keep_start=False, keep_edge=True)
    all_paths = session.query(p).all()
    assert {path.edge for path in all_paths} == {None, "AC", "AB", "BD", "CD"}


def test_diamond_edge_stopping_at(session, diamond_graph):
    p = (
        db.PathBuilder()
        .stopping_at(lambda Node: Node.uuid == "D")
        .build(diamond_graph, keep_start=False, keep_edge=True)
    )
    all_paths = session.query(p).all()
    assert {path.edge for path in all_paths} == {None, "BD", "CD"}


def test_path_length_limit(session, diamond_graph):
    p = db.PathBuilder().limited_to(1).build(diamond_graph, keep_edge=True, keep_trace=True)
    all_paths = session.query(p).all()
    assert {path.trace for path in all_paths} == {
        (),
        ("AB",),
        ("AC",),
        ("BD",),
        ("CD",),
    }


def test_path_starting_at(session, diamond_graph):
    p = (
        db.PathBuilder()
        .starting_at(lambda Node: Node.uuid == "B")
        .build(diamond_graph, keep_edge=True, keep_trace=True)
    )
    all_paths = session.query(p).all()
    assert {path.trace for path in all_paths} == {(), ("BD",)}


def test_path_continuing_while(session, diamond_graph):
    p = (
        db.PathBuilder()
        .continuing_while(lambda _, Edge: Edge.uuid.in_({"AB", "BD"}))
        .build(diamond_graph, keep_edge=True, keep_trace=True)
    )
    all_paths = session.query(p).all()
    assert {path.trace for path in all_paths} == {("AB",), ("BD",), ("AB", "BD"), ()}


def test_path_stopping_at(session, diamond_graph):
    p = (
        db.PathBuilder()
        .stopping_at(lambda Node: Node.uuid == "D")
        .build(diamond_graph, keep_edge=True, keep_trace=True)
    )
    all_paths = session.query(p).all()
    assert {path.trace for path in all_paths} == {
        (),
        ("AB", "BD"),
        ("AC", "CD"),
        ("BD",),
        ("CD",),
    }


def test_path_reverse_starting_at(session, diamond_graph):
    p = (
        db.PathBuilder()
        .starting_at(lambda Node: Node.uuid == "B")
        .reverse()
        .build(diamond_graph, keep_edge=True, keep_trace=True)
    )

    all_paths = session.query(p).all()
    assert {path.trace for path in all_paths} == {(), ("BD",)}


def test_path_reverse_stopping_at(session, diamond_graph):
    p = (
        db.PathBuilder()
        .stopping_at(lambda Node: Node.uuid == "C")
        .reverse()
        .build(diamond_graph, keep_edge=True, keep_trace=True)
    )

    all_paths = session.query(p).all()
    assert {path.trace for path in all_paths} == {(), ("AC",)}
