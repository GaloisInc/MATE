from mate_query.cfl import CSDataflowPath, CSThinDataflowPath
from mate_query.db import PathBuilder


def test_thin_dataflow(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "test-dataflow.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
    )

    input_uuids = [
        n
        for (n,) in (
            session.query(cpg.InputSignature.uuid)
            .filter(cpg.InputSignature.tags.contains(["user_input"]))
            .all()
        )
    ]

    bind_uuids = [n for (n,) in (session.query(cpg.ParamBinding.uuid).all())]

    df = (
        PathBuilder(CSThinDataflowPath)
        .starting_at(lambda Node: Node.uuid.in_(input_uuids))
        .stopping_at(lambda Node: Node.uuid.in_(bind_uuids))
        .build(cpg, keep_start=False)
    )

    # There's only a thin dataflow to *one* of the two prints.
    session.query(df).with_entities(df.target).one()


def test_thick_dataflow(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "test-dataflow.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
    )

    input_uuids = [
        n
        for (n,) in (
            session.query(cpg.InputSignature.uuid)
            .filter(cpg.InputSignature.tags.contains(["user_input"]))
            .all()
        )
    ]

    bind_uuids = [n for (n,) in (session.query(cpg.ParamBinding.uuid).all())]

    df = (
        PathBuilder(CSDataflowPath)
        .starting_at(lambda Node: Node.uuid.in_(input_uuids))
        .stopping_at(lambda Node: Node.uuid.in_(bind_uuids))
        .build(cpg, keep_start=False)
    )

    # There's a thick dataflow to *both* prints
    assert 2 == len(session.query(df).with_entities(df.target).all())
