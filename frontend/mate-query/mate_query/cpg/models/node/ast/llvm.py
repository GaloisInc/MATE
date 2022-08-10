"""Nodes in the LLVM AST.

At runtime, the models here are accessed via attributes on a CPG, not directly.
"""
from __future__ import annotations

import binascii
import logging
import typing
from collections.abc import Iterable
from typing import TYPE_CHECKING, Type

from sqlalchemy import and_
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import Comparator, hybrid_method, hybrid_property
from sqlalchemy.orm import backref, relationship
from sqlalchemy.types import JSON

from mate_common.datastructures.digraph import Digraph
from mate_common.models.analyses import SalientFunction
from mate_common.models.cpg_types import EdgeKind, NodeKind
from mate_query.cpg.models.core.relationships import Direction
from mate_query.cpg.models.node._typechecking import NodeMixin

if TYPE_CHECKING:
    from typing import Any, ClassVar, Dict, List, Optional

    from sqlalchemy.orm import RelationshipProperty

    from mate_query.cpg.models.core.cpg import MemoryLocation
    from mate_query.cpg.models.core.node import Node
    from mate_query.db import Graph as CPG


logger = logging.getLogger(__name__)


class LLVMType(NodeMixin):
    _kind = NodeKind.LLVM_TYPE

    @declared_attr
    def instructions(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.HAS_LLVM_TYPE, cls.cpg.Instruction, backref="llvm_type"
        )

    @declared_attr
    def functions(cls) -> RelationshipProperty:
        return cls.edge_relationship(EdgeKind.HAS_LLVM_TYPE, cls.cpg.Function, backref="llvm_type")

    @declared_attr
    def blocks(cls) -> RelationshipProperty:
        return cls.edge_relationship(EdgeKind.HAS_LLVM_TYPE, cls.cpg.Block, backref="llvm_type")

    @declared_attr
    def constants(cls) -> RelationshipProperty:
        return cls.edge_relationship(EdgeKind.HAS_LLVM_TYPE, cls.cpg.Constant, backref="llvm_type")

    @declared_attr
    def arguments(cls) -> RelationshipProperty:
        return cls.edge_relationship(EdgeKind.HAS_LLVM_TYPE, cls.cpg.Argument, backref="llvm_type")

    @declared_attr
    def global_variables(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.HAS_LLVM_TYPE, cls.cpg.GlobalVariable, backref="llvm_type"
        )

    @hybrid_property
    def name(self):
        return self.attributes["definition"]["name"]

    @name.expression  # type: ignore[no-redef]
    def name(cls):
        return cls.attributes["definition"]["name"].as_string()

    @hybrid_property
    def definition(self) -> Any:
        return self.attributes["definition"]

    def get(self, key: str) -> Any:
        try:
            return self.definition.get(key)
        except AttributeError:  # definition is a string, e.g. "void"
            return None

    @hybrid_property
    def is_void(self) -> bool:
        return self.definition.as_string() == "void"

    @hybrid_property
    def is_array_type(self) -> bool:
        return self.get("array") is not None

    @is_array_type.expression  # type: ignore[no-redef]
    def is_array_type(cls):
        return cls.definition["array_size"].as_integer() != JSON.NULL

    @hybrid_property
    def array_size(self) -> int:
        return self.attributes["definition"]["array_size"]

    @hybrid_property
    def is_pointer_type(self) -> bool:
        return self.get("pointer") is not None

    @is_pointer_type.expression  # type: ignore[no-redef]
    def is_pointer_type(cls):
        return cls.definition.has_key("pointer")

    @hybrid_property
    def is_function_type(self) -> bool:
        return self.is_pointer_type and self.get("pointer").get("function") is not None

    @is_function_type.expression  # type: ignore[no-redef]
    def is_function_type(cls):
        return cls.definition["pointer"].has_key("function")

    @hybrid_property
    def is_struct_type(self) -> bool:
        return self.get("struct") is not None

    @is_struct_type.expression  # type: ignore[no-redef]
    def is_struct_type(cls):
        return cls.definition.has_key("struct")

    @hybrid_property
    def is_named_struct_type(self):
        return self.is_struct_type and self.get("name") is not None

    @is_named_struct_type.expression  # type: ignore[no-redef]
    def is_named_struct_type(cls):
        return cls.is_struct_type & cls.definition.has_key("name")

    @hybrid_property
    def size_in_bits(self):
        return self.attributes["size_in_bits"]

    @size_in_bits.expression  # type: ignore[no-redef]
    def size_in_bits(cls):
        return cls.attributes["size_in_bits"].as_integer()


