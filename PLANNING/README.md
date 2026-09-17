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

1. Copy [TEMPLATE_planning.md](TEMPLATE_planning.md) → `PLANNING/TODO_<kebab-topic>.md`.
2. Skim `CLAUDE.md` and the project memory first, so the plan doesn't contradict reality.
3. Fill every section — especially **Scope** (in/out), **Task breakdown**, and
   **Acceptance criteria**.
4. Write the **kickoff prompt**: self-contained, assumes no prior conversation.
5. Open the plan PR on `docs/plan-<topic>`; review and merge it before work starts.

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
