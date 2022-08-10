"""This module contains the DwarfCore class that plugins will use to query DWARF information.

DwarfCore does not actually parse the DWARF information itself. It extracts the
information from the MATE CPG.

There could be a difference between what Manticore uses for the VA of a
function or location and what DWARF information lists. Care must be taken
to make sure that the correct associated VA is used. One case this occurs is
when a binary is compiled with a dynamic base address, i.e.
position-independent code (PIC) with the ``ET_DYN`` ELF attribute. The DWARF
information will report from a 0x0 offset, but Manticore loads the code at an
arbitrary offset (see Manticore's ``Linux.BASE_DYN_ADDR_32`` and
``Linux.BASE_DYN_ADDR`` constants).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, NamedTuple, Optional, Union, cast

from capstone import Cs, CsInsn
from elftools.elf.elffile import ELFFile
from manticore.core.smtlib.expression import Expression, issymbolic
from manticore.native.cpu.abstractcpu import RegisterFile
from manticore.native.state import State
from manticore.platforms.linux import Linux
from sqlalchemy.orm import Session, aliased
from sqlalchemy.orm.exc import NoResultFound

import dwarfcore.logging
from mate.build.tob_chess_utils.dwarf import (
    DWARFAddrLocation,
    MantiDwarfTypeInfo,
    SourceCodeInfo,
    source_info_from_va,
    var_info_to_manti_info,
)
from mate.build.tob_chess_utils.elf import parse_dyn_sym_table
from mate.build.tob_chess_utils.range_avl_tree import RangeAVL, inorder
from mate_query.db import Graph

if TYPE_CHECKING:
    from mate_query.cpg.models.node.ast.mc import MachineFunction


logger = dwarfcore.logging.logger


class DwarfcoreException(Exception):
    """Generic dwarfcore exception."""

    pass


class Address(int):
    """Convenience class for pretty-printing addresses."""

    def __repr__(self) -> str:
        return f"{self.real:#x}"

    def __str__(self) -> str:
        return f"{self.real:#x}"


class DwarfAddress(Address):
    """An address that DWARF debug info uses."""

    pass


class ManticoreAddress(Address):
    """An address that Manticore uses."""

    pass


class VariableOperations(NamedTuple):
    read: List[str]
    write: List[str]


class DwarfCore:
    def __init__(self, session: Session, cpg: Graph, program_path: Path):
        """Instantiate a DwarfCore class.

        :param session: A DB session
        :param cpg: A MATE CPG handle
        :param program_path: The path to the elf program executable
        """
        with program_path.open("rb") as f:
            elf = ELFFile(f)

            dyn_base = 0
            addressbitsize = {"x86": 32, "x64": 64, "ARM": 32, "AArch64": 64}[
                elf.get_machine_arch()
            ]
            if elf.header.e_type == "ET_DYN":
                # DWARF and Manticore disagree on VA when analyzing DYN binaries
                if addressbitsize == 32:
                    dyn_base = Linux.BASE_DYN_ADDR_32
                else:
                    dyn_base = Linux.BASE_DYN_ADDR
            self.dyn_base = ManticoreAddress(dyn_base)
            # Get the function address mapping to dynamic symbol table from the ELF file
            self.func_addr_sym_table: Dict[DwarfAddress, str] = cast(
                Dict[DwarfAddress, str], parse_dyn_sym_table(elf)
            )

        self.session = session
        self.cpg = cpg

    @lru_cache()
    def func_addr_tree(self) -> RangeAVL:
        """A data structure for fast lookup of mapping from DWARF VA to function name.

        This is useful because a function is a _range_ of VAs, and a RangeAVL
        tree will take care of comparing bounds on the passed VA to find the
        correct function.

        :return: RangeAVL tree of DWARF VA to function name
        """
        return _func_addr_tree(self.session, self.cpg)

    @lru_cache()
    def all_functions(self) -> Dict[DwarfAddress, str]:
        """Retrieve all known functions, local and dynamic.

        :return: Mapping of DWARF address to function name
        """
        # Local functions
        ret = {DwarfAddress(node.lower): node.label for node in inorder(self.func_addr_tree().root)}
        # Dynamic functions
        ret.update(self.func_addr_sym_table)
        return ret

    @lru_cache()
    def start_va_of_function(self, func: str) -> Optional[DwarfAddress]:
        """Get the start VA (DWARF-VA) of given function or None if not found.

        :param func: Function name
        :return: DWARF VA or None
        """
        # TODO(ek) Check performance of this
        # Local functions
        for node in inorder(self.func_addr_tree().root):
            if node.label == func:
                return DwarfAddress(node.lower)
        for sym_va, sym_name in self.func_addr_sym_table.items():
            if sym_name == func:
                return sym_va
        return None

    @lru_cache()
    def start_va_of_function_m(self, func: str) -> Optional[ManticoreAddress]:
        """Get the start VA (Manticore-VA) of given function or None if not found.

        :param func: Function name
        :return: Manticore VA or None
        """
        dwarf_va = self.start_va_of_function(func)
        if dwarf_va is None:
            return None
        return ManticoreAddress(dwarf_va + self.dyn_base)

    @lru_cache()
    def func_name_from_va(self, va: Union[ManticoreAddress, Expression]) -> Optional[str]:
        """Return the mangled function name from a given Manticore VA.

        :param va: Manticore VA
        :return: Function name or None
        """
        if issymbolic(va):
            logger.debug("Unsupported symbolic VA Dwarf function lookup")
            return None
        assert isinstance(va, ManticoreAddress)

        # Need to modify va from Manticore's va to what is loaded in the tree
        # Subtract here, because we added before
        va -= self.dyn_base
        va = DwarfAddress(va)

        ret = self.func_addr_tree().find(va)
        if ret is not None:
            return ret.label

        # Try again using dynamic symbol table
        return self.func_addr_sym_table.get(va, None)

    @lru_cache()
    def va_to_func_in_cpg(
        self, va: Union[ManticoreAddress, Expression]
    ) -> Optional[MachineFunction]:
        """Get the DWARF information for a function, given a Manticore VA.

        :param va: Manticore VA
        :return: Function information or None
        """
        if issymbolic(va):
            logger.debug("Unsupported symbolic VA Dwarf function DIE lookup")
            return None

        # Need to modify va from Manticore's va to what is loaded in the tree
        # Subtract here, because we added before
        va -= self.dyn_base

        func_node = self.func_addr_tree().find(va)
        return (
            func_node
            and self.session.query(self.cpg.MachineFunction).filter_by(name=func_node.label).one()
        )

    def _insn_writing_to_reg(
        self, disasm: Cs, code: bytes, reg_name: str, first: bool
    ) -> Optional[int]:
        """Helper function that finds an instruction writing to register.

        `first` argument decides whether we return with the first occurrence
        (True) or last (False).

        NOTE(ek): This could be done using the CPG and querying those
        instructions to find register reads/writes
        """
        last_write_offset: Optional[int] = None
        insn: CsInsn
        for insn in disasm.disasm(code, 0):
            (_regs_read, regs_write) = insn.regs_access()
            regs_write = [disasm.reg_name(reg_id) for reg_id in regs_write]
            if reg_name.lower() in regs_write:
                last_write_offset = insn.address
                if first:
                    break
        return last_write_offset

    def first_insn_writing_to_reg(self, disasm: Cs, code: bytes, reg_name: str) -> Optional[int]:
        """Find the first instruction that writes to the register reg_name in the given code segment
        with the given disassembler.

        Returns the first offset of the instruction that writes to the register
        or None if no instructions in the range write to the register

        A use case is to find when a function prologue writes to the base
        pointer register that begins the scope of stack-based variables
        """
        return self._insn_writing_to_reg(disasm, code, reg_name, first=True)

    def last_insn_writing_to_reg(self, disasm: Cs, code: bytes, reg_name: str) -> Optional[int]:
        """Find the last instruction that writes to the register in the given code segment.

        Returns the last offset of the instruction that writes to the register
        or None if no instructions in the range write to the register

        A use case is to find when a function prologue writes to the base
        pointer register that ends the scope of stack-based variables
        """
        return self._insn_writing_to_reg(disasm, code, reg_name, first=False)

    def variables_at_va(
        self,
        va: Union[ManticoreAddress, Expression],
        state: State,
        regfile: Optional[RegisterFile] = None,
    ) -> List[MantiDwarfTypeInfo]:
        """Get the variables that are in scope at a Manticore VA.

        :param va: Manticore VA of instruction to be executed
        :param state: Manticore state to look up register values
        :param regfile: Optional register file to use for register values
            instead of from state's
        :return: Mapping of variables where keys are "params" and "vars"
            and the values are custom dictionary that describe the variables
        """
        if regfile is None:
            regfile = state.cpu.regfile

        if issymbolic(va):
            logger.debug("Unsupported symbolic VA Dwarf variables lookup")
            return list()
        norm_va = DwarfAddress(va - self.dyn_base)

        func_name = self.func_name_from_va(va)
        if func_name is None:
            return list()
        try:
            cpg_func = self.session.query(self.cpg.MachineFunction).filter_by(name=func_name).one()
        except NoResultFound:
            return list()

        vars_in_function = variables_for_function(self.session, self.cpg, func_name)

        def _in_scope(_var_summary: MantiDwarfTypeInfo) -> bool:
            _scope = _var_summary.scope
            # flag to check if at least one location is in scope
            loc_in_scope: Optional[bool] = None
            # If this function has a prologue and we're in it, then we need to
            # do some other checking to make sure the prologue has been executed
            # and the variable location is valid if it's a special register
            for loc in _var_summary.locations:
                if isinstance(loc, DWARFAddrLocation):
                    # Always in scope
                    return True
                register_loc: str = loc.reg.upper()
                # * RSP is a special register because the validity of an offset using RBP
                # requires knowing where the function prologue and epilogue are bounded
                assert state.cpu.machine == "amd64", f"Unsupported architecture {state.cpu.machine}"
                last_write_offset: Optional[int]
                if register_loc in {"RSP", "RBP"}:
                    after_real_prologue: bool = True
                    # Check if we're actually after the real prologue
                    if cpg_func.prologues and norm_va < cpg_func.prologues[0][1]:
                        prologue_end_manti = ManticoreAddress(
                            cpg_func.prologues[0][1] + self.dyn_base
                        )
                        prologue_start_manti = ManticoreAddress(
                            cpg_func.prologues[0][0] + self.dyn_base
                        )
                        code = b"".join(
                            state.cpu.read_bytes(
                                prologue_start_manti,
                                prologue_end_manti - prologue_start_manti,
                                force=True,
                                publish=False,
                            )
                        )
                        # Check whether we've written to RSP and it is valid
                        first_write_offset: Optional[int] = self.first_insn_writing_to_reg(
                            state.cpu.disasm.disasm, code, register_loc
                        )
                        last_write_offset = self.last_insn_writing_to_reg(
                            state.cpu.disasm.disasm, code, register_loc
                        )
                        # If the ending prologue va is also the same as the
                        # cpg_func.va_end, then it's just a single basic_block
                        # and we can ignore the first and last offsets being
                        # equal
                        if first_write_offset is None or (
                            first_write_offset == last_write_offset
                            and cpg_func.prologues[0][1] == cpg_func.va_end
                        ):
                            # There are no prologue instructions touching this register or
                            # A 'ret' is the only instruction touching
                            after_real_prologue = True
                        else:
                            after_real_prologue = va > prologue_start_manti + first_write_offset

                    before_real_epilogue: bool = True
                    if cpg_func.epilogues and norm_va > cpg_func.epilogues[0][0]:
                        epilogue_start_manti = ManticoreAddress(
                            cpg_func.epilogues[0][0] + self.dyn_base
                        )
                        epilogue_end_manti = ManticoreAddress(
                            cpg_func.epilogues[0][1] + self.dyn_base
                        )
                        code = b"".join(
                            state.cpu.read_bytes(
                                epilogue_start_manti,
                                epilogue_end_manti - epilogue_start_manti,
                                force=True,
                                publish=False,
                            )
                        )
                        # Check where the last write to the register is (assuming the function cleans itself up)
                        last_write_offset = self.last_insn_writing_to_reg(
                            state.cpu.disasm.disasm, code, register_loc
                        )
                        if last_write_offset is None:
                            # There are no epilogue instructions touching this register
                            before_real_epilogue = True
                        else:
                            before_real_epilogue = va < epilogue_start_manti + last_write_offset

                    valid_in_body = after_real_prologue and before_real_epilogue
                    if loc_in_scope is None:
                        loc_in_scope = valid_in_body
                    else:
                        loc_in_scope |= valid_in_body

            if loc_in_scope is None:
                return _scope.va_start <= norm_va < _scope.va_end
            return loc_in_scope and (_scope.va_start <= norm_va < _scope.va_end)

        # Get values of variables
        # TODO(ek): Should there be another function to actually resolve the values of the variables?
        inscope_vars: List[MantiDwarfTypeInfo] = list()

        for cpg_var in vars_in_function:
            var: MantiDwarfTypeInfo = var_info_to_manti_info(
                self.session, self.cpg, cpg_var, cpg_func
            )

            if not _in_scope(var):
                continue

            locs = var.locations
            base_type = var.base_type
            vals = []
            for loc in locs:
                if isinstance(loc, DWARFAddrLocation):
                    # Directly addressable location
                    vals.append(loc.address + self.dyn_base)
                else:
                    # Check if this location info is valid (in scope)
                    if (
                        loc.va_start is None and loc.va_end is None
                    ) or loc.va_start + self.dyn_base <= regfile.read(
                        "PC"
                    ) < loc.va_end + self.dyn_base:
                        vals.append(regfile.read(loc.reg.upper()) + (loc.offset or 0))
            # concrete location could be on the stack or heap or in a register
            var.location_conc = vals
            if var.indirections == 0:
                # TODO(ekilmer): Test other primitive types
                if base_type == "int":
                    var.values = vals
                elif base_type == "char":
                    var.values = vals
            else:
                # TODO(ekilmer): Handle pointers. Let's not follow any
                #  indirections because we don't know at any arbitrary point
                #  whether the pointer is valid
                pass
                # for _ in range(var.indirections):
                #    try:
                #        vals = [state.cpu.read_int(val, publish=False) for val in vals]
                #    except InvalidMemoryAccess as e:
                #        logger.warning(
                #            f"Caught invalid memory read (@{regfile.read('PC'):#x} while lookup location of {var=}\n{cpg_var=}"
                #        )
                #        raise e
                # var.values = vals

            inscope_vars.append(var)

        return inscope_vars

    def source_info_from_va(self, binary_path: str, va: ManticoreAddress) -> SourceCodeInfo:
        return source_info_from_va(self.session, self.cpg, binary_path, va)


def variables_for_function(session: Session, cpg: Graph, func_name: str) -> List:
    """Return all variables this function could access during execution.

    This includes locals, arguments, and globals

    :param cpg: CPG handle
    :param func_name: Function name to lookup
    :return: List of variables that the function could access
    """
    mi_func = aliased(cpg.MachineFunction)
    function_vars = []
    try:
        mi_func_obj: MachineFunction = (
            session.query(mi_func).filter(mi_func.name == func_name).one()
        )
        function_vars.extend(mi_func_obj.local_variables)
        function_vars.extend(mi_func_obj.arguments)
    except NoResultFound:
        pass
    return function_vars + session.query(cpg.ASMGlobalVariable).all()


def _func_addr_tree(session: Session, cpg: Graph) -> RangeAVL:
    """An AVL tree with the range of DWARF VAs for every function in the CPG.

    :param cpg_info: Function information from the CPG
    :return: RangeAVL tree with DWARF VA ranges as keys pointing to function
        names
    """
    tree = RangeAVL()
    for machine_func in session.query(cpg.MachineFunction).all():
        tree.insert(machine_func.va_start, machine_func.va_end, machine_func.name)

    return tree
