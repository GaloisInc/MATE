import argparse
from enum import Enum, unique
from types import SimpleNamespace
from typing import Dict, Final, FrozenSet, NamedTuple, Set, Union

from mate_common.assertions import mate_assert
from mate_common.models.cpg_types.dwarf import DWARFTypeKind
from mate_common.models.cpg_types.llvm import LLVMConstantData, Opcode

# Our tests pass around SimpleNamespace where our implementation uses an
# argparse namespace.
Namespace = Union[argparse.Namespace, SimpleNamespace]


@unique
class NodeJSON(Enum):
    """JSON attributes of nodes."""

    NODE_KIND = "node_kind"
    LLVM_TYPE = "llvm_type"
    NAME = "name"
    DEMANGLED_NAME = "demangled_name"
    OPCODE = "opcode"
    STRING_VALUE = "string_value"
    PRETTY_STRING = "pretty_string"
    ALIAS_SET_IDENTIFIER = "alias_set_identifier"
    ALLOCATION_TYPE = "allocation_type"
    ALIGNMENT = "alignment"
    ALLOCATION_SIZE_BITS = "allocation_size_bits"
    DEFINITION = "definition"
    MOD_REF_BEHAVIOR = "mod_ref_behavior"
    LOCATION = "location"
    POSITION = "position"
    ARGUMENT_NUMBER = "argument_number"
    ARG_OP_NUMBER = "arg_op_number"
    ALLOCATION_SIZE_BYTES = "allocation_size_bytes"
    MIGHT_BE_NULL = "might_be_null"
    IS_DIRECT = "is_direct"
    INTRINSIC = "intrinsic"
    ALLOCATION_CONTEXT = "allocation_context"
    HAS_INITIALIZER = "has_initializer"
    IS_CONSTANT = "is_constant"
    SIZE_IN_BITS = "size_in_bits"
    STORE_SIZE_IN_BITS = "store_size_in_bits"
    ALLOC_SIZE_IN_BITS = "alloc_size_in_bits"
    ABI_TYPE_ALIGNMENT = "abi_type_alignment"
    CONSTANT_DATA_SUBCLASS = "constant_data_subclass"
    CONSTANT_INT_VALUE = "constant_int_value"
    IS_NULL_VALUE = "is_null_value"
    IS_ONE_VALUE = "is_one_value"
    IS_ALL_ONES_VALUE = "is_all_ones_value"
    IS_ZERO_VALUE = "is_zero_value"
    IS_NORMAL_FP = "is_normal_fp"
    IS_NAN = "is_nan"
    CONTAINS_UNDEF = "contains_undef"
    CAN_TRAP = "can_trap"
    SECTION = "section"
    SSA_NAME = "ssa_name"
    MODULE_NAME = "module_name"
    SOURCE_FILE = "source_file"
    TARGET_TRIPLE = "target_triple"
    DATA_LAYOUT = "data_layout"
    SOURCE_LANGUAGE = "source_language"
    PRODUCER = "producer"
    FILENAME = "filename"
    IS_DECLARATION = "is_declaration"
    LABEL = "label"
    TAGS = "tags"
    CONTEXT = "context"
    CALLER_CONTEXT = "caller_context"
    CALLEE_CONTEXT = "callee_context"
    DEALLOCATOR = "deallocator"
    SOURCE_CODE = "source_code"

    # From quotidian:
    SOURCE = "source"
    ADDRESS_TAKEN = "address_taken"
    FUNC_REFERENCE = "func_reference"
    VA_START = "va_start"
    CAN_FALLTHROUGH = "can_fallthrough"
    ENDS_IN_RETURN = "ends_in_return"
    VA_END = "va_end"
    FLAGS = "flags"
    FUNC_OFFSET = "func_offset"
    HAS_INLINE_ASM = "has_inline_asm"
    INSTRS = "instrs"
    NUMBER = "number"
    OFFSET = "offset"
    OPERAND = "operand"
    PREDS = "preds"
    VA = "va"
    SUCCS = "succs"
    SYMBOL = "symbol"
    UNPAIRED = "unpaired"
    TYPE = "type"
    SOURCE_LOCATION = "source_location"
    SOURCE_SCOPE = "source_scope"
    DWARF_TYPE = "dwarf_type"
    UNROLLED_DWARF_TYPE = "unrolled_dwarf_type"
    TYPE_ID = "type_id"
    DWARF_LOCATION = "dwarf_location"
    DWARF_SCOPE = "dwarf_scope"
    ARTIFICIAL = "artificial"
    FROM_VARIADIC_TEMPLATE = "from_variadic_template"
    ORIGINAL_NAME = "original_name"
    PARAMETER_INDEX = "parameter_index"
    VARIADIC_INDEX = "variadic_index"
    TEMPLATE_INDEX = "template_index"
    IS_MANGLED = "is_mangled"
    SIZE = "size"
    MNEMONIC = "mnemonic"
    ASM = "asm"
    USED_REGISTERS = "used_registers"
    USED_MEMORY = "used_memory"
    LOCAL_TO_UNIT = "local_to_unit"
    DEFINITION_LOCATION = "definition_location"
    LINKAGE_NAME = "linkage_name"
    FRAME_INFO = "frame_info"
    SYMBOLS = "symbols"
    THREAD_LOCAL = "thread_local"
    PROLOGUES = "prologues"
    EPILOGUES = "epilogues"
    IS_PROLOGUE_INSERTION_BLOCK = "is_prologue_insertion_block"
    IS_EPILOGUE_INSERTION_BLOCK = "is_epilogue_insertion_block"
    MEMBERS = "members"
    RTTI_VA = "rtti_va"
    CLASS_NAME = "class_name"

    # From quotidian, but should be removed very soon:
    PARAMETER = "parameter"
    ARG = "arg"
    KIND = "kind"


