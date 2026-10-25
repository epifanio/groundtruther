# Working on GroundTruther with agent sessions

This project is built by many agent sessions at once, from several machines and by several people,
under the rules in [`WORKFLOW.md`](WORKFLOW.md). This page is the short version for a person who
joins. The agent reads `CLAUDE.md`; you read this.

## 1. Your machine, once

```bash
git clone https://github.com/epifanio/groundtruther.git ~/dev/groundtruther
cd ~/dev/groundtruther
scripts/memory-repo.sh init https://github.com/epifanio/groundtruther-memory   # the private memory repo, cloned at ~/dev/groundtruther-memory
git config core.hooksPath .githooks                                 # the kit's hooks
git config user.name "<you>" && git config user.email "<yours>"    # identity module: one of the allowed addresses
```

You need `git`, `python3` (3.10 or newer), the GitHub CLI `gh` logged in (`gh auth status`), and
Claude Code. Then write a short note about yourself in the memory repo, `user_<your GitHub login>.md`
(who you are, how you like to work): every session you run reads it after `MEMORY.md`. Cloud
sessions need no setup: attach `epifanio/groundtruther-memory` alongside the project when the session starts.

## 2. How work happens

- **You have an idea, feedback or a bug**, or a GitHub issue. Open a session in this checkout and
  talk about it (an issue: give its number; the session that finishes the work closes it). That
  is a *planning session*: it reads the facts, asks you numbered questions with a recommendation
  each (a tick means *keep the recommendation*), writes or extends `PLANNING/TODO_<topic>.md`, gives
  each piece of work a row and a pastable prompt in the queue, lands one docs-only PR, and stops. It
  builds nothing.
- **You want work done.** `scripts/session.sh next`, or §1 of
  [`TODO_session_sequence.md`](TODO_session_sequence.md), shows the ⏭ row of each free slot and its
  prompt. Paste the prompt into a fresh session. That *build session* claims its row, builds one piece
  in its own worktree, closes its row with receipts and tells you the next prompt.
- **A machine that has been idle for days.** Paste the catch-up prompt (`WORKFLOW.md` §2.1) first.
  It is read-only and tells you what is deployed, running, next and owed.
- **Something urgent with no row.** Open a session and say so. It registers under *Beside the
  queue* in its first PR and follows the build rules.

## 3. The queue's marks

| Mark | Means |
|---|---|
| ⏭ | the next prompt to paste in that slot; one per slot |
| ▶ | running; *Who* says who pasted it |
| ⬜ | queued, later |
| ⏸ | waiting on something the row names |
| ✅ | done, with receipts: date, PRs, how it was verified, the memory note |
| ◐ | done with open ends, listed under *Open ends* |
| 💤 | deferred by a maintainer, with their words and the date |
| 🚫 | dropped, with why |

A ▶ row with nothing running stopped early: paste the same prompt again, it carries on from its
branch. Two people who paste the same prompt meet at the claim: the second sees ▶ and stops.

## 4. Decisions that bind more than one plan

A plan freezes the answers given for its own work. An answer that binds other plans too (a store, a
library ban, a public contract, a vocabulary, a deploy rule) becomes a record in
[`decisions/`](decisions/README.md) with a row in [`DECISIONS.md`](DECISIONS.md), written by the
planning session that heard it, in the plan's own PR. Later plans cite it instead of asking again,
and a build session that would have to break it stops and says so. To change one, talk to a planning
session: it writes a new record that supersedes the old one; nobody edits an accepted record. With
several maintainers a new record is `proposed` until the approval chosen at setup (`WORKFLOW.md` §12
Q10), and the rows that depend on it wait.

## 5. Who decides what

| Decision | Who |
|---|---|
| a plan's questions (then frozen) | any maintainer: epifanio; the plan records their name and the date |
| accepting a decision record | `WORKFLOW.md` §12 Q10 |
| moving a row up, deferring, dropping | any maintainer, with their name, their words and the date |
| the production go | one of epifanio, each time, never reused |
| "this session is done" (its worktree and branches may go) | the person who started it |

## 6. What runs by itself

Hooks (`.claude/settings.json`) sync memory at session start and end, print the queue at start, and
block five git mistakes before a command runs: a branch switch in the main checkout, a branch
deletion fed by `git branch` output, a force push onto an open PR, a worktree removal before you
declared the session done (then the session runs it with `SESSION_DONE=<session>` in front), and a
merge run by hand past `scripts/session.sh` (then, for the PR you named, `OWNER_MERGE=<pr>` in
front).
`.githooks/pre-push` runs the planning check before every push; CI runs it on every PR.

## 7. Where things are

| What | Where |
|---|---|
| the rules | [`WORKFLOW.md`](WORKFLOW.md) |
| where `PLANNING/` lives | in this repo |
| what runs next, what is deployed, what is owed | [`TODO_session_sequence.md`](TODO_session_sequence.md) |
| the plans | [`TODO_INDEX.md`](TODO_INDEX.md) |
| decisions | [`DECISIONS.md`](DECISIONS.md) |
| memory (private) | `epifanio/groundtruther-memory`, cloned at `~/dev/groundtruther-memory` |
| the scripts | `scripts/session.sh` (start, claim, close, next), `scripts/ci-wait.sh`, `scripts/memory-repo.sh` |
