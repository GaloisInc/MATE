"""Test points-to and dataflow signatures."""
import itertools
from pathlib import Path

import jsonschema
import pytest
import yaml
from sqlalchemy.orm import aliased

from mate.build.build import CPGBuildError, signatures
from mate_common.models.builds import PointerAnalysis
from mate_common.models.cpg_types import EdgeKind
from mate_common.schemata import SIGNATURES_SCHEMA
from mate_query import db
from mate_query.cfl import CSThinDataflowPath

_HERE: Path = Path(__file__).resolve().parent
_ASSETS: Path = _HERE / "assets"


def load_signatures(path):
    with open(path) as io:
        return yaml.safe_load(io)


def check_signature_links(cpg, session):
    F = aliased(cpg.Function)
    CS = aliased(cpg.CallSite)
    for klass in [cpg.InputSignature, cpg.OutputSignature, cpg.DataflowSignature]:
        assert (session.query(klass).count()) == (
            session.query(klass).join(F, klass.signature_for_function).count()
        )
        assert (session.query(klass).count()) == (
            session.query(klass).join(CS, klass.signature_for).count()
        )


def test_signatures_schema():
    signature_file = (_HERE.parent.parent / "default-signatures.yml").resolve()
    assert signature_file.is_file()
    with open(signature_file, "r") as sigfile:
        sigs = yaml.safe_load(sigfile)
    jsonschema.validate(instance=sigs, schema=SIGNATURES_SCHEMA)


def test_signatures_bad(cpg_db_v2):
    with pytest.raises(CPGBuildError) as exc:
        cpg_db_v2(
            "signatures.c",
            build_options=dict(signatures=load_signatures(_ASSETS / "signatures-bad.yml")),
        )

    # TODO(ww): Could also probably test the inner exception string here,
    # to double-check that it's the intended validation error.
    assert isinstance(exc.value, CPGBuildError)


def test_pts_signature_return_alloc(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "signatures.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
        build_options=dict(
            PointerAnalysis=PointerAnalysis.DEBUG,
            signatures=load_signatures(_ASSETS / "signatures.yml"),
        ),
    )
    check_signature_links(cpg, session)

    pos = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_return_alloc_test"))
        .all()
    )
    assert len(pos) == 2

    points_to0 = pos[0].points_to
    points_to1 = pos[1].points_to

    assert len(points_to0) > 0
    assert len(points_to1) > 0
    assert len(set(points_to0).intersection(set(points_to1))) == 0

    CS = aliased(cpg.CallSite)
    IS = aliased(cpg.InputSignature)
    N = aliased(cpg.Node)
    DL = aliased(cpg.MemoryLocation)
    assert set(
        session.query(CS)
        .filter(CS.callees.any(cpg.Function.name == "mate_return_alloc_test"))
        .join(IS, CS.input_signatures)
        .join(N, IS.flows_to)
        .with_entities(N)
        .all()
    ) == set(
        session.query(CS)
        .filter(CS.callees.any(cpg.Function.name == "mate_return_alloc_test"))
        .join(cpg.MemoryLocation, CS.points_to)
        .join(DL, cpg.MemoryLocation.may_alias)
        .with_entities(DL)
        .all()
    )

    neg = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_return_alloc_test_neg"))
        .one()
    )
    assert len(neg.points_to) == 0


def test_pts_signature_return_alloc_override(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "signatures.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
        build_options=dict(
            PointerAnalysis=PointerAnalysis.DEBUG,
            signatures=load_signatures(_ASSETS / "signatures.yml"),
        ),
    )
    check_signature_links(cpg, session)

    pos = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_return_alloc_override_test"))
        .all()
    )
    assert len(pos) == 2

    points_to0 = pos[0].points_to
    points_to1 = pos[1].points_to
    print(points_to0)
    print(points_to1)

    assert len(points_to0) > 0
    assert len(points_to1) > 0
    assert len(set(points_to0).intersection(set(points_to1))) == 0

    CS = aliased(cpg.CallSite)
    IS = aliased(cpg.InputSignature)
    N = aliased(cpg.Node)
    DL = aliased(cpg.MemoryLocation)
    assert set(
        session.query(CS)
        .filter(CS.callees.any(cpg.Function.name == "mate_return_alloc_override_test"))
        .join(IS, CS.input_signatures)
        .join(N, IS.flows_to)
        .with_entities(N)
        .all()
    ) == set(
        session.query(CS)
        .filter(CS.callees.any(cpg.Function.name == "mate_return_alloc_override_test"))
        .join(cpg.MemoryLocation, CS.points_to)
        .join(DL, cpg.MemoryLocation.may_alias)
        .with_entities(DL)
        .all()
    )

    neg = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_return_alloc_override_test_neg"))
        .one()
    )
    assert len(neg.points_to) == 1 and neg.points_to[0].pretty_string == "nil*null*"


