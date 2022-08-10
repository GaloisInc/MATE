###################################
mate-cli Command Line Tool Overview
###################################

See also the :doc:`quickstart`.

The Python APIs that ``mate-cli`` uses under the hood can be found under the
`MATE REST Client API documentation <api/MATERestClient/mate_rest_client.html#http://>`_.

.. NOTE::
    For the detailed reference manual for ``mate-cli`` see :doc:`cli`.

***********************
Installing ``mate-cli``
***********************

.. TIP::

    The steps below can be skipped entirely by using the version
    hosted on PyPI instead:

    .. code-block:: console

        $ python -m pip install mate-cli
        $ mate-cli --help

.. NOTE::

    If you are running an interactive shell inside the ``mate-dist`` Docker
    environment, then ``mate-cli`` should already be available on your
    ``$PATH``. You do not need to follow the steps below.

``mate-cli`` is designed to be usable outside of the normal MATE runtime
environment.

This means that you can use it on your local development machine,
**without Docker**, as long as you have a few basic runtime requirements:
Python 3 (3.8+) and ``pip``.

Start from the MATE repository root:

.. code-block:: bash

    $ # create a new virtual environment, and enter it
    $ python3 -m venv env
    $ source env/bin/activate
    (env) $ # install mate-cli and its dependencies into the virtual environment
    (env) $ pip install -r cli-requirements.txt
    (env) $ # confirm that mate-cli is installed and functional
    (env) $ mate-cli --help


Once ``mate-cli`` is installed, you'll be able to interact with any MATE server.

By default, ``mate-cli`` will connect to ``localhost:8666``. You can change this
by specifying ``--conn your-server:port`` instead:

.. code-block:: bash

    (env) $ mate-cli --conn some-mate-host:8666 <your-args...>

********************
Running ``mate-cli``
********************

``mate-cli`` provides a number of subcommands, such as: ``mate-cli artifact``, ``mate-cli compile``,
``mate-cli build``, etc.

These subcommands are usually followed by another subcommand such ``get``, ``create`` or ``task``.
For example, to find all compilations that have completed successfully in MATE, the invocation would
look like:

.. code-block:: bash

    mate-cli compile get --state compiled

When executing a command, the ``mate-cli`` tool will print out the response from the MATE server as
a JSON structure. So a typical response will look like:

.. code-block:: json

    [
      {
        "compilation_id": "5e092549f5a04a00b97bd9af738787a0",
        "build_ids": [],
        "state": "compiled",
        "source_artifact": {
          "artifact_id": "4a76ae25dcc24bd2822e0431e82bf123",
          "kind": "compile-target:single",
          "has_object": true,
          "attributes": {
            "filename": "overflowable-allocations.c"
          },
          "build_ids": [],
          "compilation_ids": [
            "5e092549f5a04a00b97bd9af738787a0"
          ]
        },
        "log_artifact": {
          "artifact_id": "f697ef320def4e8b96190b78d2084d54",
          "kind": "compile-output:compile-log",
          "has_object": true,
          "attributes": {
            "filename": "compile.log"
          },
          "build_ids": [],
          "compilation_ids": [
            "5e092549f5a04a00b97bd9af738787a0"
          ]
        },
        "artifact_ids": [
          "4a76ae25dcc24bd2822e0431e82bf123",
          "f697ef320def4e8b96190b78d2084d54",
          "2a47bea363ca4df69b9dc4cded0b4056",
          "4c652b2ca5b7455a9aad61fd4123cd6f",
          "90968eb954f546d19ad3bd344aada644"
        ],
        "options": {
          "testbed": null,
          "containerized": false,
          "experimental_embed_bitcode": false,
          "docker_image": null,
          "containerized_infer_build": true,
          "make_targets": null,
          "extra_compiler_flags": []
        }
      }
    ]

One important point to note is that ``mate-cli`` supports an optional top-level ``--conn`` argument
to specify the MATE service to use. For MATE developers who are running MATE locally with the
instructions `here <getting-started.html#running-mate>`_, the default of ``http://localhost:8666``
will work fine however, users who wish to query an external MATE service will have to provide the
connection details like so:

.. code-block:: bash

    mate-cli --conn http://YOUR_CHESS_SYSTEM:8666 <subcommand>

To see the full set of subcommands and arguments, run ``mate-cli --help`` or refer to the reference
manual at :doc:`cli`.

.. _mate_cli_basic:

**********************************
A basic workflow with ``mate-cli``
**********************************

.. NOTE::

    For many use cases, :ref:`mate-cli oneshot <mate_cli_oneshot>` will be
    faster and simpler than the steps listed below.

