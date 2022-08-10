import argparse
import io
import json
import logging
import os
import shutil
from argparse import Namespace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, Optional, Union

from pydantic import parse_obj_as
from pydantic.json import pydantic_encoder

from dwarfcore.helper import manticore_explore
from mantiserve.exceptions import MantiserveError
from mantiserve.logging import (
    RedirectedManticoreLogs,
    configure,
    default_manticore_file_logging_handler,
    logger,
)
from mantiserve.tasks.docker_util import run_task_in_docker
from mantiserve.tasks.util import cleanup_task_with_failure, mantiserve_workspace_path
from mate.config import EXPLORE_RUNNER
from mate.tasks import _Task, executor
from mate_common.models.bytes import Mebibytes
from mate_common.models.integration import Explore, ExploreFunction
from mate_query import db, storage


class _ExploreTask(_Task):
    def on_failure(
        self, exc: Exception, _task_id: Any, _args: Any, kwargs: Dict[str, Any], _einfo: Any
    ) -> None:
        """Set the state of the task to failed and attach a message based on ``exc``."""
        explore_task_id = kwargs.get("explore_task_id")
        if explore_task_id is None:
            logger.error("probable API misuse: task didn't take a explore_task_id kwarg")
            return

        cleanup_task_with_failure(self.session, exc, explore_task_id)


@executor.task(bind=True, base=_ExploreTask)
def run_exploration(
    self: _ExploreTask,
    explore_msg: Union[Explore, ExploreFunction],
    explore_task_id: str,
    build_id: str,
    docker_image: Optional[str] = None,
    memory_limit: Optional[Mebibytes] = None,
) -> None:
    task_result = self.session.query(db.MantiserveTask).get(explore_task_id)
    task_result.job_id = self.request.id
    self.session.add(task_result)
    self.session.commit()
    """Run the actual explore task."""
    if docker_image is None:
        return _run_explore_natively(build_id, explore_msg, explore_task_id, self.session)

    return _run_explore_docker(
        build_id, docker_image, explore_msg, explore_task_id, self.session, memory_limit
    )


def _run_explore_natively(
    build_id: str,
    explore_msg: Union[Explore, ExploreFunction],
    explore_task_id: str,
    session: db.Session,
) -> None:
    """Internal function to run Explore task natively."""
    logger.debug(f"Running exploration task natively {explore_task_id}")

    # Save logs from Manticore and Mantiserve from this point on
    # Set up similarly as Manticore to get reasonable-looking output formatting
    workspace = mantiserve_workspace_path(explore_task_id)
    log_file_name = str(workspace / "explore.log")
    native_capture_log_handler = default_manticore_file_logging_handler(log_file_name)

    try:
        # Run the exploration
        with RedirectedManticoreLogs(native_capture_log_handler):
            _do_explore(
                explore_msg,
                explore_task_id,
                build_id,
                session,
                manticore_workspace=str(workspace),
            )
    except Exception as e:
        with open(log_file_name, "rb") as log_file:
            logs = log_file.read()
        raise MantiserveError(f"Issue during exploration: {e}", logs=logs)
    finally:
        task_result = session.query(db.MantiserveTask).get(explore_task_id)
        if os.stat(log_file_name).st_size != 0:
            logger.debug(f"Saving log file {log_file_name} to artifact store")
            with open(log_file_name, "rb") as log_file:
                # Save the logs
                mantiserve_run_artifact_log = db.Artifact.create_with_object(
                    kind=db.ArtifactKind.MantiserveTaskLog,
                    fileobj=log_file,
                    attributes={"filename": "explore_native.log", "task_id": explore_task_id},
                )
                task_result.artifacts.append(mantiserve_run_artifact_log)
                logger.info(f"Saved logs in artifact store: {mantiserve_run_artifact_log.uuid}")
        else:
            logger.info(f"Log file empty, not saving it in artifact store")
        session.add(task_result)
        session.commit()


def _run_explore_docker(
    build_id: str,
    docker_image: str,
    explore_msg: Union[Explore, ExploreFunction],
    explore_task_id: str,
    session: db.Session,
    memory_limit: Optional[Mebibytes] = None,
) -> None:
    """Internal function to handle Docker integration when running exploration."""
    logger.info(f"Running exploration task in Docker {explore_task_id}")

    # Manticore will create its workspace directory as a child of this directory
    explore_workspace = mantiserve_workspace_path(explore_task_id)
    explore_msg_file: Path = Path(explore_workspace) / "explore_msg.json"
    with explore_msg_file.open("w") as rf:
        json.dump(explore_msg, rf, default=pydantic_encoder)

    # Run the explore task within Docker container
    explore_logs = run_task_in_docker(
        docker_image,
        container_name=f"mantiserve-explore-{explore_task_id}",
        command=[
            "python3",
            str(EXPLORE_RUNNER),
            str(explore_msg_file),
            f"--task_id={explore_task_id}",
            f"--build_id={build_id}",
            f"--manticore_workspace={str(explore_workspace)}",
            f"--task={type(explore_msg).__name__}",  # Explore or ExploreFunction
        ],
        working_dir=str(explore_workspace),
        memory_limit=memory_limit,
    )

    if len(explore_logs) > 0:
        logger.debug("Saving Manticore Explore container logs as artifacts")
        task_result = session.query(db.MantiserveTask).get(explore_task_id)
        mantiserve_run_artifact_log = db.Artifact.create_with_object(
            kind=db.ArtifactKind.MantiserveTaskLog,
            fileobj=io.BytesIO(explore_logs),
            attributes={"filename": "explore_docker.log", "task_id": explore_task_id},
        )
        task_result.artifacts.append(mantiserve_run_artifact_log)
        session.add(task_result)
        session.commit()
        logger.info(f"Saved logs in artifact store: {mantiserve_run_artifact_log.uuid}")
    else:
        logger.warning("Manticore Explore container has no logs to save")


