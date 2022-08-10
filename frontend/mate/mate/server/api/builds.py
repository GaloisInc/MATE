"""API routes for managing MATE CPG builds.

These routes are **not** documented in Sphinx, since they aren't Python APIs.

See the OpenAPI or Swagger UI documentation.
"""

from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from sqlalchemy import orm

import mate_query.db as db
from mate.logging import logger
from mate.server.api.common import has_build, has_compilation, has_db
from mate.tasks import build as build_tasks
from mate_common.models.artifacts import ArtifactInformation, ArtifactKind
from mate_common.models.builds import BuildInformation, BuildOptions, BuildState
from mate_common.models.challenge_broker import ChallengeMetadataPathType, ChallengeMetadataTarget
from mate_common.models.compilations import CompilationState

router = APIRouter()


@router.post("/builds/{compilation_id}/build", response_model=List[str])
def _start_builds_from_compilation(
    opts: BuildOptions,
    run_all_pois: bool = False,
    session: orm.Session = Depends(has_db),
    compilation: db.Compilation = Depends(has_compilation(state=CompilationState.Compiled)),
) -> List[str]:
    """Create one or more CPG builds from the given compilation.

    One build is created for each binary produced by the compilation phase. This can produce a large
    number of builds when the compilation has a large number of binary outputs; use the "Start
    Single Build From Compilation" endpoint to create just a single CPG build for a binary in the
    compilation.
    """
    is_brokered = compilation.source_artifact.kind == ArtifactKind.CompileTargetBrokeredChallenge
    chess_targets = []
    if is_brokered:
        chess_targets = [
            ChallengeMetadataTarget(**t)
            for t in compilation.source_artifact.attributes["chess_metadata"]["targets"]
        ]

    builds = []
    for artifact in compilation.artifacts:
        if artifact.kind != ArtifactKind.CompileOutputBitcode:
            continue

        if is_brokered:
            # If we're dealing with the compilation products of a brokered challenge,
            # then we only want to start CPG builds for the targets specified by
            # the CHESS metadata. Perform that filtering here.
            binary_filename = artifact.attributes["binary_filename"]
            if not any(
                t.runtime.type_ == ChallengeMetadataPathType.ELF
                and t.runtime.path.endswith(binary_filename)
                for t in chess_targets
            ):
                logger.debug(
                    f"skipping build for binary produced from a non-target: {binary_filename}"
                )
                continue

        build = db.Build.create(
            bitcode_artifact=artifact,
            compilation=compilation,
            options=jsonable_encoder(opts),
        )
        build.artifacts.append(artifact)
        builds.append(build)

    session.add_all(builds)
    session.commit()

    # Start all builds after commiting them above, so that they show up as created.
    for build in builds:
        build_tasks.build_artifact.delay(build.bitcode_artifact.uuid, opts, build_id=build.uuid)
        if run_all_pois:
            build_tasks.await_built_state_and_start_all_analyses.delay(build.uuid)

    return [b.uuid for b in builds]


@router.post("/builds/{compilation_id}/build/single")
def _start_single_build_from_compilation(
    request: Request,
    response: Response,
    opts: BuildOptions,
    session: orm.Session = Depends(has_db),
    compilation: db.Compilation = Depends(has_compilation(state=CompilationState.Compiled)),
    target: Optional[str] = Query(None),
    run_all_pois: bool = Query(False, alias="run-all-pois"),
    artifact_detail: bool = Query(False, alias="artifact-detail"),
    rebuild_of: Optional[str] = Query(None, alias="rebuild-of"),
) -> BuildInformation:
    """Creates a single CPG build from the given compilation.

    The filename of the binary to target for the CPG is selected via the `target` parameter. If
    `target` is not specified, then the first binary output recorded by the compilation phase is
    used.

    `run-all-pois` controls whether all registered POI analyses are run as soon as the CPG is ready.
    By default, this endpoint does not run any analyses.

    `artifact-detail` controls the level of detail for each artifact in the response model.

    `rebuild-of` links the newly created build to a previous build, which may or may not
    have failed. This field has no effect on this build itself, but can be used by the UI
    to prevent repeated rebuilds.
    """

    # If we're being asked to perform a rebuild, ensure that the original
    # build actually exists.
    if rebuild_of is not None:
        previous_build = session.query(db.Build).get(rebuild_of)
        if previous_build is None:
            raise HTTPException(
                status_code=404,
                detail=f"nonexistent original build: {rebuild_of}",
            )

    if target is None:
        artifact = next(
            (a for a in compilation.artifacts if a.kind == ArtifactKind.CompileOutputBitcode), None
        )
    else:
        artifact = next(
            (
                a
                for a in compilation.artifacts
                if a.kind == ArtifactKind.CompileOutputBitcode
                and a.attributes["binary_filename"] == target
            ),
            None,
        )

    if artifact is None:
        raise HTTPException(
            status_code=404,
            detail=f"couldn't find a suitable bitcode target for single build: {target=}",
        )

    build = db.Build.create(
        bitcode_artifact=artifact,
        compilation=compilation,
        options=jsonable_encoder(opts),
        attributes={"rebuild_of": rebuild_of} if rebuild_of is not None else {},
    )
    build.artifacts.append(artifact)

    session.add(build)
    session.commit()

    build_tasks.build_artifact.delay(build.bitcode_artifact.uuid, opts, build_id=build.uuid)
    if run_all_pois:
        build_tasks.await_built_state_and_start_all_analyses.delay(build.uuid)

    response.headers["Location"] = request.url_for(_get_build.__name__, build_id=build.uuid)

    return build.to_info(artifact_detail=artifact_detail)


@router.get("/builds", response_model=Union[List[str], List[BuildInformation]])
def _get_builds(
    session: orm.Session = Depends(has_db),
    state: Optional[BuildState] = None,
    detail: bool = False,
    artifact_detail: bool = Query(False, alias="artifact-detail"),
) -> Union[List[str], List[BuildInformation]]:
    """List all builds currently known to MATE.

    `state` allows the list of builds to be filtered on status, e.g. `built` to
    list only builds that have been fully built.

    `detail` and `artifact-detail` control the detail in the response. Without
    `detail`, the response is a list of build IDs. With `detail`, the response
    is a list of build information models. With `artifact-detail`, the build
    information models are additionally supplemented with detail about each
    artifact associated with the build.
    """
    query = session.query(db.Build)
    if state is not None:
        query = query.filter_by(state=state)
    builds = query.all()

    if detail:
        return [b.to_info(artifact_detail=artifact_detail) for b in builds]
    else:
        return [b.uuid for b in builds]


@router.get("/builds/{build_id}", response_model=BuildInformation)
def _get_build(
    build: db.Build = Depends(has_build()),
    artifact_detail: bool = Query(False, alias="artifact-detail"),
) -> BuildInformation:
    """Return information for a single build.

    With `artifact-detail`, the information model additionally includes detail about each associated
    artifact.
    """
    return build.to_info(artifact_detail=artifact_detail)


@router.get("/builds/{build_id}/logs", response_model=ArtifactInformation)
def _get_build_logs(
    build: db.Build = Depends(has_build(state=BuildState.Built)),
) -> ArtifactInformation:
    """Return artifact information for a build's log artifact.

    The artifact ID returned in this response can be used to fetch the log's contents.
    """
    artifact = [a for a in build.artifacts if a.kind == ArtifactKind.BuildOutputTaskLog]
    if len(artifact) == 1:
        return artifact[0].to_info()
    elif len(artifact) == 0:
        raise HTTPException(status_code=404, detail="no logs for this compilation")
    else:
        raise HTTPException(status_code=500, detail="internal error: more than one build log")
