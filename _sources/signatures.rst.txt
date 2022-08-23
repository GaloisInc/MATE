###############
MATE Signatures
###############

MATE is designed to analyze whole programs for vulnerabilities. If the
program under analysis invokes library code or system calls that are
not included in the source under analysis, MATE may miss possible
behaviors of the program and potential vulnerabilities.

MATE can model the behavior of external code via *signatures* that
describe the salient features of the code that is not available for
analysis.

Providing signatures
####################

When using the legacy command line interface to MATE, you can specify
additional signatures to use during analysis with the command line
argument :code:`--signatures <path to yml file>`. The required format
of this file is described in the section `Signature file
format`. Signatures in the specified file will be used *in addition*
to signatures that are part of the MATE distribution. Those signatures
are shown in section `Built-in signatures`.

When using the MATE server, additional signatures can be supplied via
``signatures`` list in the build's options (see `BuildOptions`). The format of
each dictionary in this list is the serialized representation of the format
described in the `Signature file format` section.

.. _Signature file format:

Signature file format
#####################

Each entry should have the form:

.. code-block::

   - name: function_name
     signatures:
     - signature_name: [ signature arguments ... ]
     - ...

If a signature should be applied multiple times with different
arguments, it should appear multiple times in the list. For example:

.. code-block::

   name: example_function
   signatures:
   - pts_arg_memcpy_arg: [ 0, 1 ]
   - pts_arg_memcpy_arg: [ 0, 2 ]
   - input:
      to:
        - return: []
   - output:
      from:
        - arg: [ 1 ]
   - dataflow:
       from:
        direct:
          - arg: [ 0 ]
       to:
       - return: []

Available signatures
####################

Points-to signatures
********************

:code:`- pts_none: []`

  Used to indicate that the function has no points-to relevant
  behavior and that the function should not be reported as missing
  points-to signatures.

:code:`- pts_return_alloc: []`

  Allocates a new memory object with type compatible with the
  callsite's return type.

  Example:
   :code:`pts_return_alloc: []`

   .. code-block::

      int *a = example();
      int *b = example();

   Variables :code:`a` and :code:`b` will point to distinct allocations of type :code:`int`.

:code:`- pts_return_alloc_once: []`

  The pointer returned by this function at any callsite will point
  to the same allocation. Can be used to model libraries which
  return a pointer to a static internal location.

  Example:
   :code:`pts_return_alloc_once: []`

   .. code-block::

      int *a = example();
      int *b = example();

   Variables :code:`a` and :code:`b` will point to the same allocation of type :code:`int`.

:code:`- pts_return_aliases_arg: [ <arg index> ]`

  The pointer returned by this function may point to any
  type-compatible allocation pointed to by the argument at the
  specified index.

  Example:
   :code:`pts_return_aliases_arg: [ 1 ]`

   .. code-block::

      int a = 0;
      int b = 1;
      int *c = example(&a, &b);

   Variable :code:`c` will point to the stack allocation for variable :code:`b`.

:code:`- pts_return_aliases_arg_reachable: [ <arg index> ]`

  The pointer returned by this function may point to any
  type-compatible allocation that is reachable in the points-to
  graph from the argument at the specified index.

  Can be used to model functions that extract interior pointers
  from arguments.

  Example:
   :code:`pts_return_aliases_arg: [ 1 ]`

   .. code-block::

      struct container { int *internal; };
      int a = 0;
      int b = 1;
      struct container as = { .internal = &a };
      struct container bs = { .internal = &b };
      int *c = example(&as, &bs);

   Variable :code:`c` will point to the stack allocation for variable :code:`b`.

:code:`- pts_return_points_to_global: [ <global name> ]`

  The pointer returned by this function points to the allocation
  corresponding to the named global (which must be defined in the
  program under analysis).

  Example:
   :code:`pts_return_points_to_global: [ test ]`

   .. code-block::

      int test = 5;

      void main(void) {
        int *a = example();
      }

   Variable :code:`a` will point to the global allocation for :code:`test`.

:code:`- pts_return_aliases_global: [ <global name> ]`

  The pointer returned by this function may point to any
  type-compatible allocation pointed to by the named global (which
  must be defined in the program under analysis).

  Example:
   :code:`pts_return_aliases_global: [ testptr ]`

   .. code-block::

      int test = 5;
      int *testptr = &test;

      void main(void) {
        int *a = example();
      }

   Variable :code:`a` will point to the global allocation for :code:`test`.

:code:`- pts_return_aliases_global_reachable: [ <global name> ]`

  The pointer returned by this function may point to any
  type-compatible allocation that is reachable in the points-to
  graph from the named global (which must be defined in the program
  under analysis).

  Example:
   :code:`pts_return_aliases_global_reachable: [ testptr ]`

   .. code-block::

      struct container { int *internal; };

      int test = 5;
      struct container teststruct = { .internal = &test };
      int *testptr = &teststruct;

      void main(void) {
        int *a = example();
      }

  Variable :code:`a` will point to the global allocation for :code:`test`.

