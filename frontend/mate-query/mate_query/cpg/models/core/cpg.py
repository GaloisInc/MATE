# NOTE(lb) With the resolution of #1044, the majority of this module will
# disappear.
from __future__ import annotations

from typing import List, Optional, Type

from mate_common.assertions import mate_assert

# TODO(ww): Something about Type[...] really screws with pylint here.
from mate_query.cpg.models.core.edge import Edge  # pylint: disable=unused-import
from mate_query.cpg.models.core.node import Node  # pylint: disable=unused-import
from mate_query.cpg.models.core.node import Node as BaseNode
from mate_query.cpg.models.node.analysis import (
    DataflowSignature,
    InputSignature,
    MemoryLocation,
    OutputSignature,
)
from mate_query.cpg.models.node.ast.bin import ASMBlock, ASMGlobalVariable, ASMInst, PLTStub, VTable
from mate_query.cpg.models.node.ast.llvm import (
    Alloca,
    Argument,
    Block,
    Call,
    CallReturn,
    CallSite,
    Constant,
    ConstantFP,
    ConstantInt,
    ConstantString,
    ConstantUndef,
    Function,
    GlobalVariable,
    Instruction,
    Intrinsic,
    Invoke,
    LLVMType,
    Load,
    LocalVariable,
    Memcpy,
    Memset,
    Module,
    ParamBinding,
    Resume,
    Ret,
    Store,
    UnclassifiedNode,
    Variable,
)
from mate_query.cpg.models.node.ast.mc import MachineBasicBlock, MachineFunction, MachineInstr
from mate_query.cpg.models.node.dwarf import (
    ArrayType,
    BasicType,
    ClassType,
    CompositeCachedType,
    CompositeType,
    DerivedType,
    DWARFArgument,
    DWARFLocalVariable,
    DWARFType,
    EnumType,
    StructureType,
    SubroutineType,
    UnionType,
)
from mate_query.cpg.models.node.translation_unit import TranslationUnit


