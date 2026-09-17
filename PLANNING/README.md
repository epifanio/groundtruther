# `PLANNING/` — how we plan work on GroundTruther

Substantial changes are **planned before they are executed**. A planning file is a
durable artifact that a *fresh, independent* agent session can pick up and run to
completion with minimal hand-holding — which buys us parallelism (several sessions,
each in its own git worktree), continuity across sessions, review of scope *before*
work starts, and a traceable record afterwards.

Use a planning file for anything non-trivial: a feature, a multi-file bug fix, a
refactor, a docs overhaul, an API migration. Skip it for one-line fixes and
conversational Q&A.

**The canonical rules live in [planning_rules.md](planning_rules.md).** This README is
the one-screen orientation.

## Files here

| File | What it is |
|---|---|
| [planning_rules.md](planning_rules.md) | The rules: two-flow model, folder conventions, anatomy of a plan, worktrees, kickoff prompts, Definition of Done. |
| [TEMPLATE_planning.md](TEMPLATE_planning.md) | Fill-in-the-blanks template. Copy it to `TODO_<topic>.md` to start a plan. |
| `TODO_<topic>.md` | An open plan (`PLANNED` or `IN PROGRESS`). |
| `<topic>.md` | A completed plan (`DONE`) — kept as a record. |

## Two flows, two branches

Authoring a plan and executing it are **separate steps** with separate branches and PRs:

| Flow | Where | Branch | PR |
|---|---|---|---|
| **A. Author** the plan | main working copy | `docs/plan-<topic>` | "the plan" PR |
| **B. Execute** the plan | a dedicated **worktree** | `<type>/<topic>` | "the work" PR |

The worktree is created at the **start of execution**, not while writing the plan.

## Lifecycle

`PLANNED` → `IN PROGRESS` → `DONE`, mirrored by the filename: `TODO_` prefix while
open, prefix **removed** on completion. One topic per file; link related files with
`See also:`.

## Starting a plan (Flow A)

The intended path is to **hand your raw thoughts to a fresh agent session and let it write
the plan**. Paste the authoring prompt below with your notes appended — unordered and
half-formed is fine; the agent does the structuring, grounds the plan in the actual source
and memory, and states an assumption wherever your notes are silent rather than stalling.

### Authoring prompt

```
You are working on the GroundTruther QGIS plugin (QGIS 4 / Qt6). Author a planning file
from my notes below. Do NOT implement any of the work.

First: read CLAUDE.md, PLANNING/README.md and PLANNING/planning_rules.md, and review the
project memory (your recalled memories + the MEMORY.md index). Then read enough of the
actual source to make the plan concrete — a plan that contradicts the code is worse than
no plan.

Then, on a new branch `docs/plan-<kebab-topic>` in the main working copy (no worktree —
that comes at execution time), copy PLANNING/TEMPLATE_planning.md →
PLANNING/TODO_<kebab-topic>.md and fill in every section:
- Header table (Status: PLANNED; Worktree branch = the EXECUTION branch <type>/<topic>).
- Objective, in outcome terms.
- Context & background — cite real files as path:line and link the relevant memory slugs.
- Scope — explicit in/out bullets; this is where creep gets contained.
- Prerequisites, Worktree setup, Task breakdown (sub-tasks small enough to verify each).
- Acceptance criteria — including the manual QGIS GUI check *I* must do, since agents
  cannot drive the GUI.
- Risks & rollback.
- A self-contained Kickoff prompt (§6) that assumes zero prior conversation.
Leave the Progress log empty.

Where my notes are silent or ambiguous, pick a sensible default and state it — do not
stall. Then open the plan PR against master (gh, account epifanio) and report back: the
assumptions you made, and any question whose answer would actually change the plan. Do
NOT merge, and do NOT start the work.

My notes:
<paste your thoughts here — rough, unordered, whatever form they are in>
```

Useful to include in the notes (all optional — gaps become flagged assumptions): the topic
and its type (`feat`/`fix`/`docs`/`refactor`/`chore`); what "done" lets you *do*; what is
explicitly out; opinions on approach or ordering; what you will check by hand in QGIS.

### Doing it yourself

1. Copy [TEMPLATE_planning.md](TEMPLATE_planning.md) → `PLANNING/TODO_<kebab-topic>.md`.
2. Skim `CLAUDE.md` and the project memory first, so the plan doesn't contradict reality.
3. Fill every section — especially **Scope** (in/out), **Task breakdown**, and
   **Acceptance criteria**.
4. Write the **kickoff prompt**: self-contained, assumes no prior conversation.
5. Open the plan PR on `docs/plan-<topic>`; review and merge it before work starts.

Either way the **topic slug is kebab-case and identical across all three places**: the file
`TODO_<topic>.md`, the execution branch `<type>/<topic>`, and the worktree
`../groundtruther-<topic>`.

## Executing a plan (Flow B)

Paste the plan's kickoff prompt into a **fresh** agent session. The agent:

1. Reads `CLAUDE.md` and the project memory (`MEMORY.md` index + recalled entries) **first**.
2. Creates the worktree:
   ```bash
   cd /home/epinux/dev/groundtruther
   git fetch origin
   git worktree add ../groundtruther-<topic> -b <type>/<topic> origin/master
   cd ../groundtruther-<topic>
   ```
   This leaves the QGIS profile symlink (which points at the main working copy)
   untouched, so a WIP branch never breaks the running QGIS.
3. Works the Task Breakdown, verifying headlessly (`.venv/bin/pytest`, offscreen
   import/load per `CLAUDE.md`). Agents do **not** launch the QGIS GUI — that's the
   user's job, in the main copy.
4. Finishes per the **Definition of Done** (see
   [planning_rules.md §7](planning_rules.md)): tests green, **project memory updated**,
   Progress Log filled, `TODO_` prefix dropped and `Status: DONE`, work PR opened
   (`gh`, account `epifanio`) — **not merged**; the user reviews and merges.

Never stage `config/config.yaml` (machine-specific, holds a secret).

## Cleanup (after the work PR merges)

```bash
cd /home/epinux/dev/groundtruther
git worktree remove ../groundtruther-<topic>
git branch -d <type>/<topic>
```