mate_assert(all(variant.name.lower() == variant.value for variant in NodeJSON))

NODE_JSON: Final[FrozenSet[str]] = frozenset({k.value for k in NodeJSON})


def _make_dwarf_type_name(s: str) -> str:
    return "".join(s0.capitalize() for s0 in s.split("_")) + "Type"


@unique
class NodeKind(Enum):
    """Valid values for the ``node_kind`` attribute.

    These must match the map in ASTGraphWriter.
    """

    FUNCTION = "Function"
    BLOCK = "Block"
    MEMORY_LOCATION = "MemoryLocation"
    UNCLASSIFIED_NODE = "UnclassifiedNode"
    LLVM_TYPE = "LLVMType"
    VARIABLE = "Variable"
    ARGUMENT = "Argument"
    LOCAL_VARIABLE = "LocalVariable"
    PARAM_BINDING = "ParamBinding"
    CALL_RETURN = "CallReturn"
    GLOBAL_VARIABLE = "GlobalVariable"
    MODULE = "Module"
    TRANSLATION_UNIT = "TranslationUnit"

    INSTRUCTION = "Instruction"
    ALLOCA = Opcode.ALLOCA.value.capitalize()
    CALL = Opcode.CALL.value.capitalize()
    LOAD = Opcode.LOAD.value.capitalize()
    INVOKE = Opcode.INVOKE.value.capitalize()
    RESUME = Opcode.RESUME.value.capitalize()
    RET = Opcode.RET.value.capitalize()
    STORE = Opcode.STORE.value.capitalize()
    MEMCPY = "Memcpy"
    MEMSET = "Memset"

    CONSTANT = "Constant"
    CONSTANT_FP = LLVMConstantData.CONSTANT_FP.value
    CONSTANT_INT = LLVMConstantData.CONSTANT_INT.value
    # We break with LLVM's naming of "undef" for internal consistency
    CONSTANT_UNDEF = "ConstantUndef"
    # Constant string is not an LLVM-level concept
    CONSTANT_STRING = "ConstantString"

    ASM_GLOBAL_VARIABLE = "ASMGlobalVariable"
    MACHINE_BASIC_BLOCK = "MachineBasicBlock"
    MACHINE_FUNCTION = "MachineFunction"
    MACHINE_INSTR = "MachineInstr"
    ASM_BLOCK = "ASMBlock"
    ASM_INST = "ASMInst"
    PLT_STUB = "PLTStub"
    VTABLE = "VTable"

    # NOTE(lb): DWARFType is never instantiated directly (it is partitioned by
    # its subclasses), but we keep it as a kind for consistency (e.g. when
    # generating relationships, checking the endpoints against endpoints.json)
    DWARF_TYPE = "DWARFType"
    BASIC_TYPE = _make_dwarf_type_name(DWARFTypeKind.BASIC.value)
    COMPOSITE_TYPE = _make_dwarf_type_name(DWARFTypeKind.COMPOSITE.value)
    COMPOSITE_CACHED_TYPE = _make_dwarf_type_name(DWARFTypeKind.COMPOSITE_CACHED.value)
    STRUCTURE_TYPE = _make_dwarf_type_name(DWARFTypeKind.STRUCTURE.value)
    ARRAY_TYPE = _make_dwarf_type_name(DWARFTypeKind.ARRAY.value)
    ENUM_TYPE = _make_dwarf_type_name(DWARFTypeKind.ENUM.value)
    UNION_TYPE = _make_dwarf_type_name(DWARFTypeKind.UNION.value)
    CLASS_TYPE = _make_dwarf_type_name(DWARFTypeKind.CLASS.value)
    DERIVED_TYPE = _make_dwarf_type_name(DWARFTypeKind.DERIVED.value)
    SUBROUTINE_TYPE = _make_dwarf_type_name(DWARFTypeKind.SUBROUTINE.value)

    DWARF_LOCAL_VARIABLE = "DWARFLocalVariable"
    DWARF_ARGUMENT = "DWARFArgument"

    DATAFLOW_SIGNATURE = "DataflowSignature"
    INPUT_SIGNATURE = "InputSignature"
    OUTPUT_SIGNATURE = "OutputSignature"


