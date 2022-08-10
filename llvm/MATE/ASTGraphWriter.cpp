#include <algorithm>
#include <cassert>
#include <set>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

#include "ControlDependenceGraph.h"
#include "Edges.h"
#include "Nodes.h"
#include "PointerAnalysis.h"
#include "Serialize/Nodes.h"
#include "Serialize/Types.h"
#include "Utils.h"
#include "llvm/ADT/Optional.h"
#include "llvm/ADT/StringMap.h"
#include "llvm/Analysis/AliasAnalysis.h"
#include "llvm/Analysis/AliasSetTracker.h"
#include "llvm/Analysis/BasicAliasAnalysis.h"
#include "llvm/Analysis/CFLAndersAliasAnalysis.h"
#include "llvm/Analysis/CFLSteensAliasAnalysis.h"
#include "llvm/Analysis/ConstantFolding.h"
#include "llvm/Analysis/GlobalsModRef.h"
#include "llvm/Analysis/MemoryDependenceAnalysis.h"
#include "llvm/Analysis/MemoryLocation.h"
#include "llvm/Analysis/ScopedNoAliasAA.h"
#include "llvm/IR/CFG.h"
#include "llvm/IR/Constants.h"
#include "llvm/IR/DebugInfoMetadata.h"
#include "llvm/IR/InstrTypes.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/Metadata.h"
#include "llvm/IR/Type.h"
#include "llvm/IR/ValueMap.h"
#include "llvm/Pass.h"
#include "llvm/Support/CommandLine.h"
#include "llvm/Support/JSON.h"
#include "llvm/Support/Path.h"
#include "llvm/Support/raw_ostream.h"