class Constant(NodeMixin):
    _kind = NodeKind.CONSTANT


class ConstantInt(Constant):
    _kind = NodeKind.CONSTANT_INT


class ConstantFP(Constant):
    _kind = NodeKind.CONSTANT_FP


class CSComparator(Comparator):
    """A specialized SQLAlchemy Comparator for ``ConstantString``"""

    @staticmethod
    def __cast__(value: Any) -> Any:
        """Turns value into a hexstring, if appropriate."""
        if isinstance(value, str):
            return binascii.hexlify(value.encode()).decode()
        elif isinstance(value, bytes):
            return binascii.hexlify(value).decode()
        elif isinstance(value, Iterable):
            return [CSComparator.__cast__(v) for v in value]
        return value

    def operate(self, op: Any, other: Any, **_kwargs: Any) -> Any:
        return op(self.__clause_element__(), CSComparator.__cast__(other))


class ConstantString(Constant):
    _kind = NodeKind.CONSTANT_STRING

    @hybrid_property
    def string_value(self):
        return binascii.unhexlify(self.attributes["string_value"])

    @string_value.comparator  # type: ignore[no-redef]
    def string_value(cls):
        return CSComparator(cls.attributes["string_value"].as_string())


class ConstantUndef(Constant):
    _kind = NodeKind.CONSTANT_UNDEF


class Variable(NodeMixin):
    _kind = NodeKind.VARIABLE


class Argument(Variable):
    _kind = NodeKind.ARGUMENT

    @declared_attr
    def as_dwarf(cls) -> RelationshipProperty:
        return cls.edge_relationship(EdgeKind.ARGUMENT_TO_DWARF_ARGUMENT, cls.cpg.DWARFArgument)

    @property
    def memory_locations(cls) -> Optional[List[MemoryLocation]]:
        if not cls.allocation_site:
            return None
        return cls.allocation_site.allocates

    @declared_attr
    def allocation_site(cls) -> RelationshipProperty:
        return relationship(
            cls.cpg.Alloca,
            secondary=cls.cpg.Edge.__table__,
            primaryjoin=and_(
                cls.cpg.Edge.target == cls.uuid,
                cls.cpg.Edge.kind == EdgeKind.CREATES_VAR,
            ),
            secondaryjoin=cls.cpg.Alloca.uuid == cls.cpg.Edge.source,
            uselist=False,
            doc="Link to the Alloca that created this Argument",
        )


class Function(NodeMixin):
    _kind = NodeKind.FUNCTION

    @declared_attr
    def arguments(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.FUNCTION_TO_ARGUMENT, cls.cpg.Argument, backref="parent_function"
        )

    @declared_attr
    def blocks(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.BLOCK_TO_PARENT_FUNCTION, cls.cpg.Block, backref="parent_function"
        )

    @declared_attr
    def machine_functions(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.MI_FUNCTION_TO_IR_FUNCTION,
            cls.cpg.MachineFunction,
            backref="ir_function",
        )

    @declared_attr
    def plt_stub(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.FUNCTION_TO_PLT_STUB,
            cls.cpg.PLTStub,
            backref="ir_function",
        )

    @declared_attr
    def entry_block(cls) -> RelationshipProperty:
        return cls.edge_relationship(EdgeKind.FUNCTION_TO_ENTRY_BLOCK, cls.cpg.Block)

    @declared_attr
    def entry_controls_blocks(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.FUNCTION_ENTRY_TO_CONTROL_DEPENDENT_BLOCK,
            cls.cpg.Block,
            direction=Direction.OUT,
            backref="controlled_by_function_entry",
        )

    @declared_attr
    def entry_controls_instructions(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.FUNCTION_ENTRY_TO_CONTROL_DEPENDENT_INSTRUCTION,
            cls.cpg.Instruction,
            direction=Direction.OUT,
            backref="controlled_by_function_entry",
        )

    @declared_attr
    def callsites(cls) -> RelationshipProperty:
        return cls.edge_relationship(EdgeKind.CALL_TO_FUNCTION, cls.cpg.CallSite, backref="callees")

    @declared_attr
    def callees(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.CALLGRAPH,
            cls,  # type: ignore[arg-type]
            direction=Direction.OUT,
            backref="callers",
        )

    @declared_attr
    def signatures(cls) -> RelationshipProperty:
        return relationship(
            cls.cpg.Node,
            secondary=cls.cpg.Edge.__table__,
            primaryjoin=cls.uuid == cls.cpg.Edge.target,
            secondaryjoin=and_(
                cls.cpg.Edge.kind == EdgeKind.DATAFLOW_SIGNATURE_FOR_FUNCTION,
                cls.cpg.Edge.source == cls.cpg.Node.uuid,
            ),
            lazy="dynamic",
            doc="Connects a function to signatures defined for its call sites.",
        )

    def as_salient(self) -> SalientFunction:
        """Create a ``SalientFunction`` from this ``Function``."""
        return SalientFunction(cpg_id=self.uuid, demangled_name=self.demangled_name, name=self.name)


