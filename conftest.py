import contextlib
import fcntl
import subprocess
from itertools import chain, product
from os import getenv
from os.path import dirname, join, realpath
from pathlib import Path
from typing import Final, List, Tuple

import pytest

MATE_OUT: str = join(dirname(realpath(__file__)), ".out")
OUT: str = join(MATE_OUT, "build", "tests")
PROGRAMS_PATH: Path = Path(__file__).resolve().parent / "frontend" / "test" / "programs"


@pytest.fixture
def make_tarball(tmp_path):
    def _make_tarball(dir_: Path):
        assert dir_.is_dir(), f"not a directory: {dir_=}"

        archive = (tmp_path / dir_.name).with_suffix(".tar.gz")

        # NOTE(ww): We could use shutil.make_archive here, but is has an incredibly
        # misuse-prone API. `tar` should always be available and is much more
        # readable here.
        subprocess.run(["tar", "czf", archive, dir_.name], cwd=dir_.parent, check=True)

        assert archive.is_file()

        return archive

    return _make_tarball


@pytest.fixture(scope="session")
def programs_path():
    """Return an absolute path to the directory that our single-file test programs reside under.

    This is primarily useful in unit tests that don't need to invoke the entirety of MATE for their
    functionality, such as the PA tests.
    """
    return PROGRAMS_PATH


@pytest.fixture(scope="session")
def test_dir():
    return Path(OUT)


@pytest.fixture(scope="session")
def exclusive_lock(tmp_path_factory):
    """Returns a context manager for exclusive cross-process locks."""

    @contextlib.contextmanager
    def _exclusive_lock(name: str):
        root_tmp_dir = tmp_path_factory.getbasetemp().parent
        lockfile = root_tmp_dir / f"{name}.lock"
        exists = lockfile.exists()

        with lockfile.open("a") as io:
            try:
                fcntl.flock(io, fcntl.LOCK_EX)
                yield exists
            finally:
                fcntl.flock(io, fcntl.LOCK_UN)

    return _exclusive_lock


ProgramAndFlags = Tuple[str, Tuple[str, ...]]

# HACK(ww): Don't run these programs in the `every_program` fixture.
# In general, the reason for this is that they don't compile with the default flags.
EVERY_PROGRAM_DENYLIST: Final[List[str]] = [
    "exception-driven-control-flow.cpp",
    "heap_oob.cpp",
]

CFLAGS: Final[List[Tuple[str]]] = [("-O0",)]  # TODO(881): Also test at -O1, -O2, and -O3
CPROGS: Final[List[str]] = [
    p.name for p in PROGRAMS_PATH.glob("*.c") if p.name not in EVERY_PROGRAM_DENYLIST
]
CXXPROGS: Final[List[str]] = [
    p.name for p in PROGRAMS_PATH.glob("*.cpp") if p.name not in EVERY_PROGRAM_DENYLIST
]
CPARAMS: Final[List[ProgramAndFlags]] = list(product(CPROGS, CFLAGS))
CXXPARAMS: Final[List[ProgramAndFlags]] = list(product(CXXPROGS, CFLAGS))

EVERY_PROGRAM: Final[List[ProgramAndFlags]] = list(chain(CPARAMS, CXXPARAMS))
SOME_PROGRAMS: Final[List[ProgramAndFlags]] = list(
    product(
        (
            "allocation-sizes.c",
            "cxxbasic.cpp",
            "functiontable.c",
            "notes.c",
            "points-to_context.c",
            "recurse.c",
            "virtual.cpp",
        ),
        CFLAGS,
    )
)

ONE_PROGRAM: Final[List[ProgramAndFlags]] = [SOME_PROGRAMS[0]]

EVERY_PROGRAM_FIXTURE_NAME: Final[str] = "every_program"
SOME_PROGRAMS_FIXTURE_NAME: Final[str] = "some_programs"


def pytest_generate_tests(metafunc):
    extra_tests = getenv("MATE_INTEGRATION_TESTS") == "1"
    if EVERY_PROGRAM_FIXTURE_NAME in metafunc.fixturenames:
        if extra_tests:
            metafunc.parametrize(EVERY_PROGRAM_FIXTURE_NAME, EVERY_PROGRAM)
        else:
            metafunc.parametrize(EVERY_PROGRAM_FIXTURE_NAME, ONE_PROGRAM)
    if SOME_PROGRAMS_FIXTURE_NAME in metafunc.fixturenames:
        if extra_tests:
            metafunc.parametrize(SOME_PROGRAMS_FIXTURE_NAME, SOME_PROGRAMS)
        else:
            metafunc.parametrize(SOME_PROGRAMS_FIXTURE_NAME, ONE_PROGRAM)
    if "optimization_flags" in metafunc.fixturenames:
        if extra_tests:
            metafunc.parametrize("optimization_flags", (("-O0",), ("-O1",), ("-O2",), ("-O3",)))
        else:
            metafunc.parametrize("optimization_flags", (("-O0",), ("-O2",)))
