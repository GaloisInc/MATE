MATE Tooling Architecture
#########################

This page provides a high-level overview of MATE's architecture,
as well as an index for tools and instrumentation components within
MATE.

Analysis Workflow
-----------------

The MATE workflow can be visualized as a transition from some source-code
representation of a program, to a compilation that can produce one
or more executables, to one CPG build per executable, and finally to individual
analyses run on each CPG:

..
  NOTE(ww): Keep this up-to-date with the image below!
  Use https://flowchart.fun to re-render any changes.

  ~~~
  layout:
    name: dagre
    rankDir: LR
  ~~~

  ingest: Source tarball
    (compilation)
  ingest: Brokered challenge
    (compilation)
  ingest: C/C++ source file
    [compilation] compilation
      executable: binary, bitcode
        CPG build: CPG
          Manticore: (analysis)
          [analysis] POI framework: analysis results
      executable: binary, bitcode
        CPG build: CPG
          Manticore: (analysis)
          POI framework: (analysis)
      executable: binary, bitcode
        CPG build: CPG
          Manticore: (analysis)
          POI framework: (analysis)
      executable: binary, bitcode
        CPG build: CPG
          Manticore: (analysis)
          POI framework: (analysis)

.. image:: assets/mate-workflow.png

System architecture
-------------------

The MATE system is decomposed into nine services which run as part of the overall
CHESS system:

server
   The ``server`` component presents a REST API that can be used to
   initiate individual steps of the analysis workflow depicted
   above. This API is used to coordinate analysis tasks in response to
   new challenges being submitted to the CHESS and also allows users
   to manually run analyses steps with custom options or changes in
   response to errors. The server API also implements backend queries
   for MATE UI components including FlowFinder.

executor
   The ``executor`` component asynchronously processes long-running
   requests initiated by the ``server`` component, such as challenge
   compilation, CPG generation, and POI analyses. For compilation and
   CPG generation steps that depend on the challenge environment, the
   executor manages creating and executing docker containers served by
   the CHESS docker registry.

db
   The ``db`` component runs a standard PostgreSQL installation and
   stores all generated Code Property Graphs. Any CHESS component
   (including other components of MATE) can access CPGs via the MATE
   domain-specific query language connecting to the database via
   the CHESS network. In addition to storing CPGs, the ``db`` component
   stores all persistent MATE system state.

storage
   The ``storage`` component supplements the ``db`` component with a
   MinIO object store and is used to store large analysis artifacts
   such as challenge source code, compiled binaries, and logs.

bridge
   The ``bridge`` component connects MATE to the CHESS message bus and
   is responsible for forwarding messages to other MATE
   components. The bridge component also creates analysis pipeline
   tasks for new challenges submitted to the CHESS challenge
   broker. These tasks run on the executor and execute the compilation,
   CPG generation, and POI analysis tasks in sequence for the challenge.

broker
   The ``broker`` component is a MATE-internal message bus used to
   coordinate MATE components.

mate-ui
   The ``mate-ui`` component serves a web-based user-interface to the
   MATE system. It provides interfaces to monitor the compilation and
   CPG generation processes, in addition to an interactive CPG
   visualization tool called Flowfinder.

notebook
   The ``notebook`` component provides a Jupyter notebook environment
   for interacting with the MATE system via the Python domain-specific
   query language. It is intended as an expert-level interface for
   accessing the full capabilities of the MATE system.

mantiserve
   The ``mantiserve`` component exposes a REST API for running
   symbolic execution queries against challenge programs. The API
   allows symbolic execution tasks to be parameterized by specific
   detector plugins that monitor for potential vulnerabilities.

Component index
---------------

Compilation components
======================

The following tools and components are responsible for compiling a program into an
LLVM bitcode module that is suitable for CPG generation.

.. _Blight_desc:

blight
~~~~~~

Provenance: ToB (`GitHub <https://github.com/trailofbits/blight>`__)

``blight`` is a build tool wrapper for C/C++ compilers (``cc`` and ``c++``) as well as the
standalone preprocessor (``cpp``), assembler (``as``), linker (``ld``), and other standard
build tools.

MATE uses ``blight`` for instrumenting arbitrary program build systems, ensuring that
they can be eventually ingested as CPGs. ``blight``'s responsibilities include:

#. Ensuring that MATE's required compilation flags are *always* passed to individual compiler
   invocations.
#. Saving an accurate record of each step in a build process, to improve recompilation fidelity.
#. Saving an accurate record of each output of each build step, so that multiple independent
   CPGs can be produced from a build system that produces more than one executable.
