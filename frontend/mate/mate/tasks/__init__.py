import io
import logging
import traceback
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict, Optional

import celery
from celery.signals import worker_process_init

from mate_common.models.artifacts import ArtifactKind
from mate_common.models.builds import BuildState
from mate_common.models.compilations import CompilationState
from mate_query import db, storage

logger = logging.getLogger(__name__)


class _Task(celery.Task):
    """A MATE-specific subclass of Celery's ``Task`.."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._session: Optional[db.Session] = None

    def after_return(self, *_args: Any, **_kwargs: Any) -> None:
        if self._session is not None:
            self._session.close()

    @property
    def session(self) -> db.orm.Session:
        if self._session is None:
            self._session = db.new_session()

        return self._session


class _CompilationTask(_Task):
    """A task class for the compilation pipeline.

    This class provides last-ditch error handling for the compilation pipeline, and **must** be used
    instead of the more generic ``_Task`` when performing compilation tasks.
    """

    def on_failure(
        self, exc: Any, _task_id: Any, _args: Any, kwargs: Dict[str, Any], _einfo: Any
    ) -> None:
        try:
            # NOTE(ww): We intentionally don't use `self.session` here, since we might
            # be dealing with an uncontrolled failure caused by a stale session.
            session = db.new_session()
            compilation_id = kwargs.get("compilation_id")
            if compilation_id is None:
                logger.error("probable API misuse: task didn't take a compilation_id kwarg")
                return

            compilation = session.query(db.Compilation).get(compilation_id)
            if compilation.state != CompilationState.Failed:
                logger.warning(
                    f"task={self} failed with {exc} but didn't set the compilation to failed; fixing"
                )
                compilation.transition_to_state(CompilationState.Failed)

            # If we've failed and don't already have a compilation log, then we create one
            # with our current exception state.
            compilation_log = next(
                (
                    a
                    for a in compilation.artifacts
                    if a.kind == ArtifactKind.CompileOutputCompileLog
                ),
                None,
            )
            if compilation_log is None:
                log = f"Top exception:\n\n{str(exc)}\n\n{traceback.format_exc()}"
                compilation.artifacts.append(
                    db.Artifact.create_with_object(
                        kind=ArtifactKind.CompileOutputCompileLog,
                        fileobj=io.StringIO(log),
                        attributes={"filename": "compile.log"},
                    )
                )

            session.add(compilation)
        finally:
            session.commit()
            session.close()


class _BuildTask(_Task):
    """A task class for the build pipeline.

    This class provides last-ditch error handling for the build pipeline, and **must** be used
    instead of the more generic ``_Task`` when performing build tasks.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._build_log_handler: logging.Handler = logging.NullHandler()

    @property
    def build_log_handler(self) -> logging.Handler:
        return self._build_log_handler

    def before_start(self, _task_id: Any, _args: Any, _kwargs: Any) -> None:
        self._build_log_path = Path(NamedTemporaryFile(suffix=".log", delete=False).name)
        self._build_log_handler = logging.FileHandler(self._build_log_path)

    # TODO(ww): mypy is unhappy with this subclass signature, but it's identical
    # to the one in the Celery codebase. Typechecking bug?
    def after_return(  # type: ignore[override]
        self,
        _status: Any,
        _retval: Any,
        _task_id: Any,
        _args: Any,
        kwargs: Dict[str, Any],
        _einfo: Any,
    ) -> None:
        if not self._build_log_path.exists():
            logger.error("build log doesn't exist?")
            return

        try:
            # NOTE(ww): We intentionally don't use `self.session` here, since we might
            # be dealing with an uncontrolled failure caused by a stale session.
            session = db.new_session()
            build_id = kwargs.get("build_id")
            if build_id is None:
                logger.error("probable API misuse: task didn't take a build_id kwarg")
                return

            build = session.query(db.Build).get(build_id)
            with self._build_log_path.open() as io:
                build.artifacts.append(
                    db.Artifact.create_with_object(
                        kind=ArtifactKind.BuildOutputTaskLog,
                        fileobj=io,
                        attributes={"filename": "build.log"},
                    )
                )
            session.add(build)
        finally:
            self._build_log_path.unlink()
            session.commit()
            session.close()

    def on_failure(self, exc: Any, _task_id: Any, _args: Any, kwargs: Any, _einfo: Any) -> None:
        try:
            # NOTE(ww): We intentionally don't use `self.session` here, since we might
            # be dealing with an uncontrolled failure caused by a stale session.
            session = db.new_session()
            build_id = kwargs.get("build_id")
            if build_id is None:
                logger.error("probable API misuse: task didn't take a build_id kwarg")
                return

            build = session.query(db.Build).get(build_id)
            if build.state != BuildState.Failed:
                logger.warning(
                    f"task={self} failed with {exc} but didn't set the build to failed; fixing"
                )
                build.transition_to_state(BuildState.Failed)
                session.add(build)
                session.commit()
        finally:
            session.commit()
            session.close()