namespace mate {
llvm::cl::opt<std::string> cpg_file_option(
    "cpg-file",
    llvm::cl::desc("Path to write CPG data."),
    llvm::cl::value_desc("FILENAME"),
    llvm::cl::init("cpg.jsonl"));
llvm::cl::opt<bool> datalog_pointer_analysis(
    "datalog-pointer-analysis",
    llvm::cl::desc("Use datalog pointer analysis."),
    llvm::cl::init(true));
llvm::cl::opt<bool> pretty_llvm_value(
    "pretty-llvm-value",
    llvm::cl::desc("Print LLVM value pretty string in the CPG."),
    llvm::cl::init(true));
llvm::cl::opt<bool> mem_dep_edges(
    "mem-dep-edges",
    llvm::cl::desc("Emit memory dependence edges."),
    llvm::cl::init(true));
llvm::cl::opt<bool> control_dep_edges(
    "control-dep-edges",
    llvm::cl::desc("Emit control dependence edges."),
    llvm::cl::init(true));
// Currently unused. Eventually, we will want to look at the C(++) source for
// the source-level AST.
llvm::cl::opt<std::string> source_dir_option(
    "c-source",
    llvm::cl::desc("Directory containing program source."),
    llvm::cl::value_desc("DIRNAME"),
    llvm::cl::init("source/"));

// Retrieve the Argument at index i, if one exists
static auto maybeGetArg(const llvm::Function* function, unsigned i)
    -> const llvm::Argument* {
  if (i < function->arg_size()) {
    return function->getArg(i);
  }
  return nullptr;
}

static constexpr auto is_debug_intrinsic(llvm::Intrinsic::ID iid) -> bool {
  switch (iid) {
    case llvm::Intrinsic::dbg_declare:
    case llvm::Intrinsic::dbg_addr:
    case llvm::Intrinsic::dbg_value:
      return true;
    default:
      return false;
  }
}

// Find llvm.dbg.{addr,declare,value} statements in a function and extract the
// attached metadata nodes.
//
// Builds a map from argument numbers to their DILocalVariable nodes,
// and a vector of all DILocalVariable nodes that appear as local variables,
// all together with their allocation sites (when these can be determined).
//
// Local variable metadata is encoded as MetadataAsValue nodes because there
// is a map MetadataAsValue -> Metadata, but the constructor of
// MetadataAsValue is private, so one can't go back the other way.
static auto function_debug_declares(const llvm::Function& function)
    -> std::pair<
        llvm::DenseMap<
            unsigned,
            std::tuple<
                const llvm::DILocalVariable*,
                const llvm::DIExpression*,
                const llvm::DebugLoc*,
                const llvm::AllocaInst*>>,
        std::vector<std::tuple<
            const llvm::MetadataAsValue*,
            const llvm::DIExpression*,
            const llvm::DebugLoc*,
            const llvm::AllocaInst*>>> {
  llvm::DenseMap<
      unsigned,
      std::tuple<
          const llvm::DILocalVariable*,
          const llvm::DIExpression*,
          const llvm::DebugLoc*,
          const llvm::AllocaInst*>>
      map;
  std::vector<std::tuple<
      const llvm::MetadataAsValue*,
      const llvm::DIExpression*,
      const llvm::DebugLoc*,
      const llvm::AllocaInst*>>
      vec;
  for (const auto& block : function) {
    for (const auto& instruction : block) {
      const auto maybe_call_site = asCallSite(instruction);
      if (maybe_call_site.hasValue()) {
        const llvm::ImmutableCallSite call_site = maybe_call_site.getValue();
        if (is_debug_intrinsic(maybe_call_site->getIntrinsicID())) {
          const auto* di_local_variable_as_value =
              llvm::cast<llvm::MetadataAsValue>(call_site.getArgument(1));
          const auto* di_local_variable = &llvm::cast<llvm::DILocalVariable>(
              *di_local_variable_as_value->getMetadata());
          // NOTE(lb): While the 0th argument is /usually/ a
          // MetadataAsValue(ValueAsMetadata(Value)), it can also just be an
          // empty debug info record, hence the dyn_casts here.
          // NOTE(ww): Similarly, the MetadataAsValue might be empty for
          // whatever reason. This bug hasn't been fully diagnosed yet; see
          // MATE#1380.
          const llvm::AllocaInst* maybe_alloca = nullptr;
          if (const auto* MAV = llvm::dyn_cast<llvm::MetadataAsValue>(
                  call_site.getArgument(0))) {
            if (const auto* VAM = llvm::dyn_cast_or_null<llvm::ValueAsMetadata>(
                    MAV->getMetadata())) {
              maybe_alloca = llvm::dyn_cast<llvm::AllocaInst>(VAM->getValue());
            }
          }

          const auto* dbg_loc =
              &llvm::cast<llvm::DebugLoc>(call_site->getDebugLoc());
          const auto* di_expression = llvm::cast<llvm::DIExpression>(
              llvm::cast<llvm::MetadataAsValue>(call_site.getArgument(2))
                  ->getMetadata());

          // NOTE(ww): This check currently serves two purposes:
          // 1. It prevents us from clobbering our actual function arguments
          //    with debug information for arguments that LLVM has inlined.
          //    LLVM preserves the numbering for the latter, so failing to check
          //    here would cause us to clobber our argument map below.
          // 2. It's an unpleasant hack that prevents us from mis-emitting
          //    local variables that have been inlined into this function.
          //    We *should* eventually emit these (and inlined) arguments,
          //    but we need to do more refactoring of ASTGraphWriter first.
          //    See: MATE#1053.
          if (dbg_loc->getInlinedAt()) {
            continue;
          }

          if (di_local_variable->isParameter()) {
            map[di_local_variable->getArg()] = std::tuple<
                const llvm::DILocalVariable*,
                const llvm::DIExpression*,
                const llvm::DebugLoc*,
                const llvm::AllocaInst*>(
                di_local_variable, di_expression, dbg_loc, maybe_alloca);
          } else {
            // NOTE(ww): Artificial non-parameter DILocalVariables are a good
            // sign that we're visiting some generates STL code. These are
            // currently impossible to disambiguate correctly, since they tend
            // to reuse the same variable name in different lexical blocks
            // within the same function. Handling them will require us to
            // fundamentally re-evaluate our approach to DI-level variable
            // collection within ASTGraphWriter. See:
            // https://gitlab-ext.galois.com/mate/MATE/-/issues/1039#note_69505
            if (di_local_variable->isArtificial()) {
              continue;
            }

            vec.emplace_back(
                di_local_variable_as_value,
                di_expression,
                dbg_loc,
                maybe_alloca);
          }
        }
      }
    }
  }
  return std::pair<
      llvm::DenseMap<
          unsigned,
          std::tuple<
              const llvm::DILocalVariable*,
              const llvm::DIExpression*,
              const llvm::DebugLoc*,
              const llvm::AllocaInst*>>,
      std::vector<std::tuple<
          const llvm::MetadataAsValue*,
          const llvm::DIExpression*,
          const llvm::DebugLoc*,
          const llvm::AllocaInst*>>>(map, vec);
}

static auto might_be_null(
    const llvm::Value& value,
    const llvm::Optional<std::set<const llvm::Value*>>& maybe_null_set)
    -> llvm::Optional<bool> {
  llvm::Optional<bool> maybe_is_null;
  if (maybe_null_set.hasValue()) {
    auto set_it = maybe_null_set.getValue().find(&value);
    maybe_is_null =
        llvm::Optional<bool>(set_it != maybe_null_set.getValue().end());
  }
  return maybe_is_null;
}

static inline auto construct_payload_for_value(
    const llvm::Value& value,
    NodeType type,
    const llvm::Optional<std::set<const llvm::Value*>>& maybe_null_set)
    -> llvm::json::Object {
  switch (type) {
    case kGlobalVariable: {
      return serializeGlobalVariable(
          llvm::cast<llvm::GlobalVariable>(value), pretty_llvm_value);
    }
    case kFunction: {
      return serializeFunction(
          llvm::cast<llvm::Function>(value), pretty_llvm_value);
    }
    case kBlock: {
      return serializeBlock(
          llvm::cast<llvm::BasicBlock>(value), pretty_llvm_value);
    }
      FALLTHROUGH_INSTRUCTION_CASES
    case kInstruction: {
      return serializeInstruction(
          llvm::cast<llvm::Instruction>(value),
          pretty_llvm_value,
          might_be_null(value, maybe_null_set));
    }
      FALLTHROUGH_CONSTANT_CASES
    case kConstant: {
      return serializeConstant(
          llvm::cast<llvm::Constant>(value), pretty_llvm_value);
    }
    default: {
      return llvm::json::Object({});
    }
  }
  assert(false);  // unreachable
}

static inline auto construct_payload_for_node(
    Node& node,
    const llvm::DataLayout& dl,
    const llvm::Optional<std::set<const llvm::Value*>>& maybe_null_set)
    -> llvm::json::Object {
  switch (node.type) {
    case kArgument:
    case kLocalVariable:
    case kDatalogMemoryLocation:
    case kParamBinding:
      assert(node.payload.size() != 0);
      break;
    case kCallReturn:
      assert(node.payload.size() == 0);
      break;
    case kLLVMType: {
      assert(node.payload.size() == 0);
      node.payload =
          serializeLLVMType(*node.getLLVMType(), pretty_llvm_value, dl);
      break;
    }
    default: {
      assert(node.payload.size() == 0);
      node.payload = construct_payload_for_value(
          *node.getValue(), node.type, maybe_null_set);
      break;
    }
  }

  node.payload["node_kind"] = node_type_string_map.at(node.type);
  return llvm::json::Object(
      {{"entity", "node"},
       {"uuid", node.uuid},
       {"attributes", std::move(node.payload)}});
}

static inline auto construct_payload_for_edge(Edge edge, const Nodes& nodes)
    -> llvm::json::Object {
  edge.payload["edge_kind"] = edge_type_string_map.at(edge.type);
  return llvm::json::Object(
      {{"entity", "edge"},
       {"uuid", std::to_string(edge.id)},
       {"source", nodes.lookup(edge.source_id)},
       {"target", nodes.lookup(edge.destination_id)},
       {"attributes", std::move(edge.payload)}});
}

class ASTGraphWriter : public llvm::ModulePass {
 public:
  static char ID;

  ASTGraphWriter() : llvm::ModulePass(ID) {}
  void getAnalysisUsage(llvm::AnalysisUsage& analysis_usage) const override {
    if (mem_dep_edges) {
      analysis_usage.addRequired<llvm::MemoryDependenceWrapperPass>();
    }
    if (control_dep_edges) {
      analysis_usage.addRequired<llvm::ControlDependenceGraph>();
    }
    if (datalog_pointer_analysis) {
      analysis_usage.addRequired<cclyzer::LegacyPointerAnalysis>();
    }
    analysis_usage.setPreservesAll();
  }

