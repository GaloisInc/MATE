"""A utility model containing functions and classes related to parsing and interpreting DWARF
information."""

from __future__ import annotations

import itertools
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Collection, Dict, List, Optional, Set, Tuple, Union

from elftools.dwarf.compileunit import CompileUnit
from elftools.dwarf.constants import DW_INL_declared_inlined, DW_INL_inlined
from elftools.dwarf.descriptions import describe_reg_name
from elftools.dwarf.die import DIE, AttributeValue
from elftools.dwarf.dwarfinfo import DWARFInfo
from elftools.dwarf.locationlists import BaseAddressEntry as LocationBaseAddressEntry
from elftools.dwarf.ranges import BaseAddressEntry as RangeBaseAddressEntry
from sqlalchemy.orm import Session, aliased
from sqlalchemy.orm.exc import NoResultFound

from dwarflang.ast import DwarfInstr, instr_to_json, offset_to_int, set_fbreg
from dwarflang.decoder import Decoder
from dwarflang.enums import DW_OP, DwarfRegister, breg_num, reg_num
from dwarflang.fold import constant_fold
from mate.config import LLVM_ADDR2LINE
from mate_common.models.cpg_types import (
    DWARFScope,
    DWARFSubrangeKind,
    DWARFTypeCommonInfo,
    DWARFTypeKind,
    NodeKind,
)
from mate_query import db
from mate_query.cpg.models.node.dwarf import DerivedType

if TYPE_CHECKING:
    from mate_query.cpg.models.core.cpg import CPG
    from mate_query.cpg.models.node.ast.mc import MachineFunction
    from mate_query.cpg.models.node.ast.bin import ASMGlobalVariable
    from mate_query.cpg.models.node.dwarf import DWARFType, DWARFArgument, DWARFLocalVariable

from .logging import make_logger

logger = make_logger(__name__)

# A set of types that can be further unrolled into meaningful identities
UNROLLABLE_CPG_DT_TYPES = frozenset(
    {DWARFTypeKind.UNION.value, DWARFTypeKind.STRUCTURE.value, DWARFTypeKind.CLASS.value}
)

# A set of types that are composites of multiple other types.
# NOTE(ww): Observe that this set is the same as the set of types
# supplied by LLVM's DICompositeType with the exception of COMPOSITE_CACHED
# (which is a special-case for handling recursive composites).
COMPOSITE_CPG_DT_TYPES = frozenset(
    {
        DWARFTypeKind.COMPOSITE.value,
        DWARFTypeKind.COMPOSITE_CACHED.value,
        DWARFTypeKind.STRUCTURE.value,
        DWARFTypeKind.ARRAY.value,
        DWARFTypeKind.ENUM.value,
        DWARFTypeKind.UNION.value,
        DWARFTypeKind.CLASS.value,
    }
)


@dataclass(frozen=True, eq=True)
class DWARFRegLocation:
    """Represents an DWARF program location based on a register."""

    reg: str
    """
    The base register for the location computation.
    """

    offset: Optional[int] = None
    """
    The offset from the base register.
    """
    va_start: Optional[int] = None
    """The beginning VA for this location to be valid"""
    va_end: Optional[int] = None
    """The ending VA for this location to be valid"""


@dataclass(frozen=True, eq=True)
class DWARFAddrLocation:
    """Represents a DWARF address location."""

    address: int
    """The address location"""


@dataclass(frozen=True, eq=True)
class ScopeInfo:
    """Represents some information about a DWARF scope."""

    va_start: int
    """
    The virtual address that the scope begins at (inclusive).
    """

    va_end: int
    """
    The virtual address that the scope ends at (exclusive).
    """

    contiguous: bool
    """
    Whether or not the scope is contiguous, i.e., whether every
    address in ``[va_start, va_end)`` is in the scope.
    """


@dataclass
class MantiDwarfTypeInfo:
    name: str
    base_type: str
    base_type_size: int
    """ele_count * base_type_size"""
    total_size: int
    common: DWARFTypeCommonInfo
    locations: Optional[List[Union[DWARFRegLocation, DWARFAddrLocation]]] = None
    recursive: bool = False
    scope: Optional[ScopeInfo] = None
    """For structs"""
    parent_var: Optional[MantiDwarfTypeInfo] = None
    child_vars: Optional[Union[List[MantiDwarfTypeInfo], str]] = None
    """For arrays"""
    ele_count: int = 1
    is_vla: bool = False
    """For pointers"""
    indirections: int = 0
    """For run-time location info"""
    location_conc: Optional[List[int]] = None
    """For run-time value info"""
    values: Optional[List[int]] = None


@dataclass(eq=True)
class UnrolledFieldName:
    nest_name: str
    field_name: str

    @property
    def full_name(self) -> str:
        return f"{self.nest_name}.{self.field_name}"


@dataclass(frozen=True, eq=True)
class UnrolledField:
    name: UnrolledFieldName  # Unrolled field name
    size: int
    padding: bool = False


@dataclass(frozen=True, eq=True)
class FieldOffset:
    offset: int
    field: UnrolledField


@dataclass(frozen=True, eq=True)
class UnrolledTypeInfo:
    name: str  # Top-level name
    total_size: int  # Total size of unrolled var
    field_offsets: List[FieldOffset] = field(
        default_factory=list
    )  # Mapping of offsets to UnrolledField


class LocationListWalker:
    """A helper class for iterating over DWARF location lists, yielding accurate base addresses for
    each entry."""

    def __init__(self, cu_base, location_list):
        self._base = cu_base
        self._location_list = location_list

    def locations(self):
        for location in self._location_list:
            if isinstance(location, LocationBaseAddressEntry):
                self._base = location.base_address
            else:
                # DWARFv4 2.6.2:
                # The applicable base address of a location list entry is determined by
                # the closest preceding base address selection entry (...)
                # If there is no such selection entry, then the applicable base address
                # defaults to the base address of the compilation unit.
                yield (self._base, location)


@lru_cache()
def all_cus(dwarf: DWARFInfo) -> List[CompileUnit]:
    """Given a ``DWARFInfo``, returns all compilation unit DIEs."""
    return dwarf.iter_CUs()


