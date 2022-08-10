##################
Points of Interest
##################

MATE identifies potential vulnerabilities and reports Points of Interest (POIs).
The various kinds of vulnerabilities that MATE can detect are described in
:doc:`vulnerability-types`.

To view the POIs that MATE found for a particular binary, navigate to the MATE
builds page (usually at `<http://localhost:3000/builds>`_) and click "view POIs"
to see a list of POIs.

.. figure:: assets/dashboard-pois.png
   :scale: 35

   The POI page will list POI findings, with links to view each finding in Flowfinder

.. important::
   The list of POIs starts empty. Results are added one-by-one as the MATE analyses running in the background report findings. Refresh the POIs page periodically to see the most up-to-date set of results.

For each POI result, there is:

- "Analysis Name": the type of analysis, see :doc:`vulnerability-types` for details
- "Insight": brief summary of the finding itself
- "Code Graph": click the "analyze" link to visualize this finding in Flowfinder, see :doc:`using-flowfinder` for details

.. figure:: assets/flowfinder-usage.png
   :scale: 15

   Visualizing a POI in Flowfinder
