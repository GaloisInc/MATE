#################
MATE POI Analyses
#################

MATE performs various analyses to produce Points of Interest (POIs).

MATE comes with built-in analyses, and you can also write and run your own.
This page explains how to write analysis scripts and how to run analyses via
the MATE REST API.

To write an analysis you need to define two classes:

1. a ``POI`` class which is a record to describe the point of interest

2. an ``Analysis`` class which contains a ``run`` method with the logic of your analysis.

``Analysis`` subclasses yield instances of ``POI`` subclasses as soon as they are computed.

Let's look at a simple example:

*******
Example
*******

.. literalinclude:: ../../bdist/local/lib/python3.8/site-packages/mate/poi/analysis/Example.py
   :language: python


Here are all of the contractual requirements for POIs and Analyses:

    - POIs must be JSON serializable
    - The POI base class provides default ``to_json`` and ``from_json``
      functions which call ``json.loads`` and ``json.dumps``. If your POI
      subclass has simple fields (such as strings) this will be sufficient.
      If you POI has more complex fields (such as objects) you must define your
      own ``to_json`` and ``from_json`` objects that describe how to serialize
      and deserialize instances of your subclass.
    - Analyses must provide a ``run`` method with exactly the signature up above
    - Analyses should yield instances of the POI subclass they are returning as soon as possible
    - Analysis scripts must contain exactly one instance of an Analysis subclass.
    - Analyses may log using calls to ``logger.{log_level}`` but **MUST NOT** print
    - The analysis module itself **MUST** provide an ``analysis_background`` field,
      in Markdown, that will be rendered as context for each POI produced.

*******************
How to run Analyses
*******************

`Click here for the MATE OpenAPI REST API documentation <api.html>`_.

The four relevant REST endpoints are:

    - ``GET /analyses/`` to get all known analysis IDs
    - ``POST /analyses/`` to register an analysis script
    - ``POST /analyses/run/`` to run all analyses
    - ``POST /analyses/{analysis_id}/run/`` to run a specific analysis

Here are examples of how to call each endpoint directly.

.. TIP::
  Replace ``localhost:8666`` as needed with the IP and port number of the MATE
  API service in your local environment.

..
    Note(AC): This section should change as soon as there is a MATE client (#939).

Get all known analysis IDs:
---------------------------

From the command line with the httpie tool:

    .. code-block:: bash

        http GET http://localhost:8666/api/v1/analyses/

or from Python with the ``requests`` library:

    .. code-block:: python

        response = requests.get(f"{base_url}/analyses")

Register an analysis:
---------------------

From the command line with the httpie tool:

    .. code-block:: bash

        http -f POST http://localhost:8666/api/v1/analyses/ analysis@CommandInjection.py

or from Python with the ``requests`` library:

    .. code-block:: python

        response = requests.post(f"{base_url}/analyses", files={"analysis": open(analysis_path, "rb")})

Run all analyses:
-----------------

From the command line with the httpie tool:

    .. code-block:: bash

        http POST http://localhost:8666/api/v1/analyses/run/?build_id=1234-5678-9012-3456

or from Python with the ``requests`` library:

    .. code-block:: python

        response = requests.post(f"{base_url}/analyses/run", params={"build_id" : build_id})

Run a specific analysis:
------------------------

From the command line with the httpie tool:

    .. code-block:: bash

        http POST http://localhost:8666/api/v1/analyses/CommandInjection/run/?build_id=1234567890123456

or from Python with the ``requests`` library:

    .. code-block:: python

        response = requests.post(f"{base_url}/analyses/{analysis_id}/run/", params={"build_id" : build_id})


Workflow
--------

..
    Note(AC): This should also change as soon as there is a MATE client (#939).

Currently, if you would like to run a specific analysis, you need to know its
analysis ID; you can get all known analysis IDs by querying the
``GET /analyses/`` endpoint.

All built-in analyses get an analysis ID when MATE starts up. You can create an
analysis ID for your own analysis by first registering it with the server.

To register your own analysis:
    - ``POST /analyses/``

To run any analysis:
    - ``GET /analyses/ to find its ID``
    - ``POST /analyses/{analysis_id}/run/``

To run all analyses:
    - ``POST /analyses/run/``
