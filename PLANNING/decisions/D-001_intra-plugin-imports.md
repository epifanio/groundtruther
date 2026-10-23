---
id: D-001
date: 2026-09-17
status: accepted
decided-by: epifanio, 2026-09-17 (PR #35; recorded by plan-adopt-groundtruther from CLAUDE.md, 2026-10-23)
lanes: U, C, P
enforced-by: tests/gui/test_import_hygiene.py
---
**Decision.** Every intra-plugin import is absolute: `from groundtruther… import …`. Never a bare
`from gt.… import` or `import ioutils`, and **nothing may append the plugin directory to
`sys.path`** — only `__init__.py`'s `_bootstrap_venv()` may touch `sys.path`, and only to add the
venv.

**Why.** QGIS puts the *plugins* directory on `sys.path`, not the plugin's own, so a bare name
resolves only if something has polluted the path — and then the module is loaded **twice**, under
two names, with its module-level state duplicated, in a `sys.modules` shared with every other
installed plugin. `groundtruther.py` used to do exactly this with
`sys.path.append(os.path.dirname(__file__))`; PR #35 removed it and added the test.

**Binds.** Every lane, every new module. The test runs the real plugin load in a subprocess and
asserts the plugin directory is absent from `sys.path`, so it fails if this returns. A new helper
goes under an existing package (`gt/`, `mixins/`, `pygui/`) and is imported by its full dotted path.
