# Adopt the knowledge GroundTruther already carried

**The owner's brief** (2026-10-23): install the session system into GroundTruther and harvest what
the project already knows from a year of agentic coding, so a fresh session starts oriented.
SETUP step 7c; the checklist is `/adopt-project`.

## Status

**◐ closed 2026-10-23 by `plan-adopt-groundtruther`.** Everything the harvest could reach from this
Mac is in its home: 8 decision records (D-001…D-008) from `CLAUDE.md`'s standing choices, the two
late setup answers written into `WORKFLOW.md` §12 (Q2, Q13), the State table read from the running
system, `CLAUDE.md` rewritten to cite the records (not *trimmed* — see the correction below), and
`user_epifanio.md` in
the memory repo. **Nothing was queued**: there is no live plan and no adopted work in flight, so
both slots are empty and the test of the harvest is `/catch-up`, not a ⏭ prompt
(`/adopt-project` step 8).

**Three things are owed, all the owner's**, and each is where they will see it: two in the queue's
§3 (the Linux machine's memory import, and the `PyQt6 import sip` question) and one on *The owner's
list* (whether the roughness work moves to a separate repository). Until the Linux import happens
the harvest is **incomplete by design** — see "What exists today".

Conventions: `PLANNING/WORKFLOW.md` §5.2 (rules 0–6).

## Correction, 2026-10-23 (`plan-adopt-groundtruther-gaps`)

The catch-up test required by `/adopt-project` step 8 read these files cold and caught two false
claims, both made by the sessions that wrote them:

1. **`CLAUDE.md` was not "trimmed".** It went **191 lines at 650a164 → 223 at d7affe8 (the install)
   → 239 at 88a36ad (this harvest)**: 48 lines *longer*. Process rules did move out to the rulebook,
   but the record citations, the two corrections and the project-specific notes added more than that
   removed. The honest word is *rewritten*, and the "191 lines" in `WORKFLOW.md` §12 Q13 is now
   dated to the commit it was measured at.
2. **A State row narrated `master`'s position** ("master has since moved to d7affe8"), and the very
   next merge made it false. The cell no longer names `master`'s tip; it says how to compare the two
   shas instead.

Fourteen other gaps came out of the same test. The ones that live in this project are fixed in that
session's PR; the ones that belong to agent-session-kit are listed for the kit. The test was worth
more than the harvest it checked.

## What exists today

Verified on `master` d7affe8, 2026-10-23, by reading the code — not from any note.

### The inventory (`scripts/adopt-inventory.sh`, 2026-10-23)

| Source | Found |
|---|---|
| Instruction files | `CLAUDE.md`, 191 lines: layout, run/develop, conventions, gotchas, docs, testing, git, planning |
| Auto memory on **this Mac** | **none for this project.** Every memory directory here belongs to FastGIS, a different project |
| Auto memory on the **Linux machine** | not reachable from here; `/home/epinux/dev/groundtruther` is where the project's history lives |
| Transcripts | none for GroundTruther on this Mac |
| Plans in `PLANNING/` | 5, **all `DONE`**: `config-validation-hardening` (#24), `docs-audit-code-findings` (#35), `photogrammetric-ribbon` (#36), `settings-and-data-model-docs` (#29), `legacy/planning_rules` (#20) |
| Branches | 23 remote |
| Open PRs | 6: #37, #39, #40, #41, #42, #43 — **set aside by the owner**, see §6 Q2 |
| Open issues | 3: #1 plug-in dependencies, #2 missing documentation, #4 install on Windows |
| Roadmap / decision files | none |

**There was no work in flight to adopt.** All five plans are closed records, and the six open PRs
are the owner's to move elsewhere. This is why both slots are empty, and it is a fact about the
project, not a gap in the harvest.

### What the code says that `CLAUDE.md` does not

Three of `CLAUDE.md`'s rules are aspirations rather than descriptions. Each is recorded honestly in
its decision record instead of as a clean invariant:

| Rule | Reality at d7affe8 |
|---|---|
| "never `print()`" | clean in `mixins/` and `gt/`; **`episg.py` 25, `groundtruther.py` 7, `ioutils.py` 4**, several `pygui/*_gui.py`. D-003 enforces only the clean directories |
| "never `PyQt6` directly" | **one violation**, `mixins/video_browser_mixin.py:693` (`from PyQt6 import sip`, function-local). D-004 carries no `enforce` line because of it |
| "`gt/` is no-Qt" | `task_runner.py` imports `qgis.core` at module level by necessity; `annotations.py:71` imports it *inside a function*. D-008 names both |

An `enforce:` regex on an accepted record fails CI on a match (checker rule D4), so writing any of
these as a blanket rule would have broken the build on the next PR. D4 was proved live: a probe file
containing `print(` in `mixins/` failed the checker, and passed again once removed.

### What the running system says that the files do not

`setup-session-system` filled the State table's plugin row from `metadata.txt` (`version=0.4`).
That was wrong, and reading the live feed corrected it:

| | `metadata.txt` on `master` | plugins.qgis.org, read 2026-10-23 |
|---|---|---|
| Version | 0.4 | **0.3** |
| QGIS | `qgisMinimumVersion=4.0` | 3.0.0 – 3.99.0 |
| Flag | — | **experimental** |
| Date | — | **2023-06-01** |

**The QGIS 4 / Qt6 rewrite has never been published.** Users installing GroundTruther from the
official repository get the 2023 QGIS-3 build, `plugin_id` 2982, author `epinux`. Whether to publish
0.4 is the owner's call and a production rollout (`WORKFLOW.md` §8); it is not queued, because
nobody asked for it — but it is the largest gap between this repo and the world, and it is why the
State row now carries the live numbers and the date they were read.

The docs site checked out clean: `gh-pages` abe7632 says "Deployed 650a164", the site answers
HTTP 200, and it is still built from 650a164 even though `master` is now d7affe8 — correct, because
PR #45 touched no `website/**` path.

## Design

The harvest writes into the homes the rulebook already defines, one home per fact:

- a **standing choice** → a record in `decisions/`, cited by number, never re-decided;
- a **setup answer** → `WORKFLOW.md` §12, frozen;
- **what is deployed** → the queue's State table, read from the running system;
- **how the owner works** → `user_epifanio.md` in the memory repo;
- **what the code shows** → nowhere: `CLAUDE.md` already says it, and duplicating it would drift.

Nothing was invented. Where `CLAUDE.md` was the only source, the record says so in `decided-by`.

## Questions for the owner

Asked 2026-10-23, answered the same day, frozen.

**Q1. Which machines and accounts will run sessions?** → *"Both, plus cloud sessions."* This Mac,
the Linux machine, and cloud sessions. Written into §12 Q2. The Linux machine owes a one-time
`memory-repo.sh init … --import`.

**Q2. Which of the six open PRs are live work?** → *"those are all unrelated the fastgis at the
moment keep them alone, we probably need to move them out of fastgis and transfer them to my
seafloor roughness repository"*. So #37, #39–#43 are **neither queued nor dropped**: nobody touches
those branches. The repository question is on *The owner's list*; it becomes a decision record when
they decide it, not before. Written into §12 Q13.

**Q3. (from setup) All 13 setup recommendations** → accepted as written, 2026-10-23. `WORKFLOW.md`
§12.

Promoted to records because they bind work outside this plan: none of the three. The eight records
this plan wrote come from `CLAUDE.md`, not from an answer.

## Work packages

| Package | Scope | State |
|---|---|---|
| `adopt-groundtruther WP-1` | the 8 decision records and their index rows | ✅ merged in this plan's PR |
| `adopt-groundtruther WP-2` | §12 Q2 and Q13; the State table; *The owner's list*; the queue's §3 | ✅ merged in this plan's PR |
| `adopt-groundtruther WP-3` | `CLAUDE.md`: process rules out to the rulebook, record citations in. **Net +48 lines, not a trim** | ✅ merged in this plan's PR |
| `adopt-groundtruther WP-4` | `user_epifanio.md` and the memory note | ✅ synced to the memory repo |
| `adopt-groundtruther WP-5` | the Linux machine's auto-memory import | ⏸ **the owner's**, queue §3 |

## Lane split

All of WP-1…WP-4 are one docs-only PR in no lane: they touch `PLANNING/`, `CLAUDE.md` and the
memory repo only. WP-5 cannot run from this machine at all. No session collides with this plan.

## Verification

- `python3 PLANNING/check_planning.py` clean, including the D4 regexes of D-002 and D-003 over the
  real tree, and proved to fail on a planted violation.
- Every record's claim was read in the code at d7affe8 and is cited with its file and line.
- Every `enforced-by` names a test that exists: `tests/gui/test_import_hygiene.py`,
  `tests/unit/test_settings_docs.py`, `tests/conftest.py`.
- The real test of the harvest is a fresh session: `/catch-up`, since nothing was queued.

## Kickoff

Closed; nothing queued. The next session is whatever the owner's first real topic turns out to be —
a planning session, by `WORKFLOW.md` §4.
