"""Retrieve documentation for the CPG models from the JSON schemata."""

import logging
from typing import Any, Dict

from mate_common.schemata import NODE_SCHEMA_BY_KIND

logger = logging.getLogger(__name__)

_NO_DOCS = "No documentation available"


def _no_docs(message: str) -> str:
    """Gracefully put a message where documentation should be."""
    return f"{_NO_DOCS}: {message}"


def _description_for_kind(schema_by_kind: Dict[str, Any], kind: str) -> str:
    """Retrieve the JSON schema 'description' field for this node/edge kind."""
    try:
        if schema_by_kind is not None:
            return schema_by_kind[kind]["description"]
    except KeyError:
        logger.warning(f"Malformed JSON schema for {kind}")
    return _no_docs(f"Malformed JSON schema for {kind}")


def description_for_node_kind(kind: str) -> str:
    return _description_for_kind(NODE_SCHEMA_BY_KIND, kind)
