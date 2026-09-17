# GroundTruther — agent guide

QGIS **4 / Qt6** plugin for **seafloor characterization**: jointly browse and analyse
multibeam echo-sounder (MBES) data, seafloor imagery (HabCam), and survey video,
with toolboxes that call a remote **GRASS GIS** service for bathymetric derivatives,
backscatter queries, and arbitrary GRASS modules. It runs **inside QGIS** (not
standalone). Published at https://plugins.qgis.org/plugins/groundtruther/.

This file orients an AI agent. Deep-dive on the GRASS subsystem: [docs/grass_fastgis.md](docs/grass_fastgis.md).

## Run / develop (Linux)
- QGIS 4.0+ runs on **system Python 3.14** (PEP-668, no pip). Plugin Python deps live
  in a **`.venv`** beside the source (created `--system-site-packages`); the plugin's
  [__init__.py](__init__.py) `_bootstrap_venv()` appends it to `sys.path` at load, so
  deps resolve regardless of how QGIS launches.
- Install = **symlink** this dir into the QGIS profile and enable it:
  `~/.local/share/QGIS/QGIS4/profiles/default/python/plugins/groundtruther → <repo>`
  (folder MUST be named `groundtruther` — code imports `from groundtruther...`).
- **Launch with `QT_QPA_PLATFORM=xcb qgis`** on Wayland, otherwise floating dock
  widgets can't be dragged/repositioned. After code changes, reload via the
  **Plugin Reloader** plugin (or restart QGIS).
