"""This module contains common hooks for replacing functions that can be modeled more efficiently in
Python, rather than letting Manticore add and solve constraints.

Some of these functions could include hooks for printing to standard out or sending network packets
over the network, which really isn't interesting for finding vulnerabilities within the program
itself. These hooks aim to speed up and assist in the symbolic execution of binaries to prevent
premature concretization and avoid complex functions within libc and other libraries.
"""

from typing import Any

from manticore.native import Manticore
from manticore.native.models import strcpy
from manticore.native.models import strlen_approx as strlen

from dwarfcore.dwarfcore import DwarfCore

from .logging import logger


def hook_defaults(manticore: Manticore, dwarfcore: DwarfCore) -> None:
    """Hook listed functions and replace them with Python implementation on all runs of
    Manticore."""
    strlen_addr = dwarfcore.start_va_of_function_m("strlen")
    if strlen_addr is not None:
        manticore.add_hook(strlen_addr, strlen_hook)

    strcpy_addr = dwarfcore.start_va_of_function_m("strcpy")
    if strcpy_addr is not None:
        manticore.add_hook(strcpy_addr, strcpy_hook)

    printf_addr = dwarfcore.start_va_of_function_m("printf")
    if printf_addr is not None:
        manticore.add_hook(printf_addr, printf_hook)

    fputs_addr = dwarfcore.start_va_of_function_m("fputs")
    if fputs_addr is not None:
        manticore.add_hook(fputs_addr, fputs_hook)


def strlen_hook(hook_state) -> None:
    """Use Manticore's pre-existing model of strlen to add constraints.

    This is useful because symbolic execution of string-comparison functions introduces many states
    into the execution and is more effectively implemented in Python.
    """
    logger.info(f" [{hook_state.id}] 0x{hook_state.cpu.PC:x}: Hooking strlen of our symbolic input")
    hook_state.invoke_model(strlen)


def strcpy_hook(hook_state) -> None:
    """Use Manticore's pre-existing model of strcpy to add constraints.

    This is useful because symbolic execution of string-comparison functions introduces many states
    into the execution and is more effectively implemented in Python.
    """
    logger.info(f" [{hook_state.id}] 0x{hook_state.cpu.PC:x}: Hooking strcpy of our symbolic input")
    hook_state.invoke_model(strcpy)


def _fputs(_state: Any, _f: Any, _s: Any) -> int:
    """Don't do anything if fputs is called."""
    return 0


def printf_hook(hook_state) -> None:
    """Hook printf."""
    logger.info(f" [{hook_state.id}] 0x{hook_state.cpu.PC:x}: Hooking and skipping printf")
    hook_state.invoke_model(_fputs)


def fputs_hook(hook_state) -> None:
    """Hook fputs."""
    logger.info(f" [{hook_state.id}] 0x{hook_state.cpu.PC:x}: Hooking and skipping fputs")
    hook_state.invoke_model(_fputs)
