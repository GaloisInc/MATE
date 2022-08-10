"""A test for the basic semantic correctness of our ASMInst attributes."""


def test_asm_insts(session, cpg_db_v2):
    cpg = cpg_db_v2("notes.c")  # the particular program isn't that important

    # Sanity check our register/memory use information by testing a few
    # different instructions with well-known semantics.

    # RET uses one register (RSP/R+W) and does one memory op ([RSP]).
    for ret in session.query(cpg.ASMInst).filter_by(mnemonic="ret").all():
        assert len(ret.used_registers) == 1
        assert len(ret.used_memory) == 1

        assert ret.used_registers[0].register_ == "RSP"
        assert ret.used_registers[0].access == "READ_WRITE"

        assert ret.used_memory[0].base == "RSP"
        assert ret.used_memory[0].memory_size == 8
        assert ret.used_memory[0].access == "READ"

    # POP uses two registers (RBP/W and RSP/R+W) and does one memory op ([RSP])
    for pop in session.query(cpg.ASMInst).filter_by(mnemonic="pop").all():
        assert len(pop.used_registers) == 2
        assert len(pop.used_memory) == 1

        for ur in pop.used_registers:
            if ur.register_ == "RBP":
                assert ur.access == "WRITE"
            elif ur.register_ == "RSP":
                assert ur.access == "READ_WRITE"
            else:
                assert False

        assert pop.used_memory[0].base == "RSP"
        assert pop.used_memory[0].memory_size == 8
        assert pop.used_memory[0].access == "READ"
