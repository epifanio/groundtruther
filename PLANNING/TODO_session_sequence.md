# TODO — Session sequence: what to paste next

**Status:** live since 2026-10-23. **Every queued session's prompt is in this file**, in the order
they run. The plans that own the work stay the truth for *what* to build; this file says *what runs
next* and *what is deployed now*, and carries the prompt to paste. The rules behind it are in
[`WORKFLOW.md`](WORKFLOW.md), and `python3 PLANNING/check_planning.py` checks this file.

## How to use it

1. In §1, find the **⏭** row of each slot: that is the next prompt to paste there. A slot that shows a
   **▶** row is busy: wait for that session to close, unless the order rules say the ⏭ one can run
   beside it. If a slot shows neither ▶ nor ⏭, its next session is the first ⬜ row.
2. Open that row's prompt in §2. Copy the whole code block and paste it into a fresh session (a
   short prompt starts with `/build-session <session>`: the skill carries the rest).
   `scripts/session.sh next` prints the same: each slot's state and the prompt to paste.
3. Nothing else. **Every session keeps this file current** (§6.1). It claims its row when it starts:
   ▶, the date, who pasted it in *Who*. When it closes it ticks the row, moves ⏭ on, records what it
   deployed and what it leaves open, and fixes any later prompt its work made stale. You never edit
   this file by hand.
4. **To add work** (a new topic, feedback, a bug), open a session and talk it through. That planning
   session writes or extends the plan, gives each piece a row and a prompt here, and stops
   (`WORKFLOW.md` §4).
5. **On an account or a machine that has been idle for days**, paste the catch-up prompt first
   (`WORKFLOW.md` §2.1).

Marks: ✅ done · ◐ done, with open ends (listed under *Open ends*) · ▶ running · ⏭ paste this next ·
⬜ later · ⏸ waiting (the row says on what) · 💤 deferred by a maintainer · 🚫 dropped. A slot has at
most one ⏭. The rows run top to bottom. If a row shows ▶ but no session is running, that session
stopped early: paste the same prompt again; it reads what is on its branch and carries on.

## 1. The queue

### State — what is deployed now

One row per unit. A session that deploys or switches something replaces **the rows of its own
units** and nothing else. What was there before is in git history and in the closed rows' receipts.
The running system is the truth: read it before a rollout (`WORKFLOW.md` §8).

