"""This module contains classes that represent tables in the Postgres DB, or derive from them."""

from __future__ import annotations

import io
import logging
import pathlib
import shutil
import sys
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import cached_property, lru_cache
from typing import TYPE_CHECKING, TypeVar

import minio
from fastapi.encoders import jsonable_encoder
from sqlalchemy import Column, ForeignKey, ForeignKeyConstraint, Index, create_engine, orm
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, array
from sqlalchemy.ext import compiler
from sqlalchemy.ext.declarative import as_declarative
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import mapper, relationship, sessionmaker
from sqlalchemy.schema import DDLElement, Table
from sqlalchemy.sql.elements import Grouping
from sqlalchemy.sql.expression import (
    FromClause,
    case,
    func,
    join,
    literal,
    null,
    select,
    text,
    true,
)
from sqlalchemy.types import Boolean, String

from mate.poi.poi_types import Analysis
from mate_common.assertions import mate_assert
from mate_common.error import MateError
from mate_common.models.analyses import (
    AnalysisTaskInfo,
    AnalysisTaskState,
    FlowFinderAnnotations,
    FlowFinderSnapshotInfo,
    GraphRequests,
    POIResultComplexity,
    POIResultInfo,
)
from mate_common.models.artifacts import ArtifactInformation, ArtifactKind
from mate_common.models.builds import BuildInformation, BuildOptions, BuildState
from mate_common.models.compilations import CompilationInformation, CompilationState, CompileOptions
from mate_common.models.cpg_types import (
    AST_EDGES,
    CONTROL_DEP_FORWARD,
    CONTROL_FLOW_FORWARD,
    DATA_FLOW_FORWARD,
    INFO_FLOW_FORWARD,
    LOCAL_CONTROL_FLOW_FORWARD,
    POINTS_TO,
    EdgeKind,
    NodeKind,
)
from mate_common.models.manticore import (
    MantiserveTaskInformation,
    MantiserveTaskKind,
    MantiserveTaskState,
)
from mate_query import storage
from mate_query.config import MATE_DEFAULT_EXPLORATION_BOUND
from mate_query.cpg.models.core.base import enum_column, uuid_column
from mate_query.cpg.models.core.cpg import BaseCPG
from mate_query.cpg.models.core.edge import BaseEdge
from mate_query.cpg.models.core.node import BaseNode

if TYPE_CHECKING:
    from typing import (
        IO,
        Any,
        AnyStr,
        Callable,
        ClassVar,
        Dict,
        Final,
        Iterator,
        List,
        Optional,
        Set,
        Tuple,
        Type,
    )

    from sqlalchemy.sql.expression import CTE, ColumnElement, Null

    from mate_query.cpg.models.core import Edge, Node


@as_declarative()
class Model:
    pass


logger = logging.getLogger(__name__)


# These are shared global instances
_connection_string: Optional[str] = None
_engine = None
_metadata = Model.metadata  # type: ignore[attr-defined]
_Session: Optional[Session] = None


class UninitializedDatabaseError(MateError):
    """An exception denoting an attempted use of an uninitialized database."""

    pass


# =================================================================


class Session(orm.Session):
    def graph_from_build(self, build: Build) -> Graph:
        return Graph.from_build(build, self)


# =================================================================


class Artifact:
    """Represents a filesystem artifact associated with zero or more builds.

    Artifacts are tagged with a ``kind``, which indicates their disposition within MATE. The
    ``kind`` may or may not reflect the file format itself. Artifacts also carry an ``attributes``
    dictionary, which contains unstructured metadata relevant to the artifact.
    """

    __table__: Table = None

    builds: List[Build]
    compilations: List[Compilation]

    def __init__(self, uuid: str, kind: ArtifactKind, *, attributes: Dict[str, Any] = {}) -> None:
        self.uuid = uuid
        self.kind = kind
        self.attributes = attributes

    @classmethod
    def create_with_object(
        cls, kind: ArtifactKind, *, fileobj: IO[AnyStr], attributes: Dict[str, Any] = {}
    ) -> Artifact:
        """Create a new ``Artifact`` and put the given fileobj into the object store, associating it
        with the newly created artifact."""
        artifact = cls(uuid=uuid.uuid4().hex, kind=kind, attributes=attributes)
        artifact.put_object(fileobj)
        return artifact

    def has_object(self) -> bool:
        """Returns whether this artifact has an associated object, i.e. whether an object has been
        upload to the object store for it."""
        try:
            storage.client.stat_object("artifacts", self.uuid)
        except minio.error.NoSuchKey:
            return False
        return True

    def put_object(self, fileobj: IO[AnyStr], **kwargs: Any) -> None:
        """Puts the given fileobj into the object store, associating it with this artifact."""

        # First annoying hack: `copyfileobj` doesn't handle mixed file modes well, so we need
        # to suss our our source's mode.
        if hasattr(fileobj, "mode"):
            if "b" in fileobj.mode:
                mode = "w+b"
            else:
                mode = "w+"
        elif isinstance(fileobj, io.StringIO):
            # Second annoying hack: the StringIO wrapper doesn't include a mode,
            # so we have to sniff its instance directly and specialize for it.
            mode = "w+"
        else:
            # If we don't have a mode attr, then we're probably dealing with a "file-like"
            # Response object or something similar. Treat these as binary-only for the time
            # being, which is almost certainly incorrect.
            mode = "w+b"

        with tempfile.TemporaryFile(mode=mode) as dst:
            shutil.copyfileobj(fileobj, dst)
            length = dst.tell()
            mate_assert(
                length != 0, f"artifact: given an empty fileobj to upload {self.uuid=} {self.kind=}"
            )

            dst.seek(0)

            # Third annoying hack: if we opened the `dst` tempfile in text mode above, we need
            # to grab its underlying binary buffer to put it into the object store.
            if hasattr(dst, "buffer"):
                real_dst = dst.buffer  # type: ignore[attr-defined]
            else:
                real_dst = dst

            storage.client.put_object("artifacts", self.uuid, real_dst, length, **kwargs)

    @contextmanager
    def get_object(self) -> Iterator[IO[bytes]]:
        """Yields the object associated with this artifact as a file-like object."""
        # NOTE(ww): For whatever reason, just yielding the response here doesn't work;
        # it fails silently and the response is empty. urllib3's HTTPResponse *claims*
        # to implement IO, so this is probably a bug on their side.
        try:
            response = storage.client.get_object("artifacts", self.uuid)
            dst = tempfile.TemporaryFile()
            shutil.copyfileobj(response, dst)
            dst.seek(0)
            yield dst
        finally:
            # Another probable (async) bug: this tempfile should be closed, but doing
            # so here causes a ChunkedEncodingError. Pain.
            # dst.close()
            response.close()
            # Needed? Which connection does this release? If it's the pooled one,
            # we probably don't want to release it here.
            # response.release_conn()

    def persist_locally(self, *, suffix: Optional[str] = None) -> pathlib.Path:
        """Create a local copy of the artifact and return it as a ``pathlib.Path``.

        The caller is responsible for disposing of the path. No cleanup is performed by default.
        """
        local_dir = pathlib.Path(tempfile.mkdtemp())
        local_file = local_dir / self.attributes["filename"]
        if suffix:
            local_file = local_file.with_suffix(suffix)

        with local_file.open("wb") as io:
            try:
                response = storage.client.get_object("artifacts", self.uuid)
                shutil.copyfileobj(response, io)
            finally:
                response.close()
        return local_file

    def to_info(self) -> ArtifactInformation:
        """Returns an ``ArtifactInformation`` model for this artifact."""
        return ArtifactInformation(
            artifact_id=self.uuid,
            kind=self.kind,
            has_object=self.has_object(),
            attributes=self.attributes,
            build_ids=[b.uuid for b in self.builds],
            compilation_ids=[c.uuid for c in self.compilations],
        )


