##########
Mantiserve
##########

.. important::
   Users interact with Mantiserve via the the MATE REST API.
   See the documentation `here <api.html>`_.

*Mantiserve* is a service included with MATE that serves a REST API to start,
check, and kill *Manticore* tasks. Mantiserve uses the MATE-built target binary
and associated CPG to perform its analyses.

*Manticore* is a symbolic execution tool for analysis of binaries. It executes a
target program to explore its behavior as related to user-controlled input.
Manticore provides a rich API to write plugins that can detect and report on
program properties like all possible values of an input at a certain point
during execution. When paired with MATE and the CPG, Manticore plugins can
perform deep inspection of the program during execution to detect the potential for
and impact of various forms of memory corruption, violation of memory safety,
and other issues.

*****
Usage
*****

.. _mantiserve-usage:

The primary usage of Mantiserve is through the REST API located at
`<http://localhost:8666/api/v1/>`_, which you can visit on your browser for a nicely
formatted FastAPI help page where you can hit the endpoints and peruse the different message
schemas.

Each Mantiserve task kind requires a ``build_id`` (listed next to each target on the MATE Dashboard
at `<http://localhost:8050/build>`_). This build ID is used to determine Manticore's target
binary, as well as the Docker image to isolate Manticore's execution within (unless
overridden by :ref:`docker_image <specifying-a-docker_image>`).

Within the message request body you may also
optionally specify a memory limit, in MB, to impose when using Manticore within
a Docker container (:ref:`docker_memory_limit_mb <specifying-a-docker-memory-limit>`).


.. important::
   It is **highly** recommended to provide a Docker image that is representative
   of the deployed execution environment for the target program. Not only will
   this provide all of the necessary files, environment variables, and
   dependencies, but Docker provides system isolation for each run which is
   crucial for accurate and repeatable results.

