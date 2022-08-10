"""API routes for managing MATE artifacts.

These routes are **not** documented in Sphinx, since they aren't Python APIs.

See the OpenAPI or Swagger UI documentation.
"""

import uuid
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import orm

import mate_query.db as db
from mate.server.api.common import has_artifact, has_db
from mate_common.models.artifacts import ArtifactInformation, ArtifactKind, ArtifactSpecification

router = APIRouter()


@router.post("/artifacts", status_code=201, response_model=ArtifactInformation)
def _create_artifact(
    spec: ArtifactSpecification,
    request: Request,
    response: Response,
    session: orm.Session = Depends(has_db),
) -> ArtifactInformation:
    """Create a new artifact.

    Artifacts have no initial content when created through this endpoint.
    """
    artifact = db.Artifact(uuid=uuid.uuid4().hex, kind=spec.kind, attributes=spec.attributes)
    session.add(artifact)
    session.commit()

    response.headers["Location"] = request.url_for(
        _get_artifact.__name__, artifact_id=artifact.uuid
    )
    return artifact.to_info()


@router.get("/artifacts/{artifact_id}", response_model=ArtifactInformation)
def _get_artifact(artifact: db.Artifact = Depends(has_artifact())) -> ArtifactInformation:
    """Return an information model for the given artifact."""
    return artifact.to_info()


@router.post("/artifacts/{artifact_id}/object", status_code=201, response_model=ArtifactInformation)
def _upload_artifact_contents(
    request: Request,
    response: Response,
    artifact: db.Artifact = Depends(has_artifact(populated=False)),
    file: UploadFile = File(...),
    session: orm.Session = Depends(has_db),
) -> ArtifactInformation:
    """Upload content for the given artifact.

    Only empty (i.e., just created) artifacts can have content added to them.
    """
    artifact.put_object(file.file)
    artifact.attributes["filename"] = file.filename
    session.add(artifact)
    session.commit()

    response.headers["Location"] = request.url_for(
        _get_artifact_contents.__name__, artifact_id=artifact.uuid
    )
    return artifact.to_info()


@router.get("/artifacts/{artifact_id}/object")
def _get_artifact_contents(
    artifact: db.Artifact = Depends(has_artifact(populated=True)),
) -> StreamingResponse:
    """Stream the contents of this artifact.

    Only artifacts that actually contain content can be streamed.
    """
    with artifact.get_object() as io:
        return StreamingResponse(io)


@router.get("/artifacts", response_model=Union[List[str], List[ArtifactInformation]])
def _get_artifacts(
    session: orm.Session = Depends(has_db),
    kind: Optional[ArtifactKind] = None,
    detail: bool = False,
) -> Union[List[str], List[ArtifactInformation]]:
    """List all artifacts currently known to MATE.

    `kind` allows the list of artifacts to be filtered by content, e.g.
    `compile-output:binary` to list only artifacts that are binaries produced
    by some compilation process.

    `detail` controls the output format for this endpoint. When `true`, the output
    is a list of artifact information models. When `false`, the output is a list
    of artifact IDs.
    """
    query = session.query(db.Artifact)
    if kind is not None:
        query = query.filter_by(kind=kind)
    artifacts = query.all()

    if detail:
        return [a.to_info() for a in artifacts]
    else:
        return [a.uuid for a in artifacts]