class Compilation:
    __table__: Table = None

    # NOTE(ww): Give mypy a helping hand with these relationship properties.
    artifacts: List[Artifact]
    builds: List[Build]

    def __init__(
        self,
        uuid: str,
        state: CompilationState,
        source_artifact: Artifact,
        *,
        options: Dict[str, Any],  # TODO(ww): This should become CompileOptions.
    ) -> None:
        mate_assert(
            source_artifact.kind.is_compile_target(),
            f"API misuse: {source_artifact.kind=} is not a compilation target",
        )

        self.uuid = uuid
        self.state = state
        self.source_artifact = source_artifact
        self.options = options

    @classmethod
    def create(cls, source_artifact: Artifact, *, options: Dict[str, Any]) -> Compilation:
        return cls(
            uuid=uuid.uuid4().hex,
            state=CompilationState.Created,
            source_artifact=source_artifact,
            options=options,
        )

    def transition_to_state(self, new_state: CompilationState) -> None:
        mate_assert(
            self.state.can_transition_to(new_state),
            f"impossible compilation state transition: {self.state} -> {new_state}",
        )
        self.state = new_state

    @cached_property
    def challenge_id(self) -> Optional[str]:
        """Returns the challenge broker ID that corresponds to this compilation, if this compilation
        was created from a brokered challenge."""
        return self.source_artifact.attributes.get("challenge_id")

    def to_info(self) -> CompilationInformation:
        """Returns a ``CompilationInformation`` model for this compilation."""
        log_artifact = next(
            (a for a in self.artifacts if a.kind == ArtifactKind.CompileOutputCompileLog), None
        )

        return CompilationInformation(
            compilation_id=self.uuid,
            build_ids=[b.uuid for b in self.builds],
            state=self.state,
            source_artifact=self.source_artifact.to_info(),
            log_artifact=log_artifact.to_info() if log_artifact else None,
            artifact_ids=[a.uuid for a in self.artifacts],
            options=CompileOptions(**self.options),
        )


class Build:
    __table__: Table = None

    # NOTE(ww): Same as Compilation; help mypy out.
    artifacts: List[Artifact]
    analysis_tasks: List[AnalysisTask]
    mantiserve_tasks: List[MantiserveTask]

    def __init__(
        self,
        uuid: str,
        state: BuildState,
        bitcode_artifact: Artifact,
        compilation: Compilation,
        *,
        options: Dict[str, Any],  # TODO(ww): This should become BuildOptions.
        attributes: Dict[str, Any],
    ) -> None:
        mate_assert(
            bitcode_artifact.kind == ArtifactKind.CompileOutputBitcode,
            f"API misuse: {bitcode_artifact.kind=} != CompileOutputBitcode",
        )

        self.uuid = uuid
        self.state = state
        self.bitcode_artifact = bitcode_artifact
        self.compilation = compilation
        self.options = options
        self.attributes = attributes

    @classmethod
    def create(
        cls,
        bitcode_artifact: Artifact,
        compilation: Compilation,
        *,
        options: Dict[str, Any],
        attributes: Dict[str, Any] = {},
    ) -> Build:
        return cls(
            uuid=uuid.uuid4().hex,
            state=BuildState.Created,
            bitcode_artifact=bitcode_artifact,
            compilation=compilation,
            options=options,
            attributes=attributes,
        )

    def transition_to_state(self, new_state: BuildState) -> None:
        mate_assert(
            self.state.can_transition_to(new_state),
            f"impossible build state transition: {self.state} -> {new_state}",
        )
        self.state = new_state

    def to_info(self, artifact_detail: bool = False) -> BuildInformation:
        """Returns a ``BuildInformation`` model for this build.

        If ``artifact_detail`` is supplied, the resulting ``BuildInformation`` includes the
        ``ArtifactInformation`` for each artifact in the build.
        """
        return BuildInformation(
            build_id=self.uuid,
            compilation=self.compilation.to_info(),
            state=self.state,
            bitcode_artifact=self.bitcode_artifact.to_info(),
            artifact_ids=[a.uuid for a in self.artifacts],
            artifacts=([a.to_info() for a in self.artifacts] if artifact_detail else []),
            analysis_task_ids=[a.uuid for a in self.analysis_tasks],
            mantiserve_task_ids=[t.uuid for t in self.mantiserve_tasks],
            options=BuildOptions(**self.options),
            attributes=self.attributes,
        )


class CompilationArtifactAssociation:
    """A many-many association table for mapping artifacts to compilations and compilations to
    artifacts.

    An artifact can have many compilations, since multiple independent ``db.Compilation`s
    can be created (with different configurations) for one artifact.

    Each ``db.Compilation``, in turn, can have many ``db.Artifacts`` (in the form
    of compilation products and byproducts).
    """

    __table__: Table = None


class BuildArtifactAssociation:
    """A many-many association table for mapping artifacts to builds and builds to artifacts.

    An artifact can have many builds in one case: a compile target that's
    used to produce multiple builds.

    A build can have many artifacts in the normal case: each build is expected
    to produce compilation outputs and other artifacts that are associated with it.
    """

    __table__: Table = None


class MantiserveTask:
    """Mantiserve task info."""

    __table__: Table = None

    # NOTE(ekilmer): We declare a variable attribute here to help mypy.
    build: Build
    artifacts: List[Artifact]

    def __init__(
        self,
        uuid: str,
        build: Build,
        kind: MantiserveTaskKind,
        request_msg: Dict[str, Any],
        state: MantiserveTaskState,
        response_msg: Optional[Dict[str, Any]] = None,
        docker_image: Optional[str] = None,
        job_id: Optional[str] = None,
    ):
        """request_msg and response_msg are a json-encoded response message related to
        MantiserveTaskKind."""
        self.uuid = uuid
        self.build = build
        self.kind = kind
        self.request_msg = request_msg
        self.response_msg = response_msg
        self.state = state
        self.docker_image = docker_image
        self.job_id = job_id

    @classmethod
    def create(
        cls,
        build: Build,
        kind: MantiserveTaskKind,
        request_msg: Dict[str, Any],
        docker_image: Optional[str] = None,
    ) -> MantiserveTask:
        return MantiserveTask(
            uuid=uuid.uuid4().hex,
            build=build,
            kind=kind,
            request_msg=request_msg,
            response_msg=None,
            state=MantiserveTaskState.Created,
            docker_image=docker_image,
            job_id=None,
        )

    def transition_to_state(
        self, new_state: MantiserveTaskState, msg: Optional[str] = None
    ) -> None:
        """Transition to a different state with validity checking.

        :param new_state: Transition to this state
        :param msg: Optional log message to attach to ``self.response_msg``. If
            not present, does not touch ``self.response_msg``. Should only be used
            when transitioning to a `MantiserveTaskState.Failed` state.
        :return: None
        """
        mate_assert(
            self.state.can_transition_to(new_state),
            f"impossible mantiserve task state transition: {self.state} -> {new_state}",
        )
        if msg is not None:
            if self.response_msg is not None:
                logger.warning(
                    "Overwriting previous response message while transitioning state from "
                    f"'{self.state}' to '{new_state}':\n"
                    f"\tOriginal: {self.response_msg}\n"
                    f"\tNew: {msg}"
                )
            self.response_msg = {"log": msg}
        self.state = new_state

    def to_info(self) -> MantiserveTaskInformation:
        """Returns a ``MantiserveTaskInformation`` model for this Mantiserve task."""
        return MantiserveTaskInformation(
            task_id=self.uuid,
            build_id=self.build.uuid,
            artifact_ids=[a.uuid for a in self.artifacts],
            kind=self.kind,
            request=self.request_msg,
            result=self.response_msg,
            state=self.state,
            docker_image=self.docker_image,
        )


