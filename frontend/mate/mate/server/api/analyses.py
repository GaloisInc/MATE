"""Routes for managing and running POI analyses.

These routes are **not** documented in Sphinx, since they aren't Python APIs.

See the OpenAPI or Swagger UI documentation.
"""

import logging
from typing import Dict, List, Optional, Union

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from sqlalchemy import orm

import mate_query.db as db
from mate.poi.poi_types import Analysis
from mate.server.api.common import (
    has_build,
    has_db,
    has_flowfinder_snapshot,
    has_poi_analysis,
    has_poi_result,
)
from mate.tasks.analyze import run_analysis
from mate_common.models.analyses import (
    AnalysisInfo,
    AnalysisTaskInfo,
    FlowFinderAnnotations,
    FlowFinderSnapshotInfo,
    GraphRequests,
    POIResultInfo,
)
from mate_common.models.builds import BuildState

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/analyses", response_model=List[AnalysisInfo])
def _get_all_analyses() -> List[AnalysisInfo]:
    """Returns all registered analyses."""
    return [k.to_info() for _, k in Analysis.iter_analyses()]


@router.get("/analyses/tasks", response_model=Union[List[str], List[AnalysisTaskInfo]])
def _get_all_analysis_tasks(
    session: orm.Session = Depends(has_db),
    state: Optional[db.AnalysisTaskState] = None,
    detail: bool = False,
) -> Union[List[str], List[AnalysisTaskInfo]]:
    """Return information on all known analysis tasks."""
    query = session.query(db.AnalysisTask)
    if state is not None:
        query = query.filter_by(state=state)

    tasks = query.all()
    if detail:
        return [task.to_info() for task in tasks]
    else:
        return [task.uuid for task in tasks]


@router.get("/analyses/tasks/{build_id}", response_model=Union[List[str], List[AnalysisTaskInfo]])
def _get_analysis_tasks_for_build(
    build: db.Build = Depends(has_build(state=db.BuildState.Built)),
    state: Optional[db.AnalysisTaskState] = None,
    detail: bool = False,
) -> Union[List[str], List[AnalysisTaskInfo]]:
    """Return information on any analysis tasks currently associated with the given build."""
    tasks = build.analysis_tasks
    if state is not None:
        tasks = [task for task in tasks if task.state == state]

    if detail:
        return [task.to_info() for task in tasks]
    else:
        return [task.uuid for task in tasks]


@router.get("/pois/build/{build_id}", response_model=List[POIResultInfo])
def _get_pois_by_build(
    build: db.Build = Depends(has_build(state=db.BuildState.Built)),
) -> List[POIResultInfo]:
    """Returns all POI results for a given build ID."""

    pois = []
    for analysis_task in build.analysis_tasks:
        for poi in analysis_task.poi_results:
            pois.append(poi.to_info())

    return pois


@router.get("/pois", response_model=List[POIResultInfo])
def _get_all_pois(session: orm.Session = Depends(has_db)) -> List[POIResultInfo]:
    """Returns all POI results for all builds."""
    return [poi.to_info() for poi in session.query(db.POIResult).all()]


@router.get("/pois/{poi_id}/detail", response_model=POIResultInfo)
def _get_poi_details(result: db.POIResult = Depends(has_poi_result)) -> POIResultInfo:
    """Return detailed POI information for the given POI result ID."""

    return result.to_info()


@router.put("/pois/{poi_id}")
def _put_poi_status(
    done: Optional[bool] = None,
    flagged: Optional[bool] = None,
    poi: db.POIResult = Depends(has_poi_result),
    session: orm.Session = Depends(has_db),
) -> None:
    """Update the `flagged` and `done` states for the given POI result."""
    if done is not None:
        poi.done = done
    if flagged is not None:
        poi.flagged = flagged
    session.commit()


@router.get("/pois/{poi_id}/snapshots", response_model=List[FlowFinderSnapshotInfo])
def _get_snapshots_for_poi_result(
    poi: db.POIResult = Depends(has_poi_result),
) -> List[FlowFinderSnapshotInfo]:
    """Return all snapshots for the given POI result."""
    return [s.to_info() for s in poi.snapshots]


@router.post("/pois/{poi_id}/snapshots", response_model=str)
def _create_snapshot_for_poi_result(
    label: str = Body(...),
    filters: List[str] = Body(...),
    graph_requests: GraphRequests = Body(...),
    hidden_graph_ids: List[str] = Body(...),
    hidden_node_ids: List[str] = Body(...),
    user_annotations: Dict[str, FlowFinderAnnotations] = Body(...),
    poi: db.POIResult = Depends(has_poi_result),
    session: orm.Session = Depends(has_db),
) -> str:
    """Creates a new snapshot for the given POI result, with the given label and graph requests."""
    snapshot = db.FlowFinderSnapshot.create(
        poi_result=poi,
        build=poi.analysis_task.build,
        label=label,
        filters=filters,
        graph_requests=graph_requests,
        hidden_graph_ids=hidden_graph_ids,
        hidden_node_ids=hidden_node_ids,
        user_annotations=user_annotations,
    )
    session.add(snapshot)
    session.commit()

    return snapshot.uuid


