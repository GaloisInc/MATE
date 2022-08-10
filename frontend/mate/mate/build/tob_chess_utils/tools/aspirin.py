#!/usr/bin/env python3

# aspirin.py: Take a binary instrumented by the Headache pass
# and extract the virtual addresses of all basic blocks.

import argparse
import enum
import json
import os
import re
import struct
import sys
from collections import defaultdict
from types import ModuleType
from typing import Any, BinaryIO, Dict, Iterator, List, NamedTuple, Optional, Set, Tuple

import iced_x86
from elftools.dwarf.die import DIE
from elftools.dwarf.dwarfinfo import DWARFInfo
from elftools.elf.elffile import ELFFile
from elftools.elf.sections import Symbol, SymbolTableSection

from mate.build.tob_chess_utils.dwarf import (
    decode_global_location,
    global_dies_map,
    summarize_func_dies,
    va_dies_map,
)
from mate.build.tob_chess_utils.elf import (
    get_global_va,
    get_symbol_va_base,
    get_va_text_base,
    plt_va_map,
    va_symbol_map,
)
from mate.build.tob_chess_utils.logging import make_logger

_MIGRAINE_BB_PATTERN = re.compile(r"^migraine::bb::(.+)::(.+)::(.+)$")
_MIGRAINE_FUNC_PATTERN = re.compile(r"^migraine::func::(.+)::(.+)$")

_UNPAIRED_BB_PATTERN = re.compile(r"ex_(.+)$")
_BB_PATTERN = re.compile(r"(%.+)$")

logger = make_logger(__name__)

parser = argparse.ArgumentParser(
    description="Extract variable information and basic block addresses "
    "from a migraine-instrumented binary and the output of the headache pass"
)
parser.add_argument("-b", "--binary", type=argparse.FileType("rb"), required=True, help="ELF input")
parser.add_argument(
    "-H", "--headache_vi", type=argparse.FileType("r"), required=True, help="Headache VI input"
)
parser.add_argument(
    "-o", "--output", type=argparse.FileType("w"), default=sys.stdout, help="JSONL output"
)
parser.add_argument(
    "-Xl",
    "--omit_line_program",
    action="store_true",
    help="Don't emit source line pairings that come from the line program",
)


AspirinRecord = Dict[str, Any]


@enum.unique
class AspirinRecordKind(str, enum.Enum):
    Local = "local"
    Global = "global"
    BasicBlock = "bb"
    PLTStub = "plt_stub"
    Module = "module"
    Function = "function"
    VTable = "vtable"


class VALineEntry(NamedTuple):
    va: int
    filename: str
    line: int
    column: int
    is_prologue_end: bool
    is_epilogue_begin: bool


class MachineInfo(NamedTuple):
    arch: str
    addr_len: int
    decoder_bitness: int


class AspirinContext(NamedTuple):
    binary: BinaryIO
    elf: ELFFile
    dwarf: DWARFInfo
    symtab: SymbolTableSection
    va_symbols: Dict[int, List[Symbol]]
    line_program_pairings: bool
    va_line_entries: Set[VALineEntry]
    va_line_func_map: Dict[str, Set[VALineEntry]]
    func_epilogue_begin_map: Dict[str, Set[int]]
    func_prologue_end_map: Dict[str, Set[int]]
    vi_dicts: List[dict]
    machine: MachineInfo
    formatter: iced_x86.Formatter
    info_factory: iced_x86.InstructionInfoFactory


def _module_enum_map(mod: ModuleType) -> Dict[str, Any]:
    return {mod.__dict__[key]: key for key in mod.__dict__ if isinstance(mod.__dict__[key], int)}


ICED_REG2STR = _module_enum_map(iced_x86.Register)
ICED_OPACCESS2STR = _module_enum_map(iced_x86.OpAccess)
ICED_CODE2STR = _module_enum_map(iced_x86.Code)


