//===- IntraProc/ControlDependenceGraph.h -----------------------*- C++ -*-===//
//
//                      Static Program Analysis for LLVM
//
// Copyright (c) 2013 President and Fellows of Harvard College
// All rights reserved.
//
// Developed by:
//
//     Scott Moore
//     Harvard School of Engineering and Applied Science
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are
// met:
//
//     Redistributions of source code must retain the above copyright
//     notice, this list of conditions and the following disclaimer.
//
//     Redistributions in binary form must reproduce the above copyright
//     notice, this list of conditions and the following disclaimer in
//     the documentation and/or other materials provided with the
//     distribution.
//
//     Neither the name of the Harvard University nor the names of the
//     developers may be used to endorse or promote products derived
//     from this software without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
// "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
// LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
// A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
// HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
// SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
// LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
// DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
// THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
//
//===----------------------------------------------------------------------===//
//
// This file defines the ControlDependenceGraph class, which allows fast and
// efficient control dependence queries. It is based on Ranganath et al.'s
// algorithm for non-termination sensitive control dependence as described in
// "A New Foundation for Control Dependence and Slicing for Modern Program
// Structures."
//
//===----------------------------------------------------------------------===//

#ifndef ANALYSIS_CONTROLDEPENDENCEGRAPH_H
#define ANALYSIS_CONTROLDEPENDENCEGRAPH_H

#include <map>

#include "llvm/ADT/DepthFirstIterator.h"
#include "llvm/ADT/GraphTraits.h"
#include "llvm/Analysis/PostDominators.h"
#include "llvm/IR/Module.h"
#include "llvm/Pass.h"
#include "llvm/Support/DOTGraphTraits.h"
//#include <set>
#include <iterator>

namespace llvm {

class BasicBlock;
class ControlDependenceGraphBase;

class ControlDependenceNode {
 public:
  enum class EdgeType { TRUE, FALSE, OTHER };
  typedef std::set<ControlDependenceNode *>::iterator node_iterator;
  using const_node_iterator = std::set<ControlDependenceNode *>::const_iterator;

  struct edge_iterator {
    using value_type = node_iterator::value_type;
    using difference_type = node_iterator::difference_type;
    using reference = node_iterator::reference;
    using pointer = node_iterator::pointer;
    using iterator_category = std::input_iterator_tag;

    edge_iterator(ControlDependenceNode *n)
        : node(n),
          stage(EdgeType::TRUE),
          it(n->TrueChildren.begin()),
          end(n->TrueChildren.end()) {
      while ((stage != EdgeType::OTHER) && (it == end)) this->operator++();
    }
    edge_iterator(
        ControlDependenceNode *n, EdgeType t, node_iterator i, node_iterator e)
        : node(n), stage(t), it(i), end(e) {
      while ((stage != EdgeType::OTHER) && (it == end)) this->operator++();
    }
    [[nodiscard]] auto type() const -> EdgeType { return stage; }
    auto operator==(edge_iterator const &other) const -> bool {
      return (this->stage == other.stage) && (this->it == other.it);
    }
    auto operator!=(edge_iterator const &other) const -> bool {
      return !(*this == other);
    }
    auto operator*() -> reference { return *this->it; }
    auto operator->() -> pointer { return &*this->it; }
    auto operator++() -> edge_iterator & {
      if (it != end) ++it;
      while ((stage != EdgeType::OTHER) && (it == end)) {
        if (stage == EdgeType::TRUE) {
          it = node->FalseChildren.begin();
          end = node->FalseChildren.end();
          stage = EdgeType::FALSE;
        } else {
          it = node->OtherChildren.begin();
          end = node->OtherChildren.end();
          stage = EdgeType::OTHER;
        }
      }
      return *this;
    }
    auto operator++(int) -> edge_iterator {
      edge_iterator ret(*this);
      assert(ret.stage == EdgeType::OTHER || ret.it != ret.end);
      this->operator++();
      return ret;
    }

   private:
    ControlDependenceNode *node;
    EdgeType stage;
    node_iterator it, end;
  };

  auto begin() -> edge_iterator { return edge_iterator(this); }
  auto end() -> edge_iterator {
    return edge_iterator(
        this, EdgeType::OTHER, OtherChildren.end(), OtherChildren.end());
  }