mate_assert(
    all(variant.name.replace("_", "").lower() == variant.value.lower() for variant in NodeKind)
)


NODE_KINDS: Final[FrozenSet[str]] = frozenset({k.value for k in NodeKind})


CONSTANT_NODES: Final[FrozenSet[NodeKind]] = frozenset(
    {
        NodeKind.CONSTANT,
        NodeKind.CONSTANT_FP,
        NodeKind.CONSTANT_INT,
        NodeKind.CONSTANT_UNDEF,
        NodeKind.CONSTANT_STRING,
    }
)


INTRINSIC_NODES: Final[FrozenSet[NodeKind]] = frozenset({NodeKind.MEMCPY, NodeKind.MEMSET})


CALL_NODES: Final[FrozenSet[NodeKind]] = frozenset(
    {NodeKind.CALL, NodeKind.INVOKE} | INTRINSIC_NODES
)


INSTRUCTION_NODES: Final[FrozenSet[NodeKind]] = frozenset(
    {
        NodeKind.INSTRUCTION,
        NodeKind.ALLOCA,
        NodeKind.RESUME,
        NodeKind.RET,
        NodeKind.LOAD,
        NodeKind.STORE,
    }
    | CALL_NODES
)

LLVM_NODES: Final[FrozenSet[NodeKind]] = frozenset(
    INSTRUCTION_NODES
    | CONSTANT_NODES
    | {
        NodeKind.FUNCTION,
        NodeKind.BLOCK,
        NodeKind.INSTRUCTION,
        NodeKind.LLVM_TYPE,
        NodeKind.ARGUMENT,
        NodeKind.LOCAL_VARIABLE,
        NodeKind.GLOBAL_VARIABLE,
        NodeKind.MODULE,
        NodeKind.TRANSLATION_UNIT,
        NodeKind.UNCLASSIFIED_NODE,
    }
)