class MantiserveTaskArtifactAssociation:
    """Associate table of a MantiserveTask to many Artifacts."""

    __table__: Table = None


# =================================================================


class AnalysisTask:
    """Represents a concrete invocation of a POI analysis on a ``Build``."""

    __table__: Table = None

    build: Build
    poi_results: List[POIResult]

    def __init__(self, uuid: str, analysis_name: str, state: AnalysisTaskState, build: Build):
        self.uuid = uuid
        self.analysis_name = analysis_name
        self.state = state
        self.build = build

    @classmethod
    def create(cls, analysis_name: str, build: Build) -> AnalysisTask:
        return cls(
            uuid=uuid.uuid4().hex,
            analysis_name=analysis_name,
            state=AnalysisTaskState.Created,
            build=build,
        )

    def transition_to_state(self, new_state: AnalysisTaskState) -> None:
        mate_assert(
            self.state.can_transition_to(new_state),
            f"impossible analysis task state transition: {self.state} -> {new_state}",
        )
        self.state = new_state

    def to_info(self) -> AnalysisTaskInfo:
        """Returns an ``AnalysisTaskInfo`` model for this analysis task."""
        return AnalysisTaskInfo(
            analysis_task_id=self.uuid,
            analysis_name=self.analysis_name,
            build_id=self.build.uuid,
            poi_result_ids=[poi.uuid for poi in self.poi_results],
            state=self.state,
        )


class POIResult:
    """Represents a single POI result, produced by running a POI analysis through an
    ``AnalysisTask``."""

    __table__: Table = None

    analysis_task: AnalysisTask
    parent: Optional[POIResult]
    children: List[POIResult]
    snapshots: List[FlowFinderSnapshot]

    def __init__(
        self,
        uuid: str,
        poi: Dict[str, Any],
        analysis_task: AnalysisTask,
        graph_requests: GraphRequests,
        flagged: bool = False,
        done: bool = False,
        complexity: POIResultComplexity = POIResultComplexity.Unknown,
    ) -> None:
        self.uuid = uuid
        self.poi = poi
        self.analysis_task = analysis_task
        self.graph_requests = graph_requests
        self.flagged = flagged
        self.done = done
        self.complexity = complexity

    @classmethod
    def create(
        cls,
        poi: Dict[str, Any],
        analysis_task: AnalysisTask,
        graph_requests: List[Dict[str, Any]],
        complexity: POIResultComplexity = POIResultComplexity.Unknown,
    ) -> POIResult:
        return cls(
            uuid=uuid.uuid4().hex,
            poi=poi,
            analysis_task=analysis_task,
            graph_requests=graph_requests,
            complexity=complexity,
        )

    def to_info(self) -> POIResultInfo:
        """Returns a ``POIResultInfo`` model for this POI result."""
        return POIResultInfo(
            poi_result_id=self.uuid,
            build_id=self.analysis_task.build.uuid,
            analysis_task_id=self.analysis_task.uuid,
            analysis_name=self.analysis_task.analysis_name,
            poi=self.poi,
            flagged=self.flagged,
            done=self.done,
            complexity=self.complexity,
            parent_result_id=self.parent.uuid if self.parent else None,
            child_result_ids=[c.uuid for c in self.children],
            snapshot_ids=[s.uuid for s in self.snapshots],
            graph_requests=self.graph_requests,
            insight=self.poi["insight"],
            background=Analysis.by_name(self.analysis_task.analysis_name).background(),
            salient_functions=self.poi.pop("salient_functions"),
        )


class FlowFinderSnapshot:
    """Represents the state of a user's analysis of a ``POIResult``."""

    __table__: Table = None

    poi_result: Optional[POIResult]
    build: Build

    def __init__(
        self,
        *,
        uuid: str,
        poi_result: Optional[POIResult],
        build: Build,
        label: str,
        filters: List[str],
        graph_requests: GraphRequests,
        hidden_graph_ids: List[str],
        hidden_node_ids: List[str],
        user_annotations: Dict[str, FlowFinderAnnotations],
    ) -> None:
        if poi_result is not None:
            mate_assert(
                poi_result.analysis_task.build.uuid == build.uuid,
                "invariant: POI result and build must match",
            )

        self.uuid = uuid
        self.poi_result = poi_result
        self.build = build
        self.label = label
        self.filters = filters
        self.graph_requests = jsonable_encoder(graph_requests)
        self.hidden_graph_ids = hidden_graph_ids
        self.hidden_node_ids = hidden_node_ids
        self.user_annotations = user_annotations

    @classmethod
    def create(
        cls,
        *,
        poi_result: Optional[POIResult],
        build: Build,
        label: str,
        filters: List[str] = [],
        graph_requests: GraphRequests = [],
        hidden_graph_ids: List[str] = [],
        hidden_node_ids: List[str] = [],
        user_annotations: Dict[str, FlowFinderAnnotations] = {},
    ) -> FlowFinderSnapshot:
        return cls(
            uuid=uuid.uuid4().hex,
            poi_result=poi_result,
            build=build,
            label=label,
            filters=filters,
            graph_requests=graph_requests,
            hidden_graph_ids=hidden_graph_ids,
            hidden_node_ids=hidden_node_ids,
            user_annotations=user_annotations,
        )

    def to_info(self) -> FlowFinderSnapshotInfo:
        """Returns a ``FlowFinderSnapshotInfo`` model for this snapshot."""
        return FlowFinderSnapshotInfo(
            snapshot_id=self.uuid,
            poi_result_id=self.poi_result.uuid if self.poi_result else None,
            build_id=self.build.uuid,
            label=self.label,
            filters=self.filters,
            graph_requests=self.graph_requests,
            hidden_graph_ids=self.hidden_graph_ids,
            hidden_node_ids=self.hidden_node_ids,
            user_annotations=self.user_annotations,
        )


# =================================================================


@lru_cache(maxsize=None)
def build_model_classes(build: str) -> Tuple[Type[BaseNode], Type[BaseEdge]]:
    class Node(Model, BaseNode):

        __tablename__ = f"base_nodes_{build}"
        build_id = build

        def __init__(self, uuid: str, kind: str, attributes: Dict[Any, Any]) -> None:
            self.uuid = uuid
            self.kind = kind
            self.attributes = attributes

    Node.__table__.create(_engine, checkfirst=True)
    NodeClass = Node

    class Edge(Model, BaseEdge):

        __tablename__ = f"base_edges_{build}"

        Node = NodeClass  # type: ignore[assignment]
        build_id = build

        def __init__(
            self,
            uuid: str,
            kind: str,
            source: str,
            target: str,
            attributes: Dict[Any, Any],
        ) -> None:
            super().__init__()  # type: ignore[call-arg]

            self.uuid = uuid
            self.kind = kind
            self.source = source
            self.target = target
            self.attributes = attributes

    Edge.__table__.create(_engine, checkfirst=True)
    EdgeClass = Edge

    return NodeClass, EdgeClass


# =================================================================


class CreateView(DDLElement):
    def __init__(self, name: str, selectable: FromClause) -> None:
        self.name = name
        self.selectable = selectable


@compiler.compiles(CreateView)
def emit_view(element: Any, compiler: Any, **_kw: Dict[str, Any]) -> str:
    return "CREATE OR REPLACE VIEW %s AS %s" % (
        element.name,
        compiler.sql_compiler.process(element.selectable, literal_binds=True),
    )


# =================================================================

# AdvisoryLockBuildTransaction takes a Postgres advisory lock for the
# current transaction until it is commited or aborted.
# AdvisoryLockBuildTransaction may use the same lock id for two
# different UUIDs, since the space of possible UUIDs is larger than
# the space of possible lock IDs. As a result, it should not be used
# to guard operations that require synchronized access to more than
# one UUID at a time.
class AdvisoryLockBuildTransaction(DDLElement):
    def __init__(self, build: str) -> None:
        self.build = build