class GlobalVariable(Variable):
    _kind = NodeKind.GLOBAL_VARIABLE

    @declared_attr
    def initializer(cls) -> RelationshipProperty:
        return relationship(
            cls.cpg.Node,
            secondary=cls.cpg.Edge.__table__,
            primaryjoin=and_(
                cls.cpg.Edge.source == cls.uuid,
                cls.cpg.Edge.kind == EdgeKind.GLOBAL_TO_INITIALIZER,
            ),
            secondaryjoin=cls.cpg.Edge.target == cls.cpg.Node.uuid,
            lazy="select",
            uselist=False,
            backref=backref(
                "initializes", doc="Connects an initializer to the global variables it initializes."
            ),
            doc="Connects a global variable to its initializer.",
        )

    @property
    def memory_locations(cls) -> Optional[List[MemoryLocation]]:
        return cls.allocates


class Module(NodeMixin):
    _kind = NodeKind.MODULE

    def translation_units(cls) -> RelationshipProperty:
        """A sequence of all source-level translation units in this module."""
        return cls.edge_relationship(EdgeKind.MODULE_TO_TRANSLATION_UNIT, cls.cpg.TranslationUnit)


class Block(NodeMixin):

    _kind = NodeKind.BLOCK

    @declared_attr
    def mi_blocks(cls) -> RelationshipProperty:
        """All middle-end blocks (``MachineBasicBlock``s) for this IR block."""
        return cls.edge_relationship(
            EdgeKind.MI_BLOCK_TO_IR_BLOCK, cls.cpg.MachineBasicBlock, backref="ir_block"
        )

    @declared_attr
    def instructions(cls) -> RelationshipProperty:
        """All instructions in this block."""
        return cls.edge_relationship(
            EdgeKind.INSTRUCTION_TO_PARENT_BLOCK,
            cls.cpg.Instruction,
            backref="parent_block",
        )

    @declared_attr
    def entry(cls) -> RelationshipProperty:
        """The entry instruction for this block."""
        return cls.edge_relationship(EdgeKind.BLOCK_TO_ENTRY_INSTRUCTION, cls.cpg.Instruction)

    @declared_attr
    def terminator(cls) -> RelationshipProperty:
        """The terminator instruction for this block."""
        return cls.edge_relationship(EdgeKind.BLOCK_TO_TERMINATOR_INSTRUCTION, cls.cpg.Instruction)

    @declared_attr
    def successors(cls) -> RelationshipProperty:
        """The successor blocks for this block."""
        return cls.edge_relationship(
            EdgeKind.BLOCK_TO_SUCCESSOR_BLOCK,
            cls,  # type: ignore[arg-type]
            direction=Direction.OUT,
            backref="predecessors",
        )

    @declared_attr
    def controls(cls) -> RelationshipProperty:
        """The blocks controlled by this block."""
        return cls.edge_relationship(
            EdgeKind.BLOCK_TO_CONTROL_DEPENDENT_BLOCK,
            cls,  # type: ignore[arg-type]
            direction=Direction.OUT,
            backref="controlled_by",
        )

    def sorted_mi_blocks(self) -> typing.Iterable[Node]:
        """The ``MachineBasicBlock``s for this block, sorted."""
        # NOTE(lb): We don't use standard Python `sorted` here because the
        # (assumed) complete linear order by control-flow is very expensive to
        # compute (it requires SQL path queries). Instead, we assume each MI
        # block will be an immediate successor of another one, or the last
        # block in the list, and perform a topological sort based on the
        # (partial) successor relation.
        #
        # The point is to optimize for number of SQL queries.
        #
        # This is still pretty expensive.
        if len(self.mi_blocks) <= 1:
            return self.mi_blocks

        def get_successors(block: Node) -> typing.Iterable[Node]:
            return (
                e.target_node
                for e in block.outgoing
                if e.kind == EdgeKind.BLOCK_TO_SUCCESSOR_BLOCK and e in self.mi_blocks
            )

        done = Digraph.from_successor_function(self.mi_blocks, get_successors).topological_sort()

        if len(done) != len(self.mi_blocks):
            logger.error(f"Weird list of MI blocks for {self}. Sorted: {done}")

        return done


