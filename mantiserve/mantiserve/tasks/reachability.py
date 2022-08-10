import argparse
import io
import json
import logging
import shutil
from argparse import Namespace
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict, Optional

from pydantic import parse_obj_as
from pydantic.json import pydantic_encoder

from mantiserve.exceptions import MantiserveError
from mantiserve.logging import (
    RedirectedManticoreLogs,
    configure,
    default_manticore_file_logging_handler,
    logger,
)
from mantiserve.mantireach import manticore_reach
from mantiserve.tasks.docker_util import run_task_in_docker
from mantiserve.tasks.util import cleanup_task_with_failure, mantiserve_workspace_path
from mate.config import REACHABILITY_RUNNER
from mate.tasks import _Task, executor
from mate_common.models.bytes import Mebibytes
from mate_common.models.integration import Reachability
from mate_query import db, storage


class _ReachabilityTask(_Task):
    def on_failure(
        self, exc: Exception, _task_id: Any, _args: Any, kwargs: Dict[str, Any], _einfo: Any
    ) -> None:
        """Set the state of the task to failed and attach a message based on ``exc``."""
        reachability_task_id = kwargs.get("reachability_task_id")
        if reachability_task_id is None:
            logger.error("probable API misuse: task didn't take a reachability_task_id kwarg")
            return

        cleanup_task_with_failure(self.session, exc, reachability_task_id)


@executor.task(bind=True, base=_ReachabilityTask)
def run_reachability(
    self: _ReachabilityTask,
    reach_msg: Reachability,
    reachability_task_id: str,
    build_id: str,
    docker_image: Optional[str] = None,
    memory_limit: Optional[Mebibytes] = None,
) -> None:
    """Run the actual reachability task."""
    task_result = self.session.query(db.MantiserveTask).get(reachability_task_id)
    task_result.job_id = self.request.id
    self.session.add(task_result)
    self.session.commit()
    if docker_image is None:
        return _run_reachability_natively(build_id, reach_msg, reachability_task_id, self.session)

    return _run_reachability_docker(
        build_id, docker_image, reach_msg, reachability_task_id, self.session, memory_limit
    )


def _run_reachability_natively(
    build_id: str, reach_msg: Reachability, reachability_task_id: str, session: db.Session
) -> None:
    """Internal function to run reachability task natively."""
    logger.debug(f"Running reachability task natively {reachability_task_id}")

    # Save logs from Manticore and Mantiserve from this point on
    # Set up similarly as Manticore to get reasonable-looking output formatting
    workspace = mantiserve_workspace_path(reachability_task_id)
    log_file_name = str(workspace / "reachability.log")
    native_capture_log_handler = default_manticore_file_logging_handler(log_file_name)

    try:
        # Run the reachability
        with RedirectedManticoreLogs(native_capture_log_handler):
            _do_reachability(
                reach_msg,
                reachability_task_id,
                build_id,
                session,
                manticore_workspace=str(workspace),
            )
    except Exception as e:
        with open(log_file_name, "rb") as log_file:
            logs = log_file.read()
        raise MantiserveError(f"Issue during reachability: {e}", logs=logs)
    finally:
        logger.debug(f"Saving log file {log_file_name} to artifact store")
        with open(log_file_name, "rb") as log_file:
            # Save the logs
            task_result = session.query(db.MantiserveTask).get(reachability_task_id)
            mantiserve_run_artifact_log = db.Artifact.create_with_object(
                kind=db.ArtifactKind.MantiserveTaskLog,
                fileobj=log_file,
                attributes={"filename": "reachability_native.log", "task_id": reachability_task_id},
            )
            logger.info(f"Saved logs in artifact store: {mantiserve_run_artifact_log.uuid}")
        task_result.artifacts.append(mantiserve_run_artifact_log)
        session.add(task_result)
        session.commit()