@lru_cache()
def all_dies(dwarf: DWARFInfo) -> List[DIE]:
    """Returns every single child DIE in every single compilation unit in the given ``DWARFInfo``,
    including null DIEs."""
    return [die for cu in all_cus(dwarf) for die in cu.iter_DIEs()]


@lru_cache()
def offset_die_map(dwarf: DWARFInfo) -> Dict[int, DIE]:
    """Returns a mapping of ``offset -> DIE`` for all non-trivial (i.e., non- null) DIEs in the
    supplied ``DWARFInfo``."""

    # NOTE(ww): This is safe across multiple compilation units, since each DIE's
    # offset is relative to the overall .debug_info stream and *NOT* the compilation
    # unit that it belongs to.

    return {die.offset: die for die in all_dies(dwarf) if not die.is_null()}


def dwarf_getattr(die: DIE, name: str, default: Optional[Any] = None) -> Optional[Any]:
    """Extracts the value from a DWARF DIE's attributures by name, returning the specified default
    if no such attribute exists."""
    attr = die.attributes.get(name)
    if attr is not None:
        return attr.value
    else:
        return default


def dwarf_reg_to_machine_reg(opcode_name: str, arch="x64") -> str:
    """Change a ``DW_OP_(b?)reg([0-9]+)`` to the name of an ``x86(_64)?`` register.

    ``arch`` may be ``"x64"`` or ``"x86"``.
    """
    if opcode_name.startswith(DwarfRegister.DW_OP_REG.value):
        return describe_reg_name(int(opcode_name[9:]), arch)
    elif opcode_name.startswith(DwarfRegister.DW_OP_BREG.value):
        return describe_reg_name(int(opcode_name[10:]), arch)
    assert False, "Expected DW_OP_reg or DW_OP_breg, found " + opcode_name


def dwarf_expr_as_value(
    expr: List[DwarfInstr], parent_loc_expr: Optional[List[DwarfInstr]] = None, arch: str = "x64"
) -> Optional[Union[str, Tuple[str, int]]]:
    """Return a representation of this DWARF expression as a value.

    This only works if the expression is length 1 (a single instruction), and
    that instruction is one of the various ``DW_OP_(b?)reg([0-9]+)`` registers.

    It may return:

    - The name of a register, in which case the value of the expression is the
      value stored in register
    - A ``(register name, offset)`` pair, in which case the value of the expression
      is a pointer equal to the value stored in that register plus an offset
    - ``None``, if the expression is more complex
    """
    if len(expr) != 1:
        return None
    (dwarf_op, args) = instr_to_json(expr[0])

    if dwarf_op.startswith(DwarfRegister.DW_OP_REG.value) or dwarf_op.startswith(
        DwarfRegister.DW_OP_REGX.value
    ):
        assert len(args) == 0
        return dwarf_reg_to_machine_reg(dwarf_op, arch=arch)

    if dwarf_op.startswith(DwarfRegister.DW_OP_BREG.value) or dwarf_op.startswith(
        DwarfRegister.DW_OP_BREGX.value
    ):
        assert len(args) == 1
        return (dwarf_reg_to_machine_reg(dwarf_op, arch=arch), args[0])

    if dwarf_op == DwarfRegister.DW_OP_FBREG.value and parent_loc_expr is not None:
        assert len(parent_loc_expr) == 1
        parent_loc = parent_loc_expr[0]

        def replace_fbreg(fbreg_instr: DwarfInstr) -> List[DwarfInstr]:
            return [
                DwarfInstr(DW_OP.CONSTU, [offset_to_int(fbreg_instr)]),
                parent_loc,
                DwarfInstr(DW_OP.PLUS, []),
            ]

        if reg_num(parent_loc.opcode) is not None or breg_num(parent_loc.opcode) is not None:
            folded = constant_fold(set_fbreg(expr, replace_fbreg))
            if len(folded) == 1:
                (dwarf_op, args) = instr_to_json(folded[0])
                return (dwarf_reg_to_machine_reg(dwarf_op, arch=arch), args[0])

    return None


def decode_locations(
    attr,
    dwarf: DWARFInfo,
    parent_loc: Optional[List[int]] = None,
    var_name: str = "<unknown>",
    arch: str = "x64",
) -> List[Dict[str, Any]]:
    """Turn a ``DW_AT_location`` into a list of location specifications.

    A ``DW_AT_location`` is either:

    1. a location expression, which is decoded by the ``dwarflang`` into
       a register + an offset, or
    2. an offset into the location lists which has to be looked up, and becomes
       a list of location expressions as described below.

    Because the value of registers can change over the lifetime of the program,
    this function returns a list of locations, each of which specifies the
    program counter range in which the location is valid (``begin_offset`` to
    ``end_offset``).
    """
    logger.debug(f"Decoding location for variable {var_name}")

    def decode(serialized_expr: List[int]) -> List[DwarfInstr]:
        decoder = Decoder(dwarf.structs)
        decoder.process_expr(serialized_expr)
        return decoder.get_result()

    def location_to_json(serialized_expr: List[int]) -> Dict[str, Any]:
        expr = decode(serialized_expr)
        parent_loc_expr = None if parent_loc is None else decode(parent_loc)
        val = {
            "location": dwarf_expr_as_value(expr, parent_loc_expr=parent_loc_expr, arch=arch),
            "location_expression": list(map(instr_to_json, expr)),
        }
        return val

    if attr.form == "DW_FORM_sec_offset":
        loc_list: List[AttributeValue] = dwarf.location_lists().get_location_list_at_offset(
            attr.value
        )
        cu: CompileUnit = dwarf.get_CU_containing(attr.offset)
        cu_tag: DIE = dwarf.get_DIE_from_refaddr(cu.cu_die_offset, cu)
        walker = LocationListWalker(cu_tag.attributes["DW_AT_low_pc"].value, loc_list)
        return [
            {
                "base_address": base_address,
                "begin_offset": location_entry.begin_offset,
                "end_offset": location_entry.end_offset,
                **location_to_json(location_entry.loc_expr),
            }
            for (base_address, location_entry) in walker.locations()
        ]

    assert attr.form == "DW_form_exprloc" or attr.form == "DW_FORM_exprloc"
    return [location_to_json(attr.value)]