@compiler.compiles(AdvisoryLockBuildTransaction)
def emit_lock(element: Any, _compiler: Any, **_kw: Dict[str, Any]) -> str:
    # convert build uuid to BIGINT key
    # Note: only uses partial uuid.
    lockid = int.from_bytes(
        int(element.build[0:16], 16).to_bytes(length=8, byteorder=sys.byteorder),
        byteorder=sys.byteorder,
        signed=True,
    )
    return f"SELECT pg_advisory_xact_lock({lockid})"


# =================================================================


def new_session() -> orm.Session:
    if _Session is None:
        raise UninitializedDatabaseError()
    return _Session()


@contextmanager
def session_scope() -> Iterator[orm.Session]:
    if _Session is None:
        raise UninitializedDatabaseError()
    session = _Session()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def initialize(connection_string: str, echo: bool = False, create: bool = False) -> None:
    global _connection_string, _engine, _metadata, _Session

    if _connection_string is not None:
        logger.error(
            f"MATE has already been initialized with a connection string {_connection_string}. "
            "Skipping reinitialization."
        )
        return

    _connection_string = connection_string
    _engine = create_engine(
        connection_string,
        echo=echo,
        pool_pre_ping=True,
        connect_args={
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        },
        executemany_mode="batch",
        # NOTE(ww): Don't place any limits on connections at the SQLAlchemy level.
        # Why not? Because SQLAlchemy's pooling strategies are a *little* too
        # clever for our use case: by default it will accept N connections in
        # the pool, complemented by M "overflow" connections when those N
        # connections are all active. When that M threshold is crossed, it
        # begins rejecting connections. This is normally desirable, but MATE's
        # access patterns can include dozens of long-running connections when
        # the system is under heavy load (e.g., multiple simultaneous CPG builds).
        # We don't want in-progress builds to cause knock-on failures, so we
        # tell SQLAlchemy to create as many "overflow" connections as the
        # underlying database will tolerate.
        # See: https://gitlab-ext.galois.com/mate/MATE/-/merge_requests/1573
        max_overflow=-1,
    )
    _Session = sessionmaker(bind=_engine, class_=Session)

    Artifact.__table__ = _make_artifact_table("artifacts")
    mapper(
        Artifact,
        Artifact.__table__,
        properties={
            "compilations": relationship(
                Compilation,
                secondary=lambda: CompilationArtifactAssociation.__table__,
                back_populates="artifacts",
            ),
            "builds": relationship(
                Build,
                secondary=lambda: BuildArtifactAssociation.__table__,
                back_populates="artifacts",
            ),
        },
    )

    Compilation.__table__ = _make_compilation_table("compilations")
    mapper(
        Compilation,
        Compilation.__table__,
        properties={
            "source_artifact": relationship(Artifact),
            "artifacts": relationship(
                Artifact,
                secondary=lambda: CompilationArtifactAssociation.__table__,
                back_populates="compilations",
            ),
            "builds": relationship(
                Build,
                backref="compilation",
            ),
        },
    )

    Build.__table__ = _make_build_table("builds")
    mapper(
        Build,
        Build.__table__,
        properties={
            "bitcode_artifact": relationship(Artifact),
            "artifacts": relationship(
                Artifact,
                secondary=lambda: BuildArtifactAssociation.__table__,
                back_populates="builds",
            ),
            "mantiserve_tasks": relationship(MantiserveTask, backref="build"),
            "snapshots": relationship(FlowFinderSnapshot, backref="build"),
        },
    )

    CompilationArtifactAssociation.__table__ = _make_compilation_artifact_association_table(
        "compilation_artifact_association"
    )
    mapper(CompilationArtifactAssociation, CompilationArtifactAssociation.__table__)

    BuildArtifactAssociation.__table__ = _make_build_artifact_association_table(
        "build_artifact_association"
    )
    mapper(BuildArtifactAssociation, BuildArtifactAssociation.__table__)

    AnalysisTask.__table__ = _make_analysis_task_table("analysis_tasks")
    mapper(
        AnalysisTask,
        AnalysisTask.__table__,
        properties={
            "build": relationship(Build, backref="analysis_tasks"),
        },
    )

    POIResult.__table__ = _make_poi_results_table("poi_results")
    mapper(
        POIResult,
        POIResult.__table__,
        properties={
            "analysis_task": relationship(
                AnalysisTask,
                backref="poi_results",
            ),
            "parent": relationship(
                POIResult, backref="children", remote_side=lambda: POIResult.uuid
            ),
            "snapshots": relationship(FlowFinderSnapshot, backref="poi_result"),
        },
    )

    FlowFinderSnapshot.__table__ = _make_flowfinder_snapshots_table("flowfinder_snapshots")
    mapper(
        FlowFinderSnapshot,
        FlowFinderSnapshot.__table__,
    )

    MantiserveTask.__table__ = _make_mantiserve_table("mantiserve_task")
    mapper(
        MantiserveTask,
        MantiserveTask.__table__,
        properties={
            "artifacts": relationship(
                Artifact,
                secondary=lambda: MantiserveTaskArtifactAssociation.__table__,
                backref="mantiserve_task",
            ),
        },
    )
    MantiserveTaskArtifactAssociation.__table__ = _make_mantiserve_task_artifact_association_table(
        "mantiserve_task_artifact_association"
    )
    mapper(MantiserveTaskArtifactAssociation, MantiserveTaskArtifactAssociation.__table__)

    if not create:
        return

    # NOTE(ww): SQLAlchemy's `create_all` is idempotent by default,
    # and shouldn't fail under normal circumstances (even if the tables
    # already exist). However, it *can* fail on a race condition
    # where two services are attempting to create the same tables at
    # exactly the same time. At least one of those services should succeed
    # and not raise during creation, so we turn it into a warning here.
    # See: https://gitlab-ext.galois.com/mate/MATE/-/issues/1181
    try:
        _metadata.create_all(bind=_engine)
    except Exception as e:
        logger.warning(f"table creation failed: {e}")


def _make_artifact_table(name: str) -> Table:
    return Table(
        name,
        _metadata,
        uuid_column(),
        enum_column("kind", ArtifactKind),
        Column("attributes", MutableDict.as_mutable(JSONB), nullable=False),
    )


def _make_compilation_artifact_association_table(name: str) -> Table:
    return Table(
        name,
        _metadata,
        Column(
            "compilation_uuid",
            String,
            ForeignKey("compilations.uuid"),
            primary_key=True,
            nullable=False,
        ),
        Column(
            "artifact_uuid", String, ForeignKey("artifacts.uuid"), primary_key=True, nullable=False
        ),
    )


def _make_build_artifact_association_table(name: str) -> Table:
    return Table(
        name,
        _metadata,
        Column("build_uuid", String, ForeignKey("builds.uuid"), primary_key=True, nullable=False),
        Column(
            "artifact_uuid", String, ForeignKey("artifacts.uuid"), primary_key=True, nullable=False
        ),
    )


def _make_compilation_table(name: str) -> Table:
    return Table(
        name,
        _metadata,
        uuid_column(),
        enum_column("state", CompilationState),
        Column("source_artifact_uuid", String, ForeignKey("artifacts.uuid"), nullable=False),
        Column("options", JSONB, nullable=False),
    )


def _make_build_table(name: str) -> Table:
    return Table(
        name,
        _metadata,
        uuid_column(),
        enum_column("state", BuildState),
        Column("bitcode_artifact_uuid", String, ForeignKey("artifacts.uuid"), nullable=False),
        Column("compilation_uuid", String, ForeignKey("compilations.uuid"), nullable=False),
        Column("options", JSONB, nullable=False),
        Column("attributes", MutableDict.as_mutable(JSONB), nullable=False),
    )


