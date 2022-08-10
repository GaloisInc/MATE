#pragma once

#include <string>
#include <utility>

#include "PointerAnalysis.h"
#include "Utils.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/IntrinsicInst.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/ValueMap.h"
#include "llvm/Support/JSON.h"
#include "llvm/Support/Path.h"

namespace mate {
// Please see (and update!) the JSON schema for descriptions of the contents of
// the database. The MATE README should mention it under "Documentation".
enum NodeType {
  kFunction,
  kBlock,
  kInstruction,
  kAlloca,
  kCall,
  kInvoke,
  kLoad,
  kResume,
  kRet,
  kStore,
  kMemset,
  kMemcpy,
  kGlobalVariable,
  kConstant,
  kConstantFP,
  kConstantInt,
  kConstantUndef,
  kConstantString,
  kDatalogMemoryLocation,
  kLLVMType,
  kArgument,
  kLocalVariable,
  kUnclassifiedNode,
  kParamBinding,
  kCallReturn,
};

// NOTE(lb): These must match the enumeration in
// mate_common.models.cpg_types.mate.
const std::map<NodeType, const std::string> node_type_string_map = {
    {kFunction, "Function"},
    {kBlock, "Block"},
    {kInstruction, "Instruction"},
    {kAlloca, "Alloca"},
    {kCall, "Call"},
    {kInvoke, "Invoke"},
    {kLoad, "Load"},
    {kResume, "Resume"},
    {kRet, "Ret"},
    {kStore, "Store"},
    {kMemset, "Memset"},
    {kMemcpy, "Memcpy"},
    {kGlobalVariable, "GlobalVariable"},
    {kConstant, "Constant"},
    {kConstantFP, "ConstantFP"},
    {kConstantInt, "ConstantInt"},
    {kConstantString, "ConstantString"},
    {kConstantUndef, "ConstantUndef"},
    {kDatalogMemoryLocation, "MemoryLocation"},
    {kLLVMType, "LLVMType"},
    {kArgument, "Argument"},
    {kLocalVariable, "LocalVariable"},
    {kUnclassifiedNode, "UnclassifiedNode"},
    {kParamBinding, "ParamBinding"},
    {kCallReturn, "CallReturn"}};

const std::map<unsigned, const std::set<NodeType>> opcode_node_type_map = {
    {llvm::Instruction::Alloca, {kAlloca}},
    {llvm::Instruction::Call, {kCall, kMemcpy, kMemset}},
    {llvm::Instruction::Invoke, {kInvoke}},
    {llvm::Instruction::Load, {kLoad}},
    {llvm::Instruction::Resume, {kResume}},
    {llvm::Instruction::Ret, {kRet}},
    {llvm::Instruction::Store, {kStore}},
};

const std::set<NodeType> instruction_kinds = {
    kInstruction,
    kAlloca,
    kCall,
    kInvoke,
    kLoad,
    kResume,
    kRet,
    kStore,
    kMemset,
    kMemcpy,
};

// Should contain every case except Call
#define FALLTHROUGH_CALL_CASES \
  case kInvoke:                \
    [[fallthrough]];           \
  case kMemset:                \
    [[fallthrough]];           \
  case kMemcpy:                \
    [[fallthrough]];

// Should contain every case except Instruction
#define FALLTHROUGH_INSTRUCTION_CASES \
  case kAlloca:                       \
    [[fallthrough]];                  \
  case kLoad:                         \
    [[fallthrough]];                  \
  case kResume:                       \
    [[fallthrough]];                  \
  case kRet:                          \
    [[fallthrough]];                  \
  case kStore:                        \
    [[fallthrough]];                  \
    FALLTHROUGH_CALL_CASES            \
  case kCall:                         \
    [[fallthrough]];

const std::set<NodeType> call_kinds = {
    kCall,
    kInvoke,
    kMemset,
    kMemcpy,
};

// Should contain every case except Constant
#define FALLTHROUGH_CONSTANT_CASES \
  case kConstantFP:                \
    [[fallthrough]];               \
  case kConstantInt:               \
    [[fallthrough]];               \
  case kConstantString:            \
    [[fallthrough]];               \
  case kConstantUndef:             \
    [[fallthrough]];

const std::set<NodeType> constant_kinds = {
    kConstant,
    kConstantFP,
    kConstantInt,
    kConstantString,
    kConstantUndef,
};

auto value_node_type(const llvm::Value& value) -> NodeType;
auto instruction_node_type(const llvm::Instruction& instruction) -> NodeType;

// Some nodes need to be referenced from tools that generate other parts of the
// CPG, so they have deterministic IDs.
auto serializeNodeId(
    const std::size_t, const llvm::Value*, NodeType, llvm::json::Object&)
    -> std::string;

class Node {
 public:
  Node(
      std::size_t id,
      const llvm::Value* value,
      NodeType type,
      llvm::json::Object payload)
      : id(id),
        uuid(serializeNodeId(id, value, type, payload)),
        type(type),
        payload(std::move(payload)),
        value((void*)value) {}