:code:`- pts_arg_alloc: [ <arg index> ]`

  Allocates a new memory object with type compatible with the
  specified argument's pointer type and updates the points-to set of
  the pointer.

  Example:
   :code:`pts_arg_alloc: [ 1 ]`

   .. code-block::

      int *a = nullptr;
      int *b = nullptr;
      int *c = nullptr;
      int *d = nullptr;
      example(&a, &b);
      example(&c, &d);

   Variables :code:`b` and :code:`d` will point to distinct
   allocations of type :code:`int`. Variables :code:`a` and :code:`c` will not
   point to any allocations.

:code:`- pts_arg_alloc_once: [ <arg index> ]`

  Any pointers pointed-to by callsite arguments at the specified index
  will point to the same allocation. Can be used to model libraries which
  assign pointers to static locations into output variables.

  Example:
   :code:`pts_arg_alloc_once: [ 1 ]`

   .. code-block::

      int *a = nullptr;
      int *b = nullptr;
      int *c = nullptr;
      int *d = nullptr;
      example(&a, &b);
      example(&c, &d);

   Variables :code:`b` and :code:`d` will point to the same allocation
   of type :code:`int`.

:code:`- pts_arg_memcpy_arg: [ <destination arg index>, <source arg index> ]`

  Points-to sets will be updated as if the memory pointed to by the
  source argument might have been copied to the memory pointed to by
  the destination argument.

  Example:
   :code:`pts_arg_memcpy_arg: [ 0, 1 ]`

   .. code-block::

      int a = 0;
      int b = 1;
      int *ap = &a;
      int *bp = &b;
      example(&ap, &bp);

   Variable :code:`ap` will point to the allocations for both
   variables :code:`a` and :code:`b`. The points-to set of variable
   :code:`bp` will be unchanged and still refer only to :code:`b`.

:code:`- pts_arg_memcpy_arg_reachable: [ <destination arg index>, <source arg index> ]`

  Points-to sets will be updated as if any type-compatible  memory
  allocation reachable from the source argument might have been copied
  to the memory pointed to by the destination argument.

  Example:
   :code:`pts_arg_memcpy_arg_reachable: [ 0, 1 ]`

   .. code-block::

      struct container { int *internal; };
      int a = 0;
      int b = 1;
      struct container sb = {.internal = &b};
      int *ap = &a;
      struct container *sbp = &sb;
      example(&ap, &sbp);

   Variable :code:`ap` will point to the allocations for both
   variables :code:`a` and :code:`b`. The points-to set of variable
   :code:`sbp` and :code:`sb.internal` will be unchanged.

:code:`- pts_arg_memcpy_global: [ <destination arg index>, <global name> ]`

  Points-to sets will be updated as if the named global might have
  been copied to the memory pointed to by the destination argument.

  Example:
   :code:`pts_arg_memcpy_arg: [ 0, test_struct ]`

   .. code-block::

      struct container { int *internal; };
      test_int = 0;
      struct container test_struct = {.internal = &global_int};

      void main(void) {
        struct container a;
        example(&a);
      }

   Variable :code:`a.internal` will point to the global allocation
   :code:`test_int`.

:code:`- pts_arg_memcpy_global_reachable: [ <destination arg index>, <global name> ]`

  Points-to sets will be updated as if the named global or any data
  reachable from it might have been copied to the memory pointed to by
  the destination argument.

  Example:
   :code:`pts_arg_memcpy_global_reachable: [ 0, test_struct ]`

   .. code-block::


      struct container { int *internal; };
      test_int = 0;
      struct container test_struct = {.internal = &global_int};

      void main(void) {
        int a = 0;
        int *ap = &a;
        example(&ap);
      }

   Variable :code:`ap` will point to the global allocation :code:`test_int`.

:code:`- pts_arg_points_to_global: [ <destination arg index>, <global name> ]`

  The points-to set of the pointer pointed to by the specified
  argument will be updated to include the allocation corresponding to
  the named global.

  Example:
   :code:`pts_arg_points_to_global: [ 0, test_int ]`

   .. code-block::

      test_int = 0;

      void main(void) {
        int a = 0;
        int *ap = &a;
        example(&ap);
      }

   Variable :code:`ap` will point to the global alocation :code:`test_int`.

Dataflow signatures
*******************

Dataflow signatures describe how values involved in an external function call
depend on each other.

MATE currently supports three kinds of dataflow signatures:

* Input signatures, which indicate values that may be directly
  influenced by external input to the program,

* Output signatures, which indicate values that may directly
  effect externally observable behaviors of the program, and

