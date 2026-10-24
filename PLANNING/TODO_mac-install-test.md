# Install GroundTruther on macOS QGIS 4.2.1 — what actually works

**The owner's brief** (2026-10-24, side session `mac-install-test`, beside the queue): install
GroundTruther on this Mac from the release zip and find out what actually works. A verification
session: it produces knowledge, not a feature.

## Status

**2026-10-24 — ◐ done, and it found two blockers nobody knew about.** The 0.4 code does load on a
real QGIS 4 on macOS, and almost every dependency works. But the plugin's *mandatory* startup path
— reading `HabCam.imagemetadata` — **segfaults QGIS 4.2.1 on macOS**, and the `.venv` strategy
cannot fix it, because `import qgis.core` has already imported QGIS's own broken `pandas`/`pyarrow`
before any plugin code runs. Two follow-up rows were queued; **WP-2 is now built** (`seq-C2-parquet-no-pandas`, PR #73, open
for the owner) and `seq-U2-macos-profile-docs` is still queued; `publish-0-4` WP-3/WP-4 gain facts
they were going to guess at. §5's diagnosis was narrower than the truth — see the correction there. The
GUI half is the owner's: §6 below is a launch-and-look checklist, with both profiles already built.
Nothing in this session touched plugin code.

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

So **the app can load pip wheels and the bundled `python3.12` cannot.** The headless recipe in
`CLAUDE.md` runs `python3.12`, and under it *every* compiled dependency fails with

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

## 5. The blocker nobody knew about: reading the image metadata segfaults QGIS

`gt/image_manager.load_metadata()` is `pd.read_parquet`, and `HabCam.imagemetadata` is one of the
only two config keys that are *errors* — the plugin cannot start without it. On this QGIS it does not
raise. **It kills the process with SIGSEGV** (exit 139), no exception, no log line.

Bisected to one line, with no GroundTruther and no venv involved:

```python
import pyarrow as pa, datetime
pa.table({"t": pa.array([datetime.datetime(2015, 1, 1)], type=pa.timestamp("us"))}).to_pandas()
```

| Where | Result |
|---|---|
| QGIS 4.2.1's pandas 3.0.3 + pyarrow 23.0.1 | **SIGSEGV** |
| homebrew 3.12 + pandas 3.1.0 + pyarrow 26.0.0 | fine |

So it is a **QGIS 4.2.1 macOS bundling bug**: that pandas/pyarrow pair cannot convert a
`timestamp[us]` column. `pq.read_table()` is fine; only `.to_pandas()` dies. Narrowed by column:
doubles fine, both string columns fine, and `test_imagemetadata.pq`'s `index` column is
`timestamp[us]` — so the plugin's own test dataset triggers it.

> **Correction, `seq-C2-parquet-no-pandas` 2026-10-24.** The fault is **wider than the Arrow bridge,
> and pyarrow is innocent.** Measured one process per case on the bundled stack (pandas 3.0.3,
> pyarrow 23.0.1, numpy 2.5.0): `to_pandas()` on timestamp of *every* unit with or without a
> timezone **and on duration**, `pd.to_datetime(int64, unit=…)`,
> `pd.Series(np.array([], dtype="datetime64[us]"))` — an **empty** array — and
> `pd.Series(arrow, dtype=pd.ArrowDtype(timestamp))` are all SIGSEGV; `date32`, `date64`, `time64`,
> doubles, strings and object-dtype `datetime.datetime` are all fine, as is numpy's own
> `datetime64`. So it is pandas' **dtype machinery** (pandas 3.0.3 against numpy 2.5.0, an ABI
> mismatch), not the data and not the bridge alone. A sibling measurement confirmed pandas is the
> sole variable: QGIS's own pyarrow 23.0.1 is fine under pandas 2.x. Two consequences: pinning
> pyarrow could never have helped, and **the breakage cannot be probed for at runtime, because the
> probe is the crash** — which is why the fix in PR #73 is unconditional rather than
> platform-branched. One edge remains: object datetimes are inert in a *column* but pandas
> re-infers them leaving an *index*, so `reset_index()` and `pd.concat()` on such a frame still
> die. The plugin calls neither.

**And the `.venv` cannot rescue it.** Prepending instead of appending gets the venv's working
pandas 3.1.0 / pyarrow 26.0.0 and the real file then reads fine — but only in a process that has not
started QGIS. Measured:

```text
after initQgis: pandas already imported? True | pyarrow? True
```