  auto true_begin() -> node_iterator { return TrueChildren.begin(); }
  auto true_end() -> node_iterator { return TrueChildren.end(); }

  auto false_begin() -> node_iterator { return FalseChildren.begin(); }
  auto false_end() -> node_iterator { return FalseChildren.end(); }

  auto other_begin() -> node_iterator { return OtherChildren.begin(); }
  auto other_end() -> node_iterator { return OtherChildren.end(); }

  auto parent_begin() -> node_iterator { return Parents.begin(); }
  auto parent_end() -> node_iterator { return Parents.end(); }
  [[nodiscard]] auto parent_begin() const -> const_node_iterator {
    return Parents.begin();
  }
  [[nodiscard]] auto parent_end() const -> const_node_iterator {
    return Parents.end();
  }

  [[nodiscard]] auto getBlock() const -> BasicBlock * { return TheBB; }
  [[nodiscard]] auto getNumParents() const -> size_t { return Parents.size(); }
  [[nodiscard]] auto getNumChildren() const -> size_t {
    return TrueChildren.size() + FalseChildren.size() + OtherChildren.size();
  }

 private:
  BasicBlock *TheBB{nullptr};
  std::set<ControlDependenceNode *> Parents;
  std::set<ControlDependenceNode *> TrueChildren;
  std::set<ControlDependenceNode *> FalseChildren;
  std::set<ControlDependenceNode *> OtherChildren;

  friend class ControlDependenceGraphBase;

  void clearAllChildren() {
    TrueChildren.clear();
    FalseChildren.clear();
    OtherChildren.clear();
  }
  void clearAllParents() { Parents.clear(); }

  void addTrue(ControlDependenceNode *Child);
  void addFalse(ControlDependenceNode *Child);
  void addOther(ControlDependenceNode *Child);
  void addParent(ControlDependenceNode *Parent);
  void removeTrue(ControlDependenceNode *Child);
  void removeFalse(ControlDependenceNode *Child);
  void removeOther(ControlDependenceNode *Child);
  void removeParent(ControlDependenceNode *Child);

  ControlDependenceNode() = default;
  ControlDependenceNode(BasicBlock *bb) : TheBB(bb) {}
};

template <>
struct GraphTraits<ControlDependenceNode *> {
  using NodeRef = ControlDependenceNode *;
  using NodeType = ControlDependenceNode;
  using ChildIteratorType = NodeType::edge_iterator;

  static auto getEntryNode(NodeType *N) -> NodeType * { return N; }

  static inline auto child_begin(NodeType *N) -> ChildIteratorType {
    return N->begin();
  }
  static inline auto child_end(NodeType *N) -> ChildIteratorType {
    return N->end();
  }

  using nodes_iterator = df_iterator<ControlDependenceNode *>;

  static auto nodes_begin(ControlDependenceNode *N) -> nodes_iterator {
    return df_begin(getEntryNode(N));
  }
  static auto nodes_end(ControlDependenceNode *N) -> nodes_iterator {
    return df_end(getEntryNode(N));
  }
};

class ControlDependenceGraphBase {
 public:
  ControlDependenceGraphBase() = default;
  virtual ~ControlDependenceGraphBase() { releaseMemory(); }
  virtual void releaseMemory() {
    for (auto node : nodes) delete node;
    nodes.clear();
    bbMap.clear();
    root = nullptr;
  }

  void graphForFunction(Function &F);

  auto getRoot() -> ControlDependenceNode * { return root; }
  [[nodiscard]] auto getRoot() const -> const ControlDependenceNode * {
    return root;
  }
  auto operator[](const BasicBlock *BB) -> ControlDependenceNode * {
    return getNode(BB);
  }
  auto operator[](const BasicBlock *BB) const -> const ControlDependenceNode * {
    return getNode(BB);
  }
  auto getNode(const BasicBlock *BB) -> ControlDependenceNode * {
    return bbMap[BB];
  }
  auto getNode(const BasicBlock *BB) const -> const ControlDependenceNode * {
    return (bbMap.find(BB) != bbMap.end()) ? bbMap.find(BB)->second : NULL;
  }
  auto controls(BasicBlock *A, BasicBlock *B) const -> bool;
  auto influences(BasicBlock *A, BasicBlock *B) const -> bool;

