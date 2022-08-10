#!/usr/bin/env python3

# margin.py: Take the JSONL output of Wedlock, aspirin, Headache (TI only)
# and flatten it into MATE-compatible CSV.

# MATE's schema: https://gitlab-ext.galois.com/mate/MATE/blob/master/db/scripts/sql/schema.sql
# Node structure: https://gitlab-ext.galois.com/mate/MATE/blob/master/db/schemata/nodes.json
# Edge structure: https://gitlab-ext.galois.com/mate/MATE/blob/master/db/schemata/edges.json

import argparse
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha1
from json import dumps, loads
from typing import Any, Dict, Final, FrozenSet, Iterator, List, Optional, Set, Tuple

from mate.build.tob_chess_utils.logging import make_logger
from mate.build.tob_chess_utils.tools.aspirin import AspirinRecordKind
from mate_common.error import MateError
from mate_common.models.cpg_types import (
    DWARF_TYPE_KIND_TO_NODE_KIND,
    DWARFTypeIDSentinel,
    DWARFTypeKind,
    EdgeKind,
    NodeKind,
)


class MarginError(MateError):
    """A generic error, internal to ``margin-walker``."""

    pass


_IR_BB_OPERAND_PATTERN = re.compile(r"^%i\d+$")

StringKeyedDict = Dict[str, Any]

logger = make_logger(__name__)

parser = argparse.ArgumentParser(description="Flatten ToB JSONL into MATE-compatible JSONL")
parser.add_argument(
    "-w", "--wedlock", type=argparse.FileType("r"), required=True, help="Wedlock input"
)
parser.add_argument(
    "-a", "--aspirin", type=argparse.FileType("r"), required=True, help="Aspirin input"
)
parser.add_argument(
    "-t", "--headache_ti", type=argparse.FileType("r"), required=True, help="Headache TI input"
)
parser.add_argument(
    "-c", "--headache_cu", type=argparse.FileType("r"), required=True, help="Headache CU input"
)
parser.add_argument(
    "-o", "--output", type=argparse.FileType("w"), required=True, help="Output JSONL"
)
parser.add_argument(
    "-S", "--sanity_checks", action="store_true", help="Perform input sanity checks"
)
parser.add_argument(
    "-Xs",
    "--omit_plt_stub_nodes",
    action="store_true",
    help="Don't emit PLT function stub nodes",
)
parser.add_argument(
    "-Xc",
    "--omit_translation_unit_nodes",
    action="store_true",
    help="Don't emit translation unit nodes",
)
parser.add_argument("-Xt", "--omit_type_nodes", action="store_true", help="Don't emit type nodes")
parser.add_argument(
    "-Xg", "--omit_global_nodes", action="store_true", help="Don't emit global variable nodes"
)
parser.add_argument(
    "-Xw",
    "--omit_wedlock_function_nodes",
    action="store_true",
    help="Don't emit Wedlock function nodes",
)
parser.add_argument(
    "-Xp", "--omit_param_nodes", action="store_true", help="Don't emit function parameter nodes"
)
parser.add_argument(
    "-Xv", "--omit_var_nodes", action="store_true", help="Don't emit function local variable nodes"
)
parser.add_argument(
    "-Xi", "--omit_asm_inst_nodes", action="store_true", help="Don't emit ASM instruction nodes"
)
parser.add_argument(
    "-xe", "--emit_arg_edges", action="store_false", help="Do emit Argument <-> DWARFArgument edges"
)

# These members of each aspirin BB dictionary shouldn't make their
# way into the ultimate ASMBlock record.
FILTERED_ASPIRIN_BB_ATTRIBUTES: Final[List[str]] = ["instructions", "operand"]


@dataclass(eq=True, frozen=True)
class MarginWalkerOptions:
    sanity_checks: bool = False
    omit_plt_stub_nodes: bool = False
    omit_translation_unit_nodes: bool = False
    omit_type_nodes: bool = False
    omit_global_nodes: bool = False
    omit_wedlock_function_nodes: bool = False
    omit_param_nodes: bool = False
    omit_var_nodes: bool = False
    omit_asm_inst_nodes: bool = False
    omit_arg_edges: bool = True


class MarginWalkerContext:
    def __init__(self, options: MarginWalkerOptions):
        self._options = options
        self._counter = 0
        self._edge_map: Dict[FrozenSet[str], Set[EdgeKind]] = defaultdict(set)

    @property
    def options(self) -> MarginWalkerOptions:
        return self._options

    def next_id(self) -> str:
        id_ = f"tob:{self._counter}"
        self._counter += 1
        return id_

    def _make_edge(self, edge_kind: EdgeKind) -> StringKeyedDict:
        return {"edge_kind": edge_kind.value}

    def emit_node(self, uuid: str, attrs: StringKeyedDict) -> StringKeyedDict:
        return {"entity": "node", "uuid": str(uuid), "attributes": attrs}

    def emit_edge(self, source: str, dest: str, edge_kind: EdgeKind) -> Iterator[StringKeyedDict]:
        node_pair = frozenset({source, dest})
        edge_kinds = self._edge_map[node_pair]

        # NOTE(ww): A particular (source, dest) pair should only have one edge of
        # a particular kind. Some of our DWARF type pairing patterns below naturally
        # result in trying to draw multiple edges of the same kind; we catch those
        # here and make sure not to emit them.
        if edge_kind in edge_kinds:
            yield from ()
        else:
            self._edge_map[node_pair].add(edge_kind)
            yield {
                "entity": "edge",
                "uuid": self.next_id(),
                "source": str(source),
                "target": str(dest),
                "attributes": self._make_edge(edge_kind),
            }


