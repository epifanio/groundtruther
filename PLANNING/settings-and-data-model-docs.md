# TODO — Document every setting and every data model, and audit the existing docs

| | |
|---|---|
| **Status** | `DONE` — executed 2026-09-17 |
| **Type** | docs |
| **Worktree branch** | `docs/settings-and-data-model` |
| **Created** | 2026-09-17 |
| **Related memory** | `config-validation`, `roughness-integration`, `fastgis-grass-api`, `install-and-run`, `project-overview`, `april-2026-refactor` |
| **Execution PR** | [#29](https://github.com/epifanio/groundtruther/pull/29) |

## Objective

A user who opens GroundTruther's Settings dialog, or who has to prepare their own
data for it, can answer every question from the documentation site alone — without
reading `config_model.py` or asking the author. When done the site has a
**Configuration** section documenting all 27 config keys (what each does, its type,
default, what happens when it is wrong, and which feature it disables) and a **Data
model** section documenting every column the plugin reads from the HabCam image
metadata and MBES soundings parquets, with physical meaning and units. The audit
leg closes the gaps it finds in the pages that already exist — most glaringly, that
the site does not mention the Seafloor Roughness feature at all.

## Context & background

### Where the docs live

- **The site** is MkDocs Material in [website/](../website/), published to
  <https://epifanio.github.io/groundtruther/> by
  [.github/workflows/docs.yml](../.github/workflows/docs.yml) — it deploys on every
  push to `master` that touches `website/**`, so **merging the execution PR
  publishes immediately**. `website/site/` is a local build artifact and is not
  tracked; do not commit it.
- Current nav: Home, Installation (index + linux/macos/windows), Tools (image-browser,
  video-player, annotation, query-builder, report-builder, grass-fastgis),
  Architecture. 747 lines across 12 pages; the tool pages are 36–52 lines each.
- **[docs/grass_fastgis.md](../docs/grass_fastgis.md)** is an *agent-facing* deep dive
  referenced from `CLAUDE.md`. Different audience from the site — keep it separate,
  but cross-check it for drift.
- **[help/](../help/)** is a four-file Sphinx skeleton (`index`, `requirements`,
  `quickstart`) from the Plugin Builder template. It is not built by any workflow and
  duplicates the site badly.
- `docs/slides_groundtruther_update_2026.*` are a talk, not reference docs. Leave alone.

### What the audit already found (verify, then fix)

| Gap | Evidence |
|---|---|
| **No configuration documentation at all** | `grep -rn "config.yaml" website/docs/` → one passing mention in `installation/index.md:71`. The Settings dialog, the YAML file and all 27 keys are undocumented. |
| **Seafloor Roughness is entirely absent** | `grep -ril roughness website/docs/` → no matches. It is a four-tab dock (Metrics / Spectrum / Micro-DEM 3D / Georef), a FastGIS service, GeoTIFF output and 13 config keys. See the `roughness-integration` memory. |
| **No data-model documentation** | The plugin hard-codes column names it expects. The test dataset's image metadata has **38 columns**, the soundings **18**. A user bringing their own survey has no way to know what to provide. |
| **`help/` is stale and unbuilt** | Plugin Builder skeleton, never updated through the QGIS4 port or the 2026-04 refactor. |
| **Tool pages are thin** | 36–52 lines each; several predate the video player and the mixin refactor. |

### Source of truth for the content

Do **not** invent values — every default and constraint has a definition in code:

- Config schema and defaults: [config_model.py](../config_model.py)
  (`HabCam`, `Mbes`, `Export`, `Processing`, `Filesystem`, `VideoSettings`,
  `SessionSettings`, `RoughnessSettings`).
- Per-key validation, severity and failure text: [gt/config_check.py](../gt/config_check.py)
  `SPEC` — the authoritative list of which keys are fatal vs. degrading.
- The dialog's widgets and their tooltips: [configure.py](../configure.py)
  `ConfigDialog` (`_add_roughness_box`, `_add_video_annotation_row`,
  `_add_reference_surface_row`).
- Roughness transport and the `geo` object: [gt/roughness_client.py](../gt/roughness_client.py),
  [gt/roughness_geo.py](../gt/roughness_geo.py), and the shared contract
  `/home/epinux/dev/stereo-roughness/INTERFACE.md` (**pin to it** — it is the agreed
  interface with the FastGIS/stereo-roughness side; quote it, don't paraphrase it).
- Column usage: `gt/image_manager.py`, `gt/roughness_geo.py` (`usbl_xy`,
  `usbl_easting_northing`), `gt/mbes_fields.py` (`detect_backscatter_fields`),
  `mixins/settings_mixin.py` (`_attach_usbl_lonlat`), `pygui/querybuilder_gui.py`.

### Two facts that must appear, because they are non-obvious and easy to get wrong

1. **Positioning.** `Xutm+dx` / `Yutm+dy` is the **calibrated USBL fix** and is what
   GroundTruther uses everywhere. `Xutm_adj`/`Yutm_adj` is a layback *model* (~2.5 m
   median off) and `sXutm`/`sYutm` is the **ship GPS** (~138 m off — never a seafloor
   position). Getting this wrong silently misplaces every sample. See the
   `roughness-integration` memory.
2. **`Roughness.georeference` / `epsg` / `heading_offset_deg` / `mirror` are only
   defaults for datasets with no saved calibration.** The roughness panel's Georef tab
   writes a per-dataset calibration into `QgsSettings` (keyed by a hash of the metadata
   file path) and that takes precedence — a user who edits the config and sees no change
   needs to be told why.

## Scope

**In scope:**

- A new **Configuration** site section: the Settings dialog walkthrough, the
  `config.yaml` reference (all 27 keys), and the validation/troubleshooting model.
- A new **Data model** site section: HabCam image metadata and MBES soundings column
  references, plus the annotation CSV and video metadata formats.
- A new **Seafloor Roughness** tool page (the missing feature page).
- Audit and refresh of the existing 12 pages; `mkdocs.yml` nav updated.
- A decision on `help/`: retire it or reduce it to a pointer at the site.
- A short "documenting a new setting" note in `CLAUDE.md` so the docs stay current.

**Out of scope:**

- Re-theming the site or changing the MkDocs/Material setup beyond nav entries.
- Screenshots requiring a live QGIS session — an agent cannot drive the GUI. Leave
  marked placeholders and list them for the user (see Acceptance criteria).
- Documenting the FastGIS **server** API beyond what GroundTruther sends and receives
  (that lives in `INTERFACE.md` and the FastGIS repo).
- Changing any plugin behaviour, config schema or default. **This is a docs-only
  plan.** If the audit turns up a *code* bug, record it in the Progress Log and open a
  separate issue — do not fix it here.
- `docs/slides_*` and `docs/build_pptx.py`.

## Prerequisites

- Read: `CLAUDE.md`, project memory (`MEMORY.md` + `config-validation`,
  `roughness-integration`, `fastgis-grass-api`, `install-and-run`).
- Read `/home/epinux/dev/stereo-roughness/INTERFACE.md` before writing anything about
  the roughness request/response or the `geo` object.
- The Zenodo test dataset (<https://zenodo.org/records/7995674>) for column
  descriptions; on this machine the user's own copies are richer and are what the
  audit numbers above came from:
  `/home/epinux/dev/groundtruther_test_dataset/projectdata.pq` (38 cols) and
  `/home/epinux/mbqc_final/mbes_2015_multilevel.parquet` (18 cols).
- Build the site locally to check nav and links:
  `pip install -r website/requirements-docs.txt && mkdocs serve -f website/mkdocs.yml`
  (or `mkdocs build --strict`). Do not commit `website/site/`.
- No credentials needed. **Do not call the FastGIS API** — the contract file and the
  memory entries carry the verified request/response shapes.

## Worktree setup

```bash
cd /home/epinux/dev/groundtruther
git fetch origin
git worktree add ../groundtruther-settings-docs -b docs/settings-and-data-model origin/master
cd ../groundtruther-settings-docs
```

## Task breakdown

- [x] **1. Audit pass — record before changing.** Read all 12 existing pages against the
      current code and write the findings into the Progress Log as a table
      (page → claim → status: current / stale / missing). Check specifically for: the
      QGIS 4 / Qt6 port, the `.venv` install route (`install-and-run` memory), the
      mixin architecture, the FastGIS endpoint + `X-API-Key` model (the old
      `mbapi.wps.met.no` endpoint must not survive anywhere), and the video player.
- [x] **2. `configuration/index.md`** — what the config is, where it lives, that it is
      per-install and holds a secret (`grass_api_key`), how to open Settings, and how
      the file is written (merge + `yaml.safe_dump`, so hand-edited sections survive).
- [x] **3. `configuration/settings-reference.md`** — every key, grouped by section, as a
      table: key · type · default · required/optional · what it does · effect when unset
      or wrong. Generate the requiredness column from `gt/config_check.SPEC`, not by
      hand. Cover all 27 keys including the 13 `Roughness.*`.
- [x] **4. `configuration/validation.md`** — the per-key severity model: which two keys
      are fatal, that everything else degrades one feature, where the findings appear
      (the `GroundTruther` message log), and a troubleshooting table of real failure
      messages → cause → fix. Include the unmounted-drive case
      (`/run/media/...` + "the drive may not be mounted"), which is the failure that
      motivated the validation work.
- [x] **5. `data-model/image-metadata.md`** — the HabCam parquet: every column the
      plugin reads, with dtype, units and physical meaning; which are **required** vs
      optional; the derived `usbl_lon`/`usbl_lat` columns GroundTruther adds at load.
      Must state the positioning hierarchy from "Context" fact 1 explicitly, including
      why `sXutm`/`sYutm` is never a seafloor position.
- [x] **6. `data-model/mbes-soundings.md`** — the soundings parquet: geometry columns,
      the `BS_*` backscatter family and how `gt/mbes_fields.detect_backscatter_fields`
      picks between them, angle columns, `Beam Flag`, and the field names the query
      builder expects to match.
- [x] **7. `data-model/annotations-and-video.md`** — the annotation CSV columns
      (`ioutils.parse_annotation`), the video metadata CSV
      (`VideoSettings` docstring + `gt/video_manager.py`), and the per-frame video
      annotation format.
- [x] **8. `tools/seafloor-roughness.md`** — the missing feature page: what it computes,
      the four tabs, the request/response contract at the level a user needs,
      the outputs (micro-DEM, orthophoto, spectrum, GeoTIFFs), and a georeferencing
      section explaining **heading offset** (continuous rotation correction, applied to
      the nav heading server-side) versus **mirror** (discrete port/starboard handedness
      flip — a reflection no rotation can undo), with the symptom that tells them apart.
      State the QgsSettings-override rule from "Context" fact 2.
- [x] **9. Fix what the audit found** in the existing pages; add a "Configuration" link
      from `installation/index.md` where `config.yaml` is currently mentioned in passing.
- [x] **10. `mkdocs.yml` nav** — add Configuration and Data model sections and the
      roughness tool page. Keep the existing ordering convention.
- [x] **11. `help/` decision** — retire it (preferred: delete, leaving the site as the
      single doc surface) or reduce `index.rst` to a pointer. State which and why in the
      Progress Log; check nothing in `Makefile` / `pb_tool.cfg` / `metadata.txt` depends
      on it before deleting.
- [x] **12. Keep it current** — add a line to `CLAUDE.md`'s conventions: a new config key
      means `config_model.py` + `config_check.SPEC` + a row in the settings reference.
      Consider a unit test asserting every `SPEC` key appears in
      `website/docs/configuration/settings-reference.md`, so the docs cannot silently
      drift (this is the one code change the plan allows; put it in `tests/unit/`).
- [x] **13. Memory** — add a `documentation` memory entry (where the docs live, how they
      deploy, the audit's conclusions, the `help/` decision) with a `MEMORY.md` pointer.

## Acceptance criteria & verification

- [x] `mkdocs build --strict -f website/mkdocs.yml` succeeds with no warnings
      (strict catches broken internal links and pages missing from the nav).
- [x] `.venv/bin/pytest` green — 304 passed / 4 skipped with QGIS on `PYTHONPATH`,
      287 / 6 without, plus the new drift test from task 12.
- [x] Every key in `gt/config_check.SPEC` appears in the settings reference —
      verified mechanically, not by eye.
- [x] Every column the plugin reads by name appears in the data-model pages. Derive the
      list by grepping the source for string literals used as column keys; list any
      column deliberately left undocumented in the Progress Log.
- [x] No page still refers to QGIS 3, PyQt5, the old `mbapi.wps.met.no` endpoint, or a
      pip/conda install route contradicted by the `install-and-run` memory.
- [x] Screenshot placeholders are listed explicitly in the PR description so the user
      knows exactly which images to capture.
- [x] `website/site/` is not committed; `config/config.yaml` is not staged.
- [ ] **Manual check by the user:** `mkdocs serve`, then read the Configuration section
      start to finish against the real Settings dialog and confirm nothing is missing,
      mislabelled, or contradicted by what the dialog shows.

## Risks & rollback

- **Risk: docs that drift the moment they are written.** Mitigation: the task-12 drift
  test, and generating the requiredness/default columns from `SPEC` and
  `config_model.py` rather than transcribing them.
- **Risk: plausible-but-wrong physical descriptions of data columns.** Several columns
  in the test dataset are survey-specific (`Step`, `Position`, `TripDay`, `location`,
  `line`). Do **not** guess a meaning. Document what the plugin *does* with a column;
  where the physical meaning is genuinely unknown, say so and list it in the Progress
  Log as a question for the user rather than inventing a definition.
- **Risk: merging publishes immediately** — `docs.yml` deploys on push to `master`
  touching `website/**`. Review rendered output before merge.
- **Risk: scope sprawl.** Twelve pages plus six new ones is a lot; if it must be split,
  land Configuration + the roughness page first (highest user value) and Data model
  second, as two PRs from the same worktree.
- **Rollback:** docs-only on its own branch/worktree — drop the branch and nothing in
  the plugin or the published site changes (the site only rebuilds from `master`).

## Kickoff prompt

```
You are working on the GroundTruther QGIS plugin (QGIS 4 / Qt6). Execute the plan in
PLANNING/TODO_settings-and-data-model-docs.md end to end.

First: read CLAUDE.md and review the project memory (your recalled memories + the
MEMORY.md index). Then create the dedicated worktree exactly as the plan's "Worktree
setup" section specifies (branch: docs/settings-and-data-model).

Then complete the Task Breakdown and meet the Acceptance Criteria. This is a docs-only
plan: do not change plugin behaviour, the config schema, or any default — the single
permitted code change is the drift test in task 12. Every default, constraint and
column meaning must come from the source files the plan names; where a column's
physical meaning is genuinely unknown, say so rather than inventing one, and list it in
the Progress Log as a question for the user.

When done: run mkdocs build --strict and .venv/bin/pytest, update the project memory
with your findings, fill the Progress Log (including the audit table from task 1 and
the list of screenshot placeholders), rename
PLANNING/TODO_settings-and-data-model-docs.md → PLANNING/settings-and-data-model-docs.md
(Status: DONE), and open a PR against master (gh, account epifanio). Do NOT merge —
merging publishes the site, and the user reviews the rendered pages first.
```

## Progress log

_(appended by the execution agent)_

**2026-09-17 — executed** (agent session, worktree `../groundtruther-settings-docs`,
branch `docs/settings-and-data-model` off `origin/master` @ `5843d98`).

Read `CLAUDE.md` + the project memory (`MEMORY.md` index, `config-validation`,
`roughness-integration`, `install-and-run`) first, then the worktree per the plan.
No plugin behaviour, config schema or default was changed; the only code change is
the task-12 drift test.

### Task 1 — audit of the 12 existing pages

Checked each claim against the current source. **The site was in much better shape
than the plan's "tool pages are thin / several predate the refactor" hypothesis
suggested** — the QGIS 4 / Qt6 port, the `.venv` install route, the mixin
architecture, the `api.fastgis.eu` + `X-API-Key` model and the video player are all
described correctly. `grep -rniE "qgis ?3|pyqt5|mbapi|wps\.met\.no" website/` → **no
matches**. The real gaps were the three the plan named (no configuration docs, no
data-model docs, no roughness page) plus a handful of small inaccuracies.

| Page | Claim checked | Status | Action |
|---|---|---|---|
| `index.md` | Feature list, paper citation, "At a glance" table | **stale (incomplete)** — no mention of seafloor roughness or of configuration | Added a roughness bullet, a Configuration row, and links to Configuration + Data model from the "Get started" tip |
| `installation/index.md` | QGIS ≥ 4.0, Qt6/PyQt6, "never pip-install qgis/gdal/PyQt", conda + venv routes | current | — |
| `installation/index.md` | Dependency list vs `dependencies/requirements.txt` | **stale** — `av` (PyAV) missing | Synced the list to the requirements file |
| `installation/index.md` | "Settings persist to `config/config.yaml`" (the one config mention on the whole site, line 71) | **thin** | Expanded: where the file lives, that only 2 keys are mandatory, links to all three Configuration pages and to Data model |
| `installation/linux.md` | System QGIS 4 + `--system-site-packages` venv, `__init__.py` bootstrap, Wayland `QT_QPA_PLATFORM=xcb` | current (matches `install-and-run`) | — |
| `installation/macos.md`, `windows.md` | Profile paths, OSGeo4W shell, conda route | current | — |
| `tools/image-browser.md` | KD-tree, LRU cache, confidence threshold, map-scale zoom | current | — |
| `tools/image-browser.md` | "coordinates from the metadata are treated as WGS-84" | **misleading** — the marker uses the USBL fix `Xutm+dx`/`Yutm+dy` reprojected at load, falling back to `habcam_lon/lat` | Rewrote the tip; linked the Positioning section |
| `tools/image-browser.md` | Metadata panel "(position, depth, altimeter, …)" | **understated** — the panel lists *every* column of the table | Corrected |
| `tools/video-player.md` | "GPS metadata log (frame index / timestamp, latitude, longitude)" | **wrong** — the plugin calls `load_video_metadata_survey()`, which expects the cruise-survey DDM format (`LatDeg`/`LatMin`/`NorthSouth`…). The generic schema in the `VideoSettings` docstring is the *normalised output*, not the on-disk format | Corrected + linked the new column reference |
| `tools/video-player.md` | "decoding frames with OpenCV" / "Headless OpenCV" note | **stale** — `gt/video_reader.py` prefers **PyAV** (yadif deinterlace) and falls back to OpenCV | Rewrote both |
| `tools/annotation.md` | Draw/edit/delete, shared confidence threshold, remembered labels | current | Added a pointer to the two (quite different) file formats |
| `tools/query-builder.md` | Point query, numba/cuspatial selection, plotnine distributions | current | — |
| `tools/query-builder.md` | Inputs table | **incomplete** — `Mbes.reference_surface` missing; no mention that the coordinate column names are user-editable | Added both |
| `tools/report-builder.md` | Inputs table header "Settings → Export" listing `filemanager` | **wrong section** — `filemanager` is under `Filesystem` | Split into a Setting/Section table |
| `tools/grass-fastgis.md` | Environments, region, module dialogs, `X-API-Key`, `api.fastgis.eu` | current | Added links to the settings reference + a note that roughness reuses the same credentials |
| `architecture.md` | Mermaid data-flow and module map, design notes | **stale (incomplete)** — no roughness mixin, no `roughness_*`/`config_check` in the `gt/` box, no `av` in the dependency table, nothing on the validation model | Added all four |
| `architecture.md` | "pydantic v2, settings dialog" | current (`config_model.py` is the schema of record; runtime validation is `config_check`) | — |

### What was written

- **`configuration/index.md`** — what the file is, per-OS paths, per-install (not
  per-project) scope, the `grass_api_key` secret + the `.gitignore` / `config.example.yaml`
  arrangement, how to open Settings, the merge-based save (and that comments are *not*
  preserved — `yaml.safe_dump`), a worked example.
- **`configuration/settings-reference.md`** — all **27 keys in 8 sections**. Type,
  default, requiredness and bounds were generated from `config_check.SPEC` +
  `config_model.py` rather than transcribed.
- **`configuration/validation.md`** — the degrade-don't-veto model, where findings
  appear (`GroundTruther` message-log tab, Critical vs Warning), the unmounted-drive
  case, a *message → cause → fix* table built from the literal reason strings in
  `config_check.py`, and a reverse *symptom → setting* table.
- **`data-model/image-metadata.md`**, **`mbes-soundings.md`**,
  **`annotations-and-video.md`** — see "Data-model findings" below.
- **`tools/seafloor-roughness.md`** — the missing feature page: transport, the four
  tabs, metric interpretation (γ₂ load-bearing; w₂ absolute trust-gated per frame),
  the outputs, the mosaic modes, heading-offset-vs-mirror, and the QgsSettings
  override rule.

### Data-model findings (columns verified, not guessed)

Rather than assume, every relationship was checked numerically against
`groundtruther_test_dataset/projectdata.pq` (123 394 × 38) and
`mbqc_final/mbes_2015_multilevel.parquet` (14 526 619 × 18). Verified exactly:
`Xutm`/`Yutm` == `proj(Longitude, Latitude)`; `Xutm_adj`/`Yutm_adj` ==
`proj(habcam_lon, habcam_lat)`; `x`/`y` == `proj(vessel_lon, vessel_lat)`;
`hypot(dx,dy) == distance` and `atan2(dx,dy) == bearing`; median ship→USBL separation
**≈ 148 m**; `V_Depth + Altimeter ≈ Water_Depth`; `Fov ≈ Mm_pix × 1360 px`;
`DateTm == Date + DecDay`; `diff(Position) == Step` (99.999 % of rows);
`Ping Time` == epoch seconds of `datetime`. These are recorded in the new
`data-model-facts` memory entry.

Column coverage was checked mechanically: all 114 column names the plugin references
or that exist in either reference file appear in the data-model pages. **Nothing was
left undocumented.**

### Questions for the user (physical meaning not derivable from code or data)

1. **`bearing` as `heading_deg` — is the georeference 180° out?**
   > **ANSWERED, 2026-09-17: yes.** The user supplied the missing fact — the camera's
   > orientation follows the vessel, which tows it just astern — and a template-matching
   > measurement on the imagery closed it: seabed content scrolls **downward** in 62 of 62
   > confident consecutive-frame pairs (median +597 px ≈ 464 mm, against ≈ 495 mm predicted
   > from speed × interval), so image bottom→top points **forward**. The service rotates by
   > `heading_deg` bottom→top, so the correct value is the vessel heading ≈ `bearing + 180`.
   > The plugin sends `bearing`. Every georeferenced micro-DEM, orthophoto and nav-placed
   > mosaic is rotated 180° about its own centre; positions are unaffected, which is why a
   > check that verified position never caught it. Fix planned as Track 3 of
   > `PLANNING/docs-audit-code-findings.md`.
   >
   > **CLOSED, 2026-09-17 — answered *and* fixed.** Track 3 of
   > `PLANNING/docs-audit-code-findings.md` shipped the fix (PR
   > [#35](https://github.com/epifanio/groundtruther/pull/35), issue #31 closed):
   > `gt/roughness_geo.HEADING_SOURCES` now applies a per-column rule — a `Heading` column
   > as it stands, a `bearing` column reversed. The measurement was re-run from scratch
   > during execution and reproduced (content down in **60 of 60** pairs; `heading =
   > bearing` gives a median 175.1° error against the nav-derived course over ground,
   > `bearing + 180` gives 4.9°). The docs on this site were updated to state the
   > conclusion rather than the open question, and the ~5° residual is quoted as the
   > accuracy of the derived heading. The other four questions in this section remain open.

   Original wording: `bearing` is
   verifiably the direction of the (`dx`,`dy`) offset vector (base → HabCam), which
   sits **~173° (median) from the course over ground** — as expected for a body towed
   astern. `gt/roughness_geo.py` sends it as `heading_deg` when there is no `Heading`
   column (this dataset has none), and the service's convention is "image bottom→top =
   heading". Does the mount convention absorb the reciprocal, or is every georeferenced
   frame rotated 180°? The `roughness-integration` memory records the georeferencing as
   verified end-to-end, so the docs state the measured fact without asserting a bug.
   **Not changed.**
2. **`Step` / `Position` units.** `Position` is monotonic with an origin offset of
   ≈ 2.6 × 10⁶ and `diff(Position) == Step`; the magnitudes fit an along-track distance
   in metres (≈ 69 km over 6.5 h ≈ 3 m/s). Confirm? Documented as "not confirmed".
3. **`Cdom` / `Chlorophyll` / `Turb` / `O2` units.** `Cdom` takes negative values, so
   the three optical channels are clearly raw uncalibrated sensor output; `O2` ≈ 6.9–8.9
   (mg/L? ml/L?). Documented as raw / unconfirmed rather than invented.
4. **`Beam Flag` encoding.** All-zero throughout the reference file, so nothing can be
   read off the data. Documented as "the plugin does not filter on it — pre-filter
   rejected soundings yourself".
5. `Nominal Angle`, `Beam Number`, `Ping Number`, `TripDay`, `dT`, `location`, `x`/`y`,
   `sXutm`/`sYutm`, `Frame_Identifier`, `Target_Length` are documented by their verified
   behaviour and marked **"not read by the plugin"** where that is the case.

### Code bugs found — recorded, not fixed (docs-only plan)

- **[#27](https://github.com/epifanio/groundtruther/issues/27)** — seven imports in the
  video subsystem use bare `gt.…` instead of `groundtruther.gt.…`.

  > **Correction, 2026-09-17 (same day).** The effect claimed here is **wrong**. It was
  > reproduced with a hand-built `PYTHONPATH`, which is not representative. Re-tested
  > against a real `QgsApplication` + plugin load: `groundtruther.py:46` runs
  > `sys.path.append(os.path.dirname(__file__))`, and `classFactory()` imports that
  > module — so the plugin's own directory *is* on `sys.path` before any mixin runs and
  > bare `gt.…` resolves. **The video subsystem is not dead.** The real defect is that
  > `gt.video_manager` and `groundtruther.gt.video_manager` are two distinct module
  > objects (split module state, broken exception identity) and that the path append
  > publishes 19 modules + 2 packages under bare names into the QGIS-wide namespace. The
  > issue has been retitled and corrected; scope is 14 bare imports, not 7. See
  > `PLANNING/docs-audit-code-findings.md`.
  >
  > **FIXED, 2026-09-17** (PR [#35](https://github.com/epifanio/groundtruther/pull/35)).
  > It turned out to be **17** bare imports and **33** leaked names — three `pygui.…`
  > spellings the grep pattern missed, and every plugin *directory* leaking as a PEP-420
  > namespace package on top of the modules. `tests/gui/test_import_hygiene.py` guards it.
  >
  > **Lesson:** verify an import failure in the offscreen QGIS harness `CLAUDE.md`
  > describes, not in an ad-hoc `PYTHONPATH`.
- **[#28](https://github.com/epifanio/groundtruther/issues/28)** — `ioutils.parse_annotation`
  hard-codes `skiprows=[0, 1]`, so a CSV with a single header row loses its **first
  detection** (verified: 7 278 rows in, 7 277 out on the sample file). The behaviour and
  its workaround are documented on the annotations page with a warning box.

  > **Follow-up, 2026-09-17.** The `[0, 1]` is not arbitrary:
  > `pygui/annotation_editor_gui.py:473` writes `"\n\n"` before the header, so it
  > matches GroundTruther's *own* save format. The parser is therefore wrong for both of
  > its inputs, in opposite directions — an own-saved file reads back **N+1** records
  > (the header survives as a phantom row) and a detector export reads back **N−1**.
  > Details on the issue; fix planned in `PLANNING/docs-audit-code-findings.md`.
  >
  > **FIXED, 2026-09-17** (PR [#35](https://github.com/epifanio/groundtruther/pull/35)).
  > The reader moved to a Qt-free `gt/annotations.py` and now sniffs the preamble; the
  > writer emits an ordinary CSV. The warning box and its workaround were removed from the
  > annotations page.

### Deviations from the plan

- **Task 11 — `help/` was reduced to a pointer, not deleted.** The plan preferred
  deletion "after checking nothing depends on it"; something does:
  `Makefile:74,129,218` (`make doc`, `make deploy` → `cp help/build/html …`) and
  `pb_tool.cfg:73-77` (`[help] dir: help/build/html`). Deleting the tree would break
  plugin packaging, which is a build change, not a docs change. So: `help/source/index.rst`
  is now a short pointer at the site, and the two duplicated stub pages
  (`requirements/index.rst` with its stale `python=3.10` / `polars` conda recipe, and the
  empty `quickstart/index.rst`) were deleted. `make doc` still works; nothing in
  `metadata.txt` referenced `help/`.
- **`CLAUDE.md` had one factually stale line, corrected as part of task 12.** It said
  "`config/config.yaml` is tracked… the committed version has an empty `grass_api_key`".
  It is **gitignored** (since `9dfc3e6`) and the committed template is
  `config/config.example.yaml`. A new `## Documentation` section was also added (where
  the site is, that merging publishes, the three-place rule for a new config key, the
  `help/` status, and that agents leave screenshot placeholders).
- **Test-count baseline differed from the plan.** The plan predicted 287/6 without QGIS;
  the actual baseline at `5843d98` was **282 passed / 6 skipped**. Final: **286 / 6**
  without QGIS, **303 passed / 4 skipped** with `/usr/share/qgis/python` on `PYTHONPATH`
  (+4 from the new drift test).
- **`config_check.write_settings` does not use `explicit_start=True, indent=4`** (the
  `config-validation` memory says it does). Current code is
  `yaml.safe_dump(…, sort_keys=False, default_flow_style=False, allow_unicode=True)`.
  The docs describe the actual behaviour; no code was touched.

### Verification

- `mkdocs build --strict -f website/mkdocs.yml` → **built, no warnings**. (Material
  prints an unrelated red "MkDocs 2.0" advisory banner on every run, baseline included.)
- `.venv/bin/pytest` → **286 passed, 6 skipped**; with QGIS on `PYTHONPATH`
  → **303 passed, 4 skipped**.
- Drift test negative-tested: renaming one key in the page makes both directions fail.
- `website/site/` not committed (gitignored); `config/config.yaml` never staged (it is
  gitignored and does not exist in this worktree).

### Screenshot placeholders for the user to capture

Every figure still points at `assets/img/placeholder.svg`. Agents cannot drive the QGIS
GUI, so these are for you. **Two are new in this PR:**

| File | Page | What to capture |
|---|---|---|
| `settings-dialog-1.png` | `configuration/index.md` | **NEW** — the Settings dialog, scrolled so several group boxes are visible (ideally HabCam + Mbes + Seafloor roughness) |
| `roughness-metrics-1.png` | `tools/seafloor-roughness.md` | **NEW** — the Seafloor Roughness dock on the Metrics tab, with a computed frame (γ₂ populated) |
| `image-browser-1.png`, `image-browser-2.png` | `tools/image-browser.md` | pre-existing |
| `video-player-1.png` | `tools/video-player.md` | pre-existing |
| `annotation-image-1.png`, `annotation-video-1.png` | `tools/annotation.md` | pre-existing |
| `query-builder-1.png` | `tools/query-builder.md` | pre-existing |
| `report-builder-1.png` | `tools/report-builder.md` | pre-existing |
| `grass-settings-1.png`, `grass-module-1.png`, `grass-region-1.png` | `tools/grass-fastgis.md` | pre-existing |
| *(hero)* | `index.md` | pre-existing — full plugin in QGIS |

Drop the PNGs in `website/docs/assets/img/` and swap the `src` in the `<figure>` block
marked with a `TODO` comment. The catalogue in `website/docs/assets/img/README.md` has
been updated with the two new names.

### Memory

Two new entries with `MEMORY.md` pointers: **`documentation`** (where the docs live,
deploy-on-merge, the structure, the drift-test rule, the `help/` decision) and
**`data-model-facts`** (the verified column relationships above, so the next session
does not re-derive them).

### Follow-up for the user

1. `mkdocs serve -f website/mkdocs.yml` and read the Configuration section against the
   real Settings dialog (the remaining unticked acceptance criterion).
2. Answer the five questions above so the "unconfirmed" notes can be replaced.
3. Capture the two new screenshots.
4. Merge **only after** reviewing the rendered pages — merging publishes the site.
5. Then: `git worktree remove ../groundtruther-settings-docs && git branch -d docs/settings-and-data-model`.