def lpe_filename(file_index: int, lp_header: Any) -> str:
    assert file_index != 0, "Asked to find a line-program for index=0"

    file_entries = lp_header["file_entry"]
    assert file_index - 1 < len(file_entries), f"index={file_index} exceeds file entry table"

    # File and directory indices are 1-indexed.
    file_entry = file_entries[file_index - 1]
    dir_index = file_entry["dir_index"]

    # dir_index == 0 indicates the absence of an absolute directory.
    if dir_index == 0:
        return file_entry.name.decode()

    directory = lp_header["include_directory"][dir_index - 1]

    return os.path.join(directory, file_entry.name).decode()


def build_va_line_entries(elf: ELFFile) -> Set[VALineEntry]:
    va_base = get_va_text_base(elf)
    lines = set()
    dwarf = elf.get_dwarf_info()
    for cu in dwarf.iter_CUs():
        cu_die = cu.get_top_DIE()
        if cu_die.tag != "DW_TAG_compile_unit":
            logger.error(f"Weird: Expected DW_TAG_compile_unit, got {cu_die.tag}")
            continue

        line_program = dwarf.line_program_for_CU(cu)
        if line_program is None:
            logger.error("Weird: CU missing an entry in .debug_line?")
            continue
        for lpe in line_program.get_entries():
            # Skip entries that don't introduce a new state.
            # NOTE(ww): See DWARFv4, 6.2.2 State Machine Registers
            if lpe.state is not None:
                filename = lpe_filename(lpe.state.file, line_program.header)
                lines.add(
                    VALineEntry(
                        lpe.state.address - va_base,
                        filename,
                        lpe.state.line,
                        lpe.state.column,
                        lpe.state.prologue_end,
                        lpe.state.epilogue_begin,
                    )
                )

    return lines


def pair_bb_line_entries(asp_ctx: AspirinContext, bb_dict: Dict[str, Any]) -> None:
    """Pair the given basic block record with its line program entries, modifying the record in the
    process, if requested via ``asp_ctx.line_program_pairings``."""
    if not asp_ctx.line_program_pairings:
        return

    source = set()
    va_start = bb_dict["bb"]["va"] - bb_dict["va_base"]
    va_end = bb_dict["bb"]["va_end"] - bb_dict["va_base"]

    # NOTE(ww): Instead of iterating over the entire line entry table,
    # we use the cached map of function -> line entries.
    line_entries = asp_ctx.va_line_func_map[bb_dict["function"]["name"]]
    for line_entry in line_entries:
        if va_start <= line_entry.va <= va_end:
            source.add((line_entry.filename, line_entry.line, line_entry.column))

    logger.debug(
        f"Associated {bb_dict['function']['name']}:{bb_dict['bb']['operand']} "
        f"with {len(source)} lines of source"
    )
    bb_dict["bb"]["source"] = list(source)