def _compressed_id(
    func: str, dir_: str, file: str, line: int, col: int, scope_line: int, scope_column: int
) -> str:
    """Returns a compressed ID for the parameters.

    See ``compressedScopeID`` in ``Utils.h`` for more details.
    """
    return sha1(
        f"{func}:{dir_}:{file}:{line}:{col}:{scope_line}:{scope_column}".encode()
    ).hexdigest()


def emit_plt_stub_nodes(
    ctx: MarginWalkerContext, asp_plt_dicts: List[StringKeyedDict]
) -> Iterator[StringKeyedDict]:
    for plt_stub in asp_plt_dicts:
        plt_uuid = ctx.next_id()
        plt_stub_node = {
            "node_kind": NodeKind.PLT_STUB.value,
            "symbol": plt_stub["symbol"],
            "va": plt_stub["va"],
        }

        yield ctx.emit_node(plt_uuid, plt_stub_node)


def emit_translation_unit_nodes_and_edges(
    ctx: MarginWalkerContext, cu_dict: StringKeyedDict, asp_module_dict: StringKeyedDict
) -> Iterator[StringKeyedDict]:
    """Yields a TranslationUnit node for every compilation unit in ``cu_dict``, as well as edges to
    the containing LLVM module."""
    module_uuid = f"<module>:{cu_dict['source_stem']}"
    module_node = {
        "node_kind": NodeKind.MODULE.value,
        "module_name": cu_dict["module_name"],
        "source_file": cu_dict["source_file"],
        # "source_stem": cu_dict["source_stem"],
        "target_triple": cu_dict["target_triple"],
        "data_layout": cu_dict["data_layout"],
        "symbols": asp_module_dict["symbols"],
    }

    # NOTE(ww): Conceptually this belongs in ASTGraphWriter, but ASTGraphWriter
    # uses llvm::Value as its fundamental type and llvm::Module is NOT an llvm::Value.
    yield ctx.emit_node(module_uuid, module_node)

    for cu in cu_dict["cus"]:
        translation_unit_node = {
            "node_kind": NodeKind.TRANSLATION_UNIT.value,
            "source_language": cu["source_language"],
            "producer": cu["producer"],
            "flags": cu["flags"],
            "filename": os.path.join(cu["file"]["directory"], cu["file"]["filename"]),
        }

        tu_uuid = ctx.next_id()
        yield ctx.emit_node(tu_uuid, translation_unit_node)
        yield from ctx.emit_edge(module_uuid, tu_uuid, EdgeKind.MODULE_TO_TRANSLATION_UNIT)

    # TODO(ww): We also have a list of every external symbol exposed by the module;
    # we should draw these back to their corresponding functions and global variables.
    # See: https://gitlab-ext.galois.com/mate/MATE/-/issues/618


