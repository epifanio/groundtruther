# TODO — Investigate and fix the three code findings from the documentation audit

| | |
|---|---|
| **Status** | `PLANNED` |
| **Type** | fix |
| **Worktree branch** | `fix/docs-audit-code-findings` |
| **Created** | 2026-09-17 |
| **Related memory** | `data-model-facts`, `documentation`, `roughness-integration`, `config-validation`, `project-overview`, `april-2026-refactor` |
| **Execution PR** | _(filled in by the execution agent)_ |

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
3. **The `bearing` → `heading_deg` question is answered** with evidence, not opinion:
   either the roughness georeference is confirmed correct and the reasoning is written
   down where the next person will find it, or a 180° error is demonstrated and fixed.

Tracks 1 and 2 are code fixes with a known shape. Track 3 is an **investigation with a
decision gate** — it may end in a one-line fix, or in a documented "no, it's correct,
here is why".

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

### Finding 3 — is `bearing` the wrong heading?

Measured on `projectdata.pq` (see the `data-model-facts` memory):

- `hypot(dx, dy) == distance` and `atan2(dx, dy) == bearing` — so **`bearing` is the
  direction of the base→HabCam offset vector**, not a vehicle attitude.
- That direction sits **~173° (median) from the course over ground** — exactly as
  expected for a body towed astern.
- [gt/roughness_geo.py:48](../gt/roughness_geo.py) `DEFAULT_HEADING_COLS = ("Heading", "bearing")`
  and this dataset has **no** `Heading` column, so `bearing` is what is sent as
  `heading_deg`.
- The service's convention (`/home/epinux/dev/stereo-roughness/INTERFACE.md`) is
  *"image bottom→top = vessel `heading_deg`, image-right = starboard"*.

So the value sent is ≈ course + 180°. Either the mount convention absorbs that, or every
georeferenced frame and mosaic is rotated 180° about its own centre.

**What could not settle it offline:** `groundtruther_test_dataset/test_mosaic_real.pgw`
is a *north-up* world file for a 4.96 m × 2.45 m patch. A 180° rotation about the centre
leaves that axis-aligned bounding box essentially unchanged, so the file proves only that
the mosaic is placed at the HabCam (≈3.6 m from the USBL fix) and not at the ship
(≈148 m away). It cannot distinguish the two orientations.

*(Aside, worth one minute during the investigation: that `.prj` declares **NAD83 / UTM 19N
(EPSG:26919)**, while the plugin writes **EPSG:32619**. The parquet's `Xutm` is verified
WGS-84-consistent (`Xutm == proj(Longitude, Latitude)` under 32619, 0.0 m residual), so
the plugin looks right and that stray `.prj` was probably produced elsewhere — but
confirm rather than assume.)*

