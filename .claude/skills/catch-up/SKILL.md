---
name: catch-up
description: Catch this account up after days away, read-only - a fresh worktree from origin, memory synced, the queue read and checked against GitHub, a report of what is deployed, running, next and owed. Use when the owner pastes the catch-up prompt, or when this checkout's last commit is days old and nobody pasted a prompt.
---
# Catch-up (`PLANNING/WORKFLOW.md` §2.1)

Follow the prompt in `PLANNING/WORKFLOW.md` §2.1 exactly, as session `catchup-<account>-<date>`:
build nothing, deploy nothing, delete nothing, open no PRs. One catch-up per account at a time: if
one is running, message it and stop. The checkout and its `CLAUDE.md` may be days old, so trust the
fresh worktree, `origin/<default branch>`, `gh pr list` and the running system, not the files alone.
Report in the four parts §2.1 names. A question the files could not answer, or answered wrongly, is
a gap in them: say so, change nothing; the fix is a planning session's work.
