from enum import Enum, unique
from typing import Final, FrozenSet

# This is imported as a re-export
from .intrinsics import LLVMIntrinsic  # pylint: disable=unused-import

LLVM_INTRINSIC_IDS: Final[FrozenSet[int]] = frozenset(i.value for i in LLVMIntrinsic)


@unique
class Opcode(Enum):
    """Valid values for the ``opcode`` attribute."""

    RET = "ret"
    BR = "br"
    SWITCH = "switch"
    INDIRECTBR = "indirectbr"
    INVOKE = "invoke"
    RESUME = "resume"
    UNREACHABLE = "unreachable"
    CLEANUPRET = "cleanupret"
    CATCHRET = "catchret"
    CATCHPAD = "catchpad"
    CATCHSWITCH = "catchswitch"
    FNEG = "fneg"
    ADD = "add"
    FADD = "fadd"
    SUB = "sub"
    FSUB = "fsub"
    MUL = "mul"
    FMUL = "fmul"
    UDIV = "udiv"
    SDIV = "sdiv"
    FDIV = "fdiv"
    UREM = "urem"
    SREM = "srem"
    FREM = "frem"
    AND = "and"
    OR = "or"
    XOR = "xor"
    ALLOCA = "alloca"
    LOAD = "load"
    STORE = "store"
    ATOMICCMPXCHG = "atomiccmpxchg"
    ATOMICRMW = "atomicrmw"
    FENCE = "fence"
    GETELEMENTPTR = "getelementptr"
    TRUNC = "trunc"
    ZEXT = "zext"
    SEXT = "sext"
    FPTRUNC = "fptrunc"
    FPEXT = "fpext"
    FPTOUI = "fptoui"
    FPTOSI = "fptosi"
    UITOFP = "uitofp"
    SITOFP = "sitofp"
    INTTOPTR = "inttoptr"
    PTRTOINT = "ptrtoint"
    BITCAST = "bitcast"
    ADDRSPACECAST = "addrspacecast"
    ICMP = "icmp"
    FCMP = "fcmp"
    PHI = "phi"
    SELECT = "select"
    CALL = "call"
    CALLSITE = "callsite"  # Dummy Opcode to support CallSite model
    SHL = "shl"
    LSHR = "lshr"
    ASHR = "ashr"
    VAARG = "vaarg"
    EXTRACTELEMENT = "extractelement"
    INSERTELEMENT = "insertelement"
    SHUFFLEVECTOR = "shufflevector"
    EXTRACTVALUE = "extractvalue"
    INSERTVALUE = "insertvalue"
    LANDINGPAD = "landingpad"
    CLEANUPPAD = "cleanuppad"


LLVM_OPCODES = frozenset(i.value for i in Opcode)


@unique
class LLVMConstantData(Enum):
    """Types of constant data in LLVM."""

    CONSTANT_AGGREGATE_ZERO = "ConstantAggregateZero"
    CONSTANT_DATA_ARRAY = "ConstantDataArray"
    CONSTANT_DATA_VECTOR = "ConstantDataVector"
    CONSTANT_FP = "ConstantFP"
    CONSTANT_INT = "ConstantInt"
    CONSTANT_POINTER_NULL = "ConstantPointerNull"
    CONSTANT_TOKEN_NONE = "ConstantTokenNone"
    CONSTANT_UNDEF = "UndefValue"


LLVM_CONSTANT_DATA = frozenset(i.value for i in LLVMConstantData)
