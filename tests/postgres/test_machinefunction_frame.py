"""This file tests various stack frame invariants in ``MachineFunction``."""

import pytest

# TODO(ww): Tests for MachineFunction.frame.
# See: https://gitlab-ext.galois.com/mate/MATE/-/issues/887


@pytest.mark.skip(reason="TODO(#1711)")
@pytest.mark.parametrize("cflags", [("-O0",), ("-O1",), ("-O2",)])
def test_no_epilogues(session, cpg_db_v2, cflags):
    cpg = cpg_db_v2("example_1.c", compile_options=dict(extra_compiler_flags=cflags))

    runServer = session.query(cpg.MachineFunction).filter_by(name="runServer").one()

    # runServer is a special case: it has a stack frame, but LLVM is smart enough
    # to optimize out its epilogue (as it contains a never-returning infinite loop).
    # Consequently, runServer.epilogues should be empty
    assert runServer.epilogues == []

    # On the other hand, runServer *does* have a normal prologue, and its standard
    # invariants hold.
    assert len(runServer.prologues) == 1
    assert runServer.va_start < runServer.prologues[0][1]
