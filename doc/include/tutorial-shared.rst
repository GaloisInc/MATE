..
  This part is shared between the Flowfinder and notebook tutorials.

*****
Setup
*****

First, get a MATE system running and install the CLI (see :doc:`quickstart`).
Then,

- Download
  `notes.c
  <https://github.com/GaloisInc/MATE/blob/main/frontend/test/programs/notes.c>`__,
  or copy it from the MATE source root: ``cp
  $MATE_SOURCE/frontend/test/programs/notes.c .``
- Upload ``notes.c`` to MATE: ``mate-cli oneshot -p notes.c``
- Navigate to the builds page (at `<http://localhost:3000/builds>`_) to check
  the status of the build; it should complete in less than a minute

**********
Background
**********

The target program is a simple server that allows users to create notes
(i.e., store binary blobs). When a note is written, the user is given a
completely random key. They can retrieve the note using this key.

The server supports three commands, ``write``, ``read``, and ``quit``.

Example use:

::

   $ clang -Wall -Werror -o notes -O1 -g notes.c
   $ ./notes
   Listening on port 8894

In a separate terminal:

::

   $ nc localhost 8894
   notes> write very secret data
   <server will send back a long alphanumeric key here>
   notes> read <key that the server sent back>
   very secret data

Notably, we'll use MATE to find a bug that *can't be found by a fuzzer*. The
``notes.c`` program contains tests and a fuzzing harness, all of which can
be run with `Valgrind <https://valgrind.org/docs/manual/mc-manual.html>`_,
`ASan <https://clang.llvm.org/docs/AddressSanitizer.html>`_, and
`UBSan <https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html>`_
without detecting any errors.
