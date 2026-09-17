# Config validation hardening: no key may crash the plugin

| | |
|---|---|
| **Status** | `DONE` — executed 2026-09-17 |
| **Type** | fix |
| **Worktree branch** | `fix/config-validation-hardening` |
| **Created** | 2026-09-17 |
| **Related memory** | `config-validation`, `project-overview`, `install-and-run`, `april-2026-refactor`, `roughness-integration`, `fastgis-grass-api` |
| **Execution PR** | [#23](https://github.com/epifanio/groundtruther/pull/23) |

## Objective

A GroundTruther session must **start** no matter what `config/config.yaml` contains.
Today a single bad path anywhere in the file invalidates the *entire* config, the dock
falls back to a dict of empty strings, and the first consumer that touches one of those
empty strings dies with an opaque traceback — taking the whole plugin down before the UI
exists. When done: every config key is validated individually; an invalid **optional**
key degrades only the feature that uses it; an invalid **required** key produces a
message that *names the offending key and its value* instead of a traceback; every
consumer guards the empty/missing case; and saving from the Settings dialog no longer
silently destroys config sections it does not know about.

## Context & background

### The bug that triggered this

Real session, 2026-09-17. `HabCam.imagepath` pointed at
`/run/media/epinux/ssd1/HBC/DATA/2015_stereo`; the external drive had been remounted
under a different label (`WD_BLACK`), so the directory no longer existed. Chain:

1. [configure.py:96-119](../configure.py#L96-L119) — `validate_config()` builds a
   `HabcamSettings`; `imagepath` is a pydantic `DirectoryPath` → `ValidationError` →
   [configure.py:130](../configure.py#L130) `get_settings()` returns `None`.
2. [groundtruther_dockwidget.py:100-109](../groundtruther_dockwidget.py#L100-L109) — dock
   falls back to safe defaults, in which **every path is `""`**, including
   `"Mbes": {"soundings": ""}`.
3. [pygui/querybuilder_gui.py:562](../pygui/querybuilder_gui.py#L562) —
   `pd.read_parquet("")` → `FileNotFoundError: [Errno 2] No such file or directory: ''`.
   The surrounding `except ArrowInvalid` ([querybuilder_gui.py:590](../pygui/querybuilder_gui.py#L590))
   does not cover it, so it propagates out of `QueryBuilder.__init__` →
   `init_ui()` → `GroundTrutherDockWidget.__init__` → `GroundTruther.run()`.

So a broken **image directory** surfaced as a `FileNotFoundError` on an **MBES parquet**
path the user had set correctly. Three separate defects compound here: coarse
whole-config validation, a fallback that fabricates empty paths, and an unguarded
consumer.

### Full audit — every config key, its validation, and its failure mode

Model: [config_model.py](../config_model.py). Validator:
[configure.py:83-119](../configure.py#L83-L119) — note it constructs a **partial**
`HabcamSettings`, so `Video`, `Session`, `Roughness`, `Mbes.reference_surface` and
`Processing.grass_api_key` are **never validated at all**.

| Key | Model type | In `validate_config()` | Consumers | Failure mode when empty / invalid |
|---|---|---|---|---|
| `HabCam.imagepath` | `DirectoryPath` | yes | [dockwidget:115](../groundtruther_dockwidget.py#L115), [settings_mixin:30](../mixins/settings_mixin.py#L30), [querybuilder:556](../pygui/querybuilder_gui.py#L556) | **Fatal today** — invalidates the whole config (the reported bug) |
| `HabCam.imagemetadata` | `FilePath` | yes | [settings_mixin:35](../mixins/settings_mixin.py#L35) *(guarded: `is_file()` check)*, [querybuilder:559+568](../pygui/querybuilder_gui.py#L559) | `read_parquet("")` → `FileNotFoundError`, same crash as soundings |
| `HabCam.imageannotation` | `Optional[FilePath]` | yes | [settings_mixin:66](../mixins/settings_mixin.py#L66) *(guarded)* | Consumer is safe, but a stale path invalidates the **whole** config |
| `Mbes.soundings` | `Optional[FilePath]` | yes | [querybuilder:562](../pygui/querybuilder_gui.py#L562) | **The reported crash** — unguarded `read_parquet` |
| `Mbes.reference_surface` | `Optional[str]` | **no** | [querybuilder:563](../pygui/querybuilder_gui.py#L563) → [gt/reference_surface.py](../gt/reference_surface.py) | Guarded — falls back to the soundings surface |
| `Export.kmldir` | `Optional[DirectoryPath]` | yes | [querybuilder:730](../pygui/querybuilder_gui.py#L730), [1075-1081](../pygui/querybuilder_gui.py#L1075-L1081), [1106](../pygui/querybuilder_gui.py#L1106); [kmlsave_gui:343](../pygui/kmlsave_gui.py#L343), [487](../pygui/kmlsave_gui.py#L487), [783](../pygui/kmlsave_gui.py#L783) | `kmlsave` guarded (falls back to tempdir). **querybuilder is not**: `pathlib.Path(None)` → `TypeError`; the f-string forms silently write to a literal `None/` or `/`-rooted path |
| `Processing.gpu_avaibility` | `bool` | yes | querybuilder ×5 | Safe |
| `Processing.grass_api_endpoint` | `Optional[AnyUrl]` | yes | [dockwidget:118](../groundtruther_dockwidget.py#L118), [grassconfig:118](../grassconfig.py#L118) | Guarded — falls back to `grass_api.DEFAULT_ENDPOINT` |
| `Processing.grass_api_key` | `Optional[str]` | **no** | [grassconfig:119](../grassconfig.py#L119), [dockwidget:300-304](../groundtruther_dockwidget.py#L300-L304) | Guarded — gates cloud features off |
| `Filesystem.filemanager` | `Optional[FilePath]` | yes | [kmlsave_gui:486](../pygui/kmlsave_gui.py#L486) | Consumer guarded (error dialog), but a stale path invalidates the **whole** config |
| `Video.videofile` / `.videometadata` / `.videoannotation` | `Optional[str]` | **no** | [video_browser_mixin:178](../mixins/video_browser_mixin.py#L178), [594](../mixins/video_browser_mixin.py#L594); [video_annotation_mixin:145](../mixins/video_annotation_mixin.py#L145), [261](../mixins/video_annotation_mixin.py#L261) | Guarded — empty paths skipped, unreadable file logs a warning |
| `Session.groundtruther_project` | `Optional[str]` | **no** | [session_mixin:76](../mixins/session_mixin.py#L76) | Guarded — `None` → prompts for a path |
| `Roughness.*` | mixed | **no** | [roughness_mixin:276/372/531/1190](../mixins/roughness_mixin.py#L276), [image_browser_mixin:289](../mixins/image_browser_mixin.py#L289), [settings_mixin:118](../mixins/settings_mixin.py#L118) | Mostly guarded, but `int(... .get("epsg") or 32619)` raises `ValueError` on a non-numeric string. **Worse: the whole section is silently destroyed on save — see below** |

Non-config but the same crash class: [querybuilder_gui.py:555](../pygui/querybuilder_gui.py#L555)
`self.utmzone_string = int(self.utmzone.text())` sits **outside** the `try` and raises
`ValueError` if the UTM-zone field is blanked — again during dock construction.

### Second defect found during the audit — the Settings dialog eats `Roughness`

[configure.py:363-394](../configure.py#L363-L394) `get_gui_settings()` and
[config/templates/config_template.yaml](../config/templates/config_template.yaml)
both enumerate a **fixed** set of sections, and neither includes `Roughness`. Saving
from the Settings dialog re-renders the whole file from that template, so every
`Roughness:` key (`georeference`, `epsg`, `direct_url`, `dem_*`, `res_mm`, `n_water` —
see [config_model.py:74-132](../config_model.py#L74-L132) and the `roughness-integration`
memory) is **silently deleted**. The same mechanism would drop any future section. The
template also interpolates raw values (`key: {{value}}`), so a path containing `:` or `#`
would emit invalid YAML.

### Design direction

- **Per-key, severity-aware validation.** One bad *optional* key must never invalidate
  the config. Split findings into `errors` (the plugin genuinely cannot function:
  `HabCam.imagepath`, `HabCam.imagemetadata`) and `warnings` (set-but-invalid optional
  keys: soundings, annotations, kmldir, filemanager, reference_surface, video, session,
  roughness, GRASS endpoint/key). Return a structured report that names key, value and
  reason.
- **Put the logic in `gt/`.** Per `CLAUDE.md`, stateless logic belongs in the Qt-free
  `gt/` package so it is unit-testable — new module `gt/config_check.py`.
  `configure.validate_config()` stays as a thin back-compat wrapper (it is used by
  `write_config`, and `validate_config2` is a documented shim).
- **Degrade per-feature, not globally.** Instead of replacing the whole settings dict
  with empty strings, keep the loaded values and blank only the keys that failed, so a
  broken `imagepath` leaves the MBES query builder fully working.
- **Mount-aware hint.** A missing path under `/run/media`, `/media` or `/mnt` should say
  so ("the drive may not be mounted") — that is precisely the reported failure.

## Scope

**In scope:**
- New `gt/config_check.py`: per-key validation producing a severity-tagged report.
- Extend validation coverage to `Video`, `Session`, `Roughness`, `Mbes.reference_surface`,
  `Processing.grass_api_key` (as warnings — they must never block startup).
- Rework the dock's invalid-config path ([groundtruther_dockwidget.py:96-109](../groundtruther_dockwidget.py#L96-L109)):
  partial degradation + a message naming the offending keys + per-key `QgsMessageLog` lines.
- Guard every unguarded consumer found in the audit: `querybuilder_gui.refresh_settings()`
  (both parquet reads, `int(utmzone)`), the three `Export.kmldir` uses in
  `querybuilder_gui.py`, and the `int(epsg)` calls in `image_browser_mixin` /
  `settings_mixin`.
- Widen `except ArrowInvalid` to also catch `FileNotFoundError` / `OSError` / `ValueError`.
- Fix the `Roughness` section loss: save the config by merging into the loaded document
  and dumping with `yaml.safe_dump`, instead of re-rendering the fixed Jinja template.
- Unit tests for all of the above in `tests/unit/`.

**Out of scope:**
- Redesigning the Settings dialog UI or adding new fields (no `Roughness` widgets — the
  section is preserved on save, still hand-edited in YAML).
- Changing `config_model.py` field *types* or making currently-optional keys required.
- A config-migration/versioning scheme.
- Touching the user's own `config/config.yaml` (machine-specific, holds a secret, is
  gitignored — never stage it).
- The GRASS/FastGIS client itself (separate topic, see the `fastgis-grass-api` memory).

## Prerequisites
- Read: `CLAUDE.md`, project memory (`MEMORY.md` + `project-overview`, `install-and-run`,
  `roughness-integration`).
- No services or credentials needed — everything here is verifiable offline.
- Note the `qtui/*.ui` staleness gotcha in `CLAUDE.md`: do **not** run `compile_ui.sh`;
  `app_settings` is known-stale, so any dialog change must be hand-edited in the
  generated `pygui/Ui_app_settings_ui.py`. This plan should not need UI changes at all.

## Worktree setup
```bash
cd /home/epinux/dev/groundtruther
git fetch origin
git worktree add ../groundtruther-config-validation-hardening -b fix/config-validation-hardening origin/master
cd ../groundtruther-config-validation-hardening
```

## Task breakdown

- [x] **1. `gt/config_check.py`** — Qt-free module. `check_settings(settings: dict) -> ConfigReport`
      where `ConfigReport` carries `errors: list[Finding]`, `warnings: list[Finding]`,
      `Finding(key, value, reason, severity)` and a `.summary()` that renders
      `HabCam.imagepath: directory does not exist: '/run/media/...' (the drive may not be
      mounted)`. Required keys = `HabCam.imagepath`, `HabCam.imagemetadata`; everything
      else is a warning when set-but-invalid, and silent when unset. Include the
      removable-media hint for missing paths under `/run/media`, `/media`, `/mnt`.
- [x] **2. Validate the previously-unchecked sections** — feed `Video`, `Session`,
      `Roughness`, `Mbes.reference_surface`, `Processing.grass_api_key` through the full
      `HabcamSettings` model (or per-key checks) so bad values are *reported*; they stay
      warnings and never block startup. Include numeric sanity for `Roughness.epsg`,
      `res_mm`, `n_water`, `dem_*`.
- [x] **3. `configure.py` wiring** — `validate_config()` delegates to `check_settings()`
      (keeping its `(bool, str)` signature for `write_config` / `validate_config2`);
      add `get_settings_checked(path)` returning `(settings, report)` so callers can
      degrade per-key. Keep `get_settings()` behaviour for callers that only want a dict,
      but base "valid" on `report.errors` only — a stale optional path must no longer
      return `None`.
- [x] **4. Dock startup path** — in [groundtruther_dockwidget.py:94-109](../groundtruther_dockwidget.py#L94-L109),
      load + check, log every finding to `QgsMessageLog` (`'GroundTruther'`), and when
      there are errors show a dialog listing the offending keys/values (not the current
      bare "No valid configuration found"). Build the fallback by blanking **only** the
      failed keys over the loaded dict, and give it the full section set
      (`Video`, `Session`, `Roughness`, `Mbes.reference_surface`) so `settings[...]`
      lookups elsewhere cannot `KeyError`.
- [x] **5. `querybuilder_gui.refresh_settings()`** — skip the parquet loads when
      `soundings` / `imagemetadata` is empty or not an existing file; disable
      `query_builder_tools` + `draw_graph` and log/report instead of raising; widen
      `except ArrowInvalid` → `(ArrowInvalid, FileNotFoundError, OSError, ValueError)`;
      move `int(self.utmzone.text())` into a guarded parse with the documented default
      (`19`, per the UI default at [Ui_query_builder_ui.py:449](../pygui/Ui_query_builder_ui.py#L449)).
- [x] **6. `Export.kmldir` guards** — add one helper (e.g. `_export_dir()` mirroring
      [kmlsave_gui.py:341-344](../pygui/kmlsave_gui.py#L341-L344)'s tempdir fallback) and
      use it at [querybuilder_gui.py:730](../pygui/querybuilder_gui.py#L730),
      [1075-1081](../pygui/querybuilder_gui.py#L1075-L1081) and
      [1106](../pygui/querybuilder_gui.py#L1106) so `None` can never reach `pathlib.Path`
      or an f-string path.
- [x] **7. `int(epsg)` guards** — [image_browser_mixin.py:289](../mixins/image_browser_mixin.py#L289)
      and [settings_mixin.py:118](../mixins/settings_mixin.py#L118): wrap in a safe int
      parse falling back to `32619`.
- [x] **8. Lossless config save** — rewrite `ConfigDialog.write_config()`
      ([configure.py:400-432](../configure.py#L400-L432)) to `load_config()` the existing
      document, deep-merge the dialog's values over it, and write with `yaml.safe_dump`
      (preserving `Roughness` and any unknown section, and quoting values correctly).
      Retire or keep `config_template.yaml` only for creating a config from scratch —
      state which in the progress log.
- [x] **9. Tests** — `tests/unit/test_config_check.py`: every key empty / missing /
      wrong-type; an invalid optional key yields a warning and a *usable* settings dict;
      an invalid required key yields an error naming the key; the removable-media hint
      fires for `/run/media/...`; regression test reproducing the reported chain (a
      missing `imagepath` must NOT blank `Mbes.soundings`). Plus a test that a
      save-round-trip through the new `write_config` merge preserves a `Roughness`
      section. Extend `tests/unit/test_config_model.py` if model coverage gaps appear.
- [x] **10. Docs + memory** — note the new validation behaviour in `CLAUDE.md`'s gotchas
      if it changes an agent-visible rule; add/update a project-memory entry
      (`config-validation`) describing per-key severity, the `Roughness`-on-save fix and
      the removable-media failure mode, with a `MEMORY.md` pointer.

## Acceptance criteria & verification

- [x] `.venv/bin/pytest` green (unit; gui/integration auto-skip) — currently 188 passed,
      5 skipped; new tests add to that.
- [x] Headless import/construct check per `CLAUDE.md` passes.
- [x] Headless regression for the reported bug: build a settings dict with a nonexistent
      `HabCam.imagepath` **and a valid `Mbes.soundings`**, run it through the new check —
      one error for `imagepath`, `soundings` untouched, no exception.
- [x] No consumer in the audit table can raise on an empty/`None` value: grep shows every
      `read_parquet`, `pathlib.Path(...)`, `int(...)` fed from settings is guarded.
- [x] `write_config` round-trip preserves a hand-added `Roughness:` section (unit test).
- [ ] **Manual GUI check by the user** (agents cannot drive the QGIS GUI):
      1. Temporarily point `HabCam.imagepath` at a nonexistent directory (simulating the
         unmounted drive), restart/reload the plugin → the dock **opens**, with a message
         naming `HabCam.imagepath`; the query builder still loads the MBES parquet.
      2. Blank `Mbes.soundings` → dock opens, query-builder tools disabled with a clear
         message, no traceback.
      3. Open Settings, change nothing, Save → `config/config.yaml` still contains the
         `Roughness:` section (add one by hand first if absent).
      4. Restore the real paths → everything behaves as before.

## Risks & rollback

- **Risk: over-permissive startup.** Making previously-fatal validation non-fatal could
  let the plugin start in a half-configured state and fail later, more obscurely.
  Mitigation: keep `HabCam.imagepath` / `imagemetadata` as hard errors, and make every
  warning visible in both the message log and the status bar.
- **Risk: `get_settings()` semantics change.** Several callers
  (`settings_mixin._apply_settings`, `querybuilder.refresh_settings`, `kmlsave_gui.filemanager`,
  `grassconfig._load_conn`) treat a falsy return as "keep the old settings". Returning a
  dict where they previously got `None` changes that path — review each of those call
  sites rather than assuming.
- **Risk: YAML save rewrite.** Switching from the Jinja template to `safe_dump` changes
  the file's formatting (key order, quoting). Harmless to the loader, but the user's file
  will look different after the first save; mention it in the PR description. Back up
  `config/config.yaml` before any manual GUI check.
- **Never stage `config/config.yaml`** — machine-specific and holds the GRASS API key.
- **Rollback:** the work lives in a worktree on `fix/config-validation-hardening`; drop
  the branch/worktree and nothing in the main copy (or the live QGIS symlink) is affected.

## Kickoff prompt
```
You are working on the GroundTruther QGIS plugin (QGIS 4 / Qt6). Execute the plan in
PLANNING/TODO_config-validation-hardening.md end to end.

First: read CLAUDE.md and review the project memory (your recalled memories + the
MEMORY.md index). Then create the dedicated worktree exactly as the plan's "Worktree
setup" section specifies (branch: fix/config-validation-hardening).

Then complete the Task Breakdown and meet the Acceptance Criteria. The plan's audit
table lists every config key and its current failure mode — treat it as the checklist
of consumers to guard, and re-verify it against the source rather than trusting it
blindly. Do not touch config/config.yaml, and never stage it.

When done: run .venv/bin/pytest plus the headless checks, update the project memory with
your findings, fill the Progress Log in the plan, rename
PLANNING/TODO_config-validation-hardening.md → PLANNING/config-validation-hardening.md
(Status: DONE), and open a PR against master (gh, account epifanio). Do NOT merge — I
will review and merge, and I will run the manual QGIS GUI checks listed in the
Acceptance Criteria.
```

## Progress log

**2026-09-17 — executed in worktree `../groundtruther-config-validation-hardening`
(branch `fix/config-validation-hardening`), PR
[#23](https://github.com/epifanio/groundtruther/pull/23).**

### What was built

**1. `gt/config_check.py` (new, 500 lines, Qt-free).** A declarative `SPEC` of 26
`KeySpec` entries — one per config key — each with a `kind` (`dir`, `file`,
`parent_dir`, `url`, `bool`, `int`, `float`, `str`), a `required` flag, optional numeric
bounds, and the `blank` value it degrades to. `check_settings()` walks it and returns a
`ConfigReport(errors, warnings)` of `Finding(key, value, reason, severity)`; `.summary()`
renders `HabCam.imagepath: directory does not exist: '/run/media/…' (the drive may not be
mounted)` and `.message()` builds the user-facing dialog text. `degrade(settings, report)`
returns a **usable** dict: only failed keys blanked, every section present.
Also exports the coercion helpers the consumers now use — `as_int`, `as_float`,
`as_bool`, `as_path_str` — and the document helpers `merge_settings` / `write_settings`.

**2. Coverage extended to the never-validated sections.** `Video`, `Session`,
`Roughness`, `Mbes.reference_surface` and `Processing.grass_api_key` are now checked
(all as warnings), including numeric sanity for `Roughness.epsg` (EPSG range),
`res_mm`, `n_water`, `dem_max_side`, `dem_trim_border`, `dem_clip_sigma`, `dem_erode`.
`Session.groundtruther_project` is validated as `parent_dir` — the file itself is
created on first save, so only its directory has to exist.

**3. `configure.py`.** `validate_config()` keeps its `(bool, str)` signature but
delegates to `check_settings()`, and "valid" now means *no errors*. New
`get_settings_checked(path) -> (settings, report)`; `check_config(settings) -> report`.
`get_settings()` still returns `None` on a fatal problem — but a stale **optional** path
no longer vetoes the file.

**4. Dock startup.** `GroundTrutherDockWidget._load_settings()` loads, logs every
finding to `QgsMessageLog` (`Critical` for errors, `Warning` for warnings), opens the
Settings dialog once on a fatal finding, and — if still fatal — shows a dialog naming the
offending keys and their values. The result is `degrade()`d, so the old
"dict of empty strings" fallback is gone. The report is kept on `self.config_report`.

**5–7. Consumers guarded.** `querybuilder_gui.refresh_settings()` pre-checks both
parquet paths with `os.path.isfile` and disables the tools with a message instead of
raising; `except ArrowInvalid` widened to `(ArrowInvalid, FileNotFoundError, OSError,
ValueError)`; `int(self.utmzone.text())` → `as_int(..., DEFAULT_UTM_ZONE=19)`. A new
`_export_dir()` (tempdir fallback, mirroring `kmlsave_gui`) replaced all three raw
`Export.kmldir` uses. `int(epsg)` in `image_browser_mixin` / `settings_mixin` and every
`int()`/`float()` over `Roughness.*` in `roughness_mixin` now go through the coercion
helpers.

**8. Lossless save.** `ConfigDialog.write_config()` now `load_config()`s the existing
document, deep-merges the dialog's values over it (`merge_settings`) and writes with
`yaml.safe_dump` (`write_settings`). `Roughness` — and any future/unknown section —
survives a save.

**9. Tests.** `tests/unit/test_config_check.py`, 100 tests. Suite: **282 passed,
5 skipped** (was 188/5).

### Decisions / deviations from the plan

- **`config/templates/config_template.yaml` was deleted, not kept.** With the merge-based
  save it is dead code, and leaving a template that silently eats `Roughness` is a trap.
  A missing config file merges into `{}` and produces a complete document, so
  create-from-scratch still works. `config/templates/` itself stays — `kmlsave_gui` uses
  `report.html.j2` from it. The now-unused `starlette`/`Jinja2Templates` import was
  dropped from `configure.py` (the package is left in `requirements.txt`).
- **Validation is per-key stdlib checks, not per-key pydantic.** Feeding keys through
  `HabcamSettings` one at a time gave worse messages and no real gain. `config_model.py`
  stays the **schema of record**, and `test_spec_covers_exactly_the_pydantic_model`
  asserts `SPEC` covers exactly its fields, so the two cannot silently drift. As a
  consequence `configure.py` no longer imports `HabcamSettings` (or pydantic) at all.
- **Two items in the plan's audit table were already guarded.** `settings_mixin:118` and
  `image_browser_mixin:289` sat inside `try: … except Exception` blocks, so they could not
  actually raise. They were still converted to `as_int` — it removes a blanket
  `except Exception` and centralises the default. The *genuinely* unguarded `int()`/
  `float()` calls were in `roughness_mixin` (lines 281/291/300, 375–381, 534–537,
  1204–1206), which the table did not break out.
- **Three defects found beyond the audit, all fixed:**
  1. `settings_mixin` did `Path(self.imageannotationfile).is_file()` — `Path(None)`
     raises `TypeError`, so a config with an *empty* `imageannotation:` broke image
     metadata loading entirely (swallowed by the broad `except Exception` into an
     "Error reading …" dialog).
  2. `ConfigDialog._populate_fields()` did `setText(hbc.get("imagepath", ""))` — a key
     present with an empty YAML value reads back as `None`, and `QLineEdit.setText(None)`
     raises. Opening Settings on a half-empty config crashed.
  3. `get_gui_settings()` returned `"videoannotation": None`; under the new merge that
     would overwrite a hand-edited value, so the key is now simply omitted.
- **`refresh_settings(quiet=…)`.** It runs from `QueryBuilder.__init__`, so an
  unconfigured `Mbes.soundings` would have greeted the user with a modal before the UI
  existed. `__init__` passes `quiet=True` (log only); explicit reloads and
  `settings_saved` still show the dialog. `*_args` swallows the `checked` flag Qt passes
  from the button connection.
- **`get_images` / `get_point`** (wired to a combo-box change, re-reading parquet long
  after startup) were not in the plan but had the same unguarded `read_parquet`; both now
  go through a `_read_parquet()` helper that logs and returns `None`.

### Verification

- `.venv/bin/pytest` → **282 passed, 5 skipped** (gui + integration auto-skip).
- Headless import of all 9 touched modules under `QT_QPA_PLATFORM=offscreen` → ok.
- `qgis.utils.loadPlugin("groundtruther")` against the worktree → `True`.
- Headless end-to-end script (scratchpad): the reported chain reproduces as
  **one error for `HabCam.imagepath` with the removable-media hint, `Mbes.soundings`
  untouched**; a stale `Export.kmldir` is a warning and `get_settings()` no longer
  returns `None`; a real offscreen `ConfigDialog.write_config()` round trip preserves the
  `Roughness` section.
- `config/config.yaml` was **not** touched or staged.

### Note for the reviewer

The first Settings save after this change **rewrites `config/config.yaml` with
`yaml.safe_dump` formatting** (2-space indent, explicit `null`, quoted values where
needed, `---` header gone). The content is equivalent and the loader is unaffected, but
the file will look different — back it up before the manual GUI checks.

### Follow-ups (not done, out of scope)

- The Settings dialog still has no `Roughness` widgets; the section is preserved but
  hand-edited in YAML.
- `starlette` is now unused by the plugin and could be dropped from
  `dependencies/requirements.txt` / `environment.yml`.
- Worktree cleanup after merge: `git worktree remove ../groundtruther-config-validation-hardening`
  and `git branch -d fix/config-validation-hardening`.

