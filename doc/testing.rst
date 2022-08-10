################################
Writing and running MATE's tests
################################

.. important::
   This page is intended for the developers of MATE only -- it is not relevant for users.

.. note::
    This page assumes that you have a functional MATE development environment.
    See :doc:`hacking` for build instructions.

******************
MATE's test suites
******************

The MATE codebase contains multiple suites of unit and integration tests, all of
which are controlled by ``pytest``:

* Unit tests for the CPG live under ``tests/postgres``
* Dwarfcore-specific tests live under ``tests/dwarfcore``
* Mantiserve-specific tests live under ``tests/mantiserve``
* Integration tests live under ``tests/integration``
* Pointer analysis tests live under ``llvm/PointerAnalysis/test``
* "Legacy" tests (mostly for datastructures) live under ``frontend/test``

*****************
Running the tests
*****************

All of MATE's tests are run in the CI, either with each commit or on a schedule
(for more intensive integration tests). However, they can all be run locally
with a normal MATE development environment as well.

CPG, Dwarfcore, and Mantiserve tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Running any of these test suites requires a similar setup.

You'll need two terminal windows available.

In your first window, use ``docker-compose`` to bring up the ``db``
``storage``, and ``mate-runtime-state`` services:

.. code-block:: bash

    docker-compose up -V db storage mate-runtime-state

.. important::
    The ``mate-runtime-state`` container is vital to the correct execution
    of tests that use containers for isolation. It exits successfully once its
    job is finished, so do not be concerned if it does not stay running.

These services are **stable**: you do **not** have to bring them up with each
test suite invocation.

In your second window, use ``docker-compose`` to run the test suite you're
interested in:

* CPG tests: ``test``
* Dwarfcore tests: ``dwarfcore-test``
* Mantiserve tests: ``mantiserve-test``

.. code-block:: bash

    # CPG tests
    docker-compose \
      -f docker-compose.yml \
      -f docker-compose.test.yml \
      run -v "$(pwd):/mate" test

    # Dwarfcore tests
    docker-compose \
      -f docker-compose.yml \
      -f docker-compose.test.yml \
      run -v "$(pwd):/mate" dwarfcore-test

    # Mantiserve tests
    docker-compose \
      -f docker-compose.yml \
      -f docker-compose.test.yml \
      run -v "$(pwd):/mate" mantiserve-test

These ``docker-compose`` targets run ``pytest`` under the hood, so you can
pass additional flags to control ``pytest``'s behavior. For example, to
run the CPG tests in "fail-fast" mode:

.. code-block:: bash

    docker-compose \
      -f docker-compose.yml \
      -f docker-compose.test.yml \
      run -v "$(pwd):/mate" test -- -- -x

or to run just a single test (``test_allocation_sizes``):

.. code-block:: bash

    docker-compose \
      -f docker-compose.yml \
      -f docker-compose.test.yml \
      run -v "$(pwd):/mate" test -- -- -k test_allocation_sizes

Once you're done testing, you can bring the entire test environment down
with ``docker-compose``:

.. code-block:: bash

    docker-compose \
      -f docker-compose.yml \
      -f docker-compose.test.yml \
      down -v --remove-orphans

Integration tests
~~~~~~~~~~~~~~~~~

.. note::
    These tests are extremely resource intensive, and should almost never be
    run locally.

The integration tests are nearly identical to the CPG, etc. tests above. Like
above, you'll need two terminal windows.

In your first window:

.. code-block:: bash

    docker-compose up -V db storage mate-runtime-state

Separately, you can choose to enable intensive invariant tests in the normal
test suite by setting ``MATE_INTEGRATION_TESTS=1``:

.. code-block:: bash

    docker-compose \
      -f docker-compose.yml \
      -f docker-compose.test.yml \
      run -v "$(pwd):/mate" -e MATE_INTEGRATION_TESTS=1 test


"Legacy" and pointer analysis tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The "legacy" and pointer analysis tests do not require access to CPGs, and
therefore can be run outside of a ``docker-compose`` environment.

To run the "legacy" and pointer analysis tests:

.. code-block:: bash

  docker run --rm -v $(pwd):/mate -it mate-dev:latest ./shake.sh -j pytests -- -- -x
