# GroundTruther test suite

Layered so most tests run **without QGIS or network**, while heavier checks are
available when you have them.

| Layer | Needs | What it covers |
|---|---|---|
| `tests/unit/` | nothing (just the venv) | `gt/grass_api.py` (URL/auth/error handling, response unwrapping, WCS MIME-strip), `gt/image_manager.py` (metadata/KD-tree/annotations), `config_model.py` (pydantic validation) |
| `tests/gui/` | QGIS/Qt (offscreen) | schema-driven module form (`pygui/grass_module_form.py`) — pure helpers + widget build/collect |
| `tests/integration/` | live FastGIS API + key | end-to-end client calls (whoami, modules, create/use/delete env) |

How it stays QGIS-free: `tests/conftest.py` registers `groundtruther` as a package
pointing at the repo and **stubs `groundtruther.configure`** (no-op `log_exception`),
so the stateless `gt/` helpers import without dragging in `qgis.PyQt`.

## Run

```bash
# from the repo root, using the project venv
.venv/bin/pytest                      # unit tests run; gui + integration auto-skip

# unit only
.venv/bin/pytest tests/unit

# gui tests (need QGIS on the path; run offscreen)
QT_QPA_PLATFORM=offscreen PYTHONPATH=/usr/share/qgis/python \
  .venv/bin/pytest tests/gui -m gui

# integration tests (live API — creates & deletes a throwaway env)
GROUNDTRUTHER_API_KEY=fgk_... \
  [GROUNDTRUTHER_API_URL=https://api.fastgis.eu] \
  .venv/bin/pytest tests/integration -m integration
```

Markers (`gui`, `integration`) are declared in `pytest.ini`. The `gui` module
self-skips via `importorskip` when QGIS isn't importable; integration tests skip
unless `GROUNDTRUTHER_API_KEY` is set.

## Install the test tooling

```bash
.venv/bin/python -m pip install -r dependencies/requirements-dev.txt
```

## Adding tests
- **Prefer `tests/unit/`** — keep new logic in the stateless `gt/` package (or
  other Qt-free modules) so it can be tested here.
- For widget behaviour, add to `tests/gui/` and gate on QGIS with
  `pytest.importorskip(...)`; build widgets under a module-scoped `QApplication`.
- For API contract checks against the server, add to `tests/integration/` behind
  the `integration` marker and the API-key skip.