def is_block_inlined(block_die: DIE) -> bool:
    """Walks up a "block"-type DIE (e.g. scope)'s parents to the nearest function, returning whether
    or not that function has been inlined by the compiler."""
    if block_die.tag == "DW_TAG_subprogram":
        if "DW_AT_inline" not in block_die.attributes:
            return False
        else:
            return block_die.attributes["DW_AT_inline"].value in (
                DW_INL_inlined,
                DW_INL_declared_inlined,
            )
    else:
        return is_block_inlined(block_die.get_parent())


def decode_scope(var_dies: Collection[DIE]) -> Dict[str, Any]:
    """Given a set of DIEs corresponding to a local variable or parameter, determine the (maximal)
    VA range for which the underlying variable is in scope."""
    block_dies = {var_die.get_parent() for var_die in var_dies}

    block_tags = {block_die.tag for block_die in block_dies}
    block_tag = None
    if len(block_tags) == 1:
        block_tag = block_tags.pop()
    elif len(block_tags) > 1:
        logger.error(
            f"Weird: variable claims to be in multiple parent scopes: {', '.join(block_tags)}"
        )

    if block_tag == "DW_TAG_subprogram":
        # NOTE(ww): Annoying extra work: in case we're decoding the scope
        # of a parameter that is mismatched between its function DIEs
        # (see the NOTE in collect_param_dies when building param_dies_list),
        # we need to make sure our block_dies set is maximal. We do this
        # by grabbing the VA of the enclosing scope (since it's a subprogram)
        # and keying into va_dies_map. This gets us any additional block DIEs
        # that don't explicitly reference the parameter but do contain it.
        block_va = dies_attribute_one_value(block_dies, "DW_AT_low_pc")
        if block_va is not None:
            dies_map = va_dies_map(next(iter(block_dies)).dwarfinfo)
            block_dies.update(dies_map[block_va])

    scope_line = dies_attribute_one_value(var_dies, "DW_AT_decl_line")

    scope = {
        "tag": block_tag,
        "contiguous": dies_attribute_one(block_dies, "DW_AT_ranges") is None,
        "inlined": any(is_block_inlined(block_die) for block_die in block_dies),
        "line": scope_line,
    }

    # If we're in a function that's been inlined or a lexical scope within
    # an inlined function, or we're reading from a declaration, then we have
    # no VA range information to retrieve.
    if scope["inlined"]:
        return scope

    if scope["contiguous"]:
        low_pc = dies_attribute_one_value(block_dies, "DW_AT_low_pc")
        high_pc = dies_attribute_one_value(block_dies, "DW_AT_high_pc")
        if low_pc is None or high_pc is None:
            logger.error("Weird: Inferred a contiguous scope but wasn't given a PC range")
            return scope

        scope.update(
            {
                "va_start": low_pc,
                # NOTE(ww): DWARF cheekiness: high_pc isn't actuall a full VA, but a
                # relative offset from low_pc. We add the two to get the full end VA.
                "va_end": low_pc + high_pc,
            }
        )
    else:
        range_lists = next(iter(var_dies)).dwarfinfo.range_lists()
        # NOTE(ww): mypy complains here because it can't infer that we're in
        # a branch that guarantees that DW_AT_ranges is available.
        range_list = range_lists.get_range_list_at_offset(
            dies_attribute_one_value(block_dies, "DW_AT_ranges")
        )
        va_start: Optional[int] = None
        va_end: Optional[int] = None
        for va_range in range_list:
            # NOTE(ww): We might need to handle this in the future.
            # For the time being none of our samples have included
            # a base address entry in their .debug_ranges and thus
            # default to the compilation unit's base address.
            assert not isinstance(va_range, RangeBaseAddressEntry)
            if va_start is None or va_start > va_range.begin_offset:
                va_start = va_range.begin_offset
            if va_end is None or va_end < va_range.end_offset:
                va_end = va_range.end_offset

        scope.update({"range_list": range_list, "va_start": va_start, "va_end": va_end})

    return scope


def summarize_local_var(
    var_dies: Collection[DIE], dwarf: DWARFInfo, parent_loc: Optional[List[int]], arch="x64"
) -> Dict[str, Any]:
    """Summarize a parameter or local variable from a set of associated DIEs."""
    name = dies_attribute_one_value(var_dies, "DW_AT_name")
    if name is not None:
        name = name.decode()
    else:
        name = "<unknown>"

    location = dies_attribute_one(var_dies, "DW_AT_location")
    if parent_loc is not None and location is not None:
        location = decode_locations(
            location, dwarf, parent_loc=parent_loc, var_name=name, arch=arch
        )

    is_artificial = dies_attribute_one_value(var_dies, "DW_AT_artificial")
    if is_artificial is None:
        is_artificial = False

    logger.debug(f"Decoding scope for {name}")
    scope = decode_scope(var_dies)

    # NOTE(ww): Implicit this parameters don't have a DW_AT_line, since they don't actually
    # appear in the source code. LLVM treats these as having a line of 0, so we do the same
    # here for pairing purposes. We could probably do the same more generally on
    # every artificial argument/local; this is worth investigating.
    if scope["line"] is None and name == "this":
        scope["line"] = 0

    ret = {"name": name, "dwarf_scope": scope, "artificial": is_artificial}

    if location is not None:
        ret["dwarf_location"] = location

    return ret


def decode_global_location(var_die: DIE, dwarf: DWARFInfo) -> List[Dict[str, Any]]:
    """Given a DIE for a global variable, return a representation of that global's DWARF location
    expression."""
    name = var_die.attributes.get("DW_AT_name")
    if name is not None:
        name = name.value.decode()

    location = var_die.attributes.get("DW_AT_location")
    if location is not None:
        return decode_locations(location, dwarf, var_name=name)
    else:
        # Global variables should always have a location, but LLVM's DWARF emission
        # is occasionally bugged.
        logger.warning(f"weird: global variable missing DW_AT_location: {name=} {var_die=}")
        return []


