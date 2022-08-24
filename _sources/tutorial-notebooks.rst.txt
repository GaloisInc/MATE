#################
Notebook Tutorial
#################

This tutorial will guide you through finding a bug with
:doc:`MATE Notebooks <using-notebooks>`.

.. include:: include/tutorial-shared.rst

********
Tutorial
********

First, open the program in a notebook by clicking the "Open Jupyter Notebook"
button. Highlight the first cell and click "Run" or press Shift+Enter to run
the first cell. You should see the number of nodes in the CPG printed out.

This tutorial will present the Python code to enter into your notebook, followed
by an example output. Some parts may not exactly match your notebook, such as
the build ID and number of nodes here, or specific node IDs in the rest of the
tutorial.

.. code-block:: python

  session = db.new_session()
  cpg = session.graph_from_build(session.query(db.Build).get("47dda0abe95c426f97dcae314e1d55a7"))
  session.query(cpg.Node).count()

::

  3088

Exploring a Function
====================

Let’s start by looking at where user input enters the program from the network,
via ``recv``. Grab the ``Function`` node representing ``recv`` from the CPG:

.. code-block:: python

  recv = session.query(cpg.Function).filter_by(name="recv").one()

::

  <Function(<function>:llvm-link:@recv)>

What can we do with this node? Take a look at ``help(recv)``:

::

  Help on Function in module mate_query.cpg.models.core.cpg object:

  class Function(mate_query.cpg.models.node.ast.llvm.Function, ...)
  |  Function(**kwargs)
  |  
  |  LLVM IR functions
  |  
  |  Method resolution order:
  |      Function
  |      ...
  |  
  |  Methods defined here:
  |      ...
  |  
  |  ----------------------------------------------------------------------
  |  Data descriptors defined here:
  |  
  |  ...
  |  
  |  callsites
  |      This edge relates a function to the 'call' or 'invoke' instructions that call it based on the pointer analysis.

(We could find a nicer looking version of this same information by searching for
``Function`` in the :ref:`API docs <api/index:MATE API Documentation>`.)

``recv`` is an instance of ``Function``, which has a bunch of attributes. Let's
look at the *callsites* attribute of ``recv`` to see where it's called (i.e.,
where user input can enter the program):

.. code-block:: python

  recv.callsites

::

  [<Call(727)>]

This is a list with a single ``Call`` instruction in it. Let's take a closer
look:

.. code-block:: python

  call = recv.callsites[0]
  help(call)

::

  ...

You can see what this instruction looks like at the LLVM level with
``.pretty_string``:

.. code-block:: python

  call.pretty_string

::

  '  %t8 = call i64 @recv(i32 %t6, i8* %t7, i64 1023, i32 0), !dbg !117'

But where is this call happening? Look at the function the call is in:

.. code-block:: python

  caller = call.parent_block.parent_function
  caller

::

  <Function(<function>:llvm-link:@handle_loop)>


Exploring the CFG
=================

Now we know that network input enters the program at this call to ``recv`` in
``handle_loop``. What happens after that? Look at the *successors* (i.e.,
instructions immediately following) this call:

.. code-block:: python

  caller.successors

::

  [<Store(730)>]

This isn’t too helpful - we’ve just taken a single step through the *control
flow graph* (CFG). Let’s try taking a few at once. This recursive query will
build the slice of the CFG that follows this call (essentially, the transitive
closure of ``.successors`` and function calls):

.. code-block:: python

  path = (
      db.PathBuilder(cfl.ForwardCFGPath)
      .starting_at(lambda Node: Node.uuid == call.uuid)
      .limited_to(200)
      .build(cpg)
  )
  session.query(cpg.Node).join(path, path.target == cpg.Node.uuid).all()

