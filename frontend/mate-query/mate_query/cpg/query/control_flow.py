from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

from smt2lib.SMTLIBv2Parser import SMTLIBv2Parser

from mate_common.models.integration import (
    Addr,
    Assertion,
    Constraint,
    Register,
    SMTIdentifier,
    Waypoint,
)

if TYPE_CHECKING:
    from typing import Any, Iterable, List, Optional

    from sqlalchemy.orm import Session

    from mate_query.cpg.models import Edge, Node
    from mate_query.cpg.models.node.ast.bin import ASMBlock
    from mate_query.cpg.models.node.ast.llvm import Instruction
    from mate_query.db import Graph as CPG
    from mate_query.db import Path


# Replacement token recognized by Manticore
# Remove the surrounding ' characters
SMT_REPLACE_TOK = SMTLIBv2Parser.literalNames[SMTLIBv2Parser.Replace].strip("'")


def _construct_waypoint_for_blocks(
    asm_block: ASMBlock, next_asm_block: Optional[ASMBlock]
) -> Waypoint:
    """Construct a waypoint that should be active during the last instruction in ``asm_block``,
    where ``next_asm_block`` is where control flows next."""
    # TODO: Need mypy support for protobuf to use correct Assertion type
    asserts: List[Any] = []
    va = Addr(va=asm_block.terminator.va)
    if next_asm_block is not None and (
        next_asm_block.mi_block.ir_block.parent_function
        == asm_block.mi_block.ir_block.parent_function
    ):
        # If this is an intra-procedural jump, we know that we are jumping
        # to the beginning of the next block, and constrain the instruction
        # pointer accordingly.
        asserts = [
            Assertion(
                location=va,
                constraint=[
                    Constraint(
                        id=[SMTIdentifier(identifier=Register.RIP)],
                        expr=f"(assert (= {SMT_REPLACE_TOK}0 {next_asm_block.va}))",
                    )
                ],
            )
        ]
    return Waypoint(start=va, end=va, asserts=asserts, replacements=[])


def cfg_path_to_waypoints(cpg: CPG, session: Session, cfg_path: Path) -> Iterable[Waypoint]:
    (instrs1, instrs2) = itertools.tee(cfg_path_to_instructions(cpg, session, cfg_path))
    next(instrs2)
    for llvm_instr, next_llvm_instr in itertools.zip_longest(instrs1, instrs2):
        llvm_block = llvm_instr.parent_block

        if llvm_instr == llvm_block.terminator:
            mi_blocks = llvm_block.sorted_mi_blocks()
            if len(mi_blocks) <= 0:
                continue
            mi_block = mi_blocks[-1]

            # Skip fall-through blocks, except the last block/instruction on the path
            if mi_block.can_fallthrough and next_llvm_instr is not None:
                continue

            asm_block = mi_block.asm_block

            va = Addr(va=asm_block.terminator.va)
            no_assert = Waypoint(start=va, end=va, asserts=[], replacements=[])
            if next_llvm_instr is None:  # this was the last instruction
                yield no_assert
                continue

            next_mi_blocks = next_llvm_instr.parent_block.sorted_mi_blocks()
            if len(next_mi_blocks) > 0:
                yield _construct_waypoint_for_blocks(asm_block, next_mi_blocks[0].asm_block)
            else:
                yield no_assert

        elif llvm_instr == llvm_block.entry:
            mi_blocks = llvm_block.sorted_mi_blocks()
            if len(mi_blocks) <= 0:
                continue
            asm_block = mi_blocks[0].asm_block

            va = Addr(va=asm_block.va)
            yield Waypoint(start=va, end=va, asserts=[], replacements=[])


def trace_edges(cpg: CPG, session: Session, path: Path) -> Iterable[Edge]:
    return (session.query(cpg.Edge).get(edge_id) for edge_id in path.trace)


def trace_nodes(cpg: CPG, session: Session, cfg_path: Path) -> Iterable[Node]:
    trace = cfg_path.trace
    if len(trace) == 0:
        raise StopIteration
    # Yield the source of the first edge
    yield session.query(cpg.Edge).get(trace[0]).source_node
    # Yield the targets of each edge
    for edge in trace_edges(cpg, session, cfg_path):
        yield edge.target_node


def cfg_path_to_instructions(cpg: CPG, session: Session, cfg_path: Path) -> Iterable[Instruction]:
    """Lower an Instruction-level CFG path in the CPG to VA blocks."""
    for node in trace_nodes(cpg, session, cfg_path):
        if isinstance(node, cpg.Instruction):
            yield node