def _make_use_relationship(
    cpg: CPG,
    this_class: Type[Node],
    constraints: List[Any],
    other: Optional[Type[Node]] = None,
    doc: Optional[str] = None,
) -> RelationshipProperty:
    if other is None:
        other = cpg.Node
    return relationship(
        other,
        secondary=cpg.Edge.__table__,
        primaryjoin=and_(
            *(
                [
                    cpg.Edge.target == this_class.uuid,
                    cpg.Edge.kind == EdgeKind.VALUE_DEFINITION_TO_USE.value,
                ]
                + constraints
            )
        ),
        secondaryjoin=other.uuid == cpg.Edge.source,
        lazy="select",
        uselist=False,
        doc=doc,
    )


def _make_operand_relationship(
    cpg: CPG,
    this_class: Type[Node],
    number: int,
    other: Optional[Type[Node]] = None,
    additional_constraints: List[Any] = [],
    doc: Optional[str] = None,
) -> RelationshipProperty:
    return _make_use_relationship(
        cpg,
        this_class,
        [cpg.Edge.attributes["operand_number"].as_integer() == number] + additional_constraints,
        other,
        doc=doc if doc is not None else f"Operand {number} of the instruction.",
    )


class Instruction(NodeMixin):
    _kind = NodeKind.INSTRUCTION

    @declared_attr
    def controls(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.TERMINATOR_INSTRUCTION_TO_CONTROL_DEPENDENT_INSTRUCTION,
            cls,  # type: ignore[arg-type]
            direction=Direction.OUT,
            backref="controlled_by",
        )

    @declared_attr
    def successors(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION,
            cls,  # type: ignore[arg-type]
            direction=Direction.OUT,
            backref="predecessors",
        )

    @declared_attr
    def uses(cls) -> RelationshipProperty:
        return relationship(
            cls.cpg.Node,
            secondary=cls.cpg.Edge.__table__,
            primaryjoin=and_(
                cls.cpg.Edge.target == cls.uuid,
            ),
            secondaryjoin=and_(
                cls.cpg.Edge.source == cls.uuid,
                cls.cpg.Edge.kind == EdgeKind.VALUE_DEFINITION_TO_USE,
            ),
            lazy="dynamic",
            backref=backref(
                "used_by", doc="Connects a definition to the instructions that use it."
            ),
            doc="Connects an instruction to the definitions it uses.",
        )

    @declared_attr
    def operand0(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 0)

    @declared_attr
    def operand1(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 1)

    @declared_attr
    def operand2(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 2)

    @declared_attr
    def operand3(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 3)

    @declared_attr
    def operand4(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 4)

    @declared_attr
    def operand5(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 5)

    @declared_attr
    def operand6(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 6)

    @declared_attr
    def operand7(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 7)

    @declared_attr
    def operand8(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 8)

    @declared_attr
    def operand9(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 9)

    @classmethod
    def operand_relationship(
        cls, cpg: CPG, operand_number: int, operand_class: Optional[Type[Node]] = None
    ) -> RelationshipProperty:
        """Specifications of the operands of an LLVM instruction.

        Arguments:

        * ``cpg``: The CPG

        * ``operand_number``: The operand number

        * ``operand_class``: The ``Node`` subclass that should be on the other end
          of the use edge/relationship, if it's more specific than LLVM's ``Value``
          class (e.g. the first operand of a ``CallSite``) node should be a
          ``Function``, but the other operands could be any ``Node`` in the LLVM
          AST).
        """
        return _make_operand_relationship(cpg, cls, operand_number, operand_class)


