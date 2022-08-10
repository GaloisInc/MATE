"""Common default configuration state."""

import logging
import os
from typing import Callable, Final, TypeVar

logger = logging.getLogger(__name__)

V = TypeVar("V")


def get_config(key: str, converter: Callable[[str], V], default: V) -> V:
    env_val = os.getenv(key)
    if env_val is None:
        logger.info(
            f"Configuration environment variable {key} not present, defaulting to {default}"
        )
        return default
    else:
        try:
            value = converter(env_val)
            logger.info(f"Loaded configuration environment variable {key} with value {value}")
            return value
        except Exception as e:
            logger.exception(f"Environment variable {key} is present, but could not be converted!")
            raise e


MATE_DEFAULT_MEMORY_LIMIT_GB: Final[int] = get_config("MATE_DEFAULT_MEMORY_LIMIT_GB", int, 32)

MATE_ASSERTIONS: Final[bool] = get_config("MATE_ASSERTIONS", bool, False)
