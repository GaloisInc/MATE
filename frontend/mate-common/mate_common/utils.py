"""Miscellaneous helpers for MATE."""

import builtins
import itertools
import tarfile
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any, AnyStr, Final, Iterable, Iterator, NoReturn

SPHINX_BUILD: Final[bool] = hasattr(builtins, "__sphinx_build__")


def unreachable(x: NoReturn) -> NoReturn:
    """A hint to the typechecker that a branch can never occur."""
    assert False, f"unreachable type: {type(x).__name__}"  # pragma: no cover


@contextmanager
def stateless_io(io: IO[AnyStr]) -> Iterator[IO[AnyStr]]:
    """A context manager for presenting a "stateless" view of some IO object.

    The object is reset to its starting position before and after the managed context, allowing
    operations within the context to consume the IO without producing side effects in other places
    that use it.
    """
    io.seek(0)
    try:
        yield io
    finally:
        io.seek(0)


@contextmanager
def tarball(src: Path) -> Iterator[Path]:
    """Create a temporary tarball (``.tar.gz``) for the given path and yield it."""
    try:
        # Create a temporary file and explicitly delete it by closing to free the name up.
        temp = tempfile.NamedTemporaryFile(suffix=".tar.gz")
        path = Path(temp.name)
        temp.close()

        with tarfile.open(path, mode="w:gz") as tar:
            # Set the arcname to the basename of the source path, to prevent
            # absolute paths from showing up in the tarball.
            tar.add(src, arcname=src.name)

        yield path
    finally:
        path.unlink()


# NOTE(ww): Based on https://stackoverflow.com/a/8998040
def grouper(n: int, iterable: Iterable[Any]) -> Iterator[Iterable[Any]]:
    """Group ``iterable`` into chunks of ``n``, truncating the last group if there aren't enough
    elements."""
    it = iter(iterable)
    while True:
        chunk_it = itertools.islice(it, n)
        try:
            first_el = next(chunk_it)
        except StopIteration:
            return
        yield itertools.chain((first_el,), chunk_it)