* Dataflow signatures, which describe the flow of data between
  values within the program.

Input signatures have the format:

.. code-block::

   - input:
      tags: [tag0,tag1,..]
      to:
        - selector: [ arguments ... ]
        ...

Where each selector is a valid selector as described below.
The :code:`tags` entry is optional for input, output and dataflow signatures. For example, the following signature is also valid:

.. code-block::

   - input:
      to:
        - selector: [ arguments ... ]
        ...

Output signatures have the format:

.. code-block::

   - output:
      tags: [tag0,tag1,..]
      from:
        - selector: [ arguments ... ]
        ...

Dataflow signatures have the format:

.. code-block::

   - dataflow:
       tags: [tag0,tag1,..]
       from:
          dataflow-type:
            - selector: [ arguments ... ]
            ...
       to:
          - selector: [ arguments ... ]
         ...

Note that elements :code:`from`, :code:`to` and :code:`tags` are not preceded by a
:code:`-`.

The :code:`from` value of dataflow signatures must contain objects whose keys are 
a :code:`dataflow-type`. The three options of :code:`dataflow-type` are:

* :code:`direct`: representing values that are copied or directly computed with to derive new values

* :code:`indirect`: representing the dependency of a result on which data is accessed via a pointer or pointer-like value such as a file descriptor

* :code:`control`: representing dependency due to conditional execution


:code:`indirect` dataflow specifies that an argument effects the way in which a result 
is computed (as in: which value is used?), while a :code:`control` dataflow specifies 
that an argument effects whether a result is computed.

As an example, take the signature of the function :code:`__xpg_basename`:

.. code-block::

  - name: __xpg_basename
    # char * __xpg_basename(const char * path)
    #
    # __xpg_basename shall return a pointer to the final component of
    # the pathname named by path.
    signatures:
    - pts_return_aliases_arg: [0]
    - dataflow:
        from:
          direct:
            - arg: [0]
          indirect:
            - arg_points_to: [0]
        to:
          - return: []

There is :code:`direct` dataflow from :code:`arg: [0]` because it is used directly
to derive the pointer to the final component of the pathname. There is also 
:code:`indirect` dataflow from :code:`arg_points_to: [0]` because the contents of the
buffer pointed to by :code:`path` effect how the result is computed. For example, the
basename is computed differently if the :code:`path` buffer has the string :code:`"/etc/passwords"`
than if it has the string :code:`""`.

For more examples, look at default-signatures.yml.

Selectors
=========

The currently implemented selectors for dataflow signatures are
described below:

:code:`- return: []`

  Selects the return value of the call site

:code:`- return_points_to: []`

  Selects memory locations pointed to by the return value of the call
  site along with any potential aliases.

:code:`- return_points_to_aggregate: []`

  Selects memory locations pointed to by the return value of the call
  site along with any potential aliases. For pointers to the beginning
  of aggregate objects (such as structs), also includes subregions of
  the aggregate object.

:code:`- return_reachable: []`

  Selects memory locations and their aliases that are reachable from
  the return value of the call site.

:code:`- arg: [ <arg index> ]`

  Selects the node corresponding to the call site's argument at that
  position.

:code:`- arg_points_to: [ <arg index> ]`

  Selects memory locations and their aliases that are reachable from
  the argument to the call site at the indicated position.

:code:`- arg_points_to_aggregate: [ <arg index> ]`

  Selects memory locations and their aliases that are reachable from
  the argument to the call site at the indicated position. For pointers
  to the beginning of aggregate objects (such as structs), also includes
  subregions of the aggregate object.
  
:code:`- arg_reachable: [ <arg index> ]`

  Selects memory locations and their aliases that are reachable from
  the argument to the call site at the indicated position.

:code:`- global: [ <global name> ]`

  Selects the named global variable.

Loading signatures to an existing MATE CPG
##########################################

To add points-to signatures to a CPG, the CPG must be rebuilt with a
new ``signatures.yml`` file.

Dataflow signatures can be added dynamically (e.g., from a MATE notebook)
calling the methods ``add_dataflow_signature``, ``add_input_signature``, or
``add_output_signature`` on your ``cpg`` object.

Each method takes two arguments: a function name and a dict whose
shape matches the corresponding YAML format.

For example, to add the signature:

.. code-block ::

   example:
     - dataflow:
         from:
         - arg: [ 0 ]
         - arg_points_to: [ 1 ]
         to:
         - return: []

You would call:

.. code-block ::

   cpg.add_dataflow_signature(
     "example",
     { "from":
       [
         { "arg": [ 0 ] },
         { "arg_points_to": [ 1 ] },
       ],
       "to":
       [
         { "return": [] },
       ],
     }
   )

.. _Built-in signatures:

Built-in signatures
###################

.. literalinclude:: ../../../default-signatures.yml
    :language: yaml
