# GroundTruther — agent guide

QGIS **4 / Qt6** plugin for **seafloor characterization**: jointly browse and analyse
multibeam echo-sounder (MBES) data, seafloor imagery (HabCam), and survey video,
with toolboxes that call a remote **GRASS GIS** service for bathymetric derivatives,
backscatter queries, and arbitrary GRASS modules. It runs **inside QGIS** (not
standalone). Published at https://plugins.qgis.org/plugins/groundtruther/.

This file orients an AI agent. Deep-dive on the GRASS subsystem: [docs/grass_fastgis.md](docs/grass_fastgis.md).

## Run / develop (Linux; the macOS differences are called out)
- QGIS 4.0+ runs on **system Python 3.14** (PEP-668, no pip). Plugin Python deps live
  in a **`.venv`** beside the source (created `--system-site-packages`); the plugin's
  [__init__.py](__init__.py) `_bootstrap_venv()` appends it to `sys.path` at load, so
  deps resolve regardless of how QGIS launches.
- Install = **symlink** this dir into the QGIS profile and enable it:
  `~/.local/share/QGIS/QGIS4/profiles/default/python/plugins/groundtruther → <repo>`
  (folder MUST be named `groundtruther` — code imports `from groundtruther...`).
- **On macOS the profiles root is elsewhere, and it is `QGIS4`, not `QGIS3`:**
  `~/Library/Application Support/QGIS/QGIS4/profiles/<profile>/python/plugins/groundtruther`
  (same folder-name rule). Measured on QGIS 4.2.1 by `mac-install-test`, 2026-10-24.
  Note that a profile installed from a **release zip holds a COPY of the plugin, not a
  symlink** — checking a later change there shows the OLD code until you reinstall
  (`scripts/make-release-zip.sh <tag>`, then unpack over it; move any `.venv` aside and
  put it back). The two test profiles `gt-mac-test` (with `.venv`) and `gt-mac-novenv`
  (Plugin-Manager-equivalent) on the owner's Mac are copies of this kind — don't delete
  them, other rows want them.
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

Each of these is now a **decision record** — the record is the authority and carries the reasoning,
the scope and what it rules out; this list is the short form a session reads every turn. Cited by
number, never re-decided ([PLANNING/DECISIONS.md](PLANNING/DECISIONS.md)). Two of them are enforced
in CI by `check_planning.py` rule D4 over the directories named in the record, so a violation there
fails the build.

- Logging: **`QgsMessageLog.logMessage(msg, 'GroundTruther', Qgis.<level>)`** — never
  `print()`. Use `configure.log_exception(context, exc, warn=?)` for tracebacks. **D-003** —
  enforced in `mixins/` and `gt/`; older top-level files and `pygui/` still have a `print()` backlog.
- Imports: **`from qgis.PyQt import ...`** (the QGIS Qt shim), not `PyQt6` directly. **D-004** —
  **no violations left** since `sip-shim-d004` (2026-10-24): `from qgis.PyQt import sip` was
  measured working in QGIS 4.2.1, so `mixins/video_browser_mixin.py` now goes through the shim
  like everything else. D-004 still carries no `enforce:` line; adding one is the follow-up
  record the decision itself asks for.
- **Intra-plugin imports are always `from groundtruther… import …`** — never a bare
  `from gt.… import` / `import ioutils`, and **never append the plugin directory to
  `sys.path`** (only `__init__.py`'s `_bootstrap_venv` may touch `sys.path`, and it
  adds the venv). QGIS puts the *plugins* dir on the path, not the plugin's own, so a
  bare name only resolves if something has polluted the path — and then the module is
  loaded **twice**, under two names, with its module-level state duplicated, in a
  `sys.modules` shared with every other plugin. `tests/gui/test_import_hygiene.py`
  fails if this comes back. **D-001**.
