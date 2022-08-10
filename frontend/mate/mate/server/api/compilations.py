"""API routes for managing MATE compilations.

These routes are **not** documented in Sphinx, since they aren't Python APIs.

See the OpenAPI or Swagger UI documentation.
"""

from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import orm

import mate_query.db as db
from mate.integration.challenge_broker import Client as BrokerClient
from mate.logging import logger
from mate.server.api.common import has_compilation, has_db
from mate.tasks import compile as compile_tasks
from mate_common.models.artifacts import ArtifactInformation, ArtifactKind
from mate_common.models.compilations import (
    CompilationInformation,
    CompilationState,
    CompileOptions,
    TargetKind,
    TargetSpecification,
)
from mate_common.utils import unreachable

router = APIRouter()


@router.get("/compilations", response_model=Union[List[str], List[CompilationInformation]])
def _get_compilations(
    session: orm.Session = Depends(has_db),
    state: Optional[CompilationState] = None,
    detail: bool = False,
) -> Union[List[str], List[CompilationInformation]]:
    """List all compilations currently known to MATE.

    `state` allows the list of compilations to be filtered on status, e.g. `compiled` to
    list only compilations that have been fully compiled.

    `detail` controls the detail in the response. Without `detail`, the response
    is a list of compilation IDs. With `detail`, the response
    is a list of compilation information models.
    """
    query = session.query(db.Compilation)
    if state is not None:
        query = query.filter_by(state=state)
    compilations = query.all()

    if detail:
        return [c.to_info() for c in compilations]
    else:
        return [c.uuid for c in compilations]


@router.get("/compilations/{compilation_id}", response_model=CompilationInformation)
def _get_compilation(
    compilation: db.Compilation = Depends(has_compilation()),
) -> CompilationInformation:
    """Return information for a single compilation."""

    return compilation.to_info()


@router.get("/compilations/{compilation_id}/logs", response_model=ArtifactInformation)
def _get_compilation_logs(
    compilation: db.Compilation = Depends(has_compilation()),
) -> ArtifactInformation:
    """Return artifact information for a compilation's log artifact.

    The artifact ID returned in this response can be used to fetch the log's contents.
    """
    artifact = [a for a in compilation.artifacts if a.kind == ArtifactKind.CompileOutputCompileLog]
    if len(artifact) == 1:
        return artifact[0].to_info()
    elif len(artifact) == 0:
        raise HTTPException(status_code=404, detail="no logs for this compilation")
    else:
        raise HTTPException(status_code=500, detail="internal error: more than one compilation log")


def _start_compilation_for_artifact(
    session: orm.Session, artifact: db.Artifact, options: CompileOptions
) -> db.Compilation:
    """Start a new compilation, using the given artifact's contents as the source code and the given
    options to control the compilation process."""
    compilation = db.Compilation.create(
        source_artifact=artifact,
        options=jsonable_encoder(options),
    )
    compilation.artifacts.append(artifact)

    session.add_all([compilation, artifact])
    session.commit()

    compile_tasks.compile_artifact.delay(
        artifact.uuid,
        options,
        compilation_id=compilation.uuid,
    )

    return compilation


