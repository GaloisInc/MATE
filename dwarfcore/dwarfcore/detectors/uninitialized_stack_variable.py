import bisect
from dataclasses import dataclass
from typing import Dict, Final, List, Optional, Union

from manticore import issymbolic
from manticore.core.plugin import Plugin
from manticore.core.smtlib import Expression
from manticore.native.cpu.disasm import Instruction
from manticore.native.state import State

import dwarfcore.logging
from dwarfcore.detectors.common import (
    CallStackFrame,
    FoundVarInfo,
    VariableAtMemoryInfo,
    record_concretize_state_vars,
    variable_at_memory,
)
from dwarfcore.dwarfcore import DwarfCore, ManticoreAddress
from dwarfcore.plugins.dwarf_track_variables import DwarfTrackVariables
from mate.build.tob_chess_utils.dwarf import (
    UNROLLABLE_CPG_DT_TYPES,
    FieldOffset,
    MantiDwarfTypeInfo,
    unroll_nested_type_fields,
)
from mate_common.models.integration import Detector, FunctionVariableInfo, ReachingTestCase

logger = dwarfcore.logging.logger


def _nested_var(base_name: str, base_var: MantiDwarfTypeInfo) -> MantiDwarfTypeInfo:
    nested_types = base_name.split(".")
    this_var = base_var
    # Take care of nested types
    for nested in nested_types[1:]:
        for child in this_var.child_vars:
            if nested == child.name:
                this_var = child
                break
    return this_var


def get_var_element_access_names(
    where: ManticoreAddress, var_at_where: VariableAtMemoryInfo, size: int
) -> List[str]:
    """Determine the refined name element name variable accessed at a specific location.

    :param where: The memory access made by Manticore
    :param var_at_where: The variable containing the Manticore access
    :param size: The size of the access
    :return: name with element number
    """
    base_name: str = var_at_where.name
    base_var: MantiDwarfTypeInfo = var_at_where.var
    # Keep track of the variable type this name points to
    this_var: MantiDwarfTypeInfo = _nested_var(base_name, base_var)
    # Offset into _this_ potentially nested variable's type
    offset = where - var_at_where.min_mem
    this_var_max_addr = var_at_where.max_mem
    this_var_min_addr = var_at_where.min_mem
    var_is_padding = var_at_where.padding

    accessed_names: List[str] = list()

    # Loop through each byte/variable of the field accesses until we have
    # consumed the total size of the access
    while size > 0:
        access_addr = ManticoreAddress(where)
        if access_addr >= this_var_max_addr or var_is_padding:
            var_is_padding = False
            # Get the top-most parent type for this variable
            while this_var.parent_var is not None:
                this_var = this_var.parent_var
            # NOTE: Somewhat duplicated at 'variable_at_memory'
            if this_var.base_type in UNROLLABLE_CPG_DT_TYPES:
                # We can expand and look at the field mem ranges of this type
                unrolled_fields = unroll_nested_type_fields(this_var)
                field_offsets = [
                    fo.offset + var_at_where.parent_min_mem for fo in unrolled_fields.field_offsets
                ]
                try:
                    # Loop through the variable trying to find the first
                    # non-padding field or we consume the whole access size
                    while True:
                        if size <= 0:
                            return accessed_names or []
                        field_var: FieldOffset = unrolled_fields.field_offsets[
                            bisect.bisect_right(field_offsets, access_addr) - 1
                        ]
                        field_mem_addr = ManticoreAddress(
                            var_at_where.parent_min_mem + field_var.offset
                        )
                        # Skip padding fields
                        if field_var.field.padding:
                            logger.debug(
                                f"Skipping memory access to padding field in struct at offset {field_var.offset}"
                            )
                            size -= field_var.field.size
                            where += field_var.field.size
                            access_addr = ManticoreAddress(where)
                            continue
                        break
                    # Set new variables
                    offset = 0
                    this_var_min_addr = field_mem_addr
                    this_var_max_addr = ManticoreAddress(field_mem_addr + field_var.field.size)
                    base_name = field_var.field.name.full_name
                    this_var = _nested_var(base_name, base_var)
                except IndexError:
                    logger.error(
                        f"Cannot find variable at address {access_addr}. Should not happen."
                    )
                    break

        # TODO(ek): This should be some type of enum
        if this_var.base_type == "array":
            element_size = this_var.base_type_size
            # it's just the first element (this works even for nested types)
            if where + offset == this_var_min_addr:
                ele_name = f"{base_name}[0]"
            else:
                # Figure out which element if not the first
                if offset % element_size != 0:
                    logger.warning(
                        "Weird offset in middle of array element: "
                        f"offset={offset} element_size={element_size}"
                    )
                ele_name = f"{base_name}[{offset // element_size}]"
            accessed_names.append(ele_name)
        else:
            if where != this_var_min_addr:
                logger.warning(
                    "Manticore is accessing a variable in a location that is not the beginning:\n\t"
                    f"Manticore@{ManticoreAddress(where)} {this_var.name}@{this_var_min_addr}-{this_var_max_addr}\n\t"
                    f"variable info: {var_at_where}"
                )
            # TODO(ek): Need to get size of pointer in here somehow
            element_size = this_var.total_size if this_var.indirections == 0 else size
            accessed_names.append(base_name)

        size -= element_size
        offset += element_size
        where += element_size
    return accessed_names or [base_name]