  auto processFunction(llvm::Function& function) -> void {
    const auto function_id = addNode(function, kFunction);

    const auto& [argument_debug_info, local_var_debug_info] =
        function_debug_declares(function);

    for (const auto& argument : function.args()) {
      // More attributes are added to the argument nodes in Aspirin
      const auto arg_iterator =
          argument_debug_info.find(argument.getArgNo() + 1);
      auto maybe_argument_is_null = mightBeNull(argument);
      if (arg_iterator != argument_debug_info.end()) {
        const auto& [di_local_variable, di_expression, debug_location, argument_alloca] =
            arg_iterator->second;
        // NOTE: The node for the 'alloca' instruction was already created
        // above, with the appropriate payload.
        addNode(
            argument,
            kArgument,
            serializeArgument(
                argument,
                pretty_llvm_value,
                maybe_argument_is_null,
                *di_local_variable,
                *debug_location));
        if (argument_alloca != nullptr) {
          addEdge(*argument_alloca, argument, kCreatesVar);
        }
      } else {
        addNode(
            argument,
            kArgument,
            serializeArgumentWithoutDebugInfo(
                argument, pretty_llvm_value, maybe_argument_is_null));
      }
      addEdge(function, argument, kFunctionToArgument);
    }

    if (function.empty()) {
      // This function is just a declaration, nothing more to do!
      return;
    }

    addEdge(
        function_id, addNode(function.front(), kBlock), kFunctionToEntryBlock);

    for (
        const auto& [di_local_variable_as_value, di_expression, debug_location, local_var_alloca] :
        local_var_debug_info) {
      const auto* di_local_variable = llvm::cast<llvm::DILocalVariable>(
          di_local_variable_as_value->getMetadata());
      addNode(
          *di_local_variable_as_value,
          kLocalVariable,
          serializeLocalVariable(*di_local_variable, *debug_location));
      addEdge(function, *di_local_variable_as_value, kFunctionToLocalVariable);

      // See above NOTE about the 'alloca' node
      // NOTE(lb): If the third argument to the debug intrinsic wasn't "trivial"
      // (of the form !DIExpression()), this is not the 'alloca' which allocates
      // this variable, so we skip linking them.
      if (local_var_alloca != nullptr && di_expression->getNumElements() == 0) {
        addEdge(*local_var_alloca, *di_local_variable_as_value, kCreatesVar);
        addValueType(
            *di_local_variable_as_value,
            *(local_var_alloca->getType()->getElementType()));
      }
    }

    for (const auto& block : function) {
      const auto block_id = addNode(block, kBlock);
      addEdge(
          block_id, addInstruction(block.front()), kBlockToEntryInstruction);
      addEdge(
          block_id,
          addInstruction(block.back()),
          kBlockToTerminatorInstruction);
      addEdge(block_id, function_id, kBlockToParentFunction);

      for (const auto successor_block_ptr : successors(&block)) {
        addEdge(
            block_id,
            addNode(*successor_block_ptr, kBlock),
            kBlockToSuccessorBlock);
      }

      for (const auto& instruction : block) {
        const auto instruction_id = addInstruction(instruction);
        addEdge(instruction_id, block_id, kInstructionToParentBlock);
        addUseEdges(instruction);

        const auto next_instruction_ptr = instruction.getNextNode();
        if (next_instruction_ptr != nullptr) {
          addEdge(
              instruction_id,
              addInstruction(*next_instruction_ptr),
              kInstructionToSuccessorInstruction);
        }

        if (llvm::isa<llvm::LoadInst>(instruction)) {
          const auto& load_instruction =
              llvm::cast<llvm::LoadInst>(instruction);
          addEdge(
              addNode(*load_instruction.getPointerOperand()),
              instruction_id,
              kLoadPointerToValue);
        }

        if (llvm::isa<llvm::StoreInst>(instruction)) {
          const auto& store_instruction =
              llvm::cast<llvm::StoreInst>(instruction);
          addEdge(
              *store_instruction.getValueOperand(),
              *store_instruction.getPointerOperand(),
              kValueToStorePointer);
        }

        if (llvm::isa<llvm::CallBase>(instruction)) {
          for (const auto& [caller_ctx, callee_ctx, callee] :
               callees(&llvm::cast<llvm::CallBase>(instruction))) {
            llvm::json::Object payload;
            payload["caller_context"] = caller_ctx.get();
            payload["callee_context"] = callee_ctx.get();
            const auto callee_id = addNode(*callee, kFunction);
            addEdge(instruction_id, callee_id, kCallToFunction, payload);
            addEdge(function_id, callee_id, kCallgraph, payload);
          }
        }
      }

      addTerminatorSuccessorEdges(block);
    }

    if (control_dep_edges) {
      controlDependence(function);
    }

    if (mem_dep_edges) {
      memoryDependence(function);
    }
  }

  auto runOnModule(llvm::Module& M) -> bool override {
    // In order to store information about what pointers might be null
    // according to the datalog analysis, we need to pass around a set that is
    // part of the results.  Since we don't always have the results, we use an
    // optional value instead of a slew of conditionals or macros.
    if (datalog_pointer_analysis) {
      cclyzer::PointerAnalysisAAResult& dl_result =
          getAnalysis<cclyzer::LegacyPointerAnalysis>().getResult();
      maybe_null_set_ = dl_result.getNullPtrSet();
    }

    for (auto& F : M) {
      processFunction(F);
    }

    std::error_code code;
    llvm::raw_fd_ostream cpg_file(cpg_file_option, code);
    if (code) {
      llvm::errs() << code.category().name() << ':' << code.value() << '\n';
      return false;
    }

    // See https://gitlab-ext.galois.com/mate/MATE/-/issues/770.
    //
    // We do this before adding the datalog pointer analysis and parameter
    // binding/call return edges because (1) there are _a lot_ of them, so they
    // slow down deduplication and (2) they shouldn't have any duplicates by
    // construction (and this is verified in invariant_test.py).
    edges_.deduplicate();

    // do this in the module pass so that Argument nodes have already been
    // added
    add_param_binding_and_call_returns(M);

    if (datalog_pointer_analysis) {
      addDatalogPointsToEdges();
    }

    // LLVMType nodes are added as we encounter values that have that type.
    // It's possible that the program contains only pointers to a named struct
    // type, and no values of that type. This loop ensures we still have the
    // definitions of those types available.
    for (const auto& named_struct_type : M.getIdentifiedStructTypes()) {
      addType(*named_struct_type);
    }

    const auto dl = M.getDataLayout();
    for (auto& node : nodes_) {
      cpg_file << construct_payload_for_node(node, dl, maybe_null_set_) << '\n';
    }

    for (auto& edge : edges_) {
      cpg_file << construct_payload_for_edge(std::move(edge), nodes_) << '\n';
    }

    return false;
  }

