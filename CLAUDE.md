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
- Config is `config/config.yaml` (validated by pydantic v2 model in
  [config_model.py](config_model.py)); test data = Zenodo `groundtruther test dataset`
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
  pydantic v2 model, and the settings dialog (`ConfigDialog`).
- The three `run_*_mdi.py` are thin presets of the generic module runner.

## Conventions (match these)
- Logging: **`QgsMessageLog.logMessage(msg, 'GroundTruther', Qgis.<level>)`** — never
  `print()`. Use `configure.log_exception(context, exc, warn=?)` for tracebacks.
- Imports: **`from qgis.PyQt import ...`** (the QGIS Qt shim), not `PyQt6` directly.
- In **generated** `Ui_*.py`, Qt6 enums use the **integer-constructor form**
  (`Qt.WindowType(1)`, `QtWidgets.QSizePolicy.Policy(7)`) — `compile_ui.sh` auto-patches
  this because the qgis.PyQt shim doesn't expose scoped enum inner-classes reliably.
  Hand-written code may use scoped enums, but matching the int form is safest in UI files.
- All GRASS HTTP goes through `gt/grass_api.py` (raises `GrassApiError`); **no inline
  `requests`** in mixins/dialogs.

## CRITICAL gotchas (these will bite)
- **`config/config.yaml` is tracked but holds machine-specific paths AND the GRASS API
  key (a secret).** NEVER `git add`/commit your local `config.yaml`. Keep it as an
  uncommitted working-tree edit; the committed version has an empty `grass_api_key`.
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