def test_pts_signature_return_alloc_once(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "signatures.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
        build_options=dict(
            pointer_analysis=PointerAnalysis.DEBUG,
            signatures=load_signatures(_ASSETS / "signatures.yml"),
        ),
    )
    check_signature_links(cpg, session)

    pos = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_return_alloc_once_test"))
        .all()
    )
    assert len(pos) == 2

    points_to0 = pos[0].points_to
    points_to1 = pos[1].points_to

    assert len(points_to0) > 0
    assert len(points_to1) > 0
    assert set(points_to0) == set(points_to1)

    neg = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_return_alloc_once_test_neg"))
        .one()
    )
    assert len(neg.points_to) == 0


def test_pts_signature_return_aliases_arg(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "signatures.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
        build_options=dict(
            pointer_analysis=PointerAnalysis.DEBUG,
            signatures=load_signatures(_ASSETS / "signatures.yml"),
        ),
    )
    check_signature_links(cpg, session)

    pos = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_return_aliases_arg_test"))
        .one()
    )
    assert len(pos.points_to) > 0
    assert len(pos.argument1.points_to) > 0
    assert len(pos.argument2.points_to) > 0
    assert len(set(pos.points_to).intersection(set(pos.argument1.points_to))) > 0
    assert len(set(pos.points_to).intersection(set(pos.argument2.points_to))) == 0

    neg = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_return_aliases_arg_test_neg"))
        .one()
    )
    assert len(neg.points_to) == 0

    CS = aliased(cpg.CallSite)
    DL = aliased(cpg.MemoryLocation)
    A = aliased(cpg.Instruction)
    arg = (
        session.query(CS)
        .filter(CS.callees.any(cpg.Function.name == "mate_return_aliases_arg_test_neg"))
        .join(A, CS.argument1)
        .join(DL, A.points_to)
        .one()
    )
    negarg = (
        session.query(CS)
        .filter(CS.callees.any(cpg.Function.name == "mate_return_aliases_arg_test_neg"))
        .join(A, CS.argument2)
        .join(DL, A.points_to)
        .one()
    )
    reachable = (
        db.PathBuilder()
        .starting_at(lambda Node: Node.uuid == arg.uuid)
        .continuing_while(lambda _, Edge: Edge.kind == EdgeKind.DATAFLOW_SIGNATURE)
        .build(cpg.dfg, keep_start=False)
    )
    assert session.query(reachable).filter_by(target=negarg.uuid).count() == 1


def get_reachable_pointers(inst):
    reachable = set(inst.points_to)
    to_visit = [p for p in inst.points_to if p.alias_set_identifier != "*null*"]

    while len(to_visit) > 0:
        cur = to_visit.pop()
        for l in itertools.chain(cur.may_alias, cur.subregions):
            if l not in reachable and l.alias_set_identifier != "*null*":
                reachable.add(l)
                to_visit.append(l)
            for p in l.points_to:
                if p not in reachable and p.alias_set_identifier != "*null*":
                    reachable.add(p)
                    to_visit.append(p)

    return reachable


def test_pts_signature_return_aliases_arg_reachable(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "signatures.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
        build_options=dict(
            pointer_analysis=PointerAnalysis.DEBUG,
            signatures=load_signatures(_ASSETS / "signatures.yml"),
        ),
    )
    check_signature_links(cpg, session)

    pos = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_return_points_to_global_test"))
        .one()
    )
    assert len(pos.points_to) > 0

    neg = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_return_points_to_global_test_neg"))
        .one()
    )
    assert len(neg.points_to) == 0


def test_pts_signature_return_aliases_global(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "signatures.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
        build_options=dict(
            pointer_analysis=PointerAnalysis.DEBUG,
            signatures=load_signatures(_ASSETS / "signatures.yml"),
        ),
    )
    check_signature_links(cpg, session)

    pos = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_return_aliases_global_test"))
        .one()
    )
    assert len(pos.points_to) > 0
    assert len([p for p in pos.points_to if "global_struct" in p.attributes["pretty_string"]]) > 0

    neg = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_return_aliases_global_test_neg"))
        .one()
    )
    assert len(neg.points_to) == 0


