"""Nodes in the LLVM middle-end's AST.

At runtime, the models here are accessed via attributes on a CPG, not directly.
"""

from __future__ import annotations

from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import RelationshipProperty

from mate_common.models.cpg_types import EdgeKind, MachineFrameInfo, NodeKind
from mate_query.cpg.models.node._typechecking import NodeMixin


class MachineFunction(NodeMixin):
    _kind = NodeKind.MACHINE_FUNCTION

    @declared_attr
    def blocks(cls) -> RelationshipProperty:
        """The function's `MachineBasicBlock` list."""
        return cls.edge_relationship(
            EdgeKind.BLOCK_TO_PARENT_FUNCTION,
            cls.cpg.MachineBasicBlock,
            backref="parent_function",
        )

    @declared_attr
    def arguments(cls) -> RelationshipProperty:
        """The arguments of this function."""
        return cls.edge_relationship(
            EdgeKind.MI_FUNCTION_TO_DWARF_ARGUMENT,
            cls.cpg.DWARFArgument,
            backref="machine_function",
        )

    @declared_attr
    def local_variables(cls) -> RelationshipProperty:
        """The local variables in this function."""
        return cls.edge_relationship(
            EdgeKind.MI_FUNCTION_TO_DWARF_LOCAL_VARIABLE,
            cls.cpg.DWARFLocalVariable,
            backref="machine_function",
        )

    @hybrid_property
    def frame(self) -> MachineFrameInfo:
        """A `MachineFrameInfo` model of the function's stack frame."""
        return MachineFrameInfo(**self.frame_info)

    @declared_attr
    def vtables(cls) -> RelationshipProperty:
        """The function's `mate_query.cpg.models.node.ast.bin.VTable` list."""
        return cls.edge_relationship(
            EdgeKind.MI_FUNCTION_TO_VTABLE,
            cls.cpg.VTable,
            backref="machine_functions",
        )

    @declared_attr
    def dwarf_type(cls) -> RelationshipProperty:
        """The function's `mate_query.cpg.models.node.dwarf.DWARFType`."""
        return cls.edge_relationship(
            EdgeKind.HAS_DWARF_TYPE, cls.cpg.DWARFType, backref="machine_functions"
        )


class MachineBasicBlock(NodeMixin):
    _kind = NodeKind.MACHINE_BASIC_BLOCK

    @declared_attr
    def asm_block(cls) -> RelationshipProperty:
        """The corresponding `ASMBlock`."""
        return cls.edge_relationship(
            EdgeKind.MI_BLOCK_TO_ASM_BLOCK, cls.cpg.ASMBlock, backref="mi_block"
        )

    @declared_attr
    def instructions(cls) -> RelationshipProperty:
        """A sequence of `MachineInstr` for each instruction in this machine basic block."""
        return cls.edge_relationship(
            EdgeKind.INSTRUCTION_TO_PARENT_BLOCK, cls.cpg.MachineInstr, backref="mi_block"
        )

    @declared_attr
    def entry(cls) -> RelationshipProperty:
        """The entry `MachineInstr` for this machine basic block."""
        return cls.edge_relationship(EdgeKind.BLOCK_TO_ENTRY_INSTRUCTION, cls.cpg.MachineInstr)

    @declared_attr
    def terminator(cls) -> RelationshipProperty:
        """The exit `MachineInstr` for this machine basic block."""
        return cls.edge_relationship(EdgeKind.BLOCK_TO_TERMINATOR_INSTRUCTION, cls.cpg.MachineInstr)


class MachineInstr(NodeMixin):
    _kind = NodeKind.MACHINE_INSTR
