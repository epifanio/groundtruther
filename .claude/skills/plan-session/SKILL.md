---
name: plan-session
description: Run a planning session for this project - establish the facts, ask the owner what is theirs to decide, write or extend the plan, promote decisions that bind other plans, queue the work with pastable prompts, land one docs-only PR, stop. Use when the owner talks about a topic (an idea, feedback, a bug) instead of pasting a prompt.
argument-hint: [topic]
---
# Planning session (`PLANNING/WORKFLOW.md` §4)

Topic: $ARGUMENTS. You plan; you build nothing. The rulebook is `PLANNING/WORKFLOW.md`; this skill
is its checklist. Read §1–§5 once, then:

1. **Start.** `scripts/session.sh start plan-<topic>` (the worktree, the hooks, memory synced). Read
   `MEMORY.md`, your `user_<login>.md`, `PLANNING/DECISIONS.md` and the queue's §1.
2. **Take the ask down** in the owner's words, dated, and say what kind it is. A GitHub issue:
   `gh issue view <n>`, and the brief cites `#<n>`.
3. **Look before writing**: `TODO_INDEX.md`, `PLANNING/`, memory, `DECISIONS.md`. One feature has one
   plan. A record that bears on the topic is a constraint to cite, not a question to ask again.
4. **Establish the facts** from the code and the live system, each with where and when it was read.
5. **Ask** numbered questions, each with a recommendation; a tick means keep it. Write the answers
   verbatim with the name of who answered and the date; then they are frozen. An answer that binds
   other plans becomes `PLANNING/decisions/D-<nnn>_<slug>.md` with its row in `DECISIONS.md` (§4 step
   5); with several maintainers it is `proposed` until the approval of §12 Q10.
6. **Write the plan** by §5.1 (the one-line pointer to §5.2, not a copy), or extend the one that
   exists.
7. **Cut it into sessions**, one lane and one work package each, and **place each** (§4 steps 7–8): a
   row at the end of its slot with a prompt in the queue's §2 (§4.1: the short form when every
   session is Claude Code), or the plan's own prompt and a line in the queue's §5, or the owner's
   list, or 💤 with their words and the date.
8. **Register the plan** in `TODO_INDEX.md`, then **bring the queue up to date**:
   `python3 PLANNING/check_planning.py --live` and fix what it reports.
9. **Land it**: one docs-only PR `[plan-<topic>] …`, the checker clean, `scripts/ci-wait.sh <n>`,
   merged by §6.3. Then the memory note, its index line, `scripts/memory-repo.sh sync`.
10. **Report and stop**: what was written, where each session sits, what is still asked, the next
    prompt to paste. A fresh session holding only the plan is the plan's test.
