#pragma once

#include "Nodes.h"

// See comment on NodeType.
enum EdgeType {
  kFunctionToEntryBlock,
  kBlockToParentFunction,
  kBlockToSuccessorBlock,
  kBlockToEntryInstruction,
  kBlockToTerminatorInstruction,
  kInstructionToParentBlock,
  kInstructionToSuccessorInstruction,
  kGlobalToInitializer,
  kValueDefinitionToUse,
  kLoadPointerToValue,
  kValueToStorePointer,
  kFunctionEntryToControlDependentBlock,
  kBlockToControlDependentBlock,
  kFunctionEntryToControlDependentInstruction,
  kTerminatorInstructionToControlDependentInstruction,
  kClobberInstructionToValueLoad,
  kDefinitionToValueLoad,
  kCallToFunction,
  kCallgraph,
  kAllocates,
  kCreatesVar,
  kDatalogMayAlias,
  kDatalogMustAlias,
  kDatalogSubregion,
  kDatalogContains,
  kDatalogPointsTo,
  kDatalogLoadMemory,
  kDatalogStoreMemory,
  kHasLLVMType,
  kFunctionToArgument,
  kFunctionToLocalVariable,
  kCallToParamBinding,
  kOperandToParamBinding,
  kParamBindingToArg,
  kReturnInstructionToCallReturn,
  kReturnValueToCallReturn,
  kCallReturnToCaller,
  kSameCall,
};

const std::map<EdgeType, const std::string> edge_type_string_map = {
    {kFunctionToEntryBlock, "FunctionToEntryBlock"},
    {kBlockToParentFunction, "BlockToParentFunction"},
    {kBlockToSuccessorBlock, "BlockToSuccessorBlock"},
    {kBlockToEntryInstruction, "BlockToEntryInstruction"},
    {kBlockToTerminatorInstruction, "BlockToTerminatorInstruction"},
    {kInstructionToParentBlock, "InstructionToParentBlock"},
    {kInstructionToSuccessorInstruction, "InstructionToSuccessorInstruction"},
    {kGlobalToInitializer, "GlobalToInitializer"},
    {kValueDefinitionToUse, "ValueDefinitionToUse"},
    {kLoadPointerToValue, "LoadPointerToValue"},
    {kValueToStorePointer, "ValueToStorePointer"},
    {kFunctionEntryToControlDependentBlock,
     "FunctionEntryToControlDependentBlock"},
    {kBlockToControlDependentBlock, "BlockToControlDependentBlock"},
    {kFunctionEntryToControlDependentInstruction,
     "FunctionEntryToControlDependentInstruction"},
    {kTerminatorInstructionToControlDependentInstruction,
     "TerminatorInstructionToControlDependentInstruction"},
    {kClobberInstructionToValueLoad, "ClobberInstructionToValueLoad"},
    {kDefinitionToValueLoad, "DefinitionToValueLoad"},
    {kCallToFunction, "CallToFunction"},
    {kCallgraph, "Callgraph"},
    {kAllocates, "Allocates"},
    {kCreatesVar, "CreatesVar"},
    {kDatalogMayAlias, "MayAlias"},
    {kDatalogMustAlias, "MustAlias"},
    {kDatalogSubregion, "Subregion"},
    {kDatalogContains, "Contains"},
    {kDatalogPointsTo, "PointsTo"},
    {kDatalogLoadMemory, "LoadMemory"},
    {kDatalogStoreMemory, "StoreMemory"},
    {kHasLLVMType, "HasLLVMType"},
    {kFunctionToArgument, "FunctionToArgument"},
    {kFunctionToLocalVariable, "FunctionToLocalVariable"},
    {kCallToParamBinding, "CallToParamBinding"},
    {kOperandToParamBinding, "OperandToParamBinding"},
    {kParamBindingToArg, "ParamBindingToArg"},
    {kReturnInstructionToCallReturn, "ReturnInstructionToCallReturn"},
    {kReturnValueToCallReturn, "ReturnValueToCallReturn"},
    {kCallReturnToCaller, "CallReturnToCaller"},
    {kSameCall, "SameCall"}};

struct Edge {
  Edge(
      std::size_t id,
      std::size_t source_id,
      std::size_t destination_id,
      EdgeType type,
      llvm::json::Object payload)
      : id(id),
        source_id(source_id),
        destination_id(destination_id),
        type(type),
        payload(std::move(payload)) {}

  const std::size_t id;
  const std::size_t source_id;
  const std::size_t destination_id;
  const EdgeType type;
  // The payload is not const because it is moved into the final JSON payload,
  // though it is not expected to be modified elsewhere.
  llvm::json::Object payload;
};

/**
 * An encapsulated representation of a vector of edges.
 *
 * Does not enforce invariants on the unique IDs, because we don't use them to
 * do fast lookups
 */
class Edges {
 public:
  Edges() = default;

  auto add(
      const std::size_t source_id,
      const std::size_t destination_id,
      const EdgeType type,
      llvm::json::Object payload) -> size_t {
    size_t id = edges_.size();
    edges_.emplace_back(
        id, source_id, destination_id, type, std::move(payload));
    return id;
  }

  auto add(
      const std::size_t source_id,
      const std::size_t destination_id,
      const EdgeType type) -> size_t {
    return add(source_id, destination_id, type, llvm::json::Object());
  }

  /**
   * Remove duplicates (ignoring payload and unique ID)
   */
  void deduplicate() {
    std::set<std::tuple<
        std::size_t,
        std::size_t,
        EdgeType,
        llvm::Optional<llvm::StringRef>,
        llvm::Optional<llvm::StringRef>,
        llvm::Optional<llvm::StringRef>>>
        already_inserted;
    std::vector<Edge> new_edges;
    for (const auto& edge : edges_) {
      auto it_bool_pair = already_inserted.emplace(
          edge.source_id,
          edge.destination_id,
          edge.type,
          edge.payload.getString("context"),
          edge.payload.getString("callee_context"),
          edge.payload.getString("caller_context"));
      if (it_bool_pair.second == true) {
        new_edges.emplace_back(
            new_edges.size(),
            edge.source_id,
            edge.destination_id,
            edge.type,
            edge.payload);
      }
    }

    edges_ = std::move(new_edges);
  }

  // Make it an iterator
  typedef std::vector<Edge>::iterator iterator;
  using const_iterator = std::vector<Edge>::const_iterator;
  auto begin() -> iterator { return edges_.begin(); }
  [[nodiscard]] auto begin() const -> const_iterator { return edges_.begin(); }
  auto end() -> iterator { return edges_.end(); }
  [[nodiscard]] auto end() const -> const_iterator { return edges_.end(); }

 private:
  std::vector<Edge> edges_;
};
