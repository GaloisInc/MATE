"""This module is an interface to a custom SMTLIBv2 parser that is able to lift SMTLIBv2 statements
into python expressions and support the insertion of python variables and values into the lifted SMT
statement through the parsing of a unique replacement identifier."""
import io
import operator
from contextlib import redirect_stderr
from typing import Any, List, Optional, Union

from antlr4 import CommonTokenStream, InputStream, ParseTreeWalker, StdinStream
from smt2lib.SMTLIBv2Lexer import SMTLIBv2Lexer
from smt2lib.SMTLIBv2Listener import SMTLIBv2Listener
from smt2lib.SMTLIBv2Parser import SMTLIBv2Parser


class LiftingError(Exception):
    """Generic error during lifting of SMT expression."""


class UnsupportedArithOp(LiftingError):
    """Exception for when we encounter unsupported arithmetic mapping operations from string to
    Python operation."""


class MismatchedDeclReplace(LiftingError):
    """Exception for when replacement of declaration goes wrong."""


class UnhandledCase(LiftingError):
    """Exception for when we encounter an SMT formula with a case that we don't handle yet."""


class SMTLIBv2Lifter(SMTLIBv2Listener):
    def __init__(self, decls: Optional[List[Any]] = None) -> None:
        """Lift the custom SMTLib2 statement(s) and insert the elements of `decls` into their
        respective replacement positions.

        Ensure that the number of elements matches the number of unique
        replacements or undefined behavior (likely a crash) will occur.

        :param decls: A list of replacement values to be inserted
        """
        self._decls = decls or []
        self._arg_stack: List[Any] = []
        self._op_stack: List[Any] = []
        self._out: List[Any] = []

    @property
    def expr(self) -> Any:
        """The resulting expression after lifting."""
        return self._out[0]

    def exitCommand(self, _: SMTLIBv2Parser.CommandContext) -> None:
        """End of the command.

        Apply our operations to the collected arguments
        """
        op = self._op_stack.pop()
        self._out.append(op(*self._arg_stack))
        self._arg_stack = []

    def enterSymbol(self, ctx: SMTLIBv2Parser.SymbolContext) -> None:
        """Symbol is an operation on a (term | identifier | spec_constant).

        Set as the current operator.
        """
        txt = ctx.getText()
        op_switch = {"=": operator.eq}
        op = op_switch.get(txt, None)
        if op is None:
            raise UnsupportedArithOp(f"Unsupported operation {txt}")
        self._op_stack.append(op)

    def enterSpec_constant(self, ctx: SMTLIBv2Parser.Spec_constantContext) -> None:
        """A constant identifier.

        Add to the current operator's argument stack
        """
        if len(ctx.children) != 1:
            raise UnhandledCase("More than 1 child in spec_constant")
        child = ctx.getChild(0)
        res = None
        if isinstance(child, SMTLIBv2Parser.NumeralContext) or isinstance(
            child, SMTLIBv2Parser.DecimalContext
        ):
            res = int(child.getText())
        elif isinstance(child, SMTLIBv2Parser.HexadecimalContext):
            res = int(child.getText().replace("#", "0"), 16)
        elif isinstance(child, SMTLIBv2Parser.BinaryContext):
            res = int(child.getText().replace("#", "0"), 2)
        elif isinstance(child, SMTLIBv2Parser.StringContext):
            res = ctx.getText()
        if res is None:
            raise UnhandledCase(f"Unknown Spec Constant child {child}")
        self._arg_stack.append(res)

    def enterReplace_identifier(self, ctx: SMTLIBv2Parser.Replace_identifierContext) -> None:
        """Replaces the special identifier with what is listed in our declarations."""
        txt = ctx.getText()
        index = int(txt.rsplit("#", 1)[1])
        try:
            self._arg_stack.append(self._decls[index])
        except IndexError:
            raise MismatchedDeclReplace(
                f"Index value of {index} is out of range of decls: {self._decls}"
            )


def lift_smt2_to_python(smt2: Union[InputStream, str], decls: List[Any]) -> Any:
    """Lift the custom smt2 expression with the special replacement identifier and insert the
    `decls`.

    :param smt2: The SMT2 formula to lift into Python
    :param decls: A list of Python declaration expressions to place in the lifted SMT2 formula
    :return: Python expression equivalent to SMT2 formula
    """
    if isinstance(smt2, str):
        smt2 = InputStream(smt2)
    lexer = SMTLIBv2Lexer(smt2)
    stream = CommonTokenStream(lexer)
    parser = SMTLIBv2Parser(stream)
    tree = parser.start()
    lifter = SMTLIBv2Lifter(decls=decls)
    walker = ParseTreeWalker()
    walker.walk(lifter, tree)

    return lifter.expr


def validate_smt2(smt2: Union[InputStream, str], replacements: List[int]) -> List[str]:
    """Validate the smt2 formula according to our grammar. Return empty list if valid, or list of
    errors otherwise.

    :param smt2: The SMT2 formula to validate
    :param replacements: List of replacements corresponding to replacement
        keywords within smt2
    :return: List of errors if any, or empty list
    """
    if isinstance(smt2, str):
        smt2 = InputStream(smt2)
    lexer = SMTLIBv2Lexer(smt2)
    stream = CommonTokenStream(lexer)
    parser = SMTLIBv2Parser(stream)

    # Easier than figuring out how to do ErrorHandling correctly
    with io.StringIO() as err, redirect_stderr(err):
        tree = parser.start()
        if parser.getNumberOfSyntaxErrors() > 0:
            return err.getvalue().splitlines()

    lifter = SMTLIBv2Lifter(decls=replacements)
    walker = ParseTreeWalker()
    try:
        # Try our own lifter code to make sure we can actually do it when its
        # needed
        walker.walk(lifter, tree)
    except LiftingError as e:
        return [str(e)]

    return []


def main() -> Any:
    expr = lift_smt2_to_python(StdinStream(), [])
    return expr


if __name__ == "__main__":
    main()
