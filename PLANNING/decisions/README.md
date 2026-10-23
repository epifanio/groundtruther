# Decision records

One file per decision that binds more than one plan: `D-<nnn>_<slug>.md`, numbered in order, three
digits (`D-001`). The index is [`../DECISIONS.md`](../DECISIONS.md): one row per record, added in
the same PR. Who writes a record and when is [`../WORKFLOW.md`](../WORKFLOW.md) §4 (step 5); what a
build session does when its work would contradict one is §6.2.

## The shape

```markdown
---
id: D-001
date: 2026-10-22
status: accepted
decided-by: <name>, 2026-10-22 (TODO_<topic>.md §6 Q3)
supersedes: D-000
lanes: A, B
enforced-by: eslint no-restricted-imports (prisma)
enforce: import .*prisma in src/
---
**Decision.** One or two lines: what is decided, in words a session can act on.
**Why.** Two or three lines from the plan's §6: the drivers, the options not taken.
**Binds.** Which lanes, plans or paths must respect it, and what it rules out.
```

- `id`, `date`, `status` and `decided-by` are required. `supersedes`, `lanes`, `enforced-by` and
  `enforce` are optional. `enforced-by` names the linter rule or CI check that makes the decision
  stick, where the project has one: prefer it, a real lint with real scoping.
- `enforce: <regex> in <path prefix or glob>`, one line each, is the fallback for a project with no
  linter, or for non-code files: for an `accepted` record the checker runs the regex over the
  project's files in that scope (`git ls-files`, so ignored files and build output never enter it;
  `PLANNING/` is never scanned) and a match is rule D4, which fails CI. The scope is a path prefix
  (`src/`) or a glob (`src/**/*.py`). It is a grep, not a review: it catches a banned import or a
  keyword in the wrong directory, nothing about shape.
- `status` is one of `proposed`, `accepted`, `rejected`, `superseded by D-<nnn>`. The index row
  says the same words.
- A `proposed` record may be edited in the PR that proposes it. **An accepted record is never
  edited**: the one change it gets is its status line (and index row) set to `superseded by D-<nnn>`
  when a new record replaces it.
- A new record takes the next number. Two planning sessions that take the same number meet at the
  merge conflict on the index: take `master`'s side, renumber yours, redo your row.
- Rows, prompts and plans cite a record as `D-<nnn>`. A ⏭, ▶ or ⬜ row, or its prompt, may cite only
  an `accepted` record (checker rule D3); a ⏸ row may wait on a `proposed` one.
