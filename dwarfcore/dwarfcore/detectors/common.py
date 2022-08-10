import base64
import bisect
from dataclasses import dataclass, field
from typing import Any, Dict, List, NamedTuple, Optional

from manticore import issymbolic
from manticore.native.cpu.abstractcpu import RegisterFile
from manticore.native.memory import InvalidMemoryAccess
from manticore.native.state import State

import dwarfcore.logging
from dwarfcore.dwarfcore import ManticoreAddress
from mate.build.tob_chess_utils.dwarf import (
    UNROLLABLE_CPG_DT_TYPES,
    DWARFAddrLocation,
    FieldOffset,
    MantiDwarfTypeInfo,
    unroll_nested_type_fields,
)
from mate_common.models.integration import ReachingInput, ReachingValue

logger = dwarfcore.logging.logger


@dataclass(eq=True)
class CallStackFrame:
    """Call Stack Frame information to look at info."""

    """Function name"""
    func_name: str
    """Address we left at"""
    leave_va: ManticoreAddress
    """Address to return to"""
    return_va: ManticoreAddress
    """Register state we left at"""
    register_state: RegisterFile
    """DWARF-derived in-scope variables"""
    inscope_variables: List[MantiDwarfTypeInfo]
    """Additional data for other plugins"""
    other_data: Dict[str, Any] = field(default_factory=dict)


class VariableAtMemoryInfo(NamedTuple):
    name: str
    min_mem: ManticoreAddress
    max_mem: ManticoreAddress
    var: MantiDwarfTypeInfo
    parent_min_mem: ManticoreAddress
    parent_max_mem: ManticoreAddress
    padding: bool


@dataclass
class FoundVarInfo:
    """Simple data structure for holding more info about a variable found at a memory location and
    how it relates to the call stack."""

    found_var: VariableAtMemoryInfo
    var_write_info: Dict[str, bool]
    call_frame: Optional[CallStackFrame]


def record_concretize_state_vars(state: State, orig_id: int) -> List[ReachingInput]:
    """Concretize and constrain all symbolic variables and return their values.

    This should be called with a temporary state if you wish to continue
    execution after this point.

    :param state: State to look for variables. Will constrain variables to values
    :param orig_id: Original state ID
    :return: Information about user inputs that reach this point in execution
    """
    solved_vars: List[ReachingInput] = []
    for sym_var in state.input_symbols:
        # Constrain after solving, in case of dependencies on other symbolic var values
        conc_val = state.solve_one(sym_var, constrain=True)
        if not isinstance(conc_val, (bytes, bytearray)):
            conc_val = repr(conc_val).encode("utf-8")

        logger.debug(f"[{orig_id}] {sym_var.name}: {conc_val!r}")
        # TODO(ek): Ignore SMT formula for now since it's extremely large
        solved_vars.append(
            ReachingInput(
                name=sym_var.name,
                symbolic_values=[
                    ReachingValue(
                        symbolic_value="Skipped",
                        concrete_value_base64=base64.b64encode(conc_val).decode("utf-8"),
                    )
                ],
            )
        )
    return solved_vars


def stack_mem_access(state: State, where: int) -> bool:
    """Check if a memory access is located at a valid position in the current stack.

    We use the stack register to determine the upper (low value for x86) bound
    and Manticore's load information for the bottom of the stack.

    :param state: Manticore State to use as context for program values
    :param where: The memory access to check
    :return: True if located in the stack; False otherwise
    """
    stack_map = state.cpu.memory.map_containing(state.cpu.STACK)
    stack_low = min(state.cpu.STACK, stack_map.start)
    stack_high = max(state.cpu.STACK, stack_map.start)
    return stack_low <= where <= stack_high


def variable_at_memory(
    mem_addr: ManticoreAddress,
    state: State,
    possible_vars: List[MantiDwarfTypeInfo],
    regfile: Optional[RegisterFile] = None,
) -> Optional[VariableAtMemoryInfo]:
    """Given a memory address and Manticore state, try to determine possible variables that occupy
    that space. Optionally, give a list of variables and their information to limit the search,
    otherwise search all known variables.

    :param mem_addr: Manticore memory address
    :param state: State to use for memory lookups
    :param possible_vars: DWARF variable information to look at for matching mem_addr
    :param regfile: Registers to use for looking up values at program state, if not specified use passed state
    :return: List of all variable information at the memory address or None
    """
    if regfile is None:
        regfile = state.cpu.regfile
    for variable in possible_vars:
        for loc in variable.locations:
            # Check all pointer indirection locations
            if isinstance(loc, DWARFAddrLocation):
                # TODO(ek): Does this need an VA offset to turn into a ManticoreAddress?
                begin_mem = ManticoreAddress(loc.address)
            else:
                # TODO(ek): Get dwarfcore dynamic base in here
                if (loc.va_start is None and loc.va_end is None) or loc.va_start <= regfile.read(
                    "PC"
                ) < loc.va_end:
                    read_reg = regfile.read(loc.reg.upper())
                    if issymbolic(read_reg):
                        logger.debug("Register value is symbolic. Not following for memory address")
                        continue
                    begin_mem = ManticoreAddress(read_reg + (loc.offset or 0))
                else:
                    continue
            indirections = variable.indirections
            while True:
                if issymbolic(begin_mem):
                    logger.debug("Got symbolic memory location. Skipping...")
                    break
                # Based on the indirection we're at, the `variable.total_size`
                # isn't correct, so use the size of a pointer
                end_mem = ManticoreAddress(
                    begin_mem
                    + (
                        variable.total_size
                        if indirections == 0
                        else state.cpu.memory.memory_bit_size // 8
                    )
                )
                min_mem = min(begin_mem, end_mem)
                max_mem = max(begin_mem, end_mem)
                if mem_addr in range(min_mem, max_mem):
                    if variable.base_type in UNROLLABLE_CPG_DT_TYPES:
                        # We can expand and look at the field mem ranges of this type
                        unrolled_fields = unroll_nested_type_fields(variable)
                        field_offsets = [
                            fo.offset + begin_mem for fo in unrolled_fields.field_offsets
                        ]
                        try:
                            field_var: FieldOffset = unrolled_fields.field_offsets[
                                bisect.bisect_right(field_offsets, mem_addr) - 1
                            ]
                            field_mem_addr = ManticoreAddress(begin_mem + field_var.offset)
                            return VariableAtMemoryInfo(
                                field_var.field.name.full_name,
                                field_mem_addr,
                                ManticoreAddress(field_mem_addr + field_var.field.size),
                                variable,
                                min_mem,
                                max_mem,
                                field_var.field.padding,
                            )
                        except IndexError:
                            logger.error(f"Cannot find variable at offset. Should not happen.")
                            return None
                    else:
                        return VariableAtMemoryInfo(
                            variable.name, min_mem, max_mem, variable, min_mem, max_mem, False
                        )

                if indirections == 0:
                    break
                # Loop over all indirection memory addresses
                try:
                    begin_mem = ManticoreAddress(
                        state.cpu.read_int(begin_mem, force=True, publish=False)
                    )
                except InvalidMemoryAccess:
                    logger.warning(
                        f"Caught invalid memory read (@{regfile.read('PC'):#x} during lookup location of {variable=}"
                    )
                indirections -= 1

    return None