def emit_type_nodes_and_edges(
    ctx: MarginWalkerContext, ti_map: StringKeyedDict, type_node_map: Dict[str, str]
) -> Iterator[StringKeyedDict]:
    """Yields a DWARFType node for every type in ``ti_map``, building up a map of type IDs to
    DWARFType node UUIDs along the way."""

    # First pass: emit a DWARFType node for each DWARF type, building up two maps in the process:
    # * type ID -> node UUID
    # * composite ID -> type ID
    composite_id_map = {}
    for type_id, typ in ti_map.items():
        # Don't emit the special sentinel for empty types.
        if type_id == DWARFTypeIDSentinel.NONE.value:
            continue

        # NOTE(ww): We make a copy of typ here so that we can remove cached_id,
        # which is an implementation detail from Headache and is not deterministic
        # between runs.
        typ_copy = typ.copy()
        composite_id = typ_copy.pop("cached_id", None)
        dwarf_type_node = {
            "node_kind": DWARF_TYPE_KIND_TO_NODE_KIND[DWARFTypeKind(typ["kind"])].value,
            "dwarf_type": typ_copy,
            "pretty_string": type_id,
        }

        type_uuid = ctx.next_id()
        yield ctx.emit_node(type_uuid, dwarf_type_node)

        type_node_map[type_id] = type_uuid

        if composite_id is not None:
            composite_id_map[composite_id] = type_id

    # Second pass: Now that we have a total map of type IDs to node UUIDs, we
    # can emit edges for the various relationships between types.
    for type_id, typ in ti_map.items():
        # Don't emit the special sentinel for empty types.
        if type_id == DWARFTypeIDSentinel.NONE.value:
            continue

        # TODO(ww): Maybe refactor this using some kind of visitor pattern.
        if typ["kind"] == DWARFTypeKind.BASIC.value:
            # Basic types have no inter-type relations; continue.
            continue
        elif typ["kind"] == DWARFTypeKind.COMPOSITE.value:
            # Composite types have an (optional) base type and a set of element types.
            if typ["base_type"] != DWARFTypeIDSentinel.NONE.value:
                yield from ctx.emit_edge(
                    type_node_map[type_id],
                    type_node_map[typ["base_type"]],
                    EdgeKind.DWARF_TYPE_TO_BASE_TYPE,
                )

            for elem_type_id in typ["elements"]:
                yield from ctx.emit_edge(
                    type_node_map[type_id],
                    type_node_map[elem_type_id],
                    EdgeKind.DWARF_TYPE_TO_MEMBER_TYPE,
                )
        elif typ["kind"] == DWARFTypeKind.COMPOSITE_CACHED.value:
            # "Cached" composites are a pseudo-type that are a byproduct of recursive type
            # handling. We choose to handle them as full-fledged types, giving them
            # an edge back to their referrent type (where the recursion begins).
            # TODO(ww): Evaluate the advantages and disadvantages of this approach.
            # This is nice and simple to implement and makes it more difficult for users to write
            # type queries that inadvertently cycle, but makes for a more clumsy API.
            referrent_type_id = composite_id_map.get(typ["cached_id"])
            if referrent_type_id is not None:
                yield from ctx.emit_edge(
                    type_node_map[type_id],
                    type_node_map[referrent_type_id],
                    EdgeKind.DWARF_TYPE_TO_RECURSIVE_TYPE,
                )
            else:
                logger.error(
                    f"Weird: Got a cached composite (type_id={type_id}) with composite_id={typ['cached_id']} but no referent type?"
                )
        elif typ["kind"] == DWARFTypeKind.STRUCTURE.value:
            # Structures are a specialized composite, with "fields" instead if "elements".
            if typ["base_type"] != DWARFTypeIDSentinel.NONE.value:
                yield from ctx.emit_edge(
                    type_node_map[type_id],
                    type_node_map[typ["base_type"]],
                    EdgeKind.DWARF_TYPE_TO_BASE_TYPE,
                )

            for parent_type_id in typ["parents"]:
                yield from ctx.emit_edge(
                    type_node_map[type_id],
                    type_node_map[parent_type_id],
                    EdgeKind.DWARF_TYPE_TO_PARENT_TYPE,
                )

            for elem_type_id in typ["members"]:
                yield from ctx.emit_edge(
                    type_node_map[type_id],
                    type_node_map[elem_type_id],
                    EdgeKind.DWARF_TYPE_TO_MEMBER_TYPE,
                )
        elif typ["kind"] == DWARFTypeKind.ARRAY.value:
            # Arrays have a base type, representing their contained type.
            if typ["base_type"] != DWARFTypeIDSentinel.NONE.value:
                yield from ctx.emit_edge(
                    type_node_map[type_id],
                    type_node_map[typ["base_type"]],
                    EdgeKind.DWARF_TYPE_TO_BASE_TYPE,
                )
            else:
                # NOTE(ww): This should never happen.
                logger.error(f"Weird: array type with no base type? ID: {type_id}")
        elif typ["kind"] == DWARFTypeKind.ENUM.value:
            # Enums have a base type, representing their enumerable type.
            if typ["base_type"] != DWARFTypeIDSentinel.NONE.value:
                yield from ctx.emit_edge(
                    type_node_map[type_id],
                    type_node_map[typ["base_type"]],
                    EdgeKind.DWARF_TYPE_TO_BASE_TYPE,
                )
            else:
                # NOTE(ww): This should never happen.
                logger.error(f"Weird: enum type with no base type? ID: {type_id}")
        elif typ["kind"] == DWARFTypeKind.UNION.value:
            # Unions are formatted identically to structures.
            if typ["base_type"] != DWARFTypeIDSentinel.NONE.value:
                yield from ctx.emit_edge(
                    type_node_map[type_id],
                    type_node_map[typ["base_type"]],
                    EdgeKind.DWARF_TYPE_TO_BASE_TYPE,
                )

            for elem_type_id in typ["members"]:
                yield from ctx.emit_edge(
                    type_node_map[type_id],
                    type_node_map[elem_type_id],
                    EdgeKind.DWARF_TYPE_TO_MEMBER_TYPE,
                )
        elif typ["kind"] == DWARFTypeKind.CLASS.value:
            # Classes are a specialized structure, with an additional set of template parameters.
            if typ["base_type"] != DWARFTypeIDSentinel.NONE.value:
                yield from ctx.emit_edge(
                    type_node_map[type_id],
                    type_node_map[typ["base_type"]],
                    EdgeKind.DWARF_TYPE_TO_BASE_TYPE,
                )

            for parent_type_id in typ["parents"]:
                yield from ctx.emit_edge(
                    type_node_map[type_id],
                    type_node_map[parent_type_id],
                    EdgeKind.DWARF_TYPE_TO_PARENT_TYPE,
                )

            for elem_type_id in typ["members"]:
                yield from ctx.emit_edge(
                    type_node_map[type_id],
                    type_node_map[elem_type_id],
                    EdgeKind.DWARF_TYPE_TO_MEMBER_TYPE,
                )

            for template_param in typ["template_params"]:
                # NOTE(ww): Experimentally, template value parameters are occasionally
                # missing a type. We handle this in headache by emitting the "none"
                # sentinel; log it here as well.
                if template_param["type"] == DWARFTypeIDSentinel.NONE.value:
                    logger.warning(
                        f"template parameter (kind={template_param['kind']}) has no type"
                    )
                    continue

                yield from ctx.emit_edge(
                    type_node_map[type_id],
                    type_node_map[template_param["type"]],
                    EdgeKind.DWARF_TYPE_TO_TEMPLATE_PARAM_TYPE,
                )
        elif typ["kind"] == DWARFTypeKind.DERIVED.value:
            # Derived types have a base type, representing the type they derive from.
            if typ["base_type"] != DWARFTypeIDSentinel.NONE.value:
                yield from ctx.emit_edge(
                    type_node_map[type_id],
                    type_node_map[typ["base_type"]],
                    EdgeKind.DWARF_TYPE_TO_BASE_TYPE,
                )
            else:
                # NOTE(ww): This should never happen.
                logger.error(f"Weird: derived type with no base type? ID: {type_id}")
        elif typ["kind"] == DWARFTypeKind.SUBROUTINE.value:
            # Subroutine types have a set of parameter types and a single return type.
            # The return type can be the special sentinel "(<void>)".
            if typ["return"] != DWARFTypeIDSentinel.NONE.value:
                yield from ctx.emit_edge(
                    type_node_map[type_id],
                    type_node_map[typ["return"]],
                    EdgeKind.DWARF_TYPE_TO_RETURN_TYPE,
                )
            else:
                # NOTE(ww): This should never happen.
                logger.error(f"Weird: subroutine type with no return type? ID: {type_id}")

            for param_type_id in typ["params"]:
                if param_type_id != DWARFTypeIDSentinel.NONE.value:
                    yield from ctx.emit_edge(
                        type_node_map[type_id],
                        type_node_map[param_type_id],
                        EdgeKind.DWARF_TYPE_TO_PARAM_TYPE,
                    )
                else:
                    # NOTE(ww): This might happen, but is unusual.
                    logger.warning(f"Weird: function parameter with no type? Parent ID: {type_id}")
        else:
            logger.error(f"Weird: Unknown DWARFType kind: {typ['kind']}")
            continue


