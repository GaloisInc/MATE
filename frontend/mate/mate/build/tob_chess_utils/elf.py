"""A utility model containing functions and classes related to parsing and interpreting ELF
information."""

import struct
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from typing import BinaryIO, Dict, Iterator, List, Optional, Tuple

import cxxfilt
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection
from elftools.elf.sections import Symbol, SymbolTableSection

from .logging import make_logger

logger = make_logger(__name__)


@dataclass(frozen=True)
class VTable:
    """Represents a C++ class's virtual table.

    The fields in this dataclass should be kept up-to-date with the JSON Schema for the "VTable" CPG
    node.
    """

    va: int
    """
    The vtable's virtual address.
    """

    size: int
    """
    The vtable's size, in bytes. Includes non-member fields, like the RTTI and
    "offset to base" field.
    """

    symbol: str
    """
    The virtual table's symbol.
    """

    class_name: str
    """
    The name of the C++ class that this vtable is for.
    """

    rtti_va: Optional[int]
    """
    The virtual address to any RTTI information, if present.
    """

    members: List[int]
    """
    All of the members of this vtable, as virtual addresses.
    """


@contextmanager
def elf_inner_stream(elf: ELFFile) -> Iterator[BinaryIO]:
    """Yield the given ``ELFFile``'s inner stream, wrapped such that any reads or seeks against the
    stream are reset at the context manager's close."""
    pos = elf.stream.tell()
    try:
        yield elf.stream
    finally:
        elf.stream.seek(pos)


@lru_cache()
def elf_address_width(elf: ELFFile) -> Tuple[int, str]:
    """Returns an appropriate address/pointer width for this ``ELFFile``."""
    if elf.header.e_machine == "EM_386":
        return (4, "<L")
    elif elf.header.e_machine == "EM_X86_64":
        return (8, "<Q")
    else:
        logger.error(f"Barf: Unsupported machine type in ELF: {elf.header.e_machine}")
        return (8, "<Q")


@lru_cache()
def get_symbol_va_base(elf: ELFFile, symbol: Symbol) -> int:
    """Returns the base virtual address for a given symbol."""

    # NOTE(ww): We might need to special-case st_shndx == SHN_XINDEX at some point.
    section = elf.get_section(symbol["st_shndx"])
    if section is None:
        logger.error(f"Weird: Symbol {symbol.name} has no section?")
        # TODO(ww): Is this a reasonable default?
        section = elf.get_section_by_name(".text")

    seg_vas = {seg["p_vaddr"] for seg in elf.iter_segments() if seg.section_in_segment(section)}
    if len(seg_vas) != 1:
        logger.error(f"Weird: expected section in exactly one segment, got {len(seg_vas)}")

    return next(iter(seg_vas))


@lru_cache()
def get_va_text_base(elf: ELFFile) -> int:
    """Returns the base virtual address for the .text section."""

    # NOTE(ww): We don't bother checking whether this succeeds (i.e., is not None);
    # failing here indicates a hopelessly broken binary so we just allow an exception to happen.
    text = elf.get_section_by_name(".text")

    # NOTE(ww): It doesn't make any sense for .text to be in multiple segments,
    # this is just for consistency with the pyelftools API. Maybe remove it?
    segs = [seg for seg in elf.iter_segments() if seg.section_in_segment(text)]
    if len(segs) != 1:
        logger.error(f"Weird: expected .text in exactly one segment, got {len(segs)}")

    return segs[0]["p_vaddr"]


def get_global_va(elf: ELFFile, symbol: Symbol) -> int:
    """Returns the virtual address for the given (global variable) symbol, taking TLS into
    account."""

    if symbol["st_info"]["type"] == "STT_TLS":
        # NOTE(ww): On Linux, symbols for thread-local variables indicate their
        # segment-relative offsets in st_value. We turn these into "full" VAs
        # by getting each symbol's VA base and adding the offset.
        # N.B. that TLVs appear in two sections: .tbss for uninitialized TLVs,
        # and .tdata for pre-initialized TLVs.
        va_base = get_symbol_va_base(elf, symbol)
        return va_base + symbol["st_value"]
    else:
        return symbol["st_value"]


def va_symbol_map(symtab: SymbolTableSection) -> Dict[int, List[Symbol]]:
    """Returns a mapping of VAs to symbols for the given symbol table."""

    # NOTE(ww): Each VA can have multiple symbols in the symbol table,
    # for a few different reasons: __attribute__((alias)), LTO, or a custom
    # build step that adds additional symbols for program features.
    mapping: Dict[int, List[Symbol]] = defaultdict(list)
    for symbol in symtab.iter_symbols():
        # TODO(ww): Maybe special-case st_value == 0 here.
        # We probably don't care about these anyways (since they aren't valid VAs),
        # but knowing about them an intentionally excluding them would emphasize
        # our use case.
        mapping[symbol["st_value"]].append(symbol)
    return mapping