def pair_bb_instructions(asp_ctx: AspirinContext, bb_dict: Dict[str, Any]) -> None:
    """Pair the given basic block record with information about each x86(_64) instruction within it,
    in order of appearance."""
    asp_ctx.binary.seek(bb_dict["bb"]["offset"])

    decoder = iced_x86.Decoder(
        asp_ctx.machine.decoder_bitness,
        asp_ctx.binary.read(bb_dict["bb"]["size"]),
        iced_x86.DecoderOptions.NONE,
        bb_dict["bb"]["va"],
    )
    instructions = []

    raw_offset = 0
    while (raw_offset < bb_dict["bb"]["size"]) and decoder.can_decode:
        insn = decoder.decode()
        if insn.is_invalid:
            logger.warning(f"Weird: iced-x86 decoding failure: {insn.last_error=}")
            # NOTE(ww): We treat _failure as a sentinel in margin-walker.
            # See emit_asm_inst_nodes_and_edges.
            instructions.append(
                {"_failure": str(insn.last_error), "va": raw_offset + bb_dict["bb"]["va"]}
            )
            break

        sema = asp_ctx.info_factory.info(insn)

        instructions.append(
            {
                "va": insn.ip,
                "size": insn.len,
                "mnemonic": asp_ctx.formatter.format_mnemonic(
                    insn, iced_x86.FormatMnemonicOptions.NO_PREFIXES
                ),
                "asm": asp_ctx.formatter.format(insn),
                "used_registers": [
                    {"register": ICED_REG2STR[ri.register], "access": ICED_OPACCESS2STR[ri.access]}
                    for ri in sema.used_registers()
                ],
                "used_memory": [
                    {
                        "segment": ICED_REG2STR[mi.segment],
                        "base": ICED_REG2STR[mi.base],
                        "index": ICED_REG2STR[mi.index],
                        "scale": mi.scale,
                        "displacement": mi.displacement,
                        "memory_size": iced_x86.MemorySizeExt.size(mi.memory_size),
                        "access": ICED_OPACCESS2STR[mi.access],
                        "vsib_size": mi.vsib_size,
                    }
                    for mi in sema.used_memory()
                ],
            }
        )

        raw_offset += insn.len

    if bb_dict["bb"]["va"] + raw_offset != bb_dict["bb"]["va_end"]:
        logger.error(
            f"Weird: Either undershot or overshot the end VA? "
            f"{bb_dict['bb']['va'] + raw_offset} != {bb_dict['bb']['va_end']}"
        )

    bb_dict["bb"]["instructions"] = instructions


def pair_function_line_entries(asp_ctx: AspirinContext, func_dict: Dict[str, Any]) -> None:
    """Pair the given function record with its line program entries.

    Adds the entries to the function record, if requested. Otherwise, updates
    ``asp_ctx.va_line_func_map`` and ``asp_ctx.func_epilogue_begin_map`` with the results.
    """

    source = set()
    func_name = func_dict["function"]["name"]
    va_start = func_dict["function"]["va"] - func_dict["va_base"]
    va_end = func_dict["function"]["va_end"] - func_dict["va_base"]

    for line_entry in asp_ctx.va_line_entries:
        if va_start <= line_entry.va <= va_end:
            source.add((line_entry.filename, line_entry.line, line_entry.column))
            asp_ctx.va_line_func_map[func_name].add(line_entry)
            # NOTE(ww): LLVM 10 emits DW_LNS_set_prologue_end but not
            # DW_LNS_set_epilogue_begin. Why? Unclear. As a result, we expect
            # this condition to never be hit for the time being, and we throw
            # some logs in for the off-chance that it does get hit.
            if line_entry.is_epilogue_begin:
                logger.debug(
                    f"Interesting: line program table contains DW_LNS_set_prologue: {line_entry=}"
                )
                asp_ctx.func_epilogue_begin_map[func_name].add(line_entry.va)
            if line_entry.is_prologue_end:
                asp_ctx.func_prologue_end_map[func_name].add(line_entry.va)

    logger.debug(f"Associated {func_name} with {len(source)} line entries")

    if asp_ctx.line_program_pairings:
        func_dict["function"]["source"] = list(source)