- In **generated** `Ui_*.py`, Qt6 enums use the **integer-constructor form**
  (`Qt.WindowType(1)`, `QtWidgets.QSizePolicy.Policy(7)`) — `compile_ui.sh` auto-patches
  this because the qgis.PyQt shim doesn't expose scoped enum inner-classes reliably.
  Hand-written code may use scoped enums, but matching the int form is safest in UI files.
  See also **D-005**: the generated `.py` is the truth, and `compile_ui.sh` is never run wholesale.
- All GRASS HTTP goes through `gt/grass_api.py` (raises `GrassApiError`); **no inline
  `requests`** in mixins/dialogs. **D-002** — enforced in `mixins/` and `pygui/`.
- **Config values are untrusted.** Never do `int(settings[...])`, `Path(settings[...])`,
  `read_parquet(settings[...])` or f-string a settings value into a path directly — a
  key can be absent, `None`, or junk. Use `gt/config_check.py`'s `as_int` / `as_float` /
  `as_bool` / `as_path_str`, and check `os.path.isfile/isdir` before reading. This is also rule 3
  of the session conventions (`PLANNING/WORKFLOW.md` §5.2), which every plan cites.

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
- **Never let a QMainWindow that owns an `addToolBar()` toolbar sit inside a dock registered
  on the QGIS main window.** That is what triggers the Qt6 `QToolBar::widgetForAction` crash
  during QGIS's dock-walk: `addToolBar()` and `QToolBar.addWidget()` create wrapper actions,
  and Qt dereferences their widget mapping when it walks the tree during a dock move. `self.w`
  is stripped of its toolbar *and* all its docks in `init_ui` for exactly this reason, and
  `_image_toolbar` is a plain `QToolBar` in a `QVBoxLayout` rather than `addToolBar()`.
  Registering **docks** on a freshly-created inner QMainWindow is *not* the cause and is done
  three times today — `_image_inner_window` (image metadata, annotation editor) and
  `_video_inner_window` (video annotations); `9ffac03` ("dock stability") says so in the code.
  The last site that still matched — `GrassTools.addToolBar("GrassModules")`, embedded via
  `gisToolSplitter` in the `gisTools` dock — was converted to the plain-`QToolBar` form, and
  `GrassTools` is now a plain **`QWidget`** rather than a `QMainWindow`, so it cannot reach
  `addToolBar()` at all. **No embedded window registers a toolbar any more**, and
  `tests/unit/test_embedded_toolbar_shape.py` fails if one comes back (it guards the base class
  too). Neither change was ever seen to fix a crash — the panel needs GRASS enabled, and the
  walk does not reproduce offscreen — so they remove the configuration, not an observed fault.
- **You can't reliably launch the QGIS GUI from an agent shell** (it exits with no
  output). Verify with the headless patterns below; the live GUI is the user's job.

## Documentation
- **User-facing docs are the MkDocs Material site in [website/](website/)** (**D-006**), published to
  <https://epifanio.github.io/groundtruther/> by `.github/workflows/docs.yml` on every
  push to `master` touching `website/**` — **merging a `website/` change publishes it**.
  Check with `mkdocs build --strict -f website/mkdocs.yml` (strict catches broken
  internal links and pages missing from the nav). `website/site/` is a build artifact —
  never commit it.
- Sections: Installation · Tools (one page per feature) · **Configuration** (all 27
  keys + the validation model) · **Data model** (every column the plugin reads) ·
  Architecture. Adding a *feature* means adding its tool page **and** its config keys
  to the settings reference.
- `docs/grass_fastgis.md` and `docs/photogrammetric_ribbon.md` are agent-facing deep
  dives and stay separate from the site. The ribbon **does** have a user page now
  (`website/docs/tools/seabed-ribbon.md`, added 2026-09-24) even though it is a
  script under `scripts/` and not a dock — it produces a map product users need to
  interpret. That page leads with a "this is a script, not a panel" warning; keep
  that framing if you edit it.
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
  logic to the stateless `gt/` package so it can be unit-tested (**D-008**: `gt/` stays
  importable without QGIS; `task_runner.py` is the named exception). `conftest.py`
  stubs `groundtruther.configure` so `gt/` imports stay QGIS-free.
