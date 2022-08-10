from dwarflang.ast import DwarfInstr
from dwarflang.enums import DW_OP, lookup_DW_OP
from dwarflang.fold import _can_const_arith, _lit_or_const_to_int, constant_fold


def lit(n):
    return DwarfInstr(lookup_DW_OP(f"DW_OP_lit{n}"), [])


def constu(n):
    return DwarfInstr(DW_OP.CONSTU, [n])


def consts(n):
    return DwarfInstr(DW_OP.CONSTS, [n])


def fold(instrs):
    return constant_fold(list(map(lambda x: DwarfInstr(*x), instrs)))


def test_lit_or_const_to_int():
    for n in range(32):
        assert n == _lit_or_const_to_int(lit(n))
        assert n == _lit_or_const_to_int(constu(n))
        assert n == _lit_or_const_to_int(consts(n))


def test_can_const_arith():
    assert _can_const_arith(DW_OP.CONSTU, DW_OP.CONSTU)
    assert _can_const_arith(DW_OP.CONSTS, DW_OP.CONSTS)
    for n in range(32):
        assert _can_const_arith(lit(n).opcode, lit(n).opcode)
        assert _can_const_arith(DW_OP.CONSTU, lit(n).opcode)
        assert _can_const_arith(lit(n).opcode, DW_OP.CONSTS)


def test_constant_fold():
    for n in range(32):
        assert [consts(n)] == fold([consts(n)])
        assert [lit(n)] == fold([lit(n)])

    assert [(DW_OP.REG1, [])] == fold([(DW_OP.REG1, [])])

    assert [consts(5)] == fold([lit(2), lit(3), (DW_OP.PLUS, [])])
    assert [consts(5)] == fold([constu(2), constu(3), (DW_OP.PLUS, [])])
    assert [consts(1)] == fold([consts(-2), constu(3), (DW_OP.PLUS, [])])

    assert [(DW_OP.BREG1, [8])] == fold([lit(8), (DW_OP.REG1, []), (DW_OP.PLUS, [])])