def pair_local_type_information(
    asp_ctx: AspirinContext, func_name: str, var_dict: Dict[str, Any]
) -> None:
    scope = var_dict["dwarf_scope"]

    if "from_variadic_template" in var_dict:
        var_name = var_dict["original_name"]
        logger.debug(
            "Found parameter expanded from variadic template: "
            f"{func_name}:{var_name}#{var_dict['parameter_index']}"
        )
    else:
        var_name = var_dict["name"]

    # NOTE(ww): We use `llvm_func_name` here, since the function name that we're matching
    # against comes from migraine, which in turn grabs it from LLVM via Wedlock.
    vi_vars = [
        vi
        for vi in asp_ctx.vi_dicts
        if vi["kind"] == AspirinRecordKind.Local.value
        and vi["source_location"]["llvm_func_name"] == func_name
        and vi["name"] == var_name
        and vi["source_location"]["line"] == scope["line"]
        and vi["source_scope"]["tag"] == scope["tag"]
    ]

    # If we're pairing information for a parameter, we additionally disambiguate on
    # the linkage name for the enclosing source scope (since, for parameters, we know
    # that the enclosing scope will be a function).
    if var_dict["parameter"]:
        vi_vars = [
            vi
            for vi in vi_vars
            if vi["source_scope"]["linkage_name"] == func_name
            # NOTE(ww): Annoying: LLVM's DISubprogram::getLinkageName returns an empty
            # string instead of the unmangled name if no linkage mangling is performed,
            # causing us to incorrectly filter out all VI dictionaries on C binaries.
            # The check below makes sure we don't do that.
            or vi["source_scope"]["name"] == func_name
        ]

    # Only disambiguate on arg/variadic_index if we actually have more
    # than one expanded variadic parameter to disambiguate.
    if len(vi_vars) > 1 and "from_variadic_template" in var_dict:
        logger.debug(
            f"Found {len(vi_vars)} variables named {var_name}, "
            "assuming variadic and disambiguating"
        )
        # TODO(ww): Comparing against the exact arg number here is probably unreliable,
        # since the numbers/indices can shift around with codegen (e.g., insertion
        # of artificial `this` parameters). Instead, we should really just check
        # that there are as many template-expanded variables as duplicate
        # variables at the same location and connect them pairwise.
        vi_vars = [vi for vi in vi_vars if vi["arg"] - 1 == var_dict["parameter_index"]]

    if len(vi_vars) == 1:
        var_dict.update(**vi_vars[0])
    elif len(vi_vars) == 0:
        logger.debug(f"Weird: Couldn't find type information for {func_name}:{var_name}?")
    elif len(vi_vars) > 1:
        logger.debug(json.dumps(vi_vars))
        logger.error(f"Barf: Couldn't disambiguate {len(vi_vars)} locals named {var_name}")


def pair_global_type_information(
    asp_ctx: AspirinContext, global_name: str, var_die: DIE
) -> Optional[Dict[str, Any]]:
    parent = var_die.get_parent()
    if parent.tag != "DW_TAG_compile_unit":
        logger.debug(
            f"Weird: Expected global {global_name} to be a child of a compilation unit, "
            f"but parent is {parent.tag}"
        )
        return None

    cu_filename = parent.attributes.get("DW_AT_name")
    cu_directory = parent.attributes.get("DW_AT_comp_dir")

    if cu_filename is not None and cu_directory is not None:
        cu_filename = cu_filename.value.decode()
        cu_directory = cu_directory.value.decode()
    else:
        logger.debug(
            f"Weird: Compilation unit for global {global_name} is missing filename or "
            "directory attributes"
        )
        return None

    vi_vars = [
        vi
        for vi in asp_ctx.vi_dicts
        if vi["kind"] == AspirinRecordKind.Global.value
        and (vi["name"] == global_name or vi["linkage_name"] == global_name)
        and vi["source_scope"]["filename"] == cu_filename
        and vi["source_scope"]["directory"] == cu_directory
    ]

    vi = None
    if len(vi_vars) == 0:
        logger.debug(f"Weird: Couldn't find type information for {global_name}?")
    elif len(vi_vars) > 1:
        logger.debug(f"Weird: Couldn't disambiguate {len(vi_vars)} globals named {global_name}")
    else:
        vi = vi_vars[0]

    return vi


def aspirin_module_record(asp_ctx: AspirinContext) -> Dict[str, Any]:
    return {
        "kind": AspirinRecordKind.Module.value,
        "symbols": [
            {
                "name": symbol.name,
                "va": symbol["st_value"],
                "size": symbol["st_size"],
                "binding": symbol["st_info"]["bind"],
                "type": symbol["st_info"]["type"],
                "visibility": symbol["st_other"]["visibility"],
            }
            for symbol in asp_ctx.symtab.iter_symbols()
        ],
    }