  Node(
      std::size_t id,
      const llvm::Type* value,
      NodeType type,
      llvm::json::Object payload)
      : id(id),
        uuid(std::to_string(id)),
        type(type),
        payload(std::move(payload)),
        value((void*)value) {}

  Node(std::size_t id, NodeType type, llvm::json::Object payload)
      : id(id),
        uuid(std::to_string(id)),
        type(type),
        payload(std::move(payload)),
        value(nullptr) {}

  void check() const;
  [[nodiscard]] auto isValue() const -> bool;
  void checkValue() const;
  void checkType() const;

  [[nodiscard]] auto getValue() const -> const llvm::Value*;

  [[nodiscard]] auto getLLVMType() const -> llvm::Type*;

  const std::size_t id;
  const std::string uuid;
  const NodeType type;
  // The payload is not const because it is moved into the final JSON payload,
  // though it is not expected to be modified elsewhere.
  llvm::json::Object payload;

 private:
  // This points to either a llvm::Value, an llvm::Type, a char*, or nothing.
  // See check() for details on the relationship between what this points to and
  // the node's type.
  const void* value;
};

/**
 * An encapsulated representation of a vector of nodes.
 *
 * Enforces two invariants:
 * 1. The vector of nodes is sorted by ID
 * 2. Each node's ID corresponds to its index in the vector
 */
class Nodes {
 public:
  Nodes() = default;

  template <class... T>
  auto add(const llvm::Value* value, NodeType type, T&&... args) -> size_t {
    const size_t id = nodes_.size();

    value_node_id_map_[value] = id;

    nodes_.emplace_back(id, value, type, std::forward<T>(args)...);
    return id;
  }

  // One add method for each node constructor
  template <class... T>
  auto add(T&&... args) -> size_t {
    const size_t id = nodes_.size();
    nodes_.emplace_back(id, std::forward<T>(args)...);
    return id;
  }

  [[nodiscard]] auto lookup(const std::size_t id) const -> std::string;

  [[nodiscard]] auto find(const llvm::Value& value) const
      -> llvm::Optional<size_t>;

  /**
   * Check invariants
   */
  void check() const;

  // Make it an iterator
  typedef std::vector<Node>::iterator iterator;
  using const_iterator = std::vector<Node>::const_iterator;
  auto begin() -> iterator { return nodes_.begin(); }
  [[nodiscard]] auto begin() const -> const_iterator { return nodes_.begin(); }
  auto end() -> iterator { return nodes_.end(); }
  [[nodiscard]] auto end() const -> const_iterator { return nodes_.end(); }

 private:
  std::vector<Node> nodes_;
  llvm::ValueMap<const llvm::Value*, std::size_t> value_node_id_map_;
};

struct MemoryLocationIdentifier {
  MemoryLocationIdentifier(std::string ident, std::string allocation_context)
      : identifier(ident),
        allocationContext(allocation_context),
        prettyString(boost::flyweight<std::string>(
            allocationContext.get() + identifier.get())) {}

  MemoryLocationIdentifier(
      boost::flyweight<std::string> ident,
      boost::flyweight<std::string> allocation_context)
      : identifier(std::move(ident)),
        allocationContext(std::move(allocation_context)),
        prettyString(boost::flyweight<std::string>(
            allocationContext.get() + identifier.get())) {}

  [[nodiscard]] auto getUniqueId() const -> boost::flyweight<std::string>;

  // Build up the JSON payload for a memory location
  void insertIntoPayload(llvm::json::Object& payload) const;

 private:
  const boost::flyweight<std::string> identifier;
  const boost::flyweight<std::string> allocationContext;
  const boost::flyweight<std::string> prettyString;
};

};  // namespace mate