  void print(llvm::raw_ostream& /*unused*/, const llvm::Module* /*unused*/)
      const override {}

 private:
  void addTerminatorSuccessorEdges(const llvm::BasicBlock& block) {
    const auto& terminator = block.back();
    switch (terminator.getOpcode()) {
      case llvm::Instruction::Br: {
        // Is this a conditional or unconditional 'br'?
        const auto& br_instruction = llvm::cast<llvm::BranchInst>(terminator);
        if (br_instruction.isUnconditional()) {
          // Unconditional breaks only have one successor
          assert(br_instruction.getNumSuccessors() == 1);
          addUnconditionalSuccessorEdge(
              terminator, br_instruction.getSuccessor(0)->front());
        } else {
          const auto& cond = br_instruction.getCondition();
          assert(br_instruction.getNumSuccessors() == 2);
          addBrSuccessorEdge(
              terminator, br_instruction.getSuccessor(0)->front(), cond, true);
          addBrSuccessorEdge(
              terminator, br_instruction.getSuccessor(1)->front(), cond, false);
        }
        break;
      }
      case llvm::Instruction::Switch: {
        const auto& switch_instruction =
            llvm::cast<llvm::SwitchInst>(terminator);
        addSwitchSuccessorEdge(
            terminator,
            switch_instruction.getDefaultDest()->front(),
            switch_instruction.getCondition(),
            nullptr);
        for (const auto& case_handle : switch_instruction.cases()) {
          addSwitchSuccessorEdge(
              terminator,
              case_handle.getCaseSuccessor()->front(),
              switch_instruction.getCondition(),
              case_handle.getCaseValue());
        }
        break;
      }
      case llvm::Instruction::IndirectBr: {
        // We don't statically know the conditions for this to jump to
        // any given label in the list.
        const auto& indirectbr_instruction =
            llvm::cast<llvm::IndirectBrInst>(terminator);
        for (const auto& succ : indirectbr_instruction.successors()) {
          addSwitchSuccessorEdge(
              terminator,
              succ->front(),
              indirectbr_instruction.getAddress(),
              nullptr);
        }
        break;
      }
      default: {
        // This catches, among others, Instruction::Ret. Return
        // instructions have no successors: where they land is
        // determined by the call site.
        for (const auto successor_block_ptr : successors(&block)) {
          addUnconditionalSuccessorEdge(
              terminator, successor_block_ptr->front());
        }
        break;
      }
        // TODO: Invoke has two "destinations", normal and exceptional.
        // These are pretty different from other "successor"
        // instructions, in that control flow goes first to the function
        // and to these destinations only when that function
        // returns/raises an exception. How should we handle that?
        //
        // NB: it participates in the "CallToFunction/FunctionToCall"
        // edges.
        //
        // case llvm::Instruction::Invoke: {
        //   break;
        // }
        //
        // TODO:
        // case llvm::Instruction::CallBr:
        // case llvm::Instruction::Resume:
        // case llvm::Instruction::CatchSwitch:
        // case llvm::Instruction::CatchRet:
        // case llvm::Instruction::CleanupRet:
        // case llvm::Instruction::Unreachable:
    }
  }

  void controlDependence(llvm::Function& function) {
    auto& control_dependence_graph =
        getAnalysis<llvm::ControlDependenceGraph>(function);

    const auto& entry = control_dependence_graph.getRoot();

    const auto function_id = addNode(function, kFunction);

    // Entry edges
    llvm::json::Object entry_payload;
    entry_payload["condition"] = "other";
    entry_payload["controls"] = true;
    for (auto i = entry->other_begin(), e = entry->other_end(); i != e; ++i) {
      const auto& child = (*i)->getBlock();

      addEdge(
          function_id,
          addNode(*child, kBlock),
          kFunctionEntryToControlDependentBlock,
          entry_payload);

      for (const auto& instruction : *child) {
        addEdge(
            function_id,
            addInstruction(instruction),
            kFunctionEntryToControlDependentInstruction,
            entry_payload);
      }
    }

    for (auto& block : function) {
      const auto block_id = addNode(block, kFunction);
      const auto& node = control_dependence_graph[&block];
      const auto terminator_id = addInstruction(*block.getTerminator());

      // True edges
      llvm::json::Object true_payload;
      true_payload["condition"] = "true";
      for (auto i = node->true_begin(), e = node->true_end(); i != e; ++i) {
        const auto& child = (*i)->getBlock();
        true_payload["controls"] = (*i)->getNumParents() == 1;

        addEdge(
            block_id,
            addNode(*child, kBlock),
            kBlockToControlDependentBlock,
            true_payload);

        for (const auto& instruction : *child) {
          addEdge(
              terminator_id,
              addInstruction(instruction),
              kTerminatorInstructionToControlDependentInstruction,
              true_payload);
        }
      }

      // False edges
      llvm::json::Object false_payload;
      false_payload["condition"] = "false";
      for (auto i = node->false_begin(), e = node->false_end(); i != e; ++i) {
        const auto& child = (*i)->getBlock();
        false_payload["controls"] = (*i)->getNumParents() == 1;

        addEdge(
            block_id,
            addNode(*child, kBlock),
            kBlockToControlDependentBlock,
            false_payload);

        for (const auto& instruction : *child) {
          addEdge(
              terminator_id,
              addInstruction(instruction),
              kTerminatorInstructionToControlDependentInstruction,
              false_payload);
        }
      }

      // Other edges
      llvm::json::Object other_payload;
      other_payload["condition"] = "other";
      for (auto i = node->other_begin(), e = node->other_end(); i != e; ++i) {
        const auto& child = (*i)->getBlock();
        other_payload["controls"] = (*i)->getNumParents() == 1;

        addEdge(
            block_id,
            addNode(*child, kBlock),
            kBlockToControlDependentBlock,
            other_payload);

        for (const auto& instruction : *child) {
          addEdge(
              terminator_id,
              addInstruction(instruction),
              kTerminatorInstructionToControlDependentInstruction,
              other_payload);
        }
      }
    }
  }