class DetectUninitializedStackVariable(Plugin):
    """Detect uninitialized stack variables by tracking reads and writes."""

    """Manticore context key for holding testcases by this detector"""
    MCORE_TESTCASE_LIST: Final[str] = "UninitializedVariable_testcases"

    @property
    def VAR_WRITE_KEY(self) -> str:
        """Whether a variable has been written to in the current function.

        Value at this key is an Optional[Dict[str,bool]] type
        """
        return f"{self.__class__.__name__}_var_write_flags"

    @property
    def results(self) -> List[ReachingTestCase]:
        """Any test case results found during execution."""
        with self.manticore.locked_context() as context:
            return context.get(self.MCORE_TESTCASE_LIST, list())

    @property
    def TARGET_FUNCTION_IS_LIVE_KEY(self) -> str:
        """Whether the target function is live during program execution.

        This is not exact information since we only look at whether the target
        function is on the call stack.

        Used mostly for efficiency to avoid needless variable range lookups
        through the call stack, which is expensive.
        """
        return f"{self.__class__.__name__}_target_function_is_live"

    @property
    def RESULTS_KEY(self) -> str:
        """The plugin's key to access results.

        :return: Key name to access results
        """
        return f"{self.__class__.__name__}_results"

    @dataclass(frozen=True, eq=True)
    class Result:
        """Result data structure for uninitialized stack variables."""

        function_name: str
        variable_name: str
        instruction_addr: ManticoreAddress
        # C-like representation of the variable that was detected
        variable_pretty: str
        file_path: str
        line_number: int

    def __init__(
        self,
        dwarfcore: DwarfCore,
        poi_info: Optional[List[FunctionVariableInfo]],
        fast: bool = True,
    ):
        """Initialize the Plugin.

        :param dwarfcore: An instance to a DwarfCore object that will be used
            for context
        :param poi_info: A list of functions (mangled names) that will be used
            for examining variable bounds. If this is omitted or None or empty
            list, the plugin will operate on every function
        :param fast: This plugin will stop Manticore when first detection is
            made instead of letting Manticore continue with exploration.
        """
        super().__init__()
        self.dwarfcore = dwarfcore
        self.fast = fast
        # Point of interest functions
        self.poi_info = poi_info if poi_info else None
        # Set up some functionality for grabbing variable information
        self._track_variables = DwarfTrackVariables(
            dwarfcore, [poi.function_name for poi in poi_info] if poi_info else None
        )

    def record_testcase(self, state: State, message: str):
        with state as tmp:
            testcase = ReachingTestCase(
                description=message,
                detector_triggered=Detector.UninitializedVar,
                symbolic_inputs=record_concretize_state_vars(tmp, state.id),
            )
            with tmp.manticore.locked_context() as context:
                case_list = context.get(self.MCORE_TESTCASE_LIST, list())
                case_list.append(testcase)
                context[self.MCORE_TESTCASE_LIST] = case_list

        # Generate a testcase using Manticore's internal machinery
        self.manticore.generate_testcase(state, message)

    def will_execute_instruction_callback(
        self, state: State, pc: Union[int, Expression], insn: Instruction
    ):
        """Manticore instruction callback to determine which function we are executing within."""
        # TODO(ek): Should this Detector inherit from DwarfTrackVariables? How would multiple inheritance work

        # Keep track of any changes to the call stack
        old_call_stack: List[CallStackFrame] = state.context.get(
            self._track_variables.CALL_STACK_KEY, []
        )
        old_call_stack_len = len(old_call_stack)
        old_frame: Optional[CallStackFrame] = None
        old_writes: Dict[str, bool] = dict()
        if old_call_stack_len > 0:
            old_frame = old_call_stack[-1]
            old_writes = old_frame.other_data.get(self.VAR_WRITE_KEY, dict())

        # Update the call stack and other variable tracking info
        self._track_variables.will_execute_instruction_callback(state, pc, insn)

        call_stack: List[CallStackFrame] = state.context.get(
            self._track_variables.CALL_STACK_KEY, list()
        )
        call_stack_len = len(call_stack)
        # Check whether a new frame was pushed
        if old_call_stack_len < call_stack_len:
            assert len(call_stack) > 0
            # Make sure we have something to save
            var_writes = state.context.get(self.VAR_WRITE_KEY, dict())
            new_call_frame = call_stack[-1]
            new_call_frame.other_data[self.VAR_WRITE_KEY] = var_writes
            state.context[self.VAR_WRITE_KEY] = dict()
            # Check if our targets are live now. Only executes when stack has a
            # push _and_ when we are now executing in the target func
            if self.poi_info is None or new_call_frame.func_name in {
                poi.function_name for poi in self.poi_info
            }:
                # Increment our flag to indicate we should still check mem reads/writes
                live_count = state.context.get(self.TARGET_FUNCTION_IS_LIVE_KEY, 0)
                state.context[self.TARGET_FUNCTION_IS_LIVE_KEY] = live_count + 1
        # Check whether a frame was popped
        elif old_call_stack_len > call_stack_len:
            state.context[self.VAR_WRITE_KEY] = old_writes
            # Decrement our flag if we popped a target function for whether to
            # check mem reads/writes
            if old_frame and (
                self.poi_info is None
                or old_frame.func_name in {poi.function_name for poi in self.poi_info}
            ):
                old_live_count = state.context.get(self.TARGET_FUNCTION_IS_LIVE_KEY)
                assert old_live_count and old_live_count > 0
                state.context[self.TARGET_FUNCTION_IS_LIVE_KEY] = old_live_count - 1
        else:
            # Edge case: set live flag if the first function call is our target
            if (
                call_stack_len == 0
                and not state.context.get(self.TARGET_FUNCTION_IS_LIVE_KEY)
                and (
                    self.poi_info is None
                    or state.context[self._track_variables.CURR_FUNC_KEY]
                    in {poi.function_name for poi in self.poi_info}
                )
            ):
                state.context[self.TARGET_FUNCTION_IS_LIVE_KEY] = 1

    def _variables_at_where(self, state: State, where: ManticoreAddress) -> List[FoundVarInfo]:
        """Find all program variables in memory at 'where'.

        :param state: The Manticore state to use for register value lookups
        :param where: The Manticore memory address being accessed
        :return: All (aliased, from the call stack) variables that occupy this
            address in memory
        """
        inscope_vars = state.context.get(self._track_variables.INSCOPE_VARS_KEY, list())
        func_name = state.context.get(self._track_variables.CURR_FUNC_KEY, None)

        # Return early if some preconditions aren't met
        if not state.context.get(self.TARGET_FUNCTION_IS_LIVE_KEY) and (
            self.poi_info is not None
            and func_name not in {poi.function_name for poi in self.poi_info}
        ):
            return list()

        vars_at_where: List[FoundVarInfo] = list()

        # Normal case when we are executing within the function of interest
        if inscope_vars and (
            self.poi_info is None or func_name in {poi.function_name for poi in self.poi_info}
        ):
            var_at_mem = variable_at_memory(where, state, inscope_vars)
            if var_at_mem is not None and (
                self.poi_info is None
                or any(var_at_mem.name.startswith(poi.variable_name) for poi in self.poi_info)
            ):
                vars_at_where.append(
                    FoundVarInfo(var_at_mem, state.context.get(self.VAR_WRITE_KEY, dict()), None)
                )

        # Other case where memory accesses in called functions could influence
        # the variables in our target poi function(s)
        if state.context.get(self.TARGET_FUNCTION_IS_LIVE_KEY):
            # TODO(ek): Verify this is what we want for recursive functions
            call_stack = state.context.get(self._track_variables.CALL_STACK_KEY, [])
            target_frames: List[CallStackFrame] = [
                frame
                for frame in call_stack
                if self.poi_info is None
                or frame.func_name in {poi.function_name for poi in self.poi_info}
            ]
            # Look at all frames in the call stack to determine if and which
            # variables are at this location
            for frame in target_frames:
                regfile = frame.register_state
                inscope_vars = frame.inscope_variables
                var_at_mem = variable_at_memory(where, state, inscope_vars, regfile)
                if var_at_mem is not None and (
                    self.poi_info is None
                    or any(var_at_mem.name.startswith(poi.variable_name) for poi in self.poi_info)
                ):
                    vars_at_where.append(
                        FoundVarInfo(var_at_mem, frame.other_data[self.VAR_WRITE_KEY], frame)
                    )

        return vars_at_where

    def will_read_memory_callback(
        self, state: State, where: Union[int, Expression], size: Union[int, Expression]
    ):
        if issymbolic(size):
            logger.warning(
                f"Got symbolic size for memory read. Skipping instruction {state.cpu.instruction}"
            )
            return
        if issymbolic(where):
            logger.warning(
                f"Got symbolic where for memory read in uninit variable detector. Skipping instruction {state.cpu.instruction}"
            )
            return
        # NOTE: Size is in bits
        size = size // 8
        where = ManticoreAddress(where)

        vars_at_where = self._variables_at_where(state, where)

        # Check if we don't match with any of our poi variables
        found_var_names = set()
        for var_at_where in vars_at_where:
            found_var_names.add(var_at_where.found_var.name)
            found_var_names.add(var_at_where.found_var.var.name)
        if len(vars_at_where) == 0 or (
            self.poi_info is not None
            and all(poi_info.variable_name not in found_var_names for poi_info in self.poi_info)
        ):
            return

        for target_var in vars_at_where:
            var_access_names = get_var_element_access_names(where, target_var.found_var, size)
            for var_access_name in var_access_names:
                did_write_var = target_var.var_write_info.get(var_access_name)
                instruction_address = ManticoreAddress(state.cpu.instruction.address)
                source_info = self.dwarfcore.source_info_from_va(
                    state.platform.program, instruction_address
                )

                func_var_owner = state.context[self._track_variables.CURR_FUNC_KEY]
                if target_var.call_frame:
                    func_var_owner = target_var.call_frame.func_name

                # If _any_ of our tracked variables were written, then we immediately exit.
                # This is here because we have different information for each `target_var`
                # even though they're pointing to the same underlying memory space
                if did_write_var:
                    logger.info(
                        f"Variable {var_access_name}@'{func_var_owner}' was written before reading ({source_info})"
                    )
                    return

        # TODO(ek): Ignore variables initialized outside of our view
        if var_access_name in {"argc", "argv"} and func_var_owner == "main":
            return

        msg = (
            f"Found stack variable use before initialization {var_access_name}@'{func_var_owner}' @ "
            f"{instruction_address}! ({source_info})"
        )
        self.record_testcase(state, msg)

        # TODO(ek): Merge this into the record_testcase call above
        with self.manticore.locked_context(self.RESULTS_KEY, list) as results:
            func_name = state.context[self._track_variables.CURR_FUNC_KEY]
            if target_var.call_frame:
                func_name = target_var.call_frame.func_name
            results.append(
                self.Result(
                    func_name,
                    target_var.found_var.name,
                    instruction_address,
                    var_access_name,
                    source_info.path,
                    source_info.line,
                )
            )

        if self.fast:
            state.abandon()
            state.manticore.kill()

    def will_write_memory_callback(
        self,
        state: State,
        where: Union[int, Expression],
        expression: Union[int, Expression],
        size: Union[int, Expression],
    ):
        if issymbolic(size):
            logger.warning(
                f"Got symbolic size for memory write. Skipping instruction {state.cpu.instruction}"
            )
            return
        if issymbolic(where):
            logger.warning(
                f"Got symbolic where for memory write in uninit variable detector. Skipping instruction {state.cpu.instruction}"
            )
            return
        # NOTE: Size is in bits
        size = size // 8
        where = ManticoreAddress(where)

        # Get a list of all aliased variables across the call stack where
        # Manticore is writing
        vars_at_where = self._variables_at_where(state, where)

        # Check if we don't match with any of our poi variables
        found_var_names = set()
        for var_at_where in vars_at_where:
            found_var_names.add(var_at_where.found_var.name)
            found_var_names.add(var_at_where.found_var.var.name)
        if len(vars_at_where) == 0 or (
            self.poi_info is not None
            and all(poi_info.variable_name not in found_var_names for poi_info in self.poi_info)
        ):
            return

        # Set the flag to True to indicate that we've written to the variable(s)
        for target_var in vars_at_where:
            var_access_names = get_var_element_access_names(where, target_var.found_var, size)
            for var_access_name in var_access_names:
                target_var.var_write_info[var_access_name] = True
                va = ManticoreAddress(state.cpu.instruction.address)
                source_info = self.dwarfcore.source_info_from_va(state.platform.program, va)

                func_var_owner = state.context[self._track_variables.CURR_FUNC_KEY]
                if target_var.call_frame:
                    func_var_owner = target_var.call_frame.func_name
                logger.info(
                    f"Writing {var_access_name}@'{func_var_owner}' = {expression} @ {va} ({source_info})"
                )