`import qgis.core` imports `pandas` and `pyarrow` itself, before any plugin code runs. By the time
`_bootstrap_venv()` executes they are in `sys.modules`, and a `sys.path` change — append or prepend —
cannot displace them. **No `sys.path` strategy can give this plugin a working pandas on macOS
QGIS 4.2.1.** The fix has to be in the plugin: read parquet through `pyarrow` and convert the
timestamp column without `to_pandas()`, or stop converting that column at all.

This is queued as `seq-C2-parquet-no-pandas`, and it is bigger than a bug: it is a constraint on
every future `gt/` reader, which is why it is worth a decision record if the owner agrees.

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

## 6. The GUI check — the owner's, and it is launch-and-look

No agent in this session drove the QGIS window, and nothing above is a UI check. Both profiles are
built and waiting, so this is five minutes.

**A. the Plugin Manager case** — `QGIS4/profiles/gt-mac-novenv`, plugin installed, no `.venv`:

1. Launch `/Applications/QGIS-final-4_2_1.app`, *Settings → User Profiles → gt-mac-novenv*.
2. *Plugins → Manage and Install Plugins → Installed*. **Expect**: GroundTruther listed, version 0.4.
3. Tick it. **Expect**: it fails to enable, with a traceback dialog ending
   `ModuleNotFoundError: No module named 'pyqtgraph'`.
4. *View → Panels → Log Messages*, tab **GroundTruther**. **Expect, today: nothing at all** — the tab
   is empty or absent. That emptiness is the WP-4 bug: confirming it is what makes WP-4 worth
   building. If a `GroundTruther` message *is* there, say so, because this session saw none.
5. **Expect no toolbar button and no GroundTruther menu.**

**B. the working case** — `QGIS4/profiles/gt-mac-test`, same plugin plus the `.venv`:

6. *Settings → User Profiles → gt-mac-test*, then enable GroundTruther in the Plugin Manager.
   **Expect**: it enables, and the GroundTruther toolbar button and menu appear.
7. Click the button. **Expect**: the main dock opens. There is **no `config/config.yaml`** on this
   Mac, so expect the two documented *errors* for `HabCam.imagepath` and `HabCam.imagemetadata`,
   surfaced however the dialog surfaces them — and expect **no** complaint about any other key.
8. Open *Settings* in the dock and point `HabCam.imagepath` at
   `~/dev/groundtruther_test_dataset/image_subset` and `HabCam.imagemetadata` at
   `~/dev/groundtruther_test_dataset/test_imagemetadata.pq`, then save.
9. **This is the one that matters.** Try to browse an image. **Expect QGIS to disappear** — no dialog,
   no crash report from the plugin, the whole application gone. That is §5's segfault reached through
   the UI. If QGIS *survives* and shows a HabCam image, then §5 is wrong about the GUI and
   `seq-C2-parquet-no-pandas` should be re-scoped; please say so.
10. Either way, load `~/dev/groundtruther_test_dataset/bathy_2015.tif` as a raster first and confirm
    it draws — §5 measured that it is valid and readable, and it needs no parquet.

Please don't delete the two profiles afterwards; `seq-C2` will want them.

## 7. Work packages

| Package | Scope | Depends on | Lane | Size | State |
|---|---|---|---|---|---|
| `mac-install-test WP-1` | install from the zip, confirm the no-`.venv` blocker, measure every dependency, exercise `gt/` against the dataset, leave the owner §6 | — | U | M | ✅ this session |
| `mac-install-test WP-2` | parquet without `pandas.to_pandas()` on timestamp columns | WP-1 | C | M | ◐ built by `seq-C2-parquet-no-pandas` 2026-10-24, **PR #73 open for the owner** |
| `mac-install-test WP-3` | the macOS profile path and the faithful headless harness, in `CLAUDE.md` and the install page | WP-1 | U + D | S | queued `seq-U2-macos-profile-docs` |

## 8. Lane split

WP-2 is lane C (`gt/`) and WP-3 is lane U + D; they share no file. Both must wait for
`seq-U1-deps-message`, which owns `__init__.py` — WP-3 rewrites the headless recipe in `CLAUDE.md`
that describes it, and `publish-0-4` WP-4 may change what `_bootstrap_venv` does. A session may
decide its own PR split and test shape; it may not re-decide whether to prepend the venv (§5 shows
prepending does not work) or widen `requirements.txt` pins without the owner.

## 9. Verification

The real case is §6, and it is the owner's. What a session can verify: `seq-C2` must read
`test_imagemetadata.pq` **including** its `index` column inside QGIS's own interpreter without
crashing, through the harness of §3, and the suite must still pass on Linux where the stock
`pandas.read_parquet` works.

## 10. Kickoff

Both prompts are in `TODO_session_sequence.md` §2.
