# Installation — Linux

Two supported QGIS installation types: a **system/official QGIS package** plus a
companion virtualenv, or a **conda/mamba** environment. The first matches a
typical desktop QGIS; the second is the most portable.

## Option A — System QGIS 4 + companion venv (recommended for desktop use)

This is the setup GroundTruther is developed against (Ubuntu-family, QGIS 4.x
from the official QGIS repository).

1. **Install QGIS 4** from the [official QGIS repository](https://qgis.org/resources/installation-guide/)
   (the `qgis` / `python3-qgis` packages). Confirm it's Qt6:

    ```bash
    qgis --version          # e.g. QGIS 4.0.x 'Norrköping'
    ```

2. **Create a companion virtualenv that reuses QGIS's Python** and install the
   dependencies into it. QGIS uses the *system* Python, so create the venv with
   `--system-site-packages` so it sees the QGIS-provided `qgis`/`PyQt6`/`gdal`:

    ```bash
    cd groundtruther
    python3 -m venv --system-site-packages .venv
    # if your distro's python lacks pip/ensurepip:
    #   curl -fsSL https://bootstrap.pypa.io/get-pip.py | .venv/bin/python
    .venv/bin/python -m pip install -r dependencies/requirements.txt
    ```

    The plugin automatically adds this `.venv` to QGIS's `sys.path` at load time
    (a small bootstrap in `__init__.py`), so QGIS finds the dependencies no matter
    how it's launched.

3. **Install the plugin** (symlink for development):

    ```bash
    ln -s "$(pwd)" \
      "$HOME/.local/share/QGIS/QGIS4/profiles/default/python/plugins/groundtruther"
    ```
    Enable it in *Plugins → Manage and Install Plugins*.

!!! warning "Wayland: launch QGIS with the X11 (xcb) platform"
    On a Wayland session, Qt6 floating dock widgets can't be dragged/repositioned.
    Start QGIS through XWayland so GroundTruther's panels are movable:

    ```bash
    QT_QPA_PLATFORM=xcb qgis
    ```
    (Or add a `.desktop` override with `Exec=env QT_QPA_PLATFORM=xcb qgis %F`.)

## Option B — conda/mamba (portable)

```bash
mamba create -n groundtruther -c conda-forge python=3.12 qgis
conda activate groundtruther
mamba install -c conda-forge ocl-icd-system          # OpenCL ICD loader
mamba install -c conda-forge --file dependencies/requirements.txt
qgis
```

Install the plugin from the Plugin Manager (or symlink into
`~/.local/share/QGIS/QGIS4/profiles/default/python/plugins/`).

## Verify

Launch QGIS, enable the plugin, and open **GroundTruther → Settings**. If panels
open and the toolbar icons appear, you're set — head to the
[Tools](../tools/image-browser.md).
