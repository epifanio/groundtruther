<!-- Template for a GroundTruther planning file. Copy to PLANNING/TODO_<kebab-topic>.md
     and fill in every <placeholder>. Rules: PLANNING/planning_rules.md -->

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
