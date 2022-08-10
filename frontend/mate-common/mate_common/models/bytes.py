from typing import NewType

Bytes = NewType("Bytes", int)
Kibibytes = NewType("Kibibytes", int)
Mebibytes = NewType("Mebibytes", int)
Gibibytes = NewType("Gibibytes", int)


def int_to_bytes(n: int) -> Bytes:
    assert n >= 0, f"Expected non-negative number of bytes, got {n}"
    return Bytes(n)


def bytes_to_kb(b: Bytes) -> Kibibytes:
    assert b >= 0, f"Expected non-negative number of bytes, got {b}"
    return Kibibytes(b // 1024)


def bytes_to_mb(b: Bytes) -> Mebibytes:
    assert b >= 0, f"Expected non-negative number of bytes, got {b}"
    return Mebibytes(bytes_to_kb(b) // 1024)


def bytes_to_gb(b: Bytes) -> Gibibytes:
    assert b >= 0, f"Expected non-negative number of bytes, got {b}"
    return Gibibytes(bytes_to_mb(b) // 1024)


def kb_to_bytes(kb: Kibibytes) -> Bytes:
    assert kb >= 0, f"Expected non-negative number of kibibytes, got {kb}"
    return Bytes(kb * 1024)


def mb_to_bytes(mb: Mebibytes) -> Bytes:
    assert mb >= 0, f"Expected non-negative number of mebibytes, got {mb}"
    return Bytes(mb * (1024**2))


def gb_to_bytes(gb: Gibibytes) -> Bytes:
    assert gb >= 0, f"Expected non-negative nugber of gibibytes, got {gb}"
    return Bytes(gb * (1024**3))


def gb_to_mb(gb: Gibibytes) -> Mebibytes:
    return bytes_to_mb(gb_to_bytes(gb))
