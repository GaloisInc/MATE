#include "Nodes.h"

namespace mate {

auto instruction_node_type(const llvm::Instruction& instruction) -> NodeType {
  const auto* call_site = llvm::dyn_cast<llvm::CallBase>(&instruction);
  if (call_site != nullptr) {
    if (call_site->getCalledFunction() != nullptr) {
      const auto& called_function = *call_site->getCalledFunction();
      auto iid = (unsigned)called_function.getIntrinsicID();
      if (iid == llvm::Intrinsic::memcpy) {
        return kMemcpy;
      }
      if (iid == llvm::Intrinsic::memset) {
        return kMemset;
      }
    }
    switch (instruction.getOpcode()) {
      case llvm::Instruction::Call: {
        return kCall;
      }
      case llvm::Instruction::Invoke: {
        return kInvoke;
      }
      default: {  // unreachable: call and invoke are the only call opcodes
        assert(false);
      }
    }
    assert(false);  // unreachable (default case)
  }
  switch (instruction.getOpcode()) {
    case llvm::Instruction::Alloca: {
      return kAlloca;
    }
    case llvm::Instruction::Load: {
      return kLoad;
    }
    case llvm::Instruction::Store: {
      return kStore;
    }
    case llvm::Instruction::Resume: {
      return kResume;
    }
    case llvm::Instruction::Ret: {
      return kRet;
    }
    default: {
      return kInstruction;
    }
  }
  assert(false);  // unreachable (default case)
}

auto value_node_type(const llvm::Value& value) -> NodeType {
  const auto subclass_id = value.getValueID();
  switch (subclass_id) {
    case llvm::Value::BasicBlockVal: {
      return kBlock;
    }
    case llvm::Value::ArgumentVal: {
      return kArgument;
    }
    case llvm::Value::ConstantIntVal: {
      return kConstantInt;
    }
    case llvm::Value::ConstantFPVal: {
      return kConstantFP;
    }
    case llvm::Value::UndefValueVal: {
      return kConstantUndef;
    }
    case llvm::Value::FunctionVal: {
      return kFunction;
    }
    case llvm::Value::GlobalVariableVal: {
      return kGlobalVariable;
    }
  }
  if (subclass_id >= llvm::Value::InstructionVal) {
    return instruction_node_type(llvm::cast<llvm::Instruction>(value));
  }

  if (llvm::isa<llvm::Constant>(value)) {
    if (llvm::isa<llvm::ConstantDataSequential>(value) &&
        llvm::cast<llvm::ConstantDataSequential>(value).isCString()) {
      return kConstantString;
    }
    return kConstant;
  }
  return kUnclassifiedNode;
}

// Is this node of a kind that should have an associated llvm::Value?
auto Node::isValue() const -> bool {
  return type == kFunction || type == kBlock || type == kInstruction ||
         type == kGlobalVariable || type == kConstantString ||
         type == kArgument || type == kLocalVariable ||
         type == kUnclassifiedNode ||
         constant_kinds.find(type) != constant_kinds.end() ||
         instruction_kinds.find(type) != instruction_kinds.end();
}

void Node::checkValue() const {
  assert(isValue());
  assert(value != nullptr);
  const auto* val = (llvm::Value*)value;
  assert(llvm::isa<llvm::Value>(*val));
  // NOTE(lb): Local variables are a bit odd in that they are represented by
  // their DILocalVariable nodes.
  assert(type == value_node_type(*val) || type == kLocalVariable);

  // Check that the opcode matches the kind
  if (instruction_kinds.find(type) != instruction_kinds.end()) {
    assert(llvm::isa<llvm::Instruction>(*val));
    const auto opc = llvm::cast<llvm::Instruction>(*val).getOpcode();

    const auto valid_node_types_it = opcode_node_type_map.find(opc);
    if (valid_node_types_it != opcode_node_type_map.end()) {
      const auto valid_node_types = valid_node_types_it->second;
      assert(valid_node_types.find(type) != valid_node_types.end());
    } else {
      assert(type == kInstruction);
    }
  }
}

void Node::checkType() const {
  assert(type == kLLVMType);
  assert(value != nullptr);
  assert(llvm::isa<llvm::Type>(*(llvm::Type*)value));
}

void Node::check() const {
  if (isValue()) {
    checkValue();
    return;
  }
  switch (type) {
    case kLLVMType: {
      checkType();
      break;
    }
    case kDatalogMemoryLocation:
      [[fallthrough]];
    case kParamBinding:
      [[fallthrough]];
    case kCallReturn: {
      assert(value == nullptr);
      break;
    }
    default: {
      assert(false);  // unreachable
    }
  }
}

auto Node::getValue() const -> const llvm::Value* {
  checkValue();
  return (llvm::Value*)value;
}

auto Node::getLLVMType() const -> llvm::Type* {
  checkType();
  return (llvm::Type*)value;
}

auto Nodes::lookup(const std::size_t id) const -> std::string {
  return nodes_[id].uuid;
}

// eliminate unused variable warning when building without assertions
#define _unused(x) ((void)(x))

void Nodes::check() const {
  size_t expected_id = 0;
  for (const auto& node : nodes_) {
    assert(node.id == expected_id);
    _unused(node);
    expected_id++;
  }
}

auto Nodes::find(const llvm::Value& value) const -> llvm::Optional<size_t> {
  const auto id = value_node_id_map_.find(&value);
  if (id == value_node_id_map_.end()) {
    return llvm::Optional<size_t>();
  }
  nodes_[id->second].checkValue();
  return llvm::Optional<size_t>(id->second);
}

auto MemoryLocationIdentifier::getUniqueId() const
    -> boost::flyweight<std::string> {
  return prettyString;
}

void MemoryLocationIdentifier::insertIntoPayload(
    llvm::json::Object& payload) const {
  payload["allocation_context"] = allocationContext.get();
  payload["alias_set_identifier"] = identifier.get();
  payload["pretty_string"] = prettyString.get();
}

static inline auto getSourceStem(const llvm::Module* M) -> llvm::StringRef {
  return llvm::sys::path::stem(M->getSourceFileName());
}

// Some nodes need to be referenced from tools that generate other parts of the
// CPG, so they have deterministic IDs.
auto serializeNodeId(
    const std::size_t id,
    const llvm::Value* value,
    NodeType type,
    llvm::json::Object& payload) -> std::string {
  std::string base_string;
  llvm::raw_string_ostream raw_out(base_string);

  // NOTE(lb): The format of these IDs must match what is output by
  // margin-walker
  switch (type) {
    case kFunction: {
      const auto& function = llvm::cast<llvm::Function>(*value);
      const auto* module = function.getParent();
      raw_out << "<function>:" << getSourceStem(module) << ':';
      function.printAsOperand(raw_out, false);
      break;
    }
    case kBlock: {
      const auto& block = llvm::cast<llvm::BasicBlock>(*value);
      const auto* module = block.getModule();
      raw_out << "<block>:" << getSourceStem(module) << ':';
      block.getParent()->printAsOperand(raw_out, false);
      raw_out << ':';
      block.printAsOperand(raw_out, false);
      break;
    }
    case kArgument: {
      const auto* loc = payload.getObject("location");
      if (loc != nullptr) {  // if it has a "location", it should have "line",
                             // "column", and "name"
        const auto& argument = llvm::cast<llvm::Argument>(*value);
        const auto* module = argument.getParent()->getParent();
        raw_out << "<argument>:" << getSourceStem(module) << ':'
                << payload.getObject("location")
                       ->getString("compressed_id")
                       .getValue()
                       .str()
                << ':' << argument.getArgNo() + 1 << ':'
                << payload.getString("name").getValue().str();
      } else {
        // There was no debug info available, so the ID doesn't matter
        return std::to_string(id);
      }
      break;
    }
    case kLocalVariable: {
      auto* user = value->uses().begin()->getUser();
      const auto* instr = llvm::cast<llvm::Instruction>(user);
      const auto* module = instr->getFunction()->getParent();
      raw_out << "<local>:" << getSourceStem(module) << ':'
              << payload.getObject("location")
                     ->getString("compressed_id")
                     .getValue()
                     .str()
              << ':' << payload.getString("name").getValue().str();
      break;
    }
    default: {
      return std::to_string(id);
    }
  }

  raw_out.str();
  return base_string;
}
};  // namespace mate
