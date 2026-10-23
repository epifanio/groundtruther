---
id: D-008
date: 2026-10-23
status: accepted
decided-by: epifanio (standing choice in CLAUDE.md; recorded by plan-adopt-groundtruther, 2026-10-23)
lanes: U, C
enforced-by: tests/conftest.py (stubs groundtruther.configure so tests/unit/ imports stay QGIS-free)
---
**Decision.** New logic goes in the stateless `gt/` package, which must stay importable **without
QGIS**, so it can be unit-tested. Qt and `qgis` belong in `mixins/`, `pygui/` and the dock.
`gt/task_runner.py` is the named exception: it is a `QgsTask` poller and imports `qgis.core` at
module level by necessity.

**Why.** It is what makes the test suite meaningful: 19 unit test modules under `tests/unit/` run
with no QGIS and no network, because `tests/conftest.py` installs `groundtruther` as a namespace
package and stubs `groundtruther.configure` (the real one imports `qgis.PyQt`). Logic left in a
mixin can only be exercised offscreen, or not at all.

**Binds.** Lanes U and C. **No `enforce` regex:** besides `task_runner.py`, `gt/annotations.py:71`
imports `qgis.core` *inside a function* for logging, which is the accepted pattern for a module that
must stay importable — a grep cannot tell the two apart. The real guard is that
`tests/unit/` must keep passing without QGIS; a new `gt/` module with a top-level `qgis` import
breaks that and is the signal.
