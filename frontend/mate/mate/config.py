"""This module provides filepaths and other configurations used by the server."""

from pathlib import Path
from typing import Final

from mate_common.config import get_config

MATE_SERVER_CONCURRENCY: Final[int] = get_config("MATE_SERVER_CONCURRENCY", int, 1)

MATE_BDIST_ROOT: Final[Path] = get_config("MATE_BDIST_ROOT", Path, Path("/opt/mate"))
"""
The root directory for nearly all MATE runtime components.
"""

MATE_BDIST_LIBEXEC_PATH: Final[Path] = MATE_BDIST_ROOT / "libexec"
"""
The directory for any "library executables" distributed with MATE.
"""

MATE_BDIST_LIB_PATH: Final[Path] = MATE_BDIST_ROOT / "local/lib"
"""
The directory for any shared objects distributed with MATE.
"""

MATE_BDIST_DEFAULT_SIGNATURES: Final[Path] = MATE_BDIST_ROOT / "local/share/default-signatures.yml"
"""
The path to MATE's default dataflow and points-to signatures.
"""

LLVM_WEDLOCK_BIN: Final[Path] = get_config(
    "LLVM_WEDLOCK_BIN", Path, MATE_BDIST_ROOT / "llvm-wedlock/bin"
)
"""
The directory containing MATE's copies of the LLVM and Clang CLIs.
"""

CLANG: Final[Path] = LLVM_WEDLOCK_BIN / "clang"
"""
The ``clang`` C frontend bundled with MATE.
"""

CLANGXX: Final[Path] = LLVM_WEDLOCK_BIN / "clang++"
"""
The ``clang++`` C++ frontend bundled with MATE.
"""

LLVM_OPT: Final[Path] = LLVM_WEDLOCK_BIN / "opt"
"""
The ``opt`` optimizer bundled with MATE.
"""

LLVM_LLC: Final[Path] = LLVM_WEDLOCK_BIN / "llc"
"""
The ``llc`` IR to assembly compiler bundled with MATE.
"""

LLVM_LINK: Final[Path] = LLVM_WEDLOCK_BIN / "llvm-link"
"""
The ``llvm-link`` IR linker bundled with MATE.
"""

LLVM_ADDR2LINE: Final[Path] = LLVM_WEDLOCK_BIN / "llvm-addr2line"
"""
The LLVM implementation of ``addr2line`` bundled with MATE.
"""

LLVM_OBJCOPY: Final[Path] = LLVM_WEDLOCK_BIN / "llvm-objcopy"
"""
The LLVM implementation of ``objcopy`` bundled with MATE.
"""

DOCKER_SOCKET: Final[Path] = Path("/var/run/docker.sock")
"""
The path to an active Docker socket, if MATE is running with containerization
support.
"""

MATE_SCRATCH: Final[Path] = Path("/opt/mate-scratch")
"""
The path to a suitable "scratch" directory for temporary files.
"""

# NOTE(ww): These aren't really paths, but they identify Docker volumes
# that are eventually used for I/O. Not sure where else to put them.
# NOTE(ww): These **must** be kept up-to-date with the volume labels
# in our MATE-only docker-compose, as well as the CHESS deployment.
MATE_BDIST_DOCKER_VOLUME: Final[str] = "com.galois.mate.bdist-volume"
MATE_SCRATCH_DOCKER_VOLUME: Final[str] = "com.galois.mate.scratch-volume"

REASONABLE_DEFAULT_PATH: Final[str] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
"""
A reasonable default ``$PATH`` when running containerized compilations.
"""

MATE_PYTHON_ROOT: Final[Path] = MATE_BDIST_LIB_PATH / "python3.8/site-packages/mate/"


MANTISERVE_ROOT: Final[Path] = MATE_BDIST_LIB_PATH / Path("python3.8/site-packages/mantiserve")
REACHABILITY_RUNNER: Final[Path] = MANTISERVE_ROOT / Path("tasks/reachability.py")
EXPLORE_RUNNER: Final[Path] = MANTISERVE_ROOT / Path("tasks/explore.py")

CHALLENGE_BROKER_BASE: Final[str] = get_config(
    "CHALLENGE_BROKER_BASE", str, "http://challenge-broker:5001"
)