ANALYSIS_NODES: Final[FrozenSet[NodeKind]] = frozenset(
    {
        NodeKind.MEMORY_LOCATION,
        NodeKind.PARAM_BINDING,
        NodeKind.CALL_RETURN,
        NodeKind.DATAFLOW_SIGNATURE,
        NodeKind.INPUT_SIGNATURE,
        NodeKind.OUTPUT_SIGNATURE,
    }
)

LLVM_LEVEL_NODES: Final[FrozenSet[NodeKind]] = frozenset(LLVM_NODES.union(ANALYSIS_NODES))


DWARF_TYPE_NODES: Final[FrozenSet[NodeKind]] = frozenset(
    {
        NodeKind.DWARF_TYPE,
        NodeKind.BASIC_TYPE,
        NodeKind.COMPOSITE_TYPE,
        NodeKind.COMPOSITE_CACHED_TYPE,
        NodeKind.STRUCTURE_TYPE,
        NodeKind.ARRAY_TYPE,
        NodeKind.ENUM_TYPE,
        NodeKind.UNION_TYPE,
        NodeKind.CLASS_TYPE,
        NodeKind.DERIVED_TYPE,
        NodeKind.SUBROUTINE_TYPE,
    }
)

DWARF_TYPE_KIND_TO_NODE_KIND: Final[Dict[DWARFTypeKind, NodeKind]] = {
    k: NodeKind(_make_dwarf_type_name(k.value)) for k in DWARFTypeKind
}


DWARF_FEATURE_NODES: Final[FrozenSet[NodeKind]] = frozenset(
    {
        NodeKind.DWARF_LOCAL_VARIABLE,
        NodeKind.DWARF_ARGUMENT,
    }
)


@unique
class MATEComponent(Enum):
    """An enumeration of known node-generating components of MATE."""

    # NOTE(ww): These values are currently unstructured, and should not be
    # understood as the top-most component responsible for *emitting* nodes;
    # instead, they represent the component most responsible for the *content*
    # of a particular kind of node.

    AST_GRAPH_WRITER = "ASTGraphWriter"
    HEADACHE = "Headache"
    ASPIRIN = "Aspirin"
    WEDLOCK = "Wedlock"
    SIGNATURE = "Signature"


mate_assert(
    all(variant.name.replace("_", "").lower() == variant.value.lower() for variant in MATEComponent)
)

NODE_PROVENANCE: Final[Dict[NodeKind, MATEComponent]] = {
    **{k: MATEComponent.AST_GRAPH_WRITER for k in LLVM_LEVEL_NODES},
    **{k: MATEComponent.HEADACHE for k in DWARF_TYPE_NODES},
    **{k: MATEComponent.HEADACHE for k in DWARF_FEATURE_NODES},
    **{
        NodeKind.MEMORY_LOCATION: MATEComponent.AST_GRAPH_WRITER,
        NodeKind.PARAM_BINDING: MATEComponent.AST_GRAPH_WRITER,
        NodeKind.CALL_RETURN: MATEComponent.AST_GRAPH_WRITER,
        NodeKind.GLOBAL_VARIABLE: MATEComponent.AST_GRAPH_WRITER,
        NodeKind.VARIABLE: MATEComponent.AST_GRAPH_WRITER,
        # TODO(#641): Module/TranslationUnit are _not_ from ASTGraphWriter,
        # despite being LLVM-level.
        NodeKind.MODULE: MATEComponent.HEADACHE,
        NodeKind.TRANSLATION_UNIT: MATEComponent.HEADACHE,
        NodeKind.ASM_GLOBAL_VARIABLE: MATEComponent.ASPIRIN,
        NodeKind.MACHINE_BASIC_BLOCK: MATEComponent.WEDLOCK,
        NodeKind.MACHINE_FUNCTION: MATEComponent.WEDLOCK,
        NodeKind.MACHINE_INSTR: MATEComponent.WEDLOCK,
        NodeKind.ASM_BLOCK: MATEComponent.ASPIRIN,
        NodeKind.ASM_INST: MATEComponent.ASPIRIN,
        NodeKind.PLT_STUB: MATEComponent.ASPIRIN,
        # NOTE(ww): This isn't exactly right, but it's close enough.
        NodeKind.VTABLE: MATEComponent.ASPIRIN,
        NodeKind.INPUT_SIGNATURE: MATEComponent.SIGNATURE,
        NodeKind.OUTPUT_SIGNATURE: MATEComponent.SIGNATURE,
        NodeKind.DATAFLOW_SIGNATURE: MATEComponent.SIGNATURE,
    },
}