def emit_global_variable_nodes_and_edges(
    ctx: MarginWalkerContext, asp_global_dicts: List[StringKeyedDict], type_node_map: Dict[str, str]
) -> Iterator[StringKeyedDict]:
    """Yields a ASMGlobalVariable node (and corresponding HasDWARFType edge) for every global
    variable record in ``asp_global_dicts``, using the already constructed ``type_node_map`` for
    type edge drawing."""
    for asp in asp_global_dicts:
        global_variable_node = {
            "node_kind": NodeKind.ASM_GLOBAL_VARIABLE.value,
            "pretty_string": asp["global"]["name"],
            **asp["global"],
        }

        global_variable_uuid = ctx.next_id()
        yield ctx.emit_node(global_variable_uuid, global_variable_node)

        type_uuid = type_node_map.get(asp["global"]["type_id"])
        # Each global variable contains a type_id, which we use to draw an edge to
        # the corresponding type node.
        if type_uuid is None:
            logger.error(
                f"Weird: Couldn't find type node corresponding to ID {asp['global']['type_id']}"
            )
            continue

        yield from ctx.emit_edge(global_variable_uuid, type_uuid, EdgeKind.HAS_DWARF_TYPE)


def emit_wedlock_function_nodes(
    ctx: MarginWalkerContext,
    wed_dicts: List[StringKeyedDict],
    asp_func_dicts: List[StringKeyedDict],
) -> Iterator[Tuple[StringKeyedDict, StringKeyedDict, StringKeyedDict]]:
    """Yields a MachineFunction node (and associated Wedlock + Aspirin function records) for every
    record in ``wed_dicts``."""
    for wed in wed_dicts:
        logger.debug(f"function: {wed['function']['name']}")

        func_node = {
            "node_kind": NodeKind.MACHINE_FUNCTION.value,
            "pretty_string": wed["function"]["demangled_name"],
            "name": wed["function"]["name"],
            "is_mangled": wed["function"]["is_mangled"],
            "demangled_name": wed["function"]["demangled_name"],
            "frame_info": wed["function"]["frame_info"],
            "operand": wed["function"]["operand"],
        }

        # NOTE(ww): Could probably do this when we filter through our
        # aspirin records below to save a loop, but it's a little clearer here.
        asp_func = None
        asp_funcs = [
            asp for asp in asp_func_dicts if asp["function"]["name"] == wed["function"]["name"]
        ]
        if len(asp_funcs) == 0:
            logger.error(
                "Weird: Couldn't find at least one aspirin function record for "
                f"{wed['function']['name']}?"
            )
            continue
        elif len(asp_funcs) > 1:
            logger.error(
                f"Weird: More than one aspirin function record for {wed['function']['name']}?"
            )
            continue

        asp_func = asp_funcs[0]
        func_node.update(
            {
                "va_start": asp_func["function"]["va"],
                "va_end": asp_func["function"]["va_end"],
                "prologues": asp_func["function"]["prologues"],
                "epilogues": asp_func["function"]["epilogues"],
                "offset": asp_func["function"]["offset"],
                "symbols": asp_func["function"]["symbols"],
            }
        )

        if "source" in asp_func["function"]:
            func_node["source"] = asp_func["function"]["source"]

        if "dwarf_type_id" in asp_func["function"]:
            func_node["type_id"] = asp_func["function"]["dwarf_type_id"]

        # Function node.
        func_uuid = ctx.next_id()
        yield ctx.emit_node(func_uuid, func_node), wed, asp_func