@router.post("/compilations", status_code=201, response_model=CompilationInformation)
def _start_compilation(
    spec: TargetSpecification,
    session: orm.Session = Depends(has_db),
) -> CompilationInformation:
    """Start a new compilation using the parameters in `spec`."""
    if spec.kind is TargetKind.Artifact:
        artifact = session.query(db.Artifact).get(spec.handle)

        if artifact is None:
            raise HTTPException(status_code=404, detail=f"no artifact with id {spec.handle}")
        if not artifact.kind.is_compile_target() or not artifact.has_object():
            raise HTTPException(
                status_code=400, detail="this artifact is not a valid compilation target"
            )

        compilation = _start_compilation_for_artifact(session, artifact, spec.options)
        return compilation.to_info()
    elif (
        spec.kind is TargetKind.BrokeredChallengeName
        or spec.kind is TargetKind.BrokeredChallengeID
        or spec.kind is TargetKind.BrokeredChallengeTargetID
    ):
        broker_client = BrokerClient()
        target = None
        if spec.kind is TargetKind.BrokeredChallengeID:
            challenge = broker_client.challenge_by_id(spec.handle)
            if challenge is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"no such brokered challenge: {spec.handle=} ({spec.kind=})",
                )

            target = broker_client.root_target(for_=challenge)
        elif spec.kind is TargetKind.BrokeredChallengeName:
            challenge = broker_client.challenge_by_name(spec.handle)
            if challenge is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"no such brokered challenge: {spec.handle=} ({spec.kind=})",
                )

            target = broker_client.root_target(for_=challenge)
        else:
            target = broker_client.target_by_id(spec.handle)
            if target is None:
                raise HTTPException(
                    status_code=404, detail=f"no such brokered target: {spec.handle=} ({spec.kind})"
                )

        if target is None:
            raise HTTPException(
                status_code=404,
                detail=f"broker reports that {spec=} is valid, but has no corresponding target",
            )

        if spec.options.containerized and not target.compilation_image:
            raise HTTPException(
                status_code=422,
                detail=(
                    "containerized compilation requested, but brokered target lacks an appropriate image; "
                    f"available images: {target.images}"
                ),
            )

        # NOTE(ww): We need our own copy of the target, even for containerized challenges.
        # Why? Because our target *might* not be the root source-assisted target.
        # In other words, it might have source and/or build modifications that make
        # it easier for us to ingest. We need to make sure we actually get those
        # modifications, so we can't rely on the copy that's baked into the image.
        blob = broker_client.blob_by_id(target.blob_id)
        if blob is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"challenge broker error: target={target.id_} "
                    f"specifies blob={target.blob_id} but not found"
                ),
            )

        data = broker_client.blob_data(blob)
        if data is None:
            raise HTTPException(status_code=503, detail="")

        # NOTE(ww): Obnoxious: the challenge broker might not have been configured
        # with a reasonable worker timeout, meaning that streaming the blob data
        # may exceed the default and cause the server to hang up prematurely.
        # We don't have a clear way to catch this earlier since we don't begin
        # streaming the response until we start creating the artifact on our side.
        try:
            artifact = db.Artifact.create_with_object(
                kind=ArtifactKind.CompileTargetBrokeredChallenge,
                fileobj=data,
                attributes={
                    "filename": blob.name,
                    "blob_id": blob.id_,
                    "target_id": target.id_,
                    "challenge_id": target.challenge_id,
                    "challenge_name": target.challenge_name,
                    "image": target.compilation_image,
                    "chess_metadata": target.metadata.dict(by_alias=True),
                },
            )
        except Exception:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"challenge broker error: target={target.id_} "
                    f"specifies blob={target.blob_id} but seems to have "
                    "hung up while retrieving"
                ),
            )

        logger.debug(f"created {artifact.uuid=} of kind {artifact.kind}")

        if target.source_assisted:
            compilation = _start_compilation_for_artifact(session, artifact, spec.options)
        else:
            # We use the rejected state to signal a compilation that can't be serviced,
            # e.g. one that can't be compiled because it isn't marked as source-assisted.
            # This is *not* an HTTP error case, since we do successfully produce a compilation
            # object; we just can't progress any further with it.
            logger.debug(
                "Rejecting a compilation for a non-source-assisted target: "
                f"{target} {spec.handle=} {spec.kind}"
            )
            compilation = db.Compilation.create(
                source_artifact=artifact, options=jsonable_encoder(spec.options)
            )
            compilation.transition_to_state(db.CompilationState.Rejected)
            session.add(compilation)
            session.commit()
        return compilation.to_info()
    else:
        unreachable(spec.kind)