def _make_analysis_task_table(name: str) -> Table:
    return Table(
        name,
        _metadata,
        uuid_column(),
        Column("analysis_name", String, nullable=False),
        enum_column("state", AnalysisTaskState),
        Column("build_uuid", String, ForeignKey("builds.uuid"), nullable=False),
    )


def _make_poi_results_table(name: str) -> Table:
    return Table(
        name,
        _metadata,
        uuid_column(),
        Column("poi", JSONB, nullable=False),
        Column("analysis_task_uuid", String, ForeignKey("analysis_tasks.uuid"), nullable=False),
        Column("graph_requests", JSONB, nullable=False),
        Column("flagged", Boolean, nullable=False),
        Column("done", Boolean, nullable=False),
        Column("parent_uuid", String, ForeignKey("poi_results.uuid"), nullable=True),
        enum_column("complexity", POIResultComplexity),
    )


def _make_flowfinder_snapshots_table(name: str) -> Table:
    return Table(
        name,
        _metadata,
        uuid_column(),
        Column("poi_result_uuid", String, ForeignKey("poi_results.uuid"), nullable=True),
        Column("build_id", String, ForeignKey("builds.uuid"), nullable=True),
        Column("label", String, nullable=False, unique=False),
        Column("filters", MutableList.as_mutable(JSONB), nullable=False),
        Column("graph_requests", MutableList.as_mutable(JSONB), nullable=False),
        Column("hidden_graph_ids", MutableList.as_mutable(JSONB), nullable=False),
        Column("hidden_node_ids", MutableList.as_mutable(JSONB), nullable=False),
        Column("user_annotations", MutableDict.as_mutable(JSONB), nullable=False),
    )


def _make_mantiserve_table(name: str) -> Table:
    return Table(
        name,
        _metadata,
        uuid_column(),
        Column("build_uuid", String, ForeignKey("builds.uuid"), nullable=False),
        enum_column("kind", MantiserveTaskKind),
        Column("request_msg", JSONB, nullable=False),
        Column("response_msg", MutableDict.as_mutable(JSONB), nullable=True),
        enum_column("state", MantiserveTaskState),
        Column("docker_image", String, nullable=True),
        Column("job_id", String, nullable=True),
    )


def _make_mantiserve_task_artifact_association_table(name: str) -> Table:
    return Table(
        name,
        _metadata,
        Column(
            "mantiserve_task_uuid",
            String,
            ForeignKey("mantiserve_task.uuid"),
            primary_key=True,
            nullable=False,
        ),
        Column(
            "artifact_uuid",
            String,
            ForeignKey("artifacts.uuid"),
            primary_key=True,
            nullable=False,
            unique=True,
        ),
    )


# =================================================================


class Graph(BaseCPG):
    def __init__(
        self,
        parent: Optional[Graph],
        name: str,
        build: str,
        selectables: Optional[Tuple[FromClause, FromClause]],
        session: Session,
    ) -> None:
        """Initialize a graph, setting internal state for use as a context manager.

        This constructor should generally not be called directly; instead, users should call one of
        the named classmethod constructors.
        """
        self.name = name
        self.parent = parent
        self.build = build
        self.session = session

        session.execute(AdvisoryLockBuildTransaction(build))
        if parent is None:
            self.BaseNode, self.BaseEdge = build_model_classes(build)
            session.commit()
            self.node_selectable = self.BaseNode.__table__.select()
            self.edge_selectable = self.BaseEdge.__table__.select()
        else:
            self.BaseNode = self.parent.BaseNode  # type: ignore[union-attr]
            self.BaseEdge = self.parent.BaseEdge  # type: ignore[union-attr]
            self.node_selectable, self.edge_selectable = selectables  # type: ignore[misc]

        node_table_name = f"nodes_{name}"
        edge_table_name = f"edges_{name}"

        self.session.bind.execute(CreateView(node_table_name, self.node_selectable))
        self.session.bind.execute(CreateView(edge_table_name, self.edge_selectable))
        session.commit()

        # NOTE(lb) These don't inherit from Node, Edge directly because you
        # can't inherit from something with a different __tablename__
        self.Node = type(
            f"Node{self.name}",
            (Model, BaseNode),
            {"cpg": self, "build_id": build, "__tablename__": node_table_name},
        )
        self.Edge = type(
            f"Edge{self.name}",
            (Model, BaseEdge),
            {"cpg": self, "build_id": build, "Node": self.Node, "__tablename__": edge_table_name},
        )

        self._attach_node_models(self.name)

    @classmethod
    def from_build(cls, build: Build, session: Session) -> Graph:
        """Create a graph consisting of all nodes/edges from an existing build."""
        return cls(
            None,
            uuid.uuid4().hex,
            build.uuid,
            None,
            session,
        )

    def subgraph(self, builder: SubgraphBuilder) -> Graph:
        """Run the given SubgraphBuilder on the current graph."""
        return builder.build(self)

    def paths(self, builder: PathBuilder) -> Type[Path]:
        """Run the given PathBuilder on the current graph."""
        return builder.build(self)

    @cached_property
    def cfg(self) -> Graph:
        """Construct the control-flow subgraph of the current graph."""
        return self.subgraph(SubgraphBuilder().with_edge_kinds(*LOCAL_CONTROL_FLOW_FORWARD))

    @cached_property
    def icfg(self) -> Graph:
        """Construct the interprocedural control-flow subgraph of the current graph."""
        return self.subgraph(SubgraphBuilder().with_edge_kinds(*CONTROL_FLOW_FORWARD))

    @cached_property
    def cg(self) -> Graph:
        """Construct the call-subgraph of the current graph."""
        return self.subgraph(
            SubgraphBuilder().with_node_kinds(NodeKind.FUNCTION).with_edge_kinds(EdgeKind.CALLGRAPH)
        )

    @cached_property
    def ast(self) -> Graph:
        """Construct the abstract sytnax tree subgraph of the current graph."""
        return self.subgraph(SubgraphBuilder().with_edge_kinds(*AST_EDGES))

    @cached_property
    def dfg(self) -> Graph:
        """Construct the data-flow subgraph of the current graph."""
        return self.subgraph(SubgraphBuilder().with_edge_kinds(*DATA_FLOW_FORWARD))

    @cached_property
    def ifg(self) -> Graph:
        """Construct the information-flow subgraph of the current graph."""
        return self.subgraph(SubgraphBuilder().with_edge_kinds(*INFO_FLOW_FORWARD))

    @cached_property
    def cdg(self) -> Graph:
        """Construct the control-dependence subgraph of the current graph."""
        return self.subgraph(SubgraphBuilder().with_edge_kinds(*CONTROL_DEP_FORWARD))

    @cached_property
    def ptg(self) -> Graph:
        """Construct the points-to subgraph of the current graph."""
        return self.subgraph(SubgraphBuilder().with_edge_kinds(*POINTS_TO))


class SubgraphBuilder:
    """A builder class for subgraphs."""

    def __init__(self) -> None:
        self.node_kinds: Set[NodeKind] = set()
        self.edge_kinds: Set[EdgeKind] = set()

    def with_node_kinds(self, *kinds: NodeKind) -> SubgraphBuilder:
        """Specify a set of node kinds to be included within the subgraph."""
        self.node_kinds |= set(kinds)
        return self

    def with_edge_kinds(self, *kinds: EdgeKind) -> SubgraphBuilder:
        """Specify a set of edge kinds to be included within the subgraph."""
        self.edge_kinds |= set(kinds)
        return self

    def build(self, graph: Graph) -> Graph:
        """Concretize the subgraph defined by this builder, with respect to the given graph."""
        self.session = graph.session

        node_alias = graph.node_selectable.alias()
        edge_alias = graph.edge_selectable.alias()

        subgraph_node_selectable = node_alias.select(
            (node_alias.c.kind.in_([kind.value for kind in self.node_kinds]))
            if self.node_kinds != set()
            else true()
        ).alias()

        subgraph_edge_selectable = edge_alias.select(
            (
                (edge_alias.c.kind.in_([kind.value for kind in self.edge_kinds]))
                if self.edge_kinds != set()
                else true()
            )
            & edge_alias.c.source.in_(select([subgraph_node_selectable.c.uuid]))
            & edge_alias.c.target.in_(select([subgraph_node_selectable.c.uuid]))
        )

        return Graph(
            graph,
            uuid.uuid4().hex,
            graph.build,
            (subgraph_node_selectable, subgraph_edge_selectable),
            graph.session,
        )


