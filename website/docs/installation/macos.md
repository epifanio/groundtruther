# Installation — macOS

On macOS the **conda/mamba** route is recommended: it installs QGIS 4 and all
dependencies into one environment, side-stepping the question of which Python a
given QGIS build uses. The official QGIS app bundle is supported as an
alternative.

## Option A — conda/mamba (recommended)

Install [Miniforge](https://github.com/conda-forge/miniforge) (works on both
Apple Silicon and Intel), then:

```bash
mamba create -n groundtruther -c conda-forge python=3.12 qgis
conda activate groundtruther
mamba install -c conda-forge --file dependencies/requirements.txt
qgis            # launches the conda QGIS
```

Install the plugin from the **Plugin Manager**, or symlink the source into the
profile plugins folder:

```
~/Library/Application Support/QGIS/QGIS4/profiles/default/python/plugins/groundtruther
```

## Option B — official QGIS.app + its bundled Python

1. Install **QGIS 4** from the official [macOS installer](https://qgis.org/download/)
   (the all-in-one signed package).
2. Install the dependencies into the **QGIS app's own Python** (not your system
   Python). The interpreter lives inside the bundle, e.g.:

    ```bash
    QGIS_PY="/Applications/QGIS.app/Contents/MacOS/bin/python3"
    "$QGIS_PY" -m pip install --user -r dependencies/requirements.txt
    ```

    Adjust the path to match your QGIS version. Do **not** install `qgis`,
    `gdal`, or `PyQt` via pip — they ship with the app.

3. Symlink/copy the plugin into the profile plugins folder shown above and enable
   it in the Plugin Manager.

!!! note "Which Python is my QGIS using?"
    In QGIS open *Plugins → Python Console* and run
    `import sys; print(sys.executable, sys.version)`. Install dependencies into
    **that** interpreter. (With the conda route this is automatic.)

## Verify

Launch QGIS, enable the plugin, open **GroundTruther → Settings**, and point it at
your data and the GRASS API endpoint/key. Try the
[sample dataset](https://zenodo.org/records/7995674) to confirm everything works.
