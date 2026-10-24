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
| Docs site (`gh-pages` → <https://epifanio.github.io/groundtruther/>) | built from `master` **31e13cb** (PR #85, `seq-D1`; was cf8be3d, and 650a164 before that) | 2026-10-24 | `seq-D1-install-docs` | **publishes itself**: `.github/workflows/docs.yml` runs `mkdocs gh-deploy --force` on every push to `master` touching `website/**`. No go, no staging — merging a `website/` change *is* the deploy. Read live 2026-10-23: HTTP 200, and `gh-pages` says "Deployed 650a164"; republished 2026-10-24 from `cf8be3d` when #80 merged `website/docs/installation/macos.md`, and again the same day from `31e13cb` when #85 added `website/docs/installation/plugin-manager.md` — `gh-pages` says *"Deployed 31e13cb"* and the new page answered HTTP 200. The site lags `master` whenever the commits in between touched no `website/**` path — that is the rule working, not drift, so **compare the two shas before concluding anything**; this cell deliberately does not name `master`'s tip, because the next merge would make it false. Rollback = merge a fix; the workflow redeploys. |

### Slot 1 — U (UI & plugin shell)

| Mark | Session | Who | Work | Prompt | Receipt / notes |
|---|---|---|---|---|---|
| ✅ | `seq-U1-deps-message` | epifanio | `publish-0-4` WP-4: load and say what is missing instead of dying, when the venv is absent | §2.4 | 2026-10-24 · #67 **merged by the owner** (`master` `ab010ed`; *"Go ahead and merge #67"*), opened and left for their review (§6.3) · verified: QGIS 4.2.1 (macOS, arm64) in the signed harness of TODO_mac-install-test.md §3, re-run against `master`'s own content after the merge — with no `.venv`, `startPlugin` True (was **False**), **13** messages tagged GroundTruther (were **0**), the stub is what QGIS holds; with a `.venv`, the real plugin module imports. tests/unit 432 passed, 5 pre-existing pyarrow/GDAL failures. **GUI confirmed by the owner 2026-10-24** on `gt-mac-novenv`, reinstalled from a `make-release-zip.sh` artifact of `ab010ed` first (both profiles still held pre-WP-4 code): the dialog renders with a live install link, headline *"6 of the 20"*, the 4 optional ones apart, Show Details carrying all ten REQUIRED/optional; `groundtruther=true`, no error marker. The log *panel*'s display was not eyeballed, but `_log_report` runs before the stub that produced that dialog is returned · memory note: 2026-10-24_seq-U1-deps-message.md
| ✅ | `seq-U2-macos-profile-docs` | epifanio | `mac-install-test` WP-3: the macOS profile path and a headless harness that is faithful to the app's signing, in `CLAUDE.md` and the install page | §2.7 | 2026-10-24 · #78, #80 · verified: the documented harness run verbatim on this Mac against QGIS 4.2.1: qgis.core imports pandas+pyarrow itself, messageReceived captured nothing while a spy did, gt.config_check imported; the -I variant dies at init_fs_encoding. mkdocs build --strict passes (venv on homebrew python3.12; python3.15 cannot build watchdog) · memory note: 2026-10-24_seq-U2-macos-profile-docs.md |

### Slot 2 — C (core & config), D (docs), P (packaging & install)

| Mark | Session | Who | Work | Prompt | Receipt / notes |
|---|---|---|---|---|---|
| ◐ | `seq-P2-release-zip` | claude | `publish-0-4` WP-1: one safe release zip from a tag; delete the two paths that ship the API key | §2.1 | 2026-10-24 · #50 · verified: built from a throwaway tag: 2.7 MB / 237 files; config/config.yaml, .venv, PLANNING/, website/, tests/, docs/, .claude/, .github/, grassdata/ absent; qtui/icons/ present (82 entries); no API-key value in the unpacked tree, and a planted fake key was refused; git status --short clean after a successful AND a failed build · memory note: 2026-10-24_seq-P2-release-zip.md |
| ◐ | `seq-P1-release-metadata` | epifanio | `publish-0-4` WP-2: `metadata.txt` typos, tags, homepage, icon path, 0.4 changelog | §2.2 | 2026-10-24 · #56 **merged by the owner 2026-10-24** (`master` 4f4d6b5; they said *"Go ahead and merge #56"*) · verified: configparser on metadata.txt: one [general] section, no key containing a space (origin/master had the junk key "category of the plugin"); icon=qtui/icons/epi.gif exists on disk and is tracked by git (the declared qtui/icons/qgis/epi.gif did not exist); and inside a real artifact built with scripts/make-release-zip.sh from a throwaway tag at the PR head: the zips metadata.txt parses with no junk key, description/tags/homepage as intended, version=0.4 experimental=True qgisMinimumVersion=4.0 unchanged, and groundtruther/qtui/icons/epi.gif present (2439 bytes). git status --short clean after the build; tag and zip deleted. py_compile __init__.py passes; check_planning 0/0. No website/ or docs/ page references any changed value (grep), so no docs claim to re-verify; mkdocs is not installed on the Mac, CI docs.yml is the run that counts · memory note: 2026-10-24_seq-P1-release-metadata.md |
| ✅ | `seq-C1-deps-check` | epifanio | `publish-0-4` WP-3: `gt/deps_check.py` — which required modules are importable, Qt-free | §2.3 | 2026-10-24 · #61 **merged by the owner 2026-10-24** (`master` 6e22c32; they said *"Go ahead and merge #61"*) · verified: throwaway venv in the scratchpad (Python 3.15.0, pytest 9.1.1; no .venv on this Mac): tests/unit/test_deps_check.py -> 24 passed; whole unit suite 421 passed, 3 skipped, 5 pre-existing pyarrow/GDAL failures in untouched files. check_planning 0/0; py_compile clean; no print() (D-003) and a test asserts no qgis/Qt in sys.modules after import (D-008). Finding: a static module-level import-graph walk from groundtruther.py shows 15 of the 20 deps are reached unguarded (mostly via pygui/querybuilder_gui.py, imported eagerly by the dock), so their absence stops the dock being constructed at all; only av, cv2, PyOpenGL are guarded and pydantic/starlette are off the chain. **Corrected 2026-10-24 from 16: a miscount in the prose, not in the tuple.** starlette is in requirements.txt and no module imports it. · memory note: 2026-10-24_seq-C1-deps-check.md |
| ⏭ | `plan-pandas-datetime-record` | — | promote "no pandas datetimes in `gt/`" to a decision record, and queue the call sites still unfixed | §2.8 | Added on the owner's word, 2026-10-24: *"Queue a planning session to promote 'no pandas datetimes in gt/' to a decision record."* **Moved ahead of `seq-D1-install-docs` by epifanio, 2026-10-24:** *"Move plan-pandas-datetime-record ahead of seq-D1-install-docs in slot 2."* `seq-D1` had already claimed the slot by then (#83), so it runs to its close and this is the ⏭ behind it (§3.2). Settles two of `seq-C2-parquet-no-pandas`'s open ends, and **D-004's `enforce:` line**, folded in by epifanio 2026-10-24: *"Fold the D-004 enforce record into plan-pandas-datetime-record when it runs."* Writes `PLANNING/` only |
| ◐ | `seq-D1-install-docs` | epifanio | `publish-0-4` WP-5: the install page — what the Plugin Manager gives you and what it does not | §2.5 | 2026-10-24 · #85 · verified: mkdocs build --strict -f website/mkdocs.yml clean (throwaway venv from website/requirements-docs.txt, python3.12 — 3.15 cannot build watchdog); rendered HTML read, not the diff; merged on the owner's go at master 31e13cb and the deploy confirmed live: https://epifanio.github.io/groundtruther/installation/plugin-manager/ HTTP 200, gh-pages 'Deployed 31e13cb' · shipped as: the docs site, published from master 31e13cb · memory note: 2026-10-24_seq-D1-install-docs.md |
| ◐ | `seq-C2-parquet-no-pandas` | claude | `mac-install-test` WP-2: keep datetimes out of pandas — **every** pandas datetime operation segfaults QGIS 4.2.1 on macOS, at `gt/image_manager.py:70` and `gt/video_manager.py:170` (the row's name is narrower than the work) | §2.6 | 2026-10-24 · #73 · verified: in QGIS 4.2.1's own interpreter (the plan's §3 harness): the SIGSEGV reproduced at exit 139, then test_imagemetadata.pq reading 5900x38 with its timestamp index intact AND the survey-CSV reader and compute_frame_indices returning [0, 250] — both call sites of §5. 43 tests pass under the broken pandas 3.0.3 and 464 under a working 3.1.0; a reverted reader fails 14 tests on good pandas and takes pytest down with exit 139 on the broken one · memory note: 2026-10-24_seq-C2-parquet-no-pandas.md |

**Order rules** (only about open rows; a closing session deletes the ones about itself):

- none yet
  after `seq-D1` had already claimed the slot (#83). Nothing technical orders the two — both only
  write docs — so `seq-D1` was left to run to its close rather than being stopped, and the moved row
  is the ⏭ behind it. Paste it as soon as `seq-D1` closes.
- The P strand (P2, P1) and the C/U/D strand share no file, so they may run side by side **if the
  owner starts a second slot-2 session** (`WORKFLOW.md` §3.1). Slot 2 runs one at a time by default.

### Beside the queue

Sessions that run without a queued row (urgent fixes, follow-ups) register here in their first PR.

| Mark | Session | Who | Work | Prompt | Receipt / notes |
|---|---|---|---|---|---|
| ◐ | `mac-install-test` | epifanio | install GroundTruther on macOS QGIS 4.2.1 and exercise it against the Zenodo test dataset | — | 2026-10-24 · #54 (claim), this PR · verified: installed from a `make-release-zip.sh` artifact into two fresh profiles (`gt-mac-test` with a `.venv`, `gt-mac-novenv` without). Found two blockers: `gt.image_manager.load_metadata` **SIGSEGVs QGIS 4.2.1** and no `sys.path` fix exists, and `CLAUDE.md`'s headless recipe makes good wheels look broken. 23 of 24 deps work; `pydantic` fails in *stock* QGIS. Full measurements, and the owner's GUI checklist, in `PLANNING/TODO_mac-install-test.md` · memory note: 2026-10-24_mac-install-test.md |
| ◐ | `sip-shim-d004` | epifanio | answer the D-004 `sip` question and remove the last `PyQt6` import | — | 2026-10-24 · #88, #91 (**merged by the owner 2026-10-24**, `master` `9d01eb1`; they said *"Go ahead and merge #91"*) · verified: in the signed macOS harness on QGIS 4.2.1: from qgis.PyQt import sip resolves, isdeleted is False for a live layer and True after sip.delete, and the real _track_layer_valid imported from the real module returns True alive / False after deletion with the attribute reset / False when None. grep for 'from PyQt6'/'import PyQt6' over the plugin: none left. check_planning 0/0; py_compile clean. Suite not run: no .venv on this Mac and nothing under tests/ imports mixins/ · memory note: 2026-10-24_sip-shim-d004.md |
| ◐ | `mac-ondevice-test` | epifanio | the on-device test of 0.4: the Zenodo dataset loaded, the plugin configured, every data path run in QGIS 4.2.1's own interpreter — the owner's gate on WP-6 | — | 2026-10-24 · #95 · verified: QGIS 4.2.1 (macOS arm64) own interpreter, signed harness of TODO_mac-install-test.md §3, plugin AS INSTALLED in the gt-mac-test profile, config written into that profile pointing at ~/dev/groundtruther_test_dataset (Zenodo 7995674, 2.0 GB), no API key. All 8 data paths pass: deps 20/20 present; config 0 errors 0 warnings; load_metadata 5900 images; KDTree nearest resolves to a real jpg; cv2 decodes 1360x1024; 3538 of 5900 annotated; read_parquet(mbes, epoch_us) 20,581,319 soundings in 1.5 s; bathy_2015.tif valid, EPSG:32619. THE macOS SEGFAULT IS GONE on the path that used to be certain. In gt-mac-novenv: _bootstrap_venv() None, 10 of 20 missing (6 blocking), because QGIS 4.2.1 on macOS BUNDLES pandas/numpy/pyarrow/scipy. The dock, toolbar, Log Messages panel and dialog appearance are NOT verified: no agent can drive the window · memory note: 2026-10-24_mac-ondevice-test.md |

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
| **the owner's review, after the fact** | PR #50 is a code PR and should have been left for the owner (§6.3), but `scripts/session.sh close` was run without `--no-merge` and merged it into `master` at `63b9082` on 2026-10-24. Asked whether to revert, the owner said *"Leave #50 in master — I'll review it on master myself"* (2026-10-24), so **it stays in `master` and is not reverted**. What is owed is the review, not the merge | `seq-P2-release-zip` | the owner has reviewed `scripts/make-release-zip.sh` and the Makefile on `master` |
| the owner's yes or no | the artifact still carries ~1 MB of repo furniture beyond the six stripped dirs (.githooks/, scripts/, help/, epsg, CLAUDE.md, pytest.ini, pylintrc, pb_tool.cfg, compile_ui.sh, tmp/) — asked in #50 | `seq-P2-release-zip` | they answer; if yes, the strip list grows in seq-P1-release-metadata |
| before the next session that closes a code PR | scripts/session.sh close reuses whatever PR is open on claude/<session> and merges it, so closing on the code branch would have merged #56 — exactly how #50 went in by mistake. Branch claude/close-guard adds a path guard and is NOT in master. Until it lands, close a code session on a second branch cut from origin/master, with PLANNING/queue.py close plus the PR by hand (done here, and again by `seq-C1-deps-check` on 2026-10-24) | `seq-P1-release-metadata` | claude/close-guard is merged, or the rulebook names the two-branch order |
| — | The GUI check in QGIS on the Mac is the owner's: queue §3 -> PLANNING/TODO_mac-install-test.md §6, both profiles already built | `mac-install-test` | closes when the owner reports what they saw |
| when #73 merges | PR #73 is a code PR left for the owner to review and merge; the GUI confirmation is step 9 of TODO_mac-install-test.md §6 (browse an image in the gt-mac-test profile), plus a survey-metadata CSV in the video browser for the second call site | `seq-C2-parquet-no-pandas` | #73 merged and both paths exercised without taking QGIS down |
| done 2026-10-24 | website/docs/data-model/image-metadata.md said the file is read with pandas.read_parquet and that the index is a DatetimeIndex. Corrected in **#76**, merged after #73 (`e9a0d47`) so the site never described unbuilt behaviour; the page is published. mbes-soundings.md:6 is deliberately NOT part of it — the MBES table is read by pygui/querybuilder_gui.py, which #73 does not touch, so that line is still accurate | `seq-C2-parquet-no-pandas` | ✅ closed |
| next planning session — **queued 2026-10-24 as `plan-pandas-datetime-record`, §2.8** | the no-datetime64 constraint binds every future gt/ reader of temporal data, and gt/pandas_safe.py is where a record would point; a build session writes none (WORKFLOW.md §6.2) | `seq-C2-parquet-no-pandas` | a decision record exists or the owner declines it |
| done 2026-10-24 | the same crash in pygui/querybuilder_gui.py:620,733,739, scripts/build_ribbon.py:75,90 and pip_cpu.py:8 (not previously listed) now reads through gt/pandas_safe.py — **PR #81, merged at `de84a58`** on the owner's go. The module grew `temporal="epoch_us"` (int64 microseconds, 8 bytes a row) for the million-row MBES table and `set_index=False`, because moving object datetimes out of an index re-triggers the fault. No live `pd.read_parquet` call is left outside tests | `seq-C2-parquet-no-pandas` | **closed** |
| the owner, before WP-6 | both Windows setup scripts print a QGIS3 profile path; the new page says so rather than fixing them, since they are outside lane D | `seq-D1-install-docs` | setup_windows.ps1 and setup_mamba.bat print QGIS4 |
| `plan-pandas-datetime-record` (the owner folded it in, 2026-10-24: *"Fold the D-004 enforce record into plan-pandas-datetime-record when it runs."*) | D-004 still has no enforce: line, though there is no longer anything to violate it — the record asks for a follow-up record and a build session writes none | `sip-shim-d004` | that record lands, adding enforce: PyQt6 in mixins/ |
| **BLOCKER on WP-6** — lane U | the owner ran §6.1 on 2026-10-24: the plugin loaded and the dock opened, but **QGIS vanished** when they clicked a row in the image-annotation tool. Reproduced (exit 139) in QGIS's own interpreter: the row click reaches `mixins/image_browser_mixin.py:606`, `pd.DataFrame([row])` where the row's NAME is the object-dtype datetime index label, so pandas infers a dtype and segfaults — not a Parquet read, one call past what #73/#81 fixed. Three one-line fixes measured to work; only this site has the shape. Written up as `TODO_mac-install-test.md` §6.2 | `mac-ondevice-test` | the call is fixed and the owner browses an image without QGIS dying |
| lane D, next docs session | the published install page says '15 of the 20 Python packages it needs are not installed'; measured on macOS QGIS 4.2.1 it is 10 of 20 (6 blocking), because the app bundles pandas/numpy/pyarrow/scipy. gt/deps_check.py:73's comment generalises the same way. The runtime dialog counts correctly; it is the prose that is platform-shaped | `mac-ondevice-test` | the page and the comment say it per-platform, or drop the number |

## 2. Prompts

One heading per queued session: `### 2.<n> \`<session>\``, its prompt in a `text` code block shaped
as `WORKFLOW.md` §4.1. When a session closes, it removes its block and leaves the heading as
`### 2.<n> \`<session>\` (closed <date>; its prompt is in git history)`, so the numbers never move.

### 2.1 `seq-P2-release-zip` (closed 2026-10-24; its prompt is in git history)

### 2.2 `seq-P1-release-metadata` (closed 2026-10-24; its prompt is in git history)

### 2.3 `seq-C1-deps-check` (closed 2026-10-24; its prompt is in git history)

### 2.4 `seq-U1-deps-message` (closed 2026-10-24; its prompt is in git history)

### 2.5 `seq-D1-install-docs` (closed 2026-10-24; its prompt is in git history)

### 2.6 `seq-C2-parquet-no-pandas` (closed 2026-10-24; its prompt is in git history)

### 2.7 `seq-U2-macos-profile-docs` (closed 2026-10-24; its prompt is in git history)

### 2.8 `plan-pandas-datetime-record`

```text
Plan the decision record for "no pandas datetimes in gt/", as session `plan-pandas-datetime-record`
(slot 2 of PLANNING/TODO_session_sequence.md). This is a PLANNING session: it writes the record, the
plan and the queue rows, and builds nothing. First command:
`git fetch origin && git worktree add ../groundtruther-plan-pandas-datetime-record -b claude/plan-pandas-datetime-record origin/master`
(if that branch already exists, add the worktree on it and carry on from what it holds; an app-made
session worktree counts: name its branch `claude/plan-pandas-datetime-record`), then work only there.
`scripts/session.sh start plan-pandas-datetime-record` does this and prints this prompt. The skill
`/plan-session` carries PLANNING/WORKFLOW.md §1–§5; read §4 step 5 (promoting an answer to a record),
§5.3 and PLANNING/decisions/README.md for the record's shape.
Check the tokens left and ask the owner which model to use.
Claim first: a PR that only sets your row in §1 to ▶ ("started" and the date, your handle in Who) and
moves ⏭ on, merged before any other work (`scripts/session.sh claim plan-pandas-datetime-record`).
Memory: attach `epifanio/groundtruther-memory` (local: `scripts/memory-repo.sh sync` at start and
end); read `MEMORY.md`, 2026-10-24_seq-C2-parquet-no-pandas.md and 2026-10-24_mac-install-test.md.
Read PLANNING/WORKFLOW.md §1–§5; PLANNING/TODO_mac-install-test.md §5 (the measurements and the
crash frame); PLANNING/DECISIONS.md and PLANNING/decisions/ (D-008 is the closest in shape — same
lanes, and it explains why it carries no enforce regex); gt/pandas_safe.py as it stands on `master`.

Why there is a record to write. In QGIS 4.2.1 on macOS, pandas' datetime C extension is broken (a
pandas/numpy C-API ABI mismatch in QGIS's own bundle): every pandas datetime operation SIGSEGVs the
application — pd.to_datetime, any datetime64 Series, pd.to_timedelta, and even an EMPTY
datetime64 array. `seq-C2-parquet-no-pandas` fixed the two gt/ call sites (#73, `e9a0d47`) behind
gt/pandas_safe.py and left this as an open end, because a build session writes no record
(WORKFLOW.md §6.2). Three findings of its own decide the shape of the rule: the breakage CANNOT be
probed for at runtime (the probe is the crash), so the rule is unconditional on every platform and
not a macOS gate; pd.ArrowDtype looks like the tidy alternative and is a trap (reading one element
back builds a pd.Timestamp and dies); and the real hazard is pandas' type INFERENCE — the
DataFrame/Series constructors and set_index infer datetime64 from object-dtype datetimes — so "do
not call pd.to_datetime" would be too narrow a rule to be useful.

What to decide with the owner, each asked with a recommendation (WORKFLOW.md §4, step 5), then frozen:
1. The scope the record binds: gt/ only, or every module that reads temporal data (pygui/ and
   scripts/ have call sites too — see the open end below). Recommend the wider scope, since the
   crash does not care which directory it is in.
2. Whether it carries an `enforce:` regex for the checker (D4) or, like D-008, says why it cannot.
   A regex for `pd.to_datetime|read_parquet|datetime64` over gt/, pygui/ and scripts/ would be
   cheap, but it cannot see inference through a constructor, which is the real hazard, and it must
   not fire on gt/pandas_safe.py itself. Recommend an enforce line WITH an exemption for
   pandas_safe.py, and say plainly in the record that it catches the obvious half only.
3. Whether the rule is permanent or expires when QGIS ships a fixed bundle. Recommend permanent
   with a stated review trigger, since nothing tells the plugin which build it is running on.
Write the record as PLANNING/decisions/D-009_<slug>.md (the next free id; confirm it is free) with
its row in PLANNING/DECISIONS.md in the same PR, status accepted on merge (one maintainer,
WORKFLOW.md §4 step 5). Point it at gt/pandas_safe.py as the one home, and cite the crash frame.

Also settle, while you are in here, the second open end seq-C2 left: the same crash lives in
pygui/querybuilder_gui.py:620,733,739 and scripts/build_ribbon.py:75,90, which are lanes U and P,
outside lane C — arrow_table_to_dataframe() is the drop-in. Queue that as its own row (or rows, if
the two lanes must not share a session) with a pastable prompt, and say in the order rules how it
relates to seq-U2-macos-profile-docs, which also touches lane U. Then move both of seq-C2's open
ends: the record one closes when the record exists; the call-site one closes when its row does.

Also fold in D-004's enforce line, on the owner's word 2026-10-24: "Fold the D-004 enforce record
into plan-pandas-datetime-record when it runs." D-004 (Qt through the qgis.PyQt shim) deliberately
carries no `enforce:` regex, and says why: at the time there was exactly one violation,
mixins/video_browser_mixin.py's `from PyQt6 import sip`, so a grep would have failed CI. That is no
longer true. `sip-shim-d004` measured `from qgis.PyQt import sip` working in QGIS 4.2.1 and removed
the import (#91, `master` 9d01eb1); `grep -rnE '^\s*(from PyQt6|import PyQt6)' --include='*.py'`
over the plugin now returns nothing. So write the follow-up record D-004 asks for — a NEW record
that supersedes or amends it, whichever PLANNING/decisions/README.md says, not a silent edit of an
accepted one — carrying `enforce: PyQt6 in mixins/` or wider. Two things to get right: the generated
pygui/Ui_*.py files carry a `# Created by: PyQt6 UI code generator` header and two files have the
string in a comment, so a bare `PyQt6` regex over the whole tree fails the build — scope it, or match
an import statement; and ask the owner whether it binds `mixins/` only or every hand-written module,
recommending the wider scope for the same reason as question 1 above. Then take the D-004 line out
of this file's *Open ends* (it is `sip-shim-d004`'s, and that row goes ◐ → ✅ when it leaves).

Touch only PLANNING/. Build nothing, change no code, deploy nothing (WORKFLOW.md §2).
Needs the owner's answers: the three questions above, the scope of the D-004 follow-up, and any
row you add (§7).
Decisions that bind this work: D-007 (the commit trailer). D-008 is the model to follow, not a
constraint on this one. D-004 is not a constraint either — it is the second record this session
writes a follow-up to.
Before closing: update PLANNING/TODO_mac-install-test.md §5 and PLANNING/TODO_INDEX.md if the record
changes what they claim; `python3 PLANNING/check_planning.py` clean (it checks the record's front
matter, its index row, and runs any enforce line you add over the whole tree — so an enforce regex
that is too broad will fail the build, which is the point of trying it before you commit to it).
Close by PLANNING/TODO_session_sequence.md §6.1: your row ✅ (or ◐, with its open ends) with the
date, PRs and memory note; ⏭ on the next row that can run; your prompt removed from §2; any later
prompt your work made stale. `scripts/session.sh close plan-pandas-datetime-record --mark … --prs …
--verified … --note …` does the mechanical part. Your PR is docs-only, so you merge it yourself
(§6.3). Then push the dated memory note `plan-pandas-datetime-record` and put its commit in your
final report.
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
- **Look at GroundTruther in QGIS on the Mac** — the GUI half of `mac-install-test`, and the only
  part of it no agent could do. Two profiles are already built, so it is launch-and-look:
  `gt-mac-novenv` is a Plugin Manager install (no `.venv`) and `gt-mac-test` is the same plugin with
  a working one, both under `~/Library/Application Support/QGIS/QGIS4/profiles/`. The ordered
  checklist — what to click, what should appear, and what the `GroundTruther` log panel should say —
  is `PLANNING/TODO_mac-install-test.md` §6, and §6.2 there is how to debug it. **Open the profile
  explicitly** — `open -na /Applications/QGIS-final-4_2_1.app --args --profile gt-mac-test` — because
  QGIS reopens whichever profile it used last, and the plugin is not in `default` (the owner hit this
  on 2026-10-24). Step 10 is the one that matters: browsing an image is expected to **take QGIS down
  with it**, and if it does not, `seq-C2-parquet-no-pandas` needs re-scoping. Please don't delete the
  two profiles; `seq-C2` will want them. From `mac-install-test`, 2026-10-24. **Update, `seq-C2`
  2026-10-24:** re-scoping is not needed — the crash was reproduced (exit 139) and both call sites
  are fixed in **PR #73**, which is open for review. Until #73 is merged, step 10 still takes QGIS
  down; after it merges, that step is how to confirm the fix in the GUI, and a survey-metadata CSV
  in the video browser confirms the second call site.
- **Tag, build, verify and upload 0.4** (`publish-0-4` WP-6), after `seq-P2`…`seq-D1` have landed.
  The build is one command — `git tag -a v0.4 && scripts/make-release-zip.sh v0.4` → `dist/groundtruther-v0.4.zip`
  (`seq-P2-release-zip`, 2026-10-24: it refuses to write the zip unless `config/config.yaml`, `.venv`
  and the stripped directories are absent, the icons are present, and no API-key value appears in the
  tree). `unzip -l` it yourself anyway before uploading. The upload is a production rollout: the
  owner's own go, each time, never reused (`WORKFLOW.md` §8), with their plugins.qgis.org
  credentials, which no session holds (plan §6 Q5). From `plan-publish-0-4`, 2026-10-23.
- **Record the project's working state on `master`.** No file says whether the test suite passes
  today, or whether the plugin loads under QGIS 4 — only what is *deployed*. From the Linux machine
  (`mac-install-test`, 2026-10-24: the Mac now **does** have QGIS 4.2.1 and a working `.venv`, but
  its results are not Linux's — see `PLANNING/TODO_mac-install-test.md`): run `.venv/bin/pytest` and the offscreen load check in
  `CLAUDE.md` → Testing on `master`, and put the date and result in the State table as a
  "Test suite on `master`" row. From `plan-adopt-groundtruther-gaps`, 2026-10-23.
- ~~**Is `sip` reachable through the QGIS shim in QGIS 4?**~~ **Answered 2026-10-24 by
  `sip-shim-d004`, and no longer the owner's:** it is. `from qgis.PyQt import sip` resolves in QGIS
  4.2.1 and `isdeleted` behaves, measured in the signed macOS harness — the item said this needed a
  running QGIS that only the owner has, which stopped being true once that harness existed.
  `mixins/video_browser_mixin.py` now goes through the shim (PR #91, merged 2026-10-24, `master` `9d01eb1`) and no
  `from PyQt6` / `import PyQt6` statement is left in the plugin. What remains is the follow-up
  record adding `enforce: PyQt6 in mixins/` to D-004 — an open end on `sip-shim-d004`, not a check.

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