def all_vtables(elf: ELFFile) -> List[VTable]:
    """Returns a list of all virtual tables in the binary."""
    address_width, packspec = elf_address_width(elf)
    vtables = []

    def _get_vtable(sym: Symbol) -> Optional[VTable]:
        """Parse the vtable referenced by the given symbol."""

        vtable_va = sym.entry.st_value
        vtable_size = sym.entry.st_size

        # HACK(ww): the standard demangled representation for a vtable symbol
        # is "vtable for Foo". So, to get `Foo`, we just strip off that `vtable for `
        # prefix. This is terrible, but it's identical to what GDB does.
        try:
            demangled = cxxfilt.demangle(sym.name)
        except cxxfilt.InvalidName:
            logger.warning(f"couldn't demangle: {sym.name=}")
            print(f"couldn't demangle: {sym.name=}")
            return None
        assert demangled.startswith("vtable for ")
        demangled = demangled[len("vtable for ") :]

        # TODO(ww): This lookup is very slow. We should consider building an internal RangeAVL
        # to memoize it here.
        fileoff: List[int] = list(elf.address_offsets(vtable_va, vtable_size))
        if len(fileoff) != 1:
            logger.error(
                f"Weird: expected exactly one address match, got {len(fileoff)}: {vtable_va=} {vtable_size=}"
            )
            return None

        with elf_inner_stream(elf) as io:
            io.seek(fileoff[0])
            raw_vtable = BytesIO(io.read(vtable_size))
            vtable_off = 0

        # NOTE(ww): Skip the "address to top" field, for now.
        raw_vtable.read(address_width)
        vtable_off += address_width

        (rtti_va,) = struct.unpack(packspec, raw_vtable.read(address_width))
        vtable_off += address_width

        vas = []
        while vtable_off < raw_vtable.getbuffer().nbytes:
            (func_va,) = struct.unpack(packspec, raw_vtable.read(address_width))
            vtable_off += address_width
            vas.append(func_va)

        # Make it explicit that a zero VA for RTTI means that none is present.
        if rtti_va == 0:
            rtti_va = None

        return VTable(
            va=vtable_va,
            size=vtable_size,
            symbol=sym.name,
            class_name=demangled,
            rtti_va=rtti_va,
            members=vas,
        )

    def _visit_symtab(symtab: SymbolTableSection):
        """Visit the given symbol table's symbols, building up the closure's ``mapping`` with vtable
        information."""
        for symbol in symtab.iter_symbols():
            # Skip non-vtable entries.
            if not symbol.name.startswith("_ZTV"):
                continue

            # Sanity check: vtable entries should be of "STT_OBJECT".
            if symbol.entry.st_info.type != "STT_OBJECT":
                logger.warning(
                    f"Weird: symbol looks like a vtable, but isn't STT_OBJECT: {symbol=}"
                )
                continue

            vtable = _get_vtable(symbol)
            if vtable is not None:
                vtables.append(vtable)

    symtab = elf.get_section_by_name(".symtab")
    if symtab is not None:
        _visit_symtab(symtab)

    # TODO(ww): Visit .dynsym as well? It should be a strict subset of symtab,
    # so it *shouldn't* be necessary to do so.

    return vtables


def plt_va_map(elf: ELFFile) -> Dict[str, int]:
    """Unfurl the PLT relocation table in the given ELF file, returning a mapping of symbol names to
    VAs for each function that goes through the PLT."""

    # TODO(ww): This functionality should be unified with `parse_dyn_sym_table` below.

    rela_plt = elf.get_section_by_name(".rela.plt")
    plt = elf.get_section_by_name(".plt")

    # If we don't have a PLT or relocations for our PLT, then we have nothing to do.
    if rela_plt is None or plt is None:
        return {}

    plt_base = plt["sh_addr"]
    plt_entsize = plt["sh_entsize"]
    mapping = {}

    # This should always be be `.dynsym`, but we retrieve it by reference just in case it's
    # something unusual we haven't thought of.
    symtab = elf.get_section(rela_plt["sh_link"])

    for sym_num, rel in enumerate(rela_plt.iter_relocations(), 1):
        # TODO(ww): Remove this? We shouldn't ever see a relocation for the 0th symbol in
        # a symbol table, since it's always a NULL entry. Probably overly conservative.
        if rel["r_info_sym"] == 0:
            continue

        symbol = symtab.get_symbol(rel["r_info_sym"])

        va = plt_base + (plt_entsize * sym_num)
        mapping[symbol.name] = va

    return mapping


def parse_dyn_sym_table(elf: ELFFile) -> Dict[int, str]:
    """Parse the dynamic symbol table from the ELF File and return a mapping of VA to symbol."""

    # TODO(ek): Look at elf.iter_segments for DynamicSegment.iter_symbols()
    # iterate over sections and identify symbol table section
    mapping = {}
    for section in list(elf.iter_sections()):
        if not (isinstance(section, SymbolTableSection) or isinstance(section, RelocationSection)):
            continue

        # get list of symbols by name
        if isinstance(section, SymbolTableSection):
            for symbol in list(section.iter_symbols()):
                if symbol.entry.st_info.type == "STT_FUNC" and symbol.entry.st_value != 0:
                    mapping[symbol.entry.st_value] = symbol.name
        elif isinstance(section, RelocationSection):
            symtable = elf.get_section(section["sh_link"])
            got_plt_offset = elf.get_section(section["sh_info"])["sh_addr"]
            plt_offset = elf.get_section_by_name(".plt")
            if plt_offset:
                plt_offset = plt_offset["sh_addr"]
            else:
                continue
            plt_entsize = elf.get_section_by_name(".plt").header["sh_entsize"]
            # symbol number for PLT. We skip the 0th offset because that is
            # the jump table start, and it is also the same size as all other
            # entries
            sym_num = 0
            for rel in list(section.iter_relocations()):
                sym_num += 1
                if rel["r_info_sym"] == 0:
                    continue
                symbol = symtable.get_symbol(rel["r_info_sym"])
                if symbol["st_name"] == 0:
                    symsec = elf.get_section(symbol["st_shndx"])
                    symbol_name = symsec.name
                else:
                    symbol_name = symbol.name
                    # Could get LIBC version string if wanted...
                    # version = _symbol_version(rel['r_info_sym'])
                    # version = (version['name']
                    # if version and version['name'] else '')
                offset = rel["r_offset"]
                if got_plt_offset != 0:
                    offset = plt_offset + plt_entsize * sym_num
                mapping[offset] = symbol_name
                # logger.debug(f"0x{offset:x} - {symbol_name}")

    return mapping
