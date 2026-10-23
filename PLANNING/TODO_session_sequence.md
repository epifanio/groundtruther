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

### Slot 1 — U (UI & plugin shell)

| Mark | Session | Who | Work | Prompt | Receipt / notes |
|---|---|---|---|---|---|
| ⏸ | `seq-U1-deps-message` | — | `publish-0-4` WP-4: load and say what is missing instead of dying, when the venv is absent | §2.4 | **Waits on** `seq-C1-deps-check` (it provides `gt/deps_check.py`) |

### Slot 2 — C (core & config), D (docs), P (packaging & install)

| Mark | Session | Who | Work | Prompt | Receipt / notes |
|---|---|---|---|---|---|
| ◐ | `seq-P2-release-zip` | claude | `publish-0-4` WP-1: one safe release zip from a tag; delete the two paths that ship the API key | §2.1 | 2026-10-24 · #50 · verified: built from a throwaway tag: 2.7 MB / 237 files; config/config.yaml, .venv, PLANNING/, website/, tests/, docs/, .claude/, .github/, grassdata/ absent; qtui/icons/ present (82 entries); no API-key value in the unpacked tree, and a planted fake key was refused; git status --short clean after a successful AND a failed build · memory note: 2026-10-24_seq-P2-release-zip.md |
| ⏭ | `seq-P1-release-metadata` | — | `publish-0-4` WP-2: `metadata.txt` typos, tags, homepage, icon path, 0.4 changelog | §2.2 |  |
| ⬜ | `seq-C1-deps-check` | — | `publish-0-4` WP-3: `gt/deps_check.py` — which required modules are importable, Qt-free | §2.3 | unblocks `seq-U1-deps-message` in slot 1 |
| ⏸ | `seq-D1-install-docs` | — | `publish-0-4` WP-5: the install page — what the Plugin Manager gives you and what it does not | §2.5 | **Waits on** `seq-U1-deps-message` (the page describes its real behaviour) |

**Order rules** (only about open rows; a closing session deletes the ones about itself):

- none yet
- `seq-C1-deps-check` before `seq-U1-deps-message`: C1 provides `gt/deps_check.py`, which U1 calls.
- `seq-U1-deps-message` before `seq-D1-install-docs`: the page describes the behaviour U1 builds.
- The P strand (P2, P1) and the C/U/D strand share no file, so they may run side by side **if the
  owner starts a second slot-2 session** (`WORKFLOW.md` §3.1). Slot 2 runs one at a time by default.

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
| **the owner's review, after the fact** | PR #50 is a code PR and should have been left for the owner (§6.3), but `scripts/session.sh close` was run without `--no-merge` and merged it into `master` at `63b9082` on 2026-10-24. The code is unreviewed, not unmerged. Revert it (`git revert -m 1 63b9082`) or review it on `master` | `seq-P2-release-zip` | the owner has read #50, or reverted it |
| the owner's yes or no | the artifact still carries ~1 MB of repo furniture beyond the six stripped dirs (.githooks/, scripts/, help/, epsg, CLAUDE.md, pytest.ini, pylintrc, pb_tool.cfg, compile_ui.sh, tmp/) — asked in #50 | `seq-P2-release-zip` | they answer; if yes, the strip list grows in seq-P1-release-metadata |

## 2. Prompts

One heading per queued session: `### 2.<n> \`<session>\``, its prompt in a `text` code block shaped
as `WORKFLOW.md` §4.1. When a session closes, it removes its block and leaves the heading as
`### 2.<n> \`<session>\` (closed <date>; its prompt is in git history)`, so the numbers never move.

### 2.1 `seq-P2-release-zip` (closed 2026-10-24; its prompt is in git history)

### 2.2 `seq-P1-release-metadata`

