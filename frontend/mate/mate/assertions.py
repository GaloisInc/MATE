"""Specialized assertion behavior for the MATE server."""

from dataclasses import dataclass

from mate.logging import logger
from mate_common.assertions import PANIC_MESSAGE, RuntimeAssertionError
from mate_common.config import MATE_ASSERTIONS


@dataclass(frozen=True)
class CompilationAssertionError(RuntimeAssertionError):
    """An exception class for compilation-time assertions in MATE.

    A "compilation-time" assertion is one during the compilation phase, i.e. before any CPG build
    processes.
    """

    message: str
    compilation_id: str


@dataclass(frozen=True)
class BuildAssertionError(RuntimeAssertionError):
    """An exception class for build-time assertions in MATE.

    A "build-time" assertion is one during the CPG build processes.
    """

    message: str
    build_id: str


def compilation_assert(condition: bool, msg: str, *, compilation_id: str) -> None:
    if not condition:
        logger.error(PANIC_MESSAGE + msg)

        if MATE_ASSERTIONS:
            raise CompilationAssertionError(PANIC_MESSAGE + msg, compilation_id)


def build_assert(condition: bool, msg: str, *, build_id: str) -> None:
    """Assert an unexpected condition during CPG construction.

    These assertions will cause their corresponding ``db.Build`` to be put into a "failed" state
    when used with the server. When used with the MATE CLI, they cause a process termination.
    """

    if not condition:
        logger.error(PANIC_MESSAGE + msg)

        if MATE_ASSERTIONS:
            raise BuildAssertionError(PANIC_MESSAGE + msg, build_id)
