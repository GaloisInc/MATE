"""Functionality common to various parts of the MATE build pipeline."""

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Final, Literal, NewType, Optional, Sequence, Union

import docker

from mate.config import LLVM_WEDLOCK_BIN, MATE_BDIST_ROOT, MATE_SCRATCH, REASONABLE_DEFAULT_PATH
from mate.logging import logger
from mate_common.assertions import mate_assert

# NOTE: The valid of MATE_COMPATIBLE_BASE_IMAGE must be kept in sync
# with the value of `ARG BASE=...` in the top-level MATE Dockerfile.
MATE_COMPATIBLE_BASE_IMAGE: Final[str] = "ubuntu:20.04"


Environment = NewType("Environment", Dict[str, str])

DockerContainerId = NewType("DockerContainerId", str)
DockerComposeProject = NewType("DockerComposeProject", str)

_HEXSTRING = re.compile(r"^[0-9a-fA-F]+$")


def _llvm_wedlock_path(path: Optional[str] = None) -> str:
    if path is None:
        path = os.environ["PATH"]
    return f"{LLVM_WEDLOCK_BIN}{os.pathsep}{path}"


def llvm_wedlock_environment() -> Environment:
    """Returns a mapping suitable for loading into the environment of any process that needs to
    interact with LLVM tools or, more specifically, the Wedlock builds of LLVM tools."""
    return Environment({"PATH": _llvm_wedlock_path()})


def mate_environment(llvm_wedlock: bool = False) -> Environment:
    """Returns a mapping suitable for loading into the environment of any **container** that needs
    to invoke MATE functionality and/or any tools included with the MATE bdist.

    ``llvm_wedlock`` indicates whether to include the Wedlock LLVM toolchain in the ``PATH``.

    This function **assumes** that the targeted container has the MATE bdist mounted
    into it at the same root as ``MATE_BDIST_ROOT``.
    """

    if llvm_wedlock:
        base_path = _llvm_wedlock_path(REASONABLE_DEFAULT_PATH)
    else:
        base_path = REASONABLE_DEFAULT_PATH

    return Environment(
        {
            "PATH": f"{MATE_BDIST_ROOT}/local/bin:{MATE_BDIST_ROOT}/bin:{base_path}",
            "LD_LIBRARY_PATH": f"{MATE_BDIST_ROOT}/lib",
            "PYTHONPATH": f"{MATE_BDIST_ROOT}/local/lib/python3.8/site-packages:{MATE_BDIST_ROOT}/lib/python3.8/site-packages",
        }
    )


def _gllvm_store() -> Path:
    """Return a suitable ephemeral directory for GLLVM's bitcode store.

    When ``MATE_SCRATCH`` exists, the ephemeral directory is created underneath it (so that
    containerized compilation processes can access bitcode intermediates). When it doesn't exist,
    the default temporary directory is used as a base instead.
    """
    if MATE_SCRATCH.is_dir():
        return Path(tempfile.mkdtemp(dir=MATE_SCRATCH))
    else:
        return Path(tempfile.mkdtemp())


def gllvm_environment(level: Literal["ERROR", "WARNING", "INFO", "DEBUG"] = "DEBUG") -> Environment:
    """Returns a mapping suitable for loading into the environment of any process that needs to
    interactive with GLLVM CLI tools (``gclang``, ``get-bc``, etc.)."""

    # NOTE(ww): Not a typo: GLLVM uses WLLVM's environment variables here.
    return Environment(
        {
            "WLLVM_OUTPUT_LEVEL": level,
            "WLLVM_BC_STORE": str(_gllvm_store()),
        }
    )


