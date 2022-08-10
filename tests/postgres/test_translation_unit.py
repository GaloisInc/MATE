def test_module(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2("notes.c", compile_options=dict(extra_compiler_flags=optimization_flags))

    module = session.query(cpg.Module).one()

    assert module.source_file == "llvm-link"
    assert module.target_triple == "x86_64-unknown-linux-gnu"
    assert (
        module.data_layout
        == "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-f80:128-n8:16:32:64-S128"
    )


def test_translation_unit(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2("notes.c", compile_options=dict(extra_compiler_flags=optimization_flags))

    # NOTE(ww): notes.c is a single source file, so it has exactly one translation unit.
    translation_unit = session.query(cpg.TranslationUnit).one()

    assert translation_unit.source_language == "DW_LANG_C99"
    assert translation_unit.producer == "clang version 10.0.1 "
    for optimization_flag in optimization_flags:
        assert optimization_flag in translation_unit.flags