def _do_explore(
    explore_msg: Union[Explore, ExploreFunction],
    explore_task_id: str,
    build_id: str,
    session: db.Session,
    *,
    manticore_workspace: Optional[str] = None,
) -> None:
    """A function that does the actual explore logic. Should be called from either a script
    entrypoint with the required parameters or from a Celery task.

    Caller is responsible for transitioning the task to a failed state during
    the event of an exception.

    :param explore_msg: Explore message that will be processed
    :param explore_task_id: ID for this task
    :param build_id: ID of build to get required CPG connection and artifacts
    :param session: If the caller of this function has a valid database session
        and wants to pass it here, then it will be used, otherwise this function
        creates its own session
    """
    task_result: db.MantiserveTask = session.query(db.MantiserveTask).get(explore_task_id)
    task_result.transition_to_state(db.MantiserveTaskState.Running)

    if task_result.kind not in (
        db.MantiserveTaskKind.Explore,
        db.MantiserveTaskKind.ExploreFunction,
    ):
        raise MantiserveError(
            f"Task kind ({task_result.kind=}) does not match {explore_msg.__class__.__name__} task"
        )

    build = session.query(db.Build).get(build_id)
    if build is None:
        raise MantiserveError(f"Build with build_id {build_id} does not exist.")

    graph = db.Graph.from_build(build, session)

    # Check if there is an artifact that Manticore can execute
    download_artifact_kind = db.ArtifactKind.BuildOutputQuotidianCanonicalBinary
    artifact: db.Artifact = next(
        filter(
            lambda artifact_: artifact_.kind == download_artifact_kind,
            build.artifacts,
        )
    )
    if artifact is None:
        raise MantiserveError(
            f"Could not find a suitable artifact ({download_artifact_kind}) to download for specified build ({build=})"
        )

    with TemporaryDirectory() as tmp_dir:
        bin_name = build.bitcode_artifact.attributes["binary_filename"]
        dst_name = os.path.join(tmp_dir, bin_name)
        with artifact.get_object() as src, open(dst_name, mode="w+b") as dst:
            shutil.copyfileobj(src, dst)
            dst.flush()
            bin_path = Path(dst.name)
            # manticore_explore() handles both Explore and ExploreFunction
            ret = manticore_explore(
                bin_path,
                session,
                graph,
                explore_msg,
                logger,
                manticore_workspace=manticore_workspace,
            )

    logger.debug(f"DONE running Mantiserve Explore id {explore_task_id} with result {ret}")
    task_result.response_msg = pydantic_encoder(ret)
    task_result.transition_to_state(db.MantiserveTaskState.Completed)
    session.add(task_result)
    session.commit()


def _parse_cli() -> Namespace:
    """Parse script CLI options."""
    parser = argparse.ArgumentParser(description="Process a Manticore Explore request.")

    parser.add_argument("explore_json_path", type=Path, help="Path to json Explore message")
    parser.add_argument("--task_id", type=str, help="Task ID for this task")
    parser.add_argument("--build_id", type=str, help="Build ID to get CPG info")
    parser.add_argument(
        "--task",
        type=str,
        help="Type of exploration to perform",
        choices=[Explore.__name__, ExploreFunction.__name__],
    )
    parser.add_argument(
        "--manticore_workspace",
        type=Path,
        help="Path to empty Manticore workspace where Manticore will save its artifacts",
    )

    return parser.parse_args()


if __name__ == "__main__":
    """This program is a wrapper that acqures a db connection and runs a Mantiserve Explore task,
    passing along status updates to the DB."""

    args = _parse_cli()

    # Don't use default stderr handler on root logger
    logging.getLogger().handlers = []

    logger = configure(Namespace(verbose=2))

    import manticore.utils.log

    manticore.utils.log.init_logging()

    manticore_workspace: Path = args.manticore_workspace
    if manticore_workspace:
        assert (
            manticore_workspace.is_dir()
        ), f"Manticore workspace {manticore_workspace} is not a directory."

    logger.debug("Trying to initialize database connection")
    db.initialize("postgresql://mate@db/mate", create=False)
    session = db.new_session()

    logger.debug("Trying to initialize storage connection")
    storage.initialize("storage:9000")

    with args.explore_json_path.open("r") as f:
        explore_msg_json = json.load(f)

    task_result = session.query(db.MantiserveTask).get(args.task_id)
    if task_result is None:
        build = session.query(db.Build).get(args.build_id)
        # Create a new task if it doesn't exist
        logger.warning(f"Creating a new task with ID {args.task_id} because it doesn't exist yet.")
        task_result = db.MantiserveTask(
            uuid=args.task_id,
            build=build,
            kind=db.MantiserveTaskKind.Explore,
            request_msg=explore_msg_json,
            state=db.MantiserveTaskState.Created,
        )
        session.add(task_result)
        session.commit()

    if not manticore_workspace:
        manticore_workspace = mantiserve_workspace_path(task_result.uuid)

    # NOTE(boyan): we could also use something like
    #     getattr(<mate.intergation.messages module>, args.task)
    # to get the class automatically
    msg_type = Explore if args.task == "Explore" else ExploreFunction
    try:
        _do_explore(
            parse_obj_as(msg_type, explore_msg_json),
            args.task_id,
            args.build_id,
            session,
            manticore_workspace=str(manticore_workspace),
        )
    except Exception as e:
        # Make sure we transition to a failed state
        task_result = session.query(db.MantiserveTask).get(task_result.uuid)
        if task_result.state != db.MantiserveTaskState.Failed:
            task_result.transition_to_state(db.MantiserveTaskState.Failed, str(e))
            session.add(task_result)
            session.commit()
        raise e
