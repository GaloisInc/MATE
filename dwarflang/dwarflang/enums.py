from enum import Enum, unique
from typing import Any, Dict, List, Optional

from elftools.dwarf.dwarf_expr import DW_OP_name2opcode


@unique
class DwarfRegister(Enum):
    """The variety of DWARF registers."""

    DW_OP_FBREG = "DW_OP_fbreg"
    DW_OP_BREG = "DW_OP_breg"
    DW_OP_BREGX = "DW_OP_bregx"
    DW_OP_REG = "DW_OP_reg"
    DW_OP_REGX = "DW_OP_regx"


def remove_prefix(text: str, prefix: str) -> str:
    if text.startswith(prefix):
        return text[len(prefix) :]
    return text


_DW_OP = Enum(  # type: ignore
    "DW_OP",
    {
        **{remove_prefix(k, "DW_OP_").upper(): k for k in DW_OP_name2opcode.keys()},
        # The following can't be attribute names because they are Python keywords
        "AND_": "DW_OP_and",
        "OR_": "DW_OP_or",
        "NOT_": "DW_OP_not",
        # Recent additions: https://github.com/eliben/pyelftools/commit/7d017b99cffae6d10075f3c9ede83b9762c66f92
        "STACK_VALUE": "DW_OP_stack_value",
        "IMPLICIT_VALUE": "DW_OP_implicit_value",
    },
)
DW_OP: Any = _DW_OP


_CONSTS: List[DW_OP] = [DW_OP.CONST1S, DW_OP.CONST2S, DW_OP.CONST4S, DW_OP.CONST8S]
_CONSTU: List[DW_OP] = [DW_OP.CONST1U, DW_OP.CONST2U, DW_OP.CONST4U, DW_OP.CONST8U]
CONSTANTS: List[DW_OP] = [DW_OP.CONSTS, DW_OP.CONSTU] + _CONSTS + _CONSTU


def _reverse_enum(enu: Enum) -> Dict[str, Enum]:
    return {op.value: op for op in list(enu)}  # type: ignore[call-overload]


_DW_OP_REVERSE = _reverse_enum(DW_OP)


def lookup_DW_OP(name: str) -> Optional[DW_OP]:
    return _DW_OP_REVERSE.get(name)


def lit(n: int) -> Optional[DW_OP]:
    return lookup_DW_OP(f"DW_OP_lit{n}")


def reg(n: int) -> Optional[DW_OP]:
    return lookup_DW_OP(f"DW_OP_reg{n}")


def breg(n: int) -> Optional[DW_OP]:
    return lookup_DW_OP(f"DW_OP_breg{n}")


def lit_num(op: DW_OP) -> Optional[int]:
    if op.value.startswith("DW_OP_lit"):
        return int(op.value[len("DW_OP_lit") :])
    return None


def reg_num(op: DW_OP) -> Optional[int]:
    if op.value.startswith(DwarfRegister.DW_OP_REG.value) and not op.value.startswith(
        DwarfRegister.DW_OP_REGX.value
    ):
        return int(op.value[len(DwarfRegister.DW_OP_REG.value) :])
    return None


def breg_num(op: DW_OP) -> Optional[int]:
    if op.value.startswith(DwarfRegister.DW_OP_BREG.value) and not op.value.startswith(
        DwarfRegister.DW_OP_BREGX.value
    ):
        return int(op.value[len(DwarfRegister.DW_OP_BREG.value) :])
    return None


def reg_to_breg(op: DW_OP) -> Optional[DW_OP]:
    n = reg_num(op)
    if n is not None:
        return breg(n)
    return None


def breg_to_reg(op: DW_OP) -> Optional[DW_OP]:
    n = breg_num(op)
    if n is not None:
        return reg(n)
    return None


# DW_TAG = unique(
#     Enum("DW_TAG", {remove_prefix(k, "DW_TAG_").upper(): k for k in ENUM_DW_TAG.keys()})
# )
