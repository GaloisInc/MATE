################################
Debugging Program Build Failures
################################

This page describes how to debug issues related to compiling programs and
building the associated Code Property Graph (CPG).

When turning a program into a CPG, MATE goes through two primary phases: it
first *compiles* the program into LLVM bitcode, and then it *builds* one or
more CPGs from that bitcode. Both phases have multiple internal steps, each of
which can fail. The sections below will help you debug some of the common
sources of failures.

.. TIP::

   The debugging information below does **not** include environmental failure
   conditions, such as out-of-memory (OOM) errors or disk space exhaustion.

*******************************
Identifying the kind of failure
*******************************

To start debugging MATE's behavior, we first need to know which phase
(compilation or building) actually failed. To do this, we can start by
checking the status of the compilation that we kicked off:

.. code-block:: bash

   $ http localhost:8666/api/v1/compilations/YOUR-COMPILATION-ID

This will return a JSON blob with metadata about the compilation, including
a ``state`` field that indicates the compilation's status:

.. code-block:: json
   :emphasize-lines: 26

   {
       "artifact_ids": [
           "71d004a9b9df42ea925950e274636d25",
           "b1959e0ab94941019fcb2f5535101ece",
           "40cd28faf8744cd1a4b4af72f03cb078",
           "c61de4d26c2d46bcba36eef744cb5355",
           "51b37cc4ef154a9aae000c2c70be3e8d"
       ],
       "build_ids": ["0a9d399e84eb4a21a1a849e4467015c1"],
       "compilation_id": "1bc760aa2ce54cc399c112818879ba6d",
       "options": {
           "containerized": false,
           "containerized_infer_build": true,
           "extra_compiler_flags": [],
           "make_targets": null,
           "testbed": null
       },
       "source_artifact": {
           "artifact_id": "71d004a9b9df42ea925950e274636d25",
           "attributes": {
               "filename": "mini-fenway-uaf.c"
           },
           "has_object": true,
           "kind": "compile-target:c"
       },
       "state": "compiled"
   }


``"state": "created"`` indicates a freshly created compilation. Compilations
should only be in this state for an **extremely short period**, i.e. for a few
milliseconds until they're picked up by the execution service. A compilation
that lingers in this state is a *potential* indicator of an environmental
failure in MATE itself, such as the ``executor`` service crashing. Consult
``docker service ls`` for more information. Keep in mind, however, that
high load on the ``executor`` service may also result in pending compilations
in the ``created`` state --- if the services look healthy, then it's likely
that the compilation is simply scheduled behind other tasks and needs some
time.

``"state": "compiling"`` indicates a compilation that's still in progress,
meaning that it can't be used to produce CPG builds yet. A compilation process
that stays in the ``compiling`` state for an unusually long time (i.e., more
than an order of magnitude longer than the compilation would take outside of
MATE) *might* indicate an error in MATE itself. No debugging action
is immediately required for a compilation in this state.

``"state": "compiled"`` indicates a successful compilation, producing one
or more bitcode outputs that are suitable for the CPG build pipeline.
Follow the steps under :ref:`Debugging a MATE CPG build <debugging-mate-build>`
for debugging failed builds once you've turned a compilation into CPG builds.

``"state": "failed"`` affirmatively indicates a failed compilation phase. Follow
the steps under
:ref:`Debugging a MATE compilation <debugging-mate-compilation>`.

.. _debugging-mate-compilation:

****************************
Debugging a MATE compilation
****************************

To begin debugging a MATE compilation, follow these steps:

#. First, check the Docker logs for the ``executor`` service, which handles
   compilation tasks. This will probably either be
   ``docker service logs mate_executor_1`` or
   ``docker container logs mate_executor_1``, depending on your deployment.

   The most common sources of compilation errors at this level are as follows:

   #. Compiler and linker flag errors. MATE runs compilations either in its own
      environment or in a container, depending on how the compilation was
      requested. In both cases, MATE uses its own build of the LLVM compiler
      toolchain for the individual build steps.

      This introduces several avenues of failure. For non-containerized
      compilations, the MATE environment may be missing linkage or tool
      dependencies. Alternatively, the MATE LLVM toolchain may not have the
      correct language or flag features for the target.

