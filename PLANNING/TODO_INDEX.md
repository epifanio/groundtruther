# Plans — index

**Every plan this project has, open or closed, has a row here** — including the five that predate
the session system (2026-06-23 … 2026-09-18), backfilled on 2026-10-23 so that this file answers
"what has already been planned?" without reading every file in `PLANNING/`. The checker only
*requires* a row for an open (`TODO_`-prefixed) plan, so keeping the closed ones listed is a habit,
not something CI will catch for you.

`TODO_`-prefixed files are OPEN; a closed plan loses the prefix and gains a ✅ (or ◐) banner
(`WORKFLOW.md` §5.3). How we work: [`WORKFLOW.md`](WORKFLOW.md). What runs next:
[`TODO_session_sequence.md`](TODO_session_sequence.md). Decisions that bind more than one plan:
[`DECISIONS.md`](DECISIONS.md). `python3 PLANNING/check_planning.py` checks that every open plan has a
row here and that every link resolves.

## Open

| Added | Plan | What | State |
|---|---|---|---|
| 2026-10-23 | [TODO_publish-0-4.md](TODO_publish-0-4.md) | Publish 0.4 to plugins.qgis.org: a safe release zip, honest failure when dependencies are missing, the install documented | 5 sessions queued; the upload is the owner's |
| 2026-10-24 | [TODO_mac-install-test.md](TODO_mac-install-test.md) | What GroundTruther 0.4 actually does on macOS QGIS 4.2.1: the no-`.venv` blocker confirmed, every dependency measured, and a parquet read that segfaults QGIS | ◐ measured; 2 sessions queued; the GUI check is the owner's (§6) |

## Completed

| Closed | Plan | PRs |
|---|---|---|
| 2026-10-23 | [adopt-groundtruther.md](adopt-groundtruther.md) | #45 (the install), and this plan's own PR |
| 2026-09-18 | [photogrammetric-ribbon.md](photogrammetric-ribbon.md) | [#36](https://github.com/epifanio/groundtruther/pull/36) |
| 2026-09-17 | [docs-audit-code-findings.md](docs-audit-code-findings.md) | [#35](https://github.com/epifanio/groundtruther/pull/35) |
| 2026-09-17 | [settings-and-data-model-docs.md](settings-and-data-model-docs.md) | [#29](https://github.com/epifanio/groundtruther/pull/29) |
| 2026-09-17 | [config-validation-hardening.md](config-validation-hardening.md) | [#24](https://github.com/epifanio/groundtruther/pull/24) |
| 2026-09-17 | [legacy/planning_rules.md](legacy/planning_rules.md) | [#20](https://github.com/epifanio/groundtruther/pull/20) |
