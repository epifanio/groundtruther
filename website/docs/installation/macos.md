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

2. Install the dependencies **where the plugin looks for them**. GroundTruther's
   `__init__.py` adds exactly one directory to `sys.path` at load:

    ```
    <plugin folder>/.venv/lib/python<X.Y>/site-packages
    ```

    Nothing else is consulted — not `--user`, not your system Python. Installing
    anywhere else succeeds and leaves the plugin still reporting the packages as
    missing.

    ```bash
    QGIS_APP="/Applications/QGIS.app"
    PLUGIN="$HOME/Library/Application Support/QGIS/QGIS4/profiles/default/python/plugins/groundtruther"

    # The bundled interpreter cannot start without its own PYTHONHOME: run it
    # bare and it dies with "ModuleNotFoundError: No module named 'encodings'".
    export PYTHONHOME="$QGIS_APP/Contents/Frameworks"
    export PYTHONPATH="$(echo "$QGIS_APP"/Contents/Resources/python3.*/site-packages)"
    PY="$(ls "$QGIS_APP"/Contents/MacOS/python3.* | head -1)"

    # Ask it for its own version rather than hardcoding one — the directory name
    # must match the Python your QGIS actually runs, or nothing is found.
    VER="$("$PY" -c 'import sys; print(f"python{sys.version_info.major}.{sys.version_info.minor}")')"

    "$PY" -m pip install --upgrade \
      --target "$PLUGIN/.venv/lib/$VER/site-packages" \
      -r dependencies/requirements.txt
    ```

    Do **not** install `qgis`, `gdal` or `PyQt` via pip — they ship with the app.

    !!! tip "You need fewer packages than the list suggests"
        The macOS bundle already ships `numpy`, `pandas`, `pyarrow`, `scipy`,
        `matplotlib`, `requests`, `PyYAML`, `Jinja2` and `pydantic`, so on QGIS
        4.2.1 only **10** of the 20 are actually missing. You do not have to work
        out which: pip skips what is already importable, and the plugin's own
        dialog counts at runtime and names them. The figures on this site are
        examples, not promises — the number you see is the number for your build.

    !!! warning "Running that interpreter directly is not a way to test your install"
        `Contents/MacOS/python3.12` is signed with the hardened runtime and, unlike
        the QGIS app itself, is **not** allowed to load libraries signed by anyone
        else. Installing with it works, as above; *importing* with it does not.
        Run it by hand and every pip-installed package with compiled code fails
        with *"different Team IDs"* — even though the same packages load perfectly
        inside QGIS. Check your dependencies from the QGIS **Python Console**
        instead.

3. Symlink/copy the plugin into the profile plugins folder shown above and enable
   it in the Plugin Manager.

!!! danger "A QGIS upgrade can hide every dependency"
    That `python<X.Y>` directory is tied to one Python version. If a QGIS update
    moves from, say, 3.12 to 3.13, the plugin looks in `lib/python3.13/` and finds
    nothing — every package reads as missing although none was removed. Re-run the
    install above after a QGIS upgrade; deriving `VER` rather than typing it is
    what makes that a repeat of the same command.

!!! note "Which Python is my QGIS using?"
    In QGIS open *Plugins → Python Console* and run
    `import sys; print(sys.executable, sys.version)`. Install dependencies into
    **that** interpreter. (With the conda route this is automatic.)

## Verify

Launch QGIS, enable the plugin, open **GroundTruther → Settings**, and point it at
your data and the GRASS API endpoint/key. Try the
[sample dataset](https://zenodo.org/records/7995674) to confirm everything works.
