from __future__ import annotations

import csv
import gzip
import json
import pathlib
import shutil
import uuid
from functools import lru_cache
from os import listdir
from os.path import join
from pathlib import Path
from typing import TYPE_CHECKING

import docker
import pytest
from fastapi.encoders import jsonable_encoder

from mate.build import build as mate_build
from mate.build import compile as mate_compile
from mate_common.models.artifacts import ArtifactKind
from mate_common.models.builds import BuildOptions, BuildState
from mate_common.models.compilations import CompilationState, CompileOptions
from mate_query import db, storage

if TYPE_CHECKING:
    from typing import Any, Dict, List, Optional, Tuple

    from mate_query.cpg.models.core.cpg import CPG

# -------------------------------------------------------------------

# The directory that this `conftest.py` is in.
HERE = Path(__file__).resolve().parent

# The directory that Dockerfiles for containerized pipelines live in.
DOCKERFILE_DIR = HERE / "assets" / "dockerfiles"

# Human readable identifiers (doubling as Docker image names), mapped to Dockerfile paths.
DOCKERFILE_MAP = {
    "mate-integration-phase2-environment": DOCKERFILE_DIR / "Dockerfile.phase2",
    "mate-integration-phase3-environment": DOCKERFILE_DIR / "Dockerfile.phase3",
}

# A cache for compilations that have already been run. Each compilation is uniquely
# identified by the tuple of (input_source, compile options), and is mapped to a
# compilation ID that's already present in the DB and marked as fully compiled.
# NOTE(ww): Not using an LRU cache is an intentional design choice here: using the `lru_cache`
# decorator would require the fixtures that use the cache to only accept hashable parameters,
# which would mean lots of marshaling into the actual data types used by the build pipeline,
# or lots of test-specific accommodations in the pipeline.
COMPILE_V2_CACHE: Dict[Tuple[Path, str], str] = {}

# Similarly to the above, but for CPG builds that have already been run. These
# are unique'd by the tuple of (compilation ID, build options) and are mapped to
# a build ID that's already present in the DB and marked as fully compiled.
BUILD_V2_CACHE: Dict[Tuple[str, str], str] = {}


@pytest.fixture(scope="function")
def docker_client():
    client = docker.DockerClient(base_url="unix:///var/run/docker.sock")
    yield client
    client.close()


@pytest.fixture(scope="function")
def docker_image_build(docker_client):
    def _docker_image_build(image: str):
        try:
            # Fast case: the image has already been built, so we can just return.
            docker_client.images.get(image)
        except docker.errors.ImageNotFound:
            with DOCKERFILE_MAP[image].open("rb") as io:
                docker_client.images.build(fileobj=io, tag=image)
        return image

    return _docker_image_build


@pytest.fixture(scope="session", autouse=True)
def storage_fixture():
    storage.initialize("storage:9000")


@pytest.fixture(scope="session", autouse=True)
def connection_fixture(exclusive_lock):
    with exclusive_lock("db") as exists:
        db.initialize("postgresql://mate@db/mate", create=not exists)


@pytest.fixture(scope="function")
def session():
    session = db.new_session()
    yield session
    session.close()


# NOTE(ww): This fixture contains stubbed artifacts for the underlying `db.Build`
# and `db.Artifact`. It should only be used to test pre-generated fixtures.
@pytest.fixture(scope="function")
def build(session):

    source_artifact = db.Artifact(uuid=uuid.uuid4().hex, kind=ArtifactKind.CompileTargetSingle)
    new_compilation = db.Compilation(
        uuid=uuid.uuid4().hex,
        state=CompilationState.Compiled,
        source_artifact=source_artifact,
        options=jsonable_encoder(CompileOptions()),
    )

    bitcode_artifact = db.Artifact(uuid.uuid4().hex, kind=ArtifactKind.CompileOutputBitcode)
    new_build = db.Build.create(
        bitcode_artifact=bitcode_artifact,
        compilation=new_compilation,
        options=jsonable_encoder(BuildOptions()),
    )
    session.add_all([source_artifact, new_compilation, bitcode_artifact, new_build])
    session.commit()
    yield new_build


@pytest.fixture(scope="session")
def fixture_data_dir():
    return pathlib.Path(__file__).resolve().parent / "postgres/fixtures"


def load_graph_fixture(fixture_dir, build_uuid, session):
    build = session.query(db.Build).get(build_uuid)
    # building is a no-op here, but we need to explicitly perform
    # both transitions for consistency with the state machine.
    build.transition_to_state(BuildState.Building)
    build.transition_to_state(BuildState.Inserting)
    cpg = session.graph_from_build(build)
    objects = []
    with (fixture_dir / "nodes.csv").open() as nodes_csv:
        reader = csv.reader(nodes_csv)
        for row in reader:
            objects.append(cpg.BaseNode(row[0], row[1], json.loads(row[2])))

    with (fixture_dir / "edges.csv").open() as edges_csv:
        reader = csv.reader(edges_csv)
        for row in reader:
            objects.append(
                cpg.BaseEdge(
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    json.loads(row[4]),
                )
            )

    session.bulk_save_objects(objects)
    build.transition_to_state(BuildState.Built)
    session.commit()

    graph = session.graph_from_build(build)
    return graph


@pytest.fixture(scope="function")
def diamond_graph(fixture_data_dir, build, session):
    yield load_graph_fixture(fixture_data_dir / "diamond", build.uuid, session)


