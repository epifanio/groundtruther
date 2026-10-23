---
name: build-session
description: Build one queued work package as the named session - start in its own worktree, claim its row, build in one lane, integrate, close by the queue's §6.1. Use when the owner pastes a queue prompt or writes /build-session <session>.
argument-hint: <session>
---
# Build session `$0` (`PLANNING/WORKFLOW.md` §6–§8)

Session: `$0`. The prompt that follows this line (or the row's prompt in the queue's §2) says the
plan, the scope, how to verify, the paths and the gates. This skill carries the invariant part.

1. **Start.** `scripts/session.sh start $0`: the worktree `../<project>-$0` on `claude/$0`, the
   hooks, the identity, memory synced; it prints your row, your prompt and the plan files to read.
   Work only there. Read `MEMORY.md`, your `user_<login>.md`, the notes the prompt names, the plan's
   sections and the decisions it cites (`PLANNING/decisions/`).
2. **Claim first.** `scripts/session.sh claim $0`: your row to ▶ with the date and your handle, ⏭
   moved on, that PR merged before any other work. If the row is already ▶ under another name, stop
   and report: the slot is taken (§6.1).
3. **Work** (§6.2): one lane; commit and push after every finished step; tests through the real
   boundary; a gap in the plan is fixed in the plan, in the same PR; asked decisions stay asked;
   build nothing against an accepted record in `DECISIONS.md`: say so and leave that part undone.
4. **Integrate** (§6.3): PRs titled `[<short>] …`; `scripts/ci-wait.sh <n>` and merge on 0
   (`gh pr merge --merge`) unless the prompt names a gate; if `main` moved under you by files CI
   reads, merge it in and run the checks again; never rebase and force-push a branch with an open PR;
   on a conflict in the queue or the index take `main`'s side and redo your edit.
5. **Deploy** only as §8 says: staging while you hold the unit; production on a go from one of the
   approvers, each time; record it in the State table.
6. **Close**: `/close-session $0`.