class _RunAnalysisTask(_Task):
    """A task class for the analysis runner.

    This class provides last-ditch error handling for the POI framework, and **must** be used
    instead of the more generic ``_Task`` when performing analysis tasks.
    """

    def on_failure(
        self, exc: Any, _task_id: Any, _args: Any, kwargs: Dict[str, Any], _einfo: Any
    ) -> None:
        try:
            # NOTE(ww): We intentionally don't use `self.session` here, since we might
            # be dealing with an uncontrolled failure caused by a stale session.
            session = db.new_session()
            analysis_task_id = kwargs.get("analysis_task_id")
            if analysis_task_id is None:
                logger.error("probable API misuse: task didn't take a analysis_task_id kwarg")
                return

            analysis_task = session.query(db.AnalysisTask).get(analysis_task_id)
            if analysis_task.state != db.AnalysisTaskState.Failed:
                logger.warning(
                    f"task={self} failed with {exc} but didn't set the analysis task to failed; fixing"
                )
                analysis_task.transition_to_state(db.AnalysisTaskState.Failed)
                session.add(analysis_task)
                session.commit()
        finally:
            session.close()


executor = celery.Celery(
    "mate",
    broker="amqp://broker",
    backend="db+postgresql://mate@db/mate",
    include=[
        "mantiserve.tasks.reachability",
        "mantiserve.tasks.explore",
        "mate.tasks.build",
        "mate.tasks.compile",
        "mate.tasks.pipeline",
        "mate.tasks.analyze",
    ],
    task_cls=_Task,
)

executor.conf.task_track_started = True
executor.conf.result_extended = True
executor.conf.database_engine_options = {"pool_pre_ping": True}

# NOTE(ww): Tell Celery to use Python's pickle format for task and result
# serialization. We do this to make marshaling of Pydantic models through
# the task interface less painful -- Pydantic models can be pickled trivially,
# but don't support trivial JSON serialization through the default JSON
# middleware. Longer term, we could write our own middleware that hooks into
# kombu to provide JSON serialization with specific Pydantic handling.
executor.conf.task_serializer = "pickle"
executor.conf.result_serializer = "pickle"
executor.conf.event_serializer = "json"
executor.conf.accept_content = ["application/json", "application/x-python-serialize"]
executor.conf.result_accept_content = ["application/json", "application/x-python-serialize"]


@worker_process_init.connect()
def initialize_db(**_kwargs: Any) -> None:
    db.initialize("postgresql://mate@db/mate", create=False)


@worker_process_init.connect()
def initialize_storage(**_kwargs: Any) -> None:
    storage.initialize("storage:9000")


@worker_process_init.connect()
def initialize_analyses(**_kwargs: Any) -> None:
    # NOTE(ww): Deferred imports here to avoid circular dependencies.
    from mate import poi  # noqa: F401

    poi.initialize()