#. If the Docker logs don't show any errors or the formatting of the errors is
   too difficult to follow, you may be able to obtain additional context from
   the compilation-only log stored with each containerized compilation attempt.

   To get this log, you can request all containerized compilation logs
   from the REST API and select just the one corresponding to your compilation
   ID:

   .. code-block:: bash

      http 'localhost:8666/api/v1/artifacts?kind=compile-output:compile-log&detail=true'

   Once you have the artifact ID for the container log of interest, you can
   request the raw log contents:

   .. code-block:: bash

      http localhost:8666/api/v1/artifacts/ARTIFACT-ID/object | less


.. _compilations-what-to-do:

Fixing Your Compilation
=======================

If you encounter any of the above failure modes, compilations can be re-created
using the REST API after applying workarounds and fixes.

Compilation Step Failures
-------------------------

If an individual step within the compilation process (such as a call to the C
compiler) fails, you can try the following workarounds:

#. Disable build inference and run with an explicit set of ``make`` targets.

   For example, a compilation that only needs the ``make server`` command:

   .. code-block:: bash

      http POST localhost:8666/api/v1/compilations \
         kind="your-target-kind" \
         handle="your-target-handle" \
         options:='{"containerized_infer_build": false, "make_targets": ["server"]}'

#. Inject additional compiler flags into each ``cc`` and ``c++`` invocation.

   If you see individual compiler commands failing because of incorrect or
   overly conservative flags, you can add additional flags to every compilation
   step:

   .. code-block:: bash

      http POST localhost:8666/api/v1/compilations \
         kind="your-target-kind" \
         handle="your-target-handle" \
         options:='{"extra_compiler_flags": ["-some", "-extras"]}'

   Note that these flags are added to every compiler step, and that MATE already
   performs some flag manipulation by default (such as removing ``-Werror``).

#. Attempt a combination of the above.

.. _debugging-mate-build:

**********************
Debugging a MATE build
**********************

To debug a MATE build, we can start by retrieving the build's status from
MATE's REST API:

.. code-block:: bash

   http localhost:8666/api/v1/builds/YOUR-BUILD-ID

This will return a JSON blob (abbreviated below) with metadata about the build,
including a ``state`` field that indicates the build's status:

.. code-block:: bash
   :emphasize-lines: 25

   {
       "artifact_ids": [
           "51b37cc4ef154a9aae000c2c70be3e8d",
           "d45c693324744f948666e88b22cf7b57",
           "713969d7289d41a8bc9309dd4f9ba3ef",
           "9887d2b10968454484e841df312d98c5",
           "92a909d999b8403c8fb79bd7bfc50aa9",
           "b33e5f3b8a9444559a31e7c4eb173de9",
           "8d8e1f8563a44a46bd0afe64998aa170"
       ],
       "artifacts": [],
       "bitcode_artifact": {
           "artifact_id": "51b37cc4ef154a9aae000c2c70be3e8d",
           "attributes": {
               "compile_output": "c61de4d26c2d46bcba36eef744cb5355",
               "filename": "tmpm9zfpcsn.bc"
           },
           "has_object": true,
           "kind": "compile-output:bitcode"
       },
       "build_id": "0a9d399e84eb4a21a1a849e4467015c1",
       "compilation": { ... },
       "mantiserve_task_ids": [],
       "options": { ... },
       "state": "built"
   }


Like with compilations, ``"state": "created"`` indicates a freshly created
build. Builds should only be in the ``created`` state for an extremely short
amount of time, under normal amounts of system load. A build that lingers in
the ``created`` state for more than a few seconds is a *potential* indicator of
an environmental failure in MATE itself, such as the executor service
crashing. To confirm whether a MATE service has crashed, inspect the
state of the Docker services with ``docker service ls``.

``"state": "building"``  indicates an in-progress CPG build. No debugging action
is required for a build in this state.

``"state": "inserting"`` indicates a CPG build that has finished and is being
turned into its final database representation. No debugging action is required
for a build in this state.

``"state": "failed"`` affirmatively indicates a failed CPG build. To get to the
root cause of the build failure, follow these steps:

