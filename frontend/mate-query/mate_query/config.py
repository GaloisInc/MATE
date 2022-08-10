"""``mate_query``-specific configuration state and settings."""

from typing import Final

from mate_common.config import get_config

# Default limit for the number of entries to explore during path queries
# made by mate_server / flowfinder endpoints.
MATE_SERVER_EXPLORATION_BOUND: Final[int] = get_config(
    "MATE_SERVER_EXPLORATION_BOUND", int, 5_000_000
)

# Default limit for the number of entries to explore during path queries.
# Chosen empirically by seeing what works well on challenge problems...
# TODO(sm): tune this further
MATE_DEFAULT_EXPLORATION_BOUND: Final[int] = get_config(
    "MATE_DEFAULT_EXPLORATION_BOUND", int, 5_000_000
)

MATE_STORAGE_ACCESS_KEY: Final[str] = get_config("MATE_STORAGE_ACCESS_KEY", str, "MATE_ACCESS_KEY")

MATE_STORAGE_SECRET_KEY: Final[str] = get_config("MATE_STORAGE_SECRET_KEY", str, "MATE_SECRET_KEY")
