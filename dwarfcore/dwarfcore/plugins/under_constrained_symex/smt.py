from typing import Dict

from manticore.core.smtlib import Expression, Visitor

from .exceptions import UCException


class SmtNameTranslator:
    """Small helper class that transforms arbitrary variable names into SMTlib v2 compliant
    names."""

    # TODO(boyan):  The replacement below are temporary. While the chance they would
    # produce names that clash with other variables defined in the target program, we
    # should still ensure soudness by using replacements using "|" (e.g "[" -> "|[|").
    # Smtlib v2 supports "|" in names and "|" can't be used in C for variable names, so
    # using it makes us safe w.r.t name colisions.
    # However for the moment using "|" in names makes Manticore solver fail/hang. I'll
    # investigate the issue.
    TO_SMT = {
        "[": "______at_____",
        "]": "______ta_____",
        "(": "______openbracket______",
        ")": "______closebracket______",
        "$LEN": "_____LENGTH_OF_____",
        "$CAPACITY": "_____CAPACITY_OF_____",
        "$SIZE": "_____SIZE_OF_____",
    }

    @staticmethod
    def make_name_smt_compliant(name: str) -> str:
        for k, v in SmtNameTranslator.TO_SMT.items():
            name = name.replace(k, v)
        return name

    @staticmethod
    def revert_to_original_name(name: str) -> str:
        for k, v in SmtNameTranslator.TO_SMT.items():
            name = name.replace(v, k)
        return name


class UCPrettyPrinter(Visitor):

    op_map: Dict[str, str] = {
        "BitVecAdd": "+",
        "BitVecSub": "-",
        "BitVecMul": "*",
        "BitVecDiv": "/",
        "BitVecUnsignedDiv": "UDIV",
        "BitVecMod": "%",
        "BitVecRem": "REM",
        "BitVecUnsignedRem": "UREM",
        "BitVecShiftLeft": "<<",
        "BitVecShiftRight": ">>",
        "BitVecArithmeticShiftLeft": "<<",
        "BitVecArithmeticShiftRight": "SAR",
        "BitVecAnd": "&",
        "BitVecOr": "|",
        "BitVecXor": "^",
        "BitVecNot": "~",
        "BitVecNeg": "-",
        "LessThan": "<",
        "LessOrEqual": "<=",
        "BoolEqual": "==",
        "BoolNot": "!",
        "GreaterThan": ">",
        "GreaterOrEqual": ">=",
        "UnsignedLessThan": "ULT",
        "UnsignedLessOrEqual": "ULE",
        "UnsignedGreaterThan": "UGT",
        "UnsignedGreaterOrEqual": "UGE",
        "BitVecSignExtend": "SEXT",
        "BitVecZeroExtend": "ZEXT",
        "BitVecITE": "ITE",
        "BitVecConcat": "CONCAT",
        "BoolAnd": "&&",
        "BoolOr": "||",
        "BoolXor": "BoolXOR",
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.output: str = ""
        self.depth = 0

    def visit(self, expression: Expression) -> str:
        """Overload Visitor.visit because:

        - We need a pre-order traversal
        - We use a recursion as it makes it easier to keep track of the indentation
        """
        # Arbitrary depth limit for printing expressions. This is used to avoid
        # spending forever trying to print very deep expressions
        if self.depth > 14:
            return "<truncated>"
        self.depth += 1
        res = self._method(expression)
        self.depth -= 1
        return res

    def _method(self, expression: Expression, *args) -> str:
        """Overload Visitor._method because we want to stop to iterate over the visit_ functions as
        soon as a valid visit_ function is found."""
        assert expression.__class__.__mro__[-1] is object
        for cls in expression.__class__.__mro__:
            sort = cls.__name__
            methodname = "visit_%s" % sort
            method = getattr(self, methodname, None)
            if method is not None:
                return method(expression, *args)
        raise UCException(f"Unsupported class by pretty printer {expression.__class__.__name__}")

    def _visit_binary_operation(self, expression: Expression) -> str:
        op = expression.__class__.__name__
        op_str = UCPrettyPrinter.op_map[op]
        res = f"{self.visit(expression.operands[0])} {op_str} {self.visit(expression.operands[1])}"
        return f"({res})" if self.depth > 1 else res

    visit_BitVecOperation = _visit_binary_operation
    visit_BoolOperation = _visit_binary_operation

    def _visit_funclike_binary_operation(self, expression: Expression) -> str:
        op_str = UCPrettyPrinter.op_map[expression.__class__.__name__]
        operands_str = ",".join([self.visit(op) for op in expression.operands])
        return f"{op_str}({operands_str})"

    visit_BitVecUnsignedDiv = _visit_funclike_binary_operation
    visit_BitVecRem = _visit_funclike_binary_operation
    visit_BitVecUnsignedRem = _visit_funclike_binary_operation
    visit_BitVecITE = _visit_funclike_binary_operation
    visit_BitVecConcat = _visit_funclike_binary_operation
    visit_UnsignedLessThan = _visit_funclike_binary_operation
    visit_UnsignedLessOrEqual = _visit_funclike_binary_operation
    visit_UnsignedGreaterThan = _visit_funclike_binary_operation
    visit_UnsignedGreaterOrEqual = _visit_funclike_binary_operation
    visit_BitVecArithmeticShiftRight = _visit_funclike_binary_operation
    visit_BoolXor = _visit_funclike_binary_operation

    def _visit_unary_operation(self, expression: Expression) -> str:
        op = expression.__class__.__name__
        op_str = UCPrettyPrinter.op_map[op]
        return f"{op_str}({self.visit(expression.operands[0])})"

    visit_BitVecNot = _visit_unary_operation
    visit_BitVecNeg = _visit_unary_operation
    visit_BitVecSignExtend = _visit_unary_operation
    visit_BitVecZeroExtend = _visit_unary_operation
    visit_BoolNot = _visit_unary_operation

    def visit_BitVecExtract(self, expression: Expression) -> str:
        return f"{self.visit(expression.operands[0])}[{expression.begining}:{expression.end}]"

    def _visit_constant(self, expression: Expression) -> str:
        return str(expression.value)

    def visit_BitVecConstant(self, expression: Expression) -> str:
        if expression.value > 256:
            return hex(expression.value)
        else:
            return str(expression.value)

    def visit_BoolConstant(self, expression: Expression) -> str:
        return str(expression.value)

    def _visit_variable(self, expression: Expression) -> str:
        return SmtNameTranslator.revert_to_original_name(expression.name)

    visit_ArrayVariable = _visit_variable
    visit_BitVecVariable = _visit_variable
    visit_BoolVariable = _visit_variable

    @property
    def result(self) -> str:
        return self.output


def uc_pretty_print(expression: Expression):
    if not isinstance(expression, Expression):
        return str(expression)
    pp = UCPrettyPrinter()
    return pp.visit(expression)
