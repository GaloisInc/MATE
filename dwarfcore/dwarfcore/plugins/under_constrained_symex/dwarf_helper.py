from typing import Optional

import mate_query.db as db
from mate_query.cpg.models import DWARFType

from .exceptions import UCDwarfException, UCException

_UCSE_session: Optional[db.Session] = None
_UCSE_graph: Optional[db.Graph] = None


def init_db_session(db_session: db.Session, db_graph: db.Graph):
    global _UCSE_graph
    global _UCSE_session
    _UCSE_graph = db_graph
    _UCSE_session = db_session


def dwarf_get_template_type_argument(obj_type: DWARFType, arg_num: int) -> DWARFType:
    """Return the template type argument number 'arg_num' of type 'obj_type'. For example, calling
    this method on (map<int, string>, 1) returns the string type.

    If arg_num is invalid (negative or bigger than the number of template arguments of obj_type)
    this method raises an exception
    """

    if arg_num < 0 or len(obj_type.template_params) <= arg_num:
        raise UCDwarfException(
            f"Can't get template argument {arg_num} for type {obj_type.common.name}"
        )

    return obj_type.template_params[arg_num]


def dwarf_get_base_type(dwarf_type: DWARFType) -> DWARFType:
    """Resolve derived types until we reach the real type information or a pointer."""
    while True:
        # print(f"Resolving derived type: {dwarf_type.attributes}")
        if dwarf_type.name.startswith("_vptr$"):
            break
        elif dwarf_type.kind.value == "DerivedType" and not dwarf_is_pointer_or_reference_type(
            dwarf_type
        ):
            dwarf_type = dwarf_type.base_type
        elif dwarf_type.kind.value == "CompositeCachedType":
            dwarf_type = dwarf_get_real_type_by_name(dwarf_type.name)
        else:
            break
    return dwarf_type


def dwarf_get_real_type_by_name(type_name: str) -> DWARFType:
    global _UCSE_graph
    global _UCSE_session

    if _UCSE_session is None or _UCSE_graph is None:
        raise UCException("DB session not initialized")

    for t in _UCSE_session.query(_UCSE_graph.DWARFType).filter_by(name=type_name).all():
        if t.kind.value != "CompositeCachedType":
            return t
    raise UCException(f"Failed for type {type_name}")


def dwarf_is_pointer_or_reference_type(dwarf_type: DWARFType) -> bool:
    # TODO: Use the tag until dwarf_type.is_reference is supported
    return dwarf_type.is_pointer or dwarf_type.common.tag == "DW_TAG_reference_type"