mate_assert(all(NODE_PROVENANCE.get(kind) is not None for kind in NodeKind))


@unique
class EdgeJSON(Enum):
    """JSON attributes for edges."""

    EDGE_KIND = "edge_kind"
    OPERAND_NUMBER = "operand_number"


mate_assert(all(variant.name.lower() == variant.value for variant in EdgeJSON))


@unique
class EdgeKind(Enum):
    FUNCTION_TO_ENTRY_BLOCK = "FunctionToEntryBlock"
    BLOCK_TO_PARENT_FUNCTION = "BlockToParentFunction"
    BLOCK_TO_SUCCESSOR_BLOCK = "BlockToSuccessorBlock"
    BLOCK_TO_ENTRY_INSTRUCTION = "BlockToEntryInstruction"
    BLOCK_TO_TERMINATOR_INSTRUCTION = "BlockToTerminatorInstruction"
    INSTRUCTION_TO_PARENT_BLOCK = "InstructionToParentBlock"
    INSTRUCTION_TO_SUCCESSOR_INSTRUCTION = "InstructionToSuccessorInstruction"
    VALUE_DEFINITION_TO_USE = "ValueDefinitionToUse"
    LOAD_POINTER_TO_VALUE = "LoadPointerToValue"
    VALUE_TO_STORE_POINTER = "ValueToStorePointer"
    BLOCK_TO_CONTROL_DEPENDENT_BLOCK = "BlockToControlDependentBlock"
    TERMINATOR_INSTRUCTION_TO_CONTROL_DEPENDENT_INSTRUCTION = (
        "TerminatorInstructionToControlDependentInstruction"
    )
    FUNCTION_ENTRY_TO_CONTROL_DEPENDENT_BLOCK = "FunctionEntryToControlDependentBlock"
    FUNCTION_ENTRY_TO_CONTROL_DEPENDENT_INSTRUCTION = "FunctionEntryToControlDependentInstruction"
    CLOBBER_INSTRUCTION_TO_VALUE_LOAD = "ClobberInstructionToValueLoad"
    DEFINITION_TO_VALUE_LOAD = "DefinitionToValueLoad"
    CALL_TO_FUNCTION = "CallToFunction"
    CALLGRAPH = "Callgraph"
    ALLOCATES = "Allocates"
    CREATES_VAR = "CreatesVar"
    MAY_ALIAS = "MayAlias"
    MUST_ALIAS = "MustAlias"
    SUBREGION = "Subregion"
    CONTAINS = "Contains"
    POINTS_TO = "PointsTo"
    LOAD_MEMORY = "LoadMemory"
    STORE_MEMORY = "StoreMemory"
    FUNCTION_TO_ARGUMENT = "FunctionToArgument"
    FUNCTION_TO_LOCAL_VARIABLE = "FunctionToLocalVariable"
    CALL_TO_PARAM_BINDING = "CallToParamBinding"
    OPERAND_TO_PARAM_BINDING = "OperandToParamBinding"
    PARAM_BINDING_TO_ARG = "ParamBindingToArg"
    RETURN_INSTRUCTION_TO_CALL_RETURN = "ReturnInstructionToCallReturn"
    RETURN_VALUE_TO_CALL_RETURN = "ReturnValueToCallReturn"
    CALL_RETURN_TO_CALLER = "CallReturnToCaller"
    SAME_CALL = "SameCall"
    GLOBAL_TO_INITIALIZER = "GlobalToInitializer"
    MODULE_TO_TRANSLATION_UNIT = "ModuleToTranslationUnit"

    HAS_LLVM_TYPE = "HasLLVMType"
    HAS_DWARF_TYPE = "HasDWARFType"
    DWARF_TYPE_TO_BASE_TYPE = "DWARFTypeToBaseType"
    DWARF_TYPE_TO_MEMBER_TYPE = "DWARFTypeToMemberType"
    DWARF_TYPE_TO_RECURSIVE_TYPE = "DWARFTypeToRecursiveType"
    DWARF_TYPE_TO_TEMPLATE_PARAM_TYPE = "DWARFTypeToTemplateParamType"
    DWARF_TYPE_TO_RETURN_TYPE = "DWARFTypeToReturnType"
    DWARF_TYPE_TO_PARAM_TYPE = "DWARFTypeToParamType"
    DWARF_TYPE_TO_PARENT_TYPE = "DWARFTypeToParentType"
    MI_BLOCK_TO_IR_BLOCK = "MIBlockToIRBlock"
    MI_BLOCK_TO_ASM_BLOCK = "MIBlockToASMBlock"
    MI_FUNCTION_TO_IR_FUNCTION = "MIFunctionToIRFunction"
    MI_FUNCTION_TO_DWARF_ARGUMENT = "MIFunctionToDWARFArgument"
    MI_FUNCTION_TO_DWARF_LOCAL_VARIABLE = "MIFunctionToDWARFLocalVariable"
    MI_FUNCTION_TO_VTABLE = "MIFunctionToVTable"

    LOCAL_VARIABLE_TO_DWARF_LOCAL_VARIABLE = "LocalVariableToDWARFLocalVariable"
    ARGUMENT_TO_DWARF_ARGUMENT = "ArgumentToDWARFArgument"

    FUNCTION_TO_PLT_STUB = "FunctionToPLTStub"
    PLT_STUB_TO_VTABLE = "PLTStubToVTable"

    DATAFLOW_SIGNATURE = "DataflowSignature"
    DIRECT_DATAFLOW_SIGNATURE = "DirectDataflowSignature"
    INDIRECT_DATAFLOW_SIGNATURE = "IndirectDataflowSignature"
    CONTROL_DATAFLOW_SIGNATURE = "ControlDataflowSignature"
    DATAFLOW_SIGNATURE_FOR_CALLSITE = "DataflowSignatureForCallSite"
    DATAFLOW_SIGNATURE_FOR_FUNCTION = "DataflowSignatureForFunction"


