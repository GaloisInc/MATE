"""The DWARF expression language AST.

Just a list of ``DwarfInstr``.
"""
from typing import Any, Callable, List, NamedTuple, Optional

from .enums import CONSTANTS, DW_OP, breg_num, lit


class DwarfInstr(NamedTuple):
    opcode: DW_OP
    args: List[Any]


# Modified from pyelftools:
def _generate_dynamic_values(map_, prefix, index_start, index_end, fun=lambda x: x) -> None:  # type: ignore[no-untyped-def]
    for index in range(index_start, index_end + 1):
        name = "%s%s" % (prefix, index)
        map_[name] = fun(index)


# The number of arguments for each DWARFv4 opcode
# See DWARFv4 Figure 24
# TODO: const1u, const1s, ...
ARGS = {
    # 2.5.1.1 Literal encodings
    DW_OP.ADDR: 1,
    # 2.5.1.2 Register Based Addressing
    DW_OP.FBREG: 1,
    DW_OP.BREGX: 2,
    # 2.5.1.3 Stack Operations
    DW_OP.DUP: 0,
    DW_OP.DROP: 0,
    DW_OP.PICK: 1,
    DW_OP.OVER: 0,
    DW_OP.SWAP: 0,
    DW_OP.ROT: 0,
    DW_OP.DEREF: 0,
    DW_OP.DEREF_SIZE: 1,
    DW_OP.XDEREF: 0,
    DW_OP.XDEREF_SIZE: 1,
    DW_OP.PUSH_OBJECT_ADDRESS: 0,
    DW_OP.FORM_TLS_ADDRESS: 0,
    DW_OP.CALL_FRAME_CFA: 0,
    # 2.5.1.4 Arithmetic and Logical Operations
    DW_OP.ABS: 0,
    DW_OP.AND_: 0,
    DW_OP.DIV: 0,
    DW_OP.MINUS: 0,
    DW_OP.MOD: 0,
    DW_OP.MUL: 0,
    DW_OP.NEG: 0,
    DW_OP.NOT_: 0,
    DW_OP.OR_: 0,
    DW_OP.PLUS: 0,
    DW_OP.PLUS_UCONST: 1,
    DW_OP.SHL: 0,
    DW_OP.SHR: 0,
    DW_OP.SHRA: 0,
    DW_OP.XOR: 0,
    # 2.5.1.4 Control Flow Operations
    DW_OP.LE: 0,
    DW_OP.GE: 0,
    DW_OP.EQ: 0,
    DW_OP.LT: 0,
    DW_OP.GT: 0,
    DW_OP.NE: 0,
    DW_OP.SKIP: 1,
    DW_OP.BRA: 1,
    # DW_OP.CALL2: TODO,
    # DW_OP.CALL4: TODO,
    # DW_OP.CALL_REF: TODO,
    # 2.5.1.6 Special Operations
    DW_OP.NOP: 0,
    # 2.6.1.1.2 Register Location Descriptions
    DW_OP.REGX: 1,
    DW_OP.STACK_VALUE: 0,
    DW_OP.IMPLICIT_VALUE: 2,
    # 2.6.1.2 Composite Location Descriptions
    DW_OP.PIECE: 1,
    DW_OP.BIT_PIECE: 2,
}

_generate_dynamic_values(ARGS, "DW_OP_breg", 0, 31, lambda x: 1)
_generate_dynamic_values(ARGS, "DW_OP_reg", 0, 31, lambda x: 0)
_generate_dynamic_values(ARGS, "DW_OP_lit", 0, 31, lambda x: 0)


def check(instr: DwarfInstr) -> None:
    try:
        n = ARGS[instr.opcode]
        l = len(instr.args)
        assert l == n, f"Expected {n} args for {instr.opcode.value}, found {l}"
    except KeyError:
        pass


def instr_to_json(instr: DwarfInstr) -> List[Any]:
    return [instr.opcode.value, instr.args]


def to_json(instructions: List[DwarfInstr]) -> List[Any]:
    return list(map(instr_to_json, instructions))


def replace_instructions(
    instructions: List[DwarfInstr],
    pred: Callable[[DwarfInstr], bool],
    replacement: Callable[[DwarfInstr], List[DwarfInstr]],
) -> List[DwarfInstr]:
    """Find and replace all instructions matching a predicate."""
    to_return: List[DwarfInstr] = []
    for instr in instructions:
        if pred(instr):
            to_return += replacement(instr)
        else:
            to_return.append(instr)
    return to_return


def set_fbreg(
    instructions: List[DwarfInstr], replacement: Callable[[DwarfInstr], List[DwarfInstr]]
) -> List[DwarfInstr]:
    """Replace ``DW_OP_fbreg`` with another expression.

    Function parameters and local variables often have location expressions referring to
    ``DW_OP_fbreg``, which has a value known from their parent DIE. This function can be used to
    replace instances of ``DW_OP_fbreg`` with that known value.
    """
    return replace_instructions(
        instructions, lambda instr: instr.opcode == DW_OP.FBREG, lambda instr: replacement(instr)
    )


def offset_to_int(reg_instr: DwarfInstr) -> int:
    """Get the offset in a ``DW_OP_breg`` or ``DW_OP_fbreg``"""
    assert breg_num(reg_instr.opcode) is not None or reg_instr.opcode == DW_OP.FBREG
    assert len(reg_instr.args) == 1
    return reg_instr.args[0]


def offset_as_lit(reg_instr: DwarfInstr) -> DwarfInstr:
    """Create a ``DW_OP_lit*`` instruction from the offset in ``reg_instr``"""
    return DwarfInstr(lit(offset_to_int(reg_instr)), [])


def const_to_int(instr: DwarfInstr) -> Optional[int]:
    if instr.opcode in CONSTANTS:
        assert len(instr.args) == 1
        return instr.args[0]
    return None
