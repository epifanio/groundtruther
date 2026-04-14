# GroundTruther – Windows Installation Guide

Two installation paths are supported.  
**Mamba (recommended)** gives you a fully isolated environment with no admin rights required.  
**pip into QGIS Python** is simpler if you already have QGIS installed and just need to add packages.

---

## Option A – Mamba / conda-forge (recommended)

### Why mamba?

| | pip into QGIS Python | Mamba |
|---|---|---|
| Admin rights needed | Yes (QGIS in Program Files) | No |
| Risk to system QGIS | Possible | None – isolated env |
| Binary deps (scipy, GDAL…) | Pre-built wheels, sometimes fragile | conda-forge handles everything |
| Works on Windows + Linux | Separate scripts | Same `environment.yml` |

### 1 – Install Miniforge (once)

Download **Miniforge3** for Windows from:  
<https://github.com/conda-forge/miniforge/releases/latest>

Run the installer.  When asked, choose **"Install for just me"** (no admin needed).  
Accept the default install path (`%LOCALAPPDATA%\miniforge3`).

> Anaconda or Miniconda also work, but you must add the `conda-forge` channel manually.

### 2 – Create the environment

Open a **Miniforge Prompt** (Start → Miniforge Prompt) and run:

```bat
cd path\to\repo
setup_mamba.bat
```

The script will:
1. Check that `mamba` is available.
2. Create (or update) the `groundtruther` conda environment from `environment.yml`.
3. Print the launch and plugin deployment commands.

To run it manually instead:

```bat
mamba env create --file environment.yml
```

### 3 – Deploy the plugin

Create a symbolic link so the repo **is** the installed plugin (run this in an **Administrator** command prompt):

```bat
mklink /D "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\groundtruther" "C:\path\to\repo\groundtruther"
```

Or simply copy the `groundtruther` folder to:

```
C:\Users\<you>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\
```

### 4 – Launch QGIS

From a Miniforge Prompt:

```bat
mamba activate groundtruther
qgis
```

### 5 – Enable the plugin

In QGIS: **Plugins → Manage and Install Plugins** → search for *GroundTruther* → tick the checkbox.

### Updating after a `git pull`

```bat
mamba env update --name groundtruther --file environment.yml --prune
```

---

## Option B – pip into QGIS Python

Use this if you already have the QGIS standalone installer and prefer not to manage a separate conda environment.

### 1 – Install QGIS

Download and run the **QGIS Standalone Installer** from <https://qgis.org>.  
The LTR (Long Term Release) version is recommended.

### 2 – Deploy the plugin

Create a symbolic link (run as **Administrator** in cmd):

```bat
mklink /D "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\groundtruther" "C:\path\to\repo\groundtruther"
```

Or copy the `groundtruther` folder to:

```
C:\Users\<you>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\
```

### 3 – Install Python dependencies

Right-click `setup_windows.bat` → **Run as administrator** and follow the prompts.

The script auto-detects the QGIS bundled Python (searches `C:\Program Files\QGIS*` and `C:\OSGeo4W`) and runs:

```
pip install -r dependencies\requirements.txt
```

If auto-detection fails, supply the path explicitly from a PowerShell window:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_windows.ps1 -QgisPython "C:\Program Files\QGIS 3.34\apps\Python312\python.exe"
```

Common Python paths by QGIS version:

| QGIS version | Python path |
|---|---|
| 3.34 LTR | `C:\Program Files\QGIS 3.34\apps\Python312\python.exe` |
| 3.38 | `C:\Program Files\QGIS 3.38\apps\Python312\python.exe` |
| OSGeo4W | `C:\OSGeo4W\apps\Python312\python.exe` |

#### Alternative: OSGeo4W Shell

Open **OSGeo4W Shell** (installed alongside QGIS, available in the Start menu) and run:

```bash
pip install -r C:\path\to\repo\groundtruther\dependencies\requirements.txt
```

The shell already has the correct Python on `PATH` so no path hunting is needed.

### 4 – Enable the plugin

In QGIS: **Plugins → Manage and Install Plugins** → search for *GroundTruther* → tick the checkbox.

### Re-run after a QGIS upgrade

If QGIS upgrades to a new Python version (e.g. 3.12 → 3.13), run `setup_windows.bat` again to reinstall packages into the new interpreter.

---

## Notes applicable to both options

### `pydantic` must be v1

The plugin configuration code uses `pydantic.error_wrappers`, which was removed in pydantic v2.  
The `requirements.txt` and `environment.yml` both pin `pydantic>=1.9,<2`.

### Never pip-install `gdal` / `osgeo`

QGIS ships its own GDAL build.  Installing a second GDAL via pip or conda outside the QGIS environment corrupts the setup.  Both setup files intentionally omit `gdal`/`osgeo`.

### `numba` is optional

`numba` provides JIT acceleration but requires an LLVM toolchain when installed via pip.  
It is commented out in `dependencies/requirements.txt`.  
With the mamba approach it resolves cleanly — uncomment the `numba` line in `environment.yml` if you need it.

### First-run configuration

On the first launch the plugin will open the **Settings** dialog automatically.  
Fill in the paths to your HabCam image directory, metadata parquet file, annotation CSV, and GRASS API endpoint, then click **Save**.

---

## Repository layout (quick reference)

```
groundtruther/
├── environment.yml          # mamba/conda-forge environment (Windows + Linux)
├── setup_mamba.bat          # Windows: create/update mamba environment
├── setup_windows.bat        # Windows: install deps into existing QGIS Python
├── setup_windows.ps1        # PowerShell script called by setup_windows.bat
├── setup_wsl.sh             # Linux/WSL2: mamba (preferred) or pip venv
└── dependencies/
    └── requirements.txt     # pip requirements (used by setup_windows.ps1)
```
