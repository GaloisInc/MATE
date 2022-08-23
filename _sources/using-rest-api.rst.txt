##################
Using the REST API
##################

MATE capabilities are controlled using a REST API. `Click here for the MATE
OpenAPI REST API documentation <api.html>`_.

Use this API via the :doc:`MATE CLI <cli-overview>`, the REST client of
your choice, or interactively through the interactive Swagger UI web interface
at `<http://localhost:8666/api/v1/>`_.

Some useful operations available via the REST API include:

- Get more visibility into the status of a build
- Manually starting a compilation phase with custom parameters (see API docs for
  details)
- Manually (re)starting a build with custom parameters (see API docs for
  details)
- Manually running POI analyses for a build
- Running Manticore tasks

*********************************
Running POIs after a manual build
*********************************

Assuming that you've successfully completed the build phase for a particular
target, you can explicitly run all currently registered POIs against
the build with a single HTTP request:

.. code-block:: bash

  $ http POST http://localhost:8666/api/v1/analyses/run/YOUR-BUILD-ID

This will run all POIs asynchronously, adding their results to the database
(and subsequently associating them with the build) as they come in. You
can view the status of each POI's task under the POI page for the specified
build in the MATE UI.
