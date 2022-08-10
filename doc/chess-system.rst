#############################
Working with the CHESS System
#############################

MATE forms one component of the larger CHESS System, which is the ultimate software artifact of the
DARPA CHESS program. The CHESS system is an orchestration of software stacks from each of the
performers on the program, which interact with each other over a shared set of infrastructure
services. In this section, we will see how to run the latest version of the CHESS System as
described by the stack definitions provided by each performer.

To be able to run the CHESS System, the ``chess-system`` submodule must be cloned from the upstream repositories.
This will require that you have the necessary credentials, which can currently be found on the MATE wiki.

.. code-block:: bash

   $> git submodule update submodules/chess-system

The ``chess-system`` repository contains the current set of service definitions as delivered by each
performer. These definitions reference container images rather than code repositories, and as such
represent a relatively fully specified state of the system. For more information on how to test an
in-development version of MATE against the rest of the CHESS system, see the appropriate section in
the :ref:`developer guide <hacking:Developing Against the CHESS System>`.

Within the repository, each performer's stack definition can be found in a file of the form
``docker-compose.<stack-name>.yml``. Each stack consists of a number of services, similar to a
regular ``docker-compose.yml``. MATE's own stack definition differs slightly from its
``docker-compose.yml`` in the following ways:

1. All services to be run in a deployment of MATE are found in a single file, whereas they might
   otherwise be split over multiple compose files.
2. Some services are specific to MATE's ability to interoperate with other stacks in the CHESS
   system. These services would not normally be run otherwise.
3. The images associated with each MATE service are pinned to externally pushed versions, and do not
   correspond the current state of the source code repository.

Any subset of the CHESS system can be run at a time, with the following caveats:

1. Most stacks will depend on the common infrastructure stack ``docker-compose.common.yml`` being
   deployed first.
2. Any integration points between two stacks will obviously depend on both stacks being deployed.
   MATE should not require any other stack apart from the common stack.

For more information and stack-specific instructions, see ``submodules/chess-system/README.md``.