def aspirin_plt_stub_record(_asp_ctx: AspirinContext, stub_name: str, va: int) -> Dict[str, Any]:
    return {
        "kind": AspirinRecordKind.PLTStub.value,
        "symbol": stub_name,
        "va": va,
    }


def aspirin_func_record(
    asp_ctx: AspirinContext, va_dies: Dict[int, Set[DIE]], migraine_id: str, va: int
) -> Optional[Dict[str, Any]]:
    match = re.search(_MIGRAINE_FUNC_PATTERN, migraine_id)
    if not match:
        logger.error(f"Weird: Migraine symbol doesn't match expected pattern: {migraine_id}")
        return None

    source_stem = match.group(1)
    func_name = match.group(2)

    func_syms = asp_ctx.symtab.get_symbol_by_name(func_name)
    if func_syms is None:
        logger.error(f"Weird: {func_name} has no symbol in .symtab?")
        return None

    if len(func_syms) > 1:
        logger.error(
            f"Weird: >1 ({len(func_syms)}) symbols for {func_name}: {', '.join(func_syms)}"
        )
        return None

    func_sym = func_syms[0]
    func_size = func_sym["st_size"]
    func_off = next(asp_ctx.elf.address_offsets(va, asp_ctx.machine.addr_len), None)

    migrane_func_dict: Dict[str, Any] = {
        "kind": AspirinRecordKind.Function.value,
        "va_base": get_va_text_base(asp_ctx.elf),
        "module": {"name": source_stem},
        "function": {
            "name": func_name,
            "symbols": [s.name for s in asp_ctx.va_symbols[va]],
            "va": va,
            "size": func_size,
            "va_end": va + func_size,
            "offset": func_off,
            "prologues": [],  # NOTE(ww): Filled in during migraine anchor parsing.
            "epilogues": [],  # NOTE(ww): Filled in during migraine anchor parsing.
        },
    }

    # Add some debug info, if available
    dies = va_dies.get(va)
    if dies is not None:
        logger.debug(f"Found {len(dies)} DIEs for {func_name}")
        migrane_func_dict["function"].update(
            **summarize_func_dies(func_name, dies, asp_ctx.dwarf, asp_ctx.machine.arch)
        )
        for var_dict in [
            *migrane_func_dict["function"]["params"],
            *migrane_func_dict["function"]["vars"],
        ]:
            pair_local_type_information(asp_ctx, func_name, var_dict)
    else:
        logger.debug(f"Skipping debug info extraction for {func_name}")

    pair_function_line_entries(asp_ctx, migrane_func_dict)

    # Link to the Function's DwarfType type_id if available
    for entry in asp_ctx.vi_dicts:
        if "kind" in entry and entry["kind"] == "function" and entry["func_name"] == func_name:
            migrane_func_dict["function"]["dwarf_type_id"] = entry["type_id"]
            break

    return migrane_func_dict