  void memoryDependence(llvm::Function& function) {
    auto& memory_dependence =
        getAnalysis<llvm::MemoryDependenceWrapperPass>(function).getMemDep();
    for (auto& block : function) {
      for (auto& instruction : block) {
        if (llvm::isa<llvm::LoadInst>(instruction) ||
            llvm::isa<llvm::CallInst>(instruction)) {
          llvm::SmallVector<llvm::MemDepResult, 16> results;
          const auto local_result =
              memory_dependence.getDependency(&instruction);
          if (local_result.isClobber() || local_result.isDef()) {
            results.push_back(local_result);
          } else {
            if (llvm::isa<llvm::LoadInst>(instruction)) {
              llvm::SmallVector<llvm::NonLocalDepResult, 16> non_local_results;
              memory_dependence.getNonLocalPointerDependency(
                  &instruction, non_local_results);
              for (const auto& non_local_result : non_local_results) {
                results.push_back(non_local_result.getResult());
              }
            } else if (
                llvm::isa<llvm::CallInst>(instruction) &&
                local_result.isNonLocal()) {
              auto* call_base = llvm::cast<llvm::CallBase>(&instruction);
              // note: this finds only one memory dependence per function
              // call, instead of one memory dependence per pointer
              // argument. in particular, this is accurate only for function
              // with only one pointer argument.
              const auto& non_local_results =
                  memory_dependence.getNonLocalCallDependency(call_base);
              for (const auto& non_local_result : non_local_results) {
                results.push_back(non_local_result.getResult());
              }
            }
          }

          for (const auto& result : results) {
            if (result.isClobber()) {
              addEdge(
                  *result.getInst(),
                  instruction,
                  kClobberInstructionToValueLoad);
            } else if (result.isDef()) {
              addEdge(*result.getInst(), instruction, kDefinitionToValueLoad);
            }
          }
        }
      }
    }
  }

  auto addParamBinding(
      const boost::flyweight<std::string>& callee_ctxt,
      const llvm::Function* called_function,
      const boost::flyweight<std::string>& caller_ctxt,
      const llvm::ImmutableCallSite& call_site) -> std::vector<size_t> {
    // Add one ParamBinding for each operand / argument pair
    // Return a vector of ParamBinding node ids
    std::vector<size_t> param_binding_id_accum = {};
    const llvm::Instruction* instruction = call_site.getInstruction();
    for (const llvm::Use& operand : call_site.args()) {
      // Add a new ParamBinding node; these nodes are not llvm values
      // so they can't go into the value->id map, and are pushed onto
      // the nodes vector directly
      // For now ParamBinding nodes hold on to their operand/argument number
      llvm::json::Object parambinding_payload;
      parambinding_payload["arg_op_number"] = operand.getOperandNo();
      const auto param_binding_id =
          nodes_.add(kParamBinding, parambinding_payload);
      llvm::json::Object edge_payload;
      edge_payload["caller_context"] = caller_ctxt.get();
      edge_payload["callee_context"] = callee_ctxt.get();
      // Add three edges, all of which have an empty payload:
      // 1. call site node -> param binding node
      edges_.add(
          addInstruction(*instruction),
          param_binding_id,
          kCallToParamBinding,
          edge_payload);
      // 2. operand -> ParamBinding
      edges_.add(
          addNode(*operand.get()),
          param_binding_id,
          kOperandToParamBinding,
          edge_payload);
      // 3. ParamBinding -> matching Argument node (if there is one)
      auto matching_arg = maybeGetArg(called_function, operand.getOperandNo());
      if (matching_arg != nullptr) {
        edges_.add(
            param_binding_id,
            addNode(*matching_arg, kArgument),
            kParamBindingToArg,
            edge_payload);
      }
      param_binding_id_accum.push_back(param_binding_id);
    }
    return param_binding_id_accum;
  }

  auto addCallReturn(
      const boost::flyweight<std::string>& callee_ctxt,
      const llvm::Function* called_function,
      const boost::flyweight<std::string>& caller_ctxt,
      const llvm::Instruction& call_site) -> std::vector<size_t> {
    // For every return instruction, add a new CallReturn node & return it's
    // id
    std::vector<size_t> call_return_id_accum = {};
    for (const auto& block : *called_function) {
      for (const auto& instruction : block) {
        if (llvm::isa<llvm::ReturnInst>(instruction)) {
          const auto& return_instruction =
              llvm::cast<llvm::ReturnInst>(instruction);
          llvm::json::Object call_return_payload;
          const auto call_return_id =
              nodes_.add(kCallReturn, call_return_payload);
          llvm::json::Object edge_payload;
          edge_payload["caller_context"] = caller_ctxt.get();
          edge_payload["callee_context"] = callee_ctxt.get();
          // Add three edges:
          // 1. call return node -> call site
          edges_.add(
              call_return_id,
              addInstruction(call_site),
              kCallReturnToCaller,
              edge_payload);
          // 2. terminator inst -> call return
          edges_.add(
              addNode(return_instruction, kRet),
              call_return_id,
              kReturnInstructionToCallReturn,
              edge_payload);
          if (return_instruction.getNumOperands() !=
              0) {  // in fact it ought to have 1 then
            for (const llvm::Use& return_operand :
                 return_instruction.operands()) {
              // 3. terminator value -> call return if there is a return value
              edges_.add(
                  addNode(*return_operand.get()),
                  call_return_id,
                  kReturnValueToCallReturn,
                  edge_payload);
            }
            call_return_id_accum.push_back(call_return_id);
          }
        }
      }
    }
    return call_return_id_accum;
  }

  // For each function call, we add ParamBinding nodes which connect the
  // function argument values (operands) with the formal parameters
  void add_param_binding_and_call_returns(llvm::Module& module) {
    for (const auto& function : module) {
      for (const auto& block : function) {
        for (const auto& instruction : block) {
          const auto maybe_call_site = asCallSite(instruction);
          if (maybe_call_site.hasValue()) {
            const llvm::ImmutableCallSite call_site =
                maybe_call_site.getValue();
            for (const auto& [caller_ctx, callee_ctx, callee] :
                 callees(&llvm::cast<llvm::CallBase>(instruction))) {
              addParamBindingAndCallReturnForFunction(
                  caller_ctx, call_site, instruction, callee_ctx, callee);
            }
          }
        }
      }
    }
  }

