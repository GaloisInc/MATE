"""Nodes in the x86_64 binary AST.

At runtime, the models here are accessed via attributes on a CPG, not directly.
"""

from __future__ import annotations

from typing import List

from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import RelationshipProperty

from mate_common.models.cpg_types import EdgeKind, NodeKind, UsedMemory, UsedRegister
from mate_query.cpg.models.node._typechecking import NodeMixin


class ASMBlock(NodeMixin):
    _kind = NodeKind.ASM_BLOCK

    @declared_attr
    def entry(cls) -> RelationshipProperty:
        """Returns the entry `ASMInst` for this block."""
        return cls.edge_relationship(EdgeKind.BLOCK_TO_ENTRY_INSTRUCTION, cls.cpg.ASMInst)

    @declared_attr
    def terminator(cls) -> RelationshipProperty:
        """Returns the terminating `ASMInst` for this block."""
        return cls.edge_relationship(EdgeKind.BLOCK_TO_TERMINATOR_INSTRUCTION, cls.cpg.ASMInst)

    @declared_attr
    def instructions(cls) -> RelationshipProperty:
        """Returns a sequence of every `ASMInst` in this block."""
        return cls.edge_relationship(
            EdgeKind.INSTRUCTION_TO_PARENT_BLOCK, cls.cpg.ASMInst, backref="asm_block"
        )


class ASMInst(NodeMixin):
    _kind = NodeKind.ASM_INST

    @property
    def used_registers(self) -> List[UsedRegister]:
        """Returns a sequence of `UsedRegister` for each register used by this instruction."""
        return [UsedRegister(**r) for r in self.attributes["used_registers"]]

    @property
    def used_memory(self) -> List[UsedMemory]:
        """Returns a sequence of `UsedMemory` for each discrete memory access in this
        instruction."""
        return [UsedMemory(**r) for r in self.attributes["used_memory"]]


class ASMGlobalVariable(NodeMixin):
    _kind = NodeKind.ASM_GLOBAL_VARIABLE

    @declared_attr
    def dwarf_type(cls) -> RelationshipProperty:
        """Returns the `DWARFType` for this global variable."""
        return cls.edge_relationship(
            EdgeKind.HAS_DWARF_TYPE, cls.cpg.DWARFType, backref="global_variables"
        )


class PLTStub(NodeMixin):
    _kind = NodeKind.PLT_STUB

    @declared_attr
    def vtables(cls) -> RelationshipProperty:
        """Returns a sequence of `VTable` instances associated with this PLT stub."""
        return cls.edge_relationship(
            EdgeKind.PLT_STUB_TO_VTABLE,
            cls.cpg.VTable,
            backref="plt_stubs",
        )


class VTable(NodeMixin):
    _kind = NodeKind.VTABLE

    @hybrid_property
    def members(self):
        """The members of this virtual table."""
        """Returns the individual members of this virtual table."""
        return self.attributes["members"]

    @members.expression  # type: ignore[no-redef]
    def members(cls):
        return cls.attributes["members"].as_list()