@pytest.fixture(scope="function")
def small_graph(fixture_data_dir, build, session):
    """This fixture should be used to test parts of the query interface that don't require a
    "realistic" CPG, but are more "structural".

    For example, this is used to test subgraph construction. It would *not* be particularly
    appropriate for testing if a POI query has false positives.
    """
    yield load_graph_fixture(fixture_data_dir / "small", build.uuid, session)


# -------------------------------------------------------------------


@pytest.fixture(autouse=True)
def compile_v2(session, programs_path, make_tarball):
    def _compile_v2(program: str, compile_options: Dict[str, Any]) -> db.Compilation:
        program_path = programs_path / program

        if program_path.is_file():
            kind = ArtifactKind.CompileTargetSingle
        else:
            kind = ArtifactKind.CompileTargetTarball
            program_path = make_tarball(program_path)

        options = CompileOptions(**compile_options)

        # HACK(ww): `options` is not hashable since it contains lists, so we
        # use the JSON serialized form of the model for the cache key here.
        cache_key = (program_path, options.json())
        maybe_id = COMPILE_V2_CACHE.get(cache_key)
        if maybe_id is not None:
            return session.query(db.Compilation).get(maybe_id)

        with program_path.open("rb") as io:
            source_artifact = db.Artifact.create_with_object(
                kind=kind,
                fileobj=io,
                attributes={"filename": program_path.name},
            )

        compilation = db.Compilation.create(
            source_artifact=source_artifact,
            options=jsonable_encoder(options),
        )
        compilation.artifacts.append(source_artifact)
        session.add_all([compilation, source_artifact])
        session.commit()

        mate_compile.compile_artifact(source_artifact, compilation, session, options)

        # Add our new compilation to the cache.
        COMPILE_V2_CACHE[cache_key] = compilation.uuid

        return compilation

    return _compile_v2


@pytest.fixture(autouse=True)
def build_v2(session):
    def _build_v2(
        compilation: db.Compilation, build_options: Dict[str, Any], target: Optional[str] = None
    ) -> db.Build:
        options = BuildOptions(**build_options)

        # HACK(ww): `options` is not hashable since it contains lists, so we
        # use the JSON serialized form of the model for the cache key here.
        cache_key = (compilation.uuid, options.json())
        maybe_id = BUILD_V2_CACHE.get(cache_key)
        if maybe_id is not None:
            return session.query(db.Build).get(maybe_id)

        if target is not None:
            bitcode_artifact = next(
                a
                for a in compilation.artifacts
                if a.kind == ArtifactKind.CompileOutputBitcode
                and a.attributes["binary_filename"] == target
            )
        else:
            bitcode_artifact = next(
                a for a in compilation.artifacts if a.kind == ArtifactKind.CompileOutputBitcode
            )

        build = db.Build.create(
            compilation=compilation,
            bitcode_artifact=bitcode_artifact,
            options=jsonable_encoder(options),
        )
        build.artifacts.append(bitcode_artifact)
        session.add(build)
        session.commit()

        mate_build.build_artifact(bitcode_artifact, build, session, options)

        # Add our new build to the cache.
        BUILD_V2_CACHE[cache_key] = build.uuid

        return build

    return _build_v2


@pytest.fixture(autouse=True)
def cpg_db_v2(session, compile_v2, build_v2):
    def _cpg_db_v2(
        program: str, *, compile_options: Dict[str, Any] = {}, build_options: Dict[str, Any] = {}
    ) -> CPG:
        compilation = compile_v2(program, compile_options)
        build = build_v2(compilation, build_options)
        return session.graph_from_build(build)

    return _cpg_db_v2


@pytest.fixture()
def dc_cpg_v2(cpg_db_v2, session):
    """Create a CPG for a program in the Dwarfcore binary directory, returning both the CPG and the
    canonical binary for symex."""

    def _dc_cpg(prog: str, **kwargs) -> CPG:
        # TODO(ww): `cpg.build` should really be the `Build` model, not a build ID.
        cpg = cpg_db_v2(prog, **kwargs)
        build = session.query(db.Build).get(cpg.build)
        bin_artifact = next(
            a for a in build.artifacts if a.kind == ArtifactKind.BuildOutputQuotidianCanonicalBinary
        )
        test_bin = bin_artifact.persist_locally(suffix=".bin")

        return (cpg, test_bin)

    return _dc_cpg


@pytest.fixture(autouse=True)
def pointer_analysis_results_v2():
    def _pointer_analysis_results_v2(session, cpg):
        class PointerAnalysisResults:
            def __init__(self, directory: str):
                self._directory = directory
                self._paths = {
                    filename: join(directory, filename) for filename in listdir(directory)
                }

            @lru_cache(maxsize=64)
            def get(self, filename: str) -> List[List[str]]:
                with gzip.open(self._paths[filename], "rt") as tsv_file:
                    return list(csv.reader(tsv_file, delimiter="\t"))

        build = session.query(db.Build).get(cpg.build)
        result_artifact = next(
            a for a in build.artifacts if a.kind == ArtifactKind.BuildOutputDebugPointerAnalysis
        )
        results = result_artifact.persist_locally()
        results_dir = results.parent

        # This will unpack `pa_results` relative to `results_dir`.
        shutil.unpack_archive(results, results_dir, "gztar")
        return PointerAnalysisResults(results_dir / "pa_results")

    return _pointer_analysis_results_v2
