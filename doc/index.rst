MATE: Merged Analysis To  prevent Exploits
==========================================

..
   TODO(lb, #1531): Audit for CHESS-specific references
   TODO(lb, #1709): Reorganize documentation

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
   :caption: User Documentation

   overview
   quickstart
   vulnerability-types
   using-flowfinder
   using-rest-api
   using-notebooks
   usagefinder
   pois
   mantiserve
   under-constrained-manticore
   debugging-builds

.. toctree::
   :hidden:
   :caption: Developer Documentation

   MATE REST API <api.html#http://>
   schemata/cpg
   signatures
   analysis
   hacking
   testing
   architecture
   getting-started
   mate-cli-overview
   cli
   dwarfcore
   standalonepa
   trace
   environment
   api/index
   legal

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


Project Status
==============

MATE is not actively developed by Galois, Inc. Please reach out to the email
address "mate at galois dot com" if you'd like to discuss further work on MATE!

Acknowledgments
===============

This material is based upon work supported by the United States Air Force and
Defense Advanced Research Project Agency (DARPA) under
Contract No. FA8750-19-C-0004. Any opinions, findings and conclusions or
recommendations expressed in this material are those of the author(s) and do
not necessarily reflect the views of the United States Air Force or DARPA.
Approved for Public Release, Distribution Unlimited.
