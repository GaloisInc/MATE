from __future__ import annotations

from typing import Union

import cxxfilt
from manticore.core.plugin import Plugin
from manticore.core.smtlib import Expression
from manticore.native import Manticore
from manticore.native.heap_tracking.hook_malloc_library import hook_malloc_lib
from manticore.native.state import State

import dwarfcore.logging
from dwarfcore.dwarfcore import DwarfCore

logger = dwarfcore.logging.logger


class TrackHeapInformation(Plugin):
    """Plugin to enable tracking heap information but does not do any detection work.

    This should be used as the parent of any heap based manticore detector.
    """

    def __init__(self, dwarfcore: DwarfCore, m: Manticore, enable_heap_tracking: bool = True):
        super().__init__()
        self.malloc_addr = dwarfcore.start_va_of_function_m("malloc")
        self.free_addr = dwarfcore.start_va_of_function_m("free")
        self.calloc_addr = dwarfcore.start_va_of_function_m("calloc")
        self.realloc_addr = dwarfcore.start_va_of_function_m("realloc")
        self.operator_new_addrs = self._get_operator_new_addresses(dwarfcore)
        self.m = m
        self.dwarfcore = dwarfcore

        def init_heap_tracking(initial_state: State):
            hook_malloc_lib(
                initial_state,
                malloc=self.malloc_addr,
                free=self.free_addr,
                calloc=self.calloc_addr,
                realloc=self.realloc_addr,
                workspace=m._workspace._store.uri,
            )

        if enable_heap_tracking:
            m.init(init_heap_tracking)

    def _get_operator_new_addresses(self, dwarfcore: DwarfCore):
        res = []
        for func_addr, func_name in dwarfcore.all_functions().items():
            try:
                if func_name.startswith("_Z") and "operator new" in cxxfilt.demangle(func_name):
                    res.append(func_addr)
            except cxxfilt.InvalidName:
                logger.warning(f"Heap tracking: failed to demangle '{func_name}'")
        return res


def do_not_free_memory(_state: State, _ptr: Union[int, Expression]):
    logger.debug(
        f"Not executing call to free() for address in order to keep heap addresses unique."
    )
