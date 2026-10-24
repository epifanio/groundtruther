# Install GroundTruther on macOS QGIS 4.2.1 — what actually works

**The owner's brief** (2026-10-24, side session `mac-install-test`, beside the queue): install
GroundTruther on this Mac from the release zip and find out what actually works. A verification
session: it produces knowledge, not a feature.

## Status

**2026-10-24 — ◐ done, and it found two blockers nobody knew about. §5 and §6 were corrected later
the same day.** The 0.4 code does load on a real QGIS 4 on macOS, and almost every dependency works.
But **every pandas datetime operation segfaults QGIS 4.2.1 on macOS** — `pd.to_datetime(["..."])` is
enough — which kills the plugin's *mandatory* startup path, reading `HabCam.imagemetadata`. The
`.venv` cannot fix it: `import qgis.core` imports pandas and pyarrow before any plugin code runs.

Two corrections, both made after the owner tried it in the GUI:

- §5 first blamed a pandas/pyarrow pair and a `timestamp[us]` column. The macOS crash report shows
  the fault is inside **pandas' own datetime C extension**; pyarrow is only the caller. The row was
  re-scoped and renamed `seq-C2-parquet-no-pandas`, and it now covers `gt/video_manager.py:170` as
  well as `gt/image_manager.py:70`.
- §6 assumed the reader would switch profile. The owner opened QGIS, got `default`, and saw no
  GroundTruther at all. §6.0 now leads with the launch command, and §6.2 is a debugging guide.

**WP-2 is now built** — `seq-C2-parquet-no-pandas`, **PR #73**, open for the owner; both call
sites are fixed and verified in QGIS's own interpreter, and §5 gained that session's three further
measurements below. The other follow-up is `seq-U2-macos-profile-docs`; `publish-0-4` WP-3/WP-4
gained facts they were going to guess at. The GUI half is the owner's: §6. Nothing in *this* session
touched plugin code.

Conventions: `PLANNING/WORKFLOW.md` §5.2 (rules 0–6).

## 1. What was actually run, and where

Everything below was measured on this Mac on 2026-10-24, from the release zip of a throwaway tag
built by `scripts/make-release-zip.sh` (the only sanctioned build path, `seq-P2-release-zip`).

| Thing | Value |
|---|---|
| QGIS | **4.2.1 "Belém do Pará"**, `/Applications/QGIS-final-4_2_1.app`, an **arm64** vcpkg build |
| its Python | 3.12.11, `Contents/MacOS/python3.12`; site-packages in `Contents/Resources/python3.12/site-packages` |
| venv Python | homebrew `python3.12` = 3.12.15, arm64 |
| profiles root | **`~/Library/Application Support/QGIS/QGIS4/profiles/`** |
| profile with `.venv` | `gt-mac-test` — plugin + a full `.venv` |
| profile without | `gt-mac-novenv` — plugin only, i.e. **exactly what the Plugin Manager gives you** |
| dataset | `~/dev/groundtruther_test_dataset` (Zenodo 7995674), read-only, never written to |

Two facts the brief had wrong, worth correcting because they change how the next session sets up:

- **The macOS profiles root is `QGIS4/profiles/`, not `QGIS3/profiles/`.** It mirrors the Linux
  `~/.local/share/QGIS/QGIS4/profiles/` that `CLAUDE.md` documents.
- **QGIS had already been launched on this Mac**: `QGIS4/profiles/default` dates from 2026-08-17 and
  carries a populated `qgis.org/QGIS4.ini`. The two profiles above are new and `default` was not
  touched, so the clean-profile property still holds — but "never launched" was not true.

## 2. The known blocker, confirmed — and it is quieter than expected

A Plugin Manager install has no `.venv`, so `_bootstrap_venv()` is a silent no-op. What happens then,
measured in `gt-mac-novenv`:

- `import groundtruther` **succeeds**. The bootstrap fails silently by design.
- `qgis.utils.loadPlugin("groundtruther")` **returns `True`** — it only does `__import__`, which works.
- `qgis.utils.startPlugin("groundtruther")` returns `False`; that is where `classFactory` runs:

```text
File ".../groundtruther/__init__.py", line 61, in classFactory
  from .groundtruther import GroundTruther
File ".../groundtruther/groundtruther.py", line 60, in <module>
  from .groundtruther_dockwidget import GroundTrutherDockWidget
File ".../groundtruther/groundtruther_dockwidget.py", line 34, in <module>
  import pyqtgraph as pg
ModuleNotFoundError: No module named 'pyqtgraph'
```