- **CI runs `pytest tests/unit` and `mkdocs build --strict` on every PR**
  (`.github/workflows/checks.yml`, from `dependencies/requirements-test.txt`).
  Before that workflow existed the suite had never run in CI and the strict docs
  build first ran in the job that *publishes* the site.
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
- **The recipe above is Linux-only** (`/usr/share/qgis/python`, `python3.14`). On macOS
  there is no equivalent, and **the obvious improvisation is wrong**: see the next bullet
  before you write one.
- **macOS headless harness — read this before improvising one.** The app bundle's
  `Contents/MacOS/python3.12` carries the hardened runtime with **no entitlements**, while
  the app binary *is* granted `com.apple.security.cs.disable-library-validation`. So the app
  can `dlopen` pip wheels and that interpreter cannot: every pip-installed `.so` fails with
  `code signature … not valid for use in process: … different Team IDs`, and a session that
  runs probes under it **will report perfectly good dependencies as broken**. Removing or
  re-signing the wheel does not help. `qgis --code` is not a way out either: QGIS starts
  offscreen, populates the profile, and never reaches the script. What works is a copy of
  that interpreter, ad-hoc signed with the entitlement, placed so its `@rpath` resolves:
  ```bash
  A=/Applications/QGIS-final-4_2_1.app          # your bundle
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
  "$H/MacOS/py312" your_probe.py        # NOT python3 -I — see below
  ```
  The probe itself makes `groundtruther` resolve to the repo the same way the Linux recipe
  does (`sys.modules["groundtruther"]` with `__path__ = [<repo>]`, then
  `sys.path.insert(0, <repo>)`).
- **Never pass `-I` to that interpreter.** Isolated mode ignores `PYTHONHOME`, so it dies
  before reaching your script with `Fatal Python error: init_fs_encoding: failed to get the
  Python codec of the filesystem encoding` / `No module named 'encodings'`. This collides
  with the general advice to run scripts near untrusted files with `-I`; here the harness
  wins. Verified `seq-U1-deps-message` and `seq-U2-macos-profile-docs`, 2026-10-24.
- **The harness cannot verify the QGIS log panel.** `QgsMessageLog`'s `messageReceived`
  signal is **never delivered in a non-GUI `QgsApplication`** — connecting the explicit
  3-arg overload on `QgsApplication.messageLog()` and calling `processEvents()` captures
  nothing, not even a *direct* `QgsMessageLog.logMessage`. To assert log output headlessly,
  swap `qgis.core.QgsMessageLog` for a spy object; that works because our `_log` helpers
  resolve it from the module at call time. So such a test proves `logMessage` was **called**,
  never that the panel displays it.
- **`import qgis.core` imports `pandas` and `pyarrow` itself**, before any plugin code runs,
  so a plugin cannot choose its own copy: by the time `_bootstrap_venv()` runs they are
  already in `sys.modules` and no `sys.path` change — append or prepend — displaces them.
  On macOS QGIS 4.2.1 the bundled **pandas 3.0.3** is the broken piece (a pandas↔numpy C-API
  ABI mismatch: every datetime operation SIGSEGVs the process), **not** the pandas/pyarrow
  pairing — so **no pin fixes it**, and the plugin instead keeps datetimes out of pandas
  (`gt/pandas_safe.py`). Full measurements: `PLANNING/TODO_mac-install-test.md` §3 and §5.
- For pure `gt/` helpers, stub `groundtruther.configure.log_exception` to avoid pulling
  in Qt/UI.

## Git
How branches, PRs, merging and worktrees work is the rulebook: `PLANNING/WORKFLOW.md` §6 (and §12
Q3 — a session merges its own docs-only PR; **a PR that changes code is left for the owner**, who
reviews it and checks the plugin in QGIS first). What still belongs here:
- **Never stage `config/config.yaml`** — gitignored, machine-specific, and it holds the GRASS
  API key. The committed template is `config/config.example.yaml`.
