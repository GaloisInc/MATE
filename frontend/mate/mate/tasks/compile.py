from mate.assertions import compilation_assert
from mate.build import compile as mate_compile
from mate.tasks import _CompilationTask, executor
from mate_common.models.compilations import CompilationState, CompileOptions
from mate_query import db


@executor.task(bind=True, base=_CompilationTask)
def compile_artifact(
    self: _CompilationTask, artifact_id: str, opts: CompileOptions, *, compilation_id: str
) -> None:
    artifact = self.session.query(db.Artifact).get(artifact_id)
    compilation_assert(
        artifact.kind.is_compile_target(),
        f"invalid artifact kind {artifact.kind=} (expected compile target)",
        compilation_id=compilation_id,
    )

    compilation = self.session.query(db.Compilation).get(compilation_id)
    compilation_assert(
        compilation.state == CompilationState.Created,
        f"invalid compilation state ({compilation.state=} is not created)",
        compilation_id=compilation_id,
    )

    mate_compile.compile_artifact(artifact, compilation, self.session, opts)