def _run_reachability_docker(
    build_id: str,
    docker_image: str,
    reach_msg: Reachability,
    reachability_task_id: str,
    session: db.Session,
    memory_limit: Optional[Mebibytes] = None,
) -> None:
    """Internal function to handle Docker integration when running reachability."""
    logger.info(f"Running reachability task in Docker {reachability_task_id}")

    # Manticore will create its workspace directory as a child of this directory
    reachability_workspace = mantiserve_workspace_path(reachability_task_id)
    reachability_msg_file: Path = Path(reachability_workspace) / "reach_msg.json"
    with reachability_msg_file.open("w") as rf:
        json.dump(reach_msg, rf, default=pydantic_encoder)

    # Run the reachability task within Docker container
    reachability_logs = run_task_in_docker(
        docker_image,
        container_name=f"mantiserve-reachability-{reachability_task_id}",
        command=[
            "python3",
            str(REACHABILITY_RUNNER),
            str(reachability_msg_file),
            f"--task_id={reachability_task_id}",
            f"--build_id={build_id}",
            f"--manticore_workspace={str(reachability_workspace)}",
        ],
        working_dir=str(reachability_workspace),
        memory_limit=memory_limit,
    )

    if len(reachability_logs) > 0:
        logger.debug("Saving Manticore Reachability container logs as artifacts")
        task_result = session.query(db.MantiserveTask).get(reachability_task_id)
        mantiserve_run_artifact_log = db.Artifact.create_with_object(
            kind=db.ArtifactKind.MantiserveTaskLog,
            fileobj=io.BytesIO(reachability_logs),
            attributes={"filename": "reachability_docker.log", "task_id": reachability_task_id},
        )
        task_result.artifacts.append(mantiserve_run_artifact_log)
        session.add(task_result)
        session.commit()
        logger.info(f"Saved logs in artifact store: {mantiserve_run_artifact_log.uuid}")
    else:
        logger.warning("Manticore Reachability container has no logs to save")


def _do_reachability(
    reach_msg: Reachability,
    reachability_task_id: str,
    build_id: str,
    session: db.Session,
    *,
    manticore_workspace: Optional[str] = None,
) -> None:
    """A function that does the actual reachability logic. Should be called from either a script
    entrypoint with the required parameters or from a Celery task.

    Caller is responsible for transitioning the task to a failed state during
    the event of an exception.

    :param reach_msg: Reachability message that will be processed
    :param reachability_task_id: ID for this task
    :param build_id: ID of build to get required CPG connection and artifacts
    :param session: If the caller of this function has a valid database session
        and wants to pass it here, then it will be used, otherwise this function
        creates its own session
    """
    task_result: db.MantiserveTask = session.query(db.MantiserveTask).get(reachability_task_id)
    task_result.transition_to_state(db.MantiserveTaskState.Running)

    if task_result.kind != db.MantiserveTaskKind.Reachability:
        raise MantiserveError(f"Task kind ({task_result.kind=}) does not match Reachability task")

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

    ctxt = Namespace(verbose=2, m_verbose=2)  # logging.DEBUG

    with artifact.get_object() as src, NamedTemporaryFile(mode="w+b") as dst:
        shutil.copyfileobj(src, dst)
        dst.flush()
        bin_path = Path(dst.name)

        # TODO Collect and report execution of Manticore that relate to Waypoint processing
        #   - https://gitlab-ext.galois.com/mate/MATE/issues/570
        ret = manticore_reach(
            bin_path, session, graph, ctxt, reach_msg, manticore_workspace=manticore_workspace
        )

    logger.debug(
        f"DONE running Mantiserve Reachability id {reachability_task_id} with result {ret}"
    )
    task_result.response_msg = pydantic_encoder(ret)
    task_result.transition_to_state(db.MantiserveTaskState.Completed)
    session.add(task_result)
    session.commit()


def _parse_cli() -> Namespace:
    """Parse script CLI options."""
    parser = argparse.ArgumentParser(description="Process a Manticore Reachability request.")

    parser.add_argument("reach_json_path", type=Path, help="Path to json Reachability message")
    parser.add_argument("--task_id", type=str, help="Task ID for this task")
    parser.add_argument("--build_id", type=str, help="Build ID to get CPG info")
    parser.add_argument(
        "--manticore_workspace",
        type=Path,
        help="Path to empty directory where Manticore will save its artifacts",
    )

    return parser.parse_args()


if __name__ == "__main__":
    """This program is a wrapper that acqures a db connection and runs a Mantiserve Reachability
    task, passing along status updates to the DB."""

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

    with args.reach_json_path.open("r") as f:
        reach_msg_json = json.load(f)

    task_result = session.query(db.MantiserveTask).get(args.task_id)
    if task_result is None:
        build = session.query(db.Build).get(args.build_id)
        # Create a new task if it doesn't exist
        logger.warning(f"Creating a new task with ID {args.task_id} because it doesn't exist yet.")
        task_result = db.MantiserveTask(
            uuid=args.task_id,
            build=build,
            kind=db.MantiserveTaskKind.Reachability,
            request_msg=reach_msg_json,
            state=db.MantiserveTaskState.Created,
        )
        session.add(task_result)
        session.commit()

    if not manticore_workspace:
        manticore_workspace = mantiserve_workspace_path(task_result.uuid)

    logger.info("Running reachability from script entry")
    try:
        _do_reachability(
            parse_obj_as(Reachability, reach_msg_json),
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
