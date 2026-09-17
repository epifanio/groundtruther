# TODO — Document every setting and every data model, and audit the existing docs

| | |
|---|---|
| **Status** | `PLANNED` |
| **Type** | docs |
| **Worktree branch** | `docs/settings-and-data-model` |
| **Created** | 2026-09-17 |
| **Related memory** | `config-validation`, `roughness-integration`, `fastgis-grass-api`, `install-and-run`, `project-overview`, `april-2026-refactor` |
| **Execution PR** | _(filled in by the execution agent)_ |

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

- [ ] **1. Audit pass — record before changing.** Read all 12 existing pages against the
      current code and write the findings into the Progress Log as a table
      (page → claim → status: current / stale / missing). Check specifically for: the
      QGIS 4 / Qt6 port, the `.venv` install route (`install-and-run` memory), the
      mixin architecture, the FastGIS endpoint + `X-API-Key` model (the old
      `mbapi.wps.met.no` endpoint must not survive anywhere), and the video player.
- [ ] **2. `configuration/index.md`** — what the config is, where it lives, that it is
      per-install and holds a secret (`grass_api_key`), how to open Settings, and how
      the file is written (merge + `yaml.safe_dump`, so hand-edited sections survive).
- [ ] **3. `configuration/settings-reference.md`** — every key, grouped by section, as a
      table: key · type · default · required/optional · what it does · effect when unset
      or wrong. Generate the requiredness column from `gt/config_check.SPEC`, not by
      hand. Cover all 27 keys including the 13 `Roughness.*`.
- [ ] **4. `configuration/validation.md`** — the per-key severity model: which two keys
      are fatal, that everything else degrades one feature, where the findings appear
      (the `GroundTruther` message log), and a troubleshooting table of real failure
      messages → cause → fix. Include the unmounted-drive case
      (`/run/media/...` + "the drive may not be mounted"), which is the failure that
      motivated the validation work.
- [ ] **5. `data-model/image-metadata.md`** — the HabCam parquet: every column the
      plugin reads, with dtype, units and physical meaning; which are **required** vs
      optional; the derived `usbl_lon`/`usbl_lat` columns GroundTruther adds at load.
      Must state the positioning hierarchy from "Context" fact 1 explicitly, including
      why `sXutm`/`sYutm` is never a seafloor position.
- [ ] **6. `data-model/mbes-soundings.md`** — the soundings parquet: geometry columns,
      the `BS_*` backscatter family and how `gt/mbes_fields.detect_backscatter_fields`
      picks between them, angle columns, `Beam Flag`, and the field names the query
      builder expects to match.
- [ ] **7. `data-model/annotations-and-video.md`** — the annotation CSV columns
      (`ioutils.parse_annotation`), the video metadata CSV
      (`VideoSettings` docstring + `gt/video_manager.py`), and the per-frame video
      annotation format.
- [ ] **8. `tools/seafloor-roughness.md`** — the missing feature page: what it computes,
      the four tabs, the request/response contract at the level a user needs,
      the outputs (micro-DEM, orthophoto, spectrum, GeoTIFFs), and a georeferencing
      section explaining **heading offset** (continuous rotation correction, applied to
      the nav heading server-side) versus **mirror** (discrete port/starboard handedness
      flip — a reflection no rotation can undo), with the symptom that tells them apart.
      State the QgsSettings-override rule from "Context" fact 2.
- [ ] **9. Fix what the audit found** in the existing pages; add a "Configuration" link
      from `installation/index.md` where `config.yaml` is currently mentioned in passing.
- [ ] **10. `mkdocs.yml` nav** — add Configuration and Data model sections and the
      roughness tool page. Keep the existing ordering convention.
- [ ] **11. `help/` decision** — retire it (preferred: delete, leaving the site as the
      single doc surface) or reduce `index.rst` to a pointer. State which and why in the
      Progress Log; check nothing in `Makefile` / `pb_tool.cfg` / `metadata.txt` depends
      on it before deleting.
- [ ] **12. Keep it current** — add a line to `CLAUDE.md`'s conventions: a new config key
      means `config_model.py` + `config_check.SPEC` + a row in the settings reference.
      Consider a unit test asserting every `SPEC` key appears in
      `website/docs/configuration/settings-reference.md`, so the docs cannot silently
      drift (this is the one code change the plan allows; put it in `tests/unit/`).
- [ ] **13. Memory** — add a `documentation` memory entry (where the docs live, how they
      deploy, the audit's conclusions, the `help/` decision) with a `MEMORY.md` pointer.

## Acceptance criteria & verification

- [ ] `mkdocs build --strict -f website/mkdocs.yml` succeeds with no warnings
      (strict catches broken internal links and pages missing from the nav).
- [ ] `.venv/bin/pytest` green — 304 passed / 4 skipped with QGIS on `PYTHONPATH`,
      287 / 6 without, plus the new drift test from task 12.
- [ ] Every key in `gt/config_check.SPEC` appears in the settings reference —
      verified mechanically, not by eye.
- [ ] Every column the plugin reads by name appears in the data-model pages. Derive the
      list by grepping the source for string literals used as column keys; list any
      column deliberately left undocumented in the Progress Log.
- [ ] No page still refers to QGIS 3, PyQt5, the old `mbapi.wps.met.no` endpoint, or a
      pip/conda install route contradicted by the `install-and-run` memory.
- [ ] Screenshot placeholders are listed explicitly in the PR description so the user
      knows exactly which images to capture.
- [ ] `website/site/` is not committed; `config/config.yaml` is not staged.
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