#. Dispatching to :ref:`gllvm_desc` for bitcode generation.

.. _gllvm_desc:

GLLVM
~~~~~

Provenance: SRI-CSL (3rd-party, `GitHub <https://github.com/SRI-CSL/gllvm>`__)

GLLVM is a suite of tools for wrapping ``clang`` and ``clang++`` to emit bitcode for every
intermediate output, as well combining those intermediate bitcode outputs into a unified
LLVM IR module.

.. _compile_v2_desc:

Compilation tasks
~~~~~~~~~~~~~~~~~

Provenance: ToB

The ``frontend/mate/mate/build/compile.py`` module manages the process
of compiling challenges submitted to the CHESS system while monitoring
and controlling the build process to create artifacts that can be
analyzed by other MATE components. This module is responsible for
creating docker environments in which to compile challenges on demand,
inferring build system configurations and necessary options, and
creating and storing artifacts for further analysis.


CPG generation components
=========================

The following tools and components are responsible for generating various components of the CPG.

.. _LLVM_passes_desc:

LLVM middle-end passes
~~~~~~~~~~~~~~~~~~~~~~

Provenance: Galois

There are three middle-end passes which read in bitcode and spew out analysis results. They are loaded dynamically using ``opt``. Consult the LLVM documentation to learn about loading passes into ``opt``.

-  Our custom pointer analysis lives in ``llvm/PointerAnalysis/PointerAnalysis.cpp``.

-  The FactGenerator supports the pointer analysis. It outputs datalog relations about elements of the input program (such as, variable ``x`` points to value ``y``), which are fed into ``cclyzer`` to infer more interesting facts related to pointer aliasing. These more interesting facts are then mapped back to LLVM concepts so they can be added to the CPG.

-  Many nodes and edges of the CPG are created in ``llvm/MATE/ASTGraphWriter.cpp``.

-  Basic blocks are instrumented to generate a trace for the dynamic analysis in ``llvm/MATE/TraceLogger.cpp``.

.. _points_to_dec:

Points-to analysis
~~~~~~~~~~~~~~~~~~

Provenance: Galois

MATE's code property graph representation is built on top of the
results of a whole-program points-to analysis. This analysis,
implemented using the `Soufflé  <https://souffle-lang.github.io/>`__
datalog engine, is a fork of the open-source LLVM points-to analysis
`cclyzer <https://github.com/plast-lab/cclyzer>`__. Improvements to
the cclyzer analysis implemented as part of MATE include support for
numerous bug fixes, support for context-sensitive analyses enabling
greater precision for many programs, and experimental support for a
more performant "Steensgaard"-style analysis mode.

The points-to analysis implementation is located in the
``llvm/PointerAnalysis/datalog`` directory.

.. _Headache_desc:

Machine-code mapping tools
~~~~~~~~~~~~~~~~~~~~~~~~~~

These tools are responsible for incorporating binary-level information into the CPG and linking
binary-level information against the core LLVM CPG elements.

.. _Nomina_desc:

Nomina
++++++

Provenance: ToB

Nomina is an LLVM pass responsible for canonicalizing the names
of basic blocks in LLVM bitcode. Nomina's canonicalization enables
different versions of LLVM running on potentially separate machines
to consistently identify the same basic blocks and associate them
with other program features.

Known problems: None

Expected problems: None

Headache
++++++++

Provenance: ToB

Headache is an LLVM pass with a collection of responsibilities:

- Extracting information about each compilation (i.e., translation) unit in the bitcode module
- Extracting variable information (VI) about each global, local, and argument in the bitcode module
- Extracting deduplicated DWARF type information (TI), for later pairing with the VI

Headache's compilation unit information extraction is used to inform :ref:`quotidian_desc`'s
recompilation.

Known problems: Headache's type extraction for template parameters is incomplete.

Expected problems: Headache performs scope unrolling to present a full picture of the lexical
scope in which a variable appears. The complexities of DWARF mean that there are probably
unhandled edge cases in Headache's scope handling.

.. _Wedlock_desc:

Wedlock
+++++++

Provenance: ToB

Wedlock is a *backend* LLVM pass responsible for pairing the IR representation of a bitcode
module with LLVM's "middle-end" representation.

Known problems: Pretty-printing LLVM's MIR is slow, so Wedlock doesn't do it by default.

Expected problems: Wedlock observes program features that are only produced during LLVM's code
generation phrase, such as ``%unwind_resume`` blocks for DWARF-style exception handling.
These can't be easily paired with the IR blocks seen during processing in LLVM frontend passes
(i.e. :ref:`Nomina_desc` and ASTGraphWriter) because they don't exist in the IR
until lowering begins.

