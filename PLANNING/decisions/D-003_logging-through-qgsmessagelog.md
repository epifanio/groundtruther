---
id: D-003
date: 2026-10-23
status: accepted
decided-by: epifanio (standing choice in CLAUDE.md; recorded by plan-adopt-groundtruther, 2026-10-23)
lanes: U, C
enforce: print\( in mixins/
enforce: print\( in gt/
---
**Decision.** Plugin code logs with `QgsMessageLog.logMessage(msg, 'GroundTruther', Qgis.<level>)`
and never `print()`. Tracebacks go through `configure.log_exception(context, exc, warn=?)`.

**Why.** A plugin runs inside QGIS: `print()` goes to whatever stream QGIS was launched with, which
on a desktop launch is nobody's terminal, so the message is simply lost. The `'GroundTruther'` tag
is what lets the user filter the Log Messages panel to this plugin.

**Binds.** Lanes U and C. **This is a rule for new code, not a description of the tree:** at
`master` d7affe8 (2026-10-23) `mixins/` and `gt/` were clean, and the `enforce` lines hold that
line, but `episg.py` (25 occurrences), `groundtruther.py` (7), `ioutils.py` (4) and several
`pygui/*_gui.py` files still use `print()`. That backlog is not scoped here; a session that touches
one of those files should convert the calls it touches, and widening the `enforce` scope to a
cleaned directory is a new record.
