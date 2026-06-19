# Installation

GroundTruther is a **QGIS 4 / Qt6** plugin — it runs *inside* QGIS, not on its
own. Installing it has three parts:

1. **Install QGIS 4** (the right *installation type* matters — see per-OS pages).
2. **Make the plugin's Python dependencies importable by QGIS's Python.**
3. **Install the plugin itself** (QGIS Plugin Manager, or a symlink for development).

!!! info "The key idea: deps must reach *QGIS's* Python"
    QGIS ships and uses its **own** Python interpreter. The plugin's extra
    packages (pandas, opencv, pyqtgraph, numba, …) must be visible to *that*
    interpreter. Do **not** install them into an unrelated system Python.
    The two reliable strategies are:

    - **One conda/mamba environment** that contains *both* QGIS and the
      dependencies (cleanest, identical across OSes — recommended).
    - **An OS-native QGIS** (system package / official installer) plus the
      dependencies installed into that QGIS's Python (per-OS notes below).

## Requirements

- **QGIS ≥ 4.0** (Qt6 / PyQt6).
- Python **3.12+** (whatever your QGIS bundles).
- The packages in [`dependencies/requirements.txt`](https://github.com/epifanio/groundtruther/blob/master/dependencies/requirements.txt):
  `numpy, pandas, pyarrow, scikit-image, scipy, opencv-python-headless,
  pyqtgraph, PyOpenGL, matplotlib, plotnine, pyproj, simplekml, requests, PyYAML,
  pydantic, starlette, Jinja2, geojson, numba`.

!!! warning "Never pip-install these"
    `qgis`, `gdal`/`osgeo`, and `PyQt` ship **with** QGIS — installing them via
    pip will break your QGIS. Use `--system-site-packages` (venv) or conda so the
    QGIS-provided ones are reused.

## Recommended: one conda/mamba environment (any OS)

```bash
# Miniforge provides conda + mamba on Linux/macOS/Windows
mamba create -n groundtruther -c conda-forge python=3.12 qgis
conda activate groundtruther
mamba install -c conda-forge --file dependencies/requirements.txt
qgis            # launch QGIS from this env, then install the plugin
```

This gives QGIS and all dependencies in one place, so everything "just works".
Then install the plugin (below).

## Install the plugin

=== "From the QGIS Plugin Manager"
    *Plugins → Manage and Install Plugins → search "GroundTruther" → Install.*
    (Marked experimental — enable *Show experimental plugins* in settings.)

=== "From source (development)"
    Symlink the repository into your QGIS profile's plugins folder; the folder
    **must** be named `groundtruther`:

    ```bash
    git clone https://github.com/epifanio/groundtruther.git
    ln -s "$(pwd)/groundtruther" \
      "$HOME/.local/share/QGIS/QGIS4/profiles/default/python/plugins/groundtruther"
    ```
    Then enable it in the Plugin Manager. (Windows/macOS profile paths differ —
    see those pages.)

## Configure

Open **GroundTruther → Settings** and point it at your data (HabCam images +
metadata, MBES soundings, optional video + GPS log, export folder) and the
**GRASS API endpoint + key** for the acoustic toolbox. Settings persist to
`config/config.yaml`. A ready-to-use [sample dataset](https://zenodo.org/records/7995674)
is available.

Continue to your platform: **[Linux](linux.md)** · **[macOS](macos.md)** ·
**[Windows](windows.md)**.
