from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi.encoders import jsonable_encoder

from mate.build import compile as mate_compile_v2
from mate_common.models.artifacts import ArtifactKind
from mate_common.models.compilations import CompileOptions
from mate_query import db


@pytest.fixture(autouse=True)
def compile_tarball(session):
    """A fixture for turning a source tarball through MATE's compilation pipeline.

    The tarball is expected to contain a program structure that resembles a CHESS challenge.
    """

    def _compile_tarball(tarball: Path, compile_options: Dict[str, Any]) -> db.Compilation:
        options = CompileOptions(**compile_options)

        with tarball.open("rb") as io:
            source_artifact = db.Artifact.create_with_object(
                kind=ArtifactKind.CompileTargetTarball,
                fileobj=io,
                attributes={"filename": tarball.name},
            )

        compilation = db.Compilation.create(
            source_artifact=source_artifact,
            options=jsonable_encoder(options),
        )
        compilation.artifacts.append(source_artifact)
        session.add_all([compilation, source_artifact])
        session.commit()

        mate_compile_v2.compile_artifact(source_artifact, compilation, session, options)

        return compilation

    return _compile_tarball
