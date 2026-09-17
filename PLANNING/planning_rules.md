# Planning Workflow — Rules & Bootstrap

| | |
|---|---|
| **Status** | `DONE` — executed 2026-09-17 |
| **Type** | process / bootstrap |
| **Worktree branch** | `chore/install-planning-workflow` |
| **Created** | 2026-06-23 |
| **Related memory** | `planning-workflow`, `project-overview`, `april-2026-refactor`, `install-and-run` |
| **Execution PR** | [#20](https://github.com/epifanio/groundtruther/pull/20) |

> **About this file.** It is two things at once:
> 1. the **canonical rules** for how we plan and execute substantial work on GroundTruther (bug fixes, features, docs, refactors), and
> 2. the **first planning file** that follows those rules — its own task is to *install* the workflow into the repo (README, template, CLAUDE.md wiring, a memory entry).
>
> Read §1–§7 for the rules. §8 is the reusable template. §9–§11 are this file's own plan, kickoff prompt, and progress log.

---

## 1. Purpose

Substantial changes should be **planned before they are executed**, and the plan should be a durable artifact that a *fresh, independent* AI-agent session can pick up and run to completion with minimal hand-holding. This gives us:

- **Parallelism** — several agent sessions can work different plans at once, each in its own git worktree, without stepping on each other or on your live QGIS install.
- **Continuity** — the plan + the project memory carry context across sessions, so an agent starting cold is immediately oriented.
- **Reviewability** — the plan is reviewed and merged *before* work starts, so scope and approach are agreed up front.
- **Traceability** — every plan leaves a progress log and updated memory, so "why/what/how" survives the session.

Use a planning file for anything non-trivial: a feature, a multi-file bug fix, a refactor, a docs overhaul, an API migration. Skip it for one-line fixes and conversational Q&A.

---

## 2. Core concepts (and two corrections to the naive version)

**Correction 1 — there are _two_ git flows, not one.** Writing the plan and executing the plan are separate steps with separate branches/PRs:

| Flow | Where | Branch | PR | Who |
|---|---|---|---|---|
| **A. Authoring** the plan | main working copy | `docs/plan-<topic>` | "the plan" PR | planning author (you + an agent) |
| **B. Executing** the plan | a **dedicated worktree** | `<type>/<topic>` (e.g. `feat/<topic>`) | "the work" PR | a fresh kickoff session |

The worktree is created at the **start of execution (Flow B)** — *not* while merely writing the plan. Authoring a plan is a lightweight doc change on a normal branch.

**Correction 2 — "read the memory files" means the project memory, and it is the _first_ execution step.** Before touching code, the execution agent orients itself from the **agent-aid files**: `CLAUDE.md` (in-repo) and the **Claude Code project memory** (the `MEMORY.md` index plus the `memory/` entries it recalls). These reflect current status, known gotchas, and prior decisions. The plan author should skim them too, so the plan doesn't contradict reality.

**Vocabulary**

- **Planning file** — a Markdown file in `PLANNING/`, prefixed `TODO_` while open.
- **Kickoff prompt** — a self-contained block, embedded in the planning file, that the user pastes into a fresh agent session to start Flow B.
- **Worktree** — an isolated checkout (`git worktree`) so parallel sessions don't collide and the live QGIS symlink is never disturbed.
- **Project memory** — the durable agent-aid notes under Claude Code's per-project memory (index: `MEMORY.md`).

---

## 3. The `PLANNING/` folder

- All planning files live in `PLANNING/` at the repo root.
- **Naming:** `TODO_<kebab-topic>.md` while open (e.g. `TODO_backscatter-legend.md`). On completion, the `TODO_` prefix is **removed** (`backscatter-legend.md`) — a completed plan stays in the folder as a record.
- **Lifecycle / `Status` field:** `PLANNED` → `IN PROGRESS` → `DONE`. The filename prefix mirrors this: `TODO_` for `PLANNED`/`IN PROGRESS`, prefix removed for `DONE`.
- One topic per file. Split large efforts into sub-task sections within one file, or into several linked files (`See also:` links) if they can proceed independently.

---

## 4. Anatomy of a planning file

Every planning file MUST contain, in order:

1. **Header table** — Status, Type, Worktree branch, Created date, Related memory, Execution PR (filled in later).
2. **Objective** — one paragraph: what "done" looks like, in outcome terms.
3. **Context & background** — what an agent needs to know; link the relevant `memory/` entries and source files (`path:line`).
4. **Scope** — explicit **in scope** / **out of scope** bullets. This is where creep is contained.
5. **Prerequisites** — files/memory to read first; any data, credentials, or services needed.
6. **Worktree setup** — the exact `git worktree` commands (see §5).
7. **Task breakdown** — an ordered checklist of sub-tasks (`- [ ]`), small enough to verify each.
8. **Acceptance criteria & verification** — concrete checks: which tests to run (`.venv/bin/pytest`), headless import/load checks per CLAUDE.md, and any manual GUI check the *user* must do (agents can't drive the QGIS GUI).
9. **Risks & rollback** — what could break; how to back out (the worktree makes this cheap).
10. **Kickoff prompt** — the copy-paste block (see §6).
11. **Progress log** — appended by the execution agent: decisions, deviations, results, PR link.

§8 provides a fill-in-the-blanks template for all of this.

---

## 5. Worktree conventions

Worktrees keep parallel sessions isolated and — crucially — leave the QGIS profile symlink (which points at the **main** working copy, `groundtruther/`) untouched, so a work-in-progress branch never breaks your running QGIS.

Create at the start of execution (sibling directory, matching the existing convention e.g. `groundtruther-fastgis`):

```bash
cd /home/epinux/dev/groundtruther            # main working copy
git fetch origin
git worktree add ../groundtruther-<topic> -b <type>/<topic> origin/master
cd ../groundtruther-<topic>
# work here; set up the venv/link only if a live check is needed (see note)
```

- **Branch name:** `<type>/<topic>` — `feat/…`, `fix/…`, `docs/…`, `refactor/…`, `chore/…`.
- **Verification runs headless** from the worktree (`.venv/bin/pytest`, offscreen import/load per CLAUDE.md). The venv can be reused from the main copy via `PYTHONPATH`, or created in the worktree; agents do **not** launch the QGIS GUI (that's the user's job, in the main copy).
- **Never stage `config/config.yaml`** (it is gitignored and machine-specific / holds a secret).
- **Cleanup after the work PR merges:**
  ```bash
  cd /home/epinux/dev/groundtruther
  git worktree remove ../groundtruther-<topic>
  git branch -d <type>/<topic>            # after merge
  ```

---

## 6. The kickoff prompt

Each planning file ends with a **self-contained** kickoff prompt the user pastes into a *fresh* agent session. It must, without relying on any prior conversation:

1. Name the target planning file (`PLANNING/TODO_<topic>.md`) and say "execute it end to end."
2. Order the agent to **first** read `CLAUDE.md` and review the project memory (recalled memories + `MEMORY.md`).
3. Order the agent to **create the worktree** exactly as the plan specifies.
4. Point to the Task Breakdown and Acceptance Criteria as the definition of the work.
5. State the **Definition of Done** (§7): verify, update memory, fill the progress log, remove the `TODO_` prefix, open the work PR, **do not merge** — the user reviews and merges.

Keep it terse and imperative; the details live in the plan, not the prompt.

---

## 7. Definition of Done

A plan is complete only when **all** of these hold:

- [ ] All Task-Breakdown items done; Acceptance Criteria met; tests green (`.venv/bin/pytest`).
- [ ] **Project memory updated** — new/changed `memory/` entries capturing findings, decisions, and current status, with `MEMORY.md` pointers. (This is what keeps the next session oriented.)
- [ ] **Progress log filled** in the planning file (what was done, deviations, results, PR link).
- [ ] Planning file **renamed** to drop the `TODO_` prefix; `Status` set to `DONE`.
- [ ] **Work PR opened** (`gh`, account `epifanio`) against `master` — **not merged**; the user reviews and merges.
- [ ] Worktree cleanup noted for the user (removed after merge).

---

## 8. Reusable template

Copy this into a new `PLANNING/TODO_<topic>.md` when starting a plan. (Rendered inside a 4-backtick fence so the inner code blocks survive copy-paste.)

````markdown
# TODO — <Title>

| | |
|---|---|
| **Status** | `PLANNED` |
| **Type** | feat \| fix \| docs \| refactor \| chore |
| **Worktree branch** | `<type>/<topic>` |
| **Created** | <YYYY-MM-DD> |
| **Related memory** | `<slug>`, `<slug>` |
| **Execution PR** | _(filled in by the execution agent)_ |

## Objective
<One paragraph. What "done" looks like, in outcome terms.>

## Context & background
<What the agent must know. Link memory entries and source files as path:line.>

## Scope
**In scope:** <bullets>
**Out of scope:** <bullets>

## Prerequisites
- Read: `CLAUDE.md`, project memory (`MEMORY.md` + relevant `memory/` entries).
- <data / services / credentials needed, if any>

## Worktree setup
```bash
cd /home/epinux/dev/groundtruther
git fetch origin
git worktree add ../groundtruther-<topic> -b <type>/<topic> origin/master
cd ../groundtruther-<topic>
```

## Task breakdown
- [ ] <sub-task 1>
- [ ] <sub-task 2>
- [ ] <sub-task 3>

## Acceptance criteria & verification
- [ ] `.venv/bin/pytest` green (unit; gui/integration auto-skip).
- [ ] Headless import/load check per CLAUDE.md passes.
- [ ] <feature-specific checks>
- [ ] Manual GUI check by the user: <what to look at>

## Risks & rollback
<What could break; how to back out. The worktree/branch makes rollback cheap.>

## Kickoff prompt
```
You are working on the GroundTruther QGIS plugin (QGIS 4 / Qt6). Execute the plan in
PLANNING/TODO_<topic>.md end to end.

First: read CLAUDE.md and review the project memory (your recalled memories + the
MEMORY.md index). Then create the dedicated worktree exactly as the plan's "Worktree
setup" section specifies.

Then complete the Task Breakdown and meet the Acceptance Criteria. When done: run the
tests, update the project memory with your findings, fill the Progress Log in the plan,
rename PLANNING/TODO_<topic>.md → PLANNING/<topic>.md (Status: DONE), and open a PR
against master (gh, account epifanio). Do NOT merge — I will review and merge.
```

## Progress log
_(appended by the execution agent)_
````

---

## 9. This plan — objective & task breakdown (the bootstrap)

**Objective.** Install this planning workflow into the repo so future plans have a home, a template, a discoverability hook in `CLAUDE.md`, and a memory entry that keeps agents aware of it.

**Scope**
- In: create the folder scaffolding, extract the template to its own file, wire `CLAUDE.md`, add a memory entry, finalize this file.
- Out: authoring any *real* feature/fix plan (those come later, each in its own `TODO_` file).

**Task breakdown**
- [x] Create the worktree per §5 (`chore/install-planning-workflow`).
- [x] Add `PLANNING/README.md` — one screen: what `PLANNING/` is, the lifecycle (§3), links to this rules file and the template.
- [x] Add `PLANNING/TEMPLATE_planning.md` — the §8 template extracted verbatim (no `TODO_` prefix; it is not a task).
- [x] Wire `CLAUDE.md` — add a short **"Planning workflow"** section pointing to `PLANNING/README.md` and summarizing the two-flow + worktree + kickoff rules in 3–4 lines.
- [x] Add a project-memory entry (e.g. `planning-workflow` — type `project`) describing the workflow and its files, with a `MEMORY.md` pointer, so future sessions recall it automatically.
- [x] Fill the Progress Log below.
- [x] Rename this file `TODO_planning_rules.md` → `planning_rules.md`; set `Status: DONE`.
- [x] Open the work PR (do not merge).

**Acceptance criteria & verification**
- [x] `PLANNING/README.md` and `PLANNING/TEMPLATE_planning.md` exist and are internally consistent with this file.
- [x] `CLAUDE.md` references the workflow and the `PLANNING/` folder.
- [x] A memory entry + `MEMORY.md` pointer exist for the workflow.
- [x] `.venv/bin/pytest` still green (no code changed, but confirm nothing broke).
- [x] This file renamed, `Status: DONE`, Progress Log filled.

**Risks & rollback.** Docs-only; risk is low. Rollback = drop the branch/worktree. Only real care point: do not touch `config/config.yaml`.

---

## 10. Kickoff prompt for THIS plan

```
You are working on the GroundTruther QGIS plugin (QGIS 4 / Qt6). Execute the plan in
PLANNING/TODO_planning_rules.md end to end — it bootstraps our planning workflow into
the repo.

First: read CLAUDE.md and review the project memory (your recalled memories + the
MEMORY.md index). Then read PLANNING/TODO_planning_rules.md in full and create the
dedicated worktree exactly as its "Worktree setup"/§5 section specifies
(branch: chore/install-planning-workflow).

Then complete the §9 Task Breakdown: add PLANNING/README.md and
PLANNING/TEMPLATE_planning.md, wire a short "Planning workflow" section into CLAUDE.md,
add a project-memory entry (with a MEMORY.md pointer) describing the workflow, and meet
the §9 Acceptance Criteria. When done: run .venv/bin/pytest, fill the Progress Log,
rename PLANNING/TODO_planning_rules.md → PLANNING/planning_rules.md (Status: DONE), and
open a PR against master (gh, account epifanio). Do NOT merge — I will review and merge.
```

---

## 11. Progress log

**2026-09-17 — bootstrap executed** (agent session, worktree `../groundtruther-planning-workflow`,
branch `chore/install-planning-workflow` off `origin/master`).

What was done:
- Read `CLAUDE.md` and the project memory (`MEMORY.md` index + recalled entries) first,
  then this file in full, per §10.
- Created the worktree per §5: `git worktree add ../groundtruther-planning-workflow -b
  chore/install-planning-workflow origin/master`. The main working copy (and therefore the
  QGIS profile symlink) was left untouched.
- Added **`PLANNING/README.md`** — one-screen orientation: what `PLANNING/` is, the file
  table, the two-flow branch model, the `PLANNED → IN PROGRESS → DONE` lifecycle, how to
  start a plan (Flow A) and how to execute one (Flow B), and worktree cleanup. Links to
  this rules file and to the template.
- Added **`PLANNING/TEMPLATE_planning.md`** — the §8 template extracted **verbatim**
  (lines 142–205 of the pre-rename file), unwrapped from its 4-backtick display fence and
  prefixed with an HTML comment saying where to copy it and where the rules live. No
  `TODO_` prefix: it is a template, not a task.
- Wired **`CLAUDE.md`** — new `## Planning workflow` section (last section, after `## Git`)
  pointing at `PLANNING/README.md` + `PLANNING/planning_rules.md` and summarising the
  two-flow model, the worktree rule, the template→`TODO_` →kickoff path, and the
  Definition of Done.
- Added project memory entry **`planning-workflow`** (type `project`) with a `MEMORY.md`
  pointer, cross-linked to `project-overview`, `install-and-run`, `april-2026-refactor`,
  `grass-client-blast-radius`, so future sessions recall the workflow automatically.
- Renamed `TODO_planning_rules.md` → `planning_rules.md`, `Status: DONE`, §9 checklists
  ticked. (`§7` Definition of Done is left unticked on purpose — it is the generic rule
  text, not this file's own checklist.)

Deviations from the plan: none of substance. Two small judgement calls:
- Worktree topic named `planning-workflow` (dir `../groundtruther-planning-workflow`),
  matching the README/CLAUDE.md wording rather than the file slug `planning_rules`.
- The worktree has no `.venv` of its own; tests were run with the main copy's interpreter
  (`/home/epinux/dev/groundtruther/.venv/bin/pytest`), which §5 explicitly allows.

Verification: `.venv/bin/pytest` from the worktree → **188 passed, 5 skipped**
(gui + integration auto-skipped as expected), 1 pre-existing GDAL `FutureWarning`.
Docs-only change, so no headless import/load check was needed and no runtime behaviour
changed. `config/config.yaml` was never staged.

PR: **[#20](https://github.com/epifanio/groundtruther/pull/20)** — opened against `master`, left unmerged for review.

Follow-up for the user: review and merge the PR, then
`git worktree remove ../groundtruther-planning-workflow && git branch -d chore/install-planning-workflow`.