- End commit messages with `Co-Authored-By: Claude <noreply@anthropic.com>` (**D-007**; this is why
  the kit's commit-identity module is off and `.githooks/commit-msg` is deliberately inert).

## Planning workflow
Non-trivial work (features, multi-file fixes, refactors, migrations) is **planned first** in
`PLANNING/`. **Since 2026-10-23 the process is the rulebook
[PLANNING/WORKFLOW.md](PLANNING/WORKFLOW.md)** (agent-session-kit) — see the section below for the
short version. The previous rules are kept as a record in
[PLANNING/legacy/](PLANNING/legacy/) and no longer govern: where they disagree with `WORKFLOW.md`,
`WORKFLOW.md` wins.

Project-specific, and not derivable from the rulebook:
- **Lane U owns the live QGIS install.** The QGIS profile symlink points at the one main checkout,
  so a GUI check is a serialised resource: agents verify headless and *name* the check the owner
  must do (`WORKFLOW.md` §3.1). There is no staging anywhere.
- **The QGIS profiles are shared state git does not isolate.** A worktree isolates the repo, not
  `~/Library/Application Support/QGIS/QGIS4/profiles/`, which holds *copies* of the plugin and
  `gt-mac-test`'s `.venv`. Refresh one with `scripts/mac-profile-install.sh <profile>` (never by
  hand), re-run it after a merge before asking for a GUI check, and say on the queue row that you
  touched it. `gt-mac-novenv` must stay venv-less (`WORKFLOW.md` §3.1).
- **Merging a `website/` change publishes it** to <https://epifanio.github.io/groundtruther/> —
  the one thing here that deploys on a merge (`WORKFLOW.md` §8).
- The older plans in `PLANNING/` stay as closed records; `PLANNING/legacy/` holds the pre-2026-10-23
  rules. `PLANNING/TEMPLATE_planning.md` is a usable skeleton for a plan's body, but a plan's
  required shape is `WORKFLOW.md` §5.1.
- What the harvest of 2026-10-23 found, and what is still owed:
  [PLANNING/adopt-groundtruther.md](PLANNING/adopt-groundtruther.md).


<!-- agent-session-kit:begin -->
## How sessions work here (agent-session-kit)

The rulebook is `PLANNING/WORKFLOW.md`; the skills carry its sections. The owner's first message
says which kind of session this is:

- **talks about a topic** (an idea, feedback, a bug): a planning session, `/plan-session`. It plans
  and stops; it builds nothing.
- **pastes a prompt from the queue**, or writes `/build-session <session>`: a build session. Claim
  first, one lane, close by the queue's §6.1 (`/close-session`).
- **pastes the catch-up prompt** on a machine idle for days: read-only, `/catch-up`. If this
  checkout's `git log -1` is days old and nobody pasted it, say so first.

Something urgent with no row is a side session: the build rules, registered under *Beside the queue*.

Always: one worktree per session (`scripts/session.sh start <session>`); never switch branches in a
checkout you did not create; commit and push after every finished step; the checker
(`python3 PLANNING/check_planning.py`) before any PR that touches `PLANNING/`; a production deploy is
a go from one of epifanio, each time. Hooks sync memory and block the four git mistakes; a
clean-up the owner approved runs with `SESSION_DONE=<session>` in front.

Memory is the private repo `epifanio/groundtruther-memory` (`scripts/memory-repo.sh init|sync|status`): read
`MEMORY.md`, then `user_<login>.md`; a dated note at the end; no secrets; `PLANNING/memory_inbox/`
when the repo is out of reach.

When compacting, keep: this session's name, its worktree path, its claimed row, its PR numbers, the
owner's answers, and the files changed.
<!-- agent-session-kit:end -->