def aspirin_bb_record(
    asp_ctx: AspirinContext, migraine_id: str, va: int
) -> Optional[Dict[str, Any]]:
    match = re.search(_MIGRAINE_BB_PATTERN, migraine_id)
    if not match:
        logger.error(f"Weird: Migraine symbol doesn't match expected pattern: {migraine_id}")
        return None

    source_stem = match.group(1)
    func_name = match.group(2)
    bb_stem = match.group(3)
    unpaired = False

    if bb_stem.startswith("ex_"):
        logger.debug(f"Found unpaired (no matching IR BB) migraine symbol: {migraine_id}")
        match = re.search(_UNPAIRED_BB_PATTERN, bb_stem)
        unpaired = True
    else:
        match = re.search(_BB_PATTERN, bb_stem)

    if not match:
        logger.error(f"Weird: Migraine BB stem doesn't match expected pattern: {bb_stem}")
        return None
    bb_operand = match.group(1)

    # Use our parent function name to get the corresponding symbol table
    # entry + function entry VA.
    func_syms = asp_ctx.symtab.get_symbol_by_name(func_name)
    if func_syms is None:
        logger.error(f"Weird: Function {func_name} has no corresponding symbol?")
        return None

    if len(func_syms) > 1:
        logger.warning(
            f"Weird: >1 ({len(func_syms)}) symbols for {func_name}: {', '.join(func_syms)}"
        )

    func_sym = func_syms[0]
    func_va = func_sym["st_value"]
    func_size = func_sym["st_size"]
    func_off = next(asp_ctx.elf.address_offsets(func_va, asp_ctx.machine.addr_len), None)

    if not func_off:
        logger.error(f"Weird: {func_name} at VA {func_va} doesn't refer to a valid file offset?")
        return None

    logger.debug(f"Parent function {func_name} VA: {hex(func_va)} (offset={func_off})")

    # Finally, we also turn the block VA into a real file offset, just
    # for convenience.
    offset = next(asp_ctx.elf.address_offsets(va), None)
    if not offset:
        logger.error(f"BB VA {hex(va)} for {migraine_id} doesn't refer to a valid file offset?")
        return None

    logger.debug(f"{func_name}:BB:{bb_operand} begins at {hex(va)} (offset={hex(offset)})!")

    migraine_bb_dict = {
        "kind": AspirinRecordKind.BasicBlock.value,
        "va_base": get_va_text_base(asp_ctx.elf),
        "module": {"source_stem": source_stem},
        "function": {
            "name": func_name,
            "va": func_va,
            "size": func_size,
            "va_end": func_va + func_size,
            "offset": func_off,
        },
        "bb": {
            "unpaired": unpaired,
            "operand": bb_operand,
            "va": va,
            # NOTE(ww): We determine the va_end and size in aspirin_bb_end_record.
            "va_end": 0,
            "size": 0,
            "offset": offset,
            "func_offset": va - func_va,
            "func_reference": f"{func_name}+{hex(va - func_va)}",
        },
    }
    return migraine_bb_dict


def aspirin_global_records_for_name(asp_ctx: AspirinContext, global_name: str, dies: List[DIE]):
    logger.debug(f"Emitting records for {len(dies)} associated with {global_name}")

    global_syms = asp_ctx.symtab.get_symbol_by_name(global_name)
    if global_syms is None:
        logger.debug(f"Weird: {global_name} has no symbol in .symtab?")
        return

    if len(global_syms) > 1:
        logger.error(
            f"Weird: >1 ({len(global_syms)}) symbols for {global_name}: {', '.join(global_syms)}"
        )
        return

    global_sym = global_syms[0]
    global_pairs = [(die, pair_global_type_information(asp_ctx, global_name, die)) for die in dies]

    for die, vi in global_pairs:
        if vi is None:
            logger.error(f"missing variable information for {global_name}: {die}")
            continue

        if "DW_AT_location" not in die.attributes and not vi["local_to_unit"]:
            logger.debug(f"Likely ODR violation for {global_name}")
            continue

        yield {
            "kind": AspirinRecordKind.Global.value,
            "va_base": get_symbol_va_base(asp_ctx.elf, global_sym),
            "global": {
                "name": global_sym.name,
                "thread_local": global_sym["st_info"]["type"] == "STT_TLS",
                "definition_location": vi["definition_location"],
                "definition": vi["definition"],
                "local_to_unit": vi["local_to_unit"],
                "source_scope": vi["source_scope"],
                "type_id": vi["type_id"],
                "dwarf_location": decode_global_location(die, asp_ctx.dwarf),
                "va": get_global_va(asp_ctx.elf, global_sym),
            },
        }


