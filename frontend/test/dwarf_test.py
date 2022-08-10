from elftools.dwarf.structs import DWARFStructs

from dwarflang.ast import DwarfInstr
from dwarflang.enums import DW_OP
from mate.build.tob_chess_utils.dwarf import dwarf_expr_as_value, dwarf_reg_to_machine_reg

STRUCTS64 = DWARFStructs(little_endian=True, dwarf_format=64, address_size=8, dwarf_version=4)


def test_dwarf_reg_to_machine_reg():
    assert dwarf_reg_to_machine_reg(DW_OP.BREG1.value) == "rdx"
    assert dwarf_reg_to_machine_reg(DW_OP.BREG2.value) == "rcx"


def test_dwarf_expr_as_value():
    def test_with_reg(instr):
        return dwarf_expr_as_value([instr], parent_loc_expr=[DwarfInstr(DW_OP.REG1, [])])

    def test_with_breg(instr):
        return dwarf_expr_as_value([instr], parent_loc_expr=[DwarfInstr(DW_OP.BREG1, [16])])

    assert test_with_reg(DwarfInstr(DW_OP.FBREG, [8])) == ("rdx", 8)
    assert test_with_breg(DwarfInstr(DW_OP.FBREG, [-8])) == ("rdx", 8)