mate_assert(
    all(variant.name.replace("_", "").lower() == variant.value.lower() for variant in EdgeKind)
)

EDGE_KINDS: Final[FrozenSet[str]] = frozenset({k.value for k in EdgeKind})

AST_EDGES: Final[FrozenSet[EdgeKind]] = frozenset(
    {
        EdgeKind.BLOCK_TO_PARENT_FUNCTION,
        EdgeKind.BLOCK_TO_ENTRY_INSTRUCTION,
        EdgeKind.INSTRUCTION_TO_PARENT_BLOCK,
        EdgeKind.FUNCTION_TO_ARGUMENT,
        EdgeKind.FUNCTION_TO_LOCAL_VARIABLE,
        EdgeKind.GLOBAL_TO_INITIALIZER,
        EdgeKind.MODULE_TO_TRANSLATION_UNIT,
        EdgeKind.HAS_LLVM_TYPE,
    }
)

LOCAL_CONTROL_FLOW_FORWARD: Final[FrozenSet[EdgeKind]] = frozenset(
    {
        EdgeKind.FUNCTION_TO_ENTRY_BLOCK,
        EdgeKind.BLOCK_TO_ENTRY_INSTRUCTION,
        EdgeKind.INSTRUCTION_TO_SUCCESSOR_INSTRUCTION,
    }
)