def parse_migraine_addrs(migraine_addrs: bytes) -> Iterator[Tuple[str, int]]:
    # Each migraine record is a tuple of three fields:
    #  * ID length (8 bytes)
    #  * ID (variable)
    #  * VA (8 bytes)
    idx = 0
    while idx < len(migraine_addrs):
        (id_len,) = struct.unpack("<Q", migraine_addrs[idx : idx + 8])
        idx += 8

        (migraine_id,) = struct.unpack(f"{id_len}s", migraine_addrs[idx : idx + id_len])
        migraine_id = migraine_id.decode()
        idx += id_len

        (va,) = struct.unpack("<Q", migraine_addrs[idx : idx + 8])
        idx += 8

        logger.debug(f"Found migraine record: {migraine_id} with VA={hex(va)}")
        yield migraine_id, va


def aspirin_bb_end_record(
    asp_ctx: AspirinContext, bb_dict: Dict[str, Any], _migraine_id: str, va: int
) -> Dict[str, Any]:
    # TODO(ww): We could sanity-check migraine_id here by comparing its
    # embdeed operand to bb_dict["bb"]["operand"].

    # NOTE(ww): It's important that we set these before pair_bb_line_entries and
    # pair_bb_instructions: the former uses va_end, and the latter uses size.
    bb_dict["bb"]["va_end"] = va
    bb_dict["bb"]["size"] = bb_dict["bb"]["va_end"] - bb_dict["bb"]["va"]

    pair_bb_line_entries(asp_ctx, bb_dict)
    pair_bb_instructions(asp_ctx, bb_dict)
    return bb_dict