class Alloca(Instruction):
    _kind = NodeKind.ALLOCA

    @declared_attr
    def variable(cls) -> RelationshipProperty:
        return relationship(
            cls.cpg.Variable,
            secondary=cls.cpg.Edge.__table__,
            primaryjoin=and_(
                cls.cpg.Edge.source == cls.uuid,
                cls.cpg.Edge.kind == EdgeKind.CREATES_VAR,
            ),
            secondaryjoin=cls.cpg.Edge.target == cls.cpg.Node.uuid,
            doc="Link to the Variable created by this alloca (if one was created)",
            uselist=False,
        )


class Load(Instruction):
    _kind = NodeKind.LOAD

    @declared_attr
    def pointer_operand(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 0)


class Store(Instruction):
    _kind = NodeKind.STORE

    @declared_attr
    def value_operand(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 0)

    @declared_attr
    def pointer_operand(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 1)


class Ret(Instruction):
    _kind = NodeKind.RET

    @declared_attr
    def value(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 0)


class Resume(Instruction):
    _kind = NodeKind.RESUME

    @declared_attr
    def value(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 0)


class CallSite(Instruction):
    @hybrid_method
    def calls(self, *fns):
        return any(callee in self.callees for callee in fns)

    @calls.expression  # type: ignore[no-redef]
    def calls(cls, *fns):
        return cls.callees.any(cls.cpg.Function.name.in_(fns))

    @declared_attr
    def signatures(cls) -> RelationshipProperty:
        return relationship(
            cls.cpg.Node,
            secondary=cls.cpg.Edge.__table__,
            primaryjoin=cls.uuid == cls.cpg.Edge.target,
            secondaryjoin=and_(
                cls.cpg.Edge.kind == EdgeKind.DATAFLOW_SIGNATURE_FOR_CALLSITE,
                cls.cpg.Edge.source == cls.cpg.Node.uuid,
            ),
            lazy="dynamic",
            doc="Connects a callsite to signatures defined for its callees.",
        )

    @declared_attr
    def argument0(cls) -> RelationshipProperty:
        return cls.argument_relationship(cls.cpg, 0)

    @declared_attr
    def argument1(cls) -> RelationshipProperty:
        return cls.argument_relationship(cls.cpg, 1)

    @declared_attr
    def argument2(cls) -> RelationshipProperty:
        return cls.argument_relationship(cls.cpg, 2)

    @declared_attr
    def argument3(cls) -> RelationshipProperty:
        return cls.argument_relationship(cls.cpg, 3)

    @declared_attr
    def argument4(cls) -> RelationshipProperty:
        return cls.argument_relationship(cls.cpg, 4)

    @declared_attr
    def argument5(cls) -> RelationshipProperty:
        return cls.argument_relationship(cls.cpg, 5)

    @declared_attr
    def argument6(cls) -> RelationshipProperty:
        return cls.argument_relationship(cls.cpg, 6)

    @declared_attr
    def argument7(cls) -> RelationshipProperty:
        return cls.argument_relationship(cls.cpg, 7)

    @declared_attr
    def argument8(cls) -> RelationshipProperty:
        return cls.argument_relationship(cls.cpg, 8)

    @declared_attr
    def argument9(cls) -> RelationshipProperty:
        return cls.argument_relationship(cls.cpg, 9)

    @declared_attr
    def callee_operand(cls) -> RelationshipProperty:
        return _make_use_relationship(
            cls.cpg,
            cls,  # type: ignore[arg-type]
            [cls.cpg.Edge.attributes["is_callee"].as_boolean() == True],
            doc="The callsite's callee operand.",
        )

    @classmethod
    def argument_relationship(cls, cpg: CPG, number: int) -> RelationshipProperty:
        return _make_operand_relationship(
            cpg,
            cls,
            number,
            additional_constraints=[
                cpg.Edge.attributes["is_argument_operand"].as_boolean() == True
            ],
            doc=f"Argument {number} of the callsite.",
        )

    @declared_attr
    def __mapper_args__(cls) -> Dict[str, Any]:
        # NOTE(lb): This class should never be mapped to directly, only as a
        # union of its subclasses.
        if cls._kind == NodeKind.INSTRUCTION:
            return {"polymorphic_identity": None}
        return {"polymorphic_identity": cls._kind}


