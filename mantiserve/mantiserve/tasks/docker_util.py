"""This module provides docker utility facilities.

NOTE: This is located separately because Docker tries to load libssl that may
not be present within a specific Docker image/container itself.
"""
from typing import List, Optional

import docker
from docker.models.containers import Container

from mantiserve.exceptions import MantiserveError
from mantiserve.logging import logger
from mate.build.common import (
    docker_bind,
    docker_container_id,
    docker_volume_by_label,
    mate_environment,
)
from mate.config import (
    DOCKER_SOCKET,
    MATE_BDIST_DOCKER_VOLUME,
    MATE_BDIST_ROOT,
    MATE_SCRATCH,
    MATE_SCRATCH_DOCKER_VOLUME,
)
from mate_common.models.bytes import Mebibytes, mb_to_bytes


def run_task_in_docker(
    image_name: str,
    container_name: str,
    command: List[str],
    working_dir: str,
    memory_limit: Optional[Mebibytes] = None,
) -> bytes:
    """Run a command in a Docker container set up for Mantiserve tasks.

    :param image_name: The image name to use for a container
    :param container_name: The container name to run
    :param command: The command to run within the container
    :param working_dir: The working directory within the container
    :param memory_limit: An optional memory cap to apply to the container
    :return: Docker logs
    """
    if not DOCKER_SOCKET.is_socket():
        raise MantiserveError("Mantiserve requires a Docker socket to run")

    client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET}")
    logger.debug(f"Trying to pull Docker image {image_name}")
    # Test if the image exists or can be pulled
    try:
        image = client.images.get(image_name)
    except docker.errors.ImageNotFound:
        try:
            image = client.images.pull(image_name)
        except docker.errors.APIError as e:
            raise MantiserveError(f"Unable to pull Docker image. Failed with {str(e)}")

    mate_bdist_volume = docker_volume_by_label(client, MATE_BDIST_DOCKER_VOLUME)
    if mate_bdist_volume is None:
        raise MantiserveError(
            f"Failed to locate a bdist volume for container use: {MATE_BDIST_DOCKER_VOLUME}",
        )
    mantiserve_scratch_volume = docker_volume_by_label(client, MATE_SCRATCH_DOCKER_VOLUME)
    if mate_bdist_volume is None:
        raise MantiserveError(
            f"Failed to locate a mantiserve scratch volume for container use: {MATE_SCRATCH_DOCKER_VOLUME}",
        )

    # Get the container ID we're running in for more portable networking
    container_id = docker_container_id()
    extra_container_opts = {}
    if container_id is not None:
        extra_container_opts.update({"network": f"container:{str(container_id)}"})
    else:
        extra_container_opts.update({"network": "host"})
        logger.warning("Using 'host' network for running Manticore")

    if memory_limit is not None:
        extra_container_opts["mem_limit"] = mb_to_bytes(memory_limit)

    logger.debug(f"Running Mantiserve task in container {container_name}")
    container = client.containers.run(
        image,
        name=container_name,
        auto_remove=False,
        volumes={
            mate_bdist_volume.name: docker_bind(MATE_BDIST_ROOT, mode="ro"),
            mantiserve_scratch_volume.name: docker_bind(MATE_SCRATCH),
        },
        environment=mate_environment(),
        working_dir=working_dir,
        detach=True,
        user=0,
        command=command,
        **extra_container_opts,
    )

    logger.debug(f"Waiting for Mantiserve task container '{container_name}' to finish")

    # NOTE(ek): Docker's REST endpoint for waiting on a container can fail with
    # a 404 if the container completely explodes on startup, e.g. if the exec*()
    # syscall itself fails due to an irrecoverable dynamic linker error.
    docker_logs = b""
    try:
        docker_logs = b"".join(line for line in container.logs(stream=True))
        resp = container.wait()
    except Exception as e:
        msg = (
            f"container wait failed for '{container_name}'; this is a STRONG "
            f"indicator that the given image ({image_name}) is ABI-incompatible "
            "with MATE, PROBABLY because it uses an older Ubuntu base image. "
            f"Errored with {e}"
        )
        if isinstance(container, Container):
            msg = f"Stopping container manually. {e}"
            container.stop(timeout=1)
            docker_logs = container.logs()
        container.remove(force=True)
        raise MantiserveError(
            msg,
            logs=docker_logs,
        )

    container.remove(force=True)
    if resp and resp["StatusCode"] != 0:
        raise MantiserveError(f"Container '{container_name}' failed", logs=docker_logs)
    logger.debug(f"Mantiserve task container '{container_name}' exited successfully")

    return docker_logs
