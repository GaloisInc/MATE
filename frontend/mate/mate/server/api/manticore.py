import logging
import time
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException
from pydantic.json import pydantic_encoder
from sqlalchemy import orm

from mantiserve.mantireach import validate_reachability_msg
from mantiserve.tasks.explore import run_exploration
from mantiserve.tasks.reachability import run_reachability
from mate.server.api.common import has_build, has_db, has_mantiserve_task
from mate.tasks import executor
from mate_common.models.artifacts import ArtifactInformation, ArtifactKind
from mate_common.models.manticore import (
    ExploreFunctionOptions,
    ExploreOptions,
    MantiserveTaskInformation,
    MantiserveTaskKind,
    MantiserveTaskState,
    ReachabilityOptions,
)
from mate_query import db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/manticore/tasks", response_model=Union[List[str], List[MantiserveTaskInformation]])
def _get_manticore_tasks(
    session: orm.Session = Depends(has_db),
    state: Optional[MantiserveTaskState] = None,
    detail: bool = False,
) -> Union[List[str], List[MantiserveTaskInformation]]:
    """Lists all Mantiserve tasks currently known to MATE.

    `state` allows the list of tasks to be filtered on status, e.g. `completed`
    to list only tasks that have fully run to completion.

    `detail` controls the level of detail in the response. When enabled, each list
    element is a full model of the underlying task.
    """
    query = session.query(db.MantiserveTask)
    if state is not None:
        query = query.filter_by(state=state)

    tasks = query.all()

    if detail:
        return [t.to_info() for t in tasks]
    else:
        return [t.uuid for t in tasks]


@router.get("/manticore/tasks/{task_id}", response_model=MantiserveTaskInformation)
def _get_manticore_task(
    task: db.MantiserveTask = Depends(has_mantiserve_task()),
) -> MantiserveTaskInformation:
    """Get information about the requested Mantiserve task, by ID."""
    return task.to_info()


@router.patch("/manticore/tasks/{task_id}/stop", response_model=MantiserveTaskInformation)
def _stop_manticore_task(
    task: db.MantiserveTask = Depends(has_mantiserve_task(state=MantiserveTaskState.Running)),
    session: orm.Session = Depends(has_db),
) -> MantiserveTaskInformation:
    """Stop a specific Mantiserve task. Note that a task may take up to a minute (often much less)
    to completely stop.

    Task information about the task stopped. This may not indicate the task
    state has stopped, but the task will stop within a minute (usually less).

    If the task has already been stopped, a message will be displayed saying as
    much.
    """

    # Raises an exception in the task https://stackoverflow.com/a/29627549
    executor.control.revoke(task.job_id, terminate=True, signal="SIGUSR1")

    # TODO(ww): This feels like a hack.
    # Sleep to let it update
    time.sleep(1)
    session.refresh(task)
    return task.to_info()


def _do_mantiserve_exploration_task(
    kind: MantiserveTaskKind,
    session: orm.Session,
    build: db.Build,
    opts: Union[ExploreOptions, ExploreFunctionOptions],
) -> MantiserveTaskInformation:
    """Create and run an exploration or underconstrained exploration task."""
    docker_image = opts.docker_image
    if docker_image is None:
        docker_image = build.bitcode_artifact.attributes.get("image")

    task = db.MantiserveTask.create(
        build,
        kind,
        request_msg=pydantic_encoder(opts.explore_msg),
        docker_image=docker_image,
    )
    session.add(task)
    session.commit()

    try:
        run_exploration.delay(
            explore_msg=opts.explore_msg,
            explore_task_id=task.uuid,
            build_id=build.uuid,
            docker_image=docker_image,
            memory_limit=opts.docker_memory_limit_mb,
        )
    except run_exploration.OperationalError as exc:
        err_msg = f"Encountered an error when trying start: {exc}"
        task.transition_to_state(MantiserveTaskState.Failed, err_msg)
        session.add(task)
        session.commit()
        raise HTTPException(status_code=500, detail=f"{task.uuid=}: {err_msg}")

    return task


