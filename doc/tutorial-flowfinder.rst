###################
Flowfinder Tutorial
###################

This tutorial will guide you through finding a bug with
:doc:`Flowfinder <using-flowfinder>`.

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

********
Tutorial
********

First, open the program in Flowfinder by clicking the "analyze in Flowfinder"
link. You should see a mostly empty screen with a sidebar on the right.

Exploring a Function
====================

Let’s start by looking at where user input enters the program from the network,
via ``recv``. Use the "Select a Function Node to Start…" box to add the ``recv``
function to the screen. Then, find add all the callsites of ``recv`` to see how
user input can enter the program.

-  Type ``recv`` into the "Select a Function Node to Start…" box
-  Click the "Add Node" button. You should see a box labeled ``recv``.
-  Right-click the ``recv`` box and select "Show callsites".

Feel free to re-arrange nodes and edges at any point by dragging and dropping
them. Some nodes can be collapsed or expanded by double-clicking them.

At this point, you should see an arrow from a large box labeled ``handle_loop``
to a small box labeled ``recv``, indicating that the instruction ``%t8 = call
i64 @recv ...`` in ``handle_loop`` calls ``recv``.

Exploring the CFG
=================

Now we know that network input enters the program at this call to ``recv`` in
``handle_loop``. What happens after that? Try taking a look at the slice of the
*control-flow graph* that follows this call: right-click the call instruction
and select "Show control flow from this node".

At this point, you should see a fairly large graph. What’s going on here? If you
follow enough arrows, you should be able to convince yourself that the ``recv``
is inside of a loop, and so the control-flow graph following the call is exactly
the CFG of thee ``handle_loop`` function, which consists entirely of this loop.

Hide or remove the control-flow slice by pressing the "x" or the slider in the
upper left or upper right hand corner of the corresponding card (the card should
have "Kind: Control flow" on it).

Exploring the DFG
=================

The CFG was a little overwhelming, with a suboptimal signal-to-noise ratio.
Let’s just look at the places where the data from the ``recv`` call gets used.
Right-click on the call to ``recv`` and click "Show uses". You should see a
single ``store`` instruction show up. This isn’t too helpful - we’ve just taken
a single step through the *dataflow graph*. Let’s try taking a few at once.

Try adding the slice of the dataflow graph that starts at this call to ``recv``:
right-click the call instruction and select "Show data flow from this node".

This graph seems a little sparse. First of all, the targets are all in
``handle_loop``, but surely user-provided data flows to other functions. If you
examine the source lines carefully, you can see that this slice actually shows
the data flow from *the return value* of ``recv``. If we want to look for how
user-provided data flows through the program, we’ll have to try something else.

Hide or remove all the "Dataflow" and "Uses" cards.

Signatures
==========

The problem is that we really want to track the flow of data originating
*outside* of the program. The mechanism MATE uses for this purpose is called an
:doc:`"input signature" <signatures>`. There are also corresponding "output
signatures" which represent the effect of the program on the external world
(printing messages, creating files, etc.).

Try right-clicking the call to ``recv`` and select "Show dataflow and I/O
signatures". Right-click the leftmost input signature that appears (the node is
pentagonal and pink), and click "Show data flow from this node". You should now
see a much more interesting data flow graph. Can you see the vulnerability?
Hint: it’s a path traversal.

The problem is that the user input from this call to ``recv`` flows to the path
argument of a call to ``fopen``: the key that the user gives to the ``read``
command is used as a path, with no sanitization. This means the user can input a
key like ``../../../super/secret/file`` and read the contents of that path.

Right-click the output signature for ``fopen`` (which represents the file that
may be created by ``fopen``), and click "show callsites". You should be able to
see that the vulnerable call occurs in the ``cmd_read`` function.
Congratulations, you found the vulnerability!

If you’d like to understand how the data flows from the ``recv`` to the
``fopen`` in more detail, try disabling the "Hide Nodes - memory" slider in the
sidebar. A circular, green node labeled ``nil*stack_alloc@handle_loop[[1024 x
i8]* %t1][0][*]`` should appear between the input signature for ``recv`` and the
output signature for ``fopen``, which indicates that the data flows through a
stack allocation of size 1024 that was allocated in ``handle_loop``. You can
right-click the memory node and click "Show allocation site" to show the LLVM
``alloca`` instruction which allocates this buffer (corresponding to a local
variable at the C level). If you "Show operands" on the ``call`` to ``recv`` and
then "Show operands" on the ``getelementptr`` instruction, you can see that this
is the buffer passed as the second argument of ``recv``. (You could also try
establishing this by walking the other direction in the dataflow graph, by
clicking "Show uses" on the ``alloca`` and so on.) Nice!
