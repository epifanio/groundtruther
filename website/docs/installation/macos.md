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
    QGIS_PY="/Applications/QGIS.app/Contents/MacOS/python3.12"
    "$QGIS_PY" -m pip install --user -r dependencies/requirements.txt
    ```

    Adjust the path and the version to match your QGIS — in the 4.2.1 bundle the
    interpreter is `Contents/MacOS/python3.12` and there is no `MacOS/bin/`
    directory. Do **not** install `qgis`, `gdal`, or `PyQt` via pip — they ship
    with the app.

    !!! warning "Running that interpreter directly is not a way to test your install"
        `Contents/MacOS/python3.12` is signed with the hardened runtime and, unlike
        the QGIS app itself, is **not** allowed to load libraries signed by anyone
        else. Run it by hand and every pip-installed package with compiled code
        fails with *"different Team IDs"* — even though the same packages load
        perfectly inside QGIS. Check your dependencies from the QGIS **Python
        Console** instead.

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
