import logging
from time import sleep
from typing import Tuple

from mate.assertions import build_assert
from mate.build import build as mate_build
from mate.poi.poi_types import Analysis
from mate.tasks import _BuildTask, analyze, executor
from mate_common.models.artifacts import ArtifactKind
from mate_common.models.builds import BuildOptions, BuildState
from mate_query import db

logger = logging.getLogger(__name__)


@executor.task(bind=True, base=_BuildTask)
def get_build_nodes(self: _BuildTask, *, build_id: str) -> Tuple[int, int]:
    build = self.session.query(db.Build).get(build_id)
    graph = self.session.graph_from_build(build)
    node_count = self.session.query(graph.Node).count()
    edge_count = self.session.query(graph.Edge).count()

    return (node_count, edge_count)


@executor.task(bind=True, base=_BuildTask)
def build_artifact(
    self: _BuildTask, artifact_id: str, opts: BuildOptions, *, build_id: str
) -> None:
    try:
        logger.debug(f"{self.build_log_handler=}")
        logger.addHandler(self.build_log_handler)
        logger.debug(f"running build_artifact task with {opts=}")

        artifact = self.session.query(db.Artifact).get(artifact_id)
        build_assert(
            artifact.kind == ArtifactKind.CompileOutputBitcode,
            f"invalid artifact kind ({artifact.kind=} is not bitcode)",
            build_id=build_id,
        )

        build = self.session.query(db.Build).get(build_id)
        build_assert(
            build.state == BuildState.Created,
            f"invalid build state ({build.state=} is not created)",
            build_id=build_id,
        )

        mate_build.build_artifact(artifact, build, self.session, opts)
    finally:
        logger.removeHandler(self.build_log_handler)


@executor.task(bind=True, base=_BuildTask)
def await_built_state_and_start_all_analyses(self: _BuildTask, build_id: str) -> None:
    build = self.session.query(db.Build).get(build_id)
    while not build.state.is_terminal():
        logger.debug(f"waiting for build: {build.uuid=} {build.state=}")
        sleep(5)
        self.session.expire(build)

    if build.state != BuildState.Built:
        logger.warning(
            f"got failed state for build, not running analyses: {build.uuid=} {build.state=}"
        )
        return

    # TODO(ww): This is duped with the body of `ate.server.api.analyses.routes.run_all_analyses`,
    # which isn't ideal. Both bodies should be factored out into a more general analysis task.
    for analysis, _ in Analysis.iter_analyses():
        task = db.AnalysisTask.create(analysis, build)
        self.session.add(task)
        self.session.commit()

        analyze.run_analysis.delay(analysis_task_id=task.uuid)