def emit_aspirin_param_nodes_and_edges(
    ctx: MarginWalkerContext,
    asp_params: List[StringKeyedDict],
    wed: StringKeyedDict,
    type_node_map: Dict[str, str],
    wed_func_uuid: str,
) -> Iterator[StringKeyedDict]:
    """Yields nodes and edges related to DWARF parameters, as related by ``aspirin``.

    The following nodes are emitted::
        * ``DWARFArgument`` (one per DWARF parameter)

    The following edges are emitted::
        * ``HasDWARFType`` (one per ``DWARFArgument``, relating to ``DWARFType``)
        * ``ArgumentToDWARFArgument`` (one per ``DWARFArgument``, relating to ``Argument``)
        * ``MIFunctionToDWARFArgument`` (one per ``DWARFArgument``, relating to ``MachineFunction``)
    """
    # TODO(ww): This body is identical to that of emit_aspirin_var_nodes_and_edges,
    # with the exception of the generated "UUID". They should be deduplicated at some point.
    for arg in asp_params:
        argument_node = {"node_kind": NodeKind.DWARF_ARGUMENT.value, **arg}

        # TODO(ww): We could generate these now that DWARFArgument is split from Argument.
        if "source_location" not in arg:
            logger.debug(
                f"{arg['name']} has no source location information, "
                "assuming produced in codegen and skipping"
            )
            continue

        argument_uuid = ctx.next_id()
        yield ctx.emit_node(argument_uuid, argument_node)

        yield from ctx.emit_edge(
            wed_func_uuid, argument_uuid, EdgeKind.MI_FUNCTION_TO_DWARF_ARGUMENT
        )

        # TODO(ww): This feature gate needs to be removed (or inverted by default)
        # one we fix Argument <-> DWARFArgument pairing.
        # See: https://gitlab-ext.galois.com/mate/MATE/-/issues/1053
        if not ctx.options.omit_arg_edges:
            line = arg["source_location"]["line"]
            column = arg["source_location"]["column"]
            func_name = arg["source_location"]["func_name"]
            file = arg["source_scope"]["filename"]
            dir_ = arg["source_scope"]["directory"]
            scope_line = arg["source_scope"].get("line", 0)
            scope_column = arg["source_scope"].get("column", 0)
            compressed_id = _compressed_id(
                func_name, dir_, file, line, column, scope_line, scope_column
            )
            llvm_argument_uuid = f"<argument>:{wed['module']['source_stem']}:{compressed_id}:{arg['arg']}:{arg['name']}"

            yield from ctx.emit_edge(
                llvm_argument_uuid, argument_uuid, EdgeKind.ARGUMENT_TO_DWARF_ARGUMENT
            )

        # Each argument contains a type_id, which we use to draw an edge to
        # the corresponding type node.
        type_uuid = type_node_map.get(arg["type_id"])
        if type_uuid is None:
            logger.error(f"Weird: Couldn't find type node corresponding to ID {arg['type_id']}")
            continue

        yield from ctx.emit_edge(argument_uuid, type_uuid, EdgeKind.HAS_DWARF_TYPE)


def emit_aspirin_var_nodes_and_edges(
    ctx: MarginWalkerContext,
    asp_vars: List[StringKeyedDict],
    wed: StringKeyedDict,
    type_node_map: Dict[str, str],
    wed_func_uuid: str,
) -> Iterator[StringKeyedDict]:
    """Yields a DWARFLocalVariable node (and corresponding HasDWARFType edge) for every parameter in
    ``asp_params``, using context in ``wed`` to produce the appropriate ID format for pairing with
    MATE's ``LocalVariable`` nodes."""
    for var in asp_vars:
        variable_node = {"node_kind": NodeKind.DWARF_LOCAL_VARIABLE.value, **var}

        # TODO(ww): We could generate these now that DWARFLocalVariable is split from LocalVariable.
        if "source_location" not in var:
            logger.debug(
                f"{var['name']} has no source location information, "
                "assuming produced in codegen and skipping"
            )
            continue

        variable_uuid = ctx.next_id()
        yield ctx.emit_node(variable_uuid, variable_node)
        yield from ctx.emit_edge(
            wed_func_uuid, variable_uuid, EdgeKind.MI_FUNCTION_TO_DWARF_LOCAL_VARIABLE
        )

        # Each DWARFLocalVariable has a corresponding LLVM-local LocalVariable,
        # which we draw back to using a consistent ID format.
        line = var["source_location"]["line"]
        column = var["source_location"]["column"]
        func_name = var["source_location"]["func_name"]
        file = var["source_scope"]["filename"]
        dir_ = var["source_scope"]["directory"]
        scope_line = var["source_scope"].get("line", 0)
        scope_column = var["source_scope"].get("column", 0)
        compressed_id = _compressed_id(
            func_name, dir_, file, line, column, scope_line, scope_column
        )
        llvm_variable_uuid = f"<local>:{wed['module']['source_stem']}:{compressed_id}:{var['name']}"
        yield from ctx.emit_edge(
            llvm_variable_uuid, variable_uuid, EdgeKind.LOCAL_VARIABLE_TO_DWARF_LOCAL_VARIABLE
        )

        # Each argument contains a type_id, which we use to draw an edge to
        # the corresponding type node.
        type_uuid = type_node_map.get(var["type_id"])
        if type_uuid is None:
            logger.error(f"Weird: Couldn't find type node corresponding to ID {var['type_id']}")
            continue

        yield from ctx.emit_edge(variable_uuid, type_uuid, EdgeKind.HAS_DWARF_TYPE)