def collect_param_dies(func_dies: Collection[DIE]) -> Tuple[List[Set[DIE]], List[Set[DIE]]]:
    """Given a set of DIEs for a particular function, return a list of sets of DIEs for each
    parameter to that function, as well as a list of sets of DIEs corresponding to the function's
    template parameter packs (if it has any)."""

    # Collect all of the associated parameter DIEs from each function DIE.
    # Sanity-check that the number of parameter DIEs in each is equal, since
    # we'll need to cross-reference between them later.
    # Additionally, collect the template parameter pack DIE from each
    # function DIE, if present, and add it to the set of pack DIEs.
    param_dies_list = []
    param_pack_dies_list = []

    # Sort the dies first before processing, because we want to look at the the
    # leading declaration (as provided by DWARF offset) to decide the number of
    # parameters
    for idx, func_die in enumerate(sorted(func_dies, key=lambda x: x.offset)):
        param_dies = []
        param_pack_dies = []

        for die in func_die.iter_children():
            if die.tag == "DW_TAG_formal_parameter":
                param_dies.append(die)
            elif die.tag == "DW_TAG_GNU_template_parameter_pack":
                param_pack_dies.append(die)
            # TODO(ww): Handle DW_TAG_unspecified_parameters for vararg functions.

        # Special case: Use the first function DIE we iterate over to prep the lists
        # of parameter and parameter pack DIE sets.
        if idx == 0:
            for param_die in param_dies:
                param_dies_list.append({param_die})
            for param_pack_die in param_pack_dies:
                param_pack_dies_list.append({param_pack_die})
            continue

        for idx, param_pack_die in enumerate(param_pack_dies):
            param_pack_dies_list[idx].add(param_pack_die)

        # NOTE(ww): In a perfect world, the number of parameter DIEs for
        # each DIE corresponding to a function would be identical.
        # But we don't live in a perfect world: for whatever reason,
        # LLVM will sometimes emit fewer parameter DIEs than there actually are.
        # A good example of this is png::filter::None::decode_row in the Hamlin
        # challenge: decode_row takes 4 explicit parameters (+ 1 = 5 for
        # the implicit *this needed for the object), but the definition DIE
        # for decode_row elides the last parameter for whatever reason
        # (maybe because it's unused and begins with an `_`?). Consequently,
        # the declaration and definition DIEs don't match.
        #
        # The ideal solution is to fix this in LLVM, but for the time being
        # we have two different resolution strategies available to us:
        #
        #  * Find the shortest list of parameters and use it. This causes us to
        #    lose information about parameters that LLVM decides not to emit DWARF
        #    for for whatever reason, but should be safe for all other parameters.
        #
        #  * Keep track of all parameters, and just ignore if the cardinality between
        #    function DIEs doesn't match up. This avoids the problem of missing
        #    parameters (since they'll show up, at the very least, one *one* DIE),
        #    but *might* be unsound: DWARF doesn't keep track of parameter indices,
        #    so we don't have a nice way to detect whether a parameter was silently
        #    dropped between two normally emitted ones. Consequently, we might misalign
        #    our parameter DIEs. We should catch this later one when pulling attributes,
        #    but it's a risk.
        #
        # I've gone with the second strategy below.
        for idx, param_die in enumerate(param_dies):
            if idx >= len(param_dies_list):
                logger.warning(
                    "Very weird: DIEs for function disagree on parameter count: "
                    f"{idx + 1} > {len(param_dies_list)}"
                )
                param_dies_list.append({param_die})
            else:
                param_dies_list[idx].add(param_die)

    return param_dies_list, param_pack_dies_list


def collect_scoped_vars(die: DIE) -> List[DIE]:
    """Given a DIE, recursively traverse its children and collect all child DW_TAG_variables."""
    scoped_vars = []

    for die in die.iter_children():
        # NOTE(ww): DW_TAG_common_block also exists, but appears to be Fortran only.
        # TODO(ww): DW_TAG_inlined_subroutine is another child here; we *must* collect
        # and properly track its child parameters and locals in order to provide location
        # information for inlined variables.
        if die.tag in {"DW_TAG_lexical_block", "DW_TAG_try_block", "DW_TAG_catch_block"}:
            scoped_vars.extend(collect_scoped_vars(die))
        elif die.tag == "DW_TAG_variable" and die.attributes.get("DW_AT_name"):
            scoped_vars.append(die)

    return scoped_vars


# TODO(ww): Type-hint and document this function.
def summarize_params(param_dicts, _param_pack_dies_list):
    # NOTE(ww): Ideally we would also return early if param_pack_dies_list os empty,
    # since that *should* signify that the parameters are *not* from a template
    # expansion. Unfortunately, that's not actually a reliable sentinel:
    # param_pack_dies_list comes from the parent function, but the variadic template
    # could be at the C++ class level. To make matters worse, LLVM (as of 7) doesn't even
    # bother to emit it correctly at the C++ class level.
    # So, we cross our fingers below and hope that duplicate parameter names do
    # indeed signify a template pack expansion (and not inlining or something else weird).
    if len(param_dicts) == 0:
        return param_dicts

    param_groups = itertools.groupby(param_dicts, key=lambda d: d["name"])
    parameter_idx = 0
    variadic_idx = 0
    from_template = False
    for _, grp in param_groups:
        group = list(grp)

        # When we encounter a group of parameters of the same name, we know
        # we've entered template parameter pack expansion. From here on,
        # every parameter belongs to *some* template pack even if it's alone,
        # so from_template is True.
        if len(group) > 1:
            from_template = True

        if from_template:
            for template_idx, param_dict in enumerate(group):
                param_dict.update(
                    {
                        "parameter_index": parameter_idx,
                        "variadic_index": variadic_idx,
                        "template_index": template_idx,
                        "original_name": param_dict["name"],
                        # NOTE(ww): We don't use this clobbered name anywhere,
                        # but set it to prevent downstream instrumentation
                        # (i.e., aspirin) from consuming the non-clobbered name
                        # and assuming that it's unique.
                        # Aspirin itself will un-clobber the name once it
                        # finishes disambiguating the parameter.
                        "name": f"{param_dict['name']}:{template_idx}",
                        "from_variadic_template": True,
                    }
                )
                parameter_idx += 1
        else:
            parameter_idx += 1

        variadic_idx += len(group)

    return param_dicts


