"""An implementation of the DWARFv4 stack machine.

Incomplete parts of the code are marked with ``TODO``, other
``NotImplementedError`` instances are from methods that must be overridden.

See:
 - https://github.com/llvm/llvm-project/blob/master/lldb/packages/Python/lldbsuite/test/lldbdwarf.py#L181
"""
from __future__ import print_function

import operator
from typing import Any, Callable, List, Sequence

from ..ast import DwarfInstr, _generate_dynamic_values, check
from ..enums import DW_OP, breg_num, lit_num, reg_num

# The minimum size of the stack for this operation to make sense
MIN_STACK_SIZE = {
    # 2.5.1.1 Literal encodings
    DW_OP.ADDR.value: 0,
    # 2.5.1.2 Register Based Addressing
    DW_OP.FBREG.value: 0,
    DW_OP.BREGX.value: 0,
    # 2.5.1.3 Stack Operations
    DW_OP.DUP.value: 1,
    DW_OP.DROP.value: 1,
    DW_OP.PICK.value: 1,
    DW_OP.OVER.value: 2,
    DW_OP.SWAP.value: 2,
    DW_OP.ROT.value: 3,
    DW_OP.DEREF.value: 1,
    DW_OP.DEREF_SIZE.value: 1,
    DW_OP.XDEREF.value: 1,
    DW_OP.XDEREF_SIZE.value: 1,
    DW_OP.PUSH_OBJECT_ADDRESS.value: 0,
    DW_OP.FORM_TLS_ADDRESS.value: 1,
    DW_OP.CALL_FRAME_CFA.value: 0,
    # 2.5.1.4 Arithmetic and Logical Operations
    DW_OP.ABS.value: 1,
    DW_OP.AND_.value: 2,
    DW_OP.DIV.value: 2,
    DW_OP.MINUS.value: 2,
    DW_OP.MOD.value: 2,
    DW_OP.MUL.value: 2,
    DW_OP.NEG.value: 2,
    DW_OP.NOT_.value: 2,
    DW_OP.OR_.value: 2,
    DW_OP.PLUS.value: 2,
    DW_OP.PLUS_UCONST.value: 1,
    DW_OP.SHL.value: 1,
    DW_OP.SHR.value: 1,
    DW_OP.SHRA.value: 1,
    DW_OP.XOR.value: 2,
    # 2.5.1.4 Control Flow Operations
    DW_OP.LE.value: 1,
    DW_OP.GE.value: 1,
    DW_OP.EQ.value: 1,
    DW_OP.LT.value: 1,
    DW_OP.GT.value: 1,
    DW_OP.NE.value: 1,
    # DW_OP.SKIP.value: TODO,
    # DW_OP.BRA.value: TODO,
    # DW_OP.CALL2.value: TODO,
    # DW_OP.CALL4.value: TODO,
    # DW_OP.CALL_REF.value: TODO,
    # 2.5.1.6 Special Operations
    DW_OP.NOP.value: 0,
    # 2.6.1.1.2 Register Location Descriptions
    DW_OP.REGX.value: 0,
    DW_OP.STACK_VALUE.value: 1,
    DW_OP.IMPLICIT_VALUE.value: 0,
    # 2.6.1.2 Composite Location Descriptions
    DW_OP.PIECE.value: 1,
    DW_OP.BIT_PIECE.value: 1,
}

_generate_dynamic_values(MIN_STACK_SIZE, "DW_OP_breg", 0, 31, lambda x: 0)
_generate_dynamic_values(MIN_STACK_SIZE, "DW_OP_reg", 0, 31, lambda x: 0)
_generate_dynamic_values(MIN_STACK_SIZE, "DW_OP_lit", 0, 31, lambda x: 0)


