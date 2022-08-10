"""Tests path building against the CPG's ICFG."""
import pytest

from mate_query import cfl, db


@pytest.mark.parametrize("cflags", [("-O0",), ("-O1",)])
def test_forward_cfg_cfl(session, cpg_db_v2, cflags):
    """pytest entry point."""
    cpg = cpg_db_v2(
        "cfg-test.c",
        compile_options=dict(extra_compiler_flags=cflags),
        build_options=dict(machine_code_mapping=False),
    )

    main = session.query(cpg.Function).filter_by(name="main").one()

    main1 = (
        session.query(cpg.CallSite)
        .filter(
            cpg.CallSite.callees.any(cpg.Function.name == "foo"),
            cpg.CallSite.attributes["location"]["line"].as_integer() == 17,
        )
        .one()
    )

    main2 = (
        session.query(cpg.CallSite)
        .filter(
            cpg.CallSite.callees.any(cpg.Function.name == "foo"),
            cpg.CallSite.attributes["location"]["line"].as_integer() == 19,
        )
        .one()
    )

    main3 = (
        session.query(cpg.CallSite)
        .filter(
            cpg.CallSite.callees.any(cpg.Function.name == "bar"),
            cpg.CallSite.attributes["location"]["line"].as_integer() == 20,
        )
        .one()
    )

    foo1 = (
        session.query(cpg.CallSite)
        .filter(
            cpg.CallSite.callees.any(cpg.Function.name == "bar"),
            cpg.CallSite.attributes["location"]["line"].as_integer() == 6,
        )
        .one()
    )

    stepped_in_path = session.query(
        db.PathBuilder(PathBase=cfl.ForwardCFGPath)
        .starting_at(lambda Node: Node.uuid == main1.uuid)
        .continuing_while(lambda _, Edge: ~(Edge.source == main2.uuid))
        .stopping_at(lambda Node: Node.uuid == main2.uuid)
        .build(cpg, keep_start=False, keep_trace=True)
    ).one()

    stepped_in_path_length = len(stepped_in_path.trace)

    stepped_over_path = session.query(
        db.PathBuilder(PathBase=cfl.ForwardCFGPath)
        .starting_at(lambda Node: Node.uuid == main1.uuid)
        .continuing_while(lambda _, Edge: ~(Edge.source == main2.uuid))
        .stopping_at(lambda Node: Node.uuid == main2.uuid)
        .stepping_over("baz")
        .build(cpg, keep_start=False, keep_trace=True)
    ).one()

    stepped_over_path_length = len(stepped_over_path.trace)

    assert stepped_over_path_length < stepped_in_path_length

    assert (
        session.query(
            db.PathBuilder(PathBase=cfl.ForwardCFGPath)
            .starting_at(lambda Node: Node.uuid == main1.uuid)
            .continuing_while(lambda _, Edge: ~(Edge.source == main2.uuid))
            .stopping_at(lambda Node: Node.uuid == main2.uuid)
            .build(cpg)
        ).count()
        == 1
    )

    assert (
        session.query(
            db.PathBuilder(PathBase=cfl.ForwardCFGPath)
            .starting_at(lambda Node: Node.uuid == main2.uuid)
            .continuing_while(lambda _, Edge: ~(Edge.source == main3.uuid))
            .stopping_at(lambda Node: Node.uuid == main3.uuid)
            .build(cpg)
        ).count()
        == 1
    )

    assert (
        session.query(
            db.PathBuilder(PathBase=cfl.ForwardCFGPath)
            .starting_at(lambda Node: Node.uuid == main2.uuid)
            .stopping_at(lambda Node: Node.uuid == main1.uuid)
            .build(cpg)
        ).count()
        == 0
    )

    assert (
        session.query(
            db.PathBuilder(PathBase=cfl.ForwardCFGPath)
            .starting_at(lambda Node: Node.uuid == main3.uuid)
            .continuing_while(lambda _, Edge: ~(Edge.target == main2.uuid))
            .stopping_at(lambda Node: Node.uuid == main2.uuid)
            .build(cpg)
        ).count()
        == 0
    )

    assert (
        session.query(
            db.PathBuilder(PathBase=cfl.ForwardCFGPath)
            .starting_at(lambda Node: Node.uuid == main.uuid)
            .stopping_at(lambda Node: Node.uuid == foo1.uuid)
            .build(cpg)
        ).count()
        == 4
    )

    assert (
        session.query(
            db.PathBuilder(PathBase=cfl.ForwardCFGPath)
            .starting_at(lambda Node: Node.uuid == foo1.uuid)
            .stopping_at(lambda Node: Node.uuid == main3.uuid)
            .build(cpg)
        ).count()
        == 0
    )

    assert (
        session.query(
            db.PathBuilder(PathBase=cfl.UnmatchedForwardCFGPath)
            .starting_at(lambda Node: Node.uuid == foo1.uuid)
            .stopping_at(lambda Node: Node.uuid == main3.uuid)
            .build(cpg)
        ).count()
        == 2
    )

    assert (
        session.query(
            db.PathBuilder(PathBase=cfl.UnmatchedForwardCFGPath)
            .starting_at(lambda Node: Node.uuid == foo1.uuid)
            .stopping_at(lambda Node: Node.uuid == main3.uuid)
            .build(cpg)
        ).count()
        >= 1
    )


