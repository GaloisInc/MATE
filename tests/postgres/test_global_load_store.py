"""Test that we get load and store edges for inline global variable references."""
import pytest

from mate_common.models.cpg_types import EdgeKind


# The interesting bits get optimized out of the test program at O1
@pytest.mark.parametrize("cflags", [("-O0",)])
def test_global_memory_store_load(session, cpg_db_v2, cflags):
    """Find the instructions that load from and store to the global variable and ensure they have
    load/store edges."""
    cpg = cpg_db_v2(
        "global.c",
        compile_options=dict(extra_compiler_flags=cflags),
        build_options=dict(do_pointer_analysis=True, llvm_pretty_strings=True),
    )

    mem_locs = session.query(cpg.MemoryLocation).all()
    assert len(mem_locs) > 0

    load_global = (
        session.query(cpg.Instruction)
        .filter(
            cpg.Instruction.attributes["location"]["line"].as_integer() == 6,
            cpg.Instruction.attributes["pretty_string"]
            .as_string()
            .like("%t2 = load i32, i32* @global, align 4%"),
        )
        .one()
    )
    incoming = {e.kind for e in load_global.incoming}
    assert EdgeKind.LOAD_MEMORY in incoming

    store_global = (
        session.query(cpg.Instruction)
        .filter(
            cpg.Instruction.attributes["location"]["line"].as_integer() == 13,
            cpg.Instruction.attributes["pretty_string"]
            .as_string()
            .like("%store i32 %t3, i32* @global, align 4%"),
        )
        .one()
    )
    outgoing = {e.kind for e in store_global.outgoing}
    assert EdgeKind.STORE_MEMORY in outgoing