```text
/build-session seq-P1-release-metadata
Plan: PLANNING/TODO_publish-0-4.md WP-2 (metadata), slot 2, lane P. Scope: in metadata.txt fix the
two "Caracterization" typos (description, about) to "Characterization"; replace tags=python with
real discovery tags (seafloor, bathymetry, multibeam, backscatter, habitat, GRASS, and whatever
else fits); point homepage at https://epifanio.github.io/groundtruther/; correct
icon=qtui/icons/qgis/epi.gif to qtui/icons/epi.gif (the stray qgis/ — the file does exist at the
corrected path); write a real changelog entry for 0.4 describing the QGIS 4 / Qt6 work, replacing
the current run-on line about settings and GRASS widgets; and delete the bare line "Category of
the plugin: Raster, Vector, Database or Web", which configparser parses as a junk key because of
the colon. Also fix "Serafloor Caracterization" in the __init__.py module docstring — docstring
text only, do not touch _bootstrap_venv or classFactory (seq-U1-deps-message owns that file's
code). Leave version=0.4 and experimental=True exactly as they are (plan §6 Q2, Q4).
Verify on the real thing: python3 -c "import configparser; c=configparser.ConfigParser();
c.read('metadata.txt'); print(dict(c['general']))" parses with no junk key, and the path in `icon`
resolves to a file that exists and is tracked by git.
Touch only metadata.txt and the __init__.py docstring. Needs a yes: any change to version or the
experimental flag. Decisions that bind this work: D-007. Memory notes to read: MEMORY.md,
2026-10-23_adopt-groundtruther.md. Docs check: mkdocs build --strict -f website/mkdocs.yml.
```

### 2.3 `seq-C1-deps-check`

```text
/build-session seq-C1-deps-check
Plan: PLANNING/TODO_publish-0-4.md WP-3 (the dependency probe), slot 2, lane C. Scope: add
gt/deps_check.py — a Qt-free, QGIS-free module that reads the required runtime module names and
reports which are importable, returning enough for a caller to name the missing ones and decide
which features must be disabled. The 20 runtime dependencies are listed in
dependencies/requirements.txt: READ it, do not edit it, and note that a pip package name is not
always its import name (opencv-python imports as cv2, scikit-image as skimage) — handle that
mapping explicitly rather than guessing. Probe with importlib.util.find_spec, not by importing:
importing numba or cv2 costs seconds and can abort. No Qt, no qgis, no dialog here — the message
and the dialog are seq-U1-deps-message's.
Verify on the real thing: unit tests under tests/unit/ that run with no QGIS, covering all present,
some missing, and a package whose import name differs from its pip name. `.venv/bin/pytest
tests/unit/` green.
Touch only gt/deps_check.py and tests/unit/. Needs a yes: adding any new runtime dependency.
Decisions that bind this work: D-008 (gt/ stays importable without QGIS — this module especially,
since it must run before anything else works), D-003 (no print()), D-001 (absolute
`from groundtruther...` imports), D-007. When you close, set seq-U1-deps-message in slot 1 from
⏸ to ⏭: its wait is you. Memory notes to read: MEMORY.md, 2026-10-23_adopt-groundtruther.md.
Docs check: mkdocs build --strict -f website/mkdocs.yml.
```

### 2.4 `seq-U1-deps-message`

```text
/build-session seq-U1-deps-message
Plan: PLANNING/TODO_publish-0-4.md WP-4 (honest failure), slot 1, lane U. Scope: make the plugin
load and explain itself when its dependencies are absent, instead of dying. Today
__init__.py's _bootstrap_venv() is a no-op when there is no .venv — which is exactly what a QGIS
Plugin Manager install produces — so every one of the 20 runtime dependencies fails to import.
Call gt/deps_check.py (from seq-C1-deps-check) during startup; log the missing packages to the
GroundTruther panel; show ONE dialog naming them and linking the install page; and disable the
features that cannot work rather than letting them raise later. One dialog, not one per import.
Also fix the second mismatch while you are in here: setup_wsl.sh --venv creates `gtenv` but
_bootstrap_venv() looks for `.venv`, so the documented fallback install produces a venv the plugin
never loads — make them agree and say which name won.
Verify on the real thing: unpack the release zip into a CLEAN QGIS 4 profile with NO .venv and
confirm the plugin loads, logs, and shows the dialog once. You cannot drive the QGIS GUI: do the
headless import/load checks in CLAUDE.md, then write the GUI check into the queue's §3 for the
owner, naming exactly what they should see. Do not claim it verified until they confirm.
Touch only __init__.py, the dock/startup path, and setup_wsl.sh. Do not touch gt/deps_check.py
(seq-C1-deps-check owns it) or metadata.txt. Needs a yes: anything that changes plugin behaviour
beyond failing gracefully. Decisions that bind this work: D-003 (QgsMessageLog with the
GroundTruther tag, never print()), D-004 (the qgis.PyQt shim, never PyQt6), D-001, D-008, D-007.
Your PR changes code, so open it and LEAVE IT for the owner (§12 Q3): close your row ◐ with their
review and merge as the open end. Memory notes to read: MEMORY.md,
2026-10-23_adopt-groundtruther.md. Docs check: mkdocs build --strict -f website/mkdocs.yml.
```

### 2.5 `seq-D1-install-docs`