  // Find all of the memory location nodes that have associated allocation
  // instructions (from datalog), and add allocation edges.
  void addAllocatesEdges(const std::vector<std::tuple<
                             int,
                             const llvm::Value*,
                             int,
                             boost::flyweight<std::string>>>& allocs) {
    const auto context_to_string = getAnalysis<cclyzer::LegacyPointerAnalysis>()
                                       .getResult()
                                       .getContextToString();
    for (const auto& [ptr_context, value, alloc_context, alias_set_identifier] :
         allocs) {
      MemoryLocationIdentifier mem_loc_id(
          alias_set_identifier, context_to_string.find(alloc_context)->second);
      const auto unique_id = mem_loc_id.getUniqueId();
      const auto node_id = memory_location_id_map_.find(unique_id)->second;
      const auto instr_id =
          addInstruction(*llvm::cast<llvm::Instruction>(value));
      const auto context = context_to_string.find(alloc_context)->second;
      edges_.add(
          instr_id,
          node_id,
          kAllocates,
          llvm::json::Object({{"context", context.get()}}));
    }
  }

  inline void addParamBindingAndCallReturnForFunction(
      const boost::flyweight<std::string>& caller_ctx,
      const llvm::ImmutableCallSite& call_site,
      const llvm::Instruction& instruction,
      const boost::flyweight<std::string>& callee_ctx,
      const llvm::Function* called_function) {
    // skip calls to external functions, library functions & debug
    // metadata skipping var arg functions for now (See issues #149 & #178)
    if (called_function != nullptr && !called_function->isVarArg() &&
        (!is_debug_intrinsic(call_site.getIntrinsicID()))) {
      std::vector<size_t> param_binding_ids =
          addParamBinding(callee_ctx, called_function, caller_ctx, call_site);
      std::vector<size_t> call_return_ids =
          addCallReturn(callee_ctx, called_function, caller_ctx, instruction);

      // add an edge to match up all parameter bindings with the
      // return
      for (size_t call_return_id : call_return_ids) {
        for (size_t param_binding_id : param_binding_ids) {
          edges_.add(param_binding_id, call_return_id, kSameCall);
        }
      }
    }
  }

  auto addUnconditionalSuccessorEdge(
      const llvm::Instruction& src, const llvm::Instruction& tgt)
      -> std::size_t {
    llvm::json::Object edge_payload;
    edge_payload["condition"] = nullptr;  // JSON: null
    return addEdge(src, tgt, kInstructionToSuccessorInstruction, edge_payload);
  }

  auto addSwitchSuccessorEdge(
      const llvm::Instruction& src,
      const llvm::Instruction& tgt,
      const llvm::Value* condition_expr,
      const llvm::Value* condition_value) -> std::size_t {
    llvm::json::Object edge_payload;
    llvm::json::Object condition_payload;
    if (condition_expr != nullptr) {
      addNode(*condition_expr);
      condition_payload["expression"] = addNode(*condition_expr);
    }
    // condition_value is null for switch 'default'
    if (condition_value != nullptr) {
      addNode(*condition_value);
      condition_payload["value"] = addNode(*condition_value);
    } else {
      condition_payload["value"] = nullptr;  // JSON: null
    }
    edge_payload["condition"] = std::move(condition_payload);
    return addEdge(src, tgt, kInstructionToSuccessorInstruction, edge_payload);
  }

  auto addBrSuccessorEdge(
      const llvm::Instruction& src,
      const llvm::Instruction& tgt,
      const llvm::Value* condition_expr,
      const bool condition_value) -> std::size_t {
    llvm::json::Object edge_payload;
    llvm::json::Object condition_payload;
    if (condition_expr != nullptr) {
      addNode(*condition_expr);
      condition_payload["expression"] = addNode(*condition_expr);
    }
    condition_payload["value"] = condition_value;
    edge_payload["condition"] = std::move(condition_payload);
    return addEdge(src, tgt, kInstructionToSuccessorInstruction, edge_payload);
  }

  auto addValueType(const llvm::Value& value, const llvm::Type& type)
      -> std::size_t {
    return edges_.add(
        addNode(value), addType(type), kHasLLVMType, llvm::json::Object{});
  }

  auto addType(const llvm::Type& type) -> std::size_t {
    const auto id = type_node_id_map_.find(&type);
    if (id != type_node_id_map_.end()) {
      return id->second;
    }
    const auto fresh_id = nodes_.add(&type, kLLVMType, llvm::json::Object{});
    type_node_id_map_[&type] = fresh_id;
    return fresh_id;
  }

  auto addMemoryLocation(const MemoryLocationIdentifier& memory_location_id)
      -> std::size_t {
    return addMemoryLocation(
        memory_location_id, serializeMemoryLocation(memory_location_id));
  }

  auto addMemoryLocation(
      const MemoryLocationIdentifier& ml_id, llvm::json::Object payload)
      -> std::size_t {
    const auto unique_id = ml_id.getUniqueId();
    const auto node_id = memory_location_id_map_.find(unique_id);
    if (node_id != memory_location_id_map_.end()) {
      return node_id->second;
    }
    const auto fresh_id =
        nodes_.add(kDatalogMemoryLocation, std::move(payload));
    memory_location_id_map_[unique_id] = fresh_id;
    return fresh_id;
  }

  // Assumes you've already added a node for the user
  void addUseEdges(const llvm::User& user) {
    const auto maybeCallSite = asCallSite(user);
    for (const auto& use : user.operands()) {
      // NOTE(ww): Skip any uses that are MetadataAsValue references,
      // since they're likely references to debug nodes that we haven't
      // visited yet. Visiting them here would cause us to incorrectly tag them
      // as UnclassifiedNodes.
      // See: https://gitlab-ext.galois.com/mate/MATE/-/issues/1058
      if (llvm::isa<llvm::MetadataAsValue>(*use.get())) {
        continue;
      }

      llvm::json::Object payload;
      payload["operand_number"] = use.getOperandNo();

      // Add additional labels for phi nodes
      if (llvm::isa<llvm::PHINode>(user)) {
        const auto& phi_node = llvm::cast<llvm::PHINode>(user);
        payload["incoming_block"] = addNode(*phi_node.getIncomingBlock(use));
      }

      // Add additional labels for call sites
      if (maybeCallSite.hasValue()) {
        const auto callSite = maybeCallSite.getValue();
        if (callSite.isCallee(&use)) {
          payload["is_callee"] = true;
        } else if (callSite.isArgOperand(&use)) {
          payload["is_argument_operand"] = true;
        }
      }

      addUseEdge(user, use, std::move(payload));
    }
  }