- **Zero log messages tagged `GroundTruther`.** Nothing in the plugin's own log tag says what went
  wrong; the user gets QGIS's generic plugin-error dialog.

Three things here that `publish-0-4` WP-3/WP-4 were going to have to guess:

1. **The first missing module is `pyqtgraph`**, not numpy or pandas, and it is reached through
   `groundtruther_dockwidget.py:34`. A deps check that reports "pandas missing" is testing the wrong
   thing; on macOS QGIS ships pandas and does *not* ship pyqtgraph.
2. **`loadPlugin` returning `True` is not a load.** A WP-4 message that fires from `loadPlugin`'s
   failure path will never fire. The failure is in `startPlugin` → `classFactory`.
3. The import chain dies at the **first** missing module, so a user is told about one of them at a
   time. WP-3's job of reporting *all* missing modules at once is the right design.

## 3. Do pip wheels work inside QGIS on macOS? Yes — but the obvious way to test says no

This is the question the session was created to answer, and the first answer was wrong.

macOS **library validation**: a process with the hardened runtime may only `dlopen` libraries signed
by its own Team ID, unless it carries
`com.apple.security.cs.disable-library-validation`. Every pip wheel's `.so` is ad-hoc signed with no
Team ID. Measured with `codesign -d --entitlements`:

| Binary | Hardened runtime | `disable-library-validation` |
|---|---|---|
| `QGIS-final-4_2_1` (the app) | yes | **yes** |
| `python3.12` (the helper) | yes | no |
| `qgis_process`, `crssync` | yes | no |

So **the app can load pip wheels and the bundled `python3.12` cannot.**

*(Corrected 2026-10-24 by `seq-C2-parquet-no-pandas`: this first said `CLAUDE.md`'s headless recipe
runs `python3.12`. It does not — that recipe is Linux-only, `.venv/bin/python` with
`/usr/share/qgis/python` and `python3.14` (`CLAUDE.md` Testing). The hazard is real but the gap is
different: **there is no macOS recipe at all**, so a session improvising one reaches for
`Contents/MacOS/python3.12`, which is the obvious choice and the wrong one.)*

Under that interpreter *every* compiled dependency fails with

```text
ImportError: dlopen(.../cv2/cv2.abi3.so): ... (code signature in <...> not valid for use in
process: mapping process and mapped file (non-platform) have different Team IDs)
```

Neither `codesign --remove-signature` nor an ad-hoc re-sign helps (both were tried: unsigned gives
"missing code signature", ad-hoc gives the same Team ID error). **This failure is an artifact of the
harness, not of the plugin** — and it would be very easy for a future session to report it as a
GroundTruther bug.

**The harness that is faithful.** `--code` does not work: QGIS starts under
`QT_QPA_PLATFORM=offscreen` and populates the profile, but never reaches the script, which is the
warning `CLAUDE.md` already gives. What works is a copy of QGIS's interpreter, ad-hoc signed with the
same entitlement the app carries, placed so its `@rpath` resolves:

```bash
A=/Applications/QGIS-final-4_2_1.app
H=/tmp/gt-harness; mkdir -p "$H/MacOS"
ln -s "$A/Contents/Frameworks" "$H/Frameworks"; ln -s "$A/Contents/Resources" "$H/Resources"
cp "$A/Contents/MacOS/python3.12" "$H/MacOS/py312"
cat > /tmp/ent.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>com.apple.security.cs.disable-library-validation</key><true/>
</dict></plist>
EOF
codesign --force --sign - --options runtime --entitlements /tmp/ent.plist "$H/MacOS/py312"
export PYTHONHOME="$A/Contents/Frameworks" \
       PYTHONPATH="$A/Contents/Resources/python3.12/site-packages" \
       PROJ_DATA="$A/Contents/Resources/qgis/proj" GDAL_DATA="$A/Contents/Resources/qgis/gdal" \
       QT_QPA_PLATFORM=offscreen \
       QT_QPA_PLATFORM_PLUGIN_PATH="$A/Contents/PlugIns/platforms" QT_PLUGIN_PATH="$A/Contents/PlugIns"
"$H/MacOS/py312" your_probe.py
```

It reproduces the app's *signing* regime exactly, and it is not the GUI: it has no main window and no
`iface`, so it cannot stand in for §6.

## 4. Every dependency, measured in that harness, venv appended as the plugin does

