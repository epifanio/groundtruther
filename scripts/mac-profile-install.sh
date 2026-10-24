#!/usr/bin/env bash
#
# mac-profile-install.sh — put a known state into one macOS QGIS test profile.
#
#   scripts/mac-profile-install.sh <profile> [--venv|--no-venv] [--ref <ref>] [--force]
#
# The QGIS profiles on the Mac are the one piece of this project's state that git does NOT isolate.
# A worktree per session isolates the repository; it gives nothing at all for
# `~/Library/Application Support/QGIS/QGIS4/profiles/`, which every session shares. On 2026-10-24 a
# `.venv` that had been measured working at 07:31 was gone by 09:21, no session's command log
# contained a deletion, and recovering it cost a morning — because the procedure existed only as
# prose in `PLANNING/TODO_mac-install-test.md`. This script is that prose, made runnable and
# idempotent, so the answer to "the profile is wrong" is one command instead of an investigation.
# `PLANNING/WORKFLOW.md` §3.1 says who may run it.
#
# What it does, in order:
#   1. refuses to touch a profile while QGIS is running on it (--force overrides; see below)
#   2. overlays the plugin files from a git ref with `git archive | tar -x` — an OVERLAY, never a
#      delete, so `config/config.yaml` (gitignored, machine-specific, holds the FastGIS API key)
#      and anything else untracked survives untouched
#   3. verifies every tracked file is byte-identical to that ref
#   4. for a --venv profile, installs exactly the dependencies the plugin reports missing
#
# Step 4 asks the plugin itself what is missing — `gt/deps_check.py`'s `check_dependencies()`, the
# same call the startup dialog uses — rather than carrying its own package list. So the script does
# not drift as `dependencies/requirements.txt` changes, and a second run installs nothing.
#
# Why the signed interpreter: macOS library validation lets the QGIS *app* load pip wheels but not
# the bundled `python3.12` helper, which segfaults on `import venv`. The fix is an ad-hoc copy of
# that interpreter carrying `com.apple.security.cs.disable-library-validation`, built here in a
# temp dir and thrown away after. `PLANNING/TODO_mac-install-test.md` §3 is the long version.
#
# The venv is built from QGIS's OWN python3.12, not homebrew's: the first one was homebrew-based,
# which put an interpreter nothing tracked between the plugin and its dependencies.
set -euo pipefail

PLUGINNAME=groundtruther
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PROFILES="$HOME/Library/Application Support/QGIS/QGIS4/profiles"
QGIS_APP="${QGIS_APP:-/Applications/QGIS-final-4_2_3.app}"   # 4.2.3 since 2026-10-24; override per run with QGIS_APP=

die() { echo "!! $*" >&2; exit 1; }
say() { echo ">> $*"; }

profile=""; want_venv=""; ref="origin/master"; force=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --venv)    want_venv=1; shift ;;
    --no-venv) want_venv=0; shift ;;
    --ref)     ref="${2:-}"; [[ -n "$ref" ]] || die "--ref needs a value"; shift 2 ;;
    --force)   force=1; shift ;;
    -*)        die "unknown option: $1" ;;
    *)         [[ -z "$profile" ]] || die "give one profile, not two ($profile, $1)"; profile="$1"; shift ;;
  esac
done
[[ -n "$profile" ]] || die "usage: scripts/mac-profile-install.sh <profile> [--venv|--no-venv] [--ref <ref>] [--force]"

# gt-mac-novenv exists to be EXACTLY what the QGIS Plugin Manager gives a user: no venv, so the
# missing-dependency dialog is exercised for real. Putting a venv in it destroys the only thing it
# tests, so that is refused outright rather than defaulted.
case "$profile" in
  gt-mac-novenv)
    # An explicit `if`, not `[[ ... ]] && die`: under `set -e` a false test as the left side of
    # `&&` is a trap waiting for whoever edits this next.
    if [[ "${want_venv:-0}" == 1 ]]; then
      die "gt-mac-novenv must stay venv-less — it is the Plugin Manager case (WORKFLOW.md §3.1)"
    fi
    want_venv=0 ;;
  gt-mac-test)   want_venv="${want_venv:-1}" ;;
  *)             [[ -n "$want_venv" ]] || die "for '$profile', say --venv or --no-venv explicitly" ;;
esac

dest="$PROFILES/$profile/python/plugins/$PLUGINNAME"
[[ -d "$PROFILES/$profile" ]] || die "no such profile: $PROFILES/$profile"
git -C "$REPO" rev-parse --verify --quiet "$ref" >/dev/null || die "no such ref: $ref"
sha="$(git -C "$REPO" rev-parse --short "$ref")"

# A profile rewritten under a running QGIS gives you a process holding the OLD modules and a tree
# holding the new ones — which is how a fixed bug looks unfixed. Quit QGIS first.
if pgrep -f "profile $profile" >/dev/null 2>&1 || pgrep -f "profile=$profile" >/dev/null 2>&1; then
  [[ "$force" == 1 ]] || die "QGIS is running on '$profile' — quit it first (or --force, and then restart QGIS before believing anything you see)"
  say "WARNING: QGIS is running on '$profile' and --force was given; restart it before trusting what you see"