def emit_asm_inst_nodes_and_edges(
    ctx: MarginWalkerContext, abb_uuid: str, instr_dicts: List[StringKeyedDict]
) -> Iterator[StringKeyedDict]:
    asm_inst_node = {"node_kind": NodeKind.ASM_INST.value, "pretty_string": "replaceme"}

    first_inst = True
    prev_inst = None
    asm_inst_uuid = None
    for instr in instr_dicts:
        if "_failure" in instr:
            logger.warning(
                f"Undecoded instruction(s) beginning at va={instr['va']}; "
                "not emitting potentially faulty edges"
            )
            return

        asm_inst_uuid = ctx.next_id()
        asm_inst_node.update(**instr)
        asm_inst_node["pretty_string"] = instr["mnemonic"]

        yield ctx.emit_node(asm_inst_uuid, asm_inst_node)

        if first_inst:
            first_inst = False
            prev_inst = asm_inst_uuid

            # Parent ASMBlock -> entry ASMInst edge.
            yield from ctx.emit_edge(abb_uuid, asm_inst_uuid, EdgeKind.BLOCK_TO_ENTRY_INSTRUCTION)
        else:
            # ASMInst -> successor ASMInst edge.
            # NOTE(ww): Bogus mypy error: prev_inst is always-some when `not first_inst`
            yield from ctx.emit_edge(
                prev_inst, asm_inst_uuid, EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION  # type: ignore
            )
            prev_inst = asm_inst_uuid

        # ASMInst -> parent ASMBlock edge.
        yield from ctx.emit_edge(asm_inst_uuid, abb_uuid, EdgeKind.INSTRUCTION_TO_PARENT_BLOCK)

    if asm_inst_uuid is not None:
        # Parent ASMBlock -> terminating ASMInst edge.
        yield from ctx.emit_edge(abb_uuid, asm_inst_uuid, EdgeKind.BLOCK_TO_TERMINATOR_INSTRUCTION)
    else:
        logger.warning(f"No ASMInsts for ASMBlock={abb_uuid}")


def sanity_checks(asp_bb_dicts: List[StringKeyedDict]) -> None:
    logger.debug("running extra sanity checks")

    # Aspirin sanity checks:
    # * Aspirin BB VAs should not overlap, i.e. `va_end` should not be greater
    #   than `va` for subsequent BBs
    asp_bbs = [asp["bb"] for asp in asp_bb_dicts]
    for bb in asp_bbs:
        fbbs = [fbb for fbb in asp_bbs if fbb["va"] > bb["va"]]
        for fbb in fbbs:
            if bb["va_end"] > fbb["va"]:
                logger.error(
                    f"Sanity check failure: BB#{bb['number']} has end VA "
                    f"({hex(bb['va_end'])}, {bb['func_reference']}) > "
                    f"BB#{fbb['number']} begin VA ({hex(fbb['va'])}, {fbb['func_reference']})"
                )