@pytest.mark.parametrize("cflags", [("-O0",), ("-O1",)])
def test_context_sensitive_cfg_cfl(session, cpg_db_v2, cflags):
    """pytest entry point."""
    cpg = cpg_db_v2(
        "cfg-test.c",
        compile_options=dict(extra_compiler_flags=cflags),
        build_options=dict(machine_code_mapping=False),
    )

    main = session.query(cpg.Function).filter_by(name="main").one()

    main1 = (
        session.query(cpg.CallSite)
        .filter(
            cpg.CallSite.callees.any(cpg.Function.name == "foo"),
            cpg.CallSite.attributes["location"]["line"].as_integer() == 17,
        )
        .one()
    )

    main2 = (
        session.query(cpg.CallSite)
        .filter(
            cpg.CallSite.callees.any(cpg.Function.name == "foo"),
            cpg.CallSite.attributes["location"]["line"].as_integer() == 19,
        )
        .one()
    )

    main3 = (
        session.query(cpg.CallSite)
        .filter(
            cpg.CallSite.callees.any(cpg.Function.name == "bar"),
            cpg.CallSite.attributes["location"]["line"].as_integer() == 20,
        )
        .one()
    )

    foo1 = (
        session.query(cpg.CallSite)
        .filter(
            cpg.CallSite.callees.any(cpg.Function.name == "bar"),
            cpg.CallSite.attributes["location"]["line"].as_integer() == 6,
        )
        .one()
    )

    assert (
        session.query(
            db.PathBuilder(PathBase=cfl.CSCFGPath)
            .starting_at(lambda Node: Node.uuid == main1.uuid)
            .continuing_while(lambda _, Edge: ~(Edge.source == main2.uuid))
            .stopping_at(lambda Node: Node.uuid == main2.uuid)
            .build(cpg)
        ).count()
        == 1
    )

    assert (
        session.query(
            db.PathBuilder(PathBase=cfl.CSCFGPath)
            .starting_at(lambda Node: Node.uuid == main2.uuid)
            .continuing_while(lambda _, Edge: ~(Edge.source == main3.uuid))
            .stopping_at(lambda Node: Node.uuid == main3.uuid)
            .build(cpg)
        ).count()
        == 1
    )

    assert (
        session.query(
            db.PathBuilder(PathBase=cfl.CSCFGPath)
            .starting_at(lambda Node: Node.uuid == main2.uuid)
            .stopping_at(lambda Node: Node.uuid == main1.uuid)
            .build(cpg)
        ).count()
        == 0
    )

    assert (
        session.query(
            db.PathBuilder(PathBase=cfl.CSCFGPath)
            .starting_at(lambda Node: Node.uuid == main3.uuid)
            .continuing_while(lambda _, Edge: ~(Edge.target == main2.uuid))
            .stopping_at(lambda Node: Node.uuid == main2.uuid)
            .build(cpg)
        ).count()
        == 0
    )

    assert (
        session.query(
            db.PathBuilder(PathBase=cfl.CSCFGPath)
            .starting_at(lambda Node: Node.uuid == main.uuid)
            .stopping_at(lambda Node: Node.uuid == foo1.uuid)
            .build(cpg)
        ).count()
        == 4
    )

    assert (
        session.query(
            db.PathBuilder(PathBase=cfl.CSCFGPath)
            .starting_at(lambda Node: Node.uuid == foo1.uuid)
            .stopping_at(lambda Node: Node.uuid == main3.uuid)
            .build(cpg)
        ).count()
        == 2
    )
