####################
MATE System Overview
####################

.. image:: assets/mate-architecture.jpg

MATE is a suite of tools for interactive program analysis with a focus on
hunting for bugs in C and C++ code. MATE unifies application-specific and
low-level vulnerability analysis using code property graphs (CPGs), enabling the
discovery of highly application-specific vulnerabilities that depend on both
implementation details and the high-level semantics of target C/C++ programs.

*****************
The MATE Workflow
*****************

Given a C/C++ program MATE performs both whole program static and dynamic
analyses which can be combined in search of vulnerabilities.

The static analyses works by first compiling the target program to a single
``.ll`` or ``.bc`` LLVM Intermediate Representation (IR) file using
`GLLVM <https://github.com/SRI-CSL/gllvm>`_. MATE
then constructs a CPG from the IR by compiling it with a custom build of LLVM.
The database can be queried using a Python query interface (see below) which
provides relevant domain-specific query abilities, such as searching for
control-flow paths with certain properties.

When a program is built with MATE, MATE performs a collection of built-in
analyses for common vulnerabilities types, and reports findings as Points of
Interest. See the :doc:`POI Analyses <analysis>` documentation for details.

To enable users to effectively explore potential vulnerabilities
discovered by MATE's automated analyses and apply their insights to
find concrete evidence of exploitability, MATE includes a custom
graphical user interface component Flowfinder. Flowfinder allows users to
explore the CPG by interacting with a point-and-click graph
visualization of the program, rather than manually reviewing source
code or writing complex analysis queries.

To answer more complex questions about the program, users can also access an
interactive notebook service that gives programmatic access to the full CPG
representation via a domain-specific query language. These notebooks can be used
for one-off explorations, or as a platform for users to build reusable apps on
the MATE platform. MATE includes the :doc:`UsageFinder <usagefinder>` app for
finding vulnerabilities that result from incorrect usage of internal or external
APIs.

MATE includes the `Manticore <https://github.com/trailofbits/manticore>`_
symbolic execution engine, which can be used to complement MATE's static
analysis capabilities with dynamic analysis for further exploration and
validation of the behavior of the target program.

*************
MATE Features
*************

The MATE Code Property Graph
============================

MATE combines representations of a program's syntax, control-flow, data-flow,
and the results of static analyses into a CPG that can be queried to identify
potential flaws. One of the central features of the MATE CPG is a comprehensive
and accurate mapping between program representations that occur at different
phases of compilation, from the source level (LLVM bitcode), through the LLVM
middle-end, all the way to the binary and its embedded DWARF debugging
information. For more information on the CPG, see :doc:`schema <schemata/cpg>`.

Pointer Analysis
================
..
   TODO(lb, #1708): Link to upstream pointer analysis documentation

MATE uses a precise, context-sensitive pointer analysis for C and C++ that
allows for accurate, narrow tracking of data- and control-flow through the
program under analysis. For more on the pointer analysis in MATE, see :doc:`the
documentation <standalonepa>`.

The Query Interface
===================

MATE provides a SQLAlchemy-based Domain Specific Language (DSL) for querying the
CPG, embedded in Python. It has abstractions relevant to program analysis, for
example, control- and data-flow path queries. See the
:doc:`API documentation <api/MATE/modules>` for more information.

POI Queries
===========

POI (Point-Of-Interest) queries are CPG queries written by MATE users and
developers that identify potentially problematic spots in a code base. These
can then be triaged with human assistance or examined using directed symbolic
execution. See :doc:`Vulnerability Types <vulnerability-types>` for
more information.

Flowfinder
==========

Flowfinder is an interactive, graphical user interface for exploring a
program's code property graph. Given a potential vulnerability
discovered via MATE's automated analyses, Flowfinder displays relevant
fragments of the CPG that explain relationships between program inputs,
outputs, and computations. Users can deepen their understanding of the
potential vulnerability by viewing additional fragments of the CPG
that answer specific questions about program elements, such as data
flows or control dependencies that influence specific statements. By
exploring a potential vulnerability using Flowfinder, users can apply
their high-level insights about the program's semantics and security
requirements to eliminate analysis false positives or develop concrete
inputs that demonstrate the insecurity of the program. See :doc:`Using Flowfinder
<using-flowfinder>` for more information.

Symbolic Execution with Manticore
=================================

One of the goals of the CHESS program is to not only find bugs, but generate
proofs of vulnerability (PoVs) that demonstrate the problems in the target
programs. MATE's approach to assisted PoV generation uses binary-level symbolic
execution with Manticore (developed by Trail of Bits). While MATE must have
access to the program source and does extensive analysis at that level,
binary-level symbolic execution helps ensure that MATE only generates true
exploits.

Symbolic execution is incredibly powerful, in that it can solve complicated
constraints and generate inputs to a program that cause very specific behavior.
This precision comes at the cost of performance; it's prohibitively expensive
to explore all paths in a large program using a tool like Manticore. The MATE
solution is to identify possible bugs using a range of methods
(manual inspection, POI queries, fuzzing), and then to use *directed* symbolic
execution to generate PoVs. Directed symbolic execution is when the engine
(Manticore) is provided with additional constraints telling it where to look,
rather then exploring the program state space freely.

See the :doc:`Under-constrained Manticore <under-constrained-manticore>` and
:doc:`Mantiserve <mantiserve>` documentation for more information on accessing
symbolic execution functionality within MATE.