.. _migrane_desc:

migraine
++++++++

Provenance: ToB

migraine is a Python module and utility responsible for emitting a patch of assembler directives
based on :ref:`Wedlock_desc`'s output. migraine's assembler directive patch is later used during
recompilation to generate a special ``.migraine_addrs`` section that :ref:`aspirin_desc` uses for
basic block pairing.

Known problems: None.

Expected problems: None.

.. _aspirin_desc:

aspirin
+++++++

Provenance: ToB

aspirin is a Python module and utility with a collection of responsibilities:

- Pairing each IR-level function and basic block with layout information
  (i.e. virtual address, offset, and size) in the "canonical" compiled binary
- Pairing :ref:`Headache_desc`'s variable information with each parameter and local variable in the
  compiled binary, including scoping information

Known problems: aspirin's handling of inlined functions, scopes, and variables is probably
deficient due to DWARF's complexity.

Expected problems: None.

.. _margin_walker_desc:

margin-walker
+++++++++++++

Provenance: ToB

margin-walker is a Python module and utility responsible for emitting MATE-compatible CPG records
based on the combined input of :ref:`Wedlock_desc` and :ref:`aspirin_desc`, as well as
:ref:`Headache_desc`'s type information.

Known problems: None.

Expected problems: margin-walker's runtime and memory usage will probably grow (roughly)
quadratically with program size.

.. _quotidian_desc:

quotidian
+++++++++

Provenance: ToB

quotidian is a Python module and utility that represents the primary ingress and egress for all ToB
provided instrumentation. It takes *either* a bitcode input *or* a G/WLLVM-compiled binary input.

quotidian does not require :ref:`Nomina_desc` to be run in the input bitcode beforehand. However,
failing to do so and using quotidian's bitcode elsewhere *will* cause canonicalization issues.

Known problems: None.

Expected problems: None.

Machine code mapping dependencies
+++++++++++++++++++++++++++++++++

The following depicts the dependency relations between various ToB tools and the JSONL ultimately
generated for insertion into the CPG.

.. image:: assets/tob-tool-graph.png
    :alt: Dependency relations between ToB tools and the CPG

The above image should be kept up-to-date with the following
MermaidJS specification::

    graph TD
    A[CPG JSONL] --> |margin-walker|E[Wedlock JSONL]
    A --> |margin-walker|L
    F --> |migraine|E
    F --> |migraine|G[Migraine patch]
    G --> E
    F --> |migraine|H[Unpatched ASM]
    E --> |wedlock|I[Headache IR]
    H --> |wedlock|I
    I --> |headache|J[Canonicalized IR]
    J --> |nomina|K[Uncanonicalized IR]
    K --> |clang|N[Source]
    M[Compiled binary] --> |llc|F[Migraine ASM]
    L[Aspirin JSONL] --> |aspirin|M
    L --> |aspirin|Q[headache VI JSONL]
    Q --> |headache|J
    P[headache TI JSONL] --> |headache|J
    O[CU JSONL] --> |headache|J
    A --> |margin-walker|P

Build tasks
~~~~~~~~~~~

Provenance: ToB

The ``frontend/mate/mate/build/build.py`` module manages the process
of creating code property graphs for challenges submitted to the CHESS
system. This module is responsible for creating docker environments in
which to recompile challenges and perform machine code mapping, along
with managing the overall CPG generation process. This module also
manages incorporating source code information in the CPG and applying
analysis signatures.

Analysis components
===================

CPG Query Language
~~~~~~~~~~~~~~~~~~

Provenance: Galois

MATE includes a domain-specific query language for accessing
information in the CPG. This interface abstracts the core
property-graph representation stored in the PostgreSQL database and
provides a programmatic, object-based interface in the Python
programming language. This query language, built using the
`SQLAlchemy ORM <https://docs.sqlalchemy.org/en/13/>`__, is used to
implement MATE's automated analyses and user interface, and is also
available to expert users via the Jupyter Notebook service. The
language is implemented in the ``frontend/mate-query/mate_query/cpg`` directory.

Context-free language reachability queries
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provenance: Galois

