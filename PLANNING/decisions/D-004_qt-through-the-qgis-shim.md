---
id: D-004
date: 2026-10-23
status: accepted
decided-by: epifanio (standing choice in CLAUDE.md; recorded by plan-adopt-groundtruther, 2026-10-23)
lanes: U, C
---
**Decision.** Qt is imported through the QGIS shim — `from qgis.PyQt import …` — never `PyQt6`
directly.

**Why.** The shim is what makes the plugin survive the Qt5→Qt6 transition and whatever QGIS ships
next: it resolves to the Qt that the running QGIS was built against. A direct `PyQt6` import binds
the plugin to one Qt major version and can load a second, incompatible binding into the same
process.

**Binds.** Lanes U and C, every module. **No `enforce` line on purpose:** at `master` d7affe8
(2026-10-23) there is exactly one violation, `mixins/video_browser_mixin.py:693`
(`from PyQt6 import sip`, a function-local import), so a grep would fail CI today. Whether `sip` is
reachable as `from qgis.PyQt import sip` in QGIS 4 is an open question for the owner — it is in the
queue's §3. Once it is resolved, the follow-up record adds `enforce: PyQt6 in mixins/` and the rest.
