Environment variables in the MATE container
###########################################

This document lists and describes the environment variables defined and used by the various MATE
Docker containers.

Variables that are **not** listed in this document **may** be defined for internal build and
configuration purposes. These unlisted variables should **not** be relied upon.

``MATE_BDIST_ROOT``
~~~~~~~~~~~~~~~~~~~

Provenance: ``mate-dev`` or ``mate-dist``

Container default: ``/mate/.out/bdist`` (dev) *or* ``/opt/mate`` (dist)

``MATE_BDIST_ROOT`` provides an absolute reference to the MATE "distribution";
i.e. a hermetic collection of all libraries, executables, and resources needed
to run MATE.

``MATE_DEFAULT_MEMORY_LIMIT_GB``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provenance: ``mate-dev`` or ``mate-dist``

Container default: ``32``

This variable sets the default memory limit for individual builds, in gibibytes.
The memory limit can still be overridden on a per-build basis.


``LLVM_WEDLOCK_INSTALL_DIR``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provenance: ``mate-dev`` or ``mate-dist``

Container default: ``${MATE_BDIST_ROOT}/llvm-wedlock``

This is an organization variable that will be useful for setting ``LLVM_BIN`` and ``LLVM_DIR``
in the case that they ever change or need to be reset to use wedlock-specific tools/libraries.

This is the install path for all tools built in the ``llvm-wedlock`` repository.

**Note**: This directory does not necessarily include wedlock-related ``opt`` passes -- they are
located in ``LLVM_PASS_DIR``.

``LLVM_WEDLOCK_BIN``
~~~~~~~~~~~~~~~~~~~~

Provenance: ``mate-dev`` or ``mate-dist``

Container default: None.

By default, MATE will discover a functional Wedlock build of the LLVM toolchain under
``${MATE_BDIST_ROOT}/llvm-wedlock/bin``. This variable can be used to *override* that
default, specifying a separate Wedlock build of LLVM for testing or debugging purposes.

``LLVM_DIR``
~~~~~~~~~~~~

Provenance: ``mate-dev`` or ``mate-dist``

Container default: ``${LLVM_WEDLOCK_INSTALL_DIR}/lib/cmake/llvm``

The ``LLVM_DIR`` variable's value will be a directory, under which CMake configuration for building
LLVM passes will be present.


``Clang_DIR``
~~~~~~~~~~~~~

Provenance: ``mate-dev`` or ``mate-dist``

Container default: ``${LLVM_WEDLOCK_INSTALL_DIR}/lib/cmake/clang``

The ``Clang_DIR`` variable's value will be a directory, under which CMake configuration for building
Clang analyses will be present.


``PATH``
~~~~~~~~

Provenance: ``mate-dev`` or ``mate-dist``

The ``PATH`` variable's value will contain multiple additional paths. Container consumers should not
rely on the presence of any particular path or upon path orderings other than specified below.

``gclang`` and ``gclang++`` should *not* be present on the ``PATH``; they will be supplied
under ``${MATE_BIST_ROOT}/libexec``. Similarly, the llvm-wedlock toolchain's programs
should *not* be present by default: any components that wish to use them should load
the Wedlock LLVM ``bin`` path onto the ``PATH`` temporarily (or access them directly).

Furthermore, any specific versions of tools used/required by the tools manually installed in this
Docker image will almost certainly take precedence over system-installed tools.
