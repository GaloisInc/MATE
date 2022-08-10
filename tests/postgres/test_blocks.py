def test_blocks(session, cpg_db_v2, optimization_flags):
    cpg = cpg_db_v2(
        "notes.c",  # the particular program isn't that important
        compile_options=dict(extra_compiler_flags=optimization_flags),
    )

    asm_blocks = session.query(cpg.ASMBlock).all()
    assert len(asm_blocks) > 0
    for block in asm_blocks:
        assert block.mi_block is not None
        # TODO(lb): investigate
        # assert block.instructions != []

    mi_blocks = session.query(cpg.MachineBasicBlock).all()
    assert len(mi_blocks) > 0
    for block in mi_blocks:
        assert block.ir_block is not None
        assert block.asm_block is not None
        assert block.parent_function is not None

    blocks = session.query(cpg.Block).all()
    assert len(blocks) > 0
    for block in blocks:
        assert not block.llvm_type.is_function_type
        assert not block.llvm_type.is_struct_type
        assert not block.llvm_type.is_pointer_type
        assert block.parent_function is not None
        assert len(block.instructions) > 0

    instructions = session.query(cpg.Instruction).all()
    for instruction in instructions:
        assert instruction.parent_block is not None

    for name in ["main"]:
        function = session.query(cpg.Function).filter_by(name=name).one()
        assert len(function.blocks) > 0

    # There isn't _always_ a corresponding MI block, but there usually is
    main = session.query(cpg.Function).filter_by(name="main").one()
    for block in main.blocks:
        assert block.mi_blocks != []
