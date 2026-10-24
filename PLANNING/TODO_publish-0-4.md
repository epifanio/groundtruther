# Publish 0.4 to plugins.qgis.org

**The owner's brief** (2026-10-23): *"Plan publishing 0.4 to plugins.qgis.org — users are still on
the 2023 QGIS-3 build."* A release, planned; nothing is uploaded by a session.

## Status

**2026-10-24, `seq-D1-install-docs`: WP-5 is in `master` and published** — PR
[#85](https://github.com/epifanio/groundtruther/pull/85), merged on the owner's go
(*"Go — merge #85 and publish"*) at `31e13cb`, which `.github/workflows/docs.yml` deployed to
<https://epifanio.github.io/groundtruther/installation/plugin-manager/> (live, HTTP 200, from
`gh-pages` *"Deployed 31e13cb"*). **WP-5 is done**, and with it every package a session owns:
WP-6, the tag and the upload, is the owner's.

The page leads with the limitation rather than burying it (the seabed-ribbon page's shape): the
Plugin Manager installs the code and **none** of the 20 dependencies, so without them the plugin
loads, shows one dialog and cannot open its panel. It quotes WP-4's behaviour from the code at
`ab010ed` — dialog title and body, the `REQUIRED  <pkg> (import <mod>) — <feature>` details format,
the once-per-session menu entry, the `no .venv beside the plugin …` log line — and takes every
feature string from `gt/deps_check.REQUIREMENTS`, so the page and the plugin say the same words.
`installation/index.md` carries the same warning up front, because `INSTALL_DOCS_URL` is
`…/installation/`: the dialog's link lands on the index, not on the new page.

**One drift found, not fixed** (lane C's): `gt/deps_check.py`'s module docstring says *16 of the
20* are reached by an unguarded module-level import, while the `REQUIREMENTS` table it describes
carries **15** (`pydantic` is `blocks_load=False`). The page follows the table, which is what the
code computes. Open end below.

**2026-10-24, `seq-U1-deps-message`: WP-6's artifact was dry-run end to end, and it passes.** Not
the release — no `v0.4` tag was created and nothing was uploaded; both stay the owner's (§6 Q5).
Built with `scripts/make-release-zip.sh` from a throwaway tag at `master` `9d01eb1` (deleted after),
on macOS, and checked:

| Check | Result |
|---|---|
| structure | 2.8 MB, 239 files, exactly one top-level `groundtruther/` |
| forbidden paths | none — no `config/config.yaml`, `.venv`, `PLANNING/`, `website/`, `tests/`, `docs/`, `.claude/`, `.github/`, `grassdata/`, `ribbon_work/` |
| icons | 82 under `qtui/icons/`; the declared `qtui/icons/epi.gif` present |
| `metadata.txt` | parses, one `[general]`, no key containing a space, `version=0.4`, `experimental=True`, `qgisMinimumVersion=4.0`, changelog names 0.4 |
| secret | no real `config/config.yaml` exists on that machine; the shipped example carries `grass_api_key: ""`; no key-shaped assignment anywhere in the tree |
| D-004 | **no `PyQt6` import in any shipped `.py`** — the `sip` fix (#91) ships as `from qgis.PyQt import sip` |
| it loads | unpacked into a clean profile with **no `.venv`**: `startPlugin` True, 13 messages tagged `GroundTruther`, WP-4's dialog path working from the artifact itself |

**2026-10-24: 0.4.1 IS UPLOADED, and awaiting approval. WP-6 is done; the repository's part is not.**

0.4 was uploaded (plugin 2982, version 36365) and **blocked by the repository's automated scan**:
*"critical security issues were found during validation"*. A blocked version cannot be unblocked,
only superseded, so the release became **0.4.1** (#112, `master` `555131c`, tag `v0.4.1`).

| | |
|---|---|
| uploaded | plugin 2982, **version 36366**, 2026-10-24 |
| blocked? | **no** — the banner that marks 0.4 is absent from the 0.4.1 page |
| download | HTTP 200, and the served file's sha256 is **identical** to `dist/groundtruther-v0.4.1.zip` (`679bfacd…`) |
| listed for QGIS 4 clients | **not yet** — absent from `plugins.xml?qgis=4.0` (1600 plugins, 189 experimental, none of them this one) |
| why | `<trusted>False</trusted>` on the author in the feed, so a version needs the repository's approval before it is listed. The plugin page still advertises 0.3 as the latest experimental version |

So the bytes are in place and correct; what remains is approval, which is the repository's to give.

**What the two rejections cost, and what now prevents them**

1. *No LICENSE.* Nothing in the repo had one — `git ls-files` matched nothing, GitHub said "none
   detected" — and no local check looked for it. Fixed in #111 (GPLv3, plus a notice on all 124
   source files); `$PLUGINNAME/LICENSE` is now in the release script's `REQUIRED`.
2. *Three HIGH Bandit findings.* `os.system` on a joined ogr2ogr command line, an MD5 cache key,
   and `xmlrpc.client` in `plugin_upload.py` — which had no business shipping at all. Fixed in
   #112, and `checks.yml` now runs the same scan and **fails on HIGH severity**, measured both
   ways: exit 0 after the fix, exit 1 on the commit that was blocked.

The lesson in one line: every check this project had asked "is the artifact what we meant to
build?"; neither rejection was about that. The gates that matter are the ones the *receiving* system
applies, and both are now run locally before an upload rather than discovered by it.

**2026-10-24: the tag exists and the artifact is built. Only the upload is left.**

The owner asked for the three open PRs to go in and the release retagged (*"fix it sand retag"*).
`#103`, `#106` and `#104` were merged — the last of which **published the docs site** — and `v0.4`
was moved to `master` **`6ce2c92`** and **pushed to origin** on their word. The artifact was rebuilt
from that tag:

| | |
|---|---|
| `dist/groundtruther-v0.4.zip` | 2.8 MB, 241 entries, one top-level `groundtruther/` |
| sha256 | `b6d284d9880652794f0c8c39a9d2d18e0e54bcb1ff2770b97173e16c80a0fb7b` |
| forbidden paths | none; no key-shaped literal; `qtui/icons/epi.gif` present |
| `metadata.txt` | `version=0.4`, `experimental=True`, `qgisMinimumVersion=4.0`, no key with a space |
| vs the tag | diff against a `git archive` of `v0.4`: **only** the six stripped directories differ |
| it loads | the shipped zip in a clean no-venv profile on **QGIS 4.2.3**: `loadPlugin True`, `startPlugin True`, `_MissingDependenciesPlugin`, 10 of 20 missing / 6 blocking, and the dialog's link resolves to `installation/macos/` |

**Still unanswered, and cheaper to settle before the upload than after:** `scripts/` is not on the
strip list, so `scripts/mac-profile-install.sh` now ships *inside* the plugin — a macOS
profile-management script in a QGIS plugin install. That is #50's open question about ~1 MB of repo
furniture, still awaiting the owner. Changing the strip list is a rebuild from the same tag.

So the only parts of WP-6 left are the ones no session may do: create the real tag, build from it, and
upload with the owner's plugins.qgis.org credentials. Rebuild from the real tag anyway rather than
shipping a dry-run zip, and `unzip -l` it once before uploading.

**2026-10-24, `seq-U1-deps-message`: WP-4 is in `master`** — PR
[#67](https://github.com/epifanio/groundtruther/pull/67), merged by the owner at `ab010ed` on their
word (*"Go ahead and merge #67"*), after being opened and left for their review (§6.3,
`WORKFLOW.md` §12 Q3), and **confirmed in the GUI by the owner the same day**: on `gt-mac-novenv` the dialog renders as intended, with the live install link, the headline counting only the 6 that block, and the other 4 listed apart. **WP-4 is done.** `classFactory` now probes `gt/deps_check.py` before it
imports anything, and when something the dock needs is missing it logs every missing package with
what that package costs and hands QGIS a `_MissingDependenciesPlugin` **instead of raising**: that
object loads cleanly, adds one menu entry that re-opens the explanation, shows **one** dialog naming
the packages and linking the install docs, and has no toolbar and no dock, because neither could be
constructed. Measured on QGIS 4.2.1 (macOS) with no `.venv`: `startPlugin` now returns `True` where
it returned `False`, and the `GroundTruther` log tab holds **13** lines where it held **none**.

Two things the plan had not foreseen, both from `mac-install-test`'s measurements. **The missing set
is platform-specific and so is always computed** — on that Mac 10 of the 20 are missing, `pandas` is
not among them and `pyqtgraph` is, so no wording may name a package. And **the headline must count
only what blocks**: 10 are missing there but just 6 carry `blocks_load`, so the dialog says 6 and
names the other 4 as feature losses, which is the number the user actually has to fix.

The second mismatch in §2 is fixed in the same PR (#67): **`.venv` won**, being the name `CLAUDE.md`, the
test suite and the install docs already use, and `setup_wsl.sh --venv` now creates it *beside the
plugin source* rather than `gtenv` in whatever directory it was run from — two bugs in that one
line, not one. `_bootstrap_venv()` also returns the directory it added, so the log can say which of
the two cases it is in. **What is NOT done, deliberately:** the 16 unguarded module-level imports
are untouched, so "disable what cannot work" remains the small lever WP-3 showed it to be; making
the heavy dependencies genuinely optional is still the separate plan §6 Q1 names. The log *panel*
and the dialog's appearance are the owner's GUI check (queue §3): a headless `QgsApplication` never
delivers `messageReceived`, so the lines were captured at the call site.

**2026-10-24, `seq-C1-deps-check`: WP-3 is in `master`** — PR
[#61](https://github.com/epifanio/groundtruther/pull/61), merged by the owner at `6e22c32` on their
word (*"Go ahead and merge #61"*), after being opened and left for their review (§6.3). `gt/deps_check.py` probes the 20 runtime dependencies with `importlib.util.find_spec` (never
an import: `numba` and `cv2` cost seconds and can abort QGIS), carrying each package's pip name and
import name explicitly, and returns a report naming what is missing and what it costs. 24 unit tests,
no QGIS. **Its finding narrows WP-4:** a static module-level import-graph walk from
`groundtruther.py` shows **15 of the 20 dependencies are reached by an unguarded module-level
import**, mostly through `pygui/querybuilder_gui.py`, which the dock imports eagerly — so with any
of them missing the dock cannot be constructed and the only honest behaviour is to log, say so once
and not load. Of the other five, `av`, `cv2` and `PyOpenGL` are guarded and `pydantic` and
`starlette` are off the chain. (Said 16 until 2026-10-24: a miscount in the prose; `REQUIREMENTS`
always carried 15.) "Disable what cannot work" is therefore a
much smaller lever than the plan assumed; making the heavy deps genuinely optional stays the
separate plan Q1 names. Also: `starlette` is in `dependencies/requirements.txt` and no module
imports it at 0.4.

**2026-10-24, `seq-P2-release-zip`: WP-1 built and, by mistake, merged — PR [#50](https://github.com/epifanio/groundtruther/pull/50)
went into `master` at `63b9082` without the owner's review (see the open end in the queue's §2.1).** There is now one build path, `scripts/make-release-zip.sh <tag>`, and the two
paths that put `config/config.yaml` — the GRASS/FastGIS API key — inside the artifact are deleted.
Verified on a throwaway tag: 2.7 MB, 237 files, the five forbidden paths absent, `qtui/icons/`
present, and no API-key value anywhere in the unpacked tree (the guard was proved by planting a fake
key, which it refused to ship). **#50 is in `master`; it is the owner's review that is still owed, not the merge.** Three sessions are
**2026-10-24, `seq-P1-release-metadata`: WP-2 is in `master`** — PR
[#56](https://github.com/epifanio/groundtruther/pull/56), merged by the owner at `4f4d6b5` on their
word (*"Go ahead and merge #56"*), after being opened and left for their review (§6.3). `metadata.txt` now parses with no junk key, declares an
icon that exists (`qtui/icons/epi.gif`; the old `qtui/icons/qgis/epi.gif` never did, which would have
failed the upload), carries 13 discovery tags, points `homepage` at the docs site and has a real 0.4
changelog. `version=0.4` and `experimental=True` are untouched (§6 Q2, Q4).

WP-5 is done (`seq-D1-install-docs`, #85, published from `31e13cb`); WP-4's own open end was that review, given on 2026-10-24. Every package a session owns is now in `master`. The upload itself is the owner's, by hand, every time.

Conventions: `PLANNING/WORKFLOW.md` §5.2 (rules 0–6).

## What exists today

Read in the code at `master` 83ae64c, 2026-10-23, and from the live plugin feed. Not from any note.

### What users actually have

| | `metadata.txt` on `master` | plugins.qgis.org, read 2026-10-23 |
|---|---|---|
| Version | 0.4 | **0.3** |
| QGIS | `qgisMinimumVersion=4.0` | 3.0.0 – 3.99.0 |
| Flag | `experimental=True` | experimental |
| Uploaded | — | **2023-06-01** |

`plugin_id` 2982, author `epinux`, 949 downloads. The entire QGIS 4 / Qt6 rewrite is unpublished.

### Three ways to build a zip, two of which ship the API key

*As read at `master` 83ae64c. `seq-P2-release-zip` (PR #50, 2026-10-24) deleted the first two and
replaced the third with `scripts/make-release-zip.sh`; the table is kept as the record of what was
wrong, since it is why the package existed.*

| Path | What it produces |
|---|---|
| `make_zip.sh` | excludes only `.git*`, `__pycache__`, `qtui`, `help`, `gtenv` → **ships `config/config.yaml`**, `.venv`, `grassdata/`, `tmp/`, `ribbon_work/`, `PLANNING/`, `.claude/`, and **drops all 103 icons** because `qtui/` is excluded |
| `make zip` → `deploy` | `QGISDIR` is a hardcoded **QGIS3** absolute path that `$HOME` is prepended to and `/python/plugins/` appended to twice; `cp`s `icon.png` and `groundtruther_dockwidget_base.ui`, **neither of which exists**, so it fails. Were it to run, it would zip through the profile symlink and capture the whole repo |
| `make package VERSION=<tag>` | `git archive` — **the only safe one**: gitignored files cannot enter, so the key is structurally excluded. 5.9 MB, of which `website/` is 3.1 MB |

Also stale: `PY_FILES` lists **3 files** of ~150, so `make deploy` would ship a plugin with no `gt/`,
`mixins/` or `pygui/`; `HELP = help/build/html` is the retired Sphinx stub (D-006); `metadata.txt`
says `icon=qtui/icons/qgis/epi.gif` and the file is at `qtui/icons/epi.gif`.

`make compile` builds only `resources_rc.py`. **There is no `pyuic` rule in the Makefile**, so no
release path trips D-005.

**`make package` with no `VERSION` fails into a usable mess.** The target does `rm -f
groundtruther.zip` and then `git archive … -o groundtruther.zip` with an empty tree-ish, which
exits 129 on a usage error and leaves a **0-byte `groundtruther.zip` at the repo root** — and
`.gitignore` does not cover it. So a release artifact is stageable, and a `git add -A` would commit
it (6 MB when the build succeeds). Observed on 2026-10-23 during this planning session: a stray
`make doc && make package` ran against this worktree from outside the session, left the empty zip,
and it was removed by hand. Whatever invoked it, the trap is real and is WP-1's to close.

### The dependency blocker

`__init__.py`'s `_bootstrap_venv()` appends `<plugin>/.venv/lib/pythonX.Y/site-packages` to
`sys.path` and is, in its own docstring, a **no-op if the venv is absent**. A user installing
through the QGIS Plugin Manager gets the zip unpacked into their profile with no `.venv` and no
pip, so all **20 runtime dependencies** in `dependencies/requirements.txt` (pandas, opencv,
pyarrow, scikit-image, numba, …) fail to import. **Installed the official way, the plugin cannot
work.** This is issue [#1](https://github.com/epifanio/groundtruther/issues/1) in substance.

A second, smaller mismatch: `setup_wsl.sh --venv` creates **`gtenv`**, while `_bootstrap_venv()`
looks for **`.venv`**. The documented fallback install produces a venv the plugin never loads.
**Fixed in PR #67** (`seq-U1-deps-message`, 2026-10-24, `master` `ab010ed`): `.venv` won, and the script was also
creating it in the current directory rather than beside the plugin, so it was two bugs.

### Metadata defects

`description` says "**Caracterization**" and `__init__.py` says "**Serafloor Caracterization**" (`about`, which this list originally named too, already read "characterization" — read again 2026-10-24 by `seq-P1-release-metadata`; `Makefile:4` and `groundtruther_dockwidget.py:6` still carry the typo and are out of WP-2's lane); `tags`
is `python` alone, which makes the plugin undiscoverable; `homepage` points at the repo rather than
<https://epifanio.github.io/groundtruther/>; `changelog` is a run-on line about settings and GRASS
widgets, not a 0.4 entry; and the bare line `Category of the plugin: Raster, Vector, Database or
Web` parses as a junk key, because `configparser` accepts `:` as a separator.

## Design

Ship the QGIS-4 work to users now, and be honest about the install rather than blocking the release
on the hard dependency problem. Three strands, in this order of risk:

1. **Make the artifact safe before anything can be uploaded.** One build path, starting from a tag,
   with the key structurally unable to enter. Delete the unsafe paths rather than documenting them.
2. **Make the failure honest.** When a dependency is missing the plugin must load, say exactly what
   is missing and where to read about it, and disable the features that need it — not die with a
   traceback. The detection is Qt-free logic in `gt/` (D-008); the dialog is the dock's.
3. **Say it in the docs**, and leave the upload to the owner.

Solving the dependency problem properly — a first-run installer, vendored wheels, or optional
heavy deps — is **out of scope** and is its own plan. Q1 below records why.

## Questions for the owner

Asked 2026-10-23, answered the same day in the owner's words — *"All six recommendations are fine
as written — write the plan."* Frozen: a later session asks again rather than changing one.

**Q1. How do users get the 20 Python dependencies?** → **Ship 0.4 with the current venv approach and
a graceful failure; fix dependencies as its own plan.** The alternatives were weighed and not taken:
a first-run pip installer (fragile across platforms, PEP-668 blocks system Python), vendored wheels
(opencv + numba + pyarrow are platform-specific and hundreds of MB, not viable for
plugins.qgis.org), and making the heavy deps optional with degraded features (the largest job, a
plan of its own). Shipping now reaches users who have a 2023 build; it does not pretend the install
is easy.

**Q2. Does 0.4 stay experimental?** → **Yes, `experimental=True` stays.** Given Q1, users opt in
deliberately. Stable-with-manual-dependencies would be the dishonest combination.

**Q3. Which artifact is the release?** → **A new `scripts/make-release-zip.sh`**: `git archive` from
a tag, then strip `website/`, `tests/`, `PLANNING/`, `docs/`, `.claude/`, `.github/`. **Delete
`make_zip.sh`** and fix or delete the Makefile's `deploy`/`zip` targets, so the dangerous paths stop
existing.

**Q4. Version number?** → **0.4**, unchanged. It is already in `metadata.txt` and has never been
published.

**Q5. Who uploads?** → **The owner, by hand** (the plugins.qgis.org web form, or running
`plugin_upload.py` themselves). No session holds those credentials. A build session ends at "the zip
is built, its contents verified, the tag pushed"; the upload is a production go, each time, never
reused (`WORKFLOW.md` §8).

**Q6. Metadata cleanup?** → **Yes, in one pass**: the two "Caracterization" typos and "Serafloor";
real tags; `homepage` to the docs site; the icon path's stray `qgis/`; a real 0.4 changelog; and
drop the junk `Category of the plugin:` line.

None of these bind work outside this plan, so none was promoted to a decision record.

## Work packages

| Package | Scope | Depends on | Lane | Size | State |
|---|---|---|---|---|---|
| `publish-0-4 WP-1` | `scripts/make-release-zip.sh`; delete `make_zip.sh`; fix or delete the Makefile release targets; gitignore the release artifact | — | P | M | **built** `seq-P2-release-zip` 2026-10-24, PR #50 open for the owner |
| `publish-0-4 WP-2` | `metadata.txt` and the `__init__.py` docstring typo | — | P | S | ✅ `seq-P1-release-metadata` 2026-10-24, PR #56 merged (`master` 4f4d6b5) |
| `publish-0-4 WP-3` | `gt/deps_check.py` + unit tests: which required modules are importable | — | C | M | ✅ `seq-C1-deps-check` 2026-10-24, PR #61 merged (`master` 6e22c32) |
| `publish-0-4 WP-4` | `__init__.py` + one dialog and a log line when deps are missing; disable what cannot work | WP-3 | U | M | ✅ `seq-U1-deps-message` 2026-10-24, #67 in `master` `ab010ed`, GUI confirmed |
| `publish-0-4 WP-5` | the install page on the docs site: what the Plugin Manager gives you and what it does not | WP-4 (done, `ab010ed`) | D | S | ✅ `seq-D1-install-docs` 2026-10-24, PR #85 merged (`master` 31e13cb), **published** |
| `publish-0-4 WP-6` | **the owner's**: tag `v0.4`, build the zip, verify its contents, upload | WP-1…WP-5 **+ the on-device test (passed)** | — | — | queue §3 · **the gate is cleared**: the owner, 2026-10-24, asked for a real on-device test before anything shipped. The data half passed, the GUI half failed with a segfault, PR #100 fixed it (`0155844`), and the owner re-ran it — *"The image drew and QGIS stayed up"*. Nothing now blocks the upload but the upload itself, which is theirs, by hand, with a production go |

WP-1 and WP-2 are both lane P and run in that order (the zip script is what removes the key-leak
path, so it goes first). WP-2 is small enough to fold into WP-1 if the owner would rather have one
PR; kept separate because a metadata change is reviewable at a glance and a build-script change is
not.

## Lane split

| | |
|---|---|
| **Sequential** | WP-3 → WP-4 → WP-5. WP-1 → WP-2 (same lane). |
| **Side by side** | the P strand (WP-1, WP-2) and the C/U/D strand (WP-3…WP-5) share no file; slot 2 still runs one at a time unless the owner starts a second (`WORKFLOW.md` §3.1). |
| **Collision surface** | `metadata.txt` is lane P's (WP-2); `__init__.py` is lane U's (WP-4). Nobody else touches either. `dependencies/requirements.txt` is read by WP-3 and must not be edited by it. |
| **A session decides for itself** | branch and PR split, test shape, the wording of log messages, the exact strip list beyond the six directories named in Q3. |
| **A session must ask** | anything that changes what the plugin *does* beyond failing gracefully; any new runtime dependency; the version number; and every upload. |

## Verification

The real case, end to end, is **an install from a zip into a clean QGIS 4 profile** — not a test
suite. Specifically:

- WP-1: `git status --short` is clean after a build **and after a failed build** — the artifact is
  gitignored and cannot be committed by accident.
- WP-1: build the zip from a tag, then `unzip -l` it and assert `config/config.yaml`, `.venv`,
  `PLANNING/`, `website/`, `tests/` are **absent** and `qtui/icons/` is **present**. A grep of the
  unpacked tree for the API key must find nothing. This check is the point of the package.
- WP-2: the zip's `metadata.txt` parses, and the declared `icon` path resolves inside the zip.
- WP-3: unit tests, no QGIS (D-008), including the case where every dependency is present.
- WP-4: unpack the zip into a clean QGIS 4 profile **with no `.venv`** and confirm the plugin loads,
  logs to the `GroundTruther` panel (D-003) and shows one dialog naming the missing packages —
  **the owner's GUI check**, in lane U, since no agent can drive the QGIS GUI.
- WP-5: `mkdocs build --strict -f website/mkdocs.yml` (§5.2 rule 4). **Done 2026-10-24**: clean,
  run in a throwaway venv built from `website/requirements-docs.txt` because this Mac has no
  `mkdocs` (python3.12 — on 3.15 `watchdog` has no wheel and fails to compile). The rendered
  page was read, not the diff, and the published page answered HTTP 200.

**2026-10-24, from the side session `mac-install-test`** (`PLANNING/TODO_mac-install-test.md`): the
WP-4 case has now been measured on a real QGIS 4.2.1 on macOS, from an artifact built by WP-1's
script. Three results bear directly on WP-3 and WP-4 — the first missing module is `pyqtgraph`
(macOS QGIS ships pandas but not pyqtgraph, so the missing set is platform-specific),
`qgis.utils.loadPlugin()` returns `True` in that state because it only does `__import__`, and the
`GroundTruther` log tag is empty. It also found a blocker *outside* this plan's scope: every pandas datetime
operation segfaults QGIS 4.2.1 on macOS, which kills the mandatory `HabCam.imagemetadata` read,
queued as
`seq-C2-parquet-no-pandas`. **0.4 would install and enable on macOS and then crash the application
on first use**, so WP-6's upload should wait for that row unless the owner decides otherwise.
**Updated 2026-10-24:** that row's fix is in `master` (#73), but the row is still ◐ — its open end is
the GUI confirmation that both call sites now survive (step 9 of `TODO_mac-install-test.md` §6). So
the caution stands, and what it now waits on is that check rather than the work. The root cause is
QGIS's own bundled pandas 3.0.3, which cannot hold a datetime at all, so no pin in this plan fixes
it; `plan-pandas-datetime-record` is promoting the rule to a decision record.

## Kickoff

Queued: `TODO_session_sequence.md` §2.1 … §2.5.
