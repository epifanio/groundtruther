## GroundTruther: A QGIS plug-in for seafloor characterization

The main goal of this project is to create a software system that can analyze multibeam echo sounder (MBES) datasets and seafloor imagery at the same time. This will meet the need for a single platform for exploring and analyzing seafloor data. The system has a graphical user interface for browsing images and geospatial data, as well as several toolboxes for getting backscatter distribution, its angular response, and bathymetric derivatives so that detailed quantitative reports can be made.

The overall objective is to provide an efficient means of understanding the relationships between morphology, backscatter, and the observed biota and, thus, the relationship between the physical and ecological elements of the seafloor. In addition, GroundTruther provides new ways to interpret remotely sensed information derived from MBES and aids in the development of spatial distribution models. It might also improve ground-truth databases that are used to make formal geophysical models that connect acoustic backscatter observations to the seafloor's natural properties.

The plugin is available at https://plugins.qgis.org/plugins/groundtruther/ — a sample dataset for testing is available under a CC-BY-4.0 open license at https://zenodo.org/records/7995674.

---

## What's New

### QGIS 4 / Qt6 support
GroundTruther has been ported to **QGIS 4** and **Qt6 / PyQt6**. All Qt5-specific enum usage, API calls, and UI definitions have been updated. The plugin is now tested on both **Linux** and **Windows**.

### Video player
A dedicated **Video Player** dock allows synchronized playback of survey video alongside the QGIS map canvas:

- Load a video file with an associated GPS metadata CSV
- Geo-link mode pans the map canvas to match the current video frame position
- GPS track layer rendered as a styled line on the map canvas
- Frame-level video annotation editor (add, edit, delete annotations per frame)

### Image annotation editor
The image browser now includes an improved **annotation editor** supporting per-image bounding-box annotations with configurable confidence thresholds.

### Dock-based UI
All major panels are now independent floating dock widgets that can be placed anywhere in the QGIS window:

| Toolbar button | Panel |
|---|---|
| ![image](qtui/icons/file-image.svg) | Image Browser |
| ![video](qtui/icons/forward.svg) | Video Player |
| ![report](qtui/icons/note-sticky.svg) | Report Builder |
| ![query](qtui/icons/chart-line.svg) | BS Query Builder |
| ![reset](qtui/icons/arrows-rotate.svg) | Restore Default Layout |

- Dock positions and visibility are **persisted across sessions**
- All panels start hidden on first load — open them via the toolbar icons
- "Restore Default Layout" resets positions to defaults

### Bug fixes
- Fixed crash on plugin reload caused by dangling pyqtgraph `ViewBox`
- Fixed `RuntimeError` on `QgsVectorLayer` deleted when loading a new QGIS project
- Fixed `sip.isdeleted()` import path for PyQt6 (`PyQt6.sip`)
- Fixed dock/toolbar registration crash on Qt6 when dragging tabbed docks
- Fixed image browser and video dock not removed on plugin unload

---

## Installation

A list of dependencies is included in [dependencies/requirements.txt](dependencies/requirements.txt). Create a Python virtual environment, install the requirements, make the environment accessible to QGIS, then install the plugin via the QGIS Plugin Manager.

### Linux

```bash
# Download and install Miniforge
wget https://github.com/conda-forge/miniforge/releases/download/23.3.1-1/Mambaforge-23.3.1-1-Linux-x86_64.sh
sh Mambaforge-23.3.1-1-Linux-x86_64.sh

# Create environment and install dependencies
mamba create -n groundtruther python=3.12
conda activate groundtruther
mamba install -c conda-forge ocl-icd-system
mamba install -c conda-forge qgis
mamba install -c conda-forge --file dependencies/requirements.txt
```

### Windows

GroundTruther has been tested on Windows with **Python 3.12** and **QGIS 4**. An [example conda environment](https://gist.github.com/epifanio/ed8eeb681e23a7cb7a27ce0568a04e44) is available as reference:

```bash
conda create --name groundtruther --file groundtruther.txt
```

### Key dependencies

| Package | Purpose |
|---|---|
| `opencv-python` | Video decoding and frame extraction |
| `scipy` | KD-tree for nearest-frame GPS lookup |
| `pandas` | Metadata CSV parsing |
| `pyqtgraph` | Image viewer |
| `matplotlib` | Plot generation for reports |
