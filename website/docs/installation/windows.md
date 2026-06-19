# Installation — Windows

GroundTruther is tested on Windows with **Python 3.12** and **QGIS 4**. Two
supported QGIS installation types: the **OSGeo4W** distribution (install deps via
the OSGeo4W shell) or a **conda/mamba** environment.

## Option A — OSGeo4W QGIS 4

1. Install QGIS 4 with the [**OSGeo4W network installer**](https://qgis.org/download/)
   (choose QGIS 4 / the *qgis* package). OSGeo4W gives you a dedicated shell that
   targets QGIS's own Python.
2. Open the **OSGeo4W Shell** (Start menu) and install the dependencies into
   QGIS's Python:

    ```bat
    python -m pip install -r dependencies\requirements.txt
    ```

    `numba` needs an LLVM toolchain on Windows; conda-forge wheels (Option B)
    avoid the build. Never `pip install` `qgis`, `gdal`, or `PyQt`.

3. Copy/clone the plugin into the profile plugins folder (folder name must be
   `groundtruther`):

    ```
    %APPDATA%\QGIS\QGIS4\profiles\default\python\plugins\groundtruther
    ```
    Enable it in *Plugins → Manage and Install Plugins*.

The repository also ships helper scripts — `setup_windows.ps1` / `setup_mamba.bat`
— and a [worked Windows guide](https://github.com/epifanio/groundtruther/blob/master/README_WINDOWS.md).

## Option B — conda/mamba (recommended)

Install [Miniforge](https://github.com/conda-forge/miniforge), then from the
**Miniforge Prompt**:

```bat
mamba create -n groundtruther -c conda-forge python=3.12 qgis
conda activate groundtruther
mamba install -c conda-forge --file dependencies\requirements.txt
qgis
```

A reference environment file is available as a
[gist](https://gist.github.com/epifanio/ed8eeb681e23a7cb7a27ce0568a04e44):

```bat
conda create --name groundtruther --file groundtruther.txt
```

Install the plugin from the Plugin Manager (or copy the source into the profile
plugins folder above).

## Verify

Launch QGIS, enable the plugin, open **GroundTruther → Settings**, and point it at
your data + the GRASS API endpoint/key. The
[sample dataset](https://zenodo.org/records/7995674) is a good first test.