def die_name(die: DIE) -> Optional[str]:
    """Return a sensible name for this DIE, or ``None`` if this DIE doesn't have a
    ``DW_AT_linkage_name`` or ``DW_AT_name``."""

    name = None
    # NOTE(ww): The order here (linkage name first) is important: linkage names
    # should always be less ambiguous than bare names, and choosing a bare name
    # in a C++ binary when a linkage name is available will cause us to clobber
    # things downstream.
    if "DW_AT_linkage_name" in die.attributes:
        name = die.attributes["DW_AT_linkage_name"].value.decode("utf8")
    if name is None and "DW_AT_name" in die.attributes:
        name = die.attributes["DW_AT_name"].value.decode("utf8")
    return name


def dies_attribute_many(dies: Collection[DIE], name: str) -> List[AttributeValue]:
    """Returns zero or more ``AttributeValues`` from an iterable of semantically linked DIEs."""

    return [die.attributes[name] for die in dies if name in die.attributes]


def dies_attribute_one(dies: Collection[DIE], name: str) -> Optional[AttributeValue]:
    """Returns exactly one ``AttributeValue`` from an iterable of semantically linked DIEs, or
    ``None`` under the following conditions:

    1. None of the linked DIEs contain the attribute
    2. One or more of the DIEs disagree about the value of the attribute
    """
    found_values = dies_attribute_many(dies, name)

    # NOTE(ww): Annoying: attribute values can be unhashable (like lists),
    # so we can't do the obvious thing and use a set for deduplication here.
    # We also have to de-dupe on just the internal value, since the AttributeValue
    # wrapper contains an offset that's (hopefully) unique and may be in different
    # DW_FORMs for equivalent values.
    unique_values: List[Any] = []
    for found_value in found_values:
        if found_value.value not in unique_values:
            unique_values.append(found_value.value)

    if len(unique_values) == 0:
        return None
    if len(unique_values) > 1:
        logger.debug(f"DIEs: {dies}")
        logger.error(
            f"Expected exactly one common {name} among {len(dies)} DIEs, but got "
            f"{len(unique_values)} distinct values"
        )
        return None

    return found_values.pop()


def dies_attribute_one_value(dies: Collection[DIE], name: str) -> Optional[Any]:
    """Like `dies_attribute_one`, but returns the underlying attribute value directly instead of the
    ``AttributeValue`` container.

    Returns ``None`` under the same conditons as `dies_attribute_one`.
    """
    attribute_value = dies_attribute_one(dies, name)
    if attribute_value is not None:
        return attribute_value.value
    return None


def ref_to_stream_off(ref: AttributeValue, cu: CompileUnit) -> int:
    """Converts a DWARF reference (in attribute form) into an appropriate offset into the containing
    ``.debug_info`` stream."""

    # DW_FORM_ref_addr indicates an absolute offset from the beginning of the
    # .debug_info section/stream.
    if ref.form == "DW_FORM_ref_addr":
        return ref.value
    # DW_FORM_ref\d indicates a relative offset from the header of the enclosing
    # compilation unit.
    elif re.match(r"DW_FORM_ref\d", ref.form):
        return cu.cu_offset + ref.value
    else:
        # NOTE(ww): In DWARFv4 the only other reference form is DW_FORM_ref_sig8,
        # which only gets used for type entries (and we don't touch those).
        # DWARFv5 adds another class of reference forms (DW_FORM_ref_sup)
        # for referencing supplementary object files, but we don't consume DWARFv5. Yet.
        logger.error(f"Barf: Given an unsupported reference form: {ref.form}")
        assert False


def summarize_func_dies(_func_name: str, func_dies: Collection[DIE], dwarf: DWARFInfo, arch="x64"):
    param_dies_list, param_pack_dies_list = collect_param_dies(func_dies)

    # NOTE(ww): Unlike parameters, we *probably* don't need to keep track
    # of a set of DIEs for each scoped local variable.
    # The reason: DWARF has no real reason to spread DW_TAG_variable state
    # across multiple DIEs for the same function the way it does for
    # parameters (which can appear in multiple declarations).
    scoped_vars: List[DIE] = []
    for func_die in func_dies:
        scoped_vars += collect_scoped_vars(func_die)

    # TODO(ww): Extract all declarations from func_dies

    is_external = dies_attribute_one_value(func_dies, "DW_AT_external")
    if is_external is None:
        is_external = False

    is_artificial = dies_attribute_one_value(func_dies, "DW_AT_artificial")
    if is_artificial is None:
        is_artificial = False

    summary: Dict[str, Any] = {
        "external": is_external,
        "artificial": is_artificial,
        "params": [],
        "vars": [],
    }

    func_locs: Optional[AttributeValue] = dies_attribute_one(func_dies, "DW_AT_frame_base")
    if func_locs is not None:
        # Get the stack frame base pointer
        decoded_func_locs = decode_locations(func_locs, dwarf, arch=arch)
        func_locs = func_locs.value
        assert (
            len(decoded_func_locs) == 1
        ), f"Expected one frame_base location, found {decoded_func_locs}"

    # TODO(ww): As the literal "parameter" keys below indicate, treating
    # parameters and local variables as the same for extraction purposes
    # is an increasingly unreliable assumption. We should probably refactor
    # a good deal of this to handle the two independently.
    param_dicts: List[Dict[str, Any]] = [
        {"parameter": True, **summarize_local_var(dies, dwarf, func_locs, arch=arch)}
        for dies in param_dies_list
    ]
    summarize_params(param_dicts, param_pack_dies_list)

    summary["params"] += param_dicts
    summary["vars"] += [
        {"parameter": False, **summarize_local_var([die], dwarf, func_locs, arch=arch)}
        for die in scoped_vars
    ]
    return summary


