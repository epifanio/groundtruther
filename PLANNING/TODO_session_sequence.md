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
| ◐ | `plan-pandas-datetime-record` | epifanio | promote "no pandas datetimes in `gt/`" to a decision record, and queue the call sites still unfixed | §2.8 | 2026-10-24 · #127 (claim), this PR · wrote **D-009** (the pandas rule) and **D-010** (D-004 restated, with its enforce line) · verified: QGIS 4.2.3 (pandas 3.0.5, numpy 2.5.2, pyarrow 25.0.1) in the signed harness of CLAUDE.md, each case its own process with `-u` and its exit status read un-piped — **nine cases, all exit 0** (the per-case table is in D-009 and TODO_mac-install-test.md §5). **QGIS 4.2.1 is no longer installed**, so its side of that table is quoted from §5, not re-measured. Both records' enforce lines tested in both directions at `master` d6f09e9: clean as the tree stands, and planted violations reported as D4 in every scope, then reverted. check_planning 0/0. PLANNING/ only, no code touched. The prompt's "call sites still unfixed" were already fixed by PR #81 (`de84a58`), so no row was queued · memory note: 2026-10-24_plan-pandas-datetime-record.md |
| ◐ | `seq-D1-install-docs` | epifanio | `publish-0-4` WP-5: the install page — what the Plugin Manager gives you and what it does not | §2.5 | 2026-10-24 · #85 · verified: mkdocs build --strict -f website/mkdocs.yml clean (throwaway venv from website/requirements-docs.txt, python3.12 — 3.15 cannot build watchdog); rendered HTML read, not the diff; merged on the owner's go at master 31e13cb and the deploy confirmed live: https://epifanio.github.io/groundtruther/installation/plugin-manager/ HTTP 200, gh-pages 'Deployed 31e13cb' · shipped as: the docs site, published from master 31e13cb · memory note: 2026-10-24_seq-D1-install-docs.md |
| ◐ | `seq-C2-parquet-no-pandas` | claude | `mac-install-test` WP-2: keep datetimes out of pandas — **every** pandas datetime operation segfaults QGIS 4.2.1 on macOS, at `gt/image_manager.py:70` and `gt/video_manager.py:170` (the row's name is narrower than the work) | §2.6 | 2026-10-24 · #73 · verified: in QGIS 4.2.1's own interpreter (the plan's §3 harness): the SIGSEGV reproduced at exit 139, then test_imagemetadata.pq reading 5900x38 with its timestamp index intact AND the survey-CSV reader and compute_frame_indices returning [0, 250] — both call sites of §5. 43 tests pass under the broken pandas 3.0.3 and 464 under a working 3.1.0; a reverted reader fails 14 tests on good pandas and takes pytest down with exit 139 on the broken one · memory note: 2026-10-24_seq-C2-parquet-no-pandas.md |
| ⏭ | `seq-D2-docs-pandas-per-version` | — | the site says which QGIS build the pandas segfault belongs to, and stops claiming the MBES table is read with `pandas.read_parquet` | §2.9 | Queued on the owner's word, 2026-10-24: *"Queue a docs row for the two website pages."* Three findings at `master` 62a7d85, all lane D (D-006): `image-metadata.md:19` is accurate about 4.2.1 but frames it as the reason, where **D-009** is; `macos.md:67`'s "on QGIS 4.2.1 only 10 of the 20" is version-shaped and unmeasured on 4.2.3 (that is `mac-ondevice-test`'s own open end, folded in); and `mbes-soundings.md:6` is now **false** — PR #81 moved `pygui/querybuilder_gui.py` onto `pandas_safe.read_parquet`. **Merging `website/` publishes the site** (§1 State) |
| ▶ | `seq-C3-roughness-keyless-gateway` | epifanio | make the keyless `seafloor-gateway` a configuration the plugin supports, instead of a key it refuses to go without | §2.10 | started 2026-10-25 · Queued 2026-10-24 from **D-011** question 3 (the plugin should call `https://seafloor.fastgis.eu`, not the keyed FastGIS copy). **The open end that asked for this overstated it, and this row corrects it:** the gateway *is* reachable today without code — `Roughness.direct_url` posts keyless and `mixins/roughness_mixin.py:842` derives the mosaic URL from it by sibling path — but that field is documented as the on-host GPU fast path (`config_model.py:109`), skips `base_url`+`route` composition, and is per-route. So this is not "unreachable": it is a documented keyed path plus an escape hatch being misused. The work is to make the keyless remote gateway a first-class choice. Nothing here is urgent: the GPU box is offline (§3) |
| ⏸ | `seq-C4-seafloor-code-moves` | — | move the four computing modules D-011 names out of this repository and onto the seafloor side | — | Queued 2026-10-24 from **D-011**: `gt/ribbon.py` (1065), `scripts/build_ribbon.py` (1195), `gt/roughness_join.py` (164), `gt/mosaic_nav.py` (PR #43) — ~2,400 lines. **Waits on** three things, all outside this repository: 0.4.1 being listed on plugins.qgis.org (D-011 question 4 — moving code out of a plugin whose release is awaiting approval risks the release), the GPU box being up so anything moved can be exercised at all, and a clone-and-diff of `stereo-roughness`, which was read through the GitHub API and has had no push since 2026-06-22. No prompt yet: it would describe a tree none of us has seen |

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
| ✅ | `mac-profile-ownership` | epifanio | make the macOS QGIS profiles a resource the rulebook owns, and give them a rebuild script | — | 2026-10-24 · **#103, merged by the owner at `master` `6ca19b9`** · **touched profiles: `gt-mac-test` (rebuilt its `.venv`), `gt-mac-novenv` (plugin files refreshed)**. Why: a `.venv` measured working at 07:31 was gone by 09:21 and no session's log held a deletion — git isolates the repo, not `~/Library/.../QGIS4/profiles/`. Adds `scripts/mac-profile-install.sh` (overlay from a git ref, never delete, keep `config/config.yaml`, install exactly what `gt/deps_check.py` reports missing) and the §3.1 rule for who may write to a profile. Verified on this Mac: refuses `--venv` for `gt-mac-novenv`, refuses an unknown profile with no flag, refuses a running QGIS; idempotent second run in 1.3 s; non-vacuous — `geojson` removed by hand was detected and reinstalled; `config.yaml` survived six runs; `gt-mac-test` reports 0 of 20 missing and all ten packages import for real under the signed harness. check_planning 0/0 · memory note: 2026-10-24_mac-ondevice-test.md |
| ✅ | `deps-install-docs` | epifanio | the dependency dialog links to the reader's own OS, and the macOS install route is fixed | — | 2026-10-24 · **#104, merged by the owner at `master` `6ce2c92` — which published the site** · verified: the page's own command could not run (`ModuleNotFoundError: No module named 'encodings'` without PYTHONHOME) and `--user` installs where `_bootstrap_venv()` never looks; replaced with `--target` into `<plugin>/.venv/lib/python<X.Y>/site-packages`, version derived not hardcoded, run verbatim against 4.2.1 and 4.2.3. `install_docs_url()` maps sys.platform to macos/windows/linux with the index as fallback; both URLs fetched live (200). 9 new tests incl. a guard that every URL has a page in the mkdocs nav |
| ✅ | `ci-docs-and-tests` | epifanio | run the tests and build the docs on every pull request | — | 2026-10-24 · **#105, merged by the owner at `master` `e6da796`** · why: the suite had NEVER run in CI and `mkdocs --strict` first ran in the job that *publishes*. `checks.yml` adds both as PR jobs; `dependencies/requirements-test.txt` derived empirically and proved from an empty venv (483 passed, 6 skipped). Three GeoTIFF tests now skip without GDAL instead of failing — per test, not module-level, and they still run and pass under QGIS's interpreter with PROJ_DATA set |
| ◐ | `d011-seafloor-boundary` | epifanio | where the seafloor roughness / mosaic work lives: the boundary, what moves to the API, and the six parked PRs | — | 2026-10-24 · this PR · wrote **D-011** on the owner's word (*"we have the processing on the API and QGIS holds the UI to trig the api, send payload and receive and render results"*) · verified by measurement, not by reading any repo's prose: `api.fastgis.eu/openapi.json` (200, 533 paths) still serves all four `/seafloor/*` paths, so FastGIS's own seafloor-gateway split plan (in that repo, named in D-011) claims they "never shipped" and is stale; `seafloor.fastgis.eu/seafloor/health` 502 `roughness service unreachable` (gateway up, GPU box offline); `roughness.epinux.com/health` 403 CF-Access, the expected tokenless answer. Four modules named as processing on the wrong side (`gt/ribbon.py`, `scripts/build_ribbon.py`, `gt/roughness_join.py`, `gt/mosaic_nav.py` in #43); #41 found to be **not seafloor work at all**. Two `enforce` lines tested both ways at `955f7ba`. PLANNING/ only, no code touched · memory note: 2026-10-24_d011-seafloor-boundary.md |
| ✅ | `locale-unset-crash` | epifanio | an unrecorded locale must not kill the plugin in `__init__` | — | 2026-10-24 · **#106, merged by the owner at `master` `229d808`** · `QSettings().value('locale/userLocale')[0:2]` is a TypeError when the key was never written. Now `user_locale()`, `""` for absent. **Corrected claim**: this does NOT make a complete install headless-verifiable — measured, the next failure is `self.iface.addToolBar(...)` and `iface` is None without a GUI. Impact on GUI users unproven: all three profiles carry `userLocale=en_US`. Test runs the shipped function via `ast`, non-vacuous (3 of 8 fail with the bug restored) |

### The owner's list (not sessions)

Each item carries the date it was raised, so a catch-up can say how long it has been waiting
(`WORKFLOW.md` §2.1 step 5).

- **Answered 2026-10-24 by D-011 · Where the roughness / mosaic work lives.** Raised 2026-10-23
  (*"we probably need to move them out of fastgis and transfer them to my seafloor roughness
  repository"*) and settled by the owner on 2026-10-24: *"we have the processing on the API and QGIS
  holds the UI to trig the api, send payload and receive and render results"*. The boundary, the four
  modules that move, and a per-PR disposition for **#37, #39, #40, #41, #42, #43** are in
  `decisions/D-011_seafloor-processing-on-the-api.md`. The PRs stay open: the record recommends the
  moves wait until 0.4.1 is listed, and #41 turns out not to be seafloor work at all. #43 and #37 are
  conflicting with `master`; that is `master` moving, not a verdict.
- **Since 2026-10-24 · Two of the six parked PRs can land on their own.** D-011 re-read them
  individually: **#41** (collapsible Settings sections, `configure.py` + `tests/gui/`) is not
  seafloor work at all and was parked with the batch by mistake, and **#42** is a 24-line fix to a
  UI label (`gt/roughness_interpret.py`) that the boundary does not touch. Both are the owner's to
  merge or drop; neither waits on anything.

### Deferred plans (💤, the owner's word)

- none yet

### Open ends (owed by a closed session)

| Due | What | From | Closes when |
|---|---|---|---|
| **the owner's review, after the fact** | PR #50 is a code PR and should have been left for the owner (§6.3), but `scripts/session.sh close` was run without `--no-merge` and merged it into `master` at `63b9082` on 2026-10-24. Asked whether to revert, the owner said *"Leave #50 in master — I'll review it on master myself"* (2026-10-24), so **it stays in `master` and is not reverted**. What is owed is the review, not the merge | `seq-P2-release-zip` | the owner has reviewed `scripts/make-release-zip.sh` and the Makefile on `master` |
| done 2026-10-24 | the artifact's "~1 MB of repo furniture" was measured rather than estimated, and **the premise was wrong**: 888 KB of it is `epsg`, which `search_epsg.py`, `episg.py` and `pygui/epsg.py` all read at runtime by path beside their own module. The owner said strip it (*"let's deal with the rest of #50's repo furniture"*), so #116 removes the 28 KB that is genuinely dev-only — `.githooks/`, `help/`, `tmp/`, CLAUDE.md, Makefile, pb_tool.cfg, pylintrc, pytest.ini, compile_ui.sh, resources.qrc — and **protects** `epsg`, `dependencies/requirements.txt` and `environment.yml` in REQUIRED with the reason beside each. `scripts/` and `plugin_upload.py` went earlier, in #108 and #112. 230 -> 212 entries. Guards proved non-vacuous both ways. **0.4.1 as published predates all of this** and still carries the tooling; it was not worth superseding a live release for 28 KB | `seq-P2-release-zip` | ✅ closed |
| done — **the guard is in `master`** | `scripts/session.sh close` used to reuse whatever PR was open on `claude/<session>` and merge it, which is how #50 went in by mistake. **Fixed twice over, and verified on `master` 2026-10-24:** `merge=no` is now the DEFAULT (`--merge` is opt-in, `--no-merge` kept only for compatibility), and even with `--merge` the new `pr_outside_lane()` asks GitHub for the PR's files and refuses to merge past the lane. `claude/close-guard` (`f1db515`, *"close merges nothing without an explicit go-ahead"*) is an ancestor of `master`. **The two-branch close is no longer necessary** — close on the session's own branch | `seq-P1-release-metadata` | ✅ closed |
| — | The GUI check in QGIS on the Mac is the owner's: queue §3 -> PLANNING/TODO_mac-install-test.md §6, both profiles already built | `mac-install-test` | closes when the owner reports what they saw |
| when #73 merges | PR #73 is a code PR left for the owner to review and merge; the GUI confirmation is step 9 of TODO_mac-install-test.md §6 (browse an image in the gt-mac-test profile), plus a survey-metadata CSV in the video browser for the second call site | `seq-C2-parquet-no-pandas` | #73 merged and both paths exercised without taking QGIS down |
| done 2026-10-24 | website/docs/data-model/image-metadata.md said the file is read with pandas.read_parquet and that the index is a DatetimeIndex. Corrected in **#76**, merged after #73 (`e9a0d47`) so the site never described unbuilt behaviour; the page is published. mbes-soundings.md:6 is deliberately NOT part of it — the MBES table is read by pygui/querybuilder_gui.py, which #73 does not touch, so that line is still accurate | `seq-C2-parquet-no-pandas` | ✅ closed |
| done 2026-10-24 | `scripts/mac-profile-install.sh` was a code PR, left for the owner (§6.3). **Merged by them 2026-10-24** on their word (*"fix it and retag"*, after they asked for the three open PRs to go in), `master` `6ca19b9`, and used the same day to refresh both profiles to `6ce2c92`. Still unexercised: the `--force` path (rewriting a profile under a running QGIS), and any machine but this Mac | `mac-profile-ownership` | ✅ closed |
| done 2026-10-24 | the no-datetime64 constraint is now **D-009** (`PLANNING/decisions/D-009_no-pandas-datetime-dtypes.md`), written by `plan-pandas-datetime-record`: object dtype everywhere, Arrow through `gt/pandas_safe.py`, five `enforce` lines over `gt/`, `pygui/`, `mixins/`, `scripts/` and the root modules (`tests/` deliberately out — the suites poison these calls by name). Accepted when its PR merges; a different answer to any of its three asked questions is a new record | `seq-C2-parquet-no-pandas` | **closed** |
| done 2026-10-24 | the same crash in pygui/querybuilder_gui.py:620,733,739, scripts/build_ribbon.py:75,90 and pip_cpu.py:8 (not previously listed) now reads through gt/pandas_safe.py — **PR #81, merged at `de84a58`** on the owner's go. The module grew `temporal="epoch_us"` (int64 microseconds, 8 bytes a row) for the million-row MBES table and `set_index=False`, because moving object datetimes out of an index re-triggers the fault. No live `pd.read_parquet` call is left outside tests | `seq-C2-parquet-no-pandas` | **closed** |
| done 2026-10-24 | both Windows setup scripts printed a **QGIS3** profile path while `metadata.txt` declares `qgisMinimumVersion=4.0`, so anyone following them copied the plugin into a directory QGIS 4 never reads — and both scripts SHIP in the artifact. `setup_mamba.bat:52` and `setup_windows.ps1:139` now print QGIS4, each with the reason beside it. Still untested on Windows (issue #4) | `seq-D1-install-docs` | ✅ closed |
| done 2026-10-24 | the follow-up record is **D-010**, written by `plan-pandas-datetime-record` on the owner's word (*"Fold the D-004 enforce record into plan-pandas-datetime-record when it runs."* (that record is D-010)): D-004 restated and superseded, carrying `enforce: ^\s*(from|import)\s+PyQt6` over `mixins/`, `gt/`, `pygui/`, `scripts/` and the root modules. It matches an **import statement**, not the bare name, which is what lets the scope be wide: the generated `pygui/Ui_*.py` headers, two code comments and the prose in `metadata.txt`, `README.md` and `website/` all carry the string and none of them match | `sip-shim-d004` | **closed** |
| done 2026-10-24 | the GUI half of the on-device test. The owner ran §6.1 and QGIS segfaulted at step 10 (`mixins/image_browser_mixin.py:606`, `pd.DataFrame([row])` on a row named by the object-dtype datetime index — `TODO_mac-install-test.md` §6.2). Fixed in **PR #100, merged `0155844`**; both test profiles were refreshed from `master` (they hold copies, and were stale) and **the owner then confirmed in the window: *"The image drew and QGIS stayed up"*** — no new crash report, the process still alive. Both halves of the on-device test now pass | `mac-ondevice-test` | **closed** |
| **queued 2026-10-24 as `seq-D2-docs-pandas-per-version`, §2.9** | the published install page says '15 of the 20 Python packages it needs are not installed'; measured on macOS QGIS 4.2.1 it is 10 of 20 (6 blocking), because the app bundles pandas/numpy/pyarrow/scipy. `gt/deps_check.py:73`'s comment generalises the same way. The runtime dialog counts correctly; it is the prose that is platform-shaped — and the page now says 10, still tied to 4.2.1 and never measured on 4.2.3 | `mac-ondevice-test` | that row closes, or the owner declines it |
| **queued 2026-10-24 as `seq-D2-docs-pandas-per-version`, §2.9** (the owner: *"Queue a docs row for the two website pages."*) | the site should say which build the pandas segfault belongs to, now that D-009 measured 4.2.3 clean. **This line overstated it when written and is corrected here:** `macos.md` says nothing about the segfault — its version-shaped claim is the dependency count at `:67` — while `mbes-soundings.md:6` was missed and is now false (PR #81). All three are in the queued row. Not edited by `plan-pandas-datetime-record`: merging `website/` publishes the site and publishing is the owner's to time (§1 State) | `plan-pandas-datetime-record` | that row closes, or the owner declines it |
| **queued 2026-10-24 as `seq-C3-roughness-keyless-gateway`, §2.10** | `gt/roughness_client.py:223` raises `"No API key configured"` on the `endpoint`+`route` path and `mixins/roughness_mixin.py:836` gates the dialog the same way, while `seafloor-gateway` is unauthenticated **by design**. **This line said that makes the gateway need a code change, and that was wrong** — `Roughness.direct_url` already posts keyless to a full URL and the mosaic URL is derived from it (`roughness_mixin.py:842`), so the gateway can be reached by configuration today. What is true is narrower: `direct_url` is documented as the *on-host* fast path (`config_model.py:109`), so that is an escape hatch being misused, not support. The row makes it first-class | `d011-seafloor-boundary` | that row closes, or the owner keeps the keyed FastGIS route |
| **queued 2026-10-24 as `seq-C4-seafloor-code-moves` (⏸)** | the four moves D-011 names — `gt/ribbon.py`, `scripts/build_ribbon.py`, `gt/roughness_join.py` and `gt/mosaic_nav.py` (PR #43) — out of this repository and into the seafloor side. ~2,400 lines. Deliberately not started: 0.4.1 is uploaded and awaiting approval, and the GPU box is offline so nothing moved could be exercised | `d011-seafloor-boundary` | 0.4.1 is listed and the owner answers D-011 questions 1 and 2 |
| **the owner, in the FastGIS repo** | FastGIS `main` still serves all four `/seafloor/*` paths (live OpenAPI, 2026-10-24) although its own decision of 2026-08-22 was that seafloor stays out of it, and its split plan is 💤 deferred. One surface should exist, not two. Nothing in this repository can close it | `d011-seafloor-boundary` | FastGIS drops the routes, or the owner keeps them and D-011 question 3 is answered that way |
| — | `stereo-roughness` was read through the GitHub API, not cloned, and has had no push since 2026-06-22 — the service deployed on the GPU box may be ahead of its `master`. Check before moving any code into it | `d011-seafloor-boundary` | someone clones it and compares, or the moves begin and find out |
| — | PR #41 (collapsible Settings sections) is not seafloor work and was parked with the batch by mistake; it is unrelated to D-011 and can land on its own | `d011-seafloor-boundary` | #41 merges, or the owner drops it |
| the owner | D-009's three questions (scope, the enforce lines, permanent-with-a-review-trigger) and D-010's scope question carry this session's recommendation and are accepted as written when the PR merges. A different answer is a new superseding record, not an edit | `plan-pandas-datetime-record` | the owner merges the PR, or answers differently |

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

### 2.8 `plan-pandas-datetime-record` (closed 2026-10-24; its prompt is in git history)

### 2.9 `seq-D2-docs-pandas-per-version`

```text
Work on docs-audit WP-D2 (the site says which QGIS build the pandas segfault belongs to), as session
`seq-D2-docs-pandas-per-version` (slot 2 of PLANNING/TODO_session_sequence.md). First command:
`git fetch origin && git worktree add ../groundtruther-seq-D2-docs -b claude/seq-D2-docs-pandas-per-version origin/master`
(if that branch already exists, add the worktree on it and carry on from what it holds; an app-made
session worktree counts: name its branch `claude/seq-D2-docs-pandas-per-version`), then work only
there. `scripts/session.sh start seq-D2-docs-pandas-per-version` does this and prints this prompt.
Claim first: a PR that only sets your row in §1 to ▶ ("started" and the date, your handle in Who) and
moves ⏭ on, merged before any other work (`scripts/session.sh claim seq-D2-docs-pandas-per-version`).
Memory: attach `epifanio/groundtruther-memory` (local: `scripts/memory-repo.sh sync` at start and
end); read `MEMORY.md` and 2026-10-24_plan-pandas-datetime-record.md.
Read PLANNING/WORKFLOW.md §1-§5; PLANNING/decisions/D-009_no-pandas-datetime-dtypes.md (the rule and
its per-case table) and PLANNING/TODO_mac-install-test.md §5 (the 4.2.1 measurements and the 4.2.3
box); gt/pandas_safe.py's module docstring.

Read the State table in §1 before you touch anything: merging a `website/` path PUBLISHES the site,
with no staging and no go — `.github/workflows/docs.yml` runs `mkdocs gh-deploy --force` on every
push to `master` touching `website/**`. So this PR is left OPEN for the owner (§6.3), and publishing
is theirs to time. Do not pass `--merge`.

Three findings, measured at `master` 62a7d85 by `plan-pandas-datetime-record`. Verify each still
holds before you edit it; do not take these line numbers on trust.

1. `website/docs/data-model/image-metadata.md:19` — "because on QGIS 4.2.1 on macOS building a
   pandas `datetime64` crashes the whole application". That sentence is TRUE of 4.2.1 and must not
   be deleted, but it reads as if 4.2.1 were the reason the plugin behaves this way. It is not: the
   reason is D-009, which is unconditional on every platform and every build, because the fault
   cannot be probed for at runtime (the probe is the crash) and nothing tells the plugin which
   bundle it is in. Say both: the fault was measured on 4.2.1, QGIS 4.2.3 (pandas 3.0.5, numpy
   2.5.2, pyarrow 25.0.1) is clean, and the object-dtype index is what the plugin hands you on every
   build regardless. Keep it short — it is a note for someone scripting against the table, not a
   changelog.
2. `website/docs/installation/macos.md:67` — "so on QGIS 4.2.1 only 10 of the 20 are actually
   missing". Version-shaped and never measured on 4.2.3; the page already hedges with "The figures
   on this site are examples, not promises". This is `mac-ondevice-test`'s own open end, folded in
   here: it also covers `gt/deps_check.py:73`, whose comment generalises the same way. Either say
   the figure per-build or drop the number and keep the hedge — your call, with the reason in the
   PR. Note that touching `gt/deps_check.py` puts this PR outside the docs lane; it is one comment,
   it changes no behaviour, and the PR is left open either way.
3. `website/docs/data-model/mbes-soundings.md:6` — "read with `pandas.read_parquet`, or
   `cudf.read_parquet` …" is now FALSE. An earlier open end deliberately left this line alone
   because PR #73 did not touch `pygui/querybuilder_gui.py`; PR #81 (`de84a58`) did, and that file
   now reads through `gt/pandas_safe.py` (`temporal="epoch_us"` for this table — int64 microseconds,
   8 bytes a row). D-009's `enforce` line would reject a reintroduction. Correct the line. While you
   are there, `:108` says the file's `datetime` column is `datetime64[us]`: that is true of the FILE
   and should stay. What changed is only what the plugin hands back.

Nothing else on the site names 4.2.1 or the crash — at 62a7d85, `git ls-files website docs | xargs
grep -lniE '4\.2\.1|segfault|sigsegv'` returns exactly `image-metadata.md` and `macos.md`. Run it
again rather than assuming, and widen the row if it has changed.

Touch only `website/` and, for finding 2, the one comment in `gt/deps_check.py`. Change no
behaviour. Decisions that bind this work: D-006 (user docs are the MkDocs site), D-009 (the pandas
rule this describes), D-007 (the commit trailer).
Needs the owner's answers: nothing, unless you would drop a page section rather than qualify it.
Before closing: `mkdocs build --strict -f website/mkdocs.yml` clean (a throwaway venv from
`website/requirements-docs.txt` on python3.12 — 3.15 cannot build watchdog), and read the RENDERED
page, not the diff; `python3 PLANNING/check_planning.py` clean.
Close by PLANNING/TODO_session_sequence.md §6.1: your row ✅ (or ◐, with its open ends) with the
date, PRs and memory note; ⏭ on the next row that can run; your prompt removed from §2; any later
prompt your work made stale. `scripts/session.sh close seq-D2-docs-pandas-per-version --mark … --prs
… --verified … --note …` does the mechanical part and leaves the PR open. Then push the dated memory
note `seq-D2-docs-pandas-per-version` and put its commit in your final report.
```


### 2.10 `seq-C3-roughness-keyless-gateway`

```text
Work on D-011 question 3 (the plugin calls the keyless seafloor-gateway), as session
`seq-C3-roughness-keyless-gateway` (slot 2 of PLANNING/TODO_session_sequence.md). First command:
`git fetch origin && git worktree add ../groundtruther-seq-C3-keyless -b claude/seq-C3-roughness-keyless-gateway origin/master`
(if that branch already exists, add the worktree on it and carry on from what it holds; an app-made
session worktree counts: name its branch `claude/seq-C3-roughness-keyless-gateway`), then work only
there. `scripts/session.sh start seq-C3-roughness-keyless-gateway` does this and prints this prompt.
Claim first: a PR that only sets your row in §1 to ▶ ("started" and the date, your handle in Who) and
moves ⏭ on, merged before any other work (`scripts/session.sh claim seq-C3-roughness-keyless-gateway`).
Memory: attach `epifanio/groundtruther-memory` (local: `scripts/memory-repo.sh sync` at start and
end); read `MEMORY.md` and 2026-10-24_d011-seafloor-boundary.md.
Read PLANNING/WORKFLOW.md §1-§5; PLANNING/decisions/D-011_seafloor-processing-on-the-api.md (the
boundary and its four answers), D-002 (all GRASS/FastGIS HTTP through `gt/grass_api.py`), D-003,
D-007, D-008. Then read `gt/roughness_client.py` whole, `config_model.py`'s `RoughnessSettings`, and
`mixins/roughness_mixin.py` around lines 820-870.

The job: a keyless remote gateway is a configuration this plugin SUPPORTS, not an escape hatch.
Today `gt/roughness_client.py:221-227` refuses the `endpoint`+`route` path without a key
("No API key configured") and `mixins/roughness_mixin.py:836` gates the dialog the same way. The
only keyless path is `Roughness.direct_url`, whose docstring (`config_model.py:109`) calls it the
on-host GPU URL for "running *on* the GPU host" — it takes a full URL, skips `base_url`+`route`
composition, and the mosaic URL is derived from it by sibling path at `roughness_mixin.py:842`.
Pointing that at `https://seafloor.fastgis.eu/seafloor/roughness` works today. That is the misuse to
replace, and the earlier open end was wrong to call the gateway unreachable — do not repeat that.

Three things must still be true when you are done, and your report must say how you know:
1. The keyed FastGIS route keeps working unchanged. The owner's key is live and in use against
   `api.fastgis.eu`; this is not a migration, it is a second supported shape.
2. `direct_url` keeps working, including the derived mosaic URL.
3. A keyless `base_url` + `route` sends NO `X-API-Key` header at all, rather than an empty one.
Decide and say in the PR whether keylessness is inferred (no key configured -> send no header) or
declared (an explicit field). Inferred is simpler and needs no config migration; declared catches a
key the user meant to set and forgot. Recommend one, implement one, and give the reason.

Verification, in a session that cannot reach the service: the GPU box behind both gateways is OFFLINE
(§3), so no end-to-end roughness call will succeed and you must not report one. What you CAN do, and
should: POST a junk `frame_key` keyless to `https://seafloor.fastgis.eu/seafloor/roughness` and show
that it answers 502 `roughness service unreachable` and NOT 401/403 — that is the proof the gateway
accepted an unauthenticated request. Unit-test the header shaping against a stub (the suite already
stubs `requests.post` in `tests/unit/test_roughness_client.py`), both transports and both auth
shapes. Run the whole unit suite, not just your file.

Scope: `gt/roughness_client.py`, `mixins/roughness_mixin.py`, `config_model.py`,
`tests/unit/test_roughness_client.py`, and the settings page that documents the keys (D-006 wants a
feature's config keys documented). Do NOT touch `gt/grass_api.py` or anything under `/grass/*`: those
keys stay required (D-002). Do not move any of the four modules D-011 names — that is
`seq-C4-seafloor-code-moves`, and it waits.
Needs the owner's answers: nothing. Your PR changes code, so leave it OPEN for them (§6.3) whatever
else happens, and touching `website/` means merging it publishes the site.
Before closing: `python3 PLANNING/check_planning.py` clean, and the unit suite green.
Close by PLANNING/TODO_session_sequence.md §6.1: your row ✅ (or ◐, with its open ends) with the
date, PRs and memory note; ⏭ on the next row that can run; your prompt removed from §2; any later
prompt your work made stale. `scripts/session.sh close seq-C3-roughness-keyless-gateway --mark …
--prs … --verified … --note …` does the mechanical part and leaves the PR open. Then push the dated
memory note `seq-C3-roughness-keyless-gateway` and put its commit in your final report.
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
- **Start the GPU box behind the roughness service.** Everything seafloor is blocked on it, and no
  session can do it. Measured 2026-10-25: `https://seafloor.fastgis.eu/seafloor/health` answers
  HTTP 502 `{"detail":"roughness service unreachable"}` — the gateway is healthy and the GPU service
  behind it is not. (`https://roughness.epinux.com/health` answering 403 Cloudflare Access is the
  *expected* tokenless response and says nothing either way; read the gateway's 502, not that 403.)
  It has been down since at least 2026-08-22. Until it is up, `seq-C3-roughness-keyless-gateway` can
  prove its header shaping but no roughness result can be verified end to end, and
  `seq-C4-seafloor-code-moves` cannot start. From `d011-seafloor-boundary`, 2026-10-24.
- **Decide whether FastGIS keeps serving `/seafloor/*`.** D-011 recommends one surface, the
  standalone gateway, and FastGIS's own decision of 2026-08-22 was that seafloor stays out of it —
  but `https://api.fastgis.eu/openapi.json` still lists all four seafloor paths (read 2026-10-24, re-read 2026-10-25),
  and that repository's split plan is 💤 deferred since 2026-10-09 *and* stale (it claims the routes
  never shipped). The change is in the FastGIS repository, so nothing here can close it; what is
  owed is the owner's call on whether the plugin's keyed route is being kept or retired. From
  `d011-seafloor-boundary`, 2026-10-24.

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
