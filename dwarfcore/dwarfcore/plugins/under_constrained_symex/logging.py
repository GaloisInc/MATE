import logging
from typing import Final

LOGGER_NAME: Final[str] = "manticore.under_constrained"

logger = logging.getLogger(LOGGER_NAME)
logger.setLevel(logging.DEBUG)