@dataclass
class Path:
    """For documentation of this class's attributes, see comments in ``_make_path_table`` or use
    ``help`` at runtime."""

    __table__ = None

    info: Any
    source: Any
    source_stack: Tuple[Any, ...]
    target: Any
    edge: Any
    trace: Tuple[Any, ...]
    state: Any
    stack: Tuple[Any, ...]
    stack_top: Any
    c: Any
    edge_symbol_table: Optional[Table] = None
    transition_table: Optional[Table] = None
    is_reversed: ClassVar[bool] = False
    stepped_over_functions: ClassVar[set[str]] = field(default_factory=set)
    cfl: ClassVar[bool] = False

    @classmethod
    def populate_transition_table(cls, graph: Graph) -> None:
        raise NotImplementedError

    @classmethod
    def populate_edge_symbol_table(cls, graph: Graph) -> None:
        raise NotImplementedError

    @classmethod
    def initial_state(cls) -> Null:
        return null()

    @classmethod
    def initial_stack(cls) -> Null:
        return null()


def _make_path_table(name: str, node_table: Table, edge_table: Table) -> Table:
    info_comment = "User-defined distinguisher for this path if provided (an extra piece of data that can then be consulted e.g. in a continuing_while predicate)"
    source_comment = "The source node of this path (if reversed or keep_start=True)"
    source_stack_comment = "The stack this path was initialized in (if keep_start=True)"
    target_comment = "The target node of this path (if not reversed or keep_start=True)"
    trace_comment = "The trace of edges visited by this path (if keep_trace=True)"
    state_comment = "The current PDA state of this path (if CFL query)"
    stack_comment = "The current PDA stack of this path (if CFL query)"
    stack_top_comment = "The top of the current PDA stack of this path (if CFL query)"
    edge_comment = "The last visited edge of this path (if keep_edge=True)"
    return Table(
        name,
        _metadata,
        Column(
            "info",
            String,
            primary_key=True,
            nullable=True,
            index=True,
            doc=info_comment,
            comment=info_comment,
        ),
        Column("source", String, primary_key=True, doc=source_comment, comment=source_comment),
        Column(
            "source_stack",
            ARRAY(String, as_tuple=True),
            primary_key=True,
            doc=source_stack_comment,
            comment=source_stack_comment,
        ),
        Column(
            "target",
            String,
            primary_key=True,
            index=True,
            doc=target_comment,
            comment=target_comment,
        ),
        Column(
            "trace",
            ARRAY(String, as_tuple=True),
            primary_key=True,
            doc=trace_comment,
            comment=trace_comment,
        ),
        Column(
            "state", String, primary_key=True, index=True, doc=state_comment, comment=state_comment
        ),
        Column(
            "stack",
            ARRAY(String, as_tuple=True),
            primary_key=True,
            index=True,
            doc=stack_comment,
            comment=stack_comment,
        ),
        Column(
            "stack_top",
            String,
            primary_key=True,
            index=True,
            doc=stack_top_comment,
            comment=stack_top_comment,
        ),
        Column(
            "edge",
            String,
            primary_key=True,
            nullable=True,
            index=True,
            doc=edge_comment,
            comment=edge_comment,
        ),
        ForeignKeyConstraint(["source"], [node_table.c.uuid]),
        ForeignKeyConstraint(["target"], [node_table.c.uuid]),
        ForeignKeyConstraint(["edge"], [edge_table.c.uuid]),
    )


# HACK: Force postgres to run joins in order written
#
# This was previously necessary for ensuring that the PDA transitions
# join on the transition table, *then* the edge table, see also PathBuilder.
@contextmanager
def join_collapse_limit(session: orm.Session) -> Iterator[None]:
    session.execute("SET join_collapse_limit=1")
    try:
        yield
    finally:
        session.execute("RESET join_collapse_limit")


def set_n_distinct(
    session: orm.Session, tablename: str, columns: Set[str], n_distinct: int
) -> None:
    to_update = set()
    for column in columns:
        needs_update = (
            f"SELECT 1 FROM pg_stats WHERE tablename = '{tablename}' AND"
            f" attname = '{column}' AND n_distinct = {n_distinct}::int"
        )
        if session.execute(text(needs_update)).first() is None:
            logger.debug(f"{tablename}.{column} n_distinct requires update")
            to_update.add(column)
        else:
            logger.debug(f"{tablename}.{column} n_distinct does not require update")

    for column in to_update:
        logger.debug(f"{tablename}.{column} (n_distinct={n_distinct})")
        alter_cmd = f"ALTER TABLE {tablename} ALTER COLUMN {column} SET (n_distinct={n_distinct})"
        logger.debug(alter_cmd)
        session.execute(text(alter_cmd))

    if len(to_update) > 0:
        # session.commit()
        analyze_cmd = f"ANALYZE {tablename}"
        logger.debug(analyze_cmd)
        session.execute(text(analyze_cmd))
        logger.debug(f"n_distinct statistics for {tablename} ({', '.join(to_update)}) updated")
    else:
        logger.debug(f"n_distinct statistics for {tablename} did not require update")


PB = TypeVar("PB", bound="PathBuilder")

# Bottom of the PDA stack, see PathBuilder

BOT: Final[str] = "$"


