import pytest


@pytest.mark.xfail(strict=True)
def test_arg_pairing_fails(cpg_db_v2):
    _ = cpg_db_v2(
        "accumulate.cpp",
        compile_options=dict(extra_compiler_flags=("-O0",)),
        build_options=dict(argument_edges=True),
    )