def margin(
    wed_dicts: List[StringKeyedDict],
    asp_dicts: List[StringKeyedDict],
    ti_map: StringKeyedDict,
    cu_dict: StringKeyedDict,
    options: MarginWalkerOptions = MarginWalkerOptions(),
) -> Iterator[StringKeyedDict]:
    ctx = MarginWalkerContext(options)

    # NOTE(ww): We pre-declare these dictionaries so that we don't have to allocate
    # them over and over in the loops below.
    wbb_node = {"node_kind": NodeKind.MACHINE_BASIC_BLOCK.value, "pretty_string": "replaceme"}

    mi_instr_node = {"node_kind": NodeKind.MACHINE_INSTR.value, "pretty_string": "replaceme"}

    abb_node = {"node_kind": NodeKind.ASM_BLOCK.value, "pretty_string": "replaceme"}

    asp_plt_dicts: List[StringKeyedDict] = []
    asp_func_dicts: List[StringKeyedDict] = []
    asp_bb_dicts: List[StringKeyedDict] = []
    asp_global_dicts: List[StringKeyedDict] = []
    asp_module_dict: Optional[StringKeyedDict] = None

    collection_map = {
        AspirinRecordKind.PLTStub.value: asp_plt_dicts,
        AspirinRecordKind.Function.value: asp_func_dicts,
        AspirinRecordKind.BasicBlock.value: asp_bb_dicts,
        AspirinRecordKind.Global.value: asp_global_dicts,
    }

    for asp_dict in asp_dicts:
        if asp_dict["kind"] in collection_map.keys():
            collection_map[asp_dict["kind"]].append(asp_dict)
        elif asp_dict["kind"] == AspirinRecordKind.Module.value:
            if asp_module_dict is not None:
                logger.error("Very weird: more than one module record?")
                continue
            asp_module_dict = asp_dict
        else:
            logger.debug(f"Skipping unknown aspirin record kind: {asp_dict['kind']}")

    if options.sanity_checks:
        sanity_checks(asp_bb_dicts)

    if not options.omit_plt_stub_nodes:
        for plt_stub_node in emit_plt_stub_nodes(ctx, asp_plt_dicts):
            yield plt_stub_node

    if not options.omit_translation_unit_nodes:
        if asp_module_dict is None:
            raise MarginError("Barf: No module record?")

        for tu_node_or_edge in emit_translation_unit_nodes_and_edges(ctx, cu_dict, asp_module_dict):
            yield tu_node_or_edge

    type_node_map: Dict[str, str] = {}
    if not options.omit_type_nodes:
        for type_node in emit_type_nodes_and_edges(ctx, ti_map, type_node_map):
            yield type_node

    if not options.omit_global_nodes:
        for gv_node_or_edge in emit_global_variable_nodes_and_edges(
            ctx, asp_global_dicts, type_node_map
        ):
            yield gv_node_or_edge

    for wed_func_node, wed, asp_func in emit_wedlock_function_nodes(ctx, wed_dicts, asp_func_dicts):
        if not options.omit_wedlock_function_nodes:
            yield wed_func_node

        func_name = wed["function"]["name"]
        func_uuid = wed_func_node["uuid"]

        # add edge between MIFunc and DwarfType
        if "dwarf_type_id" in asp_func["function"]:
            type_id = asp_func["function"]["dwarf_type_id"]
            type_uuid = type_node_map[type_id]
            yield from ctx.emit_edge(func_uuid, type_uuid, EdgeKind.HAS_DWARF_TYPE)

        if not options.omit_param_nodes:
            asp_params = asp_func["function"].get("params", [])
            for param_node_or_edge in emit_aspirin_param_nodes_and_edges(
                ctx,
                asp_params,
                wed,
                type_node_map,
                func_uuid,
            ):
                yield param_node_or_edge

        if not options.omit_var_nodes:
            asp_vars = asp_func["function"].get("vars", [])
            for var_node_or_edge in emit_aspirin_var_nodes_and_edges(
                ctx, asp_vars, wed, type_node_map, func_uuid
            ):
                yield var_node_or_edge

        # Wedlock function -> Galois LLVM IR function edge.
        # NOTE(ww): Not really a UUID.
        irfunc_uuid = f"<function>:{wed['module']['source_stem']}:{wed['function']['operand']}"
        yield from ctx.emit_edge(func_uuid, irfunc_uuid, EdgeKind.MI_FUNCTION_TO_IR_FUNCTION)

        bb_map = {}
        first_bb = True
        for bb in wed["function"]["bbs"]:
            # Basic block nodes.
            wbb_uuid = ctx.next_id()
            wbb_node = dict(wbb_node, **{i: bb["mi"][i] for i in bb["mi"] if i != "asm"})
            wbb_node["pretty_string"] = bb["mi"]["symbol"]
            bb_map[bb["mi"]["symbol"]] = wbb_uuid
            yield ctx.emit_node(wbb_uuid, wbb_node)

            if first_bb:
                first_bb = False
                # Function -> entry basic block edge.
                yield from ctx.emit_edge(func_uuid, wbb_uuid, EdgeKind.FUNCTION_TO_ENTRY_BLOCK)

            # Basic block -> parent function edge.
            yield from ctx.emit_edge(wbb_uuid, func_uuid, EdgeKind.BLOCK_TO_PARENT_FUNCTION)

            if "ir" in bb:
                # NOTE(ww): This check is dependent on nomina: LLVM will re-modify
                # our IR during codegen (i.e., after canonicalization) in order to
                # insert basic blocks for things like exception handling. These
                # IR BBs exist in Wedlock's view of the IR but not in MATE's because
                # only Wedlock runs in the middle-end, so we need to filter edges
                # before they can cause integrity issues with the CPG.
                # Observe that this is almost identical to the filter above; we just
                # need to catch it separately because the view of the IR we have is
                # slightly lowered.
                if re.search(_IR_BB_OPERAND_PATTERN, bb["ir"]["operand"]):
                    # Wedlock basic block -> Galois LLVM IR basic block edge.
                    # NOTE(ww): Not really a UUID.
                    irbb_uuid = (
                        f"<block>:{wed['module']['source_stem']}:"
                        f"{wed['function']['operand']}:{bb['ir']['operand']}"
                    )
                    yield from ctx.emit_edge(wbb_uuid, irbb_uuid, EdgeKind.MI_BLOCK_TO_IR_BLOCK)
                else:
                    logger.debug(
                        f"{bb['ir']['operand']} looks uncanonicalized, "
                        "assuming produced in codegen and skipping"
                    )
            else:
                logger.debug(f"Skipping MI to IR edge for unpaired MI BB: {bb['mi']['symbol']}")

            # TODO(ww): De-dupe below.

            first_instr = True
            prev_instr = None
            mi_instr_uuid = None
            for idx, instr in enumerate(bb["mi"]["instrs"]):
                # MIR instruction node.
                mi_instr_uuid = ctx.next_id()
                mi_instr_node["opcode"] = instr["opcode"]
                mi_instr_node["flags"] = instr["flags"]

                # If our Wedlock output includes pretty-printed machine instructions,
                # include the corresponding one in our node.
                if len(bb["mi"]["asm"]) > 0:
                    mi_instr_node["pretty_string"] = bb["mi"]["asm"][idx]

                yield ctx.emit_node(mi_instr_uuid, mi_instr_node)

                if first_instr:
                    first_instr = False
                    prev_instr = mi_instr_uuid
                    # Parent MachineBasicBlock -> entry MachineInstr edge.
                    yield from ctx.emit_edge(
                        wbb_uuid, mi_instr_uuid, EdgeKind.BLOCK_TO_ENTRY_INSTRUCTION
                    )
                else:
                    # MachineInstr -> successor MachineInstr edge.
                    # NOTE(ww): Bogus mypy error: prev_instr is always-some when `not first_inst`
                    yield from ctx.emit_edge(
                        prev_instr,  # type: ignore
                        mi_instr_uuid,
                        EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION,
                    )
                    prev_instr = mi_instr_uuid

                # MachineInstr -> parent MachineBasicBlock edge.
                yield from ctx.emit_edge(
                    mi_instr_uuid, wbb_uuid, EdgeKind.INSTRUCTION_TO_PARENT_BLOCK
                )

            if mi_instr_uuid is not None:
                # Parent MachineBasicBlock -> terminating MachineInstr edge.
                yield from ctx.emit_edge(
                    wbb_uuid, mi_instr_uuid, EdgeKind.BLOCK_TO_TERMINATOR_INSTRUCTION
                )
            else:
                logger.warning(f"No MachineInstrs for MachineBasicBlock={wbb_uuid}")

            # TODO(ww): Edge from last MI instr to next BB

        # Second basic block pass: now that we have a map of BB symbols -> UUIDs built,
        # we can connect each basic block to its predecessors and successors.
        for bb in wed["function"]["bbs"]:
            mibb = bb["mi"]

            try:
                wbb_uuid = bb_map[mibb["symbol"]]
            except KeyError:
                logger.error(f"Very weird: {func_name}:{mibb['symbol']} isn't in bb_map")
                continue

            for succ in mibb["succs"]:
                # Basic block -> successor BB edge.
                succ_uuid = bb_map.get(succ["symbol"])
                if not succ_uuid:
                    logger.error(
                        f"Weird: {func_name}:{mibb['symbol']} has succ "
                        f"{succ['symbol']} but not in map"
                    )
                    continue
                yield from ctx.emit_edge(wbb_uuid, succ_uuid, EdgeKind.BLOCK_TO_SUCCESSOR_BLOCK)

        # Third basic block pass: isolate the Migraine/aspirin records that we're
        # interested in, create nodes for their BBs and compiled instructions,
        # and draw edges to IR/MI/ASM.
        # NOTE(ww): This is independent from the pass above and so could be merged
        # with it, but I've put it down here for readability.
        asps = [asp for asp in asp_bb_dicts if asp["function"]["name"] == func_name]
        logger.debug(f"{len(asps)} aspirin records for {func_name}")
        for bb in wed["function"]["bbs"]:
            unpaired = False
            irbb = bb.get("ir")
            if irbb is None:
                logger.debug("No IR for this basic block; using MI information where possible")
                unpaired = True

            mibb = bb["mi"]

            if unpaired:
                match_operand = mibb["symbol"]
            else:
                match_operand = irbb["operand"]

            asp_bb = next(
                (asp["bb"] for asp in asps if asp["bb"]["operand"] == match_operand), None
            )

            if asp_bb is None:
                logger.debug(
                    f"Unable to associate {func_name}:{match_operand} with aspirin BB; "
                    "assuming optimized away"
                )
                continue

            # Migraine/aspirin BB node.
            abb_uuid = ctx.next_id()
            abb_node = dict(
                abb_node,
                **{i: asp_bb[i] for i in asp_bb if i not in FILTERED_ASPIRIN_BB_ATTRIBUTES},
            )
            abb_node["pretty_string"] = asp_bb["operand"]
            yield ctx.emit_node(abb_uuid, abb_node)

            if not options.omit_asm_inst_nodes:
                for asm_inst_node_or_edge in emit_asm_inst_nodes_and_edges(
                    ctx, abb_uuid, asp_bb["instructions"]
                ):
                    yield asm_inst_node_or_edge

            # Wedlock BB -> Migraine/aspirin BB edge.
            try:
                wbb_uuid = bb_map[mibb["symbol"]]
            except KeyError:
                logger.error(
                    f"Very weird: {func_name}:{mibb['symbol']} ({match_operand}) not in BB map"
                )
                continue

            yield from ctx.emit_edge(wbb_uuid, abb_uuid, EdgeKind.MI_BLOCK_TO_ASM_BLOCK)