def docker_container_id() -> Optional[DockerContainerId]:
    """If possible, get the Docker container ID we are currently executing within.

    This function uses two techniques to attempt to discover the container ID:

    1. First, we check whether ``HOSTNAME`` environment variable looks like a container ID.
       If it does, we use it and finish our search.

    2. If the ``HOSTNAME`` looks wrong, we search ``/proc/self/cpuset`` for
       a pseudo-path that looks like a container ID. This is our fallback technique,
       since neither Linux nor Docker guarantees the stability of this pseudo-file's
       contents.
    """
    maybe_container_id = os.getenv("HOSTNAME")
    if maybe_container_id is not None and _HEXSTRING.match(maybe_container_id):
        return DockerContainerId(maybe_container_id)

    docker_container_id_path = Path("/proc/self/cpuset")
    if not docker_container_id_path.exists():
        logger.error(f"unable to detect container ID: no path: {docker_container_id_path=}")
        return None

    # Should have the following form if within Docker:
    #   root@03f40e087860:~# cat /proc/self/cpuset
    #   /docker/03f40e08786018308f8d83f499e109ffbeca4a92f12b2b8c8aaac40ef114c8a3
    # Otherwise:
    #   $ cat /proc/self/cpuset
    #   /
    with docker_container_id_path.open("r") as f:
        out = f.readline().strip()
    if "docker" not in out:
        logger.error(f"environment doesn't look like docker based on cpuset contents: {out=}")
        return None

    container_id = Path(out).stem
    if not _HEXSTRING.match(container_id):
        logger.error(f"tried to infer container ID but it looks wrong: {container_id=}")
        return None

    logger.debug(f"Found container_id: '{container_id}'")
    return DockerContainerId(container_id)


def docker_compose_project(client: docker.DockerClient) -> Optional[DockerComposeProject]:
    """If possible, attempt to get the name for the Docker Compose project we're executing
    within."""

    container_id = docker_container_id()
    if container_id is None:
        logger.error("no container ID found; not searching for compose project")
        return None

    # To pivot to the overall Compose project, we need to inspect our current container
    # and pull the value of the "com.docker.compose.project" label from the container's
    # attributes.
    try:
        container = client.containers.get(str(container_id))
    except Exception as e:
        logger.error(f"container lookup failed: {container_id=} {e=}")
        return None

    return container.attrs["Config"]["Labels"].get("com.docker.compose.project")


def docker_volume_by_label(
    client: docker.DockerClient, label: str
) -> Optional[docker.models.volumes.Volume]:
    """Given an active Docker client, locate exactly one Docker volume with the given metadata
    label.

    Asserts if more than one volume is found, and returns ``None`` if none are found.
    """
    labels = [label]

    compose_project = docker_compose_project(client)
    if compose_project is not None:
        labels.append(f"com.docker.compose.project={str(compose_project)}")
    else:
        logger.warning("couldn't infer compose project; trying without and praying")

    matched_volumes = client.volumes.list(filters={"label": labels})

    mate_assert(
        len(matched_volumes) == 1,
        f"more than one volume matches label: {label=} {matched_volumes=!r}",
    )

    return next(iter(matched_volumes), None)


def docker_bind(dir_: Path, *, mode: str = "rw") -> Dict[str, str]:
    """Return a Docker SDK-style dictionary for binding a volume to the given directory."""
    return {"bind": str(dir_), "mode": mode}


def docker_image(client: docker.DockerClient, name: str) -> docker.models.images.Image:
    """Return an image handle for the given Docker image name, pulling it if necessary.

    Raises various Docker client errors on failure.
    """
    try:
        image = client.images.get(name)
        return image
    except docker.errors.DockerException:
        # Unconditionally attempt to pull the image down.
        return client.images.pull(name)


def run(args: Sequence[Union[str, os.PathLike]], **kwargs: Any) -> subprocess.CompletedProcess:
    """A very thin wrapper for ``subprocess.run`` that logs the invocation before execution."""

    logger.debug(f"running {args=}")

    return subprocess.run(args, **kwargs)


def format_run_log(result: subprocess.CompletedProcess) -> str:
    """Given a ``subprocess.CompletedProcess``, return a pretty-ish printed representation of the
    process's standard output, error, and exit code."""

    # NOTE(ww): stdout and stderr can be either strings or bytes (or None), depending
    # on the arguments that the originating `subprocess.run` was invoked with.
    # We want to pretty-print even when the contents are bytes, so we perform
    # a lossy conversion here for both streams.
    if isinstance(result.stdout, bytes):
        stdout = result.stdout.decode("utf-8", errors="replace")
        stderr = result.stderr.decode("utf-8", errors="replace")
    else:
        stdout = result.stdout
        stderr = result.stderr

    return f"""
=======================
EXITED WITH: {result.returncode}
=======================

=======================
STDOUT:
{stdout}
=======================

=======================
STDERR:
{stderr}
=======================
"""
