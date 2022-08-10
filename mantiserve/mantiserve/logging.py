import argparse
import logging
from typing import Any, Final

import manticore.utils.log

VERBOSITY = (logging.WARNING, logging.INFO, logging.DEBUG)
FORMAT: Final[str] = "{name}:{levelname}:{filename}:{lineno:03d}: {message}"
LOGGER_NAME: Final[str] = "MANTISERVE"

formatter = logging.Formatter(fmt=FORMAT, style="{")
logger = logging.getLogger(LOGGER_NAME)


def configure(ctxt: argparse.Namespace) -> logging.Logger:
    """Configure the logging for mantiserve according to the passed context."""
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(VERBOSITY[ctxt.verbose])
    logger.setLevel(VERBOSITY[ctxt.verbose])
    logger.addHandler(stream_handler)

    return logger


def default_manticore_file_logging_handler(filename: str) -> logging.Handler:
    """Return a logging handler that is set up to redirect Manticore logs to the file specified.

    Useful with the `RedirectedManticoreLogs` context manager.
    """
    handler = logging.FileHandler(filename, mode="w", encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(manticore.utils.log.formatter)
    handler.addFilter(manticore.utils.log.ManticoreContextFilter())
    return handler


class RedirectedManticoreLogs:
    """Resets Manticore logger."""

    def __init__(self, handler: logging.Handler) -> None:
        """Redirect Manticore and Mantiserve Logs.

        :param handler: The handler to use for logging
        """
        self.logger_handler = handler
        self.mantiserve_logger = logging.getLogger(LOGGER_NAME)
        self.manticore_logger = logging.getLogger("manticore")

        self.mantiserve_logger.addHandler(handler)
        self.manticore_logger.addHandler(handler)
        if self.manticore_logger.level == logging.NOTSET:
            self.manticore_logger.setLevel(manticore.utils.log.DEFAULT_LOG_LEVEL)

    def __enter__(self) -> None:
        pass

    def __exit__(self, _exc_type: Any, _exc_val: Any, _exc_tb: Any) -> None:
        self.mantiserve_logger.removeHandler(self.logger_handler)
        self.manticore_logger.removeHandler(self.logger_handler)
        self.logger_handler.flush()
        self.logger_handler.close()
