"""Test several CPG invariants.

TODO: It would be nice to also test that our enums don't have any extra
entries, or similarly, that each edge kind really does go between all of it's
endpoint node kinds. How can we do this when every enum value might not appear
in every program?
"""
from sqlalchemy.orm import aliased
from sqlalchemy.sql.functions import count

from mate_common.models.builds import PointerAnalysis
from mate_common.models.cpg_types import (
    EDGE_KINDS,
    LLVM_INTRINSIC_IDS,
    LLVM_OPCODES,
    NODE_JSON,
    EdgeKind,
    NodeJSON,
    NodeKind,
    Relationship,
)
from mate_common.schemata import ENDPOINTS, RELATIONSHIPS


def unique(session, cls, compare):
    cls2 = aliased(cls)
    assert (session.query(cls, cls2).filter(cls.uuid != cls2.uuid, compare(cls, cls2)).count()) == 0


def unique_projection(session, cls, project):
    unique(session, cls, lambda n1, n2: project(n1) == project(n2))


def test_invariants(session, cpg_db_v2, every_program):
    (program, cflags) = every_program
    cpg = cpg_db_v2(
        program,
        compile_options=dict(extra_compiler_flags=cflags),
        build_options=dict(
            machine_code_mapping=True,
            do_pointer_analysis=True,
            # When MATE_ASSERTIONS=1, check pointer analysis assertions
            pointer_analysis=PointerAnalysis.DEBUG,
            control_dependence=True,
        ),
    )

    # Each CPG has exactly one LLVM module.
    session.query(cpg.Module).one()

    for edge in session.query(cpg.Edge).all():
        assert edge.kind.value in EDGE_KINDS
        specs = ENDPOINTS.get(edge.kind)
        assert specs is not None

        assert [
            spec
            for spec in specs
            if NodeKind(edge.source_node.kind.value) in spec.sources
            and NodeKind(edge.target_node.kind.value) in spec.targets
        ] != [], f"{edge.source_node.kind}, {edge.target_node.kind} is not a valid source, target pair for for {edge.kind} edges"

    for node in session.query(cpg.Node).all():
        assert type(repr(node)) is str
        for k in node.attributes.keys():
            assert k in NODE_JSON
            if k == NodeJSON.INTRINSIC.value:
                assert node.attributes[k] in LLVM_INTRINSIC_IDS

            # NOTE(ww): MachineInstr nodes have an "opcode" attribute that's numeric
            # and represents a middle-end opcode, so don't check it against the known
            # LLVM opcodes.
            if k == NodeJSON.OPCODE.value and node.kind != NodeKind.MACHINE_INSTR:
                assert node.attributes[k] in LLVM_OPCODES

    # Each attribute in the JSON blob should have a getter, e.g. our JSON
    # schemata (which the hybrid properties are generated from) should list
    # every attribute.

    for node in session.query(cpg.Node).all():
        # Currently, we only do this for nodes for which we have more
        # specialized model classes than just 'cpg.Node'.
        if node.__class__ != cpg.Node:
            for k in node.attributes.keys():
                if k == "node_kind":
                    continue
                # The `DataflowSignature` node has an optional `deallocator` attribute. A `None`
                # value means that the signature is not for an allocator function and therefore, has
                # no corresponding deallocator function.
                if k == "deallocator":
                    continue
                # Not every node has source code associated with it
                if k == "source_code":
                    continue
                attr = getattr(node, k, None)
                assert attr is not None, f"{k} should be non-null for {node.__class__}"
                assert not callable(attr)  # not a method
                assert getattr(node.__class__, k, None) is not None

    # Relations should respect their specs, e.g. every one-to-one edge should
    # have exactly one endpoint on either side.

    for edge in session.query(cpg.Edge).all():

        if edge.kind == EdgeKind.CALL_RETURN_TO_CALLER:
            continue  # TODO(lb): bug?

        rel = RELATIONSHIPS.get(edge.kind)
        assert rel is not None
        if rel in [Relationship.ONE_TO_ONE, Relationship.ONE_TO_MANY]:
            assert {edge} == {e for e in edge.target_node.incoming if e.kind == edge.kind}
        if rel in [Relationship.ONE_TO_ONE, Relationship.MANY_TO_ONE]:
            assert {edge} == {e for e in edge.source_node.outgoing if e.kind == edge.kind}

    # For most edge kinds, there should only be one edge of that kind between the same
    # source and target nodes. The exception is edge kinds where there is an edge for
    # each context in which the edge is relevant.
    cpg.Edge2 = aliased(cpg.Edge)
    es = (
        session.query(cpg.Edge, cpg.Edge2)
        .join(
            cpg.Edge2,
            (
                (cpg.Edge.uuid != cpg.Edge2.uuid)
                & (cpg.Edge.source == cpg.Edge2.source)
                & (cpg.Edge.target == cpg.Edge2.target)
                & (cpg.Edge.kind == cpg.Edge2.kind)
                & (
                    cpg.Edge.attributes["context"].as_string()
                    == cpg.Edge2.attributes["context"].as_string()
                )
                & (
                    cpg.Edge.attributes["caller_context"].as_string()
                    == cpg.Edge2.attributes["caller_context"].as_string()
                )
                & (
                    cpg.Edge.attributes["callee_context"].as_string()
                    == cpg.Edge2.attributes["callee_context"].as_string()
                )
            ),
        )
        .first()
    )
    assert es is None, "\n".join([f"Duplicate edges", str(es[0]), str(es[1])])

    # Every function should have one cpg.Argument node for each of its arguments

    Arg = aliased(cpg.Argument)

    # NOTE(lb): Postgres won't allow this query to extract the Function
    # in it's entirety, which is why we grab the ID.
    for (function_id, nargs) in (
        session.query(cpg.Function.uuid, count(Arg.uuid))
        .join(Arg, cpg.Function.arguments)
        .group_by(cpg.Function.uuid)
        .all()
    ):
        if nargs > 0:
            assert (
                nargs
                == max(
                    arg.argument_number
                    for arg in session.query(cpg.Function).get(function_id).arguments
                )
                + 1
            )

    # Functions, globals have unique names

    unique_projection(session, cpg.Function, lambda f: f.name)
    unique_projection(session, cpg.GlobalVariable, lambda g: g.name)

    # Every LLVM block should have a list of MI blocks that are successors of
    # one another.

    for block in session.query(cpg.Block).all():
        assert len(block.sorted_mi_blocks()) == len(block.mi_blocks)

    # Every cpg.MemoryLocation should have a unique ID
    unique_projection(
        session, cpg.MemoryLocation, lambda m: m.attributes["pretty_string"].as_string()
    )

    for location in session.query(cpg.MemoryLocation).yield_per(1000):
        may_alias = set(location.may_alias)
        assert may_alias.issuperset(set(location.must_alias))

    # CallSites should be the disjoint union of Calls and Invokes
    assert session.query(cpg.CallSite).count() == (
        session.query(cpg.Call).count() + session.query(cpg.Invoke).count()
    )

    for mf in session.query(cpg.MachineFunction).all():
        # Every function has exactly zero or one prologues.
        assert len(mf.prologues) <= 1

        # For each prologue: the prologue starts no earlier than
        # the beginning of the function, and ends no later than the
        # end of the function. Each prologue range is also
        # internally consistent.
        for (prologue_begin, prologue_end) in mf.prologues:
            assert prologue_begin <= prologue_end
            assert prologue_begin >= mf.va_start
            assert prologue_end <= mf.va_end

        # Similarly for each epilogue.
        for (epilogue_begin, epilogue_end) in mf.epilogues:
            assert epilogue_begin <= epilogue_end
            assert epilogue_begin >= mf.va_start
            assert epilogue_end <= mf.va_end

    # Every instruction should have a predecessor unless it is the first instruction in
    # - a function-entry block
    # - an unreachable block (block with no predecessors)
    for inst in (
        session.query(cpg.Instruction)
        .filter(
            ~cpg.Instruction.incoming.any(
                cpg.Edge.kind == EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION
            )
        )
        .all()
    ):
        assert inst.uuid == inst.parent_block.entry.uuid and not any(
            edge.kind == EdgeKind.BLOCK_TO_SUCCESSOR_BLOCK for edge in inst.parent_block.incoming
        )

    # Every ASM instruction fits within its enclosing basic block and has a
    # reasonable size (1 to 15 bytes)
    for inst in session.query(cpg.ASMInst).all():
        asm_block = inst.asm_block
        assert inst.va >= asm_block.va
        assert inst.va < asm_block.va_end

        assert 15 >= inst.size >= 1

    # Every vtable references machine functions and PLT stubs, but never both
    # for the same member
    for vtable in session.query(cpg.VTable).all():
        mf_vas = {mf.va_start for mf in vtable.machine_functions}
        stub_vas = {stub.va for stub in vtable.plt_stubs}

        assert mf_vas.isdisjoint(stub_vas)

    # If a MachineFunction has a dwarf_type it should be a subroutine type
    for mi_func in session.query(cpg.MachineFunction).all():
        if mi_func.dwarf_type:
            assert mi_func.dwarf_type.kind == NodeKind.SUBROUTINE_TYPE

    # Number of Variables should equal num arguments + local vars + global vars
    variables = session.query(cpg.Variable).all()
    assert len(variables) == sum(
        session.query(cls).count() for cls in [cpg.Argument, cpg.LocalVariable, cpg.GlobalVariable]
    )

    # All Variables should have an llvm_type and memory_locations attribtue
    for var in variables:
        assert hasattr(var, "llvm_type")
        assert hasattr(var, "memory_locations")
        # NOTE(brad): GlobalVariables are not allocated by Allocas, so do not have allocation_site
        if var.kind in [NodeKind.ARGUMENT, NodeKind.LOCAL_VARIABLE]:
            # NOTE(brad): In a few cases some Variables are not linked with an Alloca
            if var.allocation_site:
                assert var.allocation_site.kind == NodeKind.ALLOCA
                assert var.allocation_site.variable.uuid == var.uuid
                assert var.allocation_site.allocates == var.memory_locations

    # TODO(lb): Every call to `malloc` should have an outgoing points-to edge
