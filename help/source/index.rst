.. GroundTruther documentation master file, created by
   sphinx-quickstart on Sun Feb 12 17:11:03 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

GroundTruther
==============

Overview
--------
`GroundTruther` is a software system for concurrently analyzing co-located multibeam echosounder (MBES) datasets (bathymetry and backscatter) and co-registered seafloor imagery. 

`GroundTruther` provides a specialized graphical user interface where image browsing and geospatial data are directly linked using the QGIS plugin system. Furthermore, it offers several toolboxes that allow extraction of the backscatter distribution and angular response and the extraction of bathymetric derivatives from any given region to ultimately build complex and detailed reports in rich-text and machine-readable formats.


`GroundTruther` is entirely built in Python, in its current version is available as a QGIS plugin and some of its functionalities are based on the `grassapi <link URL>`_  external service

At the moemnt GroundTruther is considered as a proof of concept software, where all the components are rapidly changing based on user's feedback and is by no means feature complete. 

If interested in contributing, please contact: Massimo Di Stefano (epiesasha@.com)

Installation
------------

A list of dependencies is included in the `requirements.txt <link URL>`_ - use this file to create a python virtual environment and make sure it is accessible by `QGIS`, then install the plugin via the `QGIS` plugin interface.



Contents:

.. toctree::
   :maxdepth: 2
   
   requirements/index
   quickstart/index

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