# TODO(1044): Delete this class, merge into Postgres CPG class
class BaseCPG:
    Node: Type[Node]
    Edge: Type[Edge]

    ASMBlock: Type[ASMBlock]
    ASMGlobalVariable: Type[ASMGlobalVariable]
    ASMInst: Type[ASMInst]
    Alloca: Type[Alloca]
    Argument: Type[Argument]
    ArrayType: Type[ArrayType]
    BasicType: Type[BasicType]
    Block: Type[Block]
    Call: Type[Call]
    CallReturn: Type[CallReturn]
    CallSite: Type[CallSite]
    ClassType: Type[ClassType]
    CompositeCachedType: Type[CompositeCachedType]
    CompositeType: Type[CompositeType]
    Constant: Type[Constant]
    ConstantFP: Type[ConstantFP]
    ConstantInt: Type[ConstantInt]
    ConstantString: Type[ConstantString]
    ConstantUndef: Type[ConstantUndef]
    DWARFType: Type[DWARFType]
    DWARFArgument: Type[DWARFArgument]
    DWARFLocalVariable: Type[DWARFLocalVariable]
    DataflowSignature: Type[DataflowSignature]
    DerivedType: Type[DerivedType]
    EnumType: Type[EnumType]
    Function: Type[Function]
    GlobalVariable: Type[GlobalVariable]
    LocalVariable: Type[LocalVariable]
    InputSignature: Type[InputSignature]
    Instruction: Type[Instruction]
    Intrinsic: Type[Intrinsic]
    Invoke: Type[Invoke]
    LLVMType: Type[LLVMType]
    Load: Type[Load]
    MachineBasicBlock: Type[MachineBasicBlock]
    MachineFunction: Type[MachineFunction]
    MachineInstr: Type[MachineInstr]
    Memcpy: Type[Memcpy]
    MemoryLocation: Type[MemoryLocation]
    Memset: Type[Memset]
    Module: Type[Module]
    OutputSignature: Type[OutputSignature]
    ParamBinding: Type[ParamBinding]
    PLTStub: Type[PLTStub]
    Resume: Type[Resume]
    Ret: Type[Ret]
    Store: Type[Store]
    StructureType: Type[StructureType]
    SubroutineType: Type[SubroutineType]
    TranslationUnit: Type[TranslationUnit]
    UnclassifiedNode: Type[UnclassifiedNode]
    UnionType: Type[UnionType]
    Variable: Type[Variable]
    VTable: Type[VTable]

    _node_model_classes: List[Type[BaseNode]]

    def _attach_node_models(self, name: str) -> None:
        mate_assert(self.Node is not None)

        def make_node_class(
            cpg_parent: Type[BaseNode], model_parent: Type, class_name: Optional[str] = None
        ) -> Type:
            mate_assert(cpg_parent != model_parent)
            if class_name is None:
                class_name = model_parent.__name__

            return type(
                class_name,
                (model_parent, cpg_parent),
                {"cpg": self, "build_id": name},
            )

        # NOTE(lb): These classes are in reverse relationship dependency order,
        # i.e. if B has a relationship that mentions A, then A comes before B.
        #
        # Other than that, they're grouped by parent module and inheritance
        # hierarchy.
        self.TranslationUnit = make_node_class(self.Node, TranslationUnit)
        self.DWARFArgument = make_node_class(self.Node, DWARFArgument)
        self.DWARFLocalVariable = make_node_class(self.Node, DWARFLocalVariable)
        self.DWARFType = make_node_class(self.Node, DWARFType)
        self.ArrayType = make_node_class(self.DWARFType, ArrayType)
        self.BasicType = make_node_class(self.DWARFType, BasicType)
        self.ClassType = make_node_class(self.DWARFType, ClassType)
        self.CompositeCachedType = make_node_class(self.DWARFType, CompositeCachedType)
        self.CompositeType = make_node_class(self.DWARFType, CompositeType)
        self.DerivedType = make_node_class(self.DWARFType, DerivedType)
        self.EnumType = make_node_class(self.DWARFType, EnumType)
        self.StructureType = make_node_class(self.DWARFType, StructureType)
        self.SubroutineType = make_node_class(self.DWARFType, SubroutineType)
        self.UnionType = make_node_class(self.DWARFType, UnionType)

        self.ASMInst = make_node_class(self.Node, ASMInst)
        self.ASMBlock = make_node_class(self.Node, ASMBlock)
        self.ASMGlobalVariable = make_node_class(self.Node, ASMGlobalVariable)
        self.VTable = make_node_class(self.Node, VTable)
        self.PLTStub = make_node_class(self.Node, PLTStub)

        self.MachineInstr = make_node_class(self.Node, MachineInstr)
        self.MachineBasicBlock = make_node_class(self.Node, MachineBasicBlock)
        self.MachineFunction = make_node_class(self.Node, MachineFunction)

        self.Constant = make_node_class(self.Node, Constant)
        self.ConstantFP = make_node_class(self.Constant, ConstantFP)
        self.ConstantInt = make_node_class(self.Constant, ConstantInt)
        self.ConstantString = make_node_class(self.Constant, ConstantString)
        self.ConstantUndef = make_node_class(self.Constant, ConstantUndef)

        self.Variable = make_node_class(self.Node, Variable)
        self.Instruction = make_node_class(self.Node, Instruction)
        # NOTE(lb): CallSite and Intrinsic need to pass class_name explicitly
        # because they don't have _kind attributes (they are "union" classes,
        # they don't have a corresponding node kind).
        self.CallSite = make_node_class(self.Instruction, CallSite, class_name="CallSite")
        self.Call = make_node_class(self.CallSite, Call)
        self.Invoke = make_node_class(self.CallSite, Invoke)
        self.Intrinsic = make_node_class(self.Call, Intrinsic, class_name="Instrinsic")
        self.Memcpy = make_node_class(self.Intrinsic, Memcpy)
        self.Memset = make_node_class(self.Intrinsic, Memset)
        self.Alloca = make_node_class(self.Instruction, Alloca)
        self.Load = make_node_class(self.Instruction, Load)
        self.Resume = make_node_class(self.Instruction, Resume)
        self.Ret = make_node_class(self.Instruction, Ret)
        self.Store = make_node_class(self.Instruction, Store)

        self.Module = make_node_class(self.Node, Module)
        self.Argument = make_node_class(self.Variable, Argument)
        self.Block = make_node_class(self.Node, Block)
        self.Function = make_node_class(self.Node, Function)
        self.GlobalVariable = make_node_class(self.Variable, GlobalVariable)
        self.LLVMType = make_node_class(self.Node, LLVMType)
        self.LocalVariable = make_node_class(self.Variable, LocalVariable)
        self.MemoryLocation = make_node_class(self.Node, MemoryLocation)
        self.DataflowSignature = make_node_class(self.Node, DataflowSignature)
        self.InputSignature = make_node_class(self.Node, InputSignature)
        self.OutputSignature = make_node_class(self.Node, OutputSignature)
        self.UnclassifiedNode = make_node_class(self.Node, UnclassifiedNode)
        self.ParamBinding = make_node_class(self.Node, ParamBinding)
        self.CallReturn = make_node_class(self.Node, CallReturn)

        # These are the groups of interesting inheritance hierarchies, with the
        # root at the top of each subtree.

        self._node_model_classes = [
            self.ASMBlock,
            self.ASMGlobalVariable,
            self.ASMInst,
            self.Variable,
            self.Alloca,
            self.Argument,
            self.ArrayType,
            self.BasicType,
            self.Block,
            self.Call,
            self.CallReturn,
            self.CallSite,
            self.ClassType,
            self.CompositeCachedType,
            self.CompositeType,
            self.Constant,
            self.ConstantFP,
            self.ConstantInt,
            self.ConstantString,
            self.ConstantUndef,
            self.DWARFType,
            self.DWARFArgument,
            self.DWARFLocalVariable,
            self.DataflowSignature,
            self.DerivedType,
            self.EnumType,
            self.Function,
            self.GlobalVariable,
            self.LocalVariable,
            self.InputSignature,
            self.Instruction,
            self.Intrinsic,
            self.Invoke,
            self.LLVMType,
            self.Load,
            self.MachineBasicBlock,
            self.MachineFunction,
            self.MachineInstr,
            self.Memcpy,
            self.MemoryLocation,
            self.Memset,
            self.Module,
            self.OutputSignature,
            self.ParamBinding,
            self.PLTStub,
            self.Resume,
            self.Ret,
            self.Store,
            self.StructureType,
            self.SubroutineType,
            self.TranslationUnit,
            self.UnclassifiedNode,
            self.UnionType,
            self.VTable,
        ]
