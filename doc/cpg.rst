#######################
The Code Property Graph
#######################

..
   This first paragraph is duplicated in overview.rst; updates to one should be
   reflected in the other.

MATE primarily finds vulnerabilities by static program analysis over the
target's CPG, which combines representations of a program’s syntax,
control-flow, and dependencies into a unified graph structure that can be
queried to identify potential flaws. The MATE CPG consists of the target’s:

- abstract syntax tree (AST)
- call graph (CG)
- control-flow graph (CFG)
- inter-procedural control-flow graph (ICFG)
- inter-procedural dataflow-graph (DFG)
- control-dependence graph (CDG)
- points-to graph (PTG)
- source-code to machine-code mapping
- memory layout and DWARF type graph

The CPG is a *labeled property graph*, meaning a graph where every node or edge
has a collection of *attributes*, i.e. key/value pairs. For example, many of the
nodes in the CPG represent parts of the syntax of the input program, like
``Function`` nodes. ``Function`` nodes have attributes like "name", which can be
accessed through the `Python query API <overview_query>`_.

See :doc:`schemata/cpg` for detailed information about the various kinds of
nodes, edges, and attributes in the CPG.

General Guidelines
******************

One of the central features of the MATE CPG is a comprehensive and accurate
mapping between program representations that occur at different phases of
compilation, from the source level (LLVM bitcode), through the LLVM middle-end,
all the way to the binary and its embedded DWARF debugging information.
Thus, the CPG contains three different representations of the input program
corresponding to the following stages of compilation:

- LLVM IR
- LLVM middle-end (nodes and edges that start with "MI")
- Binary (nodes and edges that start with "MC" and "ASM")
- DWARF (nodes and edges that start with "DWARF")

The LLVM IR is considered the "default" representation, since it is most similar
to the source language (C/C++). Therefore, generic names like ``Function``,
``Block``, ``Instruction``, and ``Argument`` refer to LLVM IR constructs. Nodes
representing LLVM middle-end constructs have kinds prefixed by ``Machine``, and
binary-level node kinds are prefixed by ``ASM``.

Provenance
**********

The various "layers" of the CPG are constructed by different tools.

- abstract syntax tree (AST): :ref:`ASTGraphWriter <LLVM_passes_desc>`
- call graph (CG): :ref:`pointer analysis <overview_pointer>`
  (see also :ref:`LLVM_passes_desc`)
- control-flow graph (CFG): :ref:`ASTGraphWriter <LLVM_passes_desc>` for
  intra-procedural control-flow
- inter-procedural control-flow graph (ICFG):
  :ref:`pointer analysis <overview_pointer>`
- inter-procedural dataflow-graph (DFG):
  :ref:`pointer analysis <overview_pointer>` for flows through memory and
  calls) and :ref:`ASTGraphWriter <LLVM_passes_desc>` for intra-procedural flows
- control-dependence graph (CDG): :ref:`ASTGraphWriter <LLVM_passes_desc>`
- points-to graph (PTG): :ref:`pointer analysis <overview_pointer>`
- source-code to machine-code mapping: :ref:`machine-code mapping <Machine_desc>`
- memory layout and DWARF type graph: :ref:`machine-code mapping <Machine_desc>`