`.venv` built with homebrew `python3.12 -m venv --system-site-packages` and
`dependencies/requirements.txt`. Homebrew-built arm64 wheels **do** load inside QGIS's 3.12 — the
crux question of the brief, answered yes. 23 of 24 import, and the compiled paths were exercised, not
just imported: `numpy` matmul, `scipy.ndimage.gaussian_filter`, `skimage.filters.sobel`,
`cv2.resize`, `av.codecs_available` (536), `numba.njit`, `pyarrow.table`, `statsmodels` OLS, and a
live `pyqtgraph.PlotWidget()` all succeeded.

Because `_bootstrap_venv()` **appends**, QGIS's own copy wins wherever it ships one:

| From QGIS (venv copy ignored) | From the venv |
|---|---|
| numpy 2.5.0, pandas 3.0.3, pyarrow 23.0.1, scipy 1.18.0, matplotlib 3.11.0, pyproj 3.7.2, requests 2.34.2, PyYAML 6.0.3, Jinja2 3.1.6, Pillow 12.2.0 | skimage 0.26.0, cv2 5.0.0, av 19.0.2, pyqtgraph 0.14.0, PyOpenGL 3.1.10, plotnine 0.15.8, simplekml 1.3.2, geojson 3.3.0, starlette 1.9.0, numba 0.68.0, llvmlite 0.50.0, tifffile 2026.10.15, statsmodels 0.15.0 |

Three things in that table are worth someone's attention:

- **`opencv-python-headless` resolved to 5.0.0.** `requirements.txt` pins only `>=4.8`, so pip now
  gives a **major version** the code has never been run against.
- **cv2 and av ship rival FFmpeg copies.** Importing both raises, every time:
  `objc[…]: Class AVFFrameReceiver is implemented in both .../cv2/.dylibs/libavdevice.61.3.100.dylib
  and .../av/.dylibs/libavdevice.63.1.102.dylib … This may cause spurious casting failures and
  mysterious crashes.` The video player imports both by design (PyAV preferred, OpenCV fallback), so
  this is live in the one feature that uses them.
- **`import pydantic` fails, and GroundTruther is not the reason.** Stock QGIS 4.2.1 on macOS ships
  `pydantic` 2.13.4 against `pydantic_core` 2.47.0, and that pydantic pins core 2.46.4:
  `SystemError: The installed pydantic-core version (2.47.0) is incompatible with the current
  pydantic version, which requires 2.46.4`. It reproduces with no venv and no plugin on `sys.path`.
  `groundtruther.config_model` therefore **cannot import** on this machine. `groundtruther.configure`
  still imports (its v1→v2 fallback holds), and `gt/config_check.py` is pydantic-free and works — so
  per-key validation survives and only the pydantic schema is lost.

## 5. The blocker: **every pandas datetime operation** segfaults QGIS

**Corrected 2026-10-24, after the owner found the plugin did not appear in the Plugin Manager.**
This section first said the fault was a pandas/pyarrow pair that could not convert a `timestamp[us]`
column. That was too narrow, and it would have sent `seq-C2` after the wrong fix. Reading the
macOS crash report named the real frame, and pyarrow turns out to be **innocent**.

`pandas`' datetime C extension is broken in QGIS 4.2.1 on macOS. Every one of these SIGSEGVs
(exit 139, no exception, no log line), with no GroundTruther, no venv and **no pyarrow**:

```python
import pandas as pd, numpy as np
pd.to_datetime(["2015-01-01"])                                   # SIGSEGV
pd.Series(np.array(["2015-01-01"], dtype="datetime64[ns]"))      # SIGSEGV
pd.Series(np.array(["2015-01-01"], dtype="datetime64[us]"))      # SIGSEGV
from pandas._libs.tslibs import np_datetime
np_datetime.get_supported_dtype(np.dtype("datetime64[ns]"))      # SIGSEGV
```

The crash report (`~/Library/Logs/DiagnosticReports/*.ips`) gives the frame:

```text
EXC_BAD_ACCESS (SIGSEGV), KERN_INVALID_ADDRESS at 0x0000000000000020
  pandas_datetime.cpython-312-darwin.so   get_datetime_metadata_from_dtype
  np_datetime.cpython-312-darwin.so       pandas._libs.tslibs.np_datetime.get_supported_dtype
  …
  lib.cpython-312-darwin.so               pyarrow.lib._PandasAPIShim.series
  lib.cpython-312-darwin.so               pyarrow.lib.ChunkedArray._to_pandas
```

