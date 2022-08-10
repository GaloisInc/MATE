#########################
Starting Stand-alone MATE
#########################

************
Running MATE
************

The MATE system consists of a number of long-running services, each within a separate Docker
container and orchestrated together using ``docker-compose``. To start the MATE composition, you
will need to have ``docker-compose`` installed locally as well as a copy of the ``docker-compose``
YAML files, which can currently be found in the root of the MATE source repository.

Starting the service composition can be done using the following command::

  docker-compose -f /path/to/MATE/docker-compose.yml up

**********************************
Interacting with the MATE REST API
**********************************

Once MATE is up, a REST API server will start listening for requests at ``localhost:8666/api/v1``.
Visiting that URI in a web browser will open a helpful (albeit still developer-oriented) UI.

Issuing requests to the REST API is the primary way in which clients are expected to interact with
the MATE system; some workflows may require multiple request/response cycles to complete.

Ingesting a Build
*****************

The top-level unit of analysis in MATE is a *CPG build*, or *build* for short.
A build is typically associated with a particular binary produced by a compilation process.
A compilation process can produce multiple binaries, and so a single compilation can
produce multiple CPG builds.

All CPG nodes and edges produced during the CPG build process are associated with
a particular build through each build's unique build ID.

The mechanisms for running compilation processes and creating CPG builds within
MATE are described below.

Compiling a program
~~~~~~~~~~~~~~~~~~~

MATE currently supports three types of compilation targets:

#. Standalone C or C++ files (``foo.c`` or ``foo.cpp``);
#. Program tarballs that contain a ``make``-based build (``foo.tar.gz``);
#. "Brokerized" CHESS challenges, served by the CHESS system's challenge broker

Usage of MATE outside of the integrated CHESS system primarily involves the
first two types of targets. Brokerized compilation targets are only relevant
in the presence of an active CHESS system challenge broker.

You can construct a suitable tarball for a Make-based build with the ``tar`` command::

  tar czf challenge.tar.gz challenge/

To construct a CPG from source code, MATE first needs the source code in question. We provide
it as an *artifact*::

  # a single source file (`compile-target:cxx` also works)
  artifact_uuid=$(http POST localhost:8666/api/v1/artifacts kind="compile-target:c" attributes:="{}" | jq -r '.artifact_id')
  http -f POST localhost:8666/api/v1/artifacts/${artifact_uuid}/object file@standalone.c

  # a tarball containing a Make-based build
  artifact_uuid=$(http POST localhost:8666/api/v1/artifacts kind="compile-target:tarball" attributes:="{}" | jq -r '.artifact_id')
  challenge_tarball=challenge.tar.gz
  http -f POST localhost:8666/api/v1/artifacts/${artifact_uuid}/object file@${challenge_tarball}

Next, we need to tell MATE to *compile* our new artifact. We do this by creating a
*compilation* associated with the artifact::

  compilation_uuid=$(http POST localhost:8666/api/v1/compilations kind="artifact" handle="${artifact_uuid}" options:='{}' | jq -r '.compilation_id')

Internally, this request causes MATE to asynchronously attempt a compilation of the artifact

You can check the status of that compilation with another request::

  http localhost:8666/api/v1/compilations/${compilation_uuid}

Once the compilation is in a completed state (i.e., ``compiled``), we can pass it into
MATE's build pipeline::

  http POST localhost:8666/api/v1/builds/${compilation_uuid}/build body={}

The build pipeline can be passed specific options instead of an empty body::

  # disable pointer analyses (points-to and dataflow)
  http POST localhost:8666/api/v1/builds/${compilation_uuid}/build pointer_analysis=false

  # disable machine-code mapping (all non-LLVM IR nodes and edges)
  http POST localhost:8666/api/v1/builds/${compilation_uuid}/build machine_code_mapping=false

Compilations can produce multiple binaries (think e.g. a Make-based build that
produces separate ``client`` and ``server`` targets), so the endpoint above
returns a list of newly created build IDs. We can also see that list by requesting
it separately::

  http localhost:8666/api/v1/builds

And requesting information for a particular build::

  http localhost:8666/api/v1/builds/YOUR-BUILD-ID-HERE

Like with compilations, builds are executed asynchronously within MATE. You can
use the endpoint above to poll for a build's status. Once a build has entered
the ``built`` state, it can be used to run CPG queries.

*****************
Running the Shell
*****************

MATE provides the capability to open an IPython shell which automatically connects to a running
database instance. This shell can be run as follows::

  docker-compose -f docker-compose.yml -f docker-compose.clients.yml run shell

Once inside the shell, the database object ``db`` is available and preconfigured, can be used to
make queries using the MATE query language. For example::

  >>> session = db.new_session()
  >>> session.query(db.Build).count()
  1
  >>> build = session.query(db.Build).one()
  >>> print(build.uuid)
  "e4e8e8e5e9c848fd959463d568e30194"
  >>> graph = session.graph_from_build(build)
  >>> session.query(graph.Node).count()
  909
  >>> session.query(graph.Edge).count()
  2045

***********************************
Running Manticore Symbolic Executor
***********************************

The Manticore symbolic executor can be run through a service known as *Mantiserve*, a separate service with its own endpoints. This service is setup within the main ``docker-compose.yml`` file started above and is on a different port (default ``8001``).

Once you have your build id(s), you can send them to Mantiserve to execute symbolic execution tasks that consist of reachability queries and various vulnerability detectors.

See :doc:`mantiserve` for more information on usage and features.

***************************************************
Troubleshooting the compilation and build pipelines
***************************************************

MATE's compilation and build pipelines attempt to compile arbitrary programs.
Doing so reliably for arbitrary programs is difficult, and may require
manual intervention in some cases. Some potential resolutions for common
cases are listed below.

Unusual ``make`` targets
************************

By default, MATE's compilation pipeline attempts to identify a ``make``-compatible
``Makefile`` and run its default target. For most build setups, this will perform
a normal, fresh build.

However, the default target is not always guaranteed to be correct: a build may
use the default target for a different purpose, or require the user to type
an explicit target (like ``make server`` or ``make compile-all``), or even require
multiple consecutive, independent targets (like ``make clean; make deps; make all``).

To handle these, MATE's compilation pipeline allows the default ``make`` behavior
to be overridden. To pass in a different target or set of targets, use the
``make_targets`` compilation option::

  # run `make clean; make depend; make all` for the compilation
  http POST localhost:8666/api/v1/compilations \
    kind="artifact" \
    handle="SOME-ID" \
    options:='{"make_targets": ["clean", "depend", "all"]}'

Note that ``make_targets`` can include more than one target, and that targets
are run sequentially in the order listed.
