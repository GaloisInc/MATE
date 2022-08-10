import csv
from typing import NamedTuple, Union

from manticore import Plugin
from manticore.core.smtlib import Expression
from manticore.native.cpu.disasm import Instruction
from manticore.native.state import State

import dwarfcore.logging
from dwarfcore.dwarfcore import DwarfCore, ManticoreAddress

logger = dwarfcore.logging.logger


class TraceFunction(NamedTuple):
    function: str
    address: ManticoreAddress


class DwarfTrace(Plugin):
    """Print more detailed information about which function is currently being executed in our
    trace."""

    trace_file = "dwarf_trace"

    def __init__(self, dwarfcore: DwarfCore):
        """Initialize the plugin.

        :param dwarfcore: An instance to a DwarfCore object that will be used
            for context
        """
        super().__init__()
        self.dwarfcore = dwarfcore
        self.context_key = "dwarf_trace"

    def did_execute_instruction_callback(
        self,
        state: State,
        pc: Union[int, Expression],
        _target_pc: Union[int, Expression],
        _instruction: Instruction,
    ):
        """Manticore callback that will determine whether Manticore is executing in a new function.

        If it is, it will add it to the trace list.
        """
        m_pc = ManticoreAddress(pc)
        ctxt = state.context
        current_func = ctxt.get("current_func", None)
        next_func = self.dwarfcore.func_name_from_va(m_pc)
        if next_func != current_func:
            if next_func is not None:
                logger.debug(f"[{state.id}] Now executing in func: {next_func} (0x{m_pc:x})")
                state.context.setdefault(self.context_key, []).append(
                    TraceFunction(next_func, m_pc)
                )
            ctxt["current_func"] = next_func

    def get_trace(self, state: State):
        """Return the collected trace of a specific Manticore State.

        :return: List of functions executed
        """
        return state.context.get(self.context_key, [])

    def will_terminate_state_callback(self, state: State, _ex):
        """Manticore callback on State termination.

        This will write the collected function trace to a file in Manticore's workspace location.
        """
        if state is None:
            return
        trace = state.context.get(self.context_key, [])
        with self.manticore._output.save_stream(f"{self.trace_file}_{state.id:08d}.csv") as f:
            csv_out = csv.writer(f)
            csv_out.writerow(["function", "address"])
            for f_entry in trace:
                csv_out.writerow(f_entry)
