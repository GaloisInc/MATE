def test_llvm_types(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "notes.c",  # the particular program isn't that important
        compile_options=dict(extra_compiler_flags=optimization_flags),
    )

    # Every instruction should have a type
    instructions = session.query(cpg.Instruction).all()
    assert len(instructions) > 0
    for instruction in instructions:
        assert not instruction.llvm_type.is_function_type

    # Every function should have a function type
    functions = session.query(cpg.Function).all()
    assert len(functions) > 0
    for function in functions:
        assert function.llvm_type.is_function_type
        assert not function.llvm_type.is_struct_type

    # The following hybrid_properties should work inside queries, and there
    # should be at least one of all of the following:
    filters = [
        cpg.LLVMType.is_named_struct_type,
        cpg.LLVMType.is_pointer_type,
        cpg.LLVMType.is_function_type,
        cpg.LLVMType.is_void,
    ]
    for filt in filters:
        assert len(session.query(cpg.LLVMType).filter(filt).all()) > 0

    ptr_type = (
        session.query(cpg.LLVMType)
        .filter(cpg.LLVMType.is_pointer_type & (~cpg.LLVMType.is_function_type))
        .first()
    )
    assert ptr_type.size_in_bits == 64
    assert ptr_type.store_size_in_bits == 64
    assert ptr_type.alloc_size_in_bits == 64
    assert ptr_type.abi_type_alignment == 8

    # %struct.sockaddr = type { i16, [14 x i8] }
    struct_type = (
        session.query(cpg.LLVMType)
        .filter(
            cpg.LLVMType.is_named_struct_type,
            cpg.LLVMType.definition["name"].as_string() == "struct.sockaddr",
        )
        .first()
    )
    assert struct_type.is_struct_type
    assert struct_type.size_in_bits == 128  # == 16 + (14 * 8)
    assert struct_type.store_size_in_bits == 128
    assert struct_type.alloc_size_in_bits == 128
    assert struct_type.abi_type_alignment == 2

    i1 = session.query(cpg.LLVMType).filter_by(size_in_bits=1).one()
    assert i1.store_size_in_bits == 8
