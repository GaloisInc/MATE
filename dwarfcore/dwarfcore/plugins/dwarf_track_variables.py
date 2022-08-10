import copy
from typing import TYPE_CHECKING, List, Optional, Union

from manticore.core.smtlib import Expression
from manticore.native.cpu.disasm import Instruction
from manticore.native.state import State

import dwarfcore.logging
from dwarfcore.detectors.common import CallStackFrame
from dwarfcore.dwarfcore import DwarfCore, ManticoreAddress
from mate.build.tob_chess_utils.dwarf import MantiDwarfTypeInfo

if TYPE_CHECKING:
    from mate_query.cpg.models import MachineFunction

logger = dwarfcore.logging.logger


class DwarfTrackVariables:
    """Track variable information during execution."""

    """
    Point of interest functions (mangled names) that will activate this plugin
    when Manticore is executing within them.
    """
    poi_funcs: Optional[List[str]]

    def __init__(self, dwarfcore: DwarfCore, poi_funcs: Optional[List[str]] = None):
        """Initialize the Plugin.

        :param dwarfcore: An instance to a DwarfCore object that will be used
            for context
        :param poi_funcs: Optional list of function names to gather variable information.
            If None or empty, then will collect variable information at all functions.
        """
        self.dwarfcore = dwarfcore
        self.poi_funcs = poi_funcs if poi_funcs else None

    @property
    def CALL_STACK_KEY(self) -> str:
        """Key to look up call stack, implemented as a List."""
        return f"{self.__class__.__name__}_call_stack"

    @property
    def CURR_FUNC_KEY(self) -> str:
        """Current function context key.

        Value at this key is an Optional[string] type.
        """
        return f"{self.__class__.__name__}_curr_func"

    @property
    def INSCOPE_VARS_KEY(self) -> str:
        """In-scope variables context key.

        Value at this key is dictionary of variables by string name key, and VariableInfo type
        """
        return f"{self.__class__.__name__}_inscope_vars"

    @property
    def LAST_PROCESSED_INSN_ADDRESS_KEY(self) -> str:
        """The last processed instruction address will be stored at this key.

        This is to help prevent duplication of processing when multiple plugins are active.
        :return: Key that can be used to retrieve a Manticore address
        """
        return f"{self.__class__.__name__}_last_processed_insn_address"

    def will_execute_instruction_callback(
        self, state: State, pc: Union[int, Expression], _insn: Instruction
    ):
        """Manticore instruction callback to determine which function we are executing within.

        Needs to be called from a real plugin
        """
        pc = ManticoreAddress(pc)
        c = state.context

        # Check if we need to do any processing
        if c.get(self.LAST_PROCESSED_INSN_ADDRESS_KEY) == pc:
            return
        c[self.LAST_PROCESSED_INSN_ADDRESS_KEY] = pc

        # Find where we are in the program
        check_func_name: Optional[str] = self.dwarfcore.func_name_from_va(pc)
        # Make sure we have info too, in case it's a dynamic/relocation symbol
        check_func_info: Optional[MachineFunction] = self.dwarfcore.va_to_func_in_cpg(pc)

        # Defaults for resetting context
        current_func = None
        # Save the fact that we visited a function with Dwarf info
        if check_func_info is not None:
            current_func = check_func_name

        inscope_vars: List[MantiDwarfTypeInfo] = list()
        # Either we collect info for all functions or just the points of interest
        if (
            self.poi_funcs is None or check_func_name in self.poi_funcs
        ) and check_func_name is not None:
            inscope_vars = self.dwarfcore.variables_at_va(pc, state)

        # Update call stack if needed
        previous_func = c.get(self.CURR_FUNC_KEY)
        # TODO(ek): What about recursive calls?
        # TODO(ek): What about JMPs? Control-flow won't necessarily return back to
        #   the instruction after it
        # TODO(ek): What about functions with multiple exit points?
        if check_func_name != previous_func:
            # If we're returning back from a known function
            ret_addr = c.get(self.CALL_STACK_KEY) and c[self.CALL_STACK_KEY][-1].return_va
            if pc == ret_addr:
                prev_frame: CallStackFrame = c[self.CALL_STACK_KEY].pop()
                logger.info(f"Returned to function: {prev_frame.func_name}, state {state.id}")
            elif previous_func is not None:
                if check_func_name:
                    logger.info(f"Calling function: {check_func_name}, state {state.id}")
                c.setdefault(self.CALL_STACK_KEY, []).append(
                    CallStackFrame(
                        previous_func,
                        ManticoreAddress(state.cpu.last_executed_pc),
                        ManticoreAddress(
                            state.cpu.last_executed_pc + state.cpu.last_executed_insn.size
                        ),
                        copy.copy(state.cpu.regfile),
                        c.get(self.INSCOPE_VARS_KEY, list()),
                    )
                )
            else:
                # Useful before any call stack
                unknown_ret_addr = " (unknown return)" if not check_func_info else ""
                if check_func_name:
                    logger.info(f"Calling function{unknown_ret_addr}: {check_func_name}")

        # set the context for other manticore hooks
        c[self.INSCOPE_VARS_KEY] = inscope_vars
        c[self.CURR_FUNC_KEY] = current_func
