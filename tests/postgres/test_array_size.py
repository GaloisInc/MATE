from mate_common.models.cpg_types import DWARFSubrangeKind


def test_array_size(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "notes.c",  # the particular program isn't that important
        compile_options=dict(extra_compile_flags=optimization_flags),
        build_options=dict(machine_code_mapping=False, llvm_pretty_strings=False),
    )

    # Query for all types with an array
    all_array_types = session.query(cpg.LLVMType).filter_by(is_array_type=True).all()

    # Assert that each array_type has an array_size
    for array_type in all_array_types:
        assert array_type.array_size > 0


def test_dwarf_array_type(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "array-tests.c",
        compile_options=dict(extra_compile_flags=optimization_flags),
        build_options=dict(machine_code_mapping=True, llvm_pretty_strings=False),
    )

    # Query for all DWARF ArrayType types
    all_array_types = session.query(cpg.ArrayType).all()

    seen_kinds = set()
    # Assert that each array_type has an array_size
    for array_type in all_array_types:
        seen_kinds.add(array_type.subrange.kind)
    # NOTE: Can't seem to find a test case for GLOBAL_VARIABLE subrange
    assert seen_kinds == set(k for k in DWARFSubrangeKind) - {DWARFSubrangeKind.GLOBAL_VARIABLE}
