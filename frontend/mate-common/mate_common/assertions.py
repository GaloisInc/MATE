"""Common assertion code for MATE."""

import logging
from dataclasses import dataclass
from typing import Final

from mate_common.config import MATE_ASSERTIONS

logger = logging.getLogger(__name__)

PANIC_MESSAGE: Final[
    str
] = """
You have encountered a bug in MATE's implementation. Please report it.

Additional information:
"""


class _MateAssertionError(Exception):
    """A base exception class for assertions in MATE.

    ``_MateAssertionError`` should never be used directly.

    This class is intentionally distinct from the error hierarchy in ``mate.error``,
    as well as from the standard ``AssertionError``. We separate it from the former
    to prevent confusion about the purpose of assertions (registering checks on
    conditions that we **do not** expect to fail), and from the latter to prevent
    any unintentional behavior in FastAPI or other services that may treat
    "real" Python assertions specially.
    """

    pass


@dataclass(frozen=True)
class RuntimeAssertionError(_MateAssertionError):
    """An exception class for runtime assertions in MATE.

    A "runtime" assertion is one during MATE's normal lifecycle, i.e. not tied to a particular
    compilation or build process.
    """

    message: str


def mate_assert(condition: bool, msg: str = "") -> None:
    """Assert a condition that always indicates a programming error in MATE.

    These assertions will cause a MATE process (CLI, server) to raise if assertions are enabled,
    which in turn will cause either an error response (server) or a process termination (CLI).
    """

    if not condition:
        logger.error(PANIC_MESSAGE + msg)

        if MATE_ASSERTIONS:
            raise RuntimeAssertionError(PANIC_MESSAGE + msg)