- Config is `config/config.yaml`, validated **per key** by
  [gt/config_check.py](gt/config_check.py) (`config_model.py` is the schema of
  record); test data = Zenodo `groundtruther test dataset`
  (CC-BY-4.0, https://zenodo.org/records/7995674).

## Architecture
- **Entry:** [__init__.py](__init__.py) `classFactory` → [groundtruther.py](groundtruther.py)
  `GroundTruther` (the `QgisPlugin`: toolbar, actions, `initGui`/`unload`, dock
  registration).
- **Main dock:** [groundtruther_dockwidget.py](groundtruther_dockwidget.py) — a thin
  orchestrator (~240 lines). Real logic lives in **`mixins/`**, each a focused mixin
  combined into the dock class:
  - `image_browser_mixin.py` — image nav/display, metadata panel, annotation overlay,
    LRU image cache, `MyImageView`; the central viewer + zoom-to.
  - `video_browser_mixin.py` / `video_annotation_mixin.py` — video player dock, GPS
    geo-link, per-frame annotations.
  - `grass_mixin.py` — GRASS connectivity, region set/show, raster query, layer
    context-menu "send to env" (see GRASS doc).
  - `annotation_editor_mixin.py`, `report_dock_mixin.py`, `settings_mixin.py`,
    `layout_mixin.py` (dock persistence), `toolbar_icons.py`.
- **`gt/`** — stateless, testable, no-Qt helpers: `grass_api.py` (HTTP client),
  `image_manager.py` (metadata/KDTree), `video_manager.py`, `task_runner.py`
  (`QgsTask` poller for async GRASS modules).
- **`pygui/`** — UI: `Ui_*.py` (pyuic6-generated from `qtui/*.ui`) + hand-written
  widget classes that subclass them (`*_gui.py`), plus `grass_module_form.py` /
  `grass_module_runner.py` (schema-driven GRASS module dialogs).
- **`config/`** + `config_model.py` + [configure.py](configure.py) — YAML config,
  pydantic v2 schema, and the settings dialog (`ConfigDialog`). Validation itself
  lives in `gt/config_check.py` (see the config rules below).
- The three `run_*_mdi.py` are thin presets of the generic module runner.

## Conventions (match these)
- Logging: **`QgsMessageLog.logMessage(msg, 'GroundTruther', Qgis.<level>)`** — never
  `print()`. Use `configure.log_exception(context, exc, warn=?)` for tracebacks.
- Imports: **`from qgis.PyQt import ...`** (the QGIS Qt shim), not `PyQt6` directly.
- **Intra-plugin imports are always `from groundtruther… import …`** — never a bare
  `from gt.… import` / `import ioutils`, and **never append the plugin directory to
  `sys.path`** (only `__init__.py`'s `_bootstrap_venv` may touch `sys.path`, and it
  adds the venv). QGIS puts the *plugins* dir on the path, not the plugin's own, so a
  bare name only resolves if something has polluted the path — and then the module is
  loaded **twice**, under two names, with its module-level state duplicated, in a
  `sys.modules` shared with every other plugin. `tests/gui/test_import_hygiene.py`
  fails if this comes back.
- In **generated** `Ui_*.py`, Qt6 enums use the **integer-constructor form**
  (`Qt.WindowType(1)`, `QtWidgets.QSizePolicy.Policy(7)`) — `compile_ui.sh` auto-patches
  this because the qgis.PyQt shim doesn't expose scoped enum inner-classes reliably.
  Hand-written code may use scoped enums, but matching the int form is safest in UI files.
- All GRASS HTTP goes through `gt/grass_api.py` (raises `GrassApiError`); **no inline
  `requests`** in mixins/dialogs.
- **Config values are untrusted.** Never do `int(settings[...])`, `Path(settings[...])`,
  `read_parquet(settings[...])` or f-string a settings value into a path directly — a
  key can be absent, `None`, or junk. Use `gt/config_check.py`'s `as_int` / `as_float` /
  `as_bool` / `as_path_str`, and check `os.path.isfile/isdir` before reading.

## CRITICAL gotchas (these will bite)
- **`config/config.yaml` holds machine-specific paths AND the GRASS API key (a
  secret).** It is **gitignored** (`config/config.yaml` in `.gitignore`, since
  9dfc3e6); the committed template is `config/config.example.yaml`. Never
  `git add -f` it, and never paste it into an issue or a log.
- **Config validation is per key and severity-aware** ([gt/config_check.py](gt/config_check.py)).
  Only `HabCam.imagepath` + `HabCam.imagemetadata` are *errors* (they block startup);
  every other key is a *warning* when set-but-invalid and silent when unset, so one
  stale path can only disable its own feature. `configure.get_settings_checked()` returns
  `(settings, report)`; `config_check.degrade()` blanks **only** the failed keys. Adding a
  config key means adding it in **three** places: `config_model.py`,
  `config_check.SPEC`, and a row in
  [website/docs/configuration/settings-reference.md](website/docs/configuration/settings-reference.md).
  Two unit tests enforce the chain — `tests/unit/test_config_check.py`
  (`test_spec_covers_exactly_the_pydantic_model`) and
  `tests/unit/test_settings_docs.py` — so a key added in only one or two of them
  fails the suite.
- **The Settings dialog saves by *merging* into the file on disk** (`config_check.merge_settings`
  + `yaml.safe_dump`), not by re-rendering a template. Do not reintroduce a fixed template:
  the old `config/templates/config_template.yaml` had no `Roughness:` block, so every save
  silently deleted that section. A dialog field you do not add to `get_gui_settings()` is
  simply preserved.
- **`ConfigDialog` must init exactly one base: `QDialog.__init__(self, parent)` — never
  `super()`.** `ConfigDialog(QDialog, AppSettings)` inherits two `QWidget`s, so PyQt's
  cooperative init walks on to `AppSettings.__init__`, which calls `setupUi()` a *second*
  time; the attribute references then point at the newer widget set while the older one is
  what's shown, so the dialog looks unpopulated and is missing every programmatic row —
  and **the tests still pass**. `tests/gui/test_config_dialog.py::test_the_ui_is_built_exactly_once`
  counts the widgets to catch it.
- **New settings widgets are added programmatically in `ConfigDialog`, not to the `.ui`**
  (`_add_reference_surface_row`, `_add_video_annotation_row`, `_add_roughness_box`) —
  `qtui/app_settings.ui` is stale, so regenerating it would drop them. The dialog now has a
  widget for every key in `config_model.py`; a coverage test enforces that.
- **`qtui/*.ui` files are STALE vs the generated `pygui/Ui_*.py`.** Video widgets and
  others were hand-added directly to the generated `.py`; the `.ui` was never updated.
  **Do NOT run `compile_ui.sh` wholesale** — it regenerates from stale `.ui` and silently
  drops widgets. Hand-edit the generated `.py`, or regenerate only a `.ui` you've
  verified is current. (`app_settings` and `grass_settings` are known-stale.)
- **Don't register child docks on the inner `self.w` QMainWindow** — it triggers a Qt6
  `QToolBar::widgetForAction` crash during QGIS dock-walk. Register docks with the QGIS
  main window via `iface.addDockWidget(...)` (see how image/GRASS docks do it).
- **You can't reliably launch the QGIS GUI from an agent shell** (it exits with no
  output). Verify with the headless patterns below; the live GUI is the user's job.

