import logging
from typing import Final

LOGGER_NAME: Final[str] = "manticore.dwarfcore"

logger = logging.getLogger(LOGGER_NAME)

# If you want another log level, set it manually
if logger.level == logging.NOTSET:
    logger.setLevel(logging.DEBUG)
