from elftools.dwarf.structs import DWARFStructs

from dwarflang.ast import DwarfInstr
from dwarflang.enums import DW_OP, lookup_DW_OP
from dwarflang.eval.base import Evaluator

STRUCTS64 = DWARFStructs(little_endian=True, dwarf_format=64, address_size=8, dwarf_version=4)


class Zero(Evaluator):
    """An evaluator that returns zero for every register and memory location."""

    # 2.5.1.1 Literal encodings

    # 2.5.1.2 Register Based Addressing

    def _fbreg(self, _offset):
        self._push(0)

    def _breg(self, n, _offset):
        assert 0 <= n <= 31, f"There is no DW_OP_breg{n} in DWARFv4"
        self._push(0)

    def _bregx(self, _n, _offset):
        self._push(0)

    # 2.5.1.3 Stack Operations

    def _deref(self):
        self._push(0)

    def _deref_size(self, _size):
        self._push(0)

    def _xderef(self):
        self._push(0)

    def _xderef_size(self, _size):
        self._push(0)

    # 2.5.1.4 Arithmetic and Logical Operations

    # 2.5.1.4 Control Flow Operations

    # 2.5.1.6 Special Operations

    # 2.6.1.1.2 Register Location Descriptions

    def _reg(self, n):
        assert 0 <= n <= 31
        self._push(0)

    def _regx(self, _n):
        self._push(0)


def evaluate(zero, stmts):
    zero.eval(map(lambda x: DwarfInstr(*x), stmts))
    return zero.pop()


def test_zero():
    zero = Zero()

    assert 0 == evaluate(zero, [(DW_OP.REG1, [])])
    assert 0 == evaluate(zero, [(DW_OP.BREG1, [10])])
    # assert 0 == evaluate(zero, [["DW_OP_fbreg", 255]])

    def lit(n):
        return (lookup_DW_OP(f"DW_OP_lit{n}"), [])

    for n in range(32):
        assert n == evaluate(zero, [lit(n)])

    assert 5 == evaluate(zero, [lit(2), lit(3), (DW_OP.PLUS, [])])

    # ADDR = [0xFE, 0xED, 0xDE, 0xC1, 0xDE, 0xAB, 0x1E, 0xAA]
    # ADDR_OP = (DW_OP.ADDR, [bytes(chain.from_iterable(ADDR))])
    # assert 12_258_424_208_972_770_814 == evaluate(zero, [ADDR_OP])

    assert 31 == evaluate(zero, [lit(31), (DW_OP.BREGX, [3, 8]), (DW_OP.SWAP, [])])

    assert 30 == evaluate(zero, [lit(30), lit(10), (DW_OP.DROP, [])])

    assert evaluate(zero, [lit(12), (DW_OP.DUP, [])]) == evaluate(
        zero, [lit(12), (DW_OP.PICK, [0])]  # top of the stack has index 0
    )

    assert int(True) == evaluate(zero, [lit(int(True)), lit(int(False)), (DW_OP.OR, [])])
    assert int(False) == evaluate(zero, [lit(int(True)), lit(int(False)), (DW_OP.AND, [])])
    assert int(True) == evaluate(zero, [lit(int(True)), lit(int(False)), (DW_OP.XOR, [])])

    # assert int(True) == evaluate(zero, [[f"DW_OP_lit{12}"], [f"DW_OP_lit{23}"], [f"DW_OP_lt"]])
