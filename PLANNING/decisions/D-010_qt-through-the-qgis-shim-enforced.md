---
id: D-010
date: 2026-10-24
status: accepted
decided-by: epifanio, 2026-10-24 ("Fold the D-004 enforce record into plan-pandas-datetime-record when it runs."); the scope question below carries this session's recommendation and is accepted as written when this PR merges
supersedes: D-004
lanes: U, C, P
enforce: ^\s*(from|import)\s+PyQt6 in mixins/
enforce: ^\s*(from|import)\s+PyQt6 in gt/
enforce: ^\s*(from|import)\s+PyQt6 in pygui/
enforce: ^\s*(from|import)\s+PyQt6 in scripts/
enforce: ^\s*(from|import)\s+PyQt6 in *.py
---
**Decision.** Unchanged from [D-004](D-004_qt-through-the-qgis-shim.md): Qt is imported through the
QGIS shim — `from qgis.PyQt import …` — never `PyQt6` directly. What this record adds is the
`enforce` line D-004 asked for and could not carry.

**Why.** The reason to prefer the shim is D-004's and is not revisited: it resolves to the Qt the
running QGIS was built against, so the plugin survives the next Qt transition, and a direct `PyQt6`
import can load a second, incompatible binding into the same process. What has changed is only
whether a grep can hold the line. D-004 said: *"at `master` d7affe8 (2026-10-23) there is exactly
one violation, `mixins/video_browser_mixin.py:693` (`from PyQt6 import sip`, a function-local
import), so a grep would fail CI today."* `sip-shim-d004` measured `from qgis.PyQt import sip`
working in QGIS 4.2.1's own interpreter and removed that import (PR #91, `master` `9d01eb1`).
Verified by this session at `master` `d6f09e9`: `git ls-files -- '*.py' | xargs grep -nE
'^\s*(from PyQt6|import PyQt6)'` returns nothing. The condition D-004 named is gone, so the line
goes in.

**Binds.** Lanes U, C and P: `mixins/`, `gt/`, `pygui/`, `scripts/` and the root-level modules —
every hand-written module. `tests/` is out of scope: `tests/unit/test_deps_check.py` names `PyQt6`
as a dependency string, which is correct there.

The regex matches an **import statement**, not the bare name, which is what makes the wider scope
possible: the generated `pygui/Ui_*.py` files carry a `# Created by: PyQt6 UI code generator`
header, `mixins/layout_mixin.py:80,85` and `pygui/querybuilder_gui.py:1044` mention `PyQt6` in
comments, and `metadata.txt`, `compile_ui.sh`, `README.md` and four `website/` pages carry the
string in prose. A bare `PyQt6` regex over the tree would fail the build on all of them; this one
does not match any. Verified in both directions against `master` `d6f09e9`: clean as it stands, and
a `from PyQt6 import sip` planted in `mixins/video_browser_mixin.py` is reported as D4. It is still
a grep: a dynamic `importlib.import_module("PyQt6.QtCore")` would pass it, and nothing in the tree
does that today.

**Asked, with this session's recommendation; your merge accepts it as written.**

1. **Scope** — recommend the wider one written above (every hand-written module) rather than
   `mixins/` alone, for the same reason as [D-009](D-009_no-pandas-datetime-dtypes.md) question 1:
   the hazard does not care which directory the import is in, and the directories are clean today,
   so the wider scope costs nothing to adopt and would cost a second record to widen later.

**Supersedes D-004**, which is accepted and therefore not edited beyond its status line and its
index row (`decisions/README.md`). Cite `D-010` from here on.