def main() -> None:
    args = parser.parse_args()

    with args.aspirin as aspirin:
        asp_dicts = [loads(jsonl) for jsonl in aspirin]

    with args.wedlock as wedlock:
        wed_dicts = [loads(jsonl) for jsonl in wedlock]

    with args.headache_ti as headache_ti:
        ti_map = {}
        for jsonl in headache_ti:
            ti_record = loads(jsonl)
            ti_map[ti_record["type_id"]] = ti_record["type"]

    with args.headache_cu as headache_cu:
        cu_dict = loads(headache_cu.read())

    options = MarginWalkerOptions(
        sanity_checks=args.sanity_checks,
        omit_plt_stub_nodes=args.omit_plt_stub_nodes,
        omit_translation_unit_nodes=args.omit_translation_unit_nodes,
        omit_type_nodes=args.omit_type_nodes,
        omit_global_nodes=args.omit_global_nodes,
        omit_wedlock_function_nodes=args.omit_wedlock_function_nodes,
        omit_param_nodes=args.omit_param_nodes,
        omit_var_nodes=args.omit_var_nodes,
        omit_asm_inst_nodes=args.omit_asm_inst_nodes,
        omit_arg_edges=not args.emit_arg_edges,
    )

    for record in margin(wed_dicts, asp_dicts, ti_map, cu_dict, options=options):
        print(dumps(record), file=args.output)


if __name__ == "__main__":
    main()