CONTROL_FLOW_FORWARD: Final[FrozenSet[EdgeKind]] = frozenset(
    LOCAL_CONTROL_FLOW_FORWARD.union(
        {
            EdgeKind.CALL_TO_FUNCTION,
            EdgeKind.RETURN_INSTRUCTION_TO_CALL_RETURN,
            EdgeKind.CALL_RETURN_TO_CALLER,
        }
    )
)

DATA_FLOW_FORWARD: Final[FrozenSet[EdgeKind]] = frozenset(
    {
        EdgeKind.VALUE_DEFINITION_TO_USE,
        EdgeKind.DEFINITION_TO_VALUE_LOAD,
        EdgeKind.CLOBBER_INSTRUCTION_TO_VALUE_LOAD,
        EdgeKind.LOAD_MEMORY,
        EdgeKind.STORE_MEMORY,
        EdgeKind.OPERAND_TO_PARAM_BINDING,
        EdgeKind.PARAM_BINDING_TO_ARG,
        EdgeKind.RETURN_VALUE_TO_CALL_RETURN,
        EdgeKind.CALL_RETURN_TO_CALLER,
        EdgeKind.DATAFLOW_SIGNATURE,
        EdgeKind.DIRECT_DATAFLOW_SIGNATURE,
        EdgeKind.INDIRECT_DATAFLOW_SIGNATURE,
        EdgeKind.CONTROL_DATAFLOW_SIGNATURE,
    }
)

DATA_FLOW_FORWARD_THIN: Final[FrozenSet[EdgeKind]] = frozenset(
    {
        EdgeKind.DATAFLOW_SIGNATURE,
        # Only include direct dataflow signature edges
        EdgeKind.DIRECT_DATAFLOW_SIGNATURE,
        EdgeKind.LOAD_MEMORY,
        EdgeKind.STORE_MEMORY,
        EdgeKind.OPERAND_TO_PARAM_BINDING,
        EdgeKind.PARAM_BINDING_TO_ARG,
        EdgeKind.RETURN_VALUE_TO_CALL_RETURN,
        EdgeKind.CALL_RETURN_TO_CALLER,
    }
)

CONTROL_DEP_FORWARD: Final[FrozenSet[EdgeKind]] = frozenset(
    {
        EdgeKind.FUNCTION_ENTRY_TO_CONTROL_DEPENDENT_BLOCK,
        EdgeKind.BLOCK_TO_CONTROL_DEPENDENT_BLOCK,
        EdgeKind.FUNCTION_ENTRY_TO_CONTROL_DEPENDENT_INSTRUCTION,
        EdgeKind.TERMINATOR_INSTRUCTION_TO_CONTROL_DEPENDENT_INSTRUCTION,
    }
)

INFO_FLOW_FORWARD: Final[FrozenSet[EdgeKind]] = frozenset(
    DATA_FLOW_FORWARD.union(CONTROL_DEP_FORWARD)
)

POINTS_TO: Final[FrozenSet[EdgeKind]] = frozenset(
    {
        EdgeKind.POINTS_TO,
        EdgeKind.MAY_ALIAS,
        EdgeKind.MUST_ALIAS,
        EdgeKind.SUBREGION,
    }
)


class Endpoints(NamedTuple):
    sources: Set[NodeKind]
    targets: Set[NodeKind]


@unique
class Relationship(Enum):
    ONE_TO_ONE = "one-to-one"
    ONE_TO_MANY = "one-to-many"
    MANY_TO_ONE = "many-to-one"
    MANY_TO_MANY = "many-to-many"


mate_assert(
    all(variant.name.replace("_", "-").lower() == variant.value.lower() for variant in Relationship)
)