def aspirin(
    binary: BinaryIO, vi_dicts: List[Dict[str, Any]], line_program: bool = False
) -> Iterator[AspirinRecord]:
    elf = ELFFile(binary)
    if not elf.has_dwarf_info():
        logger.error("Barf: No DWARF information in input binary; recompile with -g?")
        yield from ()

    if elf["e_machine"] == "EM_386":
        addr_len, decoder_bitness = (
            4,
            32,
        )
    elif elf["e_machine"] == "EM_X86_64":
        addr_len, decoder_bitness = (
            8,
            64,
        )
    else:
        logger.error(f"Barf: Unsupported machine type in ELF: {elf['e_machine']}")
        yield from ()

    dwarf = elf.get_dwarf_info()
    va_dies = va_dies_map(dwarf)
    elf_arch = elf.get_machine_arch()

    va_line_entries = build_va_line_entries(elf)
    va_line_func_map: Dict[str, Set[VALineEntry]] = defaultdict(set)
    func_epilogue_begin_map: Dict[str, Set[int]] = defaultdict(set)
    func_prologue_end_map: Dict[str, Set[int]] = defaultdict(set)

    symtab = elf.get_section_by_name(".symtab")
    if symtab is None:
        logger.error("No .symtab in input binary?")
        yield from ()

    va_symbols = va_symbol_map(symtab)

    asp_ctx = AspirinContext(
        binary,
        elf,
        dwarf,
        symtab,
        va_symbols,
        line_program,
        va_line_entries,
        va_line_func_map,
        func_epilogue_begin_map,
        func_prologue_end_map,
        vi_dicts,
        MachineInfo(elf_arch, addr_len, decoder_bitness),
        iced_x86.Formatter(iced_x86.FormatterSyntax.INTEL),
        iced_x86.InstructionInfoFactory(),
    )

    yield aspirin_module_record(asp_ctx)

    for global_name, dies in global_dies_map(dwarf).items():
        logger.debug(f"Found {len(dies)} DIEs for global_name={global_name}")
        for record in aspirin_global_records_for_name(asp_ctx, global_name, dies):
            if record is not None:
                yield record

    for stub_name, va in plt_va_map(elf).items():
        yield aspirin_plt_stub_record(asp_ctx, stub_name, va)

    migraine_addrs = elf.get_section_by_name(".migraine_addrs")
    if migraine_addrs is None:
        logger.error("No .migraine_addrs in input binary; missing migraine instrumentation?")
        yield from ()

    # TODO(ww): Refactor this terrible state machine into something more readable.
    last_bb_record: Optional[Dict[str, Any]] = None
    last_prologue_begin: Optional[int] = None
    last_epilogue_begin: Optional[int] = None
    for migraine_id, va in parse_migraine_addrs(migraine_addrs.data()):
        if migraine_id.startswith("migraine::func::"):
            last_func_record = aspirin_func_record(asp_ctx, va_dies, migraine_id, va)
        elif migraine_id.startswith("migraine::func_prologue_begin::"):
            if last_prologue_begin is not None:
                logger.error(f"State error: {last_prologue_begin=} should be None")

            if last_func_record is not None:
                last_prologue_begin = va
            else:
                logger.error(
                    f"No function record to pair prologue begin VA with (anchor={migraine_id}; "
                    "this probably indicates a failure in symbol pairing."
                )
        elif migraine_id.startswith("migraine::func_prologue_end::"):
            if last_prologue_begin is None:
                logger.error(
                    "No prologue begin VA to pair with this prologue end VA; "
                    "this probably indicates a critical bug in Wedlock or migraine."
                )
                continue

            if last_func_record is None:
                logger.error(
                    f"No function record to pair prologue end VA with (anchor={migraine_id}); "
                    "this probably indicates a critical bug in Wedlock or migraine."
                )

            last_func_record["function"]["prologues"].append((last_prologue_begin, va))  # type: ignore
            last_prologue_begin = None
        elif migraine_id.startswith("migraine::func_epilogue_begin::"):
            if last_epilogue_begin is not None:
                logger.error(f"State error: {last_epilogue_begin=} should be None")

            if last_func_record is not None:
                last_epilogue_begin = va
            else:
                logger.error(
                    f"No function record to pair epilogue begin VA with (anchor={migraine_id}; "
                    "this probably indicates a failure in symbol pairing."
                )
        elif migraine_id.startswith("migraine::func_epilogue_end::"):
            if last_epilogue_begin is None:
                logger.error(
                    "No epilogue begin VA to pair with this epilogue end VA; "
                    "this probably indicates a critical bug in Wedlock or migraine."
                )
                continue

            if last_func_record is None:
                logger.error(
                    f"No function record to pair epilogue end VA with (anchor={migraine_id}); "
                    "this probably indicates a critical bug in Wedlock or migraine."
                )
                continue

            last_func_record["function"]["epilogues"].append((last_epilogue_begin, va))
            last_epilogue_begin = None
        elif migraine_id.startswith("migraine::func_end::"):
            if last_func_record is None:
                logger.error(
                    f"No function record to emit at this func_end (anchor={migraine_id}); "
                    "this probably indicates a failure in symbol pairing."
                )
                continue
            yield last_func_record
            last_func_record = None
        elif migraine_id.startswith("migraine::bb::"):
            last_bb_record = aspirin_bb_record(asp_ctx, migraine_id, va)
        elif migraine_id.startswith("migraine::bb_end::"):
            if last_bb_record is None:
                logger.error(
                    "Retrieving BB record failed; not trying to find end "
                    f"VA for anchor={migraine_id}"
                )
                continue
            yield aspirin_bb_end_record(asp_ctx, last_bb_record, migraine_id, va)
            last_bb_record = None
        else:
            logger.debug(f"Skipping unknown migraine record kind: {migraine_id}")


def main() -> None:
    args = parser.parse_args()

    with args.headache_vi as vti:
        vi_dicts = [json.loads(jsonl) for jsonl in vti]

    for record in aspirin(args.binary, vi_dicts, line_program=not args.omit_line_program):
        print(json.dumps(record), file=args.output)


if __name__ == "__main__":
    main()