#. First, check the Docker logs for the ``executor`` service, which handles
   build tasks. This will probably either be
   ``docker service logs mate_executor_1`` or
   ``docker container logs mate_executor_1``, depending on your deployment.

   The most common sources of build errors at this level are as follows:

   #. Errors during recompilation. In order to produce a CPG that contains
      LLVM backend and binary-level features, MATE "recompiles" the bitcode
      produced during the compilation phase with additional instrumentation.
      Like the original compilation process, this is susceptible to
      compiler configuration and linker flag errors.

      In particular, MATE attempts to produce as complete of a CPG as possible
      by merging the bitcode produced by the compilation phase with the bitcodes
      of any static or dynamic libraries produced by the same target's build
      system that we infer as dependencies. This process isn't perfect, and
      can cause linker errors for missing or duplicated symbols.

   #. Errors and assertions during pointer analysis. MATE's pointer analysis
      component contains assertions for unexpected conditions, which will cause
      a build failure if hit. The pointer analysis component may also abort
      with a segmentation fault on certain pathological bitcode inputs,
      or with a floating point exception.

   #. Resource exhaustion. MATE's pointer analysis is limited to 32GB of RAM by
      default (or the value of ``MATE_DEFAULT_MEMORY_LIMIT_GB``, if that
      environment variables is set in the MATE server container). If the pointer
      analysis exceeds the limit, the build will fail with an error message
      indicating it could not allocate enough memory. If more resources are
      available, consider re-running the build with a higher limit set via the
      build option `memory_limit_mb`.

   #. Errors and assertions during CPG construction. One of MATE's last stages
      involves drawing edges from the LLVM-level nodes to the backend and
      binary-level nodes. This process attempts to be resilient, but makes
      certain fundamental assumptions about the correspondence between the
      different program representations (e.g., that arguments to a function
      recorded in the program's DWARF information correspond approximately
      to the LLVM-level arguments to an LLVM-level function). Violations of
      these assumptions produce an assertion, which is propagated as a build
      error.

#. Certain subcomponents of the build phase run as native LLVM passes, and
   cannot log directly to Docker. When reviewing the Docker logs above fails,
   these subcomponent logs may be of more help. One or more more messages in
   the Docker logs will indicate which subcomponent logs to inspect:

   #. A log message starting with ``Wedlock encountered some interesting
      conditions`` indicates that the "Wedlock" log should be inspected.
      The "Wedlock" log is stored as the ``build-output:quotidian-wedlock-log``
      artifact for the build.

   #. A log message starting with ``Headache encountered some interesting
      conditions`` indicates that the "Headache" log should be inspected.
      The "Headache" log is stored as the
      ``build-output:quotidian-headache-log`` artifact for the build.


   In both cases, you can use the REST API to retrieve the log's contents:

   .. code-block:: bash

      # change this as necessary
      build_id=YOUR-BUILD-ID
      target_log=build-output:quotidian-wedlock-log

      artifact_id=$(http "localhost:8666/api/v1/artifacts?kind=${target_log}&detail=true" | \
                     jq -r --arg build_id "${build_id}" \
                     '.[] | select(.build_ids | select(.[] == $build_id)) | .artifact_id')

      http localhost:8666/api/v1/artifacts/${artifact_id}/object | less

.. _builds-what-to-do:

Fixing Your Build
=================

If you encounter any of the above failure modes, builds can be re-created using
the REST API after applying workarounds and fixes.

.. important::
   POI analyses are not run automatically for builds initiated by the `REST API
   <api.html>`_. To run POI analyses for a manually-created build, wait until
   the built has completed (its state is reported as ``built``), and then submit
   a request to the ``api/v1/analyses/run/{build_id}`` endpoint supplying the
   build ID using either the REST API web page or at the command line:

   .. code-block:: bash

      http POST http://localhost:8666/api/v1/analyses/run/${build_id}


Pointer Analysis Issues
-----------------------

If you encounter resource exhaustion in the pointer analysis, you can try the
following workarounds:

#. Try rebuilding with more RAM by setting the ``memory_limit_mb`` build option
   (though this might just fail again and/or take a long time, depending on the
   program).
#. Try building with less context-sensitivity (see the ``context_sensitivity``
   build option). The default is ``2-callsite``, so you might try ``2-caller``,
   ``1-callsite`` or even ``insensitive``. The resulting analysis will be less
   precise, but hopefully more scalable.
#. Try building without bitcode merging, i.e., set ``merge_library_bitcode`` to
   ``false``. The resulting CPG may not be "complete" in the sense that it might
   not contain a representation of the whole program with all its
   accompanying libraries. Some programs may fail to build with
   ``merge_library_bitcode`` set to ``false``, particularly if they use complex
   linking instructions (e.g., libtool-based build systems).


Machine-code Mapping Issues
---------------------------

If you encounter errors in the machine-code mapping phase ("quotidian"), you can
try disabling it entirely. This will not affect any current POIs, although it
will make MATE's integration with Manticore nonfunctional for this particular
CPG.

To disable machine-code mapping, set the ``machine_code_mapping`` build option
to ``false``.
