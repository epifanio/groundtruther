---
name: adopt-project
description: Harvest the knowledge a project already carries from agentic coding into the kit's homes - decision records, memory notes, plans and queue rows, the State table - then test it with a fresh session. Use once, when the kit is installed into a project that an agent was already building (SETUP step 7c), or when a colleague brings their own agent history.
argument-hint: [project]
---
# Adopt a project's existing knowledge (`PLANNING/WORKFLOW.md` §4)

A planning session named `plan-adopt-<project>`. Read once, write into the homes, keep one home per
fact, and cite the source of everything you write. You build nothing.

1. **Inventory.** `scripts/adopt-inventory.sh` lists the sources: instruction files, each machine's
   auto memory and transcripts, branches and PRs, issues, roadmap and decision files. Paste it into
   the plan's "What exists today". Ask the owner which sources still count and what is stale (§12
   Q13), as numbered questions with a recommendation each; the answers are frozen.
2. **Decisions.** Every standing choice found in instruction files, old ADRs or transcripts (a store,
   a library ban, a public contract, a vocabulary, a deploy rule) becomes
   `PLANNING/decisions/D-<nnn>_<slug>.md` with its row in `DECISIONS.md`: `accepted`, dated the day
   it was made when known, `decided-by` the owner, the source named in *Why*. A choice the owner no
   longer stands by is `rejected` with the reason, not silently dropped.
3. **Memory.** Lessons and corrections become `feedback_*` notes with *Why* and *How to apply*;
   where things live, `reference_*`; the owner's own habits, `user_<login>.md`. Each machine's auto
   memory comes in with `scripts/memory-repo.sh init <url> --import <dir>` (a clash is kept as a
   dated local copy: merge it by hand, delete the copy). Nothing the code shows; no secrets (the sync
   refuses them).
4. **Work in flight.** One plan per piece (§5), a row per session (§4 steps 7–8): an open PR's branch
   is a running session, ▶ with its author in *Who*; roadmap items are ⬜ rows or the owner's list;
   an issue enters by number (§4 step 2). The State table says what runs where now, read from the
   running system, not from a note.
5. **`CLAUDE.md`.** Keep the project's layout and build notes. Move the process rules the kit's
   section now covers out of it (two instructions that disagree are followed arbitrarily), and the
   standing choices into decisions. The kit's section stays between its markers.
6. **Transcripts** are read, never committed: distil a decision and its discarded options into the
   record's *Why* or the plan's "options not taken", and nothing else.
7. **Land it**: one docs-only PR `[plan-adopt-<project>] …`, the checker clean, `scripts/ci-wait.sh`,
   merged by §6.3; then the memory note and `scripts/memory-repo.sh sync`.
8. **Test.** Paste the first ⏭ prompt into a fresh session, or run `/catch-up` when nothing was
   queued: whatever it has to ask is a gap in the harvest, fixed in the files, never remembered.