## Documentation
- **User-facing docs are the MkDocs Material site in [website/](website/)**, published to
  <https://epifanio.github.io/groundtruther/> by `.github/workflows/docs.yml` on every
  push to `master` touching `website/**` — **merging a `website/` change publishes it**.
  Check with `mkdocs build --strict -f website/mkdocs.yml` (strict catches broken
  internal links and pages missing from the nav). `website/site/` is a build artifact —
  never commit it.
- Sections: Installation · Tools (one page per feature) · **Configuration** (all 27
  keys + the validation model) · **Data model** (every column the plugin reads) ·
  Architecture. Adding a *feature* means adding its tool page **and** its config keys
  to the settings reference.
- `docs/grass_fastgis.md` is agent-facing and stays separate from the site.
  `help/` is a retired Plugin Builder Sphinx stub, reduced to a pointer at the site
  and kept only because `Makefile` / `pb_tool.cfg` expect `help/build/html` to exist —
  **do not add docs there.**
- Screenshots live in `website/docs/assets/img/`; pages that need one point at
  `placeholder.svg` with a `TODO` comment naming the expected file. Agents cannot
  capture them — leave the placeholder and tell the user which image to take.

## Testing
- **Test suite: `tests/`** (`unit/` = no QGIS/network, `gui/` = offscreen Qt,
  `integration/` = live API, opt-in). Run `.venv/bin/pytest` (unit runs; gui +
  integration auto-skip). See [tests/README.md](tests/README.md). Prefer adding
  logic to the stateless `gt/` package so it can be unit-tested. `conftest.py`
  stubs `groundtruther.configure` so `gt/` imports stay QGIS-free.
- Ad-hoc syntax check: `.venv/bin/python -m py_compile <files>`.
- Import/construct under QGIS offscreen — make `groundtruther` resolve to the repo:
  ```bash
  QT_QPA_PLATFORM=offscreen \
  PYTHONPATH="<repo>/.venv/lib/python3.14/site-packages:/usr/share/qgis/python" \
  .venv/bin/python - <<'PY'
  import sys, types, pathlib
  ROOT = pathlib.Path("<repo>")
  pkg = types.ModuleType("groundtruther"); pkg.__path__=[str(ROOT)]; sys.modules["groundtruther"]=pkg
  sys.path.insert(0, str(ROOT))
  from qgis.PyQt.QtWidgets import QApplication; app = QApplication([])
  import importlib; importlib.import_module("groundtruther.groundtruther")
  print("ok")
  PY
  ```
- Authoritative load check: init a `QgsApplication(offscreen)` and
  `qgis.utils.loadPlugin("groundtruther")` (add the profile plugins dir to `sys.path`).
- For pure `gt/` helpers, stub `groundtruther.configure.log_exception` to avoid pulling
  in Qt/UI.

## Git
- Work on a branch off `master`; open a PR (`gh`, account `epifanio`). The user merges.
- **Never stage `config/config.yaml`.** End commit messages with
  `Co-Authored-By: Claude <noreply@anthropic.com>`.

## Planning workflow
Non-trivial work (features, multi-file fixes, refactors, migrations) is **planned first**
in `PLANNING/` — see [PLANNING/README.md](PLANNING/README.md) and the rules in
[PLANNING/planning_rules.md](PLANNING/planning_rules.md).
- **Two flows, two branches:** *authoring* a plan is a doc change on `docs/plan-<topic>`;
  *executing* it happens later on `<type>/<topic>` with its own PR.
- **Execution runs in a dedicated worktree** (`git worktree add ../groundtruther-<topic>
  -b <type>/<topic> origin/master`) so parallel sessions and the live QGIS symlink (which
  points at this main copy) never collide.
- A plan is started by copying [PLANNING/TEMPLATE_planning.md](PLANNING/TEMPLATE_planning.md)
  → `PLANNING/TODO_<topic>.md`; its **kickoff prompt** is pasted into a fresh agent session,
  which reads `CLAUDE.md` + the project memory *first*.
- **Two prompts:** the *authoring* prompt (in `PLANNING/README.md`) turns the user's raw notes
  into a filled plan; the *kickoff* prompt at the end of each plan executes it. If you are
  handed notes for substantial work, offer to author a plan rather than start coding.
- **Done** = tests green, project memory updated, Progress Log filled, `TODO_` prefix
  dropped (`Status: DONE`), work PR opened and left for the user to merge.