class Call(CallSite):
    _kind = NodeKind.CALL


class Invoke(CallSite):
    _kind = NodeKind.INVOKE


class Intrinsic(Call):

    overloaded: ClassVar[bool] = False

    @declared_attr
    def __mapper_args__(cls) -> Dict[str, Any]:
        # NOTE(lb): This class should never be mapped to directly, only as a
        # union of its subclasses.
        if cls._kind == NodeKind.CALL:
            return {"polymorphic_identity": None}
        return {"polymorphic_identity": cls._kind}


class Memcpy(Intrinsic):

    _kind = NodeKind.MEMCPY

    overloaded = True

    @declared_attr
    def dest(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 0)

    @declared_attr
    def src(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 1)

    @declared_attr
    def size(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 2)

    @declared_attr
    def volatile(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 3)


class Memset(Intrinsic):

    _kind = NodeKind.MEMSET

    overloaded = True

    @declared_attr
    def pointer(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 0)

    @declared_attr
    def value(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 1)

    @declared_attr
    def size(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 2)

    @declared_attr
    def volatile(cls) -> RelationshipProperty:
        return cls.operand_relationship(cls.cpg, 3)


class UnclassifiedNode(NodeMixin):
    _kind = NodeKind.UNCLASSIFIED_NODE


class ParamBinding(NodeMixin):
    _kind = NodeKind.PARAM_BINDING

    @declared_attr
    def callsite(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.CALL_TO_PARAM_BINDING, cls.cpg.Instruction, backref="binds"
        )

    @declared_attr
    def operand(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.OPERAND_TO_PARAM_BINDING, cls.cpg.Instruction, backref="bound_by"
        )

    @declared_attr
    def argument(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.PARAM_BINDING_TO_ARG, cls.cpg.Argument, backref="bound_by"
        )


class CallReturn(NodeMixin):
    _kind = NodeKind.CALL_RETURN

    @declared_attr
    def callsite(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.CALL_RETURN_TO_CALLER, cls.cpg.Instruction, backref="returns_from"
        )

    @declared_attr
    def bindings(cls) -> RelationshipProperty:
        return cls.edge_relationship(EdgeKind.SAME_CALL, cls.cpg.ParamBinding, backref="return_")

    @declared_attr
    def instruction(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.RETURN_INSTRUCTION_TO_CALL_RETURN,
            cls.cpg.Instruction,
            backref="returns_to",
        )

    @declared_attr
    def value(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.RETURN_VALUE_TO_CALL_RETURN,
            cls.cpg.Instruction,
            backref="returned_by",
        )

    @declared_attr
    def returns_from(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.RETURN_INSTRUCTION_TO_CALL_RETURN, cls.cpg.Instruction
        )


class LocalVariable(Variable):
    _kind = NodeKind.LOCAL_VARIABLE

    @declared_attr
    def parent_function(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.FUNCTION_TO_LOCAL_VARIABLE,
            cls.cpg.Function,
            backref="local_variables",
        )

    @declared_attr
    def llvm_type(cls) -> RelationshipProperty:
        return cls.edge_relationship(EdgeKind.HAS_LLVM_TYPE, cls.cpg.LLVMType)

    @declared_attr
    def as_dwarf(cls) -> RelationshipProperty:
        return cls.edge_relationship(
            EdgeKind.LOCAL_VARIABLE_TO_DWARF_LOCAL_VARIABLE,
            cls.cpg.DWARFLocalVariable,
            backref="as_llvm",
        )

    @property
    def memory_locations(cls) -> Optional[List[MemoryLocation]]:
        if not cls.allocation_site:
            return None
        return cls.allocation_site.allocates

    @declared_attr
    def allocation_site(cls) -> RelationshipProperty:
        return relationship(
            cls.cpg.Alloca,
            secondary=cls.cpg.Edge.__table__,
            primaryjoin=and_(
                cls.cpg.Edge.target == cls.uuid,
                cls.cpg.Edge.kind == EdgeKind.CREATES_VAR,
            ),
            secondaryjoin=cls.cpg.Alloca.uuid == cls.cpg.Edge.source,
            uselist=False,
            doc="Link to the Alloca that created this LocalVariable",
        )