```text
/build-session seq-D1-install-docs
Plan: PLANNING/TODO_publish-0-4.md WP-5 (the install page), slot 2, lane D. Scope: on the MkDocs
site under website/docs/, say plainly what installing GroundTruther from the QGIS Plugin Manager
does and does not give you — it does NOT install the 20 Python dependencies, because the plugin
loads them from a .venv beside its source that the Plugin Manager never creates — and give the
supported route per platform from setup_wsl.sh / setup_windows.ps1 / setup_mamba.bat. Describe the
behaviour seq-U1-deps-message actually built (read its PR, do not assume), including what the
missing-dependency dialog says, so the page and the plugin agree word for word. Add the page to
the nav. Keep the project's habit of leading with the limitation rather than burying it — the
seabed-ribbon page is the model.
Verify on the real thing: mkdocs build --strict -f website/mkdocs.yml (strict catches a page
missing from the nav and a broken internal link), and read the rendered page, not the diff.
MERGING THIS PUBLISHES IT: any push to master touching website/** runs mkdocs gh-deploy
(WORKFLOW.md §8). Record the published master sha in the docs-site State row when you close.
Touch only website/. Needs a yes: none beyond the usual. Decisions that bind this work: D-006 (the
MkDocs site is the user docs; help/ is retired and takes no new pages), D-007. Memory notes to
read: MEMORY.md, 2026-10-23_adopt-groundtruther.md. Docs check: the build above IS the check.
```

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
- **Tag, build, verify and upload 0.4** (`publish-0-4` WP-6), after `seq-P2`…`seq-D1` have landed.
  The build is one command — `git tag -a v0.4 && scripts/make-release-zip.sh v0.4` → `dist/groundtruther-v0.4.zip`
  (`seq-P2-release-zip`, 2026-10-24: it refuses to write the zip unless `config/config.yaml`, `.venv`
  and the stripped directories are absent, the icons are present, and no API-key value appears in the
  tree). `unzip -l` it yourself anyway before uploading. The upload is a production rollout: the
  owner's own go, each time, never reused (`WORKFLOW.md` §8), with their plugins.qgis.org
  credentials, which no session holds (plan §6 Q5). From `plan-publish-0-4`, 2026-10-23.
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
- `metadata.txt` and `__init__.py` during `publish-0-4`: `seq-P1-release-metadata` edits
  `metadata.txt` and the `__init__.py` **docstring**; `seq-U1-deps-message` edits `__init__.py`
  **code**. One file, two sessions, two lanes — the prompts say which part each owns, and the order
  rules keep them apart. If they must overlap, the later one takes `master`'s version and redoes it.
- `scripts/`: lane **P** owns it, but `scripts/session.sh`, `memory-repo.sh` and `ci-wait.sh` are
  the session system's and are changed only by a planning session, never by a build session
  tidying up.

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
| **U** UI & plugin shell | `__init__.py`, `pygui/`, `qtui/`, `mixins/`, `groundtruther.py`, `groundtruther_dockwidget.py`, `configure.py`, `resources.qrc`, `resources_rc.py`, `resources/`, `compile_ui.sh`; **and the live QGIS install on the Linux machine** | one session at a time (slot 1) |
| **C** core & config | `gt/`, `config_model.py`, `config/`, `ioutils.py`, `episg.py`, `epsg_list.py`, `search_epsg.py`, `epsg/`, `ellipse.py`, `rectangle.py`, `qtpandas.py`, `grassconfig.py`, `tests/` | one session at a time (slot 2) |
| **D** docs | `website/`, `docs/`, `help/` | one session at a time (slot 2) |
| **P** packaging & install | `Makefile`, `setup_windows.*`, `setup_mamba.bat`, `setup_wsl.sh`, `scripts/`, `dependencies/`, `pip_cpu.py`, `pip_cuda.py`, `plugin_upload.py`, `metadata.txt`, `pb_tool.cfg`, `environment.yml`, `.github/workflows/` | one session at a time (slot 2) |

Slot 2 runs **one** session at a time by default, even though it holds three lanes: a second one
only when the order rules say the two share no file and no machine, and only when the owner starts
it (`WORKFLOW.md` §3.1). Lane **U** owns the live QGIS install: a GUI check is serialised because
the QGIS profile symlink points at the one main checkout.

### 6.3 Session conventions

Every plan cites `WORKFLOW.md` §5.2 by number (a one-line pointer, not a copy). Before starting, a
session checks the tokens left and asks the owner which model to use.

## 7. History

- 2026-10-23: created by `setup-session-system` (agent-session-kit).