| Unit | Now | Since (UTC) | Recorded by | Rollback · notes |
|---|---|---|---|---|
| Plugin on plugins.qgis.org | **0.3**, experimental, QGIS 3.0–3.99 · uploaded **2023-06-01** · plugin_id 2982 | 2023-06-01 | `plan-adopt-groundtruther` | **Read from the live feed** (`plugins.xml?qgis=3.99`), 2026-10-23 — *not* from `metadata.txt`, which says `version=0.4`, `qgisMinimumVersion=4.0`. **The QGIS 4 / Qt6 work has never been published:** `master` is 0.4, users get the 2023 QGIS-3 build. Publishing 0.4 is a production rollout — a production approver's go, each time (`WORKFLOW.md` §8). Rollback = re-upload the previous zip. |
| Docs site (`gh-pages` → <https://epifanio.github.io/groundtruther/>) | built from `master` **650a164** (`gh-pages` abe7632, MkDocs 1.6.1) | 2026-09-24 | `plan-adopt-groundtruther` | **publishes itself**: `.github/workflows/docs.yml` runs `mkdocs gh-deploy --force` on every push to `master` touching `website/**`. No go, no staging — merging a `website/` change *is* the deploy. Read live 2026-10-23: HTTP 200, and `gh-pages` says "Deployed 650a164". The site lags `master` whenever the commits in between touched no `website/**` path — that is the rule working, not drift, so **compare the two shas before concluding anything**; this cell deliberately does not name `master`'s tip, because the next merge would make it false. Rollback = merge a fix; the workflow redeploys. |

> **Both slots are empty** (since 2026-10-23, `plan-adopt-groundtruther`): there is no ⏭ and no ⬜,
> so **there is nothing to paste**. That is not a fault — the harvest found no work in flight to
> adopt. The next session is a **planning session**: open one, talk a topic through, and it writes
> the plan and queues the first prompt (`WORKFLOW.md` §4, `/plan-session`). Delete this line as soon
> as a slot has a row.

### Slot 1 — U (UI & plugin shell)

| Mark | Session | Who | Work | Prompt | Receipt / notes |
|---|---|---|---|---|---|

### Slot 2 — C (core & config), D (docs), P (packaging & install)

| Mark | Session | Who | Work | Prompt | Receipt / notes |
|---|---|---|---|---|---|

**Order rules** (only about open rows; a closing session deletes the ones about itself):

- none yet

### Beside the queue

Sessions that run without a queued row (urgent fixes, follow-ups) register here in their first PR.

| Mark | Session | Who | Work | Prompt | Receipt / notes |
|---|---|---|---|---|---|

### The owner's list (not sessions)

Each item carries the date it was raised, so a catch-up can say how long it has been waiting
(`WORKFLOW.md` §2.1 step 5).

- **Since 2026-10-23 · Where the roughness / mosaic work lives.** The owner, 2026-10-23: *"those are all unrelated the
  fastgis at the moment keep them alone, we probably need to move them out of fastgis and transfer
  them to my seafloor roughness repository"*. Open PRs **#37, #39, #40, #41, #42, #43** and their
  branches are **left untouched** until they decide — neither queued nor dropped. When they decide,
  it becomes a decision record (it binds more than one plan). #43 and #37 have gone conflicting with
  `master` in the month since they were touched; that is `master` moving, not a verdict.

### Deferred plans (💤, the owner's word)

- none yet

### Open ends (owed by a closed session)

| Due | What | From | Closes when |
|---|---|---|---|

## 2. Prompts

One heading per queued session: `### 2.<n> \`<session>\``, its prompt in a `text` code block shaped
as `WORKFLOW.md` §4.1. When a session closes, it removes its block and leaves the heading as
`### 2.<n> \`<session>\` (closed <date>; its prompt is in git history)`, so the numbers never move.

## 3. Checks owed by the owner

Things only the owner can do (try it on a device, look at it in a browser, decide), each with the
session it came from and the date.

- **Link the Linux machine to the memory repo and import its auto memory.** From
  `/home/epinux/dev/groundtruther`, once:
  `scripts/memory-repo.sh init https://github.com/epifanio/groundtruther-memory --import ~/.claude/projects/-home-epinux-dev-groundtruther/memory`
  (nothing is overwritten; a clash is kept as `<name>.local-<date>.md`). Until this runs, the
  memory repo holds only what setup and the harvest wrote: every `Related memory` slug the five
  closed plans cite (`config-validation`, `roughness-integration`, `fastgis-grass-api`,
  `data-model-facts`, `documentation`, `project-overview`, `april-2026-refactor`, `install-and-run`)
  exists **only** on that machine. From `plan-adopt-groundtruther`, 2026-10-23. Also worth running
  `scripts/adopt-inventory.sh --repo /home/epinux/dev/groundtruther` there and pasting the output.
- **Record the project's working state on `master`.** No file says whether the test suite passes
  today, or whether the plugin loads under QGIS 4 — only what is *deployed*. From the Linux machine
  (this Mac has no QGIS and no `.venv`): run `.venv/bin/pytest` and the offscreen load check in
  `CLAUDE.md` → Testing on `master`, and put the date and result in the State table as a
  "Test suite on `master`" row. From `plan-adopt-groundtruther-gaps`, 2026-10-23.
- **Is `sip` reachable through the QGIS shim in QGIS 4?** `mixins/video_browser_mixin.py:693` does
  `from PyQt6 import sip`, the only violation of D-004. If `from qgis.PyQt import sip` works, that
  line is a one-word fix and D-004 gains an `enforce: PyQt6 in mixins/` line in a follow-up record;
  if it does not, D-004 should say so as a named exception. Needs a running QGIS 4 to answer, which
  only the owner has. From `plan-adopt-groundtruther`, 2026-10-23.

## 4. Where two sessions can still collide

Shared files, machines and data that two lanes both touch, one line each, with the rule that keeps
them apart.

- `PLANNING/TODO_session_sequence.md` and `PLANNING/TODO_INDEX.md`: every session edits them. On a
  conflict, take `master`'s version and redo your edit.
- `PLANNING/DECISIONS.md`: every planning session that promotes an answer adds a row. On a conflict,
  take `master`'s version; if another session took your number, renumber your record and
  redo your row.
- `config/config.yaml` on each machine: gitignored, machine-specific, and it holds the GRASS/FastGIS
  API key. No session stages it, pastes it, or logs it. The committed template is
  `config/config.example.yaml`.
- The **live QGIS install** (profile symlink → the main checkout on the Linux machine): lane **U**
  only, one session at a time. Agents never launch the GUI; they name the check for the owner.
- `pygui/Ui_*.py` vs `qtui/*.ui`: the `.ui` files are stale. Never run `compile_ui.sh` wholesale —
  it regenerates from stale `.ui` and silently drops hand-added widgets (`CLAUDE.md`).
- `website/docs/configuration/settings-reference.md`: lane **D** owns the file, but any lane that
  adds a config key must add its row (§6.3 rule 3). Coordinate in the plan, or the suite fails.

## 5. Work outside the queue

Plans that carry their own prompt and are not queued until the owner asks.

- none yet

## 6. Rules every session follows

The whole rulebook is [`WORKFLOW.md`](WORKFLOW.md). This section is the part every prompt points at.

### 6.1 Keeping this file current (every prompt repeats this)

- **One home for prompts.** A session in the queue has its full prompt here, in §2. A plan may keep
  the background, but its copy of the prompt is replaced by a pointer to this file.
- **At the start: claim.** Before any other work, a session opens a PR that only sets its own row in
  §1 to ▶ (with "started", the date, and the handle of who pasted the prompt in *Who*) and moves ⏭
  to the next row that can run, and merges it. A session beside the queue adds its row to *Beside
  the queue* the same way. Until the claim is on `master`, the queue tells everyone the
  slot is free. **Two people, one prompt:** the second claim PR conflicts on this file, takes
  `master`'s version, finds the row already ▶ with another name in *Who*, and stops: it
  reports and builds nothing. The claim is the lock. `scripts/session.sh claim <session>` does the
  claim, PR and merge included.
- **At the close**, in its last PR, a session does eight things. Throughout this section
  "**merged**" means *merged by the session* for a **docs-only** PR, and *opened and left for the
  owner* for a PR that **changes code** (`WORKFLOW.md` §6.3, §12 Q3) — a code row therefore closes
  ◐, with the owner's review and merge as its open end:
  1. sets its row to ✅ with the date, the PRs, how it was verified, what it shipped as and the memory
     note. If something is still owed (a soak, a dated check, a rollout, a part cut short), the row is
     ◐ instead, and each owed thing gets a line in *Open ends*; a GitHub issue the plan's brief cites
     is closed with the receipts (`scripts/session.sh close … --issue <n>` does it);
  2. makes sure its slot shows one ⏭, on the first row that can run: the first ⬜ row below its own,
     or a ⏸ row whose wait is now met. A ⏸ row whose wait is still open stays ⏸;
  3. replaces the State rows of what it deployed or switched: its own units' rows only;
  4. deletes the *Open ends* lines it settled;
  5. fixes any later prompt that its work made wrong (a path, a version, a precondition, an answer);
  6. writes the next prompt of its slot if it is missing. When no row is left, it asks the owner what
     comes next;
  7. removes its own prompt block from §2, leaving the heading marked closed;
  8. runs `python3 PLANNING/check_planning.py` and fixes what it reports. CI runs the same rules.
  `scripts/session.sh close <session> …` does 1, 2, 4, 7 and 8 (and deletes the order rules about
  the session) and lands the PR; 3, 5 and 6 stay the session's own.
- **After a production rollout** that follows the last merge, the record is a second, docs-only PR.
  A record PR does not record its own number.
- **When `master` moved under an edit of this file**, take its version and make the edit
  again. Two versions of one row are never merged by hand.
- **The owner decides the order.** A new row goes at the end of its slot. A row moves up, is deferred
  (💤) or dropped (🚫) only on a maintainer's word (`WORKFLOW.md` §7), and the row then carries their
  name, their words and the date.
- Done sessions keep their row in §1, as the receipt.

### 6.2 Lanes and slots

| Lane | Touches | Rule |
|---|---|---|
| **U** UI & plugin shell | `pygui/`, `qtui/`, `mixins/`, `groundtruther.py`, `groundtruther_dockwidget.py`, `configure.py`, `resources.qrc`, `resources_rc.py`, `resources/`, `compile_ui.sh`; **and the live QGIS install on the Linux machine** | one session at a time (slot 1) |
| **C** core & config | `gt/`, `config_model.py`, `config/`, `ioutils.py`, `episg.py`, `epsg_list.py`, `search_epsg.py`, `epsg/`, `ellipse.py`, `rectangle.py`, `qtpandas.py`, `grassconfig.py`, `tests/` | one session at a time (slot 2) |
| **D** docs | `website/`, `docs/`, `help/` | one session at a time (slot 2) |
| **P** packaging & install | `Makefile`, `setup_windows.*`, `setup_mamba.bat`, `setup_wsl.sh`, `scripts/`, `dependencies/`, `pip_cpu.py`, `pip_cuda.py`, `plugin_upload.py`, `make_zip.sh`, `metadata.txt`, `pb_tool.cfg`, `environment.yml`, `.github/workflows/` | one session at a time (slot 2) |

Slot 2 runs **one** session at a time by default, even though it holds three lanes: a second one
only when the order rules say the two share no file and no machine, and only when the owner starts
it (`WORKFLOW.md` §3.1). Lane **U** owns the live QGIS install: a GUI check is serialised because
the QGIS profile symlink points at the one main checkout.

### 6.3 Session conventions

Every plan cites `WORKFLOW.md` §5.2 by number (a one-line pointer, not a copy). Before starting, a
session checks the tokens left and asks the owner which model to use.

## 7. History

- 2026-10-23: created by `setup-session-system` (agent-session-kit).