class PathBuilder:
    """A builder class for enumerating paths in a graph.

    PathBuilder supports "CFL-reachability queries" (CFL stands for
    "context-free language"). These queries have two parts:

    1. In a pre-processing step, each edge in the graph is labeled with some
       symbol (string).
    2. The graph is explored one path at a time by a push-down automaton (PDA)
       that reads the edge labels and recognizes strings in a context-free
       grammar.

    These queries return the set of all paths in the graph (that start at some
    set of nodes) where the edge labels on that path form a string in the
    context-free language recognized by the PDA.

    For example the "balanced parentheses" context-free language can be used to
    encode the problem of finding control-flow graph (CFG) paths that have a
    balanced number of calls and returns.

    Step (2) above can be accomplished by any number of specialized algorithms,
    but the PDA approach is relatively simple and it's the only one MATE has so
    far.

    The state of the PDA and its set of transitions are kept in a dedicated
    database tables, see ``_make_path_table`` and ``_make_transition_table``
    respectively, and the comments on their columns especially.

    To perform a transition, the PDA state table is first joined against its
    transition table, and then joined against the edge symbol table. This join
    order is more performant than vice-versa, because the edge table is
    typically way bigger. At each step, the automation can make multiple
    transitions (end up in multiple new states).

    Because the PDA state is kept in a table, and a table is like a set of
    tuples (configurations), we get some cycle-avoidance for free. However,
    this can get more complicated if the stack or trace is kept as part of the
    PDA configuration/state, because while these are theoretically bounded in
    practice they can be too big. See the ``exploration_bound`` parameter to
    ``build``.
    """

    def __init__(self, PathBase: Type[Path] = Path):
        self.PathBase = PathBase
        self.start_predicates: List[Callable[[Type[Node]], ColumnElement]] = []
        self.stop_predicates: List[Callable[[Type[Node]], ColumnElement]] = []
        self.continue_predicates: List[Callable[[Type[Path], Type[Edge]], ColumnElement]] = []
        self.no_detail_continue_predicates: List[
            Callable[[Type[Path], Type[Edge]], ColumnElement]
        ] = []
        self.stepped_over_functions: Set[str] = set()
        self.max_length: int = 0
        self.is_reversed = False
        self.start_configuration: Optional[CTE] = None

    def starting_at(self: PB, *start_predicates: Callable[[Type[Node]], ColumnElement]) -> PB:
        """Set a predicate on nodes which starts the traversal.

        This method takes as argument a callable, which is provided with a Node object of the
        underlying graph during build, and must return a valid where-clause-compatible expression.
        """
        self.start_predicates.extend(start_predicates)
        return self

    def stopping_at(self: PB, *stop_predicates: Callable[[Type[Node]], ColumnElement]) -> PB:
        """Set a predicate on nodes which stops the traversal.

        This method takes as argument a callable, which is provided with a Node object of the
        underlying graph during build, and must return a valid where-clause-compatible expression.
        """
        self.stop_predicates.extend(stop_predicates)
        return self

    def continuing_while(
        self: PB,
        *continue_predicates: Callable[[Type[Path], Type[Edge]], ColumnElement],
        edge_detail: bool = True,
    ) -> PB:
        """Set a predicate on configurations and edges which must be satisfied by all edges on a
        valid traversal.

        This method takes as argument a callable, which is provided with a Path object of the
        PathBuilder's current configuration and an edge object of the underlying graph during build,
        and must return a valid where-clause-compatible expression.

        The optional argument edge_detail specifies whether the predicate inspects properties of the
        edge other than its source, target, or UUID
        """
        if edge_detail:
            self.continue_predicates.extend(continue_predicates)
        else:
            self.no_detail_continue_predicates.extend(continue_predicates)
        return self

    def stepping_over(self: PB, *stepped_over_functions: str) -> PB:
        """Specify a set of functions to step over during control-flow traversal."""
        self.stepped_over_functions |= set(stepped_over_functions)
        return self

    def initial_configuration(self: PB, cte: CTE) -> PB:
        """Provide an initial set of configurations (node, stack, and info) at which to start the
        traversal.

        This method takes as argument a SQLAlchemy common table expression, which must have columns
        "uuid", "stack", and "info" containing the UUID of the start node, the starting stack, and
        an information string (which may be null), respectively.
        """
        self.start_configuration = cte
        return self

    @staticmethod
    def build_conjoined_predicate(predicates: List[Callable]) -> Optional[Callable]:
        if len(predicates) == 0:
            return None
        elif len(predicates) == 1:
            return predicates[0]
        else:

            def conjoined_predicate(*pivot: Any) -> Any:
                nonlocal predicates
                conjunction = predicates[0](*pivot)
                for predicate in predicates[1:]:
                    conjunction &= predicate(*pivot)
                return conjunction

            return conjoined_predicate

    def limited_to(self: PB, max_length: int) -> PB:
        """Limit the maximum length of the traversal."""

        mate_assert(max_length >= 0)
        self.max_length = max_length
        return self

    def reverse(self: PB) -> PB:
        """Reverse the direction of traversal.

        This causes the traversal to be jump from target -> source rather than from source -> target; edge IDs in any resulting trace must be interpreted as such.

        Repeated reversals will undo each other.
        """
        self.is_reversed = not self.is_reversed
        return self

    # NOTE: The parameters to this function are also mentioned in the
    # documentation in _make_path_table, so updates here should be reflected
    # there.
    #
    # TODO(#1462): All of these bools should default to False.
    def build(
        self,
        graph: Graph,
        *,
        keep_start: bool = True,
        keep_trace: bool = False,
        keep_edge: bool = False,
        exploration_bound: int = MATE_DEFAULT_EXPLORATION_BOUND,
    ) -> Type[Path]:
        """Concretize the path set defined by this builder, with respect to the given graph.

        :param keep_start: record the starting node for each path
        :param keep_trace: record the sequence of edges visited by the path
        :param keep_edge: record the last edge visited by the path
        :param exploration_bound: the maximum number of path configurations
          to visit during exploration (not a bound on path length)

        All of the ``keep_*`` options have some performance cost if enabled.
        ``keep_trace`` is especially expensive.

        Returns a new Path class, mapped to the view represeting the path set.
        """
        name = uuid.uuid4().hex
        path_table = _make_path_table(f"paths_{name}", graph.Node.__table__, graph.Edge.__table__)

        path_class: Type[Path] = type(
            f"Path_{name}",
            (self.PathBase,),
            {
                "__table__": path_table,
                "stepped_over_functions": self.stepped_over_functions,
                "is_reversed": self.is_reversed,
            },
        )
        mapper(path_class, path_table)

        if self.PathBase.cfl:
            path_class.populate_transition_table(graph)
            path_class.populate_edge_symbol_table(graph)
            assert path_class.transition_table is not None
            assert path_class.edge_symbol_table is not None

        start_predicate = self.build_conjoined_predicate(self.start_predicates)
        stop_predicate = self.build_conjoined_predicate(self.stop_predicates)
        continue_predicate = self.build_conjoined_predicate(self.continue_predicates)
        no_detail_continue_predicate = self.build_conjoined_predicate(
            self.no_detail_continue_predicates
        )

        start_predicate = (lambda _Node: true()) if start_predicate is None else start_predicate
        stop_predicate = (lambda _Node: true()) if stop_predicate is None else stop_predicate
        no_detail_continue_predicate = (
            (lambda _Config, _Edge: true())
            if no_detail_continue_predicate is None
            else no_detail_continue_predicate
        )

        # Project out the appropriate set of columns from the base join, and add
        # on the trace column with the initial edge.
        if self.start_configuration is None:
            base_step = (
                select(
                    [
                        null().label("info"),
                        graph.Node.uuid.label("source")
                        if (keep_start or self.is_reversed)
                        else null().cast(String).label("source"),
                        path_class.initial_stack().label("source_stack")
                        if keep_start and self.PathBase.cfl
                        else null().label("source_stack"),
                        graph.Node.uuid.label("target")
                        if (keep_start or not self.is_reversed)
                        else null().cast(String).label("target"),
                        array([]).cast(ARRAY(String)).label("trace"),
                        path_class.initial_state().label("state"),
                        path_class.initial_stack().label("stack"),
                        Grouping(path_class.initial_stack().cast(ARRAY(String)))[1].label(
                            "stack_top"
                        ),
                        null().cast(String).label("edge"),
                    ]
                )
                .select_from(graph.Node)
                .where(
                    start_predicate(graph.Node)
                    if not self.is_reversed
                    else stop_predicate(graph.Node)
                )
                .cte(recursive=True, name="base_select")
            )
        else:
            base_step = (
                select(
                    [
                        self.start_configuration.c.info.label("info"),
                        graph.Node.uuid.label("source")
                        if (keep_start or self.is_reversed)
                        else null().cast(String).label("source"),
                        self.start_configuration.c.stack.label("source_stack")
                        if keep_start and self.PathBase.cfl
                        else null().label("source_stack"),
                        graph.Node.uuid.label("target")
                        if (keep_start or not self.is_reversed)
                        else null().cast(String).label("target"),
                        array([]).cast(ARRAY(String)).label("trace"),
                        path_class.initial_state().label("state"),
                        self.start_configuration.c.stack.label("stack"),
                        Grouping(self.start_configuration.c.stack)[1].label("stack_top"),
                        null().cast(String).label("edge"),
                    ]
                )
                .select_from(
                    join(
                        graph.Node,
                        self.start_configuration,
                        (graph.Node.uuid == self.start_configuration.c.uuid),
                    )
                )
                .where(
                    start_predicate(graph.Node)
                    if not self.is_reversed
                    else stop_predicate(graph.Node)
                )
                .cte(recursive=True, name="base_select")
            )

        if self.max_length == 0:
            logger.warn("Building paths with unbounded maximum length.")
            max_length_predicate = true()
        else:
            max_length_predicate = func.cardinality(base_step.c.trace) < self.max_length

        if self.PathBase.cfl:
            assert path_class.edge_symbol_table is not None

            if self.is_reversed:
                extension_direction_predicate_1 = (
                    base_step.c.source == path_class.edge_symbol_table.c.target
                )
            else:
                extension_direction_predicate_1 = (
                    base_step.c.target == path_class.edge_symbol_table.c.source
                )

            extension_join_1 = join(
                base_step,
                path_class.edge_symbol_table,
                extension_direction_predicate_1 & max_length_predicate,
            )

            extension_join_1 = join(
                extension_join_1,
                path_class.transition_table,
                (path_class.edge_symbol_table.c.symbol == path_class.transition_table.c.input)  # type: ignore[union-attr]
                & (base_step.c.state == path_class.transition_table.c.old_state)  # type: ignore[union-attr]
                & (base_step.c.stack_top == path_class.transition_table.c.old_stack)  # type: ignore[union-attr]
                & no_detail_continue_predicate(base_step, path_class.edge_symbol_table.c),
            )

            if continue_predicate is not None:
                extension_join_1 = join(
                    extension_join_1,
                    graph.Edge.__table__,
                    (path_class.edge_symbol_table.c.uuid == graph.Edge.uuid)
                    & continue_predicate(base_step, graph.Edge),
                )
        else:
            if self.is_reversed:
                extension_direction_predicate_1 = base_step.c.source == graph.Edge.target
            else:
                extension_direction_predicate_1 = base_step.c.target == graph.Edge.source

            if continue_predicate is not None:
                extension_join_1 = join(
                    base_step,
                    graph.Edge.__table__,
                    extension_direction_predicate_1
                    & no_detail_continue_predicate(base_step, graph.Edge)
                    & continue_predicate(base_step, graph.Edge)
                    & max_length_predicate,
                )
            else:
                extension_join_1 = join(
                    base_step,
                    graph.Edge.__table__,
                    extension_direction_predicate_1
                    & no_detail_continue_predicate(base_step, graph.Edge)
                    & max_length_predicate,
                )

        if self.PathBase.cfl:
            edge_rel = path_class.edge_symbol_table
        else:
            edge_rel = graph.Edge.__table__

        assert edge_rel is not None

        if not self.is_reversed:
            source_columns = [base_step.c.source]
            target_columns = [
                edge_rel.c.target.label("target"),
            ]
            augmented_trace = func.array_append(base_step.c.trace, edge_rel.c.uuid).label("trace")
        else:
            source_columns = [
                edge_rel.c.source.label("source"),
            ]
            target_columns = [base_step.c.target]
            augmented_trace = func.array_prepend(edge_rel.c.uuid, base_step.c.trace).label("trace")

        # Project out the appropriate set of columns from the first extension
        # join, and augment each path trace with the UUID of the edge just
        # added.
        extension_select_1 = select(
            [
                base_step.c.info,
                *source_columns,
                base_step.c.source_stack,
                *target_columns,
                augmented_trace if keep_trace else base_step.c.trace,
                path_class.transition_table.c.new_state.label("state")  # type: ignore[union-attr]
                if self.PathBase.cfl
                else base_step.c.state,
                case(
                    [
                        (
                            (
                                path_class.transition_table.c.new_stack[  # type: ignore[union-attr]
                                    func.cardinality(path_class.transition_table.c.new_stack)  # type: ignore[union-attr]
                                ]
                                == literal(BOT)
                            ),
                            path_class.transition_table.c.new_stack,  # type: ignore[union-attr]
                        )
                    ],
                    else_=func.array_cat(
                        path_class.transition_table.c.new_stack,  # type: ignore[union-attr]
                        base_step.c.stack[2 : func.cardinality(base_step.c.stack)],
                    ),
                )
                .cast(ARRAY(String))
                .label("stack")
                if self.PathBase.cfl
                else base_step.c.stack,
                case(
                    [
                        (
                            func.cardinality(path_class.transition_table.c.new_stack) == 0,  # type: ignore[union-attr]
                            base_step.c.stack[2],
                        ),
                    ],
                    else_=Grouping(path_class.transition_table.c.new_stack)[1],  # type: ignore[union-attr]
                )
                .cast(String)
                .label("stack_top")
                if self.PathBase.cfl
                else base_step.c.stack_top,
                edge_rel.c.uuid.label("edge") if keep_edge else base_step.c.edge,
            ],
        ).select_from(extension_join_1)

        # TODO: handle continuing while predicates with Node attributes
        path_steps = (
            base_step.union(extension_select_1).alias()
            if exploration_bound is None
            else base_step.union(extension_select_1).select().limit(exploration_bound).alias()
        )

        if (self.stop_predicates != [] and not self.is_reversed) or (
            self.start_predicates != [] and self.is_reversed
        ):
            filtered_paths = join(
                path_steps,
                graph.Node,
                (
                    (path_steps.c.target == graph.Node.uuid)
                    if not self.is_reversed
                    else (path_steps.c.source == graph.Node.uuid)
                )
                & (
                    stop_predicate(graph.Node)
                    if not self.is_reversed
                    else start_predicate(graph.Node)
                ),
            )
        else:
            filtered_paths = path_steps

        # Issue the VIEW definition. This statement should be instantaneous.
        graph.session.bind.execute(CreateView(f"paths_{name}", filtered_paths.select()))

        return path_class


