import logging
from argparse import Namespace
from types import SimpleNamespace
from typing import Union

_VERBOSITY = [logging.WARNING, logging.INFO, logging.DEBUG]
_FORMAT = "{name}:{threadName}:{levelname}:{filename}:{lineno:03d}: {message}"
_FORMATTER = logging.Formatter(fmt=_FORMAT, style="{")

# TODO(ww): Remove this.
logger = logging.getLogger("MATE")


def configure(ctxt: Union[Namespace, SimpleNamespace]) -> None:
    # NOTE(ww): Clamp verbose to a range of expected levels.
    if ctxt.verbose >= len(_VERBOSITY):
        ctxt.verbose = len(_VERBOSITY) - 1

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(_FORMATTER)
    stream_handler.setLevel(_VERBOSITY[ctxt.verbose])
    root_logger.addHandler(stream_handler)

    integration_logger = logging.getLogger("INTF")
    integration_logger.setLevel(logging.WARNING)
    integration_logger = logging.getLogger("MANTI")
    integration_logger.setLevel(logging.WARNING)