Manticore executes a program just as the program itself would run. Because
Manticore does not perfectly isolate program behavior and side-effects,
Manticore execution could make permanent changes\ [#]_ to the filesystem or
even the operating system itself. This could interfere with simultaneous runs
of a Mantiserve task and affect reproducibility of results.  Without providing
a docker image, all runs execute in the ``mate_executor`` container and could
potentially disrupt other tasks and processes that run on that container.

.. [#] By "permanent changes," we mean to say that Manticore does not totally
   isolate execution side-effects of the target program. If the target issues a
   deletion of a file during normal execution, then that file is likely to
   really be deleted on the computer running Manticore. By running Manticore in
   a new Docker container every time, we rely on Docker's isolation mechanisms
   as a good-enough solution for more deterministic analysis when Manticore is
   run multiple times.

.. _running-a-task:

==============
Running a task
==============

There are two kinds of tasks with corresponding endpoints:

.. _reachability-doc:

* **Reachability** - `reachability
  <api.html#operation/_execute_manticore_reachability_task_api_v1_manticore_reachability__build_id__post>`_
  - Guide Manticore along a path that you'd like to execute, and upon completion
  of the final ``Waypoint``, Manticore will return a concrete input that leads to
  that location. If Manticore is unable to follow your path, it will continue to
  execute until it has exhausted all possible paths. This task can also be done
  with a ``Detector`` enabled.

.. _exploration-doc:

* **Exploration** - `exploration
  <api.html#operation/_execute_manticore_exploration_task_api_v1_manticore_explore__build_id__post>`_
  - Choose a ``Detector`` and allow Manticore to execute and explore the binary given
  only initial command-line arguments, ``stdin`` parameters, or information related
  to the respective ``Detector``. Manticore will continue exploring until it has found
  something\ [#]_.

See the FastAPI webpage and :ref:`Detectors <detectors>` for more details about
the kinds of messages and structures that are expected.

.. [#] Unfortunately, Manticore is not perfect and could be missing
   implementations of system calls, assembly instruction semantics, or
   encountered an implementation bug. Furthermore, Manticore could exhaust any
   one of a host machine's resources, like RAM or storage. If Manticore is
   unable to recover, the Mantiserve task will attempt to save any log output
   from the run as an ``artifact`` (which can be downloaded from the `artifacts
   <api.html#operation/get_artifacts_api_v1_artifacts_get>`_ MATE REST
   endpoint) and set the task status accordingly. If you find that Manticore
   returns an error, please save and send us the logs!

.. _task-status:

================
Status of a Task
================

To check on the status, locate your unique task id (or query the status of the
build id) and send a REST request to the `tasks/{task_id}
<api.htmll#operation/_get_manticore_task_api_v1_manticore_tasks__task_id__get>`_
Mantiserve REST endpoint.

Furthermore, the logs for a task will be saved when the task stops execution.
The artifact ID for the log is included during querying of a task status.

.. _kill-manti-task:

================
Killing a Task
================

To kill a Manitserve task, you must have the unique task id and then send an
``HTTP PATCH`` request to the `stop
<api.html#operation/_stop_manticore_task_api_v1_manticore_tasks__task_id__stop_patch>`_
Mantiserve REST endpoint.

See :ref:`Strategies for Activating Mantiserve <strategies-for-activation>` for
deciding when it might be appropriate to kill a task.

=========================
Mantiserve Request Fields
=========================

.. code-block:: json

   {
       "docker_image": "<docker_image>",
       "docker_memory_limit_mb": 64,
       "explore_msg": {
            "command_line_flags": ["arg0", "arg1"],
            "concrete_start": "",
            "stdin_size": 256,
            "env": {"ENV_VAR": "VAL"}
        }
   }

.. code-block:: json

   {
       "docker_image": "<docker_image>",
       "docker_memory_limit_mb": 64,
       "reach_msg": {
            "command_line_flags": ["arg0", "arg1"],
            "concrete_start": "",
            "stdin_size": 256,
            "env": {"ENV_VAR": "VAL"}
            "waypoints": [
                {
                    "start": {
                        "va": 0
                    },
                    "end": {
                        "va": 0
                    },
                    "asserts": [
                        {
                            "location": {
                                "va": 0
                            },
                            "constraint": [
                                {
                                    "expr": "string",
                                    "id": [
                                        {}
                                    ]
                                }
                            ]
                        }
                    ],
                    "replacements": [
                        {
                            "location": {
                            "va": 0
                        },
                            "model": {
                                "python_code": "string"
                            }
                        }
                    ]
                }
            ],
            "constraint_vars": [
                {
                    "name": "string",
                    "value": "string",
                    "expr": "string"
                }
            ]
        }
   }


.. _specifying-a-docker_image:

* ``"docker_image"``: This **optional** field specifies the docker image that will be pulled
  where Mantiserve will insert a Manticore instance. This image must be valid with a
  ``docker pull <docker_image>``. It is HIGHLY recommended to use a Docker image to isolate
  Manticore's side-effects.

  If an image is not specified in the request, Mantiserve will use the corresponding CPG build's
  Docker image, if the CPG build was performed within a Docker container. If the corresponding
  build does not have an image, Mantiserve will execute the request within the
  ``mate_executor`` container itself. (See :ref:`Usage<mantiserve-usage>`)

.. _specifying-a-docker-memory-limit:

* ``"docker_memory_limit_mb"``: This field specifies the memory limit, in MB, to impose when using
  Manticore within a Docker container. It will be set by default to 64 GB if no value is specified.
  (See :ref:`Usage<mantiserve-usage>`)

* ``"explore_msg"`` or ``"reach_msg"``: This field specifies the message with details for Explore
  and Reachability modes. (See :ref:`Running a Task<running-a-task>`)

.. _request-path:

* ``"command_line_flags"``: Arguments passed to the program (``argv``) at time
  of execution.

* ``"stdin_size"``: When executing Manticore has a maximum number of purely
  symbolic (can be any value) bytes it can read from the stdin. This field
  specifies that number. If this is not specified the field defaults to 256. It
  is recommended to set this to a smaller number than 256 at the discretion of
  the user based on the program.

* ``"concrete_start"``: This field specifies a string of readable concrete
  bytes the symbolic executor reads before any purely symbolic bytes are read
  (see ``"stdin_size"``). If this is not specified only symbolic bytes are
  read.

* ``"env"``: This field specifies a dictionary of environment variables that
  are available to the program of interest during execution.

* ``"waypoints"``: This field contains a list of ``Waypoints``. Each ``Waypoint``
  contains ``Assertions`` and ``Replacements`` for a block of code defined by
  ``va_start`` and ``va_end``.

* ``"constraint_vars"``: This field contains a list of initial declarations for
  symbolic variables.

.. _detectors:

=========
Detectors
=========
To use a detector with either the `Exploration <exploration-doc>` or
`Reachability <reachability-doc>` modes, add the ``"detector_options"``
field to the request

.. code-block:: json

   "detector_options": {
      "fast": true,
      "detector": "UseAfterFree",
      "poi_info": []
   }

There are 3 types of ``Detector``\ s  available to Mantiserve tasks:

* **Variable Bounds Access Detector**:
  Specify ``"detector": "VariableBoundsAccess"`` within ``"detector_options"`` to use this field.

The Variable Bounds Access Detector searches for out of bounds memory access on
the stack.

If specified, the detector will only look at given function to variable pairs,
otherwise the detector will search for every possible out of bounds stack use
and detect the first out of bounds access on each given path. When a
vulnerability is found on a given path, the detector will return the function
name, variable name, and file/line/binary address location information.


* **Uninitialized Stack Variable Detector**:
  Specify ``"detector": "UninitializedVariable"`` within ``"detector_options"`` to use this field.

The Uninitialized Stack Variable Detector searches for variables allocated on
the stack and used prior to initialization.

If specified, the detector will only look inside a given function at a given
variable, otherwise the detector will search the program for every possible
uninitialized stack variable use, and only detect the first uninitialized use
on each path. Thus, it's best to specify this information if a target is in
mind. When a vulnerability is found on a given path a detector will return the
function name, variable name, and file/line/binary address location information.


* **Use After Free Detector**:
  Specify ``"detector": "UseAfterFree"`` within ``"detector_options"`` to use this field.

The Use After Free (UAF) Detector searches for and validates UAF
vulnerabilities from calls to malloc and free.

If specified the detector will only search for UAF at a given free to use site
pairs, otherwise the detector will detect the first UAF reachable in each path.
When a vulnerability is found on a given path the detector will create a
Manticore testcase with information about the allocation's use, free, and
allocation file/line/binary address location information.


**Detector Target (POI) Information** - If no target information (variable to
function or use to free site) is specified, the detector will search for the
first found vulnerability it is intended to detect on each path.

The ``"poi_info"`` field in a ``Mantiserve`` request specifies this
information. It accepts a list of dictionary objects specifying targets (See
:ref:`Examples <manti-examples>` and :ref:`Using a Detector with a POI Result
<detector-with-poi>`). If omitted from the json request or specified as
``"poi_info" : []`` the detector will search with no target.

**Detector Fast Mode** - If specified the detector will stop and create a
testcase and stop after the first vulnerability detection, otherwise Manticore
will continue to search until the symbolic execution engine has finished
(meaning all possible program paths have been explored).

The ``"fast"`` field in a ``Mantiserve`` request specifies this information. It
a boolean value; ``true`` to end on first detection and ``false`` to have
``Mantiserve`` search until completion.

It is recommended to leave ``"fast"`` as ``true`` so that you get immediate
feedback when a detector detects something.

.. _detector-with-poi:

==================================
Using a Detector with a POI Result
==================================

The ``"poi_info"`` field specifies information to be shared with a detector for
validation of POI results.  This can be used with an `Exploration <exploration-doc>` or
`Reachability <reachability-doc>` Mantiserve request.

For ``VariableBoundsAccess`` and ``UninitializedVariable`` ``Detector``\ s this
field will look like a list of function to variable pairs

.. code-block:: json

       "poi_info": [
         {
           "function_name": "syscall_adjtimex",
           "variable_name": "txc"
         },
         {
           "function_name": "overflow_field",
           "variable_name": "auth"
         }
       ]

For ``UseAfterFree`` this field will look like a list of free to use sites

.. code-block:: json

       "poi_info": [
         {
           "use_file": "tmpp96vvx_w.c",
           "use_line": 24,
           "free_file": "tmpp96vvx_w.c",
           "free_line": 20
         },
         {
           "use_file": "tmpp96vvx_w.c",
           "use_line": 25,
           "free_file": "tmpp96vvx_w.c",
           "free_line": 20
         }
       ]

.. _manti-examples:

***************
Example Queries
***************

**Explore Request with no Detector**

.. code-block:: json

   {
        "explore_msg": {
            "path": "/tmp/UninitializedVariable",
            "command_line_flags": [],
            "concrete_start": "",
            "stdin_size": 0,
            "env": {}
        }
   }

**Uninitialized Stack Variable Detector in Exploration Mode without POI
Information**

.. code-block:: json

    {
        "explore_msg": {
            "path": "/tmp/UninitializedVariable",
            "command_line_flags": [],
            "concrete_start": "",
            "stdin_size": 0,
            "env": {},
            "detector_options": {
                "fast": true,
                "detector": "UninitializedVariable",
            }
        }
    }

**Uninitialized Stack Variable Detector in Exploration Mode with POI
Information**

.. code-block:: json

   {
        "explore_msg": {
            "path": "/tmp/UninitializedVariable",
            "command_line_flags": [],
            "concrete_start": "",
            "stdin_size": 0,
            "env": {},
            "detector_options": {
                "fast": true,
                "detector": "UninitializedVariable",
                "poi_info": [
                    {
                        "function_name": "syscall_adjtimex",
                        "variable_name": "txc"
                    }
                ]
            }
        }
   }


**Use After Free Detector in Exploration Mode with POI Information**

.. code-block:: json

   {
        "explore_msg": {
            "path": "/tmp/UAF",
            "command_line_flags": [],
            "concrete_start": "A00000000ABCDEFGH.ppm\nB00000000ABCDEFGH.ppm\n",
            "stdin_size": 0,
            "env": {},
            "detector_options": {
                "fast": true,
                "detector": "UseAfterFree",
                "poi_info": [
                    {
                        "use_file": "tmpp96vvx_w.c",
                        "use_line": 166,
                        "free_file": "tmpp96vvx_w.c",
                        "free_line": 54
                    }
                ]
            }
        }
   }


****************************
Example in Progress Request
****************************

When requesting the :ref:`status of a running task <task-status>` a response similar
to the following will return:

.. code-block:: json

   {
     "task_id": "f3636f90a2de4293b0b6c7bfe35f89c9",
     "build_id": "d01e95ffe06b44e78f391b2cd20e603a",
     "state": "running",
     "kind": "Explore",
     "request_msg": {
       "env": {},
       "path": "/tmp/UAF",
       "stdin_size": 0,
       "concrete_start": "A00000000ABCDEFGH.ppm\nB00000000ABCDEFGH.ppm\n",
       "detector_options": {
         "fast": true,
         "detector": "UseAfterFree",
         "poi_info": []
       },
       "command_line_flags": []
     },
     "artifact_ids": [],
     "response_msg": null,
     "docker_image": null
   }

The key things to note here are that the ``"state"`` field is ``"running"``
and the ``"response_msg"`` field is ``null`` since Manticore is still in progress.

*********************
Example Query Results
*********************

When requesting the `status of a completed task <task-status>` the
``"state"`` field in the response will be set to ``"completed"`` and the
``"response_msg"`` field will have the following fields:

.. code-block:: json

     "response_msg": {
       "path": "/tmp/UAF",
       "cases": []
     }

where ``"path"`` is the to the binary being executed (inferred from the CPG build)
and ``"cases"`` is a list of the results. If the ``"cases"`` list is empty (like above) then
no results were found, otherwise it will contain a list of results with
``"description"``, ``"symbolic_inputs"``, and ``"detector_triggered"`` fields. See 
`ExploreRet` or `ReachabilityRet` for more details.

**Successful Uninitialized Stack Variable with a result Detection**

.. code-block:: json

   {
     "task_id": "682c20e875eb4159890d35406be90b30",
     "build_id": "350f6e0ffd714313b8d6c9a864c75158",
     "state": "completed",
     "kind": "Explore",
     "request_msg": {
       "env": {},
       "path": "/tmp/UninitializedVariable",
       "stdin_size": 0,
       "concrete_start": "",
       "detector_options": {
         "fast": true,
         "detector": "UninitializedVariable",
         "poi_info": [
           {
             "function_name": "syscall_adjtimex",
             "variable_name": "txc"
           }
         ]
       },
       "command_line_flags": []
     },
     "artifact_ids": [
       "d7b7bc165b1c4d379ea11c73562e5ee9"
     ],
     "response_msg": {
       "path": "/tmp/UninitializedVariable",
       "cases": [
         {
           "description": "Found stack variable use before initialization txc.tai@'syscall_adjtimex' @ 0x4014b6! (/tmp/tmppisodovc.c:115)",
           "symbolic_inputs": [],
           "detector_triggered": "UninitializedVariable"
         }
       ]
     },
     "docker_image": null
   }

**Successful Use After Free Run with a result Detection**

.. code-block:: json

    {
      "task_id": "a448ba792f434bb0be38e8d65a0aeb58",
      "build_id": "0b314d269ee34f84a69981478bf4ecbe",
      "state": "completed",
      "kind": "Explore",
      "request_msg": {
        "env": {},
        "path": "/tmp/UAF",
        "stdin_size": 0,
        "concrete_start": "A00000000ABCDEFGH.ppm\nB00000000ABCDEFGH.ppm\n",
        "detector_options": {
          "fast": true,
          "detector": "UseAfterFree",
          "poi_info": []
        },
        "command_line_flags": []
      },
      "artifact_ids": [
        "339463dc77f54b22acec6e6036f56e1c"
      ],
      "response_msg": {
        "path": "/tmp/UAF",
        "cases": [
          {
            "description": "Found use after free when reading address 0x425b00 @ 0x40160d (/tmp/tmpwy5w117e.c:166)!  Allocated @ 0x4011f5 (/tmp/tmpwy5w117e.c:44). Deallocated @ 0x401273 (/tmp/tmpwy5w117e.c:54).",
            "symbolic_inputs": [],
            "detector_triggered": "UseAfterFree"
          }
        ]
      },
      "docker_image": null
    }

**Completed Mantiserve Run with no Detections**

.. code-block:: json

   {
     "task_id": "31d16591696d44d9b0aa0cd98c892d5a",
     "build_id": "d01e95ffe06b44e78f391b2cd20e603a",
     "state": "completed",
     "kind": "Explore",
     "request_msg": {
       "env": {},
       "path": "/tmp/UAF",
       "stdin_size": 0,
       "concrete_start": "A00000000ABCDEFGH.ppm\nB00000000ABCDEFGH.ppm\n",
       "detector_options": {
         "fast": true,
         "detector": "UseAfterFree",
         "poi_info": [
           {
             "use_file": "badfile.c",
             "use_line": 166,
             "free_file": "badfile.c",
             "free_line": 54
           }
         ]
       },
       "command_line_flags": []
     },
     "artifact_ids": [
       "303d53ae09464498816ad7806ca64bca"
     ],
     "response_msg": {
       "path": "/tmp/UAF",
       "cases": []
     },
     "docker_image": null
   }


***********************
Mantiserve Final States
***********************

Mantiserve tasks will have an associated ``state`` field in the returned object
from the `tasks/{task_id}
<api.htmll#operation/_get_manticore_task_api_v1_manticore_tasks__task_id__get>`_
Mantiserve REST endpoint. You will know that a task has stopped running when any
of the following states appear.

* **Failed** - Mantiserve task was killed by a REST request (See :ref:`Killing
  a Task<kill-manti-task>`) or Manticore encountered an unrecoverable error

* **Completed** - Mantiserve either finished execution normally or found a
  detector result with ``fast`` mode and exited early


.. _strategies-for-activation:

************************************
Strategies for Activating Mantiserve
************************************

* **Using Fast Mode with a Detector**

Mantiserve requests can be time consuming on large binaries, particularly if
using a detector with purely symbolic input. Specifying ``fast`` to true will
allow Manticore to notify immediately when a detection is made, instead
searching indefinitely.

* **Kill Mantiserve Tasks**

After a significant amount of time has passed it might be advantageous to kill
a Mantiserve task, view the logs, and give a more specific or different kind of
request.

Mantiserve tasks can utilize a large amount of resources on large programs, so
it is important to be aware the number of tasks currently running.

* **Specify a Target (POI Information) with a Detector**

Providing detectors with a target (``poi_info``) ensures that a detector will
only look for that target or set of targets on a specific path, not returning
early with results that are not of interest. Additionally, in the case of the
Uninitialized Stack Variable Detector and the Variable Bounds Access Detector
specifying a target helps limit the functions and variables that are watched,
reducing overhead.

**********************************
Developer Python API Documentation
**********************************

See :doc:`mantiserve <api/Mantiserve/modules>` for Python package documentation.
