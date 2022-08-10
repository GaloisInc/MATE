"""This module provides facilities for utility operations that could be shared during the setup of
tasks."""
import io
from pathlib import Path

from mantiserve.exceptions import MantiserveError
from mantiserve.logging import logger
from mate.config import MATE_SCRATCH
from mate_query import db


def mantiserve_workspace_path(task_id: str) -> Path:
    """Returns a directory for persisting Mantiserve artifacts related to the ``task_id``."""
    reachability_workspace: Path = MATE_SCRATCH / Path(f"reachability-{task_id}")
    reachability_workspace.mkdir(parents=True)
    return reachability_workspace


def cleanup_task_with_failure(session: db.Session, exc: Exception, task_id: str) -> None:
    """Take care of transitioning the task to failure with information according to ``exc`` and
    commit to DB."""
    task_result = session.query(db.MantiserveTask).get(task_id)
    changed = False

    if isinstance(exc, MantiserveError):
        if exc.logs and len(exc.logs) > 0:
            mantiserve_run_artifact_log = db.Artifact.create_with_object(
                kind=db.ArtifactKind.MantiserveTaskLog,
                fileobj=io.BytesIO(exc.logs),
                attributes={"filename": "err.log", "task_id": task_id},
            )
            logger.info(f"Saved error logs in artifact store: {mantiserve_run_artifact_log.uuid}")
            task_result.artifacts.append(mantiserve_run_artifact_log)
            changed = True

    if task_result.state != db.MantiserveTaskState.Failed:
        task_result.transition_to_state(db.MantiserveTaskState.Failed, str(exc))
        changed = True

    if changed:
        session.add(task_result)
        session.commit()
