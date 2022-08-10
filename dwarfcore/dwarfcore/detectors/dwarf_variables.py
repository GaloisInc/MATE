from typing import Final, List, Optional, Union

from capstone import CsInsn
from manticore import issymbolic
from manticore.core.plugin import Plugin
from manticore.core.smtlib import Expression
from manticore.native.cpu.disasm import Instruction
from manticore.native.state import State

import dwarfcore.logging
from dwarfcore.detectors.common import (
    record_concretize_state_vars,
    stack_mem_access,
    variable_at_memory,
)
from dwarfcore.dwarfcore import DwarfCore, ManticoreAddress
from dwarfcore.plugins.dwarf_track_variables import DwarfTrackVariables
from mate_common.models.integration import Detector, ReachingTestCase

logger = dwarfcore.logging.logger


class DwarfVariables(Plugin):
    """Print information about reads and writes to source-level variables on each instruction."""

    """
    Point of interest functions (mangled names) that will activate this plugin
    when Manticore is executing within them.
    """
    poi_funcs: Optional[List[str]]

    """Manticore context key for holding testcases by this detector"""
    MCORE_TESTCASE_LIST: Final[str] = "DwarfVariables_testcases"

    def __init__(
        self, dwarfcore: DwarfCore, poi_funcs: Optional[List[str]] = None, fast: bool = True
    ):
        """Initialize the Plugin.

        :param dwarfcore: An instance to a DwarfCore object that will be used
            for context
        :param poi_funcs: A list of functions (mangled names) that will be used
            for examining variable bounds. If this is omitted or None, the
            plugin will operate on every function
        :param fast: This plugin will stop Manticore when first detection is
            made instead of letting Manticore continue with exploration.
        """
        super().__init__()
        self.dwarfcore = dwarfcore
        self.fast = fast
        # Point of interest functions
        self.poi_funcs = poi_funcs if poi_funcs else None
        # Set up some functionality for grabbing variable information
        self._track_variables = DwarfTrackVariables(dwarfcore, poi_funcs)

    @property
    def results(self) -> List[ReachingTestCase]:
        """Any test case results found during execution."""
        with self.manticore.locked_context() as context:
            return context.get(self.MCORE_TESTCASE_LIST, list())

    def stack_mem_access(self, state: State, where: int) -> bool:
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

    def record_testcase(self, state: State, message: str):
        with state as tmp:
            testcase = ReachingTestCase(
                description=message,
                detector_triggered=Detector.VariableBoundsAccess,
                symbolic_inputs=record_concretize_state_vars(tmp, state.id),
            )
            with tmp.manticore.locked_context() as context:
                case_list = context.get(self.MCORE_TESTCASE_LIST, list())
                case_list.append(testcase)
                context[self.MCORE_TESTCASE_LIST] = case_list

        # Generate a testcase using Manticore's internal machinery
        self.manticore.generate_testcase(state, message)

    def _is_symb_mem_access_oob(self, state: State, insn: Instruction, where: Expression) -> bool:
        """Check if the memory access expression by the given instruction can access out-of-bounds
        variable memory given the current inscope variables as defined by state context key
        `INSCOPE_VARS_KEY` and symbolic `where`.

        :param state: Specified Manticore State
        :param insn: Instruction causing memory access
        :param where: Symbolic memory access location
        :return: Whether the memory access is out of bounds
        """
        inscope_vars = state.context[self._track_variables.INSCOPE_VARS_KEY]
        func_name = state.context[self._track_variables.CURR_FUNC_KEY]

        # Assuming `where` is symbolic, let's solve for the extreme bounds of minimum and maximum
        # This is a location in memory (likely on stack or heap or global space)
        min_mem, max_mem = state.solve_minmax(where)

        # Keep track if we ever create a testcase
        is_oob = False

        # Check for whether the memory access is into the stack or heap
        if not stack_mem_access(state, min_mem) and not stack_mem_access(state, max_mem):
            logger.debug("Skipping check for invalid memory access outside of stack")
            return is_oob

        # state.cpu.PC is not the real PC of the instruction making the memory access
        # (Used for logging purposes)
        insn_pc = insn.address
        source_info = self.dwarfcore.source_info_from_va(state.platform.program, insn_pc)
        log_prefix = f"{insn_pc:#x} within function: '{func_name}'@{source_info}: "

        # Check variable at min value memory location
        # min_var is either details about a variable or None if no variable at memory location
        min_var = variable_at_memory(min_mem, state, inscope_vars)
        if min_var is None:
            # Use temporary state, so that Manticore can continue after we're done
            with state as temp:
                temp.constrain(where == min_mem)
                msg = f"{log_prefix} Symbolic memory access could be out of bounds lower ({min_mem:#x}, state {state.id})"
                logger.debug(f"[{state.id}] {msg}")
                # Record our findings
                self.record_testcase(temp, msg)
            is_oob = True

        # Check variable at max value memory location
        # max_var is either details about a variable or None if no variable at memory location
        max_var = variable_at_memory(max_mem, state, inscope_vars)
        if max_var is None:
            with state as temp:
                temp.constrain(where == max_mem)
                msg = f"{log_prefix} Symbolic memory access could be out of bounds upper ({max_mem:#x}, state {state.id})"
                logger.debug(f"[{state.id}] {msg}")
                # Record our findings
                self.record_testcase(temp, msg)
            is_oob = True

        # With the min and max variables known, check if they point to different variables
        # Different includes if one is None and the other points to a valid variable
        if min_var != max_var:
            # TODO(ek): is there some way to determine which was the "correct" variable that was supposed to accessed?
            topmsg = f"{log_prefix} Symbolic memory access could be out of bounds upper ({max_mem:#x}) or lower ({min_mem:#x}), state {state.id}"
            logger.debug(f"[{state.id}] {topmsg}")
            with state as temp:
                submsg = f"Upper ({max_mem:#x}) points to variable: {max_var}"
                msg = f"{topmsg}\n{submsg}"
                logger.debug(f"[{state.id}] {submsg}:")
                temp.constrain(where == max_mem)
                # Record our findings
                self.record_testcase(temp, msg)
            with state as temp:
                submsg = f"Lower ({min_mem:#x}) points to variable: {min_var}"
                msg = f"{topmsg}\n{submsg}"
                logger.debug(f"[{state.id}] {submsg}")
                temp.constrain(where == min_mem)
                # Record our findings
                self.record_testcase(temp, msg)
            is_oob = True

        return is_oob

    def _is_conc_mem_access_oob(
        self, state: State, insn: Instruction, where: ManticoreAddress, size: int
    ) -> bool:
        """Check if the memory access expression by the given instruction can access out-of-bounds
        variable memory given the current inscope variables as defined by state context key
        `INSCOPE_VARS_KEY` and concrete `where`.

        :param state: Specified Manticore State
        :param insn: Instruction causing memory access
        :param where: Concrete location of memory access
        :param size: Concrete size of access to `where`
        :return: Whether the memory access is out of bounds
        """
        inscope_vars = state.context[self._track_variables.INSCOPE_VARS_KEY]
        func_name = state.context[self._track_variables.CURR_FUNC_KEY]

        insn_pc = insn.address
        source_info = self.dwarfcore.source_info_from_va(state.platform.program, insn_pc)
        log_prefix = f"{insn_pc:#x} within function: '{func_name}'@{source_info}: "

        min_mem = where
        # Inclusive max_mem
        max_mem = where + (size // 8) - 1
        min_var = variable_at_memory(ManticoreAddress(min_mem), state, inscope_vars)
        max_var = variable_at_memory(ManticoreAddress(max_mem), state, inscope_vars)

        # Keep track if we ever create a testcase
        is_oob = False

        if min_var is None:
            msg = f"{log_prefix} Concrete memory access could be out of bounds lower ({min_mem:#x})"
            # Record our findings
            self.record_testcase(state, msg)
            is_oob = True
            logger.debug(f"[{state.id}] {msg}")

        if max_var is None:
            msg = f"{log_prefix} Concrete memory access could be out of bounds upper ({max_mem:#x})"
            # Record our findings
            self.record_testcase(state, msg)
            is_oob = True
            logger.debug(f"[{state.id}] {msg}")

        if min_var != max_var:
            topmsg = f"{log_prefix} Concrete memory access could be out of bounds upper ({max_mem:#x}) or lower ({min_mem:#x})"
            logger.debug(f"[{state.id}] {topmsg}")

            # Upper variable details
            submsg = f"Upper ({max_mem:#x}) points to variable: {max_var}"
            msg = f"{topmsg}\n{submsg}"
            logger.debug(f"[{state.id}] {submsg}:")
            # Record our findings
            self.record_testcase(state, msg)

            # Lower variable details
            submsg = f"Lower ({min_mem:#x}) points to variable: {min_var}"
            msg = f"{topmsg}\n{submsg}"
            logger.debug(f"[{state.id}] {submsg}:")
            # Record our findings
            self.record_testcase(state, msg)
            is_oob = True

        return is_oob

    def is_mem_access_oob(
        self,
        state: State,
        insn: Instruction,
        where: Union[int, Expression],
        size: Union[int, Expression],
    ) -> None:
        """Check if the memory access expression by the given instruction can access out-of-bounds
        variable memory given the current inscope variables as defined by state context key
        `INSCOPE_VARS_KEY`.

        If an out of bounds memory access is found, the state is abandoned and a test case is generated to reproduce
        the memory access.

        :param state: Specified Manticore State
        :param insn: Instruction causing memory access
        :param where: Memory access location
        :param size: Size of the memory access
        """
        inscope_vars = state.context[self._track_variables.INSCOPE_VARS_KEY]
        func_name = state.context[self._track_variables.CURR_FUNC_KEY]
        if not inscope_vars or not func_name or len(inscope_vars) == 0:
            return

        is_oob = False

        # TODO(ek): We currently don't use `size` for symbolic detection because `size` is never symbolic in the
        #   currently published events. However, if it is
        assert not issymbolic(size), "Weird. size should not be symbolic."

        if issymbolic(where):
            is_oob = self._is_symb_mem_access_oob(state, insn, where)
        else:
            pass
            # TODO(ek): This will likely catch ALOT of test cases due to the concretization and number of paths
            #   that manticore finds. Not sure yet what the best strategy is for handling these cases in a usable way.
            #   - Maybe have some way to determine if multiple states had the same path and got here again?
            #   - Sometimes Manticore system calls just concretize symbolic arguments, and we lose them when they
            #   get to a spot here, so a DWARF trace path with syscall interleaving would be interesting
            # is_oob = self._is_conc_mem_access_oob(state, insn, where, size)
        if is_oob:
            if self.fast:
                state.manticore.kill()
            state.abandon()

    def will_read_memory_callback(
        self, state: State, where: Union[int, Expression], size: Union[int, Expression]
    ):
        """Look at the variable, index, and values that we are reading from memory."""
        # Will need to look at instruction and PC to determine our context in the program (or set property)
        # Detectors:
        #   * Look for out of bounds reads of current variable
        insn: CsInsn = state.cpu.instruction
        self.is_mem_access_oob(state, insn, where, size)

    def will_write_memory_callback(
        self,
        state: State,
        where: Union[int, Expression],
        _expression: Union[int, Expression],
        size: Union[int, Expression],
    ):
        """Look at the variable, index, and values that we are writing to memory."""
        # Will need to look at instruction and PC to determine our context in the program (or set property)
        # Detectors:
        #   * Look for out of bounds writes to current variable
        insn: CsInsn = state.cpu.instruction
        self.is_mem_access_oob(state, insn, where, size)

    def will_execute_instruction_callback(
        self, state: State, pc: Union[int, Expression], insn: Instruction
    ):
        """Manticore instruction callback to determine which function we are executing within."""
        self._track_variables.will_execute_instruction_callback(state, pc, insn)