def global_dies_map(dwarf: DWARFInfo, externals=True) -> Dict[str, List[DIE]]:
    """Return a mapping of global variable names to their DIE entries."""
    mapping: Dict[str, List[DIE]] = defaultdict(list)
    for die in all_dies(dwarf):
        # Global variables are just DW_TAG_variables whose parents are a compilation unit.
        if die.tag != "DW_TAG_variable" or die.get_parent().tag != "DW_TAG_compile_unit":
            continue
        if die.attributes.get("DW_AT_external") and not externals:
            continue
        name = die_name(die)
        if name is not None:
            mapping[name].append(die)
    return mapping


def get_referent_die(die: DIE, referent_attr: str) -> Optional[DIE]:
    """Given a DIE containing an attribute that references another DIE, attempt to return the
    referenced DIE.

    Returns ``None`` if the DIE can't be found.
    """

    referent_offset = ref_to_stream_off(die.attributes[referent_attr], die.cu)
    referent_die = offset_die_map(die.dwarfinfo).get(referent_offset)

    if referent_die is None:
        logger.warning(
            f"Weird: Referent offset not in offset map: referent_offset={hex(referent_offset)}"
        )
        logger.debug(f"Attributes: {die.attributes}")
        return None

    return referent_die


def is_external_declaration(die: DIE) -> bool:
    """Returns whether or not the given DIE corresponds to an external declaration."""
    return die.attributes.get("DW_AT_declaration", False) and die.attributes.get(
        "DW_AT_external", False
    )


@lru_cache()
def va_dies_map(dwarf) -> Dict[int, Set[DIE]]:
    """Returns a mapping of function VAs to a set of DIEs for each function."""
    mapping: Dict[int, Set[DIE]] = defaultdict(set)

    # NOTE(ww): We build the VA DIEs map in a series of passes:
    # 1. We collect all function DIEs into the "orphaned" set.
    # 2. We prune the "orphaned" set, adding DIEs to the mapping
    #    if they have a DW_AT_low_pc (i.e., VA) that's present in the
    #    VA symbol map. We also add these DIEs to a mapping of DIE -> VA.
    # 3. We prune the "orphaned" set again, looking for DIEs that
    #    don't have a DW_AT_low_pc but *do* have a referent DIE that's
    #    already in the mapping. We add these DIEs to their corresponding
    #    sets by looking their referents up in the DIE -> VA mapping.
    # 4. We run a final pass on the mapping, looking for DIEs that reference
    #    other DIEs via DW_AT_abstract_origin and add them to their corresponding
    #    sets.

    # NOTE(ww): The implementation below optimizes the approach
    # specified above. It's identical in behavior, but avoids unnecessarily
    # building the entire "orphaned" set.

    orphaned: Set[DIE] = set()
    die_va_map: Dict[DIE, int] = {}
    for die in all_dies(dwarf):
        if die.tag != "DW_TAG_subprogram":
            continue

        if "DW_AT_low_pc" in die.attributes:
            va = die.attributes["DW_AT_low_pc"].value
            mapping[va].add(die)
            die_va_map[die] = va
        else:
            orphaned.add(die)

    for die in orphaned:
        # NOTE(ww): We *might* not need to check for DW_AT_abstract_origin here --
        # experimentally, it's attached to DIEs that already have DW_AT_low_pc and
        # therefore isn't in the orphaned set. However, it doesn't hurt us to check anyways.
        has_referent = False
        referent_die = None
        for referent_name in ["DW_AT_specification", "DW_AT_abstract_origin"]:
            if referent_name in die.attributes:
                has_referent = True
                referent_die = get_referent_die(die, referent_name)
                break

        if not has_referent:
            if not is_external_declaration(die):
                logger.warning(
                    "Weird: orphaned DIE has no DW_AT_specification or DW_AT_abstract_origin; "
                    f"{die.attributes=}"
                )
            continue

        if referent_die is None:
            logger.error(f"Weird: Couldn't get referent DIE; {die.attributes=}")
            continue

        referent_va = die_va_map.get(referent_die)
        if referent_va is None:
            # NOTE(ww): This is a warning (and not an error) because we expect it to happen,
            # especially in C++ binaries: our "orphaned" DIEs will contain both the declarations
            # and the bodies of fully inlined libc++ helpers, meaning that we won't have
            # direct access to their VAs. This doesn't matter much for our purposes,
            # but it's good to note. We could fix it up in the future by integrating
            # the symbol table into this method.
            logger.warning("Couldn't get an VA for referent DIE (probably inlined)")
            continue

        mapping[referent_va].add(referent_die)

    for dies in mapping.values():
        cur_dies = dies.copy()
        for die in cur_dies:
            if "DW_AT_abstract_origin" in die.attributes:
                referent_die = get_referent_die(die, "DW_AT_abstract_origin")
                if referent_die is None:
                    logger.error(f"Weird: Couldn't get referent DIE; {die.attributes=}")
                dies.add(referent_die)

    return mapping


