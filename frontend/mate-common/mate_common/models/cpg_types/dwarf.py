import enum
from typing import Final, List, Optional

from pydantic import BaseModel


@enum.unique
class DWARFTypeKind(enum.Enum):
    """Kinds of DWARF types."""

    BASIC: Final[str] = "basic"
    COMPOSITE: Final[str] = "composite"
    COMPOSITE_CACHED: Final[str] = "composite_cached"
    STRUCTURE: Final[str] = "structure"
    ARRAY: Final[str] = "array"
    ENUM: Final[str] = "enum"
    UNION: Final[str] = "union"
    CLASS: Final[str] = "class"
    DERIVED: Final[str] = "derived"
    SUBROUTINE: Final[str] = "subroutine"


DWARF_TYPE_KINDS = frozenset(i.value for i in DWARFTypeKind)


@enum.unique
class DWARFTypeIDSentinel(enum.Enum):
    """Special sentinels for DWARF type IDs."""

    # NOTE(ww): These **must** be kept in sync with the Headache LLVM pass!

    # NOTE(ww): "()" is a special sentinel type ID for a nullptr DIType. Headache emits
    # these when it's asked to resolve the base type for a type that doesn't have one,
    # or explicitly when a type knows that it has no internal type(s) to expand.
    NONE: Final[str] = "()"

    # NOTE(ww): "(<void>)" is a special sentinel for (subroutine) types that return
    # nothing (i.e., void) as well as types that derive from void (e.g. `void *`).
    VOID: Final[str] = "(<void>)"

    # NOTE(ww): "(<varargs>)" is a special sentinel for subroutine types that take
    # an indefinite number of parameters via the "..." variadic specification.
    VARARGS: Final[str] = "(<varargs>)"


class DWARFTypeCommonInfo(BaseModel):
    """Models the common information in every DWARF type."""

    name: str
    tag: str
    size: int
    align: int
    offset: int
    forward_decl: bool
    virtual: bool
    artificial: bool


class DWARFEnumerator(BaseModel):
    """Models an enum value in a DWARF enum type."""

    name: str
    unsigned: bool
    value: int


class DWARFScope(BaseModel):
    """A representation of the nearest enclosing lexical scope.

    The enclosing scope will also contain virtual address range information, unless it has been
    optimized away.
    """

    tag: str
    line: int
    contiguous: bool
    inlined: bool
    va_start: Optional[int] = None
    va_end: Optional[int] = None
    range_list: Optional[List[List[int]]] = None


@enum.unique
class DWARFSubrangeKind(enum.Enum):
    """Kinds of DWARF subrange type."""

    COUNT: Final[str] = "count"
    GLOBAL_VARIABLE: Final[str] = "global_variable"
    LOCAL_VARIABLE: Final[str] = "local_variable"


class DWARFSubrange(BaseModel):
    kind: DWARFSubrangeKind

    def is_variadic(self) -> bool:
        return self.kind != DWARFSubrangeKind.COUNT


class GlobalVariableSubrange(DWARFSubrange):
    name: str
    local_to_unit: bool
    display_name: str
    linkage_name: str


class LocalVariableSubrange(DWARFSubrange):
    name: str
    parameter: bool
    arg: int
    artificial: bool
    object_pointer: bool


class CountSubrange(DWARFSubrange):
    count: int
