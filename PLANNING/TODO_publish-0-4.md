# Publish 0.4 to plugins.qgis.org

**The owner's brief** (2026-10-23): *"Plan publishing 0.4 to plugins.qgis.org — users are still on
the 2023 QGIS-3 build."* A release, planned; nothing is uploaded by a session.

## Status

**2026-10-24, `seq-C1-deps-check`: WP-3 is built** — PR
[#61](https://github.com/epifanio/groundtruther/pull/61), CI green, **open for the owner's review**
(§6.3). `gt/deps_check.py` probes the 20 runtime dependencies with `importlib.util.find_spec` (never
an import: `numba` and `cv2` cost seconds and can abort QGIS), carrying each package's pip name and
import name explicitly, and returns a report naming what is missing and what it costs. 24 unit tests,
no QGIS. **Its finding narrows WP-4:** a static module-level import-graph walk from
`groundtruther.py` shows **16 of the 20 dependencies are reached by an unguarded module-level
import**, mostly through `pygui/querybuilder_gui.py`, which the dock imports eagerly — so with any
of them missing the dock cannot be constructed and the only honest behaviour is to log, say so once
and not load. Only `av`, `cv2` and `PyOpenGL` are guarded. "Disable what cannot work" is therefore a
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

One session is queued (WP-4, now ⏭) and WP-5 follows it. The upload itself is the owner's, by hand, every time.

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
| `publish-0-4 WP-3` | `gt/deps_check.py` + unit tests: which required modules are importable | — | C | M | **built** `seq-C1-deps-check` 2026-10-24, PR #61 open for the owner |
| `publish-0-4 WP-4` | `__init__.py` + one dialog and a log line when deps are missing; disable what cannot work | WP-3 | U | M | queued `seq-U1-deps-message` |
| `publish-0-4 WP-5` | the install page on the docs site: what the Plugin Manager gives you and what it does not | WP-4 | D | S | queued `seq-D1-install-docs` |
| `publish-0-4 WP-6` | **the owner's**: tag `v0.4`, build the zip, verify its contents, upload | WP-1…WP-5 | — | — | queue §3 |

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
- WP-5: `mkdocs build --strict -f website/mkdocs.yml` (§5.2 rule 4).

## Kickoff

Queued: `TODO_session_sequence.md` §2.1 … §2.5.