def test_pts_signature_return_aliases_global_reachable(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "signatures.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
        build_options=dict(
            pointer_analysis=PointerAnalysis.DEBUG,
            signatures=load_signatures(_ASSETS / "signatures.yml"),
        ),
    )
    check_signature_links(cpg, session)

    pos = (
        session.query(cpg.Call)
        .filter(
            cpg.Call.callees.any(cpg.Function.name == "mate_return_aliases_global_reachable_test")
        )
        .one()
    )
    assert len(pos.points_to) > 0
    assert len([p for p in pos.points_to if "global_int" in p.attributes["pretty_string"]]) > 0

    neg = (
        session.query(cpg.Call)
        .filter(
            cpg.Call.callees.any(
                cpg.Function.name == "mate_return_aliases_global_reachable_test_neg"
            )
        )
        .one()
    )
    assert len(neg.points_to) == 0


def test_pts_signature_arg_alloc(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "signatures.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
        build_options=dict(
            pointer_analysis=PointerAnalysis.DEBUG,
            signatures=load_signatures(_ASSETS / "signatures.yml"),
        ),
    )
    check_signature_links(cpg, session)

    pos = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_arg_alloc_test"))
        .all()
    )
    assert len(pos) == 2

    points_to0 = [l for p in pos[0].argument0.points_to for l in p.points_to]
    points_to1 = [l for p in pos[1].argument0.points_to for l in p.points_to]

    assert len(points_to0) > 0
    assert len(points_to1) > 0
    assert len(set(points_to0).intersection(set(points_to1))) == 0

    neg = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_arg_alloc_test_neg"))
        .one()
    )
    neg_points_to = [l for p in neg.argument0.points_to for l in p.points_to]
    assert len(neg_points_to) == 0


def test_pts_signature_arg_alloc_once(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "signatures.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
        build_options=dict(
            pointer_analysis=PointerAnalysis.DEBUG,
            signatures=load_signatures(_ASSETS / "signatures.yml"),
        ),
    )
    check_signature_links(cpg, session)

    pos = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_arg_alloc_once_test"))
        .all()
    )
    assert len(pos) == 2

    points_to0 = [l for p in pos[0].argument0.points_to for l in p.points_to]
    points_to1 = [l for p in pos[1].argument0.points_to for l in p.points_to]

    assert len(points_to0) > 0
    assert len(points_to1) > 0
    assert set(points_to0) == set(points_to1)

    neg = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_arg_alloc_once_test_neg"))
        .one()
    )
    neg_points_to = [l for p in neg.argument0.points_to for l in p.points_to]
    assert len(neg_points_to) == 0


def test_pts_signature_arg_memcpy_arg(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "signatures.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
        build_options=dict(
            pointer_analysis=PointerAnalysis.DEBUG,
            signatures=load_signatures(_ASSETS / "signatures.yml"),
        ),
    )
    check_signature_links(cpg, session)

    pos = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_arg_memcpy_arg_test"))
        .one()
    )

    points_to0 = set()
    for p in pos.argument0.points_to:
        for l in p.points_to:
            points_to0.add(l)

    points_to1 = set()
    for p in pos.argument1.points_to:
        for l in p.points_to:
            points_to1.add(l)

    assert points_to0 > points_to1
    assert not (points_to1 >= points_to0)

    neg = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_arg_memcpy_arg_test_neg"))
        .one()
    )

    neg_points_to0 = set()
    for p in neg.argument0.points_to:
        for l in p.points_to:
            neg_points_to0.add(l)

    neg_points_to1 = set()
    for p in pos.argument1.points_to:
        for l in p.points_to:
            neg_points_to1.add(l)

    assert not (neg_points_to0 >= neg_points_to1)
    assert not (neg_points_to1 >= neg_points_to0)


def test_pts_signature_arg_memcpy_arg_reachable(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "signatures.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
        build_options=dict(
            pointer_analysis=PointerAnalysis.DEBUG,
            signatures=load_signatures(_ASSETS / "signatures.yml"),
        ),
    )
    check_signature_links(cpg, session)

    pos = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_arg_memcpy_arg_reachable_test"))
        .one()
    )

    points_to0 = set()
    for p in pos.argument0.points_to:
        for l in p.points_to:
            points_to0.add(l)

    points_to1 = set()
    for p in pos.argument1.points_to:
        for l in p.points_to:
            for i in l.points_to:
                points_to1.add(i)

    assert points_to0 > points_to1
    assert not (points_to1 >= points_to0)

    neg = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_arg_memcpy_arg_reachable_test_neg"))
        .one()
    )

    neg_points_to0 = set()
    for p in neg.argument0.points_to:
        for l in p.points_to:
            neg_points_to0.add(l)

    neg_points_to1 = set()
    for p in pos.argument1.points_to:
        for l in p.points_to:
            for i in l.points_to:
                neg_points_to1.add(i)

    assert not (neg_points_to0 >= neg_points_to1)
    assert not (neg_points_to1 >= neg_points_to0)


