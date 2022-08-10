from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Final, List, Optional, Union

from manticore import issymbolic
from manticore.core.smtlib import SelectedSolver, get_taints, simplify, taint_with
from manticore.core.smtlib.expression import BitVecConstant, BoolConstant, Expression
from manticore.core.smtlib.operators import OR
from manticore.native import Manticore
from manticore.native.heap_tracking.hook_malloc_library import add_ret_hook
from manticore.native.state import State

import dwarfcore.logging
from dwarfcore.detectors.common import record_concretize_state_vars
from dwarfcore.dwarfcore import DwarfCore, DwarfcoreException
from dwarfcore.plugins.heap_common import TrackHeapInformation
from dwarfcore.plugins.under_constrained_symex.errors import AccessKind, UnderconstrainedOOB
from dwarfcore.plugins.under_constrained_symex.smt import uc_pretty_print
from dwarfcore.utils import addr_to_map_and_offset, pp_map_and_offset
from mate_common.models.integration import Detector, ReachingTestCase, UnderconstrainedTestCase

logger = dwarfcore.logging.logger


@dataclass(frozen=True)
class Alloc:
    addr: int
    size: int


class ConcreteHeapOOB(TrackHeapInformation):
    """Plugin to detect out-of-bounds memory access in the heap."""

    """Manticore context key for holding testcases by this detector"""
    MCORE_TESTCASE_LIST: Final[str] = "ConcreteHeapOOB_testcases"

    @staticmethod
    def intercept_alloc_after(state: State) -> None:
        alloc_size = state.context["last_alloc_size"].pop()
        alloc_addr = state.cpu.RAX
        state.remove_hook(state.cpu.read_register("PC"), ConcreteHeapOOB.intercept_alloc_after)
        # Plugin internal data
        heap_plugin = get_heap_oob_plugin(state)
        # Taint returned pointer
        taint: str = heap_plugin.get_new_taint()
        heap_plugin.taint_to_alloc[taint] = Alloc(alloc_addr, alloc_size)
        if issymbolic(alloc_addr):
            taint_with(alloc_addr, taint)
        else:
            alloc_addr = BitVecConstant(size=64, value=alloc_addr, taint=(taint,))
        state.cpu.RAX = alloc_addr

    @staticmethod
    def intercept_new(state: State) -> None:
        if "last_alloc_size" in state.context:
            state.context["last_alloc_size"].append(state.cpu.RDI)
        else:
            state.context["last_alloc_size"] = [state.cpu.RDI]
        heap_plugin = get_heap_oob_plugin(state)
        func_name = heap_plugin._get_func_name_from_va(state.cpu.PC)
        add_ret_hook(func_name, state, ConcreteHeapOOB.intercept_alloc_after)

    @staticmethod
    def intercept_malloc(state: State) -> None:
        if "last_alloc_size" in state.context:
            state.context["last_alloc_size"].append(state.cpu.RDI)
        else:
            state.context["last_alloc_size"] = [state.cpu.RDI]
        add_ret_hook("malloc", state, ConcreteHeapOOB.intercept_alloc_after)

    def __init__(
        self, dwarfcore: DwarfCore, m: Manticore, fast: bool = True, underconstrained: bool = False
    ):
        """Initialize the Plugin.

        :param dwarfcore: An instance to a DwarfCore object that will be used
            for context
        :param fast: This plugin will stop Manticore when first detection is
            made instead of letting Manticore continue with exploration.
        :param underconstrained: whether the plugin is enabled in the context of an
            underconstrained Manticore task
        """
        # We disable the heap tracking lib because it is not happy with
        # the symbolic return values that this plugin creates for malloc()
        super().__init__(dwarfcore, m, enable_heap_tracking=False)
        self.fast = fast

        self._taint_cnt = 0
        self.taint_to_alloc: Dict[str, Alloc] = {}
        self.underconstrained = underconstrained

        if self.malloc_addr:
            m.add_hook(self.malloc_addr, self.intercept_malloc, after=False, syscall=False)

        for new_addr in self.operator_new_addrs:
            m.add_hook(new_addr, self.intercept_new, after=False, syscall=False)

    def _get_func_name_from_va(self, va: int) -> str:
        for func_addr, func_name in self.dwarfcore.all_functions().items():
            if func_addr == va:
                return func_name
        raise DwarfcoreException("Virtual address doesn't correspond to a known function")

    def check_mem_access(
        self, state: State, address: Union[Expression, int], size: int, kind: AccessKind
    ):
        """:param size: Size of the memory access in bytes"""
        found_error: bool = False
        if issymbolic(address):
            # Get pointer taint
            try:
                taint = next(get_taints(address, taint="heap_obj*"))
                if taint is None:
                    return
            except StopIteration:
                return
            alloc = self.taint_to_alloc[taint]
            address = simplify(address)
            if isinstance(address, BitVecConstant):
                if address < alloc.addr or address + size > alloc.addr + alloc.size:
                    self.record_testcase(state, f"Heap out-of-bounds memory {kind.value}")
                    found_error = True
            else:
                oob_cond = OR(
                    (address + size).ugt(alloc.addr + alloc.size), address.ult(alloc.addr)
                )
                oob_cond = simplify(oob_cond)
                if SelectedSolver.instance().can_be_true(
                    state.cpu.memory.constraints.related_to(oob_cond), oob_cond
                ):
                    self.record_testcase(state, f"Heap out-of-bounds memory {kind.value}", oob_cond)
                    found_error = True

        if found_error and self.fast:
            state.abandon()

    def will_write_memory_callback(self, state: State, address, _value, size):
        self.check_mem_access(state, address, size // 8, AccessKind.WRITE)

    def will_read_memory_callback(self, state: State, address, size):
        self.check_mem_access(state, address, size // 8, AccessKind.READ)

    def _get_new_taint_cnt(self) -> int:
        self._taint_cnt += 1
        return self._taint_cnt - 1

    def get_new_taint(self) -> str:
        return f"heap_obj_{self._get_new_taint_cnt()}"

    def record_testcase(self, state: State, message: str, cond: Optional[Expression] = None):
        if self.underconstrained:
            self._record_testcase_underconstrained(
                state, BoolConstant(value=True) if cond is None else cond, message
            )
        else:
            self._record_testcase_regular(state, message)

    def _record_testcase_regular(self, state: State, message: str):
        with state as tmp:
            testcase = ReachingTestCase(
                description=message,
                detector_triggered=Detector.ConcreteHeapOOB,
                symbolic_inputs=record_concretize_state_vars(tmp, state.id),
            )
            with tmp.manticore.locked_context() as context:
                case_list = context.get(self.MCORE_TESTCASE_LIST, list())
                case_list.append(testcase)
                context[self.MCORE_TESTCASE_LIST] = case_list

        # Generate a testcase using Manticore's internal machinery
        self.manticore.generate_testcase(state, message)

    def _record_testcase_underconstrained(self, state: State, cond: Expression, message: str):
        from dwarfcore.plugins.under_constrained_symex.plugin import UCSE

        with state as tmp:
            with tmp.manticore.locked_context() as context:
                cases = context.get(self.MCORE_TESTCASE_LIST, list())
                test_case = UnderconstrainedTestCase(
                    description=message,
                    uid=UnderconstrainedOOB.new_testcase_uid(),
                    va=state.cpu.PC,
                    va_mapping=pp_map_and_offset(
                        addr_to_map_and_offset(state.cpu.PC, state.cpu.memory)
                    ),
                    condition=uc_pretty_print(simplify(cond)),
                    constraints=[uc_pretty_print(simplify(c)) for c in state.constraints],
                    detector_triggered=Detector.ConcreteHeapOOB,
                    symbolic_inputs=[],  # TODO(boyan): this must be computed on-the-fly
                )
                cases.append(test_case)
                context[self.MCORE_TESTCASE_LIST] = cases
                # Also add the error in the exploration tree
                context[UCSE.ctx_exploration_tree].get_state(state.id).cases.append(test_case)

    @property
    def results(self) -> List[ReachingTestCase]:
        """Any test case results found during execution."""
        with self.manticore.locked_context() as context:
            return context.get(self.MCORE_TESTCASE_LIST, list())

    @property
    def name(self) -> str:
        return "ConcreteHeapOOBPlugin"


def get_heap_oob_plugin(state: State):
    heap_plugin = [
        p for p in state.manticore.plugins.values() if p.name == "ConcreteHeapOOBPlugin"
    ][0]
    if heap_plugin is None:
        raise DwarfcoreException("Couldn't find ConcreteHeapOOBPlugin instance in manticore")
    return heap_plugin
