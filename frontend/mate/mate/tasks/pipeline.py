"""These tasks are intended to be called by the bridge, in response to a challenge-broker
message."""

import time
import urllib.parse as urlparse
from typing import List

import requests

from mate.logging import logger
from mate.tasks import _Task, executor
from mate_common.models.builds import BuildInformation, BuildOptions, BuildState
from mate_common.models.compilations import (
    CompilationInformation,
    CompilationState,
    CompileOptions,
    TargetKind,
    TargetSpecification,
)


@executor.task(bind=True)
def run_end_to_end(_self: _Task, base_url: str, target_id: str) -> None:
    # Create a compilation task for this challenge.
    logger.info(f"Attempting to compile {target_id}")
    endpoint = urlparse.urljoin(base_url, "compilations")
    target = TargetSpecification(
        kind=TargetKind.BrokeredChallengeTargetID,
        handle=target_id,
        options=CompileOptions(containerized=True, testbed=False),
    )
    response = requests.post(
        endpoint,
        data=target.json(),
    )

    retries = 10
    while not response.ok and retries > 0:
        logger.warning(
            f"Compilation creation endpoint returned {response.status_code} {response.text=}, "
            f"{retries} remaining"
        )
        time.sleep(2)
        response = requests.post(endpoint, data=target.json())
        retries -= 1

    if not response.ok:
        logger.error("Failed to start compilation; retries exhausted")
        return

    # Wait for the created compilation task to enter a terminal state.
    compilation = CompilationInformation(**response.json())
    logger.info(f"Created {compilation=}; polling for completion")
    endpoint = urlparse.urljoin(base_url, f"compilations/{compilation.compilation_id}")

    while not compilation.state.is_terminal():
        logger.info("Checking the compilation status")
        response = requests.get(endpoint)
        if not response.ok:
            logger.error(f"Failed to check compile status: {response=}")
            return

        compilation = CompilationInformation(**response.json())
        time.sleep(5)

    if compilation.state != CompilationState.Compiled:
        logger.error(f"Failed to compile: {compilation.state=}")
        return

    # Start one or more builds with our successful compilation.
    endpoint = urlparse.urljoin(base_url, f"builds/{compilation.compilation_id}/build")
    build_options = BuildOptions()
    response = requests.post(endpoint, data=build_options.json())

    if not response.ok:
        logger.error(f"Failed to create builds for {compilation=}")
        return

    # Track each pending build for state changes; trigger all POIs
    # for each build as soon as they become ready.
    builds: List[str] = response.json()
    logger.info(f"Created {builds=}; polling for completion")

    pending_builds = set(builds)
    # NOTE(ww): Pydantic models aren't hashable, hence a list instead of a set here.
    completed_builds: List[BuildInformation] = []
    while len(pending_builds) != 0:
        logger.debug(f"Waiting on {len(pending_builds)} builds...")

        for build_id in pending_builds:
            logger.debug(f"Checking {build_id} for completion")

            endpoint = urlparse.urljoin(base_url, f"builds/{build_id}")
            response = requests.get(endpoint)

            # A failure here indicates something badly awry on the server side,
            # so don't bother continuing.
            if not response.ok:
                logger.error(f"failed to check build ({build_id}) status: {response=}")
                return

            build = BuildInformation(**response.json())
            if build.state.is_terminal():
                completed_builds.append(build)
            if build.state == BuildState.Built:
                # Kick POIs off immediately, instead of waiting for all
                # other builds to become terminal.
                logger.info(f"Kicking off all POIs for {build.build_id}")
                endpoint = urlparse.urljoin(base_url, f"analyses/run/{build.build_id}")
                response = requests.post(endpoint)

                # TODO(ww): Maybe don't return here?
                if not response.ok:
                    logger.error(f"failed to start POIs: {response=}")
                    return

        # Check our completed set, and prune our pending set.
        # We do this outside of the previous loop to avoid invalidating our iterator.
        for completed_build in completed_builds:
            pending_builds.discard(completed_build.build_id)
        time.sleep(5)

    # Do one final pass over each completed build, logging the ones that failed.
    for build in completed_builds:
        if build.state != BuildState.Built:
            logger.error(f"build {build.build_id} failed")