def test_pts_signature_arg_points_to_global(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "signatures.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
        build_options=dict(
            pointer_analysis=PointerAnalysis.DEBUG,
            signatures=load_signatures(_ASSETS / "signatures.yml"),
        ),
    )
    check_signature_links(cpg, session)

    pos = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_arg_points_to_global_test"))
        .one()
    )

    points_to = set()
    for p in pos.argument0.points_to:
        for l in p.points_to:
            points_to.add(l)

    assert len(points_to) > 0
    assert len([p for p in points_to if "global_int" in p.attributes["pretty_string"]]) > 0

    neg = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_arg_points_to_global_test_neg"))
        .one()
    )

    neg_points_to = set()
    for p in neg.argument0.points_to:
        for l in p.points_to:
            neg_points_to.add(l)

    assert len(neg_points_to) > 0
    assert len([p for p in neg_points_to if "global_int" in p.attributes["pretty_string"]]) == 0


def test_pts_signature_arg_memcpy_global(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "signatures.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
        build_options=dict(
            pointer_analysis=PointerAnalysis.DEBUG,
            signatures=load_signatures(_ASSETS / "signatures.yml"),
        ),
    )
    check_signature_links(cpg, session)

    pos = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_arg_memcpy_global_test"))
        .one()
    )

    points_to = set()
    for p in pos.argument0.points_to:
        for m in p.may_alias:
            for l in m.points_to:
                points_to.add(l)

    assert len(points_to) > 0
    assert len([p for p in points_to if "global_int" in p.attributes["pretty_string"]]) > 0

    neg = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_arg_memcpy_global_test_neg"))
        .one()
    )

    neg_points_to = set()
    for p in neg.argument0.points_to:
        for m in p.may_alias:
            for l in m.points_to:
                neg_points_to.add(l)

    assert len([p for p in neg_points_to if "global_int" in p.attributes["pretty_string"]]) == 0


def test_pts_signature_arg_memcpy_global_reachable(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "signatures.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
        build_options=dict(
            pointer_analysis=PointerAnalysis.DEBUG,
            signatures=load_signatures(_ASSETS / "signatures.yml"),
        ),
    )
    check_signature_links(cpg, session)

    pos = (
        session.query(cpg.Call)
        .filter(cpg.Call.callees.any(cpg.Function.name == "mate_arg_memcpy_global_reachable_test"))
        .one()
    )

    points_to = set()
    for p in pos.argument0.points_to:
        for l in p.points_to:
            points_to.add(l)

    assert len(points_to) > 0
    assert len([p for p in points_to if "global_int" in p.attributes["pretty_string"]]) > 0

    neg = (
        session.query(cpg.Call)
        .filter(
            cpg.Call.callees.any(cpg.Function.name == "mate_arg_memcpy_global_reachable_test_neg")
        )
        .one()
    )

    neg_points_to = set()
    for p in neg.argument0.points_to:
        for l in p.points_to:
            neg_points_to.add(l)

    assert len([p for p in neg_points_to if "global_int" in p.attributes["pretty_string"]]) == 0


def test_signature_tags(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "signatures.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
        build_options=dict(
            pointer_analysis=PointerAnalysis.DEBUG,
            signatures=load_signatures(_ASSETS / "signatures.yml"),
        ),
    )
    check_signature_links(cpg, session)
    assert (
        session.query(cpg.InputSignature).filter(cpg.InputSignature.tags == ["test_input"]).count()
        == 2
    )
    # TODO(sm): better handling of multiple tags using postgres JSON features
    # assert (
    #     cpg.query(cpg.DataflowSignature).filter(cpg.DataflowSignature.tags == ["test1","test2"]).count() == 1
    # )


