//===- IntraProc/ControlDependenceGraph.cpp ---------------------*- C++ -*-===//
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

#include "ControlDependenceGraph.h"

#include <deque>
#include <set>

#include "llvm/ADT/PostOrderIterator.h"
#include "llvm/Analysis/DOTGraphTraitsPass.h"
#include "llvm/IR/CFG.h"
#include "llvm/IR/Function.h"

using namespace llvm;

namespace llvm {

void ControlDependenceNode::addTrue(ControlDependenceNode *Child) {
  TrueChildren.insert(Child);
}

void ControlDependenceNode::addFalse(ControlDependenceNode *Child) {
  FalseChildren.insert(Child);
}

void ControlDependenceNode::addOther(ControlDependenceNode *Child) {
  OtherChildren.insert(Child);
}

void ControlDependenceNode::addParent(ControlDependenceNode *Parent) {
  assert(
      std::find(Parent->begin(), Parent->end(), this) != Parent->end() &&
      "Must be a child before adding the parent!");
  Parents.insert(Parent);
}

void ControlDependenceNode::removeTrue(ControlDependenceNode *Child) {
  auto CN = TrueChildren.find(Child);
  if (CN != TrueChildren.end()) TrueChildren.erase(CN);
}

void ControlDependenceNode::removeFalse(ControlDependenceNode *Child) {
  auto CN = FalseChildren.find(Child);
  if (CN != FalseChildren.end()) FalseChildren.erase(CN);
}

void ControlDependenceNode::removeOther(ControlDependenceNode *Child) {
  auto CN = OtherChildren.find(Child);
  if (CN != OtherChildren.end()) OtherChildren.erase(CN);
}

void ControlDependenceNode::removeParent(ControlDependenceNode *Parent) {
  auto PN = Parents.find(Parent);
  if (PN != Parents.end()) Parents.erase(PN);
}

auto ControlDependenceGraphBase::getEdgeType(
    const BasicBlock *A, const BasicBlock *B)
    -> ControlDependenceNode::EdgeType {
  if (const auto *b = dyn_cast<BranchInst>(A->getTerminator())) {
    if (b->isConditional()) {
      if (b->getSuccessor(0) == B) {
        return ControlDependenceNode::EdgeType::TRUE;
      }
      if (b->getSuccessor(1) == B) {
        return ControlDependenceNode::EdgeType::FALSE;
      }
    }
  }
  return ControlDependenceNode::EdgeType::OTHER;
}

auto numSuccessors(BasicBlock *BB) -> unsigned int {
  unsigned int i = 0;
  for (succ_iterator SB = succ_begin(BB), SE = succ_end(BB); SB != SE; ++SB) {
    i++;
  }
  return i;
}

using path = std::pair<BasicBlock *, BasicBlock *>;

void ControlDependenceGraphBase::computeDependencies(Function &F) {
  for (BasicBlock &BB : F) {
    auto *bn = new ControlDependenceNode(&BB);
    nodes.insert(bn);
    bbMap[&BB] = bn;
  }

  std::set<BasicBlock *> workbag;
  std::set<BasicBlock *> condNodes;
  std::map<path, std::set<path>> maxpaths;

  // Initialize
  for (BasicBlock &BB1 : F) {
    path p1(&BB1, nullptr);
    std::set<path> s1;
    maxpaths[p1] = s1;
    path p2(nullptr, &BB1);
    std::set<path> s2;
    maxpaths[p2] = s2;
    for (BasicBlock &BB2 : F) {
      path p(&BB1, &BB2);
      std::set<path> s;
      maxpaths[p] = s;
    }
  }

  condNodes.insert(nullptr);
  path p(&F.getEntryBlock(), nullptr);
  maxpaths[p].insert(p);
  workbag.insert(&F.getEntryBlock());

  for (BasicBlock &BB : F) {
    if (numSuccessors(&BB) > 1) {
      condNodes.insert(&BB);
      for (succ_iterator SB = succ_begin(&BB), SE = succ_end(&BB); SB != SE;
           ++SB) {
        path p(*SB, &BB);
        maxpaths[p].insert(p);
        workbag.insert(*SB);
      }
    }
  }

  // Calculate all-path reachability
  while (!workbag.empty()) {
    BasicBlock *n = *workbag.begin();
    workbag.erase(workbag.begin());
    unsigned int numSucc = n == nullptr ? 2 : numSuccessors(n);
    if (numSucc == 1) {
      // Single successor (not a loop)
      BasicBlock *m = n->getSingleSuccessor();
      if (n != m) {
        for (BasicBlock *p : condNodes) {
          path np(n, p);
          path mp(m, p);
          for (path e : maxpaths[np]) {
            if (maxpaths[mp].insert(e).second) {
              workbag.insert(m);
              workbag.insert(p);
            }
          }
        }
      }
    } else if (numSucc > 1) {
      for (BasicBlock &SB : F) {
        BasicBlock *m = &SB;
        path mn(m, n);
        if (maxpaths[mn].size() == numSucc) {
          for (BasicBlock *p : condNodes) {
            if (p == n) continue;

            path np(n, p);
            path mp(m, p);
            for (path e : maxpaths[np]) {
              if (maxpaths[mp].insert(e).second) {
                workbag.insert(m);
                workbag.insert(p);
              }
            }
          }
        }
      }
      BasicBlock *m = nullptr;
      path mn(m, n);
      if (maxpaths[mn].size() == numSucc) {
        for (BasicBlock *p : condNodes) {
          if (p == n) continue;

          path np(n, p);
          path mp(m, p);
          for (path e : maxpaths[np]) {
            if (maxpaths[mp].insert(e).second) {
              workbag.insert(m);
              workbag.insert(p);
            }
          }
        }
      }
    }
  }

  // Calculate control dependence
  root = new ControlDependenceNode();
  nodes.insert(root);

  for (BasicBlock &BB : F) {
    BasicBlock *n = &BB;
    ControlDependenceNode *NN = bbMap[n];

    for (BasicBlock *m : condNodes) {
      path nm(n, m);
      unsigned long count = maxpaths[nm].size();
      unsigned int numSuccs = m == nullptr ? 2 : numSuccessors(m);
      if ((count > 0) && (count < numSuccs)) {
        ControlDependenceNode *MN = m == nullptr ? root : bbMap[m];
        ControlDependenceNode::EdgeType type =
            m == nullptr ? ControlDependenceNode::EdgeType::OTHER
                         : ControlDependenceGraphBase::getEdgeType(m, n);
        switch (type) {
          case ControlDependenceNode::EdgeType::TRUE:
            MN->addTrue(NN);
            break;
          case ControlDependenceNode::EdgeType::FALSE:
            MN->addFalse(NN);
            break;
          case ControlDependenceNode::EdgeType::OTHER:
            MN->addOther(NN);
            break;
        }
        NN->addParent(MN);
      }
    }
  }
}

void ControlDependenceGraphBase::graphForFunction(Function &F) {
  computeDependencies(F);
}

auto ControlDependenceGraphBase::controls(BasicBlock *A, BasicBlock *B) const
    -> bool {
  const ControlDependenceNode *n = getNode(B);
  assert(n && "Basic block not in control dependence graph!");

  std::set<const ControlDependenceNode *> visited;
  while (n->getNumParents() == 1) {
    n = *n->parent_begin();
    if (visited.find(n) == visited.end()) {
      visited.insert(n);
      if (n->getBlock() == A) return true;
    } else {
      break;
    }
  }
  return false;
}

auto ControlDependenceGraphBase::influences(BasicBlock *A, BasicBlock *B) const
    -> bool {
  const ControlDependenceNode *n = getNode(B);
  assert(n && "Basic block not in control dependence graph!");

  std::deque<ControlDependenceNode *> worklist;
  worklist.insert(worklist.end(), n->parent_begin(), n->parent_end());

  std::set<const ControlDependenceNode *> visited;
  while (!worklist.empty()) {
    n = worklist.front();
    worklist.pop_front();

    if (visited.find(n) == visited.end()) {
      visited.insert(n);
      if (n->getBlock() == A) return true;
      worklist.insert(worklist.end(), n->parent_begin(), n->parent_end());
    }
  }

  return false;
}
}  // namespace llvm