pyarrow appears only as the *caller* in the parquet case. The null-dereference is inside pandas'
own `get_datetime_metadata_from_dtype`, reading a dtype it cannot interpret — the signature of a
**pandas ↔ numpy C-API ABI mismatch** in QGIS's bundle (it ships pandas 3.0.3 and numpy 2.5.0).
homebrew 3.12 with pandas 3.1.0 / numpy + pyarrow 26.0.0 is fine, so it is QGIS's build, not ours,
and it is **macOS-only as far as this session measured** — the project works on Linux.

### What it costs the plugin

Two call sites, both in `gt/`, and both on paths a user reaches immediately:

| Call site | What breaks |
|---|---|
| `gt/image_manager.py:70` — `pd.read_parquet(parquet_path)` | `HabCam.imagemetadata` is one of the two config keys that *block startup*, and `test_imagemetadata.pq` has a `timestamp[us]` column (`index`). Reading it kills QGIS. |
| `gt/video_manager.py:170` — `pd.to_datetime(...)` in `load_video_metadata_survey`, and `:218` `.dt.total_seconds()` downstream | `pd.to_datetime` is proven to segfault, so this call site cannot run on macOS at all. (Not executed here for want of a survey CSV — the crash is proven on the function, not on this caller.) |

Nothing in `mixins/` or `pygui/` touches datetimes directly, so the blast radius is those two files.
Avoiding `to_pandas()` is **not sufficient**: any code that builds or parses a datetime column dies.