**The decisive experiment** is available and self-contained: the mosaic route offers
`mode:"flat"` (placed purely by nav heading) and `mode:"pixel"` (registered by **image
content**, georeferenced only through the reference frame's nav). Build the same window
both ways over a textured stretch. If the nav heading is 180° out, the two mosaics
disagree by a 180° rotation; if it is right, they agree up to registration noise. This
requires **one live API call sequence** — which this plan explicitly authorises (the
docs plan did not).

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
- The `flat` vs `pixel` mosaic experiment, and whatever it implies: a fix, or a
  documented explanation of why the current behaviour is right.
- New unit tests for each fix; updating the published docs where behaviour changes.
- Updating the two GitHub issues and closing them from the PR.

**Out of scope:**

- Any other refactor of `querybuilder_gui.py` / `kmlsave_gui.py` beyond the import lines.
  They are large and untested; touching more invites a regression this plan cannot catch.
- Renaming modules, restructuring packages, or adding `__init__.py` files beyond what the
  import conversion needs.
- The GPU path (`pip_cuda`) beyond its import line — it is unreachable without RAPIDS.
- Server-side (FastGIS / stereo-roughness) changes. If Track 3 finds the bug is on the
  service side, **stop and report** — that is a different repo and a different plan.
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
- **Track 3 needs live API credentials** (`Processing.grass_api_key` in the local
  `config/config.yaml`, which is gitignored and already present on this machine). Calling
  the API **is** authorised for this plan — one mosaic window, two modes. Do not batch
  large windows; the service is a shared GPU.
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

### Track 3 — `bearing` as `heading_deg` (investigation)

- [ ] **13. Restate the question precisely** from the code, not from memory: what
      `geo_from_record` sends, what `INTERFACE.md` says the server does with it, and what
      a 180° error would look like in the output. Write this into the Progress Log
      *before* running anything, so the experiment has a falsifiable prediction.
- [ ] **14. Run the flat-vs-pixel experiment.** One window (±5 frames) over a **textured**
      stretch — check `register.quality` comes back `ok`, i.e. ≥30 % of pairs registered
      by content; a featureless window proves nothing because it falls back to nav.
      Build `mode:"flat"` and `mode:"pixel"`, write both GeoTIFFs, compare orientation.
- [ ] **15. Cross-check against the bathymetry.** Load a georeferenced orthophoto for a
      frame over recognisable relief and compare against `bathy_2015.tif` / the
      backscatter. Independent of the mosaic experiment and cheap.
- [ ] **16. Check the stray CRS** — why `test_mosaic_real.prj` says EPSG:26919 when the
      plugin writes 32619, and whether anything in the plugin can produce that.
- [ ] **17. Decide, and act on the decision.**
      - *Correct as-is* → write the reasoning into `gt/roughness_geo.py`'s module
        docstring and into `website/docs/data-model/image-metadata.md`'s "`Heading` vs
        `bearing`" note, replacing the current "measured fact, no claim" wording.
      - *180° out* → fix it in `geo_from_record` (**not** by changing the config default
        `heading_offset_deg`, which is a user-facing calibration knob, not a place to
        hide a sign error), add a unit test pinning the convention, and check whether
        already-saved per-dataset `QgsSettings` calibrations need invalidating.
      - *Server-side* → stop, write it up, open an issue on the FastGIS side.

### Closing

- [ ] **18. Full verification** (see below), Progress Log, memory update
      (`data-model-facts` gets the Track 3 answer; a new or extended entry records the
      import convention).
- [ ] **19. Rename** `TODO_docs-audit-code-findings.md` → `docs-audit-code-findings.md`,
      `Status: DONE`; **amend** `PLANNING/settings-and-data-model-docs.md`'s Progress Log
      with a dated one-liner correcting its Finding-1 claim (it is a durable record that
      future agents read, and it currently says the video subsystem is dead).
- [ ] **20. Open the PR** with `Closes #27` / `Closes #28`, leave unmerged.

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
- [ ] Track 3 reaches a **stated conclusion with evidence** — "inconclusive" is an
      acceptable outcome only if the Progress Log says exactly what was tried and what
      would settle it.
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
- [ ] Look at the Track 3 mosaics in QGIS and say whether the orientation is right — you
      know what that seabed should look like; the agent does not.

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
- **Risk: Track 3 turns out to be a real 180° error.** Then every georeferenced roughness
  raster and mosaic produced so far is wrong, and saved per-dataset calibrations may
  encode a compensating `heading_offset_deg`. *Mitigation:* the decision gate in task 17
  explicitly covers invalidating saved calibrations; do not silently change the meaning
  of a stored value.
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
tracks: import hygiene (#27), the annotation CSV parser (#28), and the bearing →
heading_deg investigation. Read BOTH issues including their correction comments before
starting — the issue bodies alone are misleading, and #27 in particular describes an
effect that was disproved.

Track 3 is an investigation with a decision gate, not a predetermined fix: it may end in
a code change or in a written explanation of why the current behaviour is correct.
Reaching a conclusion with evidence is the deliverable. This plan authorises live calls
to the FastGIS API for that experiment — one mosaic window, two modes, no batching.

Verify what you claim: before asserting that an import fails or a value is wrong,
reproduce it in the offscreen QGIS harness described in CLAUDE.md, not in a hand-built
PYTHONPATH. That distinction is what made the original #27 report wrong.

When done: run .venv/bin/pytest (and mkdocs build --strict if any page changed), update
the project memory with your findings, fill the Progress Log, rename
PLANNING/TODO_docs-audit-code-findings.md → PLANNING/docs-audit-code-findings.md
(Status: DONE), append the dated Finding-1 correction to
PLANNING/settings-and-data-model-docs.md's Progress Log, and open a PR against master
(gh, account epifanio) with "Closes #27" and "Closes #28". Do NOT merge — I will review
and merge, and the import change needs my hands-on GUI check first.
```

## Progress log

_(appended by the execution agent)_
