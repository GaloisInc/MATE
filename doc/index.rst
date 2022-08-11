MATE: Merged Analysis To prevent Exploits
=========================================

MATE is a suite of tools for interactive program analysis with a focus on
hunting for bugs in C and C++ code. MATE unifies application-specific and
low-level vulnerability analysis using code property graphs (CPGs), enabling the
discovery of highly application-specific vulnerabilities that depend on both
implementation details and the high-level semantics of target C/C++ programs.

For a high-level overview of MATE, see :doc:`overview`. To start using MATE to
explore a program, see :doc:`quickstart`. Contributors should read
:doc:`hacking`.

..
   HACK(ww): https://stackoverflow.com/a/31820846
   HACK(ww): The above comment doesn't work in the toctree context, where
   it should be!

.. toctree::
   :hidden:
   :caption: Start Here

   overview
   quickstart

.. toctree::
   :hidden:
   :caption: Reference

   architecture
   cli
   cpg
   debugging-builds
   dwarfcore
   environment
   getting-started
   hacking
   legal
   mantiserve
   cli-overview
   pois
   schemata/cpg
   signatures
   testing
   trace
   under-constrained-manticore
   usagefinder
   using-flowfinder
   using-notebooks
   using-rest-api

.. toctree::
   :hidden:
   :caption: API Documentation

   api/index
   MATE REST API <api.html#http://>

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

Acknowledgments
===============

This material is based upon work supported by the United States Air Force and
Defense Advanced Research Project Agency (DARPA) under
Contract No. FA8750-19-C-0004. Any opinions, findings and conclusions or
recommendations expressed in this material are those of the author(s) and do
not necessarily reflect the views of the United States Air Force or DARPA.
Approved for Public Release, Distribution Unlimited.