If we're analyzing our own program with MATE, most workflows will begin by uploading an artifact. We
can do this with the ``mate-cli artifact create`` command like so:

.. code-block:: bash

    mate-cli artifact create compile-target:single ./frontend/test/programs/overflowable-allocations.c

The response from the MATE server will tell us the ID of the artifact that we just created. In this
case, it is ``276d1771d6ee4532b89359eea2668482``.

Now, we can send the artifact to MATE for compilation by providing the artifact ID we got from the
previous step:

.. code-block:: bash

    mate-cli compile create --wait --artifact-id 276d1771d6ee4532b89359eea2668482

.. NOTE::
   If we wanted to compile a challenge program instead of our own artifact, we could just as easily
   use the ``--challenge-name`` or ``--challenge-id`` arguments.

.. NOTE::

    The ``--wait`` flag causes ``mate-cli compile create`` to block with a spinner
    until the compilation enters a terminal state (e.g., ``compiled`` or ``failed``).

    Without the ``--wait`` flag, users should run ``mate-cli compile get <compilation-id>``
    to determine to compilation's status before proceeding.


When our compile job reaches the ``compiled`` state, we can then use the ``build`` subcommand and
generate the CPG so that MATE analyses can be run on the program:

.. code-block:: bash

    mate-cli build create 5e092549f5a04a00b97bd9af738787a0

Following the same convention as the compilation subcommands, we can check on the progress of the
MATE build by running ``mate-cli build get``. Once the build is done, we can run the full set of
MATE analyses on the program like so:

.. code-block:: bash

    mate-cli analysis run da4b7da519574ac3a1bef6bc39148372

This will create a task for each analysis in the system (queryable with
``mate-cli analysis task da4b7da519574ac3a1bef6bc39148372``).

Once the analysis tasks have finished running, the generated POIs can be viewed by navigating to the
MATE dashboard in a web browser. The MATE dashboard is the most convenient way to view this
information, however ``mate-cli`` has some rudimentary functionality for exploring POIs.

We can retrieve the list of generated POIs like so:

.. code-block:: bash

    mate-cli poi get

The POI information usually contains UUIDs of nodes within the CPG which can then be used with the
``mate-cli graph`` subcommands to "view" parts of the CPG.

.. _mate_cli_oneshot:

***********************
The ``oneshot`` command
***********************

Creating compilations and builds for a given source with ``mate-cli`` is a fairly common occurrence.
``mate-cli`` supports a subcommand called ``oneshot`` which is shorthand for this part of the
workflow.

The ``oneshot`` subcommand takes a single parameter describing either an artifact or a broker
challenge, compiles it and creates build tasks for each target. The parameter can be a few different
things and ``oneshot`` will try to "guess" what it is. Some examples are provided below:

From a source file:

.. code-block:: bash

    mate-cli oneshot ./program.c

From a tarball:

.. code-block:: bash

    mate-cli oneshot ./program.tar.gz

From a directory:

.. code-block:: bash

    mate-cli oneshot ./program

From an artifact ID:

.. code-block:: bash

    mate-cli oneshot 2358423ccc7d4d0dba8477f9baf19420

From a brokered challenge name (must be published on the CHESS challenge broker):

.. code-block:: bash

    mate-cli oneshot challenge-1

The ``oneshot`` subcommand also supports the ``-p``/``--run-all-pois`` flag,
which tells MATE to run all registered POI analyses once the CPG build completes:

.. code-block:: bash

    # the same as above, but also run POI analyses automatically
    mate-cli oneshot -p ./program.c

****************************
Helpful ``mate-cli`` recipes
****************************

The ``mate-cli`` is designed to compose well with itself and common utility
commands, like ``xargs`` and ``jq``. Here are some useful recipes.

Stop all currently running Manticore tasks
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

    $ mate-cli manticore get --state running \
        | jq -r '.[] | .task_id' \
        | xargs mate-cli manticore stop

Get the LLVM bitcode for a CPG
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Substitute ``BUILD-ID`` for the build you'd like.

.. code-block:: bash

    $ mate-cli build get-bc BUILD-ID

Get the "canonical" binary for a CPG
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Substitute ``BUILD-ID`` for the build you'd like.

.. code-block:: bash

    $ mate-cli build get BUILD-ID \
        | jq -r '.artifact_ids | .[]' \
        | xargs mate-cli artifact get --kind build-output:quotidian-canonical-binary \
        | jq -r '.[] | .artifact_ids'
        | xargs mate-cli artifact dump > binary.elf
