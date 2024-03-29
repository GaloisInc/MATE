#####################
MATE Python Notebooks
#####################

..
   The first paragraph is duplicated in overview.rst, and the first sentence is
   in quickstart.rst. Updates to one should be reflected in the others.

MATE has :ref:`a Python API <query_desc>` for querying :doc:`the CPG <cpg>` and
exposes browser-based, interactive Jupyter notebooks with this query interface
pre-loaded. These notebooks can be used to write complex, recursive,
whole-program queries that answer detailed questions like "What sequences of
function calls can lead from point A to point B in this program?" or "Can user
input flow into a memory location with a specific struct type, and from there to
some particular function without passing through one of these three sanitization
routines?" These notebooks can be used for one-off explorations, or as a
platform for users to build reusable apps on the MATE platform (such as
:doc:`usagefinder`).

The MATE notebook server is exposed via web interface at `<http://localhost:8889/>`_.

See :doc:`tutorial-notebooks` for a hands-on guide to finding a bug with MATE
notebooks.

*****************
Create a notebook
*****************

Navigate to the MATE notebook server at `<http://localhost:8889/>`_ and use the "New" dropdown to create a new Python3 notebook.

.. figure:: assets/create-notebook.png
   :scale: 35

   Create a new Python3 notebook

Optional: click the notebook name (initially "Untitled") to give it a more descriptive name.

.. figure:: assets/rename-notebook.jpg

   Rename the notebook


************************************
Load the desired code property graph
************************************

Within a Python notebook, you need to identify the Code Property Graph you wish to query.
You'll need the Build Id for the target you're interested in.
You can copy it from the MATE dashboard: `<http://localhost:8050/>`_

.. figure:: assets/get-build-id.png
   :scale: 35

   The BuildID for a target

Now, in your MATE notebook enter the following into the first cell, replacing the placeholder Build Id with the one copied from the MATE dashboard:

.. code-block:: python

   session = db.new_session()

   ## TODO: replace the build ID in the next line with the ID from the dashboard
   b = session.query(db.Build).get("fd60a24c857647a4b6707fea56a69db8")
   g = session.graph_from_build(b)

   print(f"Graph loaded with {session.query(g.Node).count()} Nodes and {session.query(g.Edge).count()} Edges")

You'll know it's working if you get nonzero number of nodes and edges as output.

.. figure:: assets/notebook-load-graph.jpg

   Loading a CPG in a notebook


*****************************
Query the code property graph
*****************************

The MATE notebook uses
`SQLAlchemy <https://www.sqlalchemy.org/>`_ to expose the CPG as Python objects.
See :ref:`query_desc` for more information and :doc:`API documentation
<api/MATE/modules>` for a complete reference. The reference documentation is
also available inside Python via the ``help`` function.

Below are some examples queries.
Each assume ``session``, ``b``, and ``g`` have been initialized as described above.

Print every external (e.g. located in ``libc`` ) function, each followed by a list of all the application functions that invoke it:

.. code-block:: python

   for f in session.query(g.Function).filter_by(is_declaration=True).all():
      print("### '", f.name, "' is invoked by:")
      for c in f.callers:
         print("*", c.name)


CPGs are made of nodes and edges.
Some useful utility functions:

.. code-block:: python

   # print node IDs <-> llvm for a Function object
   def show_llvm(f):
      for b in f.blocks:
         print(f"### {b} ###")
         for i in b.instructions:
               print(f"{i} {i.attributes['pretty_string']}")

   # print node IDs <-> llvm for a Function given a function name
   def show_llvm_fname(fname):
      show_llvm(session.query(g.Function).filter_by(demangled_name=fname).one())

   # helper: turn a node UUID into the corresponding Node object
   def nid(uuid):
      return session.query(g.Node).filter_by(uuid=str(uuid)).one()

.. figure:: assets/notebook-node-example.png
   :scale: 35

   Example: Using the functions above to print LLVM for a function, and using this to access a Node (corresponding to a call to ``fprintf``)