def unroll_nested_type_fields(typ: MantiDwarfTypeInfo) -> UnrolledTypeInfo:
    """Unroll an object that has fields, including nested structs into a single level representation
    of the fields contained within that object.

    :param typ: The type to be unrolled
    :return: An unrolled representation of a type
    """
    # Initial unrolled type that looks like the original, without any unrolled fields
    flat_var = UnrolledTypeInfo(name=typ.name, total_size=typ.total_size)

    if not isinstance(typ.child_vars, list):
        logger.error(f"Don't know how to handle composite cached type: {typ.child_vars}")
        return flat_var

    # To find padding areas
    curr_offset = 0
    # Loop through types
    child_var: MantiDwarfTypeInfo
    for child_var in typ.child_vars:
        # Gather offset and size info
        offset = child_var.common.offset
        if curr_offset != offset:
            # Insert a padding field if offsets don't match
            padding_name = UnrolledFieldName(flat_var.name, "<pad>")
            pad_field = UnrolledField(padding_name, offset - curr_offset, padding=True)
            flat_var.field_offsets.append(FieldOffset(curr_offset, pad_field))

        size = child_var.common.size

        if child_var.base_type not in UNROLLABLE_CPG_DT_TYPES:
            # Normal type
            field_name = UnrolledFieldName(flat_var.name, child_var.name)
            field = UnrolledField(field_name, size)
            flat_var.field_offsets.append(FieldOffset(offset, field))
        else:
            # Nested object with more fields
            nested_var = unroll_nested_type_fields(child_var)
            for field_off in nested_var.field_offsets:
                # Rework the naming by prepending the name of our current flat_var
                if field_off.field.name.nest_name:
                    field_off.field.name.nest_name = (
                        f"{flat_var.name}.{field_off.field.name.nest_name}"
                    )
                else:
                    field_off.field.name.nest_name = flat_var.name

                flat_var.field_offsets.append(
                    FieldOffset(offset + field_off.offset, field_off.field)
                )
        curr_offset = offset + size

    # NOTE: These are most likely anonymous fields in a struct. We have no DWARF
    # info about their size or offsets. There could even be padding between
    # these anonymous fields
    # TODO: These anonymous fields might be worth promoting to some type of
    #   byte-array to keep track of reads/writes at the byte-level
    if curr_offset != typ.total_size:
        flat_var.field_offsets.append(
            FieldOffset(
                curr_offset,
                UnrolledField(
                    UnrolledFieldName(flat_var.name, "<pad>"),
                    typ.total_size - curr_offset,
                    padding=True,
                ),
            )
        )

    return flat_var


def type_info_to_manti_info(
    session: Session, cpg: CPG, type_info: DWARFType, parent_var=None, indirections=0
) -> MantiDwarfTypeInfo:
    top_type = type_info.type_kind.value
    common_info = type_info.common

    # Keep track of pointer indirections
    if type_info.is_pointer:
        indirections += 1

    name = type_info.name
    if not name and type_info.is_composite:
        # If our name is empty and we're a composite type, treat it
        # like an anonymous composite.
        name = "<anon>"

    this_type_info = MantiDwarfTypeInfo(
        name=name,
        base_type=top_type,
        base_type_size=common_info.size,
        total_size=common_info.size,
        parent_var=parent_var,
        indirections=indirections,
        common=common_info,
    )

    # Check for other info
    if isinstance(type_info, DerivedType):
        nested_type = type_info.base_type
        if type_info.is_member:
            base_type = type_info_to_manti_info(
                session, cpg, nested_type, parent_var=this_type_info
            )
            this_type_info.base_type = base_type.base_type
            this_type_info.base_type_size = base_type.base_type_size
            this_type_info.child_vars = base_type.child_vars
            this_type_info.indirections = base_type.indirections
            this_type_info.ele_count = base_type.ele_count
            return this_type_info
        # TODO(ek): nested_type is a DerivedType here sometimes. What should we actually be checking?
        if isinstance(nested_type, str):
            assert False, "Check why you're here -- nested type is str"
            # TODO(ww): Unreachable code, removed because of mypy. Why was this here?
            # if nested_type == DWARFTypeIDSentinel.NONE.value:
            #     this_type_info.base_type = "<none>"
            #     return this_type_info
        else:
            return type_info_to_manti_info(
                session,
                cpg,
                nested_type,
                parent_var=parent_var,
                indirections=indirections,
            )

    if top_type in UNROLLABLE_CPG_DT_TYPES:
        # Recurse down
        children = [
            type_info_to_manti_info(session, cpg, child_info, parent_var=this_type_info)
            for child_info in type_info.members
        ]
        this_type_info.child_vars = children
        return this_type_info
    elif top_type == DWARFTypeKind.BASIC.value:
        this_type_info.base_type = name
        return this_type_info
    elif top_type == DWARFTypeKind.SUBROUTINE.value:
        # NOTE(ww): It's not clear what the semantics of a function (really always
        # a function pointer) inside of a type are in this context. We'll have marked
        # the indirection at some higher-up recursive case, so just return for now.
        return this_type_info
    elif top_type == DWARFTypeKind.ENUM.value:
        return this_type_info
    elif top_type == DWARFTypeKind.ARRAY.value:
        subrange = type_info.subrange
        if subrange.kind != DWARFSubrangeKind.COUNT:
            # TODO(ww): We should store the name of the variable providing the VLA
            # length here so that Manticore can use it.
            logger.warning(f"Unable to handle variable length array subrange: {subrange}")
            this_type_info.is_vla = True
        else:
            this_type_info.ele_count = subrange.count
        child = type_info_to_manti_info(
            session,
            cpg,
            type_info.base_type,
            parent_var=this_type_info,
            indirections=indirections,
        )
        this_type_info.child_vars = [child]
        this_type_info.base_type_size = child.base_type_size
        return this_type_info
    elif top_type == DWARFTypeKind.COMPOSITE_CACHED.value:
        this_type_info.recursive = True
        this_type_info.child_vars = type_info.name
        return this_type_info
    else:
        logger.error(f"Unsupported variable type info parsing: {top_type}")
        # NOTE(ww): Previously unreachable, but now reachable without (MATE) assertions
        # enabled. Pacifies mypy's return checker.
        assert False


