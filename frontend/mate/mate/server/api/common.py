import shutil
from pathlib import Path
from typing import Callable, Optional

from fastapi import Depends, HTTPException, UploadFile
from sqlalchemy import orm

import mate_query.db as db
from mate.logging import logger
from mate.poi.poi_types import Analysis
from mate_common.models.artifacts import ArtifactKind
from mate_common.models.builds import BuildState
from mate_common.models.compilations import CompilationState
from mate_common.models.manticore import MantiserveTaskState


def has_db() -> orm.Session:
    """Helper function to provide REST endpoint handlers with a database session.

    This function should only be used in the type annotation of a session object in an endpoint
    handler.
    """
    session = db.new_session()
    try:
        yield session
    except:
        session.rollback()
        raise
    finally:
        session.close()


def has_artifact(
    populated: Optional[bool] = None, kind: Optional[ArtifactKind] = None
) -> Callable[..., db.Artifact]:
    """Helper function to provide REST endpoint handlers with direct access to a particular
    artifact.

    The ``populated`` parameter can be used to return an artifact only if it's populated (``True``)
    or unpopulated (``False``). By default, the artifact is returned without checking.

    The ``kind`` parameter can be used to return an artifact only if it's of the specified
    ``ArtifactKind``. By default, the artifact is returned without checking.
    """

    def _has_artifact(artifact_id: str, session: orm.Session = Depends(has_db)) -> db.Artifact:
        artifact = session.query(db.Artifact).get(artifact_id)
        if artifact is None:
            raise HTTPException(
                status_code=404, detail=f"nonexistent artifact requested: {artifact_id}"
            )

        if populated is not None and populated != artifact.has_object():
            raise HTTPException(
                status_code=400,
                detail=f"invalid artifact state for this operation (expected {populated=})",
            )

        if kind is not None and kind != artifact.kind:
            raise HTTPException(
                status_code=400,
                detail=f"invalid artifact kind for this operation (expected {kind=})",
            )

        return artifact

    return _has_artifact


def has_compilation(state: Optional[CompilationState] = None) -> Callable[..., db.Compilation]:
    """Helper function to provide REST endpoint handlers with direct access to a particular
    compilation.

    The ``state`` parameter can be used to return a build if and only if it's in the specified
    state.
    """

    def _has_compilation(
        compilation_id: str, session: orm.Session = Depends(has_db)
    ) -> db.Compilation:
        compilation = session.query(db.Compilation).get(compilation_id)
        if compilation is None:
            raise HTTPException(
                status_code=404, detail=f"nonexistent compilation requested: {compilation_id}"
            )

        if state is not None and state != compilation.state:
            raise HTTPException(
                status_code=400,
                detail=f"invalid compilation state for this operation (expected {state}, got {compilation.state})",
            )
        return compilation

    return _has_compilation


def has_build(state: Optional[BuildState] = None) -> Callable[..., db.Build]:
    """Helper function to provide REST endpoint handlers with direct access to a particular build.

    The ``state`` parameter can be used to return a build if and only if it's in the specified
    state.
    """

    def _has_build(build_id: str, session: orm.Session = Depends(has_db)) -> db.Build:
        build = session.query(db.Build).get(build_id)
        if build is None:
            raise HTTPException(status_code=404, detail=f"nonexistent build requested: {build_id}")

        if state is not None and state != build.state:
            raise HTTPException(
                status_code=400,
                detail=f"invalid build state for this operation (expected {state}, got {build.state})",
            )
        return build

    return _has_build


def has_cpg(
    session: orm.Session = Depends(has_db),
    build: db.Build = Depends(has_build(state=BuildState.Built)),
) -> db.Graph:
    """Helper function to provide REST endpoint handlers with direct access to a particular CPG,
    identified by its build ID."""
    return db.Graph.from_build(build, session)


def has_poi_analysis(analysis_name: str) -> str:
    """Helper function to provide REST endpoint handlers with direct access to a particular
    registered POI analysis, identified by its name."""

    try:
        Analysis.by_name(analysis_name)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"nonexistent analysis requested: {analysis_name}"
        )

    return analysis_name


def has_poi_result(
    poi_id: str,
    session: orm.Session = Depends(has_db),
) -> db.POIResult:
    """Helper function to provide REST endpoint handlers with direct access to a particular POI
    result, identified by its POI result ID."""

    poi = session.query(db.POIResult).filter(db.POIResult.uuid == poi_id).one()
    if poi is None:
        raise HTTPException(status_code=404, detail=f"no POI result with ID: {poi_id}")
    return poi


def has_flowfinder_snapshot(
    snapshot_id: str, session: orm.Session = Depends(has_db)
) -> db.FlowFinderSnapshot:
    """Helper function to provide REST endpoint handlers with direct access to a particular
    snapshot, identified by its ID."""

    snapshot = session.query(db.FlowFinderSnapshot).get(snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"no snapshot with ID: {snapshot_id}")
    return snapshot


def has_mantiserve_task(
    state: Optional[MantiserveTaskState] = None,
) -> Callable[..., db.MantiserveTask]:
    """Helper function to provide REST endpoint handlers with direct access to a particular
    Mantiserve task, identified by its ID.

    The ``state`` parameter can be used to return a Mantiserve task if and only if it's in the
    specified state.
    """

    def _has_mantiserve_task(
        task_id: str,
        session: orm.Session = Depends(has_db),
    ) -> db.MantiserveTask:
        task = session.query(db.MantiserveTask).get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"no such Mantiserve task: {task_id}")

        if state is not None and state != task.state:
            raise HTTPException(
                status_code=400,
                detail=f"invalid task state for this operation (expected {state}, got {task.state})",
            )

        return task

    return _has_mantiserve_task


def save_file_to_server(file: UploadFile, server_path: Path) -> None:
    """Persists temporary UploadFiles to ``server_path``.

    Note: if this operation fails fastapi will automatically log the traceback
    and return a 500 internal server error, so we don't need a try/catch block here.
    """
    logger.info("Server saving uploaded file to: %s", server_path)
    file.file.seek(0)
    with server_path.open("wb") as file_on_server:
        shutil.copyfileobj(file.file, file_on_server)
    file.file.close()