In addition to the core query language, MATE provides specialized
queries for answering "context-free language" (CFL) reachability
queries. CFL-reachability queries are reachability queries on the
graph that impose additional constraints about the nodes or edges
visited by paths in the graph---for example, requiring the
control-flow paths along function invocation and return paths
represent matching control transfers that can be realized by concrete
executions. To support CFL-reachability queries, MATE implements a
general-purpose API for implementing graph traversals guided by a
specified push-down automata that tracks required conditions. MATE
includes built-in CFL-reachability analyses for precise control-flow,
dataflow, and call-graph queries. The CFL-reachability framework is
implemented in the modules ``frontend/mate-query/mate_query/db.py`` and
``frontend/mate-query/mate_query/cfl.py``. The module
``frontend/mate-query/mate_query/cpg/query/cfg_avoiding.py`` implements a wrapper
around the functionality for common vulnerability discovery queries
that require identifying control-flow paths within the program that do
not visit specific nodes.

POI framework
~~~~~~~~~~~~~

Provenance: Galois

The "Points of Interest" (POI) framework provides facilities to register,
run, and store results from automated analyses of the code property
graph. POI analyses are managed via a REST API implemented in
``frontend/mate/mate/server/api/analyses.py`` and are executed by the
``executor`` component.

POI analyses
~~~~~~~~~~~~

Provenance: Galois/ToB

The current release of MATE includes the following built-in POI analyses. The
primary CPG layer(s) used in the analysis are listed at the end of each
description.

* **CommandInjection**: Finds calls to output functions (e.g. ``write``) with
  potential SQL keywords in string arguments, detecting SQL injection (SQLi)
  vulnerabilities. (AST)

* **PathTraversal**: Find calls to filesystem operations where the path may be
  influenced by user input, detecting path traversal vulnerabilities. (DFG)

* **PointerDisclosure**: Finds pointer-typed values that may be output to the
  user, detecting vulnerabilities that may allow an attacker to circumvent
  memory protections like ASLR and stack canaries. (DFG)

* **UserStringComparisonLength**: Finds string and memory comparison calls where
  the comparison length may be controlled by user input, detecting various
  memory corruption vulnerabilities. (DFG)

* **VariableLengthStackObject**: Detects uses of C99-style variable-length
  arrays (VLAs) or the alloca library routine where the user can control the
  size of the stack allocation, detecting vulnerability to certain stack-based
  attacks. (DFG)

* **OverflowableAllocations**: Finds calls to dynamic allocations (e.g.
  ``malloc``) where the size calculation may be influenced by user input,
  detecting unsafe or unintended heap accesses. (DFG)

* **TruncatedInteger**: Finds calls to dynamic allocations where the size may be
  influenced by user input and the input is truncated and used elsewhere as a
  signed integer, detecting vulnerabilities in which an attacker may gain
  control of the heap. (DFG)

* **IteratorInvalidation**: Finds uses of C++ iterators subsequent to
  iterator-invalidating collection modifications, detecting vulnerabilities
  resulting from invalid iterator accesses. (CFG)

* **UninitializedStackMemory**: Finds potential intra- and inter-procedural uses
  of uninitialized stack memory, detecting potential information leaks or
  computation on invalid data. (CFG, PTG)

* **UseAfterFree**: Finds potential uses of heap-allocated memory after calls to
  ``free``, detecting UAF vulnerabilities. (CFG, PTG)

These analyses are implemented as Python modules in the
``frontend/mate/mate/poi/analysis`` directory.


User interface components
=========================

ui-client and Flowfinder
~~~~~~~~~~~~~~~~~~~~~~~~

Provenance: Galois

The ``ui-client`` directory includes the browser-based frontend
interface to the MATE system, implemented in Typescript using the
React framework. It provides a user-facing interfacing for monitoring
MATE system status and viewing analysis results. Backend queries
supporting the interface are executed by the ``server`` component and
implemented by modules in the ``frontend/mate/mate/server/api`` directory.

Flowfinder is a browser-based graphical user interface for accessing
the MATE CPG and exploring MATE analysis results. It is implemented
in Typescript using React and the cytoscape.js graph visualization
framework.

Mantiserve
~~~~~~~~~~

Provenance: ToB

MATE's symbolic execution capabilities are exposed via the Mantiserve component,
located in the ``mantiserve`` directory. Mantiserve provides a REST API for
configuring symbolic execution tasks, enabling detectors for a variety of bug
classes, and managing the lifecycle of individual runs of the underlying
Manticore symbolic execution platform. Mantiserve additionally adapts
Manticore's runtime environment, allowing Manticore runs to be isolated within
containers that are identical to the "normal" execution environment for a
target.

Mantiserve tasks are configured to run one or more "detectors," representing the
dynamic counterpart to MATE's static "POI" analyses. Each detector has access to
the MATE CPG for the targeted program, including a queryable graph
representation of the program's binary layout and debug information (via DWARF).
These detectors are written using Manticore's public plugin API, and are located
in the ``dwarfcore`` directory.
