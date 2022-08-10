#!/usr/bin/env python3

"""Generate an entity-relationship diagram from the database schemata."""

import argparse
import itertools
import json
from itertools import combinations
from pathlib import Path
from sys import argv


class DotFile:
    def __init__(self, file_name, rankdir="TB"):
        self._file = open(file_name, mode="w")
        print("digraph {", file=self._file)
        print(f'rankdir="{rankdir}"', file=self._file)

    def __enter__(self):
        return self._file

    def __exit__(self, _type, _value, _traceback):
        print("}", file=self._file)
        self._file.close()


def nodes_or_edges(schema):
    return [
        d for thing in schema["oneOf"] for d in thing["allOf"] if d.get("properties") is not None
    ]


def get_properties(schema_properties):
    properties = []
    for (prop, schema) in schema_properties.items():
        if "kind" in prop:
            continue
        if "type" in schema:
            properties.append(f"{prop} : {schema['type']}")
        else:
            properties.append(prop)
    return properties


def declare_node(node, with_properties: bool = True):
    kind = node["properties"]["node_kind"]["enum"][0]
    if with_properties:
        properties = "\\n".join(get_properties(node["properties"]))
        if properties != "":
            properties = "\\n\\n" + properties
        return f'{kind} [label="{kind}{properties}", shape=box];'
    return f'{kind} [label="{kind}", shape=box];'


def declare_edge(edge):
    kind = edge["properties"]["edge_kind"]["enum"][0]
    properties = "\\n".join(get_properties(edge["properties"]))
    if properties != "":
        properties = "\\n\\n" + properties
    return f'{kind} [label="{kind}{properties}"];'


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--node-schema", type=Path, default="nodes.json", help="path to the node JSON schema"
    )
    parser.add_argument(
        "--edge-schema", type=Path, default="edges.json", help="path to the edge JSON schema"
    )
    parser.add_argument(
        "--endpoints-schema",
        type=Path,
        default="endpoints.json",
        help="path to the endpoints schema",
    )
    parser.add_argument(
        "--relationships-schema",
        type=Path,
        default="relationships.json",
        help="path to the relationships schema",
    )
    parser.add_argument("--output", type=Path, default="schema.dot", help="output DOT file")

    ctxt = parser.parse_args(argv[1:])

    with open(ctxt.node_schema) as node_schema_file:
        node_schema = json.load(node_schema_file)
    with open(ctxt.edge_schema) as edge_schema_file:
        edge_schema = json.load(edge_schema_file)
    with open(ctxt.endpoints_schema) as endpoints_schema_file:
        endpoints_schema = json.load(endpoints_schema_file)
    with open(ctxt.relationships_schema) as relationships_schema_file:
        relationships_schema = json.load(relationships_schema_file)

    nodes = nodes_or_edges(node_schema)
    edges = nodes_or_edges(edge_schema)

    # Overall, big-picture
    with DotFile(ctxt.output) as output:

        for node in nodes:
            print(declare_node(node), file=output)

        for edge in edges:
            print(declare_edge(edge), file=output)
            kind = edge["properties"]["edge_kind"]["enum"][0]
            (src_cardinality, tgt_cardinality) = relationships_schema[kind].split("-to-")
            for source in itertools.chain.from_iterable(
                spec["sources"] for spec in endpoints_schema.get(kind, [])
            ):
                print(f"{source} -> {kind};", file=output)
            for target in itertools.chain.from_iterable(
                spec["targets"] for spec in endpoints_schema.get(kind, [])
            ):
                print(f"{kind} -> {target};", file=output)

            for d in endpoints_schema.get(kind, []):
                for source in d["sources"]:
                    for target in d["targets"]:
                        print(f"{source} -> {target} [style=invis];", file=output)

    # Star-shaped
    nodes_by_kind = {node["properties"]["node_kind"]["enum"][0]: node for node in nodes}
    edges_by_kind = {edge["properties"]["edge_kind"]["enum"][0]: edge for edge in edges}
    node_kinds = frozenset(nodes_by_kind.keys())
    edge_kinds = frozenset(edges_by_kind.keys())
    for node in nodes:
        node_kind = node["properties"]["node_kind"]["enum"][0]
        with DotFile(ctxt.output.with_suffix("." + node_kind + ".dot")) as output:

            print(declare_node(node, with_properties=False), file=output)
            declared_nodes = set(node_kind)
            added_edges = set()

            def do_declare_node(node):
                assert node in node_kinds, f"Invalid node! {node}"
                if node not in declared_nodes:
                    print(declare_node(nodes_by_kind[node], with_properties=False), file=output)
                    declared_nodes.add(node)

            def add_edge(src, tgt):
                assert (src in node_kinds and tgt in edge_kinds) or (
                    src in edge_kinds and tgt in node_kinds
                ), f"Invalid edge! {src} -> {tgt}"
                if (src, tgt) not in added_edges:
                    print(f"{src} -> {tgt};", file=output)
                    added_edges.add((src, tgt))

            for edge in edges:
                declared = False
                edge_kind = edge["properties"]["edge_kind"]["enum"][0]

                for pair in endpoints_schema.get(edge_kind, []):
                    if node_kind in pair.get("sources", []):
                        for target in pair.get("targets", []):
                            do_declare_node(target)
                            add_edge(node_kind, edge_kind)
                            add_edge(edge_kind, target)

                    if node_kind in pair.get("targets", []):
                        for source in pair.get("sources", []):
                            do_declare_node(source)
                            add_edge(source, edge_kind)
                            add_edge(edge_kind, node_kind)

    # State machine diagrams
    from mate_common.models.analyses import AnalysisTaskState
    from mate_common.models.builds import BuildState
    from mate_common.models.compilations import CompilationState
    from mate_common.models.manticore import MantiserveTaskState

    for sm in {AnalysisTaskState, BuildState, CompilationState, MantiserveTaskState}:
        with DotFile(
            ctxt.output.parent / f"statemachine.{sm.__name__}.dot", rankdir="LR"
        ) as output:

            def add_sm_node(node):
                if node is node.start():
                    color = "green"
                elif node.is_terminal():
                    color = "red"
                else:
                    color = "black"

                print(
                    f'{node.value} [label="{node.value}", shape=box, color="{color}"];', file=output
                )

            def add_sm_edge(src, tgt):
                print(f"{src.value} -> {tgt.value};", file=output)

            print(f'label = "{sm.__name__}"', file=output)
            print("labelloc = t", file=output)

            for state in sm:
                add_sm_node(state)

            for (src, tgt) in combinations(sm, 2):
                if src.can_transition_to(tgt):
                    add_sm_edge(src, tgt)
