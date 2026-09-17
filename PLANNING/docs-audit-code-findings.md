# TODO — Investigate and fix the three code findings from the documentation audit

| | |
|---|---|
| **Status** | `DONE` |
| **Type** | fix |
| **Worktree branch** | `fix/docs-audit-code-findings` |
| **Created** | 2026-09-17 |
| **Related memory** | `data-model-facts`, `documentation`, `roughness-integration`, `config-validation`, `project-overview`, `april-2026-refactor` |
| **Execution PR** | [#35](https://github.com/epifanio/groundtruther/pull/35) |

## Objective

Three defects surfaced while writing the documentation
(`PLANNING/settings-and-data-model-docs.md`, PR [#29](https://github.com/epifanio/groundtruther/pull/29))
and were deliberately left unfixed because that plan was docs-only. This plan closes
them. When done:

1. **No module in the plugin imports another by bare top-level name**, the three
   `sys.path.append` calls that made that work are gone, and the plugin no longer
   injects 21 generic names into the QGIS-wide module namespace
   ([#27](https://github.com/epifanio/groundtruther/issues/27)).
2. **The annotation CSV round-trips.** Saving *N* annotations and reloading yields
   exactly *N*, for GroundTruther's own writer and for a detector export alike; no
   silent row loss, no phantom header record
   ([#28](https://github.com/epifanio/groundtruther/issues/28)).
3. **The roughness georeference points the right way.** `bearing` is the direction
   *astern*, not the vehicle heading, and the plugin sends it as `heading_deg` — so every
   georeferenced micro-DEM, orthophoto and nav-placed mosaic is rotated **180° about its
   own centre**. This is now **confirmed, not suspected** (evidence below). Fix it, deal
   with the saved calibrations that may already compensate for it, correct the docs, and
   report the same assumption to the service side.

All three tracks are code fixes with a known shape. Track 3 was written as an open
investigation; it was **resolved before this plan was finalised**, so what remains is the
fix and its fallout.

## Context & background

### Finding 1 — bare intra-plugin imports on a mutated `sys.path`

**Corrected understanding.** The original issue claimed the video subsystem never loads.
That is **wrong** and has been corrected on [#27](https://github.com/epifanio/groundtruther/issues/27).
Verified against a real `QgsApplication` + plugin load:

```
loadPlugin: True
A) after loadPlugin only      -> bare gt importable? NO     # loadPlugin only runs __init__.py
B) after importing groundtruther.groundtruther:
   plugin dir on sys.path: True
   bare gt.video_manager   -> .../plugins/groundtruther/gt/video_manager.py
   SAME module object?     -> False                         # <-- the actual defect
   duplicate in sys.modules: True and True
```

[groundtruther.py:46](../groundtruther.py) runs `sys.path.append(os.path.dirname(__file__))`
at import time, and `classFactory()` imports that module — so by the time any mixin runs
the plugin's own directory *is* on `sys.path` and bare `gt.…` resolves. **The video
subsystem works.** What is broken is subtler:

- **Dual module identity.** `gt.video_manager` and `groundtruther.gt.video_manager` are
  two distinct objects loaded from one file, both in `sys.modules`. Module-level state
  exists twice (e.g. `gt/image_manager.py`'s `_PREFERRED_VARIANT`), and exception /
  `isinstance` identity does not survive the boundary. No currently dual-imported module
  defines an exception, so this is **latent** — one refactor from biting.
- **QGIS-wide namespace pollution.** All plugins share one `sys.modules`. The path
  append publishes **19 modules + 2 packages** under bare names: `gt`, `mixins`,
  `configure`, `config_model`, `ioutils`, `rectangle`, `ellipse`, `episg`, `epsg_list`,
  `qtpandas`, `pip_cpu`, `pip_cuda`, `grassconfig`, `search_epsg`, `resources_rc`,
  `groundtruther_dockwidget`, `plugin_upload`, `run_*_mdi`. Several are generic enough
  to collide with another plugin's; first import wins.

**The three enablers:**

| File | Line |
|---|---|
| [groundtruther.py](../groundtruther.py) | 46 — `sys.path.append(os.path.dirname(__file__))` |
| [pygui/querybuilder_gui.py](../pygui/querybuilder_gui.py) | 29 — `sys.path.append(parent)` |
| [pygui/kmlsave_gui.py](../pygui/kmlsave_gui.py) | 43 — `sys.path.append(parent)` |

**The 14 dependent imports:**

| Bare import | Sites |
|---|---|
| `gt.video_manager` | `mixins/video_browser_mixin.py:199,214,367` · `mixins/video_annotation_mixin.py:272` · `pygui/video_player_gui.py:632` · `pygui/video_annotation_editor_gui.py:428` |
| `gt.video_reader` | `pygui/video_player_gui.py:447` |
| `epsg_list`, `search_epsg` | `grassconfig.py:32,33` |
| `ellipse`, `rectangle`, `qtpandas` | `pygui/querybuilder_gui.py:49,50,63` |
| `pip_cuda`, `pip_cpu` | `pygui/querybuilder_gui.py:90,93` |
| `episg` (**star import**) | `pygui/epsg.py:51` |

Every other module in the repo already uses `from groundtruther… import …`; these 14 are
the stragglers. Note `pygui/kmlsave_gui.py` appends to `sys.path` and then does *not*
use a bare import — that one is pure dead weight.

### Finding 2 — the annotation CSV parser is wrong for both of its inputs

[ioutils.py:20](../ioutils.py) `parse_annotation` hard-codes
`pd.read_csv(..., skiprows=[0, 1], names=names)`. The magic number is not arbitrary:
[pygui/annotation_editor_gui.py:473](../pygui/annotation_editor_gui.py) `save_all_to_csv`
writes `fh.write("\n\n")` before the header, so GroundTruther's **own** save format is
two blank lines + header + rows. The parser was written for that. The result is wrong
for both real inputs, in opposite directions — measured, not inferred:

| Input | Wrote | Read back | Failure |
|---|---|---|---|
| GroundTruther's own save (2 blank lines + header) | 3 | **4** | pandas' `skip_blank_lines` means `skiprows=[0,1]` eats the blank lines and the **header survives as a data row** — a phantom `Imagename="Imagename"`, `Species="Species"`, `Confidence=NaN` |
| Detector export (1 header line) | 3 | **2** | header **and the first data row** are both skipped |

On the sample dataset's `test_detector_output.csv`: **7 278 rows in, 7 277 out.**

The phantom row is benign *by luck* — `NaN >= threshold` is False so it is never drawn,
and `"Imagename"` matches no frame so `attach_annotations` drops it at the join. The lost
detection is not benign: it is silent data loss with no way for a user to notice.

**Testability constraint.** `parse_annotation` lives in `ioutils.py`, which imports
`qgis.core` at module scope, so it cannot be unit-tested as-is. Per `CLAUDE.md`
("prefer adding logic to the stateless `gt/` package"), the fix should **move it to a
new Qt/QGIS-free `gt/annotations.py`** and leave a re-export in `ioutils` for the two
call sites (`mixins/settings_mixin.py:9`, `mixins/annotation_editor_mixin.py:141`).

### Finding 3 — CONFIRMED: the roughness georeference is 180° out ([#31](https://github.com/epifanio/groundtruther/issues/31))

This started as an open question and was **resolved during planning**, entirely offline,
after the user supplied the missing domain fact: *the camera's orientation follows the
vessel — it is towed just behind it.*

**The evidence chain**, every link measured on this machine:

| # | Claim | How it was verified |
|---|---|---|
| 1 | `Xutm`/`Yutm` is the **ship**, not the camera | `== proj(Longitude, Latitude)` exactly (0.0 m); 0.72 m median from `sXutm` |
| 2 | `Xutm + dx`, `Yutm + dy` is the **HabCam**, ~148 m astern | median ship→fix separation 147.7 m; 3.6 m from `Xutm_adj` (= `proj(habcam_lon/lat)`) |
| 3 | `bearing` is the compass direction **ship → HabCam**, i.e. *astern* | `atan2(dx, dy) == bearing` to 0.06°; `hypot(dx, dy) == distance` to 0.06 m |
| 4 | therefore `bearing ≈ course over ground + 180°` | median abs(COG − bearing) = **173.4°** over the survey |
| 5 | **image bottom→top is the direction of travel** | template-matching consecutive frames: content moves **DOWN** in **62 of 62** confident pairs (median +597 px; 5th–95th pct +485…+640; never negative), ≈ 464 mm of ground motion per frame against an independent prediction of ≈ 495 mm from speed × interval; `abs(dy) > abs(dx)` in 62/62 |
| 6 | the service rotates by `heading_deg`, bottom→top | `INTERFACE.md`: *"image bottom→top = vessel `heading_deg`, image-right = starboard"* |
| 7 | the camera is fixed to the tow, so its azimuth is the vessel's | stated by the user; consistent with (5), where the along-track axis is the image vertical |
| 8 | **closed loop:** rotating the measured image shift into ground coordinates under each hypothesis and comparing with the *independently measured* course over ground | **H1 (`heading = bearing`, shipped today): median error 175.2°** (IQR 173–176). **H2 (`heading = bearing + 180`): median error 4.8°** (IQR 4–7). n = 18 pairs with both a confident match and a ±15-frame nav baseline |

**Link 8 is the one to trust.** It does not rely on any argument about which way is
"forward": it takes the image displacement, converts it to a ground displacement under a
candidate heading, and checks it against the track the vehicle actually followed
according to the nav. Only one hypothesis reproduces the track. The residual 4.8° is the
expected sum of camera yaw relative to the track, USBL noise and cross-track drift —
which also tells you how accurate the corrected heading is: **good to about 5°**.

Link 5 gives the direction: a ground feature ahead of the camera enters at the **top** of
the frame and leaves at the **bottom**, so image-up points along the direction of camera
travel. Sixty-two out of sixty-two pairs, none dissenting, with the magnitude matching an
independent kinematic prediction to ~6 % — that is what makes it a measurement rather
than a coin flip, and it simultaneously validates the focal length (2480.28 px), the GSD
model (`altitude / f`) and the frame interval.

Link 8 then removes the last piece of reasoning from the chain by testing the two
candidate headings against the nav itself. Three checks that failed to discriminate are
worth recording so they are not repeated: nearest-neighbour matching of detector boxes
between consecutive frames (the platform moves ~600 px, so the "nearest" detection in the
next frame is almost always a **different** fish — a 50/50 split with no signal);
comparing `flat` and `pixel` mosaics (see below); and eyeballing a single annotated frame
pair, which is suggestive but not conclusive on featureless mud.

Rebuild this rather than trusting the paragraph — it is task 13:

```python
# flat-field the strobe vignette, CLAHE, then template-match an upper-middle
# patch of frame i against the whole of frame i+1.  Most frames are too turbid
# to match; that is expected and is why n is small relative to frames tried.
import cv2, numpy as np, pandas as pd, os
IMG = "<test dataset>/imgs_jpg"
df = pd.read_parquet("<test dataset>/projectdata.pq").sort_index()
names, alt = df.Imagename.values, df.Altimeter.values
t = df.index.values.astype("datetime64[ms]").astype(np.int64) / 1000.0
F = 2480.28                                    # rectified-left focal length, px
clahe = cv2.createCLAHE(3.0, (8, 8))

def load(i):
    a = cv2.imread(f"{IMG}/{names[i]}.jpg", cv2.IMREAD_GRAYSCALE)
    if a is None or a.shape != (1024, 1360):
        return None
    a = a.astype(np.float32)
    a = a / np.maximum(cv2.GaussianBlur(a, (0, 0), 80), 1e-3)     # flat-field
    a = cv2.normalize(a, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    return clahe.apply(a)

PH, PW, TY, TX = 260, 420, 120, 470            # patch size and origin in frame i
for i in candidate_rows:                       # consecutive pairs, t[i+1]-t[i] < 0.5 s
    A, B = load(i), load(i + 1)
    tpl = A[TY:TY + PH, TX:TX + PW]
    if tpl.std() < 10:                         # skip featureless frames
        continue
    _, score, _, loc = cv2.minMaxLoc(cv2.matchTemplate(B, tpl, cv2.TM_CCOEFF_NORMED))
    if score < 0.40:
        continue
    dx, dy = loc[0] - TX, loc[1] - TY          # displacement of the CONTENT
    gsd_mm = alt[i] * 1000.0 / F               # ground sample distance, mm/px
# expect: dy > 0 (content moves DOWN) and hypot(dx,dy)*gsd ~= speed * interval
```

Two traps worth knowing if you re-derive this independently:

* **Plain phase correlation returns ~0.** The static strobe vignette is identical
  between frames and pins the correlation peak at zero displacement. Flat-fielding
  first is not optional.
* **Only a gap of one frame works.** At ~3 m/s and 0.167 s the vehicle moves ~495 mm
  per frame ≈ 571 px, against a 1024 px frame height — so consecutive frames overlap
  ~44 % and a gap of 2 has no overlap at all.

### The gap that was open, and how it was closed

Every measurement above was originally made on the `imgs_jpg/*.jpg` delivery, while the
service reads the stereo `<name>_orig.png` from its own archive and works in the
*rectified left* frame. If `jpg == vflip(rectified_left)`, the whole finding inverts and
today's code would be correct — so this was a hard gate, not a footnote.

**Closed, offline.** The stereo archive is on an external drive at
`/run/media/epinux/WD_BLACK/DATA/HBC/DATA/2015_stereo` (73 710 `*_orig.png`, 2720 × 1024
side-by-side). Correlating each JPEG against all eight candidate orientations of both
halves:

| candidate | correlation | mean abs diff |
|---|---|---|
| **LEFT half, as-is** | **+0.985** | **2.6** |
| LEFT half, vertically flipped | +0.51 | 12.6 |
| LEFT half, horizontally flipped | +0.26 | 15.4 |
| LEFT half, rotated 180° | +0.22 | 15.8 |
| RIGHT half, any orientation | ≤ +0.52 | ≥ 12.6 |

Identical on all three frames tested. **The JPEG delivery is the left half of the stereo
pair, unflipped** — the residual 2.6 is JPEG compression noise. Rectification (raw left →
rectified left) is an orientation-preserving homography by construction, so image-up is
the same in all three frames.

Then the whole measurement was **re-run directly on the stereo left halves**, i.e. the
exact pixels the service reads:

```
n = 4 pairs (random access over USB is slow; this corroborates, it does not replace
            the n=62 and n=18 JPEG runs — and the JPEG *is* that left half)
  content moves DOWN: 4/4      median dy = +626 px,  dx = -46 px
  ground motion 504 mm/frame   (predicted ~495 from speed x interval)
  H1  heading = bearing        : median error 177.1 deg  (IQR 177-177)
  H2  heading = bearing + 180  : median error   2.9 deg  (IQR 3-3)
```

Same answer, slightly sharper. **No API call is needed to decide anything.**

**Conclusion.** The correct `heading_deg` is the vessel heading ≈ COG ≈ `bearing + 180°`.
[gt/roughness_geo.py](../gt/roughness_geo.py) sends `bearing`. Positions are correct —
which is exactly why this survived a georeferencing check that verified *position* to
~0.1 m and never tested *rotation*.

**`Heading` and `bearing` are not interchangeable.**
`DEFAULT_HEADING_COLS = ("Heading", "bearing")` treats them as two spellings of one
quantity. `Heading` is a vehicle attitude; `bearing` is layback geometry that happens to
be roughly anti-parallel to it. The fix is a per-column rule, not a new constant.

**Why the experiment this plan originally proposed would have failed.** The `flat` vs
`pixel` mosaic comparison is **not** decisive: `pixel` registers frames to each other by
content but takes its absolute orientation from the *reference frame's nav*. A global
heading error rotates both modes equally, so they would have agreed and the test would
have returned a false negative. Recorded because it is a tempting experiment.

*(Aside, still open: `groundtruther_test_dataset/test_mosaic_real.prj` declares
**EPSG:26919** (NAD83) while the plugin writes **32619** (WGS-84). The parquet's `Xutm` is
verified WGS-84-consistent, so the plugin looks right and that stray `.prj` probably came
from elsewhere — confirm rather than assume.)*

### Why these three are one plan

All three came out of the same audit pass, all three are "the ingest path does something
other than what it looks like it does", and all three need the same closing move: a live
QGIS session that only the user can run. Keeping them together means one worktree, one
review, one GUI-check session.

## Scope

**In scope:**

- Converting all 14 bare intra-plugin imports to `groundtruther.*` and deleting the
  three `sys.path.append` calls.
- Rewriting the annotation CSV reader to handle every shape it is given, and fixing the
  writer so it stops emitting the two blank lines that caused this.
- Moving `parse_annotation` into a Qt-free `gt/` module so it can be unit-tested.
- Verifying the bbox save → reload round trip (`_rect_to_bbox` / `_bbox_to_rect` /
  `parse_annotation`'s 8-value corner ring) while that code is open.
- Correcting the heading GroundTruther sends, and its fallout: the per-dataset
  `QgsSettings` calibrations that may already compensate with a 180° `heading_offset_deg`,
  and the two published pages that describe the current behaviour.
- New unit tests for each fix; updating the published docs where behaviour changes.
- Updating the two GitHub issues and closing them from the PR.

**Out of scope:**

- Any other refactor of `querybuilder_gui.py` / `kmlsave_gui.py` beyond the import lines.
  They are large and untested; touching more invites a regression this plan cannot catch.
- Renaming modules, restructuring packages, or adding `__init__.py` files beyond what the
  import conversion needs.
- The GPU path (`pip_cuda`) beyond its import line — it is unreachable without RAPIDS.
- Server-side (`epifanio/stereo-roughness`) changes. Confirmed, not suspected:
  `service/service_core.py:59` passes `bearing` as `heading_deg`, so **mode-A mosaics are
  180° out too and GroundTruther cannot fix that from here.** Already filed as
  [stereo-roughness#1](https://github.com/epifanio/stereo-roughness/issues/1) and
  [#2](https://github.com/epifanio/stereo-roughness/issues/2). Do **not** add a
  client-side compensation: it would double-correct the moment the server is fixed.
- The remaining open questions from the docs audit that are *not* defects
  (`Step`/`Position` units, the optical sensor channels, the `Beam Flag` encoding).
  Those need the user's knowledge, not an investigation.

## Prerequisites

- Read: `CLAUDE.md`, project memory (`MEMORY.md` + `data-model-facts`, `documentation`,
  `roughness-integration`, `config-validation`).
- Read the completed docs plan `PLANNING/settings-and-data-model-docs.md` — its Progress
  Log is where these findings are recorded, including the correction to Finding 1.
- Read issues [#27](https://github.com/epifanio/groundtruther/issues/27) and
  [#28](https://github.com/epifanio/groundtruther/issues/28) **including the correction
  comments** — the issue bodies alone are misleading.
- Read `/home/epinux/dev/stereo-roughness/INTERFACE.md` §`geo` and §`POST /mosaic`
  before Track 3.
- **Track 3 needs no API call to decide anything** — the question, including the
  frame-orientation gate, was settled offline during planning. One call to render a frame
  before/after the fix is authorised for visual confirmation. No batching; the service is
  a shared GPU.
- **The stereo archive lives on an external drive:**
  `/run/media/epinux/WD_BLACK/DATA/HBC/DATA/2015_stereo` (73 710 `*_orig.png`,
  2720 × 1024 side-by-side; left half = the `imgs_jpg` delivery). Mount it before Track 3.
  Random access over USB is slow — sample contiguous runs, not scattered rows.
- Reference data: `/home/epinux/dev/groundtruther_test_dataset/` (`projectdata.pq`,
  `test_detector_output.csv`, `test_mosaic_real.*`).

## Worktree setup

```bash
cd /home/epinux/dev/groundtruther
git fetch origin
git worktree add ../groundtruther-docs-audit-code-findings -b fix/docs-audit-code-findings origin/master
cd ../groundtruther-docs-audit-code-findings
ln -s /home/epinux/dev/groundtruther/.venv .venv     # reuse the main venv
```

## Task breakdown

### Track 1 — import hygiene (#27)

- [ ] **1. Baseline the namespace.** Write a throwaway script that loads the plugin
      offscreen (`QgsApplication` + `qgis.utils.loadPlugin` + import
      `groundtruther.groundtruther`) and records: whether the plugin dir is on `sys.path`,
      and which bare top-level names resolve to files under the plugin dir. Save the
      "before" list — it is the acceptance evidence for task 4.
- [ ] **2. Convert the 14 bare imports** to `groundtruther.*`, one commit per file so a
      bisect is cheap. `pygui/epsg.py:51`'s `from episg import *` needs care: enumerate
      what it actually binds before replacing the star.
- [ ] **3. Delete the three `sys.path.append` calls** (`groundtruther.py:46`,
      `pygui/querybuilder_gui.py:29`, `pygui/kmlsave_gui.py:43`) and the now-dead
      `current`/`parent` locals. This is the step that makes task 2 load-bearing — do it
      **after** the conversions, as its own commit.
- [ ] **4. Re-run the task-1 script.** Expect: plugin dir **not** on `sys.path`, and the
      bare-name list **empty**. Diff against the baseline and paste both into the
      Progress Log.
- [ ] **5. Add a regression test** (`tests/gui/`, since it needs a QGIS load) asserting
      that after a plugin load no plugin-local module is importable under a bare name.
      Keep it skip-if-no-QGIS like the other gui tests.
- [ ] **6. Grep for anything that re-introduces the hack** — `sys.path` mutation, bare
      imports of plugin-local names — and add a note to `CLAUDE.md`'s Conventions:
      intra-plugin imports are always `from groundtruther… import …`; never append the
      plugin directory to `sys.path`.

### Track 2 — annotation CSV (#28)

- [ ] **7. Write the failing tests first.** New `tests/unit/test_annotations.py`:
      round-trip *N* annotations through the writer and reader and assert *N* back;
      a detector-export fixture (1 header) keeping every row; a 2-blank-line fixture;
      a 2-banner-line fixture; a file with neither. Confirm they fail against the current
      code in the documented way (4-from-3, 2-from-3).
- [ ] **8. Move `parse_annotation` to a new Qt-free `gt/annotations.py`**, re-exported
      from `ioutils` so `mixins/settings_mixin.py:9` and
      `mixins/annotation_editor_mixin.py:141` keep working. `conftest.py` already stubs
      `groundtruther.configure`, so the new module must not import Qt/QGIS.
- [ ] **9. Replace `skiprows=[0, 1]` with a sniff:** drop leading blank/comment lines,
      then decide whether the first remaining line is a header (its numeric columns do
      not parse as numbers) or data. Keep the positional column mapping — the detector
      export's own header names differ from GroundTruther's internal names and the
      **order** is what matches.
- [ ] **10. Fix the writer**: drop `fh.write("\n\n")` from
      `pygui/annotation_editor_gui.py:473` so GroundTruther emits an ordinary CSV. The
      reader from task 9 still accepts the old shape, so existing files keep loading.
- [ ] **11. Verify the bbox round trip** — `_rect_to_bbox` → CSV → `parse_annotation`'s
      8-value ring → `_bbox_to_rect` must return the original rectangle. Add it to the
      test file. Fix if it does not; report if the ring ordering turns out to be
      load-bearing somewhere else.
- [ ] **12. Update the docs.** `website/docs/data-model/annotations-and-video.md` carries
      a warning box about the two-line skip and a workaround. Rewrite it to describe the
      new behaviour, and drop the workaround. **Remember this republishes the site on
      merge.**

### Track 3 — the 180° heading error

- [ ] **13. Reproduce both measurements before changing anything.** Rebuild the
      scroll-direction harness described in Finding 3 (flat-field → CLAHE →
      `cv2.matchTemplate` of an upper-middle patch of frame *i* against frame *i+1*, keep
      NCC ≥ 0.4), confirm content moves **down**, and then run the link-8 hypothesis test:
      rotate the measured shift into ground coordinates under `heading = bearing` and
      `heading = bearing + 180` and compare each against the course over ground from a
      ±15-frame nav baseline. Expect ~175° error for the first and ~5° for the second.
      Paste both into the Progress Log. **Do not take the fix on trust** — if this does
      not reproduce, stop and report, because everything below depends on it.
- [x] **13b. GATE (already closed during planning) — the JPEG delivery and the service's
      rectified left share a vertical orientation.** Verified offline against the stereo
      archive on `/run/media/epinux/WD_BLACK/…/2015_stereo`: the JPEG is the **left half,
      unflipped** (corr +0.985 vs ≤ +0.52 for every other orientation), and the full
      measurement re-run on the stereo left halves gives the same answer. See "The gap
      that was open" in Finding 3. Re-confirm cheaply if you wish, but this no longer
      blocks the fix.
- [ ] **14. Make `Heading` and `bearing` distinct quantities** in
      [gt/roughness_geo.py](../gt/roughness_geo.py). `DEFAULT_HEADING_COLS` currently
      treats them as interchangeable spellings. A true `Heading` column is used as-is; a
      `bearing` column is the ship→body direction and must be turned round
      (`(bearing + 180) % 360`, normalised to whatever range the service expects — check
      `INTERFACE.md`; the dataset's own `bearing` is −180…180). Name the helper so the
      distinction is obvious at the call site, and put the *reason* in the docstring, not
      just the formula.
- [ ] **15. Unit-test the convention** in `tests/unit/test_roughness_geo.py`: a record
      with `Heading` sends that value unchanged; a record with only `bearing` sends
      `bearing + 180`; a record with both prefers `Heading`; wrap-around at ±180 is
      handled. These tests are the spec — write them so a future reader learns the
      geometry from them.
- [ ] **16. Deal with the saved calibrations — the light version.** The Georef tab
      persists `heading_offset_deg` per dataset in `QgsSettings`
      (`groundtruther/roughness/<md5-of-metadata-path>/…`), and a user who noticed the
      rotation might have dialled in ±180 to compensate — which would double-correct back
      to wrong after the fix.
      **Answered 2026-09-17: the author has never dialled ±180 into that offset**, so no
      rescue is needed on this machine. The plugin is published, though, so do not skip the
      guard entirely: **bump a stored schema version and reset `heading_offset_deg` to 0
      when the stored version is older**, with one `Qgis.Info` line saying so. Cheap, safe
      for the one install we know about, and correct for any we do not. Detecting
      near-±180 values and second-guessing them is now **out of scope** — it risks clearing
      a legitimate mount calibration to solve a problem nobody has.
- [ ] **17. Check the neighbours of the bug.** Does anything else consume `bearing` as if
      it were an attitude? (`grep -rn "bearing" --include="*.py"`.) Confirm the `mirror`
      flag is genuinely independent — a 180° rotation is not a reflection, and anyone who
      "fixed" this with `mirror` has a second, different error.
- [x] **18. Report it upstream — done 2026-09-17, before execution.** Confirmed at the
      line rather than suspected: `service/service_core.py:59` builds the mode-A nav with
      `heading_deg=float(r.bearing)`, so the service has the identical bug. Two issues
      filed on `epifanio/stereo-roughness`:
      [#1](https://github.com/epifanio/stereo-roughness/issues/1) (the service code path)
      and [#2](https://github.com/epifanio/stereo-roughness/issues/2) (`INTERFACE.md`
      recommends `bearing` to every client — the contract is what led GroundTruther
      astray, and its mode-B example also shows the layback model `Xutm_adj` where the
      service itself uses the USBL fix). **`epifanio/FastGIS` needs nothing** — it is a
      pure proxy for this route.

      **Consequence to carry into task 19 and the release note:** once the client fix lands
      and before the service issues do, `/seafloor/roughness` output is correct while
      **mode-A mosaics are still 180° out** — so a roughness raster and a mosaic of the
      same patch will disagree with each other. Say so in the docs. Do **not** compensate
      client-side; it would double-correct the moment upstream lands.
- [ ] **19. Correct the published docs.** `website/docs/data-model/image-metadata.md`'s
      "`Heading` vs `bearing`" note currently states the measurement and explicitly
      declines to draw a conclusion — replace it with the conclusion. Check
      `website/docs/tools/seafloor-roughness.md`'s heading-offset/mirror section still
      reads correctly afterwards. **Merging republishes the site.**
- [ ] **20. Confirm live** (needs the user, or an authorised single API call): render a
      georeferenced frame over recognisable relief and check it against `bathy_2015.tif`
      and the backscatter. Before/after screenshots into the PR.

### Closing

- [ ] **21. Full verification** (see below), Progress Log, memory update: `data-model-facts`
      gets the confirmed heading conclusion (it currently records it as an open question),
      and the import convention is recorded for future sessions.
- [ ] **22. Rename** `TODO_docs-audit-code-findings.md` → `docs-audit-code-findings.md`,
      `Status: DONE`; **amend** `PLANNING/settings-and-data-model-docs.md`'s Progress Log
      to note that its open question #1 is now answered.
- [ ] **23. Open the PR** with `Closes #27` / `Closes #28` / `Closes #31`, leave unmerged.

## Acceptance criteria & verification

- [ ] `.venv/bin/pytest` green, plus the new tests. Baseline at `5d74466` is
      **286 passed / 6 skipped** without QGIS and **303 / 4** with
      `/usr/share/qgis/python` on `PYTHONPATH`; state both new numbers.
- [ ] Headless load check per `CLAUDE.md` passes (`QgsApplication` offscreen +
      `qgis.utils.loadPlugin("groundtruther")` → True, then all plugin modules import).
- [ ] **After a plugin load, no plugin-local module resolves under a bare top-level
      name**, and the plugin directory is not on `sys.path`. Before/after lists in the
      Progress Log.
- [ ] `grep -rnE "^ *(from|import) (gt|mixins|configure|ioutils|config_model|pip_cpu|pip_cuda|qtpandas|rectangle|ellipse|episg|epsg_list|grassconfig|search_epsg|resources_rc|groundtruther_dockwidget)\b" --include="*.py" .`
      returns nothing outside `.venv/` and `tests/`.
- [ ] `grep -rn "sys.path.append" --include="*.py" .` returns only
      `__init__.py`'s `_bootstrap_venv` (that one is legitimate — it adds the venv, not
      the plugin).
- [ ] Annotation round trip: *N* in, *N* out, for all four fixture shapes, with the
      sample `test_detector_output.csv` keeping all **7 278** rows.
- [ ] `mkdocs build --strict -f website/mkdocs.yml` clean if any page changed.
- [ ] The scroll-direction measurement **reproduces** (content moves down by roughly
      `speed × interval / GSD` px), with the numbers in the Progress Log.
- [ ] A record carrying only `bearing` sends `heading_deg = bearing + 180`; a record
      carrying `Heading` sends it unchanged; unit-tested both ways.
- [ ] Saved per-dataset `heading_offset_deg` calibrations near ±180 are handled
      explicitly, not left to double-correct.
- [ ] An issue exists on the FastGIS / stereo-roughness side for mode-A mosaics.
- [ ] `config/config.yaml` never staged (gitignored, holds the API key);
      `website/site/` not committed.

### Manual checks by the user (agents cannot drive the QGIS GUI)

- [ ] **The import change is the risky one** — it alters how every module resolves. Open
      QGIS, enable the plugin, and exercise **each** subsystem at least once: image
      browser, video player (play + geo-link + annotations), annotation editor
      (draw → save → reload), query builder (EPSG search, ellipse and rectangle sampling
      shapes, backscatter plots), GRASS toolbox, roughness panel, report/KMZ export. A
      broken bare import shows up as a feature that silently does nothing, not as a
      crash — check the `GroundTruther` message-log tab for `ImportError`.
- [ ] Annotate an image, save, reload the plugin, confirm the count is unchanged and no
      phantom entry appears in the metadata panel's species tally.
- [ ] **Track 3 is the one with a visible before/after.** Render a georeferenced frame
      over recognisable relief and compare it to `bathy_2015.tif` / the backscatter,
      before and after the fix. You know what that seabed should look like; the agent does
      not. Also say whether you had ever dialled a heading offset into the Georef tab for
      a dataset — that determines how aggressive task 16 needs to be.

## Risks & rollback

- **Risk: removing `sys.path.append` breaks an import nothing tests.** Most likely in
  `querybuilder_gui.py` / `epsg.py`, which have no test coverage and are only exercised
  through the GUI. *Mitigation:* convert first and delete the path hack as a separate,
  later commit, so `git revert` of one commit restores the old behaviour; plus the
  per-subsystem manual checklist above. This is why the GUI check is not optional.
- **Risk: the `episg` star import binds names nobody can enumerate statically.**
  *Mitigation:* enumerate at runtime before replacing it; if it is genuinely opaque, keep
  `from groundtruther.episg import *` rather than guessing a name list.
- **Risk: the annotation sniff misclassifies a real file.** A detector export whose first
  data row happens to have non-numeric coordinates would be read as a header.
  *Mitigation:* require *all* of `TL_x, TL_y, BR_x, BR_y` to fail numeric parsing before
  calling a line a header, and log at `Qgis.Info` which shape was detected.
- **Risk: every georeferenced product made so far is wrong.** It is — that is the
  finding, not a risk. The risk is the *fallout*: saved calibrations that compensate for
  it (task 16), downstream GeoTIFFs already exported and possibly used, and the service
  side making the same assumption for mode-A mosaics (task 18, out of scope to fix).
  *Mitigation:* handle the stored values explicitly and say plainly in the PR that
  previously exported rasters need regenerating.
- **Risk: over-correcting.** If the service is fixed for mode A while the client also
  compensates, the error comes back. Fix only what GroundTruther sends; report the rest.
- **Risk: the whole of Track 3 is inverted.** *Closed.* This was the one part of the plan
  that could actively make things worse; the frame-orientation gate (task 13b) was
  verified against the stereo archive before the plan was finalised. Re-read it before
  touching `geo_from_record` anyway — it is the assumption the fix rests on.
- **Risk: scope sprawl into `querybuilder_gui.py`.** It is ~1300 lines and untested. The
  Scope section forbids touching anything but the import lines. If a fix seems to require
  more, stop and say so.
- **Rollback:** own branch + worktree; three independent tracks, each in its own commits,
  so any one can be dropped without the others. Nothing here touches the config schema or
  the published site except task 12.

## Kickoff prompt

```
You are working on the GroundTruther QGIS plugin (QGIS 4 / Qt6). Execute the plan in
PLANNING/TODO_docs-audit-code-findings.md end to end.

First: read CLAUDE.md and review the project memory (your recalled memories + the
MEMORY.md index). Then create the dedicated worktree exactly as the plan's "Worktree
setup" section specifies (branch: fix/docs-audit-code-findings).

Then complete the Task Breakdown and meet the Acceptance Criteria. Three independent
tracks: import hygiene (#27), the annotation CSV parser (#28), and a confirmed 180° error
in the heading sent to the roughness service. Read BOTH issues including their correction
comments before starting — the issue bodies alone are misleading, and #27 in particular
describes an effect that was disproved.

Track 3's conclusion was reached during planning, not assumed: `bearing` is the ship→body
direction (astern), the camera's image-up points forward along the tow, and the service
rotates by `heading_deg` bottom→top — so the plugin has been sending heading + 180°. The
plan's "Finding 3" section carries the full evidence chain. **Reproduce the
scroll-direction measurement yourself (task 13) before changing any code**; if it does not
reproduce, stop and report rather than applying the fix on trust.

Verify what you claim generally: before asserting that an import fails or a value is
wrong, reproduce it in the offscreen QGIS harness described in CLAUDE.md, not in a
hand-built PYTHONPATH. That distinction is what made the original #27 report wrong.

When done: run .venv/bin/pytest (and mkdocs build --strict if any page changed), update
the project memory with your findings, fill the Progress Log, rename
PLANNING/TODO_docs-audit-code-findings.md → PLANNING/docs-audit-code-findings.md
(Status: DONE), note in PLANNING/settings-and-data-model-docs.md's Progress Log that its
open question #1 is now answered, and open a PR against master
(gh, account epifanio) with "Closes #27", "Closes #28" and "Closes #31". Do NOT merge — I will review
and merge, and the import change needs my hands-on GUI check first.
```

## Progress log

Executed 2026-09-17 in worktree `../groundtruther-docs-audit-code-findings` on branch
`fix/docs-audit-code-findings`, rebased onto `origin/master` `52333ae` after PR #34 landed
the answers to tasks 16 and 18 mid-execution.

### Track 1 — import hygiene (#27)

**Task 1 / 4 — namespace before and after.** Probe: `QgsApplication` offscreen →
`qgis.utils.loadPlugin("groundtruther")` → `import groundtruther.groundtruther`, then
`importlib.util.find_spec` for every top-level name in the plugin directory.

```
                                    BEFORE            AFTER
loadPlugin                          True              True
after loadPlugin only:
  plugin dir on sys.path            False             False
  bare names resolving into plugin  1 (groundtruther)  1 (groundtruther)
after importing the plugin module:
  plugin dir on sys.path            True              False
  bare names resolving into plugin  34                1 (groundtruther)
  gt.video_manager is
    groundtruther.gt.video_manager  False             n/a (no bare `gt`)
```

The 33 names that leaked, all now gone: `PLANNING`, `config`, `config_model`, `configure`,
`dependencies`, `docs`, `ellipse`, `episg`, `epsg_list`, `grassconfig`,
`groundtruther_dockwidget`, `gt`, `help`, `ioutils`, `maptools`, `mixins`, `pip_cpu`,
`pip_cuda`, `plugin_upload`, `pygui`, `qtpandas`, `qtui`, `rectangle`, `resources`,
`resources_rc`, `run_geomorphon_mdi`, `run_grm_lsi_mdi`, `run_paramscale_mdi`, `scripts`,
`search_epsg`, `tests`, `tmp`, `website`. (More than the 19 modules + 2 packages the plan
predicted — every *directory* leaked too, as a PEP-420 namespace package. `tests` and
`website` becoming importable top-level names for every other QGIS plugin in the process
is the most striking of them.)

**Task 2 — 17 bare imports converted, not 14.** The plan's table listed 14; the task-1
baseline turned up three more that a `gt|mixins|configure|…` grep missed because they are
spelled `pygui.…`:

| Site | Bare import |
|---|---|
| `grassconfig.py:31` | `from pygui.grass_settings_gui import GrassSettings` |
| `search_epsg.py:2` | `from pygui.epsg_search_gui import SearchEpsg` |
| `pygui/epsg_search_gui.py:18` | `from pygui.Ui_epsg_ui import Ui_Form` |

One commit per file, as planned.

`pygui/epsg.py:51`'s star import: the module body uses exactly two `episg` names,
`guioption` and `rep3`, so the star was replaced by that explicit pair rather than a
guess. Worth recording that **`pygui/epsg.py` is dead code** — nothing imports it, and its
own `from Ui_epsg_ui import Ui_Form` never resolved under any path (`Ui_epsg_ui` lives
*inside* `pygui/`, so it was never a top-level name). It is a superseded twin of
`pygui/epsg_search_gui.py`. Its imports were qualified anyway, because the acceptance
criterion is about reachability, not about whether anyone calls it. Deleting it was out of
scope; it is a candidate for a later cleanup.

**Task 3 — the three `sys.path.append` calls removed** (`groundtruther.py:46`,
`pygui/querybuilder_gui.py:29`, `pygui/kmlsave_gui.py:43`) plus the dead `current`/`parent`
locals and the `import sys` lines that became unused. Own commit, after the conversions,
so `git revert` of one commit restores the old behaviour.

`grep -rn "sys.path.append" --include="*.py"` now returns only `__init__.py:47`
(`_bootstrap_venv`, which adds the venv — legitimate).

**Every plugin module still imports under a real QGIS load** — 80 tried, 3 failed, and all
three fail identically on `origin/master`:

| Module | Why | Pre-existing? |
|---|---|---|
| `groundtruther.pip_cuda` | `No module named 'cuspatial'` (GPU path, unreachable without RAPIDS) | yes |
| `groundtruther.plugin_upload` | `name 'standard_library' is not defined` (Plugin Builder stub) | yes |
| `groundtruther.scripts.smoke_mosaic` | `RoughnessError: No mosaic endpoint configured` (a script, runs work at import) | yes |

`groundtruther.pygui.epsg` failed on master (`No module named 'Ui_epsg_ui'`) and now
imports — one fewer failure than before.

**Task 5 — `tests/gui/test_import_hygiene.py`.** Four assertions, run in a subprocess
because they are about `sys.path` / `sys.modules` after a real load and `tests/conftest.py`
wires `groundtruther` up differently inside pytest. **Confirmed to fail on the pre-fix
tree** (3 of 4) before being trusted.

Two ways the test was quietly vacuous on the first attempt, both now handled and
commented, and both worth knowing for any future check of this kind:

* the subprocess inherited the parent's `PYTHONPATH`, which under pytest contains the repo
  root — so every plugin module resolved bare and the "after" looked like the "before";
* `python -c` prepends the cwd, so running the probe from the repo root put the plugin
  directory back on the path. `cwd` is now the *plugins* directory, which is what QGIS
  itself has there.

Recorded as the memory `verifying-plugin-imports`.

**Task 6 — the convention is in `CLAUDE.md`'s Conventions section** rather than only in
project memory: it is loaded every session, which is the stronger guarantee. The
grep in the acceptance criteria returns nothing outside `.venv/`.

### Track 2 — annotation CSV (#28)

**Task 7 — both failure modes reproduced first**, against the current parser verbatim:

| Input | Wrote | Read back |
|---|---|---|
| two blank lines + header (GroundTruther's own save) | 3 | **4** — phantom `Imagename="Imagename"` |
| one header line (detector export) | 3 | **2** — header *and* first detection gone |
| sample `test_detector_output.csv` | 7 278 rows | **7 277** |

**Tasks 8–10 — new `gt/annotations.py`**, Qt/QGIS-free, with `parse_annotation` re-exported
from `ioutils` so `mixins/settings_mixin.py:9` and `mixins/annotation_editor_mixin.py:141`
are untouched. `split_preamble` drops leading blank and `#`/`//` comment lines, then calls
the first remaining line a header only if **all four** bbox columns fail to parse as
numbers — so a detection with one damaged coordinate is still data, which is the risk the
plan flagged. Which shape was detected is logged at `Qgis.Info`.

The preamble is cut with `str.splitlines()` rather than pandas' `skiprows`: whether that
counts blank lines depends on `skip_blank_lines`, and getting that interaction wrong in
either direction *is* the bug.

`save_all_to_csv` no longer writes `"\n\n"`; it calls `write_annotation_rows`, which
shares `ANNOTATION_COLUMNS` with the reader. Legacy two-blank-line files still load.

**Task 11 — the bbox round trip holds**, and the two helpers moved into `gt/annotations.py`
as `rect_to_bbox_ring` / `bbox_ring_to_rect` (they were pure and three lines each), so the
round trip they form with the reader's 8-value ring is unit-tested rather than duplicated
in a test. `pygui/annotation_editor_gui.py` imports them; the four call sites were renamed.
The ring order the reader builds is identical to the one the writer derives, so no
compatibility break.

28 new tests in `tests/unit/test_annotations.py` — six preamble shapes, the sniff itself,
writer→reader counts at N = 0/1/3/50, four bbox rectangles including two real rows from the
sample file, and the 7 278-row file.

**Task 12 — `website/docs/data-model/annotations-and-video.md`**: the warning box that
documented `skiprows=[0, 1]` and its workaround (prepend a second comment line) is replaced
by what the reader now does. Dropped an incorrect "before v0.3" version claim when
`metadata.txt` said `version=0.4`.

### Track 3 — the 180° heading error (#31)

**Task 13 — reproduced from scratch before any code changed**, harness rebuilt from the
plan's description rather than copied: flat-field ÷ Gaussian σ=80 → CLAHE(3.0, 8×8) →
`cv2.matchTemplate` (`TM_CCOEFF_NORMED`) of a 420×260 patch at (470, 120) of frame *i*
against the whole of frame *i+1*; NCC ≥ 0.40, patch σ ≥ 10, consecutive pairs with
Δt < 0.5 s. 58 163 of 123 394 frames are on disk; 938 textured pairs tried, 60 confident
matches.

```
(a) scroll direction
    content moves DOWN in 60 of 60 pairs
    median dy = +558 px   (5th-95th pct +485 ... +632)
    median dx =  -24 px   |dy| > |dx| in 60 of 60
    measured ground motion   478 mm/frame
    predicted (speed x dt)   489 mm/frame   (n=59, median speed 2.98 m/s)

(b) hypothesis test vs course over ground (+/-15-frame nav baseline)
    H1  heading = bearing         median error  175.1 deg   IQR 174-177   n=59
    H2  heading = bearing + 180   median error    4.9 deg   IQR   3-6     n=59
    median |bearing - COG| = 178.0 deg
```

Against the plan's 62/62, +597 px, 464 vs 495 mm, 175.2° / 4.8°: **it reproduces.** The
2 % agreement between measured and predicted ground motion simultaneously validates
`f = 2480.28 px`, the `altitude / f` GSD model and the frame interval. Only H2 reproduces
the track the vehicle actually followed.

**Task 14 — `DEFAULT_HEADING_COLS` replaced by `HEADING_SOURCES`**, a per-column rule that
pairs each column with whether it points astern:

```python
HEADING_SOURCES = (("Heading", False), ("bearing", True))
```

plus `reverse_bearing()` and `platform_heading_from_record()`. The *reason* is in the
docstrings, not just the formula. Normalised to `[0, 360)`; the nav's own `bearing` is
−180…180, and `INTERFACE.md` states no range requirement.

**Task 15 — `tests/unit/test_roughness_geo.py`** gained the convention as a spec: a
`Heading` row unchanged, a `bearing` row reversed, `Heading` winning when both are present,
wrap-around at ±180 both ways, double reversal as identity, and a check that the reversal
reproduces the ship direction from a real row's own `dx`/`dy`. Two pre-existing tests
asserted the old behaviour (`bearing` 88.3 → 88.3) and were updated — they encoded the bug.

**Task 16 — the light version, as PR #34 specified.** `RoughnessMixin.GEOREF_CAL_VERSION`
= 2; on load, a dataset that has a stored `heading_offset_deg` written under an older
version has it reset to the config default and gets one `Qgis.Info` line saying why.
`epsg` / `mirror` / `georeference` are untouched, and `_save_georef_calibration` now stamps
the version. No near-±180 detection — out of scope per the plan, and it would risk clearing
a legitimate mount calibration.

**Task 17 — the neighbours are clean.** `grep -rn "bearing" --include="*.py"` finds
`bearing` consumed **only** by `gt/roughness_geo.py`; the positions use `dx`/`dy` directly
and never the bearing/distance polar form. `mirror` is genuinely independent — it is
forwarded verbatim to the service as a port/starboard reflection and is never combined with
the heading client-side; a 180° rotation is not a reflection. The Georef tab's and the
Settings dialog's tooltips already describe it that way and needed no change.

Fixed a stale comment in `config_model.py:104-116` while there: it claimed
`Xutm_adj → easting` (the code uses `Xutm + dx`) and `Heading/bearing → heading_deg`.

**Task 18 — already done before execution**, verified:
[stereo-roughness#1](https://github.com/epifanio/stereo-roughness/issues/1) and
[#2](https://github.com/epifanio/stereo-roughness/issues/2) are both open.

**Task 19 — docs corrected.** `image-metadata.md`'s "`Heading` vs `bearing`" note now draws
the conclusion instead of declining to, quotes the measurement and states the ~5° accuracy
bound; a second box says previously exported rasters are rotated and that the service side
is still wrong for mode-A mosaics. `seafloor-roughness.md`'s "Heading offset vs Mirror"
section still reads correctly and was left alone apart from a new box explaining the
calibration reset. `mkdocs build --strict` clean.

**Task 20 — not done here; it is the user's.** There is **no `Roughness` section in this
machine's `config/config.yaml`**, so the roughness service is not configured and the single
authorised API call was not available. Nothing depended on it: the question was settled
offline, and the visual before/after needs someone who knows what that seabed looks like.

### Verification

| Check | Result |
|---|---|
| `.venv/bin/pytest` (no QGIS) | **331 passed, 7 skipped** (baseline 286 / 6) |
| `PYTHONPATH=/usr/share/qgis/python .venv/bin/pytest` | **352 passed, 4 skipped** (baseline 303 / 4) |
| offscreen `loadPlugin("groundtruther")` | `True`; 80 modules imported, 3 pre-existing failures |
| plugin dir on `sys.path` after load | **False** (was `True`) |
| bare plugin-local names resolving | **none** (was 33) |
| bare-import grep | nothing outside `.venv/` |
| `sys.path.append` grep | only `__init__.py`'s `_bootstrap_venv` |
| annotation round trip | N in / N out for six shapes; sample file keeps all **7 278** rows |
| `mkdocs build --strict -f website/mkdocs.yml` | clean |
| scroll-direction measurement | reproduces (60/60 down, 478 vs 489 mm) |
| `bearing`-only record | sends `heading_deg = bearing + 180`; `Heading` sent unchanged |
| saved `heading_offset_deg` | schema-versioned and reset, with a message-log note |
| upstream issue for mode-A mosaics | stereo-roughness#1 and #2, both open |
| `config/config.yaml` staged | never; `website/site/` not committed |

### Deviations from the plan

1. **17 bare imports, not 14** — three `pygui.…` spellings the plan's grep pattern missed.
2. **33 leaked names, not 21** — every plugin *directory* leaked as a namespace package too.
3. **The bbox helpers moved** into `gt/annotations.py` alongside the reader. The plan only
   asked to verify the round trip; moving the two pure three-line helpers made the round
   trip testable without duplicating them in the test file. Four call sites renamed in
   `pygui/annotation_editor_gui.py`.
4. **Task 6's convention went to `CLAUDE.md`** rather than only project memory.
5. **Task 20 not attempted** — the service is not configured on this machine.
6. `pygui/epsg.py` was found to be **dead code**; its imports were qualified but it was not
   deleted (out of scope).

### Follow-up for the user

1. **The GUI check in "Manual checks" is not optional** — the import change alters how every
   module resolves, and a broken import shows up as a feature that silently does nothing.
   Exercise each subsystem once and watch the `GroundTruther` message-log tab for
   `ImportError`. Query builder and `pygui/epsg*` have no test coverage at all.
2. Annotate an image, save, reload: the count should be unchanged and no phantom entry
   should appear in the species tally.
3. **Track 3 has the visible before/after.** Render a georeferenced frame over recognisable
   relief and compare with `bathy_2015.tif` / the backscatter. Regenerate anything exported
   earlier — it is rotated 180°.
4. Merging republishes the site (three `website/` pages changed).
5. Then: `git worktree remove ../groundtruther-docs-audit-code-findings &&
   git branch -d fix/docs-audit-code-findings`.
