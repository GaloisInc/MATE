#!/usr/bin/env python3

"""Generate Mustache data files from the JSON schemata.

TODO:
- Alphabetically sort nodes/edges
- Enums
"""

import argparse
import itertools
import json
from pathlib import Path
from sys import argv


def expand_dict(d):
    return [{"key": k, **v} for (k, v) in d.items()]


def nodes_or_edges(which, schema):
    return [
        {
            **d,
            "title": d["properties"][f"{which}_kind"]["enum"][0],
            # We have to change the name so we don't accidentally capture this when
            # we want a description of a certain attribute.
            f"{which}-description": d.get("description"),
            "description": None,
            "properties": expand_dict(d["properties"]),
        }
        for thing in schema["oneOf"]
        for d in thing["allOf"]
        if d.get("properties") is not None
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--node-schema", type=Path, default="nodes.json", help="path to the node JSON schema"
    )
    parser.add_argument(
        "--edge-schema", type=Path, default="edges.json", help="path to the edge JSON schema"
    )
    parser.add_argument("--output", type=Path, default="mustache.json", help="output JSON file")

    ctxt = parser.parse_args(argv[1:])

    with open(ctxt.node_schema) as node_schema_file:
        node_schema = json.load(node_schema_file)
    with open(ctxt.edge_schema) as edge_schema_file:
        edge_schema = json.load(edge_schema_file)
    with open(ctxt.output, mode="w") as output:
        json.dump(
            {
                "nodes": nodes_or_edges("node", node_schema),
                "edges": nodes_or_edges("edge", edge_schema),
                "definitions": [
                    {**defn, "properties": expand_dict(defn.get("properties", dict())), "key": name}
                    for (name, defn) in itertools.chain(
                        node_schema["definitions"].items(), edge_schema["definitions"].items()
                    )
                    if name != "base"
                ],
            },
            output,
            indent=2,
        )
