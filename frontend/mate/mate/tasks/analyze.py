import mate_query.db as db
from mate.logging import logger
from mate.poi.poi_types import Analysis
from mate.tasks import _RunAnalysisTask, executor


@executor.task(bind=True, base=_RunAnalysisTask)
def run_analysis(
    self: _RunAnalysisTask,
    *,
    analysis_task_id: str,
) -> None:
    """Runs a single analysis and writes results to the database.

    This happens through a subprocess call to the ``analysis_runner`` script. The script prints POI
    results to ``stdout`` as soon as they're available, and this function saves them to the database as
    soon as it receives them.

    Checks to see if the analysis underlying this ``AnalysisTask`` has already been run
    on the underlying build before actually running it.
    """

    # check the cache before running the analysis
    # TODO(#923): once there is an artifacts table, include matching over any inputs to the analysis
    session = self.session
    task = session.query(db.AnalysisTask).get(analysis_task_id)

    if (
        session.query(db.AnalysisTask)
        .filter(
            db.AnalysisTask.uuid != task.uuid,
            db.AnalysisTask.analysis_name == task.analysis_name,
            db.AnalysisTask.build == task.build,
        )
        .first()
    ) is not None:
        # NOTE(ww): For the time being, we treat analyses on builds as idempotent:
        # if we already have an analysis task for the given build with this
        # analysis, then we mark the current task as a duplicate and end early.
        # This will probably change in the future, with better support for
        # analyses that can be run multiple times with different parameters.
        task.transition_to_state(db.AnalysisTaskState.Duplicate)
        session.add(task)
        session.commit()

        logger.info(
            "Returning previously computed POI results for analysis %s and build %s",
            task.analysis.uuid,
            task.build.uuid,
        )
        return

    task.transition_to_state(db.AnalysisTaskState.Running)
    session.add(task)
    session.commit()

    try:
        graph = db.Graph.from_build(task.build, self.session)
        analysis_class = Analysis.by_name(task.analysis_name)
        analysis = analysis_class()
        for result, requests in analysis.run(self.session, graph, dict()):
            logger.info(f"Received POI from {task.analysis_name}! It is: {result}")
            poi = db.POIResult.create(
                poi=result.dict(),
                analysis_task=task,
                graph_requests=[r.dict() for r in requests],
            )
            session.add(poi)
            session.commit()

        task.transition_to_state(db.AnalysisTaskState.Completed)
    except Exception as exception:
        logger.exception(f"An exception {exception} occurred while running {task.analysis_name}")
        task.transition_to_state(db.AnalysisTaskState.Failed)
    finally:
        session.add(task)
        session.commit()