@router.post("/manticore/explore/{build_id}", response_model=MantiserveTaskInformation)
def _execute_manticore_exploration_task(
    opts: ExploreOptions,
    build: db.Build = Depends(has_build(state=db.BuildState.Built)),
    session: orm.Session = Depends(has_db),
) -> MantiserveTaskInformation:
    """Run a Mantiserve exploration task on a build with a specific Detector.

    See the associated Mantiserve docs.
    """
    logger.debug(f"Received explore message for build: {build.uuid}")

    # Start Manticore exploration.
    task = _do_mantiserve_exploration_task(MantiserveTaskKind.Explore, session, build, opts)

    return task.to_info()


@router.post("/manticore/explore-function/{build_id}", response_model=MantiserveTaskInformation)
def _execute_manticore_function_exploration_task(
    opts: ExploreFunctionOptions,
    build: db.Build = Depends(has_build(state=db.BuildState.Built)),
    session: orm.Session = Depends(has_db),
) -> MantiserveTaskInformation:
    """Run a Mantiserve underconstrained exploration task, focusing on a particular function.

    See the associated Mantiserve docs.
    """
    logger.debug(f"Received function explore message for build: {build.uuid}")

    # Start Manticore exploration.
    task = _do_mantiserve_exploration_task(MantiserveTaskKind.ExploreFunction, session, build, opts)

    return task.to_info()


@router.post("/manticore/reachability/{build_id}")
def _execute_manticore_reachability_task(
    opts: ReachabilityOptions,
    build: db.Build = Depends(has_build(state=db.BuildState.Built)),
    session: orm.Session = Depends(has_db),
) -> str:
    """Run a Mantiserve reachability task on a build with an optional Detector.

    See the associated Mantiserve docs.
    """
    logger.debug(f"Received Reachability message for build: {build.uuid}")

    # Process Reachability message and assess its validity
    validation_errs = validate_reachability_msg(opts.reach_msg)
    if len(validation_errs) != 0:
        raise HTTPException(
            status_code=400, detail=f"Invalid Reachability message: {validation_errs}"
        )

    if len(opts.reach_msg.waypoints) == 0:
        raise HTTPException(
            status_code=400, detail="Reachability message must have at least one Waypoint"
        )

    docker_image = opts.docker_image
    if docker_image is None:
        docker_image = build.bitcode_artifact.attributes.get("image")

    task = db.MantiserveTask.create(
        build,
        MantiserveTaskKind.Reachability,
        request_msg=pydantic_encoder(opts.reach_msg),
        docker_image=docker_image,
    )
    session.add(task)
    session.commit()

    # Start Manticore reachability.
    try:
        run_reachability.delay(
            reach_msg=opts.reach_msg,
            reachability_task_id=task.uuid,
            build_id=build.uuid,
            docker_image=docker_image,
            memory_limit=opts.docker_memory_limit_mb,
        )
    except run_reachability.OperationalError as exc:
        err_msg = f"Encountered an error when trying start: {exc}"
        task.transition_to_state(MantiserveTaskState.Failed, err_msg)
        session.add(task)
        session.commit()
        raise HTTPException(status_code=500, detail=f"{task.uuid=}: {err_msg}")

    return task.uuid


@router.get("/manticore/tasks/{task_id}/logs", response_model=ArtifactInformation)
def _get_manticore_logs(
    task: db.MantiserveTask = Depends(has_mantiserve_task()),
) -> ArtifactInformation:
    """Return artifact information for a mantiserve tasks's log artifact.

    The artifact ID returned in this response can be used to fetch the log's contents.
    """
    artifact = [a for a in task.artifacts if a.kind == ArtifactKind.MantiserveTaskLog]
    if len(artifact) == 1:
        return artifact[0].to_info()
    elif len(artifact) == 0:
        raise HTTPException(status_code=404, detail="no logs for this mantiserve task")
    else:
        raise HTTPException(
            status_code=500, detail="internal error: more than one mantiserve log artifact"
        )
