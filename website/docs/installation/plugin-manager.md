# Installing from the QGIS Plugin Manager

!!! warning "The Plugin Manager does not install GroundTruther's Python dependencies"
    Installing GroundTruther from *Plugins → Manage and Install Plugins* gives you
    the plugin's **code and icons, and nothing else**. The 20 Python packages it
    needs — pandas, pyarrow, pyqtgraph, numba, scikit-image and the rest — are
    **not** installed by that step, and QGIS has no mechanism that would install
    them. On a machine that does not already have them, GroundTruther **cannot
    open its panel at all**: it loads, shows one dialog naming what is missing,
    and does nothing further.

    This is why 0.4 is published as **experimental**. Installing the dependencies
    is a separate, manual step, described per platform on
    [Linux](linux.md) · [macOS](macos.md) · [Windows](windows.md).

## What the Plugin Manager install gives you, and what it does not

| Does the Plugin Manager install it? | |
|---|---|
| The plugin's Python files, icons and `metadata.txt` | **yes** |
| The 20 packages in `dependencies/requirements.txt` | **no** |
| A `.venv` beside the plugin, which is where the plugin looks for them | **no** |
| A way to run `pip` from inside QGIS to get them | **no** (see below) |

## Why it works this way

GroundTruther expects its dependencies in a virtualenv named `.venv` **beside the
plugin's own source**. At load time `__init__.py`'s `_bootstrap_venv()` appends
`<plugin>/.venv/lib/pythonX.Y/site-packages` to `sys.path`, so the packages are
importable inside QGIS however QGIS was launched. That function is a **no-op when
the venv is absent** — and a Plugin Manager install is exactly that case: the zip
is unpacked into your user profile, with no `.venv` and no build step.