def test_dynamic_signatures(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "signatures.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
        build_options=dict(
            pointer_analysis=PointerAnalysis.DEBUG,
            signatures=load_signatures(_ASSETS / "signatures.yml"),
        ),
    )
    build = session.query(db.Build).get(cpg.build)

    check_signature_links(cpg, session)

    CS = aliased(cpg.CallSite)
    DS = aliased(cpg.DataflowSignature)
    IS = aliased(cpg.InputSignature)
    OS = aliased(cpg.OutputSignature)
    N = aliased(cpg.Node)
    DL = aliased(cpg.MemoryLocation)
    A = aliased(cpg.Instruction)

    assert session.query(DS).count() == 1  # one callsite of mate_return_aliases_arg_test_neg
    assert (
        session.query(IS).count() == 4
    )  # two callsites each of mate_return_alloc_test and mate_return_alloc_override_test
    assert session.query(OS).count() == 0

    with pytest.raises(signatures.InvalidSignature):
        signatures.parse_input_signature(
            "mate_return_alloc_once_test", {"to": [{"return_reachable": ["bad"]}]}
        )

    with pytest.raises(signatures.InvalidSignature):
        signatures.parse_output_signature(
            "mate_return_alloc_once_test", {"from": [{"return_foo": ["bad"]}]}
        )

    with pytest.raises(signatures.InvalidSignature):
        signatures.parse_dataflow_signature(
            "mate_return_alloc_once_test", [{"to": []}, {"from": []}]
        )

    sig = signatures.parse_input_signature(
        "mate_return_alloc_once_test", {"to": [{"return_reachable": []}]}
    )
    sig.apply_to_cpg(build, cpg, session)
    assert set(
        session.query(CS)
        .filter(CS.callees.any(cpg.Function.name == "mate_return_alloc_once_test"))
        .join(IS, CS.input_signatures)
        .join(N, IS.flows_to)
        .with_entities(N)
        .all()
    ) == set(
        session.query(CS)
        .filter(CS.callees.any(cpg.Function.name == "mate_return_alloc_once_test"))
        .join(cpg.MemoryLocation, CS.points_to)
        .join(DL, cpg.MemoryLocation.may_alias)
        .with_entities(DL)
        .all()
    )
    before_count = session.query(cpg.InputSignature).count()

    sig = signatures.parse_input_signature(
        "mate_return_alloc_once_test", {"to": [{"return_reachable": []}]}
    )
    sig.apply_to_cpg(build, cpg, session)
    assert before_count == session.query(cpg.InputSignature).count()

    sig = signatures.parse_output_signature(
        "mate_return_aliases_arg_test", {"from": [{"arg_points_to": [1]}]}
    )
    sig.apply_to_cpg(build, cpg, session)
    assert set(
        session.query(CS)
        .filter(CS.callees.any(cpg.Function.name == "mate_return_aliases_arg_test"))
        .join(OS, CS.output_signatures)
        .join(N, OS.flows_from)
        .with_entities(N)
        .all()
    ) == set(
        session.query(CS)
        .filter(CS.callees.any(cpg.Function.name == "mate_return_aliases_arg_test"))
        .join(A, CS.argument1)
        .join(cpg.MemoryLocation, A.points_to)
        .join(DL, cpg.MemoryLocation.may_alias)
        .with_entities(DL)
        .all()
    )
    before_count = session.query(cpg.OutputSignature).count()
    sig = signatures.parse_output_signature(
        "mate_return_aliases_arg_test", {"from": [{"arg_points_to": [1]}]}
    )
    sig.apply_to_cpg(build, cpg, session)
    assert before_count == session.query(cpg.OutputSignature).count()

    sig = signatures.parse_dataflow_signature(
        "mate_return_aliases_arg_test",
        {"from": {"direct": [{"arg_points_to": [1]}]}, "to": [{"arg_points_to": [2]}]},
    )
    sig.apply_to_cpg(build, cpg, session)
    before_count = session.query(cpg.DataflowSignature).count()
    sig = signatures.parse_dataflow_signature(
        "mate_return_aliases_arg_test",
        {"from": {"direct": [{"arg_points_to": [1]}]}, "to": [{"arg_points_to": [2]}]},
    )
    sig.apply_to_cpg(build, cpg, session)
    assert before_count == session.query(cpg.DataflowSignature).count()

    arg = (
        session.query(CS)
        .filter(CS.callees.any(cpg.Function.name == "mate_return_aliases_arg_test"))
        .join(A, CS.argument1)
        .join(DL, A.points_to)
        .one()
    )
    negarg = (
        session.query(CS)
        .filter(CS.callees.any(cpg.Function.name == "mate_return_aliases_arg_test"))
        .join(A, CS.argument2)
        .join(DL, A.points_to)
        .one()
    )
    reachable = (
        db.PathBuilder()
        .starting_at(lambda Node: Node.uuid == arg.uuid)
        .continuing_while(lambda _, Edge: Edge.kind == EdgeKind.DATAFLOW_SIGNATURE)
        .build(cpg.dfg, keep_start=False)
    )
    assert session.query(reachable).filter_by(target=negarg.uuid).count() == 1

    sig = signatures.parse_output_signature(
        "mate_return_aliases_arg_reachable_test", {"from": [{"arg_reachable": [2]}]}
    )
    sig.apply_to_cpg(build, cpg, session)

    call = (
        session.query(cpg.CallSite)
        .filter(cpg.CallSite.calls("mate_return_aliases_arg_reachable_test"))
        .one()
    )

    reachable = get_reachable_pointers(call.argument2)

    query = set(
        session.query(CS)
        .filter(CS.callees.any(cpg.Function.name == "mate_return_aliases_arg_reachable_test"))
        .join(OS, CS.output_signatures)
        .join(N, OS.flows_from)
        .with_entities(N)
        .all()
    )
    assert reachable == query
    check_signature_links(cpg, session)