namespace {

struct ControlDependenceViewer
    : public DOTGraphTraitsViewer<ControlDependenceGraph, false> {
  static char ID;
  ControlDependenceViewer()
      : DOTGraphTraitsViewer<ControlDependenceGraph, false>(
            "control-deps", ID) {}
};

struct ControlDependencePrinter
    : public DOTGraphTraitsPrinter<ControlDependenceGraph, false> {
  static char ID;
  ControlDependencePrinter()
      : DOTGraphTraitsPrinter<ControlDependenceGraph, false>(
            "control-deps", ID) {}
};

}  // end anonymous namespace

char ControlDependenceGraph::ID = 0;
static RegisterPass<ControlDependenceGraph> Graph(
    "function-control-deps", "Compute control dependency graphs", true, true);

char ControlDependenceGraphs::ID = 0;
static RegisterPass<ControlDependenceGraphs> Graphs(
    "module-control-deps",
    "Compute control dependency graphs for an entire module",
    true,
    true);

char ControlDependenceViewer::ID = 0;
static RegisterPass<ControlDependenceViewer> Viewer(
    "view-control-deps", "View the control dependency graph", true, true);

char ControlDependencePrinter::ID = 0;
static RegisterPass<ControlDependencePrinter> Printer(
    "print-control-deps",
    "Print the control dependency graph as a 'dot' file",
    true,
    true);
