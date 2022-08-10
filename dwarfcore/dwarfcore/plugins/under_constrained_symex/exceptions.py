class UCException(Exception):
    """Generic class for exceptions thrown by the under-constrained manticore plugin."""


class UCDwarfException(UCException):
    """Exception raised on errors manipulating dwarf information."""


class InputError(UCException):
    """Exception raised when user inputs invalid data to the plugin."""


class VTableException(UCException):
    """An exception raise when the plugin fails to initialise a class vtable."""

    pass


class BaseNotUniqueException(UCException):
    """An exception raised when a symbolic pointer contains more than one base in its expression."""

    pass


class NoBaseException(UCException):
    """An exception raised when a symbolic pointer contains no base."""

    pass


class ExpressionTooComplexException(UCException):
    """An exception raised when an expression is too complex to be broken down into base+offset."""

    pass


class UncomputableMetaVar(UCException):
    """An exception raised when UC memory can't find a possible value for a metavar."""

    pass


class FatalSymexError(UCException):
    """Exception raised when symex can not continue because an error can't be fixed."""

    pass
