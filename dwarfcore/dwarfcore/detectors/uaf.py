from __future__ import annotations

from typing import Final, List, Optional, Union

from manticore import issymbolic
from manticore.core.smtlib.expression import Expression
from manticore.native import Manticore
from manticore.native.heap_tracking.hook_malloc_library import add_ret_hook, read_arg
from manticore.native.state import State

import dwarfcore.logging
from dwarfcore.detectors.common import record_concretize_state_vars
from dwarfcore.dwarfcore import DwarfCore
from dwarfcore.plugins.heap_common import TrackHeapInformation, do_not_free_memory
from mate.build.tob_chess_utils.dwarf import SourceCodeInfo
from mate_common.models.integration import Detector, FreeUseInfo, ReachingTestCase

logger = dwarfcore.logging.logger


class DetectUseAfterFree(TrackHeapInformation):
    """Plugin to detect use after free vulnerabilities by tracking allocations."""

    """Manticore context key for holding testcases by this detector"""
    MCORE_TESTCASE_LIST: Final[str] = "DetectUseAfterFree_testcases"

    @staticmethod
    def taint_allocation_with_va_after(state: State):
        ret_val = state.context["ret_val"]

        if not issymbolic(ret_val):
            malloc_data = state.context["malloc_lib"]
            allocation = sorted(malloc_data.malloc_lib_tree[ret_val])
            if allocation:
                allocation[0].data.allocation_location = state.context["last_malloc_addr"]
                del state.context["last_malloc_addr"]

        del state.context["ret_val"]

        state.remove_hook(
            state.cpu.read_register("PC"),
            DetectUseAfterFree.taint_allocation_with_va_after,
            after=True,
        )

    @staticmethod
    def taint_allocation_with_va(state: State):
        state.context["ret_val"] = state.cpu.read_register(
            state._platform._function_abi.get_result_reg()
        )
        state.remove_hook(
            state.cpu.read_register("PC"), DetectUseAfterFree.taint_allocation_with_va
        )
        state.add_hook(
            state.cpu.read_register("PC"),
            DetectUseAfterFree.taint_allocation_with_va_after,
            after=True,
        )

    @staticmethod
    def intercept_malloc(state: State):
        state.context["last_malloc_addr"] = state.cpu.last_executed_pc
        add_ret_hook("malloc", state, DetectUseAfterFree.taint_allocation_with_va)

    @staticmethod
    def intercept_free(state: State):
        free_address = read_arg(state.cpu, next(state._platform._function_abi.get_arguments()))

        if not issymbolic(free_address):
            # Taint the freed allocation with the va
            malloc_data = state.context["malloc_lib"]
            allocation = sorted(malloc_data.malloc_lib_tree[free_address])
            if allocation:
                allocation[0].data.deallocation_location = state.cpu.last_executed_pc

        state.invoke_model(do_not_free_memory)

    def __init__(
        self,
        dwarfcore: DwarfCore,
        m: Manticore,
        poi_info: Optional[List[FreeUseInfo]],
        fast: bool = True,
        fast_all_poi: bool = False,
    ):
        """Initialize the Plugin.

        :param dwarfcore: An instance to a DwarfCore object that will be used
            for context
        :param poi_info: A list of use and free site lines and files. If
            this is omitted or None or empty list, the plugin will look for the
            the first reachable UAF in a path.
        :param fast: This plugin will stop Manticore when first detection is
            made instead of letting Manticore continue with exploration.
        :param fast_all_poi: This plugin will stop Manticore when one detection
            has occurred for every poi specified instead of letting Manticore
            continue with exploration.
        """
        super().__init__(dwarfcore, m)
        self.fast = fast
        self.poi_info = poi_info
        self.fast_all_poi = fast_all_poi

        m.add_hook(self.free_addr, self.intercept_free, after=False, syscall=False)
        m.add_hook(self.malloc_addr, self.intercept_malloc, after=False, syscall=False)

    def record_testcase(self, state: State, message: str):
        with state as tmp:
            testcase = ReachingTestCase(
                description=message,
                detector_triggered=Detector.UseAfterFree,
                symbolic_inputs=record_concretize_state_vars(tmp, state.id),
            )
            with tmp.manticore.locked_context() as context:
                case_list = context.get(self.MCORE_TESTCASE_LIST, list())
                case_list.append(testcase)
                context[self.MCORE_TESTCASE_LIST] = case_list

        # Generate a testcase using Manticore's internal machinery
        self.manticore.generate_testcase(state, message)

    @property
    def results(self) -> List[ReachingTestCase]:
        """Any test case results found during execution."""
        with self.manticore.locked_context() as context:
            return context.get(self.MCORE_TESTCASE_LIST, list())

    def will_read_memory_callback(
        self, state: State, where: Union[int, Expression], _size: Union[int, Expression]
    ):
        if issymbolic(where):
            logger.debug(
                f"Got symbolic 'where' address when reading memory in UAF Detector, state {state.id}"
            )
            # TODO(ss): How do we want to deal with symbolic accesses?
            return

        malloc_data = state.context["malloc_lib"]
        allocation = sorted(malloc_data.malloc_lib_tree[where])
        if not allocation:
            # We have no information about this allocation.
            # It may or may not be on the heap but it doesn't matter with no alllocation information at this time
            # TODO(ss): Something may be able to be said about this allocation if it is on the heap, based on the
            #  surrounding location data if nothing else - Worry about this later
            return

        elif allocation[0].data.is_freed:
            va = state.cpu.instruction.address
            read_location = self.dwarfcore.source_info_from_va(state.platform.program, va)
            deallocation_location: Optional[SourceCodeInfo] = None
            msg = f"Found use after free when reading address {where:#x} @ {va:#x} ({read_location})! "

            if not allocation[0].data.allocation_location:
                msg += " Allocation location was not tainted for this address"
            else:
                allocation_va = allocation[0].data.allocation_location
                allocation_location = self.dwarfcore.source_info_from_va(
                    state.platform.program, allocation_va
                )
                msg += f" Allocated @ {allocation_va:#x} ({allocation_location})."

            if not allocation[0].data.deallocation_location:
                msg += " Deallocation location was not tainted for this address"
            else:
                deallocation_va = allocation[0].data.deallocation_location
                deallocation_location = self.dwarfcore.source_info_from_va(
                    state.platform.program, deallocation_va
                )
                msg += f" Deallocated @ {deallocation_va:#x} ({deallocation_location})."

            if self.poi_info and deallocation_location:
                not_of_interest = True

                for i, poi in enumerate(self.poi_info):
                    if (
                        deallocation_location.line == poi.free_line
                        and deallocation_location.file == poi.free_file
                        and read_location.line == poi.use_line
                        and read_location.file == poi.use_file
                    ):
                        not_of_interest = False
                        if self.fast_all_poi:
                            del self.poi_info[i]
                        break

                if not_of_interest:
                    # Found UAF but it is not the one requested by the poi. Return and continue search
                    msg += f"This UAF is not in the poi request list. Continuing search!"
                    logger.info(msg)
                    return

            logger.info(msg)
            self.record_testcase(state, msg)

            if self.fast or (self.fast_all_poi and not self.poi_info):
                # Only exit quickly if all requested pois of interest have been validated
                state.manticore.kill()
            state.abandon()

    def will_write_memory_callback(
        self,
        state: State,
        where: Union[int, Expression],
        _expression: Union[int, Expression],
        _size: Union[int, Expression],
    ):
        if issymbolic(where):
            logger.debug(
                f"Got symbolic 'where' address when writing memory in UAF Detector, state {state.id}"
            )
            # TODO(ss): How do we want to deal with symbolic accesses?
            return

        malloc_data = state.context["malloc_lib"]
        allocation = sorted(malloc_data.malloc_lib_tree[where])
        if not allocation:
            # We have no information about this allocation.
            # It may or may not be on the heap but it doesn't matter with no alllocation information at this time
            # TODO(ss): Something may be able to be said about this allocation if it is on the heap, based on the
            #  surrounding location data if nothing else - Worry about this later
            return

        elif allocation[0].data.is_freed:
            va = state.cpu.instruction.address
            write_location = self.dwarfcore.source_info_from_va(state.platform.program, va)
            deallocation_location: Optional[SourceCodeInfo] = None
            msg = f"Found use after free when writing to address {where:#x} @ {va:#x} ({write_location})! "

            if not allocation[0].data.allocation_location:
                msg += " Allocation location was not tainted for this address"
            else:
                allocation_va = allocation[0].data.allocation_location
                allocation_location = self.dwarfcore.source_info_from_va(
                    state.platform.program, allocation_va
                )
                msg += f" Allocated @ {allocation_va:#x} ({allocation_location})."

            if not allocation[0].data.deallocation_location:
                msg += " Deallocation location was not tainted for this address"
            else:
                deallocation_va = allocation[0].data.deallocation_location
                deallocation_location = self.dwarfcore.source_info_from_va(
                    state.platform.program, deallocation_va
                )
                msg += f" Deallocated @ {deallocation_va:#x} ({deallocation_location})."

            if self.poi_info and deallocation_location:
                not_of_interest = True

                for i, poi in enumerate(self.poi_info):
                    if (
                        deallocation_location.line == poi.free_line
                        and deallocation_location.file == poi.free_file
                        and write_location.line == poi.use_line
                        and write_location.file == poi.use_file
                    ):
                        not_of_interest = False
                        if self.fast_all_poi:
                            del self.poi_info[i]
                        break

                if not_of_interest:
                    # Found UAF but it is not the one requested by the poi. Return and continue search
                    msg += f" This UAF is not in the poi request list. Continuing search!"
                    logger.info(msg)
                    return

            logger.info(msg)
            self.record_testcase(state, msg)

            if self.fast or (self.fast_all_poi and not self.poi_info):
                # Only exit quickly if all requested pois of interest have been validated
                state.manticore.kill()
            state.abandon()