@router.get("/snapshots", response_model=Union[List[str], List[FlowFinderSnapshotInfo]])
def _get_snapshots(
    detail: bool = False, session: orm.Session = Depends(has_db)
) -> Union[List[str], List[FlowFinderSnapshotInfo]]:
    """Return a list of all POI snapshots known to MATE.

    `detail` controls the detail in the response. When true, the response is a list of snapshot
    information models. When false, the response is a list of snapshot IDs.
    """

    snapshots = session.query(db.FlowFinderSnapshot).all()

    if detail:
        return [s.to_info() for s in snapshots]
    else:
        return [s.uuid for s in snapshots]


@router.post("/snapshots/{build_id}", response_model=str)
def _create_snapshot(
    label: str = Body(...),
    filters: List[str] = Body(...),
    graph_requests: GraphRequests = Body(...),
    hidden_graph_ids: List[str] = Body(...),
    hidden_node_ids: List[str] = Body(...),
    user_annotations: Dict[str, FlowFinderAnnotations] = Body(...),
    build: db.Build = Depends(has_build(state=BuildState.Built)),
    session: orm.Session = Depends(has_db),
) -> str:
    """Creates a new snapshot from the given options, without associating it with a particular POI
    result."""

    snapshot = db.FlowFinderSnapshot.create(
        poi_result=None,
        build=build,
        label=label,
        filters=filters,
        graph_requests=graph_requests,
        hidden_graph_ids=hidden_graph_ids,
        hidden_node_ids=hidden_node_ids,
        user_annotations=user_annotations,
    )

    session.add(snapshot)
    session.commit()

    return snapshot.uuid


@router.get("/snapshots/{snapshot_id}", response_model=FlowFinderSnapshotInfo)
def _get_snapshot(
    snapshot: db.FlowFinderSnapshot = Depends(has_flowfinder_snapshot),
) -> FlowFinderSnapshotInfo:
    """Returns the model corresponding to the given snapshot ID, if it exists."""
    return snapshot.to_info()


@router.put("/snapshots/{snapshot_id}", response_model=str)
def _update_snapshot(
    label: Optional[str] = Body(None),
    graph_requests: Optional[GraphRequests] = Body(None),
    user_annotations: Optional[Dict[str, FlowFinderAnnotations]] = Body(None),
    snapshot: db.FlowFinderSnapshot = Depends(has_flowfinder_snapshot),
    session: orm.Session = Depends(has_db),
) -> str:
    """Updates the snapshot corresponding to the given ID, if it exists.

    Returns the ID of the updated snapshot.
    """
    if label is not None:
        snapshot.label = label
    if graph_requests is not None:
        if len(graph_requests) < 1:
            raise HTTPException(status_code=422, detail="`graph_requests` must not be empty")
        snapshot.graph_requests = graph_requests
    if user_annotations is not None:
        if len(user_annotations) < 1:
            raise HTTPException(status_code=422, detail="`user_annotations` must not be empty")
        snapshot.user_annotations = user_annotations

    session.add(snapshot)
    session.commit()

    return snapshot.uuid


@router.delete("/snapshots/{snapshot_id}", response_model=str)
def _delete_snapshot(
    snapshot: db.FlowFinderSnapshot = Depends(has_flowfinder_snapshot),
    session: orm.Session = Depends(has_db),
) -> str:
    """Deletes the snapshot corresponding to the given ID, if it exists.

    Returns the ID of the deleted snapshot.
    """
    session.delete(snapshot)
    session.commit()

    return snapshot.uuid


@router.post("/analyses/run/{build_id}", response_model=List[AnalysisTaskInfo])
def _run_all_analyses(
    request: Request,
    response: Response,
    build: db.Build = Depends(has_build(state=BuildState.Built)),
    session: orm.Session = Depends(has_db),
) -> List[AnalysisTaskInfo]:
    """Runs all registered POI analyses for the given build ID."""

    created_tasks = []
    for analysis, _ in Analysis.iter_analyses():
        task = db.AnalysisTask.create(analysis, build)
        session.add(task)
        session.commit()

        run_analysis.delay(analysis_task_id=task.uuid)
        created_tasks.append(task)

    response.headers["Location"] = request.url_for(_get_pois_by_build.__name__, build_id=build.uuid)
    return [task.to_info() for task in created_tasks]


@router.post("/analyses/{analysis_name}/run/{build_id}", response_model=AnalysisTaskInfo)
def _run_specific_analysis(
    request: Request,
    response: Response,
    analysis_name: str = Depends(has_poi_analysis),
    build: db.Build = Depends(has_build(state=BuildState.Built)),
    session: orm.Session = Depends(has_db),
) -> AnalysisTaskInfo:
    """Runs the requested POI analysis (by ID) for the given build."""

    task = db.AnalysisTask.create(analysis_name, build)
    session.add(task)
    session.commit()

    run_analysis.delay(analysis_task_id=task.uuid)
    response.headers["Location"] = request.url_for(_get_pois_by_build.__name__, build_id=build.uuid)

    return task.to_info()
