"""Naive constant folding for the DWARFv4 expression language AST.

TODO: Boolean logic?
"""

import operator
from enum import Enum
from typing import List, Optional

from .ast import DwarfInstr, const_to_int
from .enums import CONSTANTS, DW_OP, breg_num, lit_num, reg_num, reg_to_breg


class Op(Enum):
    ADD = operator.__add__
    SUB = operator.__sub__


def _lit_or_const_to_int(instr: DwarfInstr) -> Optional[int]:
    lit_n = lit_num(instr.opcode)
    if lit_n is not None:
        return lit_n
    const_n = const_to_int(instr)
    if const_n is not None:
        return const_n
    return None


def _can_const_arith(opcode1: DW_OP, opcode2: DW_OP) -> bool:
    """Can we do some constant folding with arithmetic on these?"""
    is_const_1 = lit_num(opcode1) is not None or opcode1 in CONSTANTS
    is_const_2 = lit_num(opcode2) is not None or opcode2 in CONSTANTS
    is_reg_1 = (
        breg_num(opcode1) is not None or reg_num(opcode1) is not None or opcode1 == DW_OP.FBREG
    )
    is_reg_2 = (
        breg_num(opcode2) is not None or reg_num(opcode2) is not None or opcode2 == DW_OP.FBREG
    )
    return (is_const_1 and (is_const_2 or is_reg_2)) or (is_const_2 and is_reg_1)


def _op_lit_or_const_breg(op: Op, lit_or_const: DwarfInstr, breg_instr: DwarfInstr) -> DwarfInstr:
    """Operate on a ``DW_OP_(lit.|const.+)`` and a ``DW_OP_breg*``"""
    assert breg_num(breg_instr.opcode) is not None
    assert len(breg_instr.args) == 1
    n = _lit_or_const_to_int(lit_or_const)
    breg_instr.args[0] = op.value(breg_instr.args[0], n)
    return breg_instr


def _op_lit_or_const_reg(op: Op, lit_or_const: DwarfInstr, reg_instr: DwarfInstr) -> DwarfInstr:
    """Operate on a ``DW_OP_lit*`` and ``DW_OP_reg*``, get a ``DW_OP_breg*``"""
    n = _lit_or_const_to_int(lit_or_const)
    assert reg_num(reg_instr.opcode) is not None
    assert n is not None
    assert len(reg_instr.args) == 0
    breg_op = reg_to_breg(reg_instr.opcode)
    if op is Op.ADD:
        return DwarfInstr(breg_op, [n])
    return DwarfInstr(breg_op, [-n])


def _const_op(op: Op, instr1: DwarfInstr, instr2: DwarfInstr) -> Optional[DwarfInstr]:
    n1 = _lit_or_const_to_int(instr1)
    n2 = _lit_or_const_to_int(instr2)

    # Both constants:
    if n1 is not None and n2 is not None:
        # Conservatively return a signed number. Might change later.
        return DwarfInstr(DW_OP.CONSTS, [op.value(n1, n2)])

    elif n1 is not None and (breg_num(instr2.opcode) is not None or instr2.opcode == DW_OP.FBREG):
        return _op_lit_or_const_breg(op, instr1, instr2)

    elif n2 is not None and (breg_num(instr1.opcode) is not None or instr1.opcode == DW_OP.FBREG):
        return _op_lit_or_const_breg(op, instr2, instr1)

    elif n1 is not None and reg_num(instr2.opcode) is not None:
        return _op_lit_or_const_reg(op, instr1, instr2)

    elif n2 is not None and reg_num(instr1.opcode) is not None:
        return _op_lit_or_const_reg(op, instr2, instr1)

    return None


def _const_add(instr1: DwarfInstr, instr2: DwarfInstr) -> Optional[DwarfInstr]:
    return _const_op(Op.ADD, instr1, instr2)


def _const_sub(instr1: DwarfInstr, instr2: DwarfInstr) -> Optional[DwarfInstr]:
    return _const_op(Op.SUB, instr1, instr2)


def constant_fold(instructions: List[DwarfInstr]) -> List[DwarfInstr]:
    """Naive constant folding for the DWARFv4 expression language AST.

    TODO: Apply local folds in a sliding window
    """
    if len(instructions) == 3:
        (instr1, instr2, operation) = instructions
        if _can_const_arith(instr1.opcode, instr2.opcode):
            if operation.opcode == DW_OP.PLUS:
                added = _const_add(instr1, instr2)
                if added is not None:
                    return [added]
            elif operation.opcode == DW_OP.MINUS:
                minused = _const_sub(instr1, instr2)
                if minused is not None:
                    return [minused]
    return instructions
