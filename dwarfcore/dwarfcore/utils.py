import os
from typing import Optional, Tuple

from manticore.native.memory import AnonMap, Memory, MemoryException


def addr_to_map_and_offset(addr: int, mem: Memory) -> Optional[Tuple[str, int]]:
    """Translates a virtual address into a tuple (mapping, offset)

    :param addr: the virtual address to translate
    :param mem: the current manticore memory object
    :return: the (mapping, offset) tuple or None if the address doesn't
    correspond to a mapping
    """

    try:
        m = mem.map_containing(addr)
    except MemoryException:
        return None

    if isinstance(m, AnonMap):
        return ("map_anonymous", addr - m.start)

    # Iterate through sorted mappings. Manticore returns mappings as
    # tuples (start, end, perms, file_offset, name)
    for start, end, _, _, name in mem.mappings():
        if name == m._filename or (start <= addr and end >= addr):
            return (
                os.path.basename(name),
                addr - start,
            )

    return None


def pp_map_and_offset(pos: Optional[Tuple[str, int]]) -> Optional[str]:
    """Pretty print a map name and offset into the map."""
    if pos is None:
        return None

    return f"{pos[0]} @ 0x{pos[1]:x}"