> **Three more measurements, `seq-C2-parquet-no-pandas` 2026-10-24** (the row that fixed both call
> sites, PR #73). They did not change the diagnosis above; they changed what a fix is allowed to do.
>
> 1. **`pd.Series(np.array([], dtype="datetime64[us]"))` — an *empty* array — is SIGSEGV.** So the
>    breakage **cannot be probed for at runtime: the probe is the crash.** Any future "detect the
>    broken build and branch" idea is dead on arrival, which is why the fix is unconditional on
>    every platform rather than macOS-only.
> 2. **`pd.ArrowDtype` is a trap that looks like a win.** `pd.Series(arrow, dtype=pd.ArrowDtype(
>    pa.timestamp("us")))` *stores* fine and `.dt.year` works — but reading one element back builds
>    a `pd.Timestamp` and dies. A probe that only constructs and aggregates will wrongly call it
>    safe. Arrow `duration` columns are SIGSEGV too; `date32`, `date64` and `time64` are fine.
> 3. **Inference is the enemy, not any single call.** pandas infers a `datetime64` from an
>    *object-dtype* array of datetimes in the `DataFrame` and `Series` constructors and in
>    `set_index`, so building the values safely is not enough — the dtype must be spelled out at
>    every hand-off. One edge therefore survives: object datetimes are inert in a *column*, but
>    pandas re-infers them leaving an *index*, so `reset_index()` and `pd.concat()` on such a frame
>    still die, while `copy`, `sort_index`, `iloc`, `at`, `to_csv` and `df.index[i]` are fine. The
>    plugin calls neither — there is no `reset_index` and no `pd.concat` anywhere in `mixins/`,
>    `gt/` or `pygui/`.
>
> The helpers and the full measurement table now live in **`gt/pandas_safe.py`** (PR #73), which is
> where a decision record on this would point.

### Why the `.venv` cannot rescue it

Prepending instead of appending gets the venv's working pandas, and the real file then reads fine —
but only in a process that has not started QGIS. Measured:

```text
after initQgis: pandas already imported? True | pyarrow? True
```

`import qgis.core` imports `pandas` and `pyarrow` itself, before any plugin code runs. By the time
`_bootstrap_venv()` executes they are in `sys.modules`, and a `sys.path` change — append or
prepend — cannot displace them. **No `sys.path` strategy can give this plugin a working pandas on
macOS QGIS 4.2.1.**

So the fix is in the plugin: keep datetimes out of pandas on this platform — read parquet through
`pyarrow` and hand back the timestamp column as something else (epoch integers, strings, or the
index), and replace `pd.to_datetime` with parsing that does not build a pandas datetime dtype.
Queued as `seq-C2-parquet-no-pandas`. It is bigger than a bug: it is a constraint on every future
`gt/` reader, which is why it is worth a decision record if the owner agrees — a build session
writes neither (`WORKFLOW.md` §6.2).

### What does work, with the venv present

Measured against the real dataset in the faithful harness:

- `bathy_2015.tif` through QGIS: valid, 3456 × 679, EPSG:32619, 1 band, min/max/mean
  −81.96 / −55.05 / −73.17, and `identify` at the centre returns −74.4126.
- `test_imagemetadata.pq` read with `pyarrow` **excluding** the timestamp column: 5900 × 38.
- `gt.image_manager`: `build_kdtree` → `KDTree`; `nearest_image_index` → `(36, 5.7e-05)`;
  `resolve_image_path` → `201503.20150619.181142496.204638.jpg`; `attach_annotations` → (5, 39).
- All 5900 JPEGs present; the first decodes to (1024, 1360, 3) through **both** `cv2.imread` and
  `skimage.io.imread`, and through Qt's own `QImage` (1360 × 1024).
- `mbes_2015.parquet`: **20 581 319 rows**, 13 columns, **one row group**; a 5000-row batch of
  `['Ping Time', 'Ping Number', 'Beam Number', 'Easting']` reads fine. One row group in a 395 MB file
  means a full-column read cannot be streamed in pieces — worth knowing before anyone tunes the BS
  query builder's memory use.
- `gt.video_manager.load_video_metadata` on `test_detector_output.csv`: 7278 rows.
- **All 19 `gt/` modules import** under QGIS with the venv appended (D-008 holds on macOS).
- `gt.config_check.check_settings({})` with **no `config/config.yaml` on this machine** reports
  exactly the two documented errors, `HabCam.imagepath` and `HabCam.imagemetadata`, and nothing else.
  The plugin does **not** need a GRASS/FastGIS API key to reach that point, so nothing in this session
  needed a secret and none was created.

Two softer leads, not chased:

- `load_video_metadata` accepted `test_detector_output.csv` — an *image* detector CSV whose columns
  are `id,Imagename,frame_id,TL_x,…` — and returned 7278 rows (the file has 7279 lines). Its sibling
  `load_video_annotations` correctly refuses the same file with `KeyError: 'frame_index'`. A loader
  that silently accepts the wrong CSV is worth a look.
- Qt6 is stricter than the generated-UI convention suggests: `rl.dataProvider().identify(pt, 1)`
  raises `TypeError: argument 2 has unexpected type 'int'`. The enum member is required in
  hand-written code. This does not contradict **D-005** (which is about generated `Ui_*.py`), but a
  session that reads the convention as "ints are fine everywhere" will be surprised.

## 6. Running and debugging it on the Mac

### 6.0 Open the right profile — this is where it goes wrong

**The plugin is NOT in the `default` profile.** It is installed in two profiles of its own, and
QGIS reopens whichever profile it used last (`profiles.ini` → `lastProfile`). On 2026-10-24 the
owner opened QGIS, saw eight plugins and no GroundTruther: that was `default`, which carries only
the core set plus `db_manager_community`.

| Profile | What is in it |
|---|---|
| `default` | the owner's own. **No GroundTruther.** Left untouched by this session |
| `gt-mac-novenv` | the plugin, **no `.venv`** — exactly what a Plugin Manager install gives you |
| `gt-mac-test` | the plugin **and** a working `.venv` |

All three live under `~/Library/Application Support/QGIS/QGIS4/profiles/` (**QGIS4**, not QGIS3).

Launch straight into one, rather than clicking through *Settings → User Profiles*:

```bash
open -na /Applications/QGIS-final-4_2_1.app --args --profile gt-mac-test
```

```bash
open -na /Applications/QGIS-final-4_2_1.app --args --profile gt-mac-novenv
```

`-n` forces a new instance, so this works even when QGIS is already open on another profile. QGIS
writes the profile it used into `profiles.ini` on exit, so after one of these a plain double-click
reopens the same one — which is also how `default` became sticky.

Two ways to confirm you are where you think you are: the window title names the profile, and
*Settings → User Profiles* shows it ticked. If GroundTruther still does not appear in
*Plugins → Manage and Install Plugins → Installed*, tick **Show also experimental plugins** in that
dialog's *Settings* tab — `metadata.txt` has `experimental=True`. (QGIS's own scanner does find it
in both profiles — `qgis.utils.findPlugins` returns `['groundtruther']` with version 0.4 and
`qgisMinimumVersion=4.0` — so discovery is not the problem; the profile is.)

### 6.1 The ordered check — the owner's, since no agent can drive the window

**A. the Plugin Manager case** — `gt-mac-novenv`:

1. Launch with the `gt-mac-novenv` command above.
2. *Plugins → Manage and Install Plugins → Installed*. **Expect**: GroundTruther, version 0.4.
3. Tick it. **Expect**: it fails to enable, with a traceback ending
   `ModuleNotFoundError: No module named 'pyqtgraph'`.
4. *View → Panels → Log Messages*, tab **GroundTruther**. What belongs here changed when
   `seq-U1-deps-message` (#67) landed — read that PR for what it now says, and compare. Before it,
   this session measured **nothing at all** in that tab.
5. **Expect no toolbar button and no GroundTruther menu.**

**B. the working case** — `gt-mac-test`:

6. Launch with the `gt-mac-test` command and enable GroundTruther. **Expect**: it enables, and the
   toolbar button and menu appear.
7. Click the button. **Expect**: the dock opens. There is **no `config/config.yaml`** on this Mac,
   so expect the two documented *errors* for `HabCam.imagepath` and `HabCam.imagemetadata` and
   **no** complaint about any other key.
8. Load `~/dev/groundtruther_test_dataset/bathy_2015.tif` as a raster and confirm it draws. It
   needs no pandas, and §5 measured it as valid and readable — so this step working tells you the
   install is sound.
9. In the dock's Settings, point `HabCam.imagepath` at
   `~/dev/groundtruther_test_dataset/image_subset` and `HabCam.imagemetadata` at
   `~/dev/groundtruther_test_dataset/test_imagemetadata.pq`, and save. **Already done** if you are
   in `gt-mac-test`: `mac-ondevice-test` wrote that config into the profile on 2026-10-24, pointing
   at the whole dataset (images, metadata, the detector CSV, the soundings and the reference
   surface), with an empty `grass_api_key`. Open Settings to look at it, then go on to 10.
10. **The one that matters.** Browse an image. **Expect it to work**: the image draws, with its
    annotation boxes, and QGIS stays up. **2026-10-24: ran twice.** First it took QGIS down (§6.2);
    after PR #100 the owner re-ran it and reported *"The image drew and QGIS stayed up"*. If it
    vanishes again, read §6.2 first — and check the profile is not holding a stale copy.

    **This expectation was reversed on 2026-10-24, and that is the point of the step.** It used to
    read *"Expect QGIS to vanish — no dialog, no plugin error, the whole application gone"*, because
    §5 had measured every pandas datetime conversion as a SIGSEGV. `seq-C2-parquet-no-pandas` (#73)
    and its follow-up (#81) routed every Parquet read through `gt/pandas_safe.py`, and
    `mac-ondevice-test` then ran the underlying calls in QGIS 4.2.1's own interpreter against this
    dataset: the timestamp-indexed metadata (5 900 images) and 20 581 319 MBES soundings both read
    in-process without taking the interpreter down, and `ioutils.parse_annotation` +
    `attach_annotations` mapped 3 538 annotated images onto it. So the crash is fixed **below** the
    UI; this step is what confirms it **through** the UI.

    **If QGIS still vanishes**, the fix does not reach the path the dock actually uses: say so, and
    name what you clicked. That is a new blocker and it blocks the 0.4 upload — not a re-scoping of
    `seq-C2`, whose own call sites are measured and fixed.

### 6.2 The crash step 10 found — `pd.DataFrame([row])` with a datetime row name

**2026-10-24. The owner loaded the plugin, opened the dock, and QGIS vanished** — reported as:
*"i was able to load the plugin, open its gui, but the image browser was missing the component to
browse the images (buttons and slider to switch image indexes) - when I open the image annotation
tool, click on a row of an annotated image got me a crash"*. So the trigger was **the annotation
tool's row click**, not the browse buttons, which they could not find (§6.3).

The step used to predict exactly this, and `mac-ondevice-test` had just argued it would not happen.
Both were right about their own evidence: the reads are fixed, and the dock crashes anyway, one call
further on.

**The faulting frame**, from `~/Library/Logs/DiagnosticReports/QGIS-final-4_2_1-2026-10-24-094356.ips`
— `SIGSEGV`, `EXC_BAD_ACCESS`, `KERN_INVALID_ADDRESS at 0x20`, main thread:

```text
0  pandas_datetime…so   get_datetime_metadata_from_dtype
1  np_datetime…so       pandas._libs.tslibs.np_datetime.is_supported_dtype
9  lib…so               pandas._libs.lib.maybe_convert_objects
   … slot_tp_new / type_call: a pandas object is being CONSTRUCTED
```

So this is not a Parquet read. It is pandas **inferring a dtype** while constructing an object, and
`gt/pandas_safe.py` already names that hazard — it just does not reach this call.

**How the row click reaches it.** `pygui/annotation_editor_gui.py:690` emits `seek_requested` →
`mixins/annotation_editor_mixin.py:115` `_on_annotation_seek_image` → `self.w.ImageIndexSlider
.setValue(index)` → the slider's signal → `add_image` → the metadata-panel update. So **every** way
of changing the image reaches the same call; the annotation list is simply the one the owner could
find.

**The call**, `mixins/image_browser_mixin.py:606`, in the metadata panel:

```python
md_str = pd.DataFrame(
    [self.imageMetadata[available].iloc[self.imageindex]]
).to_html()
```

`available` is eleven **numeric** columns, so the data is safe. The crash comes from the Series'
**name**: `.iloc[i]` carries the index label, which is a `datetime.datetime` (the metadata index is
object dtype by design), and `pd.DataFrame([series])` builds the new frame's index from that name —
straight into `maybe_convert_objects`.

**Reproduced and measured** in QGIS 4.2.1's own interpreter against the test dataset: the call exits
**139** (SIGSEGV). Three one-line fixes were each measured to survive and produce the same HTML:

| Candidate | Result |
|---|---|
| `pd.DataFrame([row.rename(None)])` | survives, 676 chars — drops the name; the panel has its own Time row (line 428) |
| `pd.DataFrame([row.to_dict()])` | survives, 676 chars |
| `pd.DataFrame([row.to_dict()], index=pd.Index([str(row.name)], dtype=object))` | survives, 701 chars — keeps the timestamp in the table |

**Scope.** A scan of the whole plugin for the same shape found **only this site**:
`querybuilder_gui.py:1096` describes soundings read as `epoch_us` (int64),
`scripts/build_ribbon.py:306` builds from dicts, and `gt/video_manager.py:141` and
`gt/roughness_join.py:112` pass an explicit dtype.

**Resolved 2026-10-24 by PR #100** (`master` `0155844`): the summary builds from `row.to_dict()`,
which drops the name, and a source-level test pins the shape because the crash does not reproduce on
Linux. The owner re-ran step 10 and the image drew. One trap on the way: **both test profiles hold
copies of the plugin and were stale after the merge**, so they were refreshed from `master` first —
a retest against a stale copy would have reproduced the crash and looked like the fix failing.

It *was* a blocker on `TODO_publish-0-4.md` WP-6. It is lane U code (`mixins/`), one line, and it is the
difference between a working plugin and one that kills QGIS the first time a user browses an image —
the plugin's primary action.

### 6.3 Why the browse controls looked missing — macOS hides them, and the slider is a separate dock

Same session, same report: *"the image browser was missing the component to browse the images
(buttons and slider to switch image indexes)"*. Nothing is broken; two deliberate decisions combine
badly on macOS.

1. **The forward/back buttons are hidden on macOS, by design.**
   `mixins/image_browser_mixin.py:191` — `if platform == "darwin": self.w.fwd.hide();
   self.w.rwd.hide()`. Introduced in `80ca551` ("split dockwidget into four focused mixins"), with
   no comment saying why, so the reason is not recoverable from the tree. On macOS the arrows simply
   are not there.
2. **The slider lives in its own top-level dock with its own toolbar button.** The nav controls
   (slider, spinbox, step, zoom-to, range) are re-parented out of the browser into a QGIS dock
   titled **"Image Index"** (line 764) which `.hide()`s at startup (line 770). It is opened by a
   *second* toolbar action, "Show / hide the Image Index navigator" (line 808) — **not** by the
   Image Browser button.

So the plugin is usable: click the second toolbar action. But the comment at line 1018 says *"The
nav follows the explicit toggle in `_toggle_image_dock`"*, and `_toggle_image_dock` (line 988) does
no such thing — it shows only `_image_dock`. The code comment is wrong about its own design, which
is why this reads as a missing widget rather than a hidden panel.

**Owed:** the macOS hide wants either a comment giving its reason or removal; the stale comment at
1018 wants deleting; and the install page should say that image navigation is a second toolbar
button. None of that blocks the upload — §6.2 does.

Please don't delete the two profiles afterwards, or the config in `gt-mac-test`: this list is the standing on-device check, and WP-6 of `TODO_publish-0-4.md` is gated on it.

### 6.2 How to debug it when something goes wrong

**Where the messages are.** *View → Panels → Log Messages* (not the Python console) has one tab per
tag. `GroundTruther` is the plugin's own (D-003); **Plugins** carries QGIS's plugin-loading errors,
and that is where a `classFactory` traceback lands. A plugin that fails to enable writes to
**Plugins**, not to `GroundTruther`, so check both before concluding the plugin said nothing.

**See stdout and stderr.** The log panel does not show them. Launch from a terminal instead of the
Finder and anything printed, plus Qt's own warnings, comes to the shell:

```bash
/Applications/QGIS-final-4_2_1.app/Contents/MacOS/QGIS-final-4_2_1 --profile gt-mac-test
```

**Reproduce an import failure by hand.** *Plugins → Python Console*, then:

```python
import importlib, traceback
try:
    importlib.import_module("groundtruther.groundtruther")
except Exception:
    traceback.print_exc()
```

and to see what the plugin's own bootstrap did:

```python
import sys, groundtruther
print(groundtruther.__file__)
print([p for p in sys.path if ".venv" in p])   # empty means _bootstrap_venv found no venv
```

**Re-enable without restarting.** Install the **Plugin Reloader** plugin and use it after editing
code. Failing that, untick and retick in the Plugin Manager — but a module that already failed to
import may be cached, so a restart is the honest check.

**When QGIS disappears with no message, it segfaulted.** macOS writes a report; the newest one names
the faulting library and function, which is how §5's diagnosis was corrected from "a pyarrow bug" to
"pandas' datetime C extension":

```bash
ls -t ~/Library/Logs/DiagnosticReports/*.ips | head -3
```

To read one without wading through 100 kB of JSON — the first line is a header, the rest is the
document:

```bash
python3 -c 'import json,sys; d=json.loads(open(sys.argv[1]).read().split("\n",1)[1]); t=d["threads"][d.get("faultingThread",0)]; i=d["usedImages"]; print(d["exception"]); [print(" ", (i[f["imageIndex"]].get("name") or "?"), f.get("symbol","")) for f in t["frames"][:12]]' "$(ls -t ~/Library/Logs/DiagnosticReports/*.ips | head -1)"
```

**Headless, without the window.** For anything that does not need the GUI, the harness in §3 is
faster and gives a real traceback. `CLAUDE.md`'s recipe under Testing is **Linux-only** and there is
no macOS one, so do not improvise: reaching for `Contents/MacOS/python3.12` is the obvious move and
makes every working compiled dependency look broken (§3). Two things `seq-C2` learned using the
harness, worth repeating: run probes with **`-u`**, or a segfault swallows the output and the run
looks like a success; and never pass **`-I`**, which discards `PYTHONHOME` so the interpreter will
not boot at all.

**Rule of thumb from this session.** A result too sweeping to be true — "every compiled dependency
fails", "pandas is entirely broken" — is usually the instrument, not the subject. Both times here,
checking the harness first would have saved the detour.

## 7. Work packages

| Package | Scope | Depends on | Lane | Size | State |
|---|---|---|---|---|---|
| `mac-install-test WP-1` | install from the zip, confirm the no-`.venv` blocker, measure every dependency, exercise `gt/` against the dataset, leave the owner §6 | — | U | M | ✅ this session |
| `mac-install-test WP-2` | keep datetimes out of pandas: `gt/image_manager.py:70` and `gt/video_manager.py:170` | WP-1 | C | M | ◐ built by `seq-C2-parquet-no-pandas` 2026-10-24, **PR #73 open for the owner** |
| `mac-install-test WP-3` | the macOS profile path and the faithful headless harness, in `CLAUDE.md` and the install page | WP-1 | U + D | S | queued `seq-U2-macos-profile-docs` |

## 8. Lane split

WP-2 is lane C (`gt/`) and WP-3 is lane U + D; they share no file. Both must wait for
`seq-U1-deps-message`, which owns `__init__.py` — WP-3 **adds** a macOS headless recipe to
`CLAUDE.md` beside the Linux one (there is none today) and documents `_bootstrap_venv`'s behaviour, and `publish-0-4` WP-4 may change what `_bootstrap_venv` does. A session may
decide its own PR split and test shape; it may not re-decide whether to prepend the venv (§5 shows
prepending does not work) or widen `requirements.txt` pins without the owner.

## 9. Verification

The real case is §6, and it is the owner's. What a session can verify: `seq-C2` must read
`test_imagemetadata.pq` **including** its `index` column inside QGIS's own interpreter without
crashing, through the harness of §3, and the suite must still pass on Linux where the stock
`pandas.read_parquet` works.

## 10. Kickoff

Both prompts are in `TODO_session_sequence.md` §2.