fi

say "profile $profile  <-  $ref ($sha)"
mkdir -p "$dest"
git -C "$REPO" archive --format=tar "$ref" | tar -x -C "$dest"
say "plugin files overlaid (untracked files, config/config.yaml included, left alone)"

tmp="$(mktemp -d "${TMPDIR:-/tmp}/gt-profile.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT
git -C "$REPO" archive --format=tar "$ref" | tar -x -C "$tmp"
differ=0
while IFS= read -r f; do
  cmp -s "$tmp/$f" "$dest/$f" || { echo "   DIFFERS: $f"; differ=$((differ+1)); }
done < <(cd "$tmp" && find . -type f | sed 's|^\./||')
[[ "$differ" == 0 ]] || die "$differ tracked file(s) do not match $ref after the overlay"
say "every tracked file is byte-identical to $sha"

if [[ "$want_venv" != 1 ]]; then
  if [[ -d "$dest/.venv" ]]; then
    say "NOTE: '$profile' is a --no-venv profile but a .venv is present; leaving it (remove it by hand if that is wrong)"
  fi
  say "done — no venv for '$profile' by design"
  exit 0
fi

# --- the signed interpreter (see the header) -------------------------------------------------
[[ -d "$QGIS_APP" ]] || die "no QGIS app at $QGIS_APP (set QGIS_APP=/path/to/QGIS.app)"
H="$tmp/harness"; mkdir -p "$H/MacOS"
ln -s "$QGIS_APP/Contents/Frameworks" "$H/Frameworks"
ln -s "$QGIS_APP/Contents/Resources"  "$H/Resources"
cp "$QGIS_APP/Contents/MacOS/python3.12" "$H/MacOS/py312"
cat > "$tmp/ent.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>com.apple.security.cs.disable-library-validation</key><true/>
</dict></plist>
PLIST
codesign --force --sign - --options runtime --entitlements "$tmp/ent.plist" "$H/MacOS/py312" >/dev/null 2>&1 \
  || die "could not ad-hoc sign the interpreter copy"
PY="$H/MacOS/py312"
export PYTHONHOME="$QGIS_APP/Contents/Frameworks"
export PYTHONPATH="$QGIS_APP/Contents/Resources/python3.12/site-packages"
export QT_QPA_PLATFORM=offscreen

ver="$("$PY" -c 'import sys;print(f"python{sys.version_info.major}.{sys.version_info.minor}")')"
site="$dest/.venv/lib/$ver/site-packages"
mkdir -p "$site"

# Ask the plugin what it is missing, with the venv already on the path, so a second run is a no-op.
cat > "$tmp/missing.py" <<'PY'
import sys, pathlib
plug = pathlib.Path(sys.argv[1]).parent
sys.path.insert(0, str(plug))
sys.path.append(sys.argv[2])
import types
pkg = types.ModuleType("groundtruther"); pkg.__path__ = [str(pathlib.Path(sys.argv[1]))]
sys.modules["groundtruther"] = pkg
from groundtruther.gt.deps_check import check_dependencies
print("\n".join(r.package for r in check_dependencies().missing))
PY
# macOS ships bash 3.2, which has no `mapfile`; a file plus `read` is the portable form.
"$PY" "$tmp/missing.py" "$dest" "$site" > "$tmp/missing.txt"
missing=()
while IFS= read -r line; do [[ -n "$line" ]] && missing+=("$line"); done < "$tmp/missing.txt"
if [[ "${#missing[@]}" -eq 0 ]]; then
  say "venv already complete — nothing to install"
else
  say "installing ${#missing[@]} missing package(s): ${missing[*]}"
  # --target, not a real venv: QGIS's python cannot run ensurepip, and __init__.py's
  # _bootstrap_venv() only ever APPENDS this directory to sys.path — it never uses .venv/bin.
  # Appending is also why a duplicate numpy/pandas in here is harmless: the QGIS-bundled pair
  # keeps priority, which is exactly what the macOS pandas ABI segfault needs.
  # --upgrade as well: without it, `--target` refuses to replace a left-over *.dist-info and
  # prints a WARNING instead of reinstalling, so a half-deleted package would never heal.
  "$PY" -m pip install --quiet --upgrade --target "$site" "${missing[@]}" \
    || die "pip install failed — see the output above"
fi

"$PY" "$tmp/missing.py" "$dest" "$site" > "$tmp/still.txt"
still=()
while IFS= read -r line; do [[ -n "$line" ]] && still+=("$line"); done < "$tmp/still.txt"
[[ "${#still[@]}" -eq 0 ]] || die "still missing after install: ${still[*]}"
say "all dependencies present in $profile ($(du -sh "$dest/.venv" | cut -f1))"
say "restart QGIS on '$profile' before checking anything in the window"
