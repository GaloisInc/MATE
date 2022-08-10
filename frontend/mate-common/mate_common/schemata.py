import json
from os.path import dirname, join, realpath
from typing import Any, Dict, List

from jsonschema.validators import RefResolver

from mate.logging import logger
from mate_common.assertions import mate_assert
from mate_common.datastructures.dict_utils import recursive_merge
from mate_common.models.cpg_types import EdgeKind, Endpoints, NodeKind, Relationship

# ------------- JSON schemata

_UP = dirname(realpath(__file__))

_NODE_SCHEMA_PATH = join(_UP, "schemata", "nodes.json")

_EDGE_SCHEMA_PATH = join(_UP, "schemata", "edges.json")

_SIGNATURES_SCHEMA_PATH = join(_UP, "schemata", "signatures.json")


def _try_load_schema(schema_path: str) -> Dict[str, Any]:
    """Attempt to load the JSON schema, return None if loading fails."""
    try:
        with open(schema_path, "r") as f:
            return json.load(f)
    except OSError:
        logger.warning(f"Could not load JSON schema at {schema_path}")
    return None  # type: ignore


NODE_SCHEMA = _try_load_schema(_NODE_SCHEMA_PATH)
EDGE_SCHEMA = _try_load_schema(_EDGE_SCHEMA_PATH)
SIGNATURES_SCHEMA = _try_load_schema(_SIGNATURES_SCHEMA_PATH)


def inline_refs(resolver: RefResolver, schema: Dict[str, Any], gas: int = 0) -> Dict[str, Any]:
    """Inline all JSON schema ``$ref`` references.

    Rather than handling recursive references in a correct, complicated way (say, with cycle-
    detection), this function takes a ``gas`` parameter which determines how many times it will call
    itself recursively.
    """
    if gas < 0:
        return schema

    out = dict(schema)  # copy (for postconditions)
    for (key, value) in schema.items():
        if isinstance(value, str) and key == "$ref":
            return inline_refs(resolver, resolver.resolve(value)[1], gas=gas - 1)
        if isinstance(value, list):
            out[key] = [
                inline_refs(resolver, sub, gas=gas - 1) if isinstance(sub, dict) else sub
                for sub in value
            ]
        if isinstance(value, dict):
            out[key] = inline_refs(resolver, value, gas=gas - 1)

    # Postconditions
    mate_assert(len(schema) <= len(out))
    mate_assert(set(schema.keys()) <= set(out.keys()) | {"$ref"})
    return out


def _organize_schema(schema: Dict[str, Any], node_or_edge: str = "node") -> Dict[str, Any]:
    """Attempt to organize the JSON schema by node/edge kind."""

    # Combine each "allOf" list of subschema into a single subschema
    merged_dicts: List[Dict[str, Any]] = []
    for all_of in (d["allOf"] for d in schema["oneOf"]):
        merged: Dict[str, Any] = dict()
        for subschema in all_of:
            # NOTE(ww): Experimentally, gas=5 is enough. Subsequent mate_assert calls
            # when building model properties should fail if it isn't, should the schema
            # become even more deeply nested.
            merged = recursive_merge(
                merged, inline_refs(RefResolver.from_schema(schema), subschema, gas=5)
            )
        merged_dicts.append(merged)

    return {d["properties"][f"{node_or_edge}_kind"]["enum"][0]: d for d in merged_dicts}


NODE_SCHEMA_BY_KIND = _organize_schema(NODE_SCHEMA)
EDGE_SCHEMA_BY_KIND = _organize_schema(EDGE_SCHEMA, "edge")

# ------------- Endpoints

_ENDPOINTS_PATH = join(_UP, "schemata", "endpoints.json")

_RAW_ENDPOINTS = _try_load_schema(_ENDPOINTS_PATH)

ENDPOINTS = {
    EdgeKind(ek): [
        Endpoints({NodeKind(nk) for nk in v["sources"]}, {NodeKind(nk) for nk in v["targets"]})
        for v in pairings
    ]
    for (ek, pairings) in _RAW_ENDPOINTS.items()
}
for edge_kind in EdgeKind:
    mate_assert(
        ENDPOINTS.get(edge_kind) is not None, f"Missing edge kind {edge_kind} in {_ENDPOINTS_PATH}"
    )

# ------------- Relationship specs

_RELATIONSHIPS_PATH = join(_UP, "schemata", "relationships.json")

_RAW_RELATIONSHIPS = _try_load_schema(_RELATIONSHIPS_PATH)

RELATIONSHIPS = {EdgeKind(ek): Relationship(rel) for (ek, rel) in _RAW_RELATIONSHIPS.items()}
for edge_kind in EdgeKind:
    mate_assert(
        RELATIONSHIPS.get(edge_kind) is not None,
        f"Missing edge kind {edge_kind} in {_RELATIONSHIPS_PATH}",
    )