 private:
  ControlDependenceNode *root{nullptr};
  std::set<ControlDependenceNode *> nodes;
  std::map<const BasicBlock *, ControlDependenceNode *> bbMap;
  static auto getEdgeType(const BasicBlock *, const BasicBlock *)
      -> ControlDependenceNode::EdgeType;
  void computeDependencies(Function &F);
};

class ControlDependenceGraph : public FunctionPass,
                               public ControlDependenceGraphBase {
 public:
  static char ID;

  ControlDependenceGraph() : FunctionPass(ID), ControlDependenceGraphBase() {}
  ~ControlDependenceGraph() override = default;
  void getAnalysisUsage(AnalysisUsage &AU) const override {
    AU.setPreservesAll();
  }

  // NOTE(ww): Probable clang-tidy bug;
  // see llvm/MATE/TraceLogger.cpp for another example of this.
  // NOLINTNEXTLINE(modernize-use-trailing-return-type)
  bool runOnFunction(Function &F) override {
    graphForFunction(F);
    return false;
  }
};

template <>
struct GraphTraits<ControlDependenceGraph *>
    : public GraphTraits<ControlDependenceNode *> {
  static auto getEntryNode(ControlDependenceGraph *CD) -> NodeType * {
    return CD->getRoot();
  }

  static auto nodes_begin(ControlDependenceGraph *CD) -> nodes_iterator {
    if (getEntryNode(CD)) return df_begin(getEntryNode(CD));
    return df_end(getEntryNode(CD));
  }

  static auto nodes_end(ControlDependenceGraph *CD) -> nodes_iterator {
    return df_end(getEntryNode(CD));
  }
};

template <>
struct DOTGraphTraits<ControlDependenceGraph *> : public DefaultDOTGraphTraits {
  DOTGraphTraits(bool isSimple = false) : DefaultDOTGraphTraits(isSimple) {}

  static auto getGraphName(ControlDependenceGraph *Graph) -> std::string {
    (void)Graph;
    return "Control dependence graph";
  }

  auto getNodeLabel(ControlDependenceNode *Node, ControlDependenceGraph *Graph)
      -> std::string {
    if (Node == Graph->getRoot()) {
      return "ENTRY";
    }
    std::string pretty_string((std::string::size_type)0, 0);
    pretty_string.reserve(1024);
    llvm::raw_string_ostream raw_pretty_stream(pretty_string);
    raw_pretty_stream.SetUnbuffered();
    raw_pretty_stream << *(Node->getBlock());
    return pretty_string;
  }

  static auto getEdgeSourceLabel(
      ControlDependenceNode *Node, ControlDependenceNode::edge_iterator I)
      -> std::string {
    (void)Node;
    switch (I.type()) {
      case ControlDependenceNode::EdgeType::TRUE:
        return "T";
      case ControlDependenceNode::EdgeType::FALSE:
        return "F";
      case ControlDependenceNode::EdgeType::OTHER:
        return "";
    }
    llvm_unreachable("Invalild ControlDependenceNode type");
  }
};

class ControlDependenceGraphs : public ModulePass {
 public:
  static char ID;

  ControlDependenceGraphs() : ModulePass(ID) {}
  ~ControlDependenceGraphs() override { graphs.clear(); }

  // NOTE(ww): Probable clang-tidy bug;
  // see llvm/MATE/TraceLogger.cpp for another example of this.
  // NOLINTNEXTLINE(modernize-use-trailing-return-type)
  bool runOnModule(Module &M) override {
    for (Function &F : M) {
      if (F.isDeclaration()) continue;
      ControlDependenceGraphBase &cdg = graphs[&F];
      cdg.graphForFunction(F);
    }
    return false;
  }

  void getAnalysisUsage(AnalysisUsage &AU) const override {
    AU.setPreservesAll();
  }

  auto operator[](const Function *F) -> ControlDependenceGraphBase & {
    return graphs[F];
  }
  auto graphFor(const Function *F) -> ControlDependenceGraphBase & {
    return graphs[F];
  }

 private:
  std::map<const Function *, ControlDependenceGraphBase> graphs;
};

}  // namespace llvm

#endif  // ANALYSIS_CONTROLDEPENDENCEGRAPH_H