  // Assumes you've already added a node for the user
  auto addUseEdge(
      const llvm::User& user, const llvm::Use& use, llvm::json::Object payload)
      -> std::size_t {
    return addEdge(*use.get(), user, kValueDefinitionToUse, std::move(payload));
  }

  // NOTE(lb): Use a variant with a given NodeType where possible for perf.
  auto addNode(const llvm::Value& value) -> std::size_t {
    return addNode(value, value_node_type(value));
  }

  auto addInstruction(const llvm::Instruction& instruction) -> std::size_t {
    return addNode(instruction, instruction_node_type(instruction));
  }

  inline void addDatalogPointsToEdges() {
    auto pa_results = getAnalysis<cclyzer::LegacyPointerAnalysis>().getResult();
    const auto context_to_string = pa_results.getContextToString();
    const auto variable_points_to = pa_results.getVariablePointsTo();
    const auto allocation_size = pa_results.getAllocationSizes();
    for (const auto& [alloc_context, alias_set_identifier, size] :
         allocation_size) {
      auto context = context_to_string.find(alloc_context)->second;
      MemoryLocationIdentifier mem_loc_id(
          alias_set_identifier, context_to_string.find(alloc_context)->second);

      llvm::json::Object payload;
      mem_loc_id.insertIntoPayload(payload);
      payload["allocation_size_bytes"] = size;
      addMemoryLocation(mem_loc_id, payload);
    }

    for (const auto& [alloc_context, alias_set_identifier, ptr_context, value] :
         variable_points_to) {
      auto context = context_to_string.find(ptr_context)->second;
      MemoryLocationIdentifier mem_loc_id(
          alias_set_identifier, context_to_string.find(alloc_context)->second);
      addPointsToEdge(*value, context, mem_loc_id);
    }

    for (const auto& [to_alloc_context, ptr_to, from_alloc_context, ptr_from] :
         pa_results.getPointerPointsTo()) {
      addPointsToEdge(
          MemoryLocationIdentifier(
              ptr_from, context_to_string.find(from_alloc_context)->second),
          MemoryLocationIdentifier(
              ptr_to, context_to_string.find(to_alloc_context)->second));
    }

    for (const auto& [alloc_context, alloc1, alloc2] :
         pa_results.getAllocMayAlias()) {
      addMayAliasEdge(
          MemoryLocationIdentifier(
              alloc1, context_to_string.find(alloc_context)->second),
          MemoryLocationIdentifier(
              alloc2, context_to_string.find(alloc_context)->second));
    }

    for (const auto& [alloc_context, alloc1, alloc2] :
         pa_results.getAllocMustAlias()) {
      addMustAliasEdge(
          MemoryLocationIdentifier(
              alloc1, context_to_string.find(alloc_context)->second),
          MemoryLocationIdentifier(
              alloc2, context_to_string.find(alloc_context)->second));
    }

    for (const auto& [alloc_context, alloc1, alloc2] :
         pa_results.getAllocSubregion()) {
      addSubregionEdge(
          MemoryLocationIdentifier(
              alloc2, context_to_string.find(alloc_context)->second),
          MemoryLocationIdentifier(
              alloc1, context_to_string.find(alloc_context)->second));
    }

    for (const auto& [alloc_context, alloc1, alloc2] :
         pa_results.getAllocContains()) {
      addContainsEdge(
          MemoryLocationIdentifier(
              alloc1, context_to_string.find(alloc_context)->second),
          MemoryLocationIdentifier(
              alloc2, context_to_string.find(alloc_context)->second));
    }

    for (const auto& [alloc_context, memory_loc, ptr_context, const_value] :
         pa_results.getOperandPointsTo()) {
      // Can't store to or load from a null pointer!
      if (memory_loc == "*null*") continue;
      auto context = context_to_string.find(ptr_context)->second;
      MemoryLocationIdentifier mem_loc_id(
          memory_loc, context_to_string.find(alloc_context)->second);
      for (const auto& user : const_value->users()) {
        if (llvm::isa<llvm::LoadInst>(user)) {
          const auto* load = llvm::cast<llvm::LoadInst>(user);
          addEdgeFromMemory(mem_loc_id, *load, context, kDatalogLoadMemory);
        } else if (llvm::isa<llvm::StoreInst>(user)) {
          const auto* store = llvm::cast<llvm::StoreInst>(user);
          if (store->getPointerOperand() == const_value) {
            addEdgeToMemory(*store, context, mem_loc_id, kDatalogStoreMemory);
          }
        }
      }
    }

    static const boost::flyweight<std::string> kEmptyCtxt("nil");
    for (const auto& [global_val, memory_loc] :
         pa_results.getGlobalAllocations()) {
      addEdgeToMemory(
          *global_val,
          kEmptyCtxt,
          MemoryLocationIdentifier(memory_loc, kEmptyCtxt),
          kAllocates);
    }

    addAllocatesEdges(pa_results.getAllocationSites());
  }

  auto addNode(const llvm::Value& value, NodeType type) -> std::size_t {
    return addNode(value, type, llvm::json::Object{});
  }

  auto addNode(
      const llvm::Value& value, NodeType type, llvm::json::Object payload)
      -> std::size_t {
    const auto id = nodes_.find(value);
    if (id.hasValue()) {
      return id.getValue();
    }

    const auto fresh_id = nodes_.add(&value, type, std::move(payload));

    // User is a superclass of Constant and GlobalVariable, so we can cast
    // without checks
    switch (type) {
      FALLTHROUGH_CONSTANT_CASES
      case kConstant: {
        addUseEdges(llvm::cast<llvm::User>(value));
        break;
      }
      case kGlobalVariable: {
        const auto& global = llvm::cast<llvm::GlobalVariable>(value);
        if (global.hasInitializer()) {
          const auto* initializer = global.getInitializer();
          if (initializer != nullptr) {
            addNode(*initializer);
            addEdge(global, *initializer, kGlobalToInitializer);
          }
        }
        addUseEdges(global);
        break;
      }
      default:
        break;
    }

    // Add the value's LLVM type to the graph as well
    const auto* valueType = value.getType();
    if (valueType != nullptr) {
      // Local variables are treated specially because the Value that
      // represents them is metadata, whereas we want the underlying
      // alloca's type.
      if (type != kLocalVariable) {
        addValueType(value, *valueType);
      }
    }
    return fresh_id;
  }

  // NOTE(lb): It's always good to use the variants of addEdge that take node
  // IDs when possible, to avoid unnecessary lookups.
  auto addEdge(
      const llvm::Value& source,
      const llvm::Value& destination,
      const EdgeType type) -> std::size_t {
    return addEdge(source, destination, type, llvm::json::Object{});
  }