Nor can the plugin create one for you. QGIS 4 runs on a **system Python**, where
[PEP 668](https://peps.python.org/pep-0668/) makes the interpreter
*externally managed* and `pip install` refuses to write into it. Several of the
packages (numba, pyarrow, opencv) are large, platform-specific binary wheels, so
bundling them into the plugin zip is not viable either.

So the supported install is: **get the dependencies into the Python your QGIS
uses, by one of the routes below, and then install the plugin.** Solving this
properly — a first-run installer, or making the heavy dependencies optional — is
deliberately left to a later release.

## What you see when the dependencies are missing

GroundTruther detects this before it tries to build anything, and says so rather
than failing with a Python traceback. Three things happen.

**1. One dialog**, titled **“GroundTruther — dependencies missing”**, which on a
machine with none of the packages installed reads:

> **GroundTruther cannot start: 15 of the 20 Python packages it needs are not installed.**
>
> The QGIS Plugin Manager does not install a plugin's Python dependencies, and
> QGIS 4 runs on a system Python that normally refuses `pip install`. Until these
> are present, GroundTruther cannot open its panel at all:
>
> `numpy, pandas, pyarrow, scikit-image, scipy, pyqtgraph, matplotlib, plotnine, pyproj, simplekml, requests, geojson, PyYAML, Jinja2, numba`
>
> 5 more are missing. They do not stop the plugin loading, but each one disables a feature:
>
> `opencv-python-headless, av, PyOpenGL, pydantic, starlette`
>
> How to install them: <https://epifanio.github.io/groundtruther/installation/linux/>
>
> The same list is in *View → Panels → Log Messages*, under *GroundTruther*.

That link is chosen from the operating system you are on — `installation/linux/`,
`installation/macos/` or `installation/windows/` — because the route genuinely
differs between them. On a platform with no page of its own it falls back to the
[installation index](index.md).

The counts and the names are **computed on your machine**, not fixed text, so what
you see depends on what you already have. They differ by platform: the macOS QGIS
bundle ships `pandas` but not `pyqtgraph`, so a macOS user typically sees a
shorter list than the one above.

Behind the dialog's **Show Details** button is one line per missing package, with
its import name and what it costs:

```text
REQUIRED  pyqtgraph (import pyqtgraph) — the image viewer and every plot
optional  av (import av) — preferred video decode backend (deinterlaces interlaced sources)
```

**2. A menu entry**, *Plugins → GroundTruther → “GroundTruther (dependencies
missing)”*. The dialog is shown once per QGIS session; this entry brings it back.
There is deliberately no toolbar button and no dock, because neither could be
constructed.

**3. The full list in the log**, under *View → Panels → Log Messages →
GroundTruther*: a headline, one line per missing package, the line

```text
  no .venv beside the plugin, so no dependencies were added to sys.path — this is what a Plugin Manager install looks like
```

and the install-docs URL. The log is the durable record — the dialog is dismissed,
this is not.

## Which packages stop the plugin, and which only disable a feature

Of the 20 requirements, **15 are reached by an unguarded module-level import** on
the way to the main panel, so the plugin cannot start without them. The remaining
5 are imported lazily or guarded, so they cost only their own feature.

| Package | Import | Powers | Missing it |
|---|---|---|---|
| `numpy` | `numpy` | all numeric work | blocks load |
| `pandas` | `pandas` | image, video and annotation tables | blocks load |
| `pyarrow` | `pyarrow` | reading the Parquet metadata tables | blocks load |
| `scikit-image` | `skimage` | reading seafloor imagery | blocks load |
| `scipy` | `scipy` | nearest-image lookup (KDTree) and roughness | blocks load |
| `pyqtgraph` | `pyqtgraph` | the image viewer and every plot | blocks load |
| `matplotlib` | `matplotlib` | query-builder figures | blocks load |
| `plotnine` | `plotnine` | query-builder statistical plots | blocks load |
| `pyproj` | `pyproj` | coordinate transforms for footprints | blocks load |
| `simplekml` | `simplekml` | KML export | blocks load |
| `requests` | `requests` | every call to the GRASS/FastGIS service | blocks load |
| `geojson` | `geojson` | GeoJSON output from the query builder | blocks load |
| `PyYAML` | `yaml` | reading and writing `config/config.yaml` | blocks load |
| `Jinja2` | `jinja2` | KML templating | blocks load |
| `numba` | `numba` | the point-in-polygon JIT used by the query builder | blocks load |
| `opencv-python-headless` | `cv2` | video decode fallback and the seabed ribbon | disables the feature |
| `av` | `av` | preferred video decode backend (deinterlaces interlaced sources) | disables the feature |
| `PyOpenGL` | `OpenGL` | 3-D views in the query builder | disables the feature |
| `pydantic` | `pydantic` | validating the configuration | disables the feature |
| `starlette` | `starlette` | declared in `requirements.txt`; nothing imports it at 0.4 | nothing |

Note that the pip name and the import name differ for five of them — installing
`opencv-python-headless` is what makes `import cv2` work.

!!! warning "Never `pip install` qgis, gdal/osgeo or PyQt"
    Those ship **with** QGIS. Installing them over the top breaks your QGIS. Use
    `--system-site-packages` (venv) or conda-forge so the QGIS-provided ones are
    reused.

## The supported routes

The repository ships a helper script for each platform. All of them do the same
thing in the end: put the 20 packages where the Python your QGIS runs on can
import them.

| Platform | Script | What it does |
|---|---|---|
| Linux / WSL2 | [`setup_wsl.sh`](https://github.com/epifanio/groundtruther/blob/master/setup_wsl.sh) | Creates or updates the conda-forge environment `groundtruther` from `environment.yml` when `mamba` is on `PATH`. With `--venv` it instead makes `.venv` beside the plugin source, with `--system-site-packages`, and `pip install -r dependencies/requirements.txt` into it — the venv `_bootstrap_venv()` looks for. |
| Windows (QGIS installer / OSGeo4W) | [`setup_windows.ps1`](https://github.com/epifanio/groundtruther/blob/master/setup_windows.ps1) | Finds the `python.exe` inside your QGIS or OSGeo4W installation and `pip install -r dependencies\requirements.txt` into it. Needs an elevated PowerShell if QGIS is under `C:\Program Files`. Pass `-QgisPython <path>` if auto-detection picks the wrong one. |
| Windows (conda) | [`setup_mamba.bat`](https://github.com/epifanio/groundtruther/blob/master/setup_mamba.bat) | Creates or updates the `groundtruther` conda-forge environment from `environment.yml`, which contains QGIS **and** the dependencies. Requires Miniforge. |
| macOS | *(no script)* | Use the conda/mamba route, or install into the app bundle's own Python — see [macOS](macos.md). |

Both Windows scripts, and `README_WINDOWS.md`, print the plugin folder under
`QGIS4`
(`%APPDATA%\QGIS\QGIS4\profiles\default\python\plugins\groundtruther`),
matching `qgisMinimumVersion=4.0`. They said `QGIS3` until 2026-10-24, which sent
people to a directory QGIS 4 never reads; if you are working from a release
earlier than that, use the path above rather than the one the script prints.

Running the scripts means having a copy of the repository, because they read
`dependencies/requirements.txt` and `environment.yml`. You can use that same copy
as the plugin — symlinked into your profile, which is also the development setup
— instead of installing from the Plugin Manager at all.

## Checking it worked

Install the dependencies first, then the plugin, then restart QGIS. If the
GroundTruther toolbar and panel appear, the dependencies are importable. If the
“dependencies missing” dialog appears instead, the packages went into a Python
your QGIS is not using — open *Plugins → Python Console* and run

```python
import sys; print(sys.executable, sys.version)
```

to see which interpreter QGIS actually runs, and install into that one.

Continue to your platform: **[Linux](linux.md)** · **[macOS](macos.md)** ·
**[Windows](windows.md)**.
