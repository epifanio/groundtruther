---
id: D-007
date: 2026-10-23
status: accepted
decided-by: epifanio, 2026-10-23 (WORKFLOW.md §12 Q5; standing choice in CLAUDE.md)
lanes: U, C, D, P
---
**Decision.** Every non-merge commit ends with
`Co-Authored-By: Claude <noreply@anthropic.com>`. The kit's **commit-identity module stays off**
(`COMMIT_IDENTITY=no`).

**Why.** The project wants the authorship of agent-assisted commits visible in its history. The
identity module does the opposite — it strips AI attribution trailers and restricts authorship to
an allowlist — so the two cannot both be installed. Asked as §12 Q5 at setup on 2026-10-23 and
answered: keep the trailer, leave the module out. The installed `.githooks/commit-msg` is therefore
a deliberate no-op: it exits 0 before its stripping step.

**Binds.** Every lane and every session. A future session that finds `.githooks/commit-msg` inert
should not "fix" it, and one that proposes the identity module must supersede this record first.
Merge commits carry no trailer, which is expected.
