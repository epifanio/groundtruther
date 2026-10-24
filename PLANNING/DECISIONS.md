# Decisions — what binds more than one plan

A plan freezes the owner's answers for its own work ([`WORKFLOW.md`](WORKFLOW.md) §4 step 5). An
answer that binds work **outside** its plan (a store, a library ban, a public contract, a
vocabulary, a deploy rule) is promoted to a record in [`decisions/`](decisions/README.md) and gets
one row here. This table is derived: the record is the truth, the plan that made it keeps the
reasoning, this file points. A planning session reads it in step 3 of `WORKFLOW.md` §4; a build
session reads the records its prompt names.

A record is never edited after it is accepted; a change is a new record that `supersedes` it. With
one owner, a record is `accepted` when its PR merges. With several maintainers it is `proposed`
until the approval in `WORKFLOW.md` §12 Q10, and a row that depends on it is ⏸ "Waits on D-nnn".
`python3 PLANNING/check_planning.py` checks this file against `decisions/` (rules D1–D4). On a merge
conflict, take `master`'s version; if another session took your number, renumber your
record and redo your row.

| ID | Status | Date | Decision | Record |
|---|---|---|---|---|
| D-001 | accepted | 2026-09-17 | Intra-plugin imports are absolute `from groundtruther…`; nothing appends the plugin dir to `sys.path` | [D-001_intra-plugin-imports.md](decisions/D-001_intra-plugin-imports.md) |
| D-002 | accepted | 2026-10-23 | All GRASS/FastGIS HTTP goes through `gt/grass_api.py`; no `requests` in `mixins/` or `pygui/` | [D-002_grass-http-through-grass-api.md](decisions/D-002_grass-http-through-grass-api.md) |
| D-003 | accepted | 2026-10-23 | Log via `QgsMessageLog` with the `GroundTruther` tag, never `print()` (enforced in `mixins/`, `gt/`) | [D-003_logging-through-qgsmessagelog.md](decisions/D-003_logging-through-qgsmessagelog.md) |
| D-004 | superseded by D-010 | 2026-10-23 | Qt through the `qgis.PyQt` shim, never `PyQt6` directly | [D-004_qt-through-the-qgis-shim.md](decisions/D-004_qt-through-the-qgis-shim.md) |
| D-005 | accepted | 2026-10-23 | The generated `pygui/Ui_*.py` is the truth, not `qtui/*.ui`; never run `compile_ui.sh` wholesale | [D-005_generated-ui-is-the-truth.md](decisions/D-005_generated-ui-is-the-truth.md) |
| D-006 | accepted | 2026-09-24 | User docs are the MkDocs site in `website/`; `help/` is retired; a feature needs its page and its config keys | [D-006_user-docs-are-the-mkdocs-site.md](decisions/D-006_user-docs-are-the-mkdocs-site.md) |
| D-007 | accepted | 2026-10-23 | Every non-merge commit carries `Co-Authored-By: Claude`; the commit-identity module stays off | [D-007_commits-carry-the-claude-trailer.md](decisions/D-007_commits-carry-the-claude-trailer.md) |
| D-008 | accepted | 2026-10-23 | New logic goes in the stateless `gt/`, importable without QGIS (`task_runner.py` excepted) | [D-008_new-logic-goes-in-the-stateless-gt-package.md](decisions/D-008_new-logic-goes-in-the-stateless-gt-package.md) |
| D-009 | accepted | 2026-10-24 | No pandas `datetime64`/`timedelta64` anywhere in the plugin: temporal data is object dtype, Arrow reaches pandas through `gt/pandas_safe.py` | [D-009_no-pandas-datetime-dtypes.md](decisions/D-009_no-pandas-datetime-dtypes.md) |
| D-010 | accepted | 2026-10-24 | D-004 again, now with the `enforce` line it asked for: no `PyQt6` import statement in any hand-written module | [D-010_qt-through-the-qgis-shim-enforced.md](decisions/D-010_qt-through-the-qgis-shim-enforced.md) |