def _make_edge_symbol_table(name: str, edge_table: Table) -> Table:
    uuid_comment = "UUID of the edge in the CPG"
    source_comment = "UUID of the edge's source node"
    target_comment = "UUID of the edge's target node"
    symbol_comment = "A symbol encoding the relevant information about the edge that will be used in the PDA's transition relation"
    return Table(
        f"{name}_edge_symbols",
        _metadata,
        Column(
            "uuid", String, primary_key=True, nullable=False, doc=uuid_comment, comment=uuid_comment
        ),
        Column(
            "source", String, index=True, nullable=False, doc=source_comment, comment=source_comment
        ),
        Column(
            "target", String, index=True, nullable=False, doc=target_comment, comment=target_comment
        ),
        Column(
            "symbol",
            String,
            primary_key=True,
            index=True,
            nullable=False,
            doc=symbol_comment,
            comment=symbol_comment,
        ),
        ForeignKeyConstraint(
            ["uuid"],
            [edge_table.c.uuid],
        ),
        Index(f"{name}_sym_ss", "symbol", "source"),
        Index(f"{name}_sym_st", "symbol", "target"),
        extend_existing=True,
    )


def _make_transition_table(name: str) -> Table:
    old_state_comment = "The PDA state for which this transition is applicable"
    old_stack_comment = "The top item of the PDA stack for which this transition is applicable (always a single symbol, even though the type is array)"
    input_comment = "The edge symbol that must match for this transition to fire"
    new_state_comment = "The state to transition to"
    new_stack_comment = "A stack of values to replace the top item on the stack with, or a replacement for the entire stack if new_stack ends with '$'"
    return Table(
        f"{name}_rules",
        _metadata,
        Column(
            "old_state", String, nullable=False, doc=old_state_comment, comment=old_state_comment
        ),
        Column(
            "old_stack",
            String,
            nullable=False,
            doc=old_stack_comment,
            comment=old_stack_comment,
        ),
        Column("input", String, nullable=False, doc=input_comment, comment=input_comment),
        Column(
            "new_state", String, nullable=False, doc=new_state_comment, comment=new_state_comment
        ),
        Column(
            "new_stack",
            ARRAY(String),
            nullable=False,
            doc=new_stack_comment,
            comment=new_stack_comment,
        ),
        Index(f"{name}_rules_j", "old_state", "old_stack", "input"),
        extend_existing=True,
    )