def test_df_sig_arg_to_ret(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "df-sig-arg-to-ret.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
        build_options=dict(
            signatures=load_signatures(_ASSETS / "df-sig-arg-to-ret.yml"),
        ),
    )
    check_signature_links(cpg, session)
    main = session.query(cpg.Function).filter_by(name="main").one()
    argc = (
        session.query(cpg.Argument)
        .filter(cpg.Argument.argument_number == 0, cpg.Argument.parent_function == main)
        .one()
    )
    ret = session.query(cpg.Ret).one()
    op = aliased(cpg.Node)
    ret_op = (
        session.query(op)
        .join(cpg.Edge, cpg.Edge.source == op.uuid)
        .filter(cpg.Edge.kind == EdgeKind.VALUE_DEFINITION_TO_USE, cpg.Edge.target == ret.uuid)
        .one()
    )

    df = (
        db.PathBuilder(CSThinDataflowPath)
        .starting_at(lambda Node: Node.uuid == argc.uuid)
        .build(cpg, keep_start=False)
    )
    assert ret_op.uuid in list(
        node_id for (node_id,) in session.query(df).with_entities(df.target).all()
    )


def test_df_sig_arg_to_arg_pts(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "df-sig-arg-to-arg-pts.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
        build_options=dict(
            signatures=load_signatures(_ASSETS / "df-sig-arg-to-arg-pts.yml"),
        ),
    )
    check_signature_links(cpg, session)
    main = session.query(cpg.Function).filter_by(name="main").one()
    argc = (
        session.query(cpg.Argument)
        .filter(cpg.Argument.argument_number == 0, cpg.Argument.parent_function == main)
        .one()
    )
    df = (
        db.PathBuilder(CSThinDataflowPath)
        .starting_at(lambda Node: Node.uuid == argc.uuid)
        .build(cpg, keep_start=False)
    )
    mems = (
        session.query(df)
        .join(cpg.MemoryLocation, cpg.MemoryLocation.uuid == df.target)
        .with_entities(cpg.MemoryLocation)
        .all()
    )
    assert len(mems) == 2


def test_df_sig_arg_to_arg_pts_agg(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "df-sig-arg-to-arg-pts-agg.c",
        compile_options=dict(extra_compiler_flags=optimization_flags),
        build_options=dict(
            signatures=load_signatures(_ASSETS / "df-sig-arg-to-arg-pts-agg.yml"),
        ),
    )
    check_signature_links(cpg, session)
    main = session.query(cpg.Function).filter_by(name="main").one()
    argc = (
        session.query(cpg.Argument)
        .filter(cpg.Argument.argument_number == 0, cpg.Argument.parent_function == main)
        .one()
    )
    df = (
        db.PathBuilder(CSThinDataflowPath)
        .starting_at(lambda Node: Node.uuid == argc.uuid)
        .build(cpg, keep_start=False)
    )
    mems = (
        session.query(df)
        .join(cpg.MemoryLocation, cpg.MemoryLocation.uuid == df.target)
        .with_entities(cpg.MemoryLocation)
        .all()
    )
    if optimization_flags == ("-O0",):
        assert len(mems) == 4
    else:
        assert len(mems) == 3