::

  [<Call(727)>,
   <Store(730)>,
   <Load(731)>,
   <Instruction(732)>,
   ...

*Woah*, that's a lot of nodes! A few hundred, at least:

.. code-block:: python

  session.query(cpg.Node).join(path, path.target == cpg.Node.uuid).count()

::

  678

That's not very helpful.

Exploring the DFG
=================

The CFG was overwhelming. Let’s just look at the places where the data from the
``recv`` call gets used.

.. code-block:: python

  call.used_by

::

  [<Store(730)>]

Again, we've just taken a single step through the graph and it sure didn't get
us very far. Let’s try taking a few at once, and this time let's print something
a bit more useful.

.. code-block:: python

  path = (
      db.PathBuilder(cfl.CSThinDataflowPath)
      .starting_at(lambda Node: Node.uuid == call.uuid)
      .limited_to(200)
      .build(cpg)
  )
  for n in session.query(cpg.Instruction).join(path, path.target == cpg.Instruction.uuid).all():
      print(n.opcode, ":", n.parent_block.parent_function.name)

::

  Opcode.CALL : handle_loop
  Opcode.STORE : handle_loop
  Opcode.LOAD : handle_loop
  Opcode.LOAD : handle_loop
  Opcode.LOAD : handle_loop
  Opcode.LOAD : handle_loop
  Opcode.LOAD : handle_loop
  Opcode.LOAD : handle_loop
  Opcode.SUB : handle_loop
  Opcode.SUB : handle_loop
  Opcode.GETELEMENTPTR : handle_loop
  Opcode.ICMP : handle_loop
  Opcode.ICMP : handle_loop
  Opcode.ICMP : handle_loop
  Opcode.GETELEMENTPTR : handle_loop
  Opcode.GETELEMENTPTR : handle_loop
  Opcode.BR : handle_loop
  Opcode.BR : handle_loop
  Opcode.BR : handle_loop

Ah, that's not so bad! In fact... it seems a little sparse. First of all, the
targets are all in ``handle_loop``, but surely user-provided data flows to other
functions. Actually, we're looking at the data flow from *the return value* of
``recv``. If we want to look for how user-provided data flows through the
program, we’ll have to try something else.

Signatures
==========

The problem is that we really want to track the flow of data originating
*outside* of the program. The mechanism MATE uses for this purpose is called an
:doc:`"input signature" <signatures>`. There are also corresponding "output
signatures" which represent the effect of the program on the external world
(printing messages, creating files, etc.).

Look at the (callees of the) calls to which user input flows:

.. code-block:: python

  ins = [s.uuid for s in recv.signatures.all() if isinstance(s, cpg.InputSignature)]
  path = (
      db.PathBuilder(cfl.CSDataflowPath)
      .starting_at(lambda Node: Node.uuid.in_(ins))
      .limited_to(200)
      .build(cpg)
  )
  for n in session.query(cpg.Call).join(path, path.target == cpg.Call.uuid).all():
      print(n.callees)

::

  [<Function(<function>:llvm-link:@recv)>]
  [<Function(<function>:llvm-link:@strchr)>]
  [<Function(<function>:llvm-link:@strcmp)>]
  [<Function(<function>:llvm-link:@strcmp)>]
  [<Function(<function>:llvm-link:@strcmp)>]
  [<Function(<function>:llvm-link:@strlen)>]
  [<Function(<function>:llvm-link:@fopen)>]
  [<Function(<function>:llvm-link:@fprintf)>]
  [<Function(<function>:llvm-link:@fclose)>]
  [<Function(<function>:llvm-link:@fgets)>]
  [<Function(<function>:llvm-link:@strlen)>]
  [<Function(<function>:llvm-link:@send)>]
  [<Function(<function>:llvm-link:@new_cmd)>]
  [<Function(<function>:llvm-link:@free)>]
  [<Function(<function>:llvm-link:@parse)>]
  [<Function(<function>:llvm-link:@cmd_write)>]
  [<Function(<function>:llvm-link:@cmd_read)>]
  [<Function(<function>:llvm-link:@free)>]
  [<Function(<function>:llvm-link:@handle)>]
  [<Function(<function>:llvm-link:@free)>]

Can you see the vulnerability? There's a lot there, but consider: For which of
these functions would it be a *problem* if its arguments were influenced by user
input? A further hint: it's a path traversal vulnerability.

The problem is that the user input from this call to ``recv`` flows to the path
argument of a call to ``fopen``: the key that the user gives to the ``read``
command is used as a path, with no sanitization. This means the user can input a
key like ``../../../super/secret/file`` and read the contents of that path.

Nice, you found the vulnerability! The :doc:`tutorial-flowfinder` walks through
finding the same bug with :doc:`Flowfinder <using-flowfinder>`. Try comparing
the two approaches!
