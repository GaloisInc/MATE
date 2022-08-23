#########
Dwarfcore
#########

Dwarfcore is a framework for building plugins that query and expose MATE CPG
information (including but not limited to DWARF debug information) to the
Manticore symbolic execution engine used by Mantiserve. Dwarfcore internal
plugins are used to build ``Detector``\ s, which are the capabilities made
available to MATE users via the :doc:`mantiserve` REST API.

Detectors:
~~~~~~~~~~

The following built-in Dwarfcore Detectors are available to users of Mantiserve:

* **Variable Bounds Access Detector** -
  (:class:`~dwarfcore.detectors.dwarf_variables.DwarfVariables`) - Detects
  out-of-bounds accesses in arrays

* **Uninitialized Stack Variable Detector** -
  (:class:`~dwarfcore.detectors.uninitialized_stack_variable.DetectUninitializedStackVariable`)
  - Detects reads from uninitialized stack objects

* **Use After Free Detector** -
  (:class:`~dwarfcore.detectors.uaf.DetectUseAfterFree`) - Detects memory
  accesses to freed memory from calls to malloc and free

Internal Plugins (Not available via REST API):
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

While not exposed directly to Mantiserve users, the following internal plugins
are available for use in developing new detectors:

* **Function Tracer** - (:class:`~dwarfcore.plugins.dwarf_trace.DwarfTrace`) -
  Traces functions during ``Mantiserve`` execution

* **Variable Tracker** -
  (:class:`~dwarfcore.plugins.dwarf_track_variables.DwarfTrackVariables`) -
  Tracks stack variable information

* **Heap Memory Tracker** -
  (:class:`~dwarfcore.plugins.heap_common.TrackHeapInformation`) - Records
  memory allocations for the malloc library and system heap


See the :doc:`Dwarfcore API<api/Dwarfcore/modules>` for Python package
documentation.


Variable Bounds Detection
~~~~~~~~~~~~~~~~~~~~~~~~~

The Dwarfcore variable bounds ``Detector`` is used primarily to detect
out-of-bounds memory accesses when indexing into variables with large sizes,
like arrays.

Dwarfcore extracts variable memory boundary information so that when Manticore
performs symbolic (or concrete) memory accesses, it knows when a value could be
in or is outside of a variable's contiguous boundary in memory. Due to the
current implementation's technique of checking *every* memory access, the
recommended way of running this plugin is by specifying function and variable
pairs for which memory accesses should be analyzed.

Upon success (without using ``fast`` mode), the Manticore logs (as pulled from
the `artifacts <api.html#operation/_get_artifact_api_v1_artifacts__artifact_id__get>`_
listing associated with a Mantiserve task ID, which is accessible through a ``GET``
request to the
`tasks/{task_id} <api.html#operation/_get_manticore_task_api_v1_manticore_tasks__task_id__get>`_
:doc:`mantiserve` REST endpoint) will display relevant messages similar to the following at the end:

.. code-block::

    DEBUG: [None] ARGV_index: b'50'
    INFO: Generated testcase No. 0 - 0x401148 within function: 'overflow_field'@/mate/frontend/test/programs/triple_nested_structs.c:32:  Symbolic memory access could be out of bounds upper (0x7ffffffff752) or lower (0x7ffffffff720)

    ...

    DEBUG: [None] ARGV_index: b'0'
    INFO: Generated testcase No. 1 - 0x401148 within function: 'overflow_field'@/mate/frontend/test/programs/triple_nested_structs.c:32:  Symbolic memory access could b

    ...

    DEBUG: [None] ARGV_index: b'200'
    INFO: Generated testcase No. 2 - 0x401148 within function: 'overflow_field'@/mate/frontend/test/programs/triple_nested_structs.c:32:  Symbolic memory access could b

    ...

    DEBUG: [None] ARGV_index: b'200'
    INFO: Generated testcase No. 3 - 0x401148 within function: 'overflow_field'@/mate/frontend/test/programs/triple_nested_structs.c:32:  Symbolic memory access could be out of bounds upper (0x7ffffffff7e8) or lower (0x7ffffffff720)

    ...

    DEBUG: Manticore finished

where ``ARGV_index`` indicates the symbolic variable (``ARGV_index`` because
it's a command-line value and ``_index`` because it's used as an index for our
test; this symbolic variable is named explicitly) and its value is printed as a
proof for repeating the discovery. Manticore also generates test cases when it
find that the State's symbolic ``ARGV_index`` could point to different
variables or no variable, which gives the analyst opportunity to dig deeper
into the program logic with both cases.


