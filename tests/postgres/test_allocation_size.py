import pytest

from mate_common.models.builds import PointerAnalysis


# NOTE(lb): This doesn't work at O0 (without mem2reg), because there are a
# million extra stack allocations.
@pytest.mark.parametrize("cflags", [("-O1",)])
def test_allocation_sizes(pointer_analysis_results_v2, session, cpg_db_v2, cflags):
    cpg = cpg_db_v2(
        "allocation-sizes.c",
        compile_options=dict(extra_compiler_flags=cflags),
        build_options=dict(debug_pointer_analysis=True, pointer_analysis=PointerAnalysis.DEBUG),
    )
    dl_results = pointer_analysis_results_v2(session, cpg)
    allocation_size = dl_results.get("allocation_size.csv.gz")
    basic_allocation = dl_results.get("basic_allocation.csv.gz")

    stack_alloc_rows = [
        row
        for row in allocation_size
        if "stack_alloc@main" in row[0] and [row[0]] in basic_allocation
    ]
    heap_alloc_rows = [
        row
        for row in allocation_size
        if "heap_alloc@main" in row[0] and [row[0]] in basic_allocation
    ]

    assert len(stack_alloc_rows) == 2
    assert len(heap_alloc_rows) == 6

    stack_alloc_sizes = {int(row[1]) for row in stack_alloc_rows}
    heap_alloc_sizes = {int(row[1]) for row in heap_alloc_rows}

    # sizes := {sizeof(char) * SMALL_CONST_SIZE, sizeof(char) * LARGE_CONST_SIZE}
    sizes = {32, 512}
    assert stack_alloc_sizes == sizes
    assert heap_alloc_sizes == sizes