def var_info_to_manti_info(
    session: Session,
    cpg,
    cpg_var: Union[DWARFLocalVariable, DWARFArgument, ASMGlobalVariable],
    cpg_func: Optional[MachineFunction] = None,
) -> MantiDwarfTypeInfo:
    """Fill out the MantiDwarfTypeInfo struct from the CPG variable Node.

    :param cpg_var: Variable node from the CPG
    :param cpg_func: CPG MachineFunction for more accurate scoping
    :return: Type that Manticore can handle
    """
    type_info = type_info_to_manti_info(session, cpg, cpg_var.dwarf_type)
    if cpg_var.kind == NodeKind.ASM_GLOBAL_VARIABLE:
        # Set scope for global variables as whole addressable space
        # NOTE: 64-bit address space should be safe
        type_info.scope = ScopeInfo(va_start=0, va_end=2**64, contiguous=True)
    else:
        dwarf_scope = cpg_var.dwarf_scope
        valid_dwarf_scope = dwarf_scope and dwarf_scope.va_start and dwarf_scope.va_end
        if (
            valid_dwarf_scope
            and cpg_func
            and cpg_var.kind in {NodeKind.DWARF_LOCAL_VARIABLE, NodeKind.DWARF_ARGUMENT}
        ):
            type_info.scope = ScopeInfo(
                va_start=dwarf_scope.va_start,
                va_end=real_dwarf_scope_end(session, cpg, cpg_func.name, dwarf_scope),
                contiguous=dwarf_scope.contiguous,
            )
        elif valid_dwarf_scope:
            type_info.scope = dwarf_scope and ScopeInfo(
                va_start=dwarf_scope.va_start,
                va_end=dwarf_scope.va_end,
                contiguous=dwarf_scope.contiguous,
            )
    location_infos = cpg_var.dwarf_location
    type_info.locations = []
    for loc in location_infos:
        location = loc["location"]
        if cpg_var.kind == NodeKind.ASM_GLOBAL_VARIABLE:
            if location is not None:
                assert False, "ASMGlobalVariable location is not None, weird. Check this out"
            # TODO(ek): Clean this up
            # For global variables:
            # "dwarf_location": [{"location": null, "location_expression": [["DW_OP_addr", [4210984]]]}]
            location_expr = loc["location_expression"]
            if len(location_expr) != 1:
                assert False, f"Unexpected location expression longer than 1: {location_expr}"
            addr_expr = location_expr[0]
            assert len(addr_expr) == 2, f"sub-expression for location list is not 2: {addr_expr}"
            assert (
                addr_expr[0] == "DW_OP_addr"
            ), f"Unexpected dwarf expression operation. Expecting 'DW_OP_addr' but got {addr_expr[0]}"
            location_addr_list = addr_expr[1]
            assert (
                len(location_addr_list) == 1
            ), f"length of location address list is not equal to 1: {location_addr_list}"
            # TODO(ek): Check if scope_info actually exists at this point
            type_info.locations.append(DWARFAddrLocation(address=location_addr_list[0]))
        else:
            try:
                va_start = loc["base_address"] + loc["begin_offset"]
                va_end = loc["base_address"] + loc["end_offset"]
            except KeyError:
                # No location scope information
                va_start = None
                va_end = None
            if isinstance(location, list):
                type_info.locations.append(
                    DWARFRegLocation(
                        reg=location[0], offset=location[1], va_start=va_start, va_end=va_end
                    )
                )
            else:
                if location is not None:
                    type_info.locations.append(
                        DWARFRegLocation(reg=location, va_start=va_start, va_end=va_end)
                    )
                else:
                    # location is None for variables that aren't stored in memory
                    # We shouldn't need to do anything for these variables
                    continue
    type_info.name = cpg_var.name
    return type_info


@dataclass(eq=True, frozen=True)
class SourceCodeInfo:
    path: str
    line: int

    def __str__(self):
        return f"{self.path}:{self.line}"

    @property
    def file(self):
        return Path(self.path).name


def source_info_from_va(
    _session: db.Session, _cpg: db.Graph, binary_path: str, va: int
) -> SourceCodeInfo:
    """Retrieve source code information given an VA.

    :param cpg: CPG to use
    :param va: va in question
    :return: Source Code info
    """
    # TODO: See issue 1054 https://gitlab-ext.galois.com/mate/MATE/-/issues/1054
    # asminst = aliased(_cpg.ASMInst)
    # source_loc = aliased(_cpg.SourceLocation)
    # location = session.query(source_loc).join(...).filter(asminst.va == f"{va}").one()
    proc = subprocess.run([LLVM_ADDR2LINE, "-h"], capture_output=True)
    if not LLVM_ADDR2LINE.exists() or proc.returncode != 0:
        # Weird mypy error when using f-strings
        logger.warning(
            "Unable to run addr2line utility at {!r}.\nstdout: {!r}\nstderr: {!r}"
        ).format(LLVM_ADDR2LINE, proc.stdout, proc.stderr)
        return SourceCodeInfo(path="?", line=-1)

    addr2line_out = subprocess.check_output(
        [LLVM_ADDR2LINE, "-e", f"{binary_path}", f"{va:#X}"], text=True
    ).strip()
    path, line = addr2line_out.split(":", 1)
    try:
        int_line = int(line)
    except ValueError:
        int_line = -1
    return SourceCodeInfo(path=path, line=int_line)


def real_dwarf_scope_end(session: Session, cpg: CPG, func_name: str, dwarf_scope: DWARFScope):
    containing_func = aliased(cpg.MachineFunction)
    mblock = aliased(cpg.MachineBasicBlock)
    asmblock = aliased(cpg.ASMBlock)

    try:
        func, mbb, asmbb = (
            session.query(containing_func)
            .join(mblock, containing_func.blocks)
            .join(asmblock, mblock.asm_block)
            .filter(
                (asmblock.va_end == f"{dwarf_scope.va_end}") & (containing_func.name == func_name)
            )
            .with_entities(containing_func, mblock, asmblock)
            .one()
        )
    except NoResultFound:
        return dwarf_scope.va_end

    # Note(sonya): This is a special case for when a function has a single basic block
    if len(func.blocks) == 1:
        return func.va_end

    if mbb.is_epilogue_insertion_block:
        for epilogue_start, _ in func.epilogues:
            if asmbb.va <= epilogue_start < asmbb.va_end:
                return epilogue_start
        logger.warning("Could not find an epilogue in basicblock VA range that has epilogue")

    return dwarf_scope.va_end


def cpg_dwarf_unroll_type_info(
    session: Session, cpg: CPG, dwarf_type: DWARFType
) -> Optional[UnrolledTypeInfo]:
    """This function uses the MATE CPG to return unrolled type information that Manticore can use
    (via dwarfcore).

    :param cpg: Connection to CPG
    :param dwarf_type: The type to retrieve unrolled variable type information for
    :return: Type information
    """

    if dwarf_type.type_kind.value not in UNROLLABLE_CPG_DT_TYPES:
        return None

    manti_type = type_info_to_manti_info(session, cpg, dwarf_type)
    return unroll_nested_type_fields(manti_type)