Uninitialized Stack Variable Detection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This ``Detector`` detects the use of uninitialized stack variables. In order to
detect this Dwarfcore provides the detector with variable scoping and
initialization status information.

Dwarfcore is able to keep track of variables across function boundaries and
track when they are read and written. If a variable (or field within that
variable) is read before it has been written, the detector will print useful
information about the access. Without specifying any target function variable
pairs the detector defaults to checking every stack variable, thus it's
recommended way to specify any function and variable pairs for which
uninitialized use should be analyzed.

Upon success (using ``fast`` mode), the Manticore logs (as pulled from
the `artifacts <api.html#operation/_get_artifact_api_v1_artifacts__artifact_id__get>`_
listing associated with a Mantiserve task ID, which is accessible through a ``GET``
request to the
`tasks/{task_id} <api.html#operation/_get_manticore_task_api_v1_manticore_tasks__task_id__get>`_
:doc:`mantiserve` REST endpoint) will display relevant messages similar to the following at the end:

.. code-block::

    INFO: Generated testcase No. 0 - Found stack variable use before initialization txc.tai@'syscall_adjtimex' @ 0x4014b6! (/mate/frontend/test/programs/poi-kernel-cve-uninit.c:115)
    DEBUG: Manticore finished


Use After Free Detection
~~~~~~~~~~~~~~~~~~~~~~~~

As the name implies, this ``Detector`` detects and validates UAF
vulnerabilities.

The ``Detector`` captures all calls to malloc and related standard library functions. From each
call, the ``Detector`` extracts argument and return information for each
allocation.

The associated MATE logs with this behavior will be similar to:

.. code-block::

    INFO: Invoking calloc for 1 element(s) of size: 65536, state: 0
    INFO: calloc ret val: 0x435c60, state: 0
    INFO: Invoking malloc for size: 288, state: 0
    INFO: malloc ret val: 0x445c70, state: 0



The detector then uses this information to record when an allocation range
(allocation start address to allocation start + offset requested in malloc
allocation) is malloced and freed.  If the program tries to access an address
in an allocation range marked as free then a UAF has been detected!

In order to detect all UAF vulnerabilities it's important to keep allocations
unique.

For example, if an object A holds a range of memory addresses which it frees
and then are allocated to a new object B. The detector needs to be able to
distinguish between an access to the address by A and an access to the address
by B. (An access by A would be a UAF but an access by B would not). In order to
create this vital distinction the detector prevents all calls to ``free()``
from executing, forcing every allocation to have it's own unique *new* address.
As a result the following will appear in the logs:

.. code-block::

    DEBUG: Not executing call to free() for address in order to keep heap addresses unique.

Upon success (using ``fast`` mode), the Manticore logs (as pulled from
the `artifacts <api.html#operation/_get_artifact_api_v1_artifacts__artifact_id__get>`_
listing associated with a Mantiserve task ID, which is accessible through a ``GET``
request to the
`tasks/{task_id} <api.html#operation/_get_manticore_task_api_v1_manticore_tasks__task_id__get>`_
:doc:`mantiserve` REST endpoint) will display relevant messages similar to the following at the end:

.. code-block::

    INFO: Generated testcase No. 0 - Found use after free when reading address 0x425b00 @ 0x40160d (/tmp/tmpdwzt42n0.c:166)!  Allocated @ 0x4011f5 (/tmp/tmpdwzt42n0.c:44). Deallocated @ 0x401273 (/tmp/tmpdwzt42n0.c:54).
    DEBUG: Manticore finished

Where the return message will be in the generated Manticore testcases:

.. code-block::

    Found use after free when reading address 0x425b00 @ 0x40160d (/tmp/tmpdwzt42n0.c:166)!  Allocated @ 0x4011f5 (/tmp/tmpdwzt42n0.c:44). Deallocated @ 0x401273 (/tmp/tmpdwzt42n0.c:54).

The testcase results can be found through a ``GET`` request to the `tasks/{task_id}
<api.html#operation/_get_manticore_task_api_v1_manticore_tasks__task_id__get>`_
:doc:`mantiserve` REST endpoint and found in
the ``response_msg`` field of the returned object.