  auto addEdge(
      const llvm::Value& source,
      const llvm::Value& destination,
      const EdgeType type,
      llvm::json::Object payload) -> std::size_t {
    return addEdge(
        addNode(source), addNode(destination), type, std::move(payload));
  }

  auto addEdge(
      std::size_t source_id, std::size_t destination_id, const EdgeType type)
      -> std::size_t {
    return edges_.add(source_id, destination_id, type, llvm::json::Object({}));
  }

  auto addEdge(
      std::size_t source_id,
      std::size_t destination_id,
      const EdgeType type,
      llvm::json::Object payload) -> std::size_t {
    return edges_.add(source_id, destination_id, type, std::move(payload));
  }

  auto addPointsToEdge(
      const MemoryLocationIdentifier& ptr_from,
      const MemoryLocationIdentifier& ptr_to) -> std::size_t {
    llvm::json::Object payload;
    auto from_id = addMemoryLocation(ptr_from);
    auto to_id = addMemoryLocation(ptr_to);
    return edges_.add(from_id, to_id, kDatalogPointsTo, payload);
  }

  auto addPointsToEdge(
      const llvm::Value& value,
      const boost::flyweight<std::string>& context,
      const MemoryLocationIdentifier& ml_id) -> std::size_t {
    return addEdgeToMemory(value, context, ml_id, kDatalogPointsTo);
  }

  auto addMayAliasEdge(
      const MemoryLocationIdentifier& ptr_from,
      const MemoryLocationIdentifier& ptr_to) -> std::size_t {
    llvm::json::Object payload;
    auto from_id = addMemoryLocation(ptr_from);
    auto to_id = addMemoryLocation(ptr_to);
    return edges_.add(from_id, to_id, kDatalogMayAlias, payload);
  }

  auto addMustAliasEdge(
      const MemoryLocationIdentifier& ptr_from,
      const MemoryLocationIdentifier& ptr_to) -> std::size_t {
    llvm::json::Object payload;
    auto from_id = addMemoryLocation(ptr_from);
    auto to_id = addMemoryLocation(ptr_to);
    return edges_.add(from_id, to_id, kDatalogMustAlias, payload);
  }

  auto addSubregionEdge(
      const MemoryLocationIdentifier& ptr_from,
      const MemoryLocationIdentifier& ptr_to) -> std::size_t {
    auto from_id = addMemoryLocation(ptr_from);
    auto to_id = addMemoryLocation(ptr_to);
    return edges_.add(
        from_id, to_id, kDatalogSubregion, llvm::json::Object({}));
  }

  auto addContainsEdge(
      const MemoryLocationIdentifier& ptr_from,
      const MemoryLocationIdentifier& ptr_to) -> std::size_t {
    auto from_id = addMemoryLocation(ptr_from);
    auto to_id = addMemoryLocation(ptr_to);
    return edges_.add(from_id, to_id, kDatalogContains, llvm::json::Object({}));
  }

  auto addEdgeToMemory(
      const llvm::Value& value,
      const boost::flyweight<std::string>& context,
      const MemoryLocationIdentifier& ml_id,
      EdgeType type) -> std::size_t {
    auto value_id = addNode(value);
    auto location_id = addMemoryLocation(ml_id);
    llvm::json::Object payload;
    payload["context"] = context.get();
    return edges_.add(value_id, location_id, type, payload);
  }

  auto addEdgeFromMemory(
      const MemoryLocationIdentifier& ml_id,
      const llvm::Value& value,
      const boost::flyweight<std::string>& context,
      EdgeType type) -> std::size_t {
    auto value_id = addNode(value);
    auto location_id = addMemoryLocation(ml_id);
    llvm::json::Object payload;
    payload["context"] = context.get();
    return edges_.add(location_id, value_id, type, payload);
  }

  [[nodiscard]] auto callees(const llvm::CallBase* call_site)
      -> std::set<std::tuple<
          boost::flyweight<std::string>,
          boost::flyweight<std::string>,
          const llvm::Function*>> {
    if (!datalog_pointer_analysis) {
      static const boost::flyweight<std::string> kEmptyCtxt("nil");
      const auto* callee = call_site->getCalledFunction();
      if (callee != nullptr) {
        return std::set<std::tuple<
            boost::flyweight<std::string>,
            boost::flyweight<std::string>,
            const llvm::Function*>>(
            {std::tuple(kEmptyCtxt, kEmptyCtxt, callee)});
      }
      return std::set<std::tuple<
          boost::flyweight<std::string>,
          boost::flyweight<std::string>,
          const llvm::Function*>>({});
    }
    std::set<std::tuple<
        boost::flyweight<std::string>,
        boost::flyweight<std::string>,
        const llvm::Function*>>
        ret;
    // Check for this instruction in the datalog callgraph results
    auto& pa_results =
        getAnalysis<cclyzer::LegacyPointerAnalysis>().getResult();
    const auto& callees = pa_results.getCallGraph().equal_range(call_site);
    const auto& context_to_string = pa_results.getContextToString();

    for (auto callee = callees.first; callee != callees.second; ++callee) {
      auto caller_ctx =
          context_to_string.find(std::get<0>(callee->second))->second;
      auto callee_ctx =
          context_to_string.find(std::get<1>(callee->second))->second;
      auto callee_fun = llvm::cast<llvm::Function>(std::get<2>(callee->second));
      auto entry = std::tuple(caller_ctx, callee_ctx, callee_fun);
      ret.insert(entry);
    }

    return ret;
  }

  [[nodiscard]] auto mightBeNull(const llvm::Value& value) const
      -> llvm::Optional<bool> {
    return might_be_null(value, maybe_null_set_);
  }

  /* End non-datalog pointer analysis */

  llvm::DenseMap<const llvm::Type*, std::size_t> type_node_id_map_;
  std::map<boost::flyweight<std::string>, std::size_t> memory_location_id_map_;
  llvm::Optional<std::set<const llvm::Value*>> maybe_null_set_;

  Nodes nodes_;
  Edges edges_;
};

char ASTGraphWriter::ID = 0;
static llvm::RegisterPass<ASTGraphWriter> X(
    "ast-graph-writer",
    "AST Graph Writer Pass",
    true /* Only looks at CFG */,
    true /* Analysis Pass */);

}  // namespace mate
