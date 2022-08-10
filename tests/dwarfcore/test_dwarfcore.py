from dwarfcore.dwarfcore import DwarfCore


def test_dwarfcore_function_vas(session, dc_cpg_v2):
    (cpg, test_bin) = dc_cpg_v2("hello.c", compile_options=dict(extra_compiler_flags=("-O1",)))
    dwarfcore = DwarfCore(session, cpg, test_bin)

    # NOTE(lb): These were hand-checked with objdump

    # Defined
    assert dwarfcore.start_va_of_function("main") == 0x401140
    assert dwarfcore.start_va_of_function("foo") == 0x4011B0
    assert dwarfcore.start_va_of_function("bar") == 0x401200

    # PLT (procedure linkage table) stubs
    assert dwarfcore.start_va_of_function("puts") == 0x401030
    assert dwarfcore.start_va_of_function("rand") == 0x401040
