###########################
Under-constrained Manticore
###########################
..
   These first two paragraphs are duplicated in overview.rst, and the first
   sentence is in quickstart.rst. Updates to one should be reflected in the
   others.

MATE provides a web UI for exploring programs with the `Manticore
<https://github.com/trailofbits/manticore>`_ symbolic execution engine in an
*under-constrained* mode. Unlike traditional symbolic execution which begins at
the program entry point and executes until the program exits, under-constrained
symbolic execution starts at an arbitrary function. This specificity means that
under-constrained symbolic execution can analyze parts of programs that would be
too large or complex for traditional symbolic execution.

Symbolic execution enables bit-precise local reasoning about memory and
arithmetic, which complements MATE's higher-level inter-procedural data- and
control-flow analyses.

Under-constrained execution is implemented as a Manticore Plugin, which means it
can be enabled/disabled easily, and should be able to coexist with other
:ref:`detectors <detectors>` such as the UAF or variable-bounds detectors.

In broad terms, under-constrained Manticore works as follows:

*  **Program initialization**:
   the program is run normally from its entry-point, until the ``main`` function
   is reached. This allows shared libraries to be properly initialized, as well as
   any globals in the program. When ``main`` is reached, Manticore jumps directly to
   the beginning of the target function and continues from there


*  **Target function setup**:
   when jumping directly to the target function, Manticore needs to provide proper
   function arguments as if it was normally called from within the program. To do so,
   it uses the CPG to infer the expected arguments and their types, and creates
   a symbolic expression for every argument. So the target function is called with fully
   symbolic inputs.


*  **Symbolic pointers**:
   when a function takes a pointer as argument, e.g ``foo(int *ptr)``, and that pointer is
   dereferenced in the function's body, Manticore has to rely on a special memory model.
   In a normal Manticore run, ``ptr`` would have been initialized previously by the program,
   but in under-constrained mode it is purely symbolic, and doesn't point to any real
   allocated data. So Manticore will artificially allocate a symbolic object pointed by
   ``ptr`` (and thus containing only symbolic data as well), and read inside that object rather
   than in the regular memory when ``ptr`` is dereferenced.
   Note that underlying usage of a special memory layout happens seamlessly.


* **Out-of-bounds memory access detection**:
  when the program reads from a symbolic offset in an under-constrained object, for instance:

  .. code-block:: c

      foo(int *ptr, int idx){
          return ptr[idx];
      }

  under-constrained Manticore is able
  to detect if the access can be out-of-bounds by using the solver to determine whether
  the symbolic offset can exceed the bounds of the object. If yes, then it will record
  a test case indicating a potential OOB error.

********************************************
Starting an under-constrained Manticore task
********************************************

Under-constrained Manticore tasks are started just like regular Manticore exploration tasks.
The request format is available in the `MATE REST API documentation
<api.html#operation/_execute_manticore_exploration_task_api_v1_manticore_explore__build_id__post>`_
by selecting ``ExploreFunctionOptions`` in the request.

The exploration options that are passed with the API call are similar to the regular exploration
options with some additional settings:

* **target_function**: the name of the target function to execute. In case of a C++ binary
  the name must be mangled.

* **input_constraints**: additional symbolic state constraints. Those can be used to
  constrain Manticore further to eliminate possible errors that are false positive or
  to optimize the execution time by trimming some exploration paths. See the
  :ref:`constraints_DSL` section for more details.

* **primitive_ptr_policy**: the policy for choosing the length of unbounded symbolic arrays
  that contain primitive types. The default policy lets Manticore choose reasonable lengths
  for arrays, but the user can specify explicit lengths to use by switching to the
  ``custom`` policy.

* **complex_ptr_policy**: the policy for choosing the length of unbounded symbolic arrays
  that contain complex types such as structures or objects. The default policy lets
  Manticore choose reasonable lengths for arrays, but the user can specify explicit lengths
  to use by switching to the ``custom`` policy.

.. _constraints_DSL:

******************************************
Specifying additional symbolic constraints
******************************************

Sending additional symbolic constraints is central in the under-constrained Manticore
workflow. When first starting a task it is very likely that Manticore will report many errors
that are false positives. Incrementally adding constraints and re-launching the task allows
to eliminate the false positives and keep only the interesting results.

Two examples of using constraints are:

* **relationship between function arguments**:
  consider the following ``strcpy``-like function:

  .. code-block:: c

    void my_strcpy(char *dst, char *src){
        while((*(dst++) = *(src++))){};
    }

  If ``src`` is longer than ``dst``, Manticore will return a potential out-of-bounds memory
  write error. However, in some cases, we might be **sure** (or want to assume) that
  ``src`` is smaller than ``dst``. Using a symbolic constraint will allow use to enforce
  the size relationship between ``src`` and ``dst`` in Manticore and remove the out-of-bounds
  error.


* **data structure invariants**:
  imagine a function that takes the following struct as argument:

  .. code-block:: c

    struct string {
        char *str;
        int len; // Length of 'str'
    };

  under-constrained Manticore doesn't know that ``len`` if referring to the size
  of ``str``. While in some cases avoiding to correlate ``len`` and ``str``
  could help find bugs withing the ``string`` implementation, we will often want
  to inform Manticore of the relationship between those two variables (one is
  the size of the other) so that the ``string`` struct behaves correctly and
  doesn't cause many false positive errors that will hide other interesting
  findings. This becomes even more true when using classes of the C++ standard
  library like ``std::vector``, ``std::string``, etc, of whom Manticore **must**
  assume that their implementations and internals are bug-free.

Symbolic constraints can be written using the Domain-Specific-Language (DSL) described below.

==================================
Constraints on function parameters
==================================

Basic constraints on function parameters can be expressed using regular
arithmetic and logic operations and by following the variable naming found
in the source code. For example if we target the ``foo`` function:

  .. code-block:: c

    struct A {
        int a;
        int b;
    };

    void foo(struct A x) {
        ...
    }

We could add the following constraint on the ``x`` argument:

  .. code-block::

    x.a <= x.b + 10

Most of the operations can be expressed using the corresponding standard C operator
(``+``, ``-``, ``*``, ``>>``, ``&``, ``^``, ``%``, etc). However, many operators exist in both *signed*
and *unsigned* versions. In order to distinguish between them, some operators are written using a
function-like syntax (``<operator>(arg1, arg2, ...)``):

* Unsigned comparisons: ``ULE()``, ``ULT()``, ``UGE()``, ``UGT()``  (``>``, ``<``, etc, default to signed comparisons)
* Signed division: ``SDIV()`` (``/`` defaults to unsigned division)
* Arithmetic shift left: ``SAR()``
* Concatenation: ``CONCAT(<higher>, <lower>)``
* Bitfield extract: ``EXTRACT(<arg>, <offset>, <size>)``

.. _meta_variables:

==============
Meta-variables
==============

The symbolic constraint DSL offers a few special operators that refer to "properties" of
variables rather than to the variable themselves. Since every property of every object is
represented by a dedicated unique symbolic variable, we call those **meta-variables**.

* ``$LEN(<var>)``: can be used to refer to the length of an array pointed by a raw pointer.
  When under-constrained Manticore receives an unbounded pointer (e.g ``int*``) it has
  to guess if the pointer points to a single integer in memory, or if it points to an
  array of integers. In addition to hard-coded heuristics, users can give hints or constrain
  array sizes using ``$LEN()``. For instance, ``$LEN(buf) < 20`` tells Manticore that the number
  of elements pointed by ``buf`` is less than 20.

  .. important::
   ``$LEN()`` refers to the *number of contiguous elements* of an array in memory, and **not**
   the total length in bytes of the array

* ``$CAPACITY(<var>)``: this refers to the total capacity of a container class such as
   ``vector`` or ``string``. When used alone, this meta-variable doesn't have much sense, it
   is meant to be used in :ref:`generic_class_constraints` to ensure that under-constrained
   container classes have enough space allocated to add elements without needing to re-allocate
   additional space.

   .. note::
   We want to avoid memory re-allocation within complex objects because memory allocation
   using symbolic pointers or sizes is likely to break under-constrained Manticore

   An example usage of ``$CAPACITY()`` can be found in our :ref:`generic_class_constraints`
   ``vector`` reference example.

* ``$SIZE(<var>)``: size is similar to ``$CAPACITY`` in so far as it refers to the current size
  of a container-class. It should be contained between ``0`` and ``$CAPACITY(<var>)``. Again,
  using ``$SIZE()`` standalone doesn't make sense, but it comes in handy for writing
  generic class constraints.

Example constraints to make the following structure coherent:

.. code-block:: c

    struct buffer {
        int *buf;
        int len; // Current number of elements stored in 'buf'
    };

    void foo(struct buffer *b);

.. code-block::

    $LEN(b.buf) == $CAPACITY(b)   # total length of b.buf: as big as b's capacity
    $SIZE(b) <= $CAPACITY(b) # current size of b less or equal to it's capacity
    b.len == $SIZE(b)


==============================
``$POINTS_WITHIN`` constraints
==============================

By default, under-constrained Manticore will create new symbolic objects for every
symbolic pointer it deals with. For example, if running the ``foo(int *a, int *b)``
function, Manticore will create two symbolic arrays, one for ``a`` and one for ``b``.
Those are distinct and will never overlap.

In some cases, pointers actually point to the same memory area. For example that is the case
in ``std::vector``'s implementation where the internal storage beginning and end are both
indicated by a raw pointer.

To tell Manticore that two pointers point to the same area, we can use the ``$POINTS_WITHIN``
operator. The following:

.. code-block::

    $POINTS_WITHIN(a,b)

will lead to Manticore creating one symbolic array for ``a`` and make ``b`` point to somewhere
within ``a``.

.. _generic_class_constraints:

=========================
Generic class constraints
=========================

Symbolic constraints that must apply to all symbolic instances of a given type or class
can be written using the following syntax:

.. code-block::

    <class_name>: <constraint>

The ``<class_name>:`` specifier must match type names as they are stored in the CPG.

Since class constraints are generic, there is no declared variable name to use when
writing the constraint. Instead, one can use the ``$OBJ.`` syntax to refer to the
instance of the class. If we build up on our previous example, that would give:

.. code-block:: c

    struct buffer {
        int *buf;
        int len; // Current number of elements stored in 'buf'
    };

    void foo(struct buffer *b);

.. code-block::

    buffer: $LEN($OBJ.buf) == $CAPACITY($OBJ)   # total length of 'buf' field as big as the instance capacity
    buffer: $SIZE($OBJ) <= $CAPACITY($OBJ) # current size of the instance less or equal to it's capacity
    buffer: $OBJ.len == $SIZE($OBJ)

When under-constrained Manticore instantiates the function argument ``b``, the generic
constraints for ``buffer`` are applied to ``b`` (``$OBJ`` gets replaced by ``b``).

It is also possible to write generic constraints for templated types by replace template
type arguments by ``#``:

.. code-block::

    some_templated_class<#,#>: ...

In the constraint body, template arguments can be referred to with the ``#<num>`` syntax.
``#0`` refers to the first template argument, ``#1`` to the second, and so on. Template arguments
references with ``#`` can be used in constraints by the following operators:

- ``$TYPESIZE(#<num>)``: returns the size in bytes for template argument number ``<num>``, starting at ``#0``

Below is an example set of constraints that enforces correct behavior for a symbolic ``std::vector``
with maximal capacity of 100 elements:

.. code-block::

  # Internal correctness of the data structure
  vector<#,#>: $OBJ._M_impl._M_finish - $OBJ._M_impl._M_start == $SIZE($OBJ)*$TYPESIZE(#0)
  vector<#,#>: $OBJ._M_impl._M_end_of_storage == $OBJ._M_impl._M_start + ($CAPACITY($OBJ)*$TYPESIZE(#0))
  vector<#,#>: $LEN($OBJ._M_impl._M_start) == $CAPACITY($OBJ)
  vector<#,#>: $CAPACITY($OBJ) == 100
  # Make all internal pointers point to the same symbolic buffer
  vector<#,#>: $POINTS_WITHIN($OBJ._M_impl._M_finish, $OBJ._M_impl._M_start)
  vector<#,#>: $POINTS_WITHIN($OBJ._M_impl._M_end_of_storage, $OBJ._M_impl._M_start)


.. _forking:

*************
State forking
*************

Under-constrained Manticore will fork at the same locations as regular Manticore.
However, for practical reasons, under-constrained Manticore also needs to perform
additional forking on :ref:`meta_variables`. It will thus fork on:

- ``$LEN``: the length of an array pointed by a symbolic pointer
- ``$CAPACITY``: the capacity of a symbolic container class instance
- ``$SIZE``: the size (number of current elements) of a symbolic container class instance

If desired it is possible to constrain some of the meta-variables further to avoid
too much state forking by  :ref:`constraints_DSL`.