class Evaluator:
    """An (unfinished) implementation of the DWARFv4 stack machine.

    To evaluate a DWARFv4 expression, subclass this and override the following
    methods:
    - ``_fbreg``
    - ``_breg``
    - ``_bregx``
    - ``_deref``
    - ``_deref_size``
    - ``_xderef``
    - ``_xderef_size``
    - ``_form_tls_address``
    - ``_call_frame_cfa``
    - ``_reg``
    - ``_regx``

    The above specify the operating environment of the evaluator, whose
    behavior is specified in terms of values in the CPU of a machine running
    the program to which this debug info is attached.

    Many other methods have names that are suffices of the various DWARFv4
    opcodes (e.g. ``DW_OP_add`` becomes ``_add``), the behavior of the
    evaluator may be changed as necessary by subclasses by overriding them.
    For even more control, override ``_dispatch``.

    TODO: say which methods access the stack through operations other than
    _push and _pop!

    NB: This is not standards compliant, the arithmetic operations are all
    supposed to happen mod some number depending on the largest representable
    address on the machine that the binary is compiled for.

    Incomplete parts of the code are marked with ``TODO``, other
    ``NotImplementedError`` instances are from methods that must be overridden.
    """

    def __init__(self) -> None:
        self._stack: List[int] = []
        self._was_stack_value = False

    # Opcode implementations:

    # 2.5.1.1 Literal encodings

    def _lit(self, n: int) -> None:
        assert 0 <= n <= 31, f"There is no DW_OP_lit{n} in DWARFv4"
        self._push(n)

    def _addr(self, addr: int) -> None:
        self._assert_valid_address(addr)
        self._push(addr)

    def _const(self, n: int) -> None:
        self._push(n)

    # 2.5.1.2 Register Based Addressing

    def _fbreg(self, _offset: int) -> None:
        raise NotImplementedError(DW_OP.FBREG.value)

    def _breg(self, n: int, _offset: int) -> None:
        assert 0 <= n <= 31, f"There is no DW_OP_breg{n} in DWARFv4"
        raise NotImplementedError(f"DW_OP_breg{n}")

    def _bregx(self, n: int, _offset: int) -> None:
        raise NotImplementedError(DW_OP.BREGX.value)

    # 2.5.1.3 Stack Operations

    def _dup(self) -> None:
        self._pick(0)

    def _drop(self) -> None:
        self._pop()

    def _pick(self, index: int) -> None:
        self._push(self._stack[-(index + 1)])

    def _over(self) -> None:
        self._pick(1)

    def _swap(self) -> None:
        top = self._pop()
        snd = self._pop()
        self._push(top)
        self._push(snd)

    def _rot(self) -> None:
        raise NotImplementedError(DW_OP.ROT.value)  # TODO

    def _deref(self) -> None:
        raise NotImplementedError(DW_OP.DEREF.value)

    def _deref_size(self, _size: int) -> None:
        raise NotImplementedError(DW_OP.DEREF_SIZE.value)

    def _xderef(self) -> None:
        raise NotImplementedError(DW_OP.XDEREF.value)

    def _xderef_size(self, _size: int) -> None:
        raise NotImplementedError(DW_OP.XDEREF_SIZE.value)

    def _push_object_address(self) -> None:
        raise NotImplementedError(DW_OP.PUSH_OBJECT_SIZE.value)

    def _form_tls_address(self) -> None:
        raise NotImplementedError(DW_OP.FORM_TLS_ADDRESS.value)

    def _call_frame_cfa(self) -> None:
        raise NotImplementedError(DW_OP.CALL_FRAME_CFA.value)

    # 2.5.1.4 Arithmetic and Logical Operations

    def _unary_operator(self, op: Callable[[int], int]) -> None:
        """Implementation detail for DWARF arithmetic and logical opcodes."""
        self._push(op(self._pop()))

    def _binary_operator(self, op: Callable[[int, int], int]) -> None:
        """Implementation detail for DWARF arithmetic and logical opcodes."""
        top = self._pop()
        snd = self._pop()
        self._push(op(snd, top))

    def _abs(self) -> None:
        self._push(abs(self._pop()))

    def _and(self) -> None:
        self._binary_operator(operator.and_)

    def _div(self) -> None:
        # TODO: correct semantics? is this appropriately signed?
        raise NotImplementedError(DW_OP.DIV.value)
        # self._binary_operator(operator.floordiv)

    def _minus(self) -> None:
        self._binary_operator(operator.sub)

    def _mod(self) -> None:
        self._binary_operator(operator.mod)

    def _mul(self) -> None:
        self._binary_operator(operator.mul)

    def _neg(self) -> None:
        self._unary_operator(operator.neg)

    def _not(self) -> None:
        self._unary_operator(operator.not_)

    def _or(self) -> None:
        self._binary_operator(operator.or_)

    def _plus(self) -> None:
        self._binary_operator(operator.add)

    def _plus_uconst(self, summand: int) -> None:
        self._push(summand)
        self._plus()

    def _shl(self) -> None:
        # TODO: correct semantics?
        raise NotImplementedError(DW_OP.SHL.value)
        # self._binary_operator(operator.shl)

    def _shr(self) -> None:
        # TODO: correct semantics?
        raise NotImplementedError(DW_OP.SHR.value)
        # self._binary_operator(operator.shr)

    def _shra(self) -> None:
        # TODO: correct semantics? this can't be right for this and ``shr``...
        raise NotImplementedError(DW_OP.SHRA.value)
        # self._binary_operator(operator.shr)

    def _xor(self) -> None:
        self._push(self._pop() ^ self._pop())

    # 2.5.1.4 Control Flow Operations

    def _cmp(self, op: Callable[[int, int], int]) -> None:
        top = self._pop()
        snd = self._pop()
        self._push(int(op(snd, top)))

    def _le(self) -> None:
        self._cmp(operator.le)

    def _ge(self) -> None:
        self._cmp(operator.ge)

    def _eq(self) -> None:
        self._cmp(operator.eq)

    def _lt(self) -> None:
        self._cmp(operator.lt)

    def _gt(self) -> None:
        self._cmp(operator.gt)

    def _ne(self) -> None:
        self._cmp(operator.ne)

    def _skip(self) -> None:
        raise NotImplementedError(DW_OP.SKIP.value)  # TODO

    def _bra(self) -> None:
        raise NotImplementedError(DW_OP.BRA.value)  # TODO

    def _call2(self) -> None:
        raise NotImplementedError(DW_OP.CALL2.value)  # TODO

    def _call4(self) -> None:
        raise NotImplementedError(DW_OP.CALL4.value)  # TODO

    def _call_ref(self) -> None:
        raise NotImplementedError(DW_OP.CALL_REF.value)  # TODO

    # 2.5.1.6 Special Operations

    def _nop(self) -> None:
        pass

    # 2.6.1.1.2 Register Location Descriptions

    def _reg(self, n: int) -> None:
        assert 0 <= n <= 31, f"There is no DW_OP_reg{n} in DWARFv4"
        raise NotImplementedError(f"DW_OP_reg{n}")

    def _regx(self, n: int) -> None:
        raise NotImplementedError(DW_OP.REGX.value)

    def _implicit_value(self, _length: int, _block: Any) -> None:
        raise NotImplementedError(DW_OP.IMPLICIT_VALUE.value)  # TODO

    def _stack_value(self) -> None:
        self._was_stack_value = True

    # 2.6.1.2 Composite Location Descriptions

    def _piece(self, _length: int) -> None:
        raise NotImplementedError(DW_OP.PIECE.value)

    def _bit_piece(self, _bit_length: int, _bit_offset: int) -> None:
        raise NotImplementedError(DW_OP.BIT_PIECE.value)

    # Private methods:

    def _assert_valid_address(self, _addr: int) -> None:
        """Assert that this is a valid address on the binary's architecture."""
        pass

    def _pop(self) -> int:
        return self._stack.pop()

    def _push(self, x: int) -> None:
        self._stack.append(x)

    def _assert_min_stack_size(self, size: int, msg: str) -> None:
        """Assert that the stack has size at least ``size``"""
        assert len(self._stack) >= size, msg + f"\nStack was: {self._stack}"

    def _dispatch(self, opcode: DW_OP, args: Sequence[int]) -> None:
        lit = lit_num(opcode)
        breg = breg_num(opcode)
        reg = reg_num(opcode)

        # 2.5.1.1 Literal encodings
        if lit is not None:
            self._lit(lit)
        elif opcode == DW_OP.ADDR:
            self._addr(args[0])

        # 2.5.1.2 Register Based Addressing
        elif breg is not None:
            self._breg(breg, args[0])
        elif opcode == DW_OP.FBREG:
            self._fbreg(args[0])
        elif opcode == DW_OP.BREGX:
            self._bregx(args[0], args[1])

        # 2.5.1.3 Stack Operations
        elif opcode == DW_OP.DUP:
            self._dup()
        elif opcode == DW_OP.DROP:
            self._drop()
        elif opcode == DW_OP.PICK:
            self._pick(args[0])
        elif opcode == DW_OP.OVER:
            self._over()
        elif opcode == DW_OP.SWAP:
            self._swap()
        elif opcode == DW_OP.ROT:
            self._rot()
        elif opcode == DW_OP.DEREF:
            self._deref()
        elif opcode == DW_OP.DEREF_SIZE:
            self._deref_size(args[0])
        elif opcode == DW_OP.XDEREF:
            self._xderef()
        elif opcode == DW_OP.XDEREF_SIZE:
            self._xderef_size(args[0])
        elif opcode == DW_OP.PUSH_OBJECT_ADDRESS:
            self._push_object_address()
        elif opcode == DW_OP.FORM_TLS_ADDRESS:
            self._form_tls_address()
        elif opcode == DW_OP.CALL_FRAME_CFA:
            self._call_frame_cfa()

        # 2.5.1.4 Arithmetic and Logical Operations
        elif opcode == DW_OP.ABS:
            self._abs()
        elif opcode == DW_OP.AND_:
            self._and()
        elif opcode == DW_OP.DIV:
            self._div()
        elif opcode == DW_OP.MINUS:
            self._minus()
        elif opcode == DW_OP.MOD:
            self._mod()
        elif opcode == DW_OP.MUL:
            self._mul()
        elif opcode == DW_OP.NEG:
            self._neg()
        elif opcode == DW_OP.NOT_:
            self._not()
        elif opcode == DW_OP.OR_:
            self._or()
        elif opcode == DW_OP.PLUS:
            self._plus()
        elif opcode == DW_OP.PLUS_UCONST:
            self._plus_uconst(args[0])
        elif opcode == DW_OP.SHL:
            self._shl()
        elif opcode == DW_OP.SHR:
            self._shr()
        elif opcode == DW_OP.SHRA:
            self._shra()
        elif opcode == DW_OP.XOR:
            self._xor()

        # 2.5.1.4 Control Flow Operations
        elif opcode == DW_OP.LE:
            self._le()
        elif opcode == DW_OP.GE:
            self._ge()
        elif opcode == DW_OP.EQ:
            self._eq()
        elif opcode == DW_OP.LT:
            self._lt()
        elif opcode == DW_OP.GT:
            self._gt()
        elif opcode == DW_OP.NE:
            self._ne()
        elif opcode == DW_OP.SKIP:
            self._skip()
        elif opcode == DW_OP.BRA:
            self._bra()
        elif opcode == DW_OP.CALL2:
            self._call2()
        elif opcode == DW_OP.CALL4:
            self._call4()
        elif opcode == DW_OP.CALL_REF:
            self._call_ref()

        # 2.5.1.6 Special Operations
        elif opcode == DW_OP.NOP:
            self._nop()

        # 2.6.1.1.2 Register Location Descriptions
        elif reg is not None:
            self._reg(reg)
        elif opcode == DW_OP.REGX:
            self._regx(args[0])
        elif opcode == DW_OP.STACK_VALUE:
            self._stack_value()

        # 2.6.1.2 Composite Location Descriptions
        elif opcode == DW_OP.PIECE:
            self._piece(args[0])
        elif opcode == DW_OP.BIT_PIECE:
            self._bit_piece(args[0], args[1])

        else:
            raise NotImplementedError(opcode)

    def _check(self, instr: DwarfInstr) -> None:
        # print(f"Checking {opcode} (args={args}) (stack={self._stack})")
        check(instr)

        try:
            # TODO: make class InsufficientStackError
            n = MIN_STACK_SIZE[instr.opcode.value]
            self._assert_min_stack_size(n, f"Expected stack depth {n} for {instr.opcode.value}")
        except KeyError:
            pass

    # Public interface:

    def was_stack_value(self) -> bool:
        return self._was_stack_value

    def pop(self) -> int:
        return self._pop()

    def eval(self, instructions: Sequence[DwarfInstr]) -> None:
        self._stack = []
        self._was_stack_value = False
        for instr in instructions:
            self._check(instr)
            self._dispatch(instr.opcode, instr.args)
