## GroundTruther: A QGIS plug-in for seafloor characterization



The main goal of this project is to create a software system that can analyze multibeam echo sounder (MBES) datasets and seafloor imagery at the same time. This will meet the need for a single platform for exploring and analyzing seafloor data. The system has a graphical user interface for browsing images and geospatial data, as well as several toolboxes for getting backscatter distribution, its angular response, and bathymetric derivatives so that detailed quantitative reports can be made.
The overall objective is to provide an efficient means of understanding the relationships between morphology, backscatter, and the observed biota and, thus, the relationship between the physical and ecological elements of the seafloor. In addition, Groundtruther provides new ways to interpret remotely sensed information derived from MBES and aids in the development of spatial distribution models. It might also improve ground-truth databases that are used to make formal geophysical models that connect acoustic backscatter observations to the seafloor's natural properties.

This plugin has been tested on Linux and is available at https://plugins.qgis.org/plugins/groundtruther/ - An experimental version that aims at being compatible with Windows is available at:  https://qgis.geohab.org/#GroundTruther - A sample dataset was also produced to test the application and is available under a ccby4 open license at https://zenodo.org/records/7995674 

## Installation


A list of dependencies is included in the [requirements.txt](../../dependencies/requirements.txt) - use this file to create a python virtual environment and make sure it is accessible by `QGIS`, then install the plugin via the `QGIS` plugin interface.

* Download a python distribution (e.g. Anaconda) and install it:

```bash
wget https://github.com/conda-forge/miniforge/releases/download/23.3.1-1/Mambaforge-23.3.1-1-Linux-x86_64.sh
sh Mambaforge-23.3.1-1-Linux-x86_64.sh
```

* create a virtual environment and install the requirements:

```bash
mamba create -n groundtruther python=3.10
conda activate groundtruther
mamba install -c conda-forge ocl-icd-system
mamba install -c conda-forge qgis 
mamba install -c conda-forge --file dependencies/requirements.txt 
```

On Windows, Groundtruther has been tested in a conda environemt running with python 3.10 and QGIS v3.34 - an [example environment](https://gist.github.com/epifanio/ed8eeb681e23a7cb7a27ce0568a04e44) is available as reference

```
conda create --name groundtruther --file groundtruther.txt
```
