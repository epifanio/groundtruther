#!/usr/bin/env bash
#
# make-release-zip.sh — build THE release artifact for plugins.qgis.org.
#
#   scripts/make-release-zip.sh <tag> [outdir]
#
# The only sanctioned way to build a zip (PLANNING/TODO_publish-0-4.md §6 Q3). It exports a TAG with
# `git archive --prefix=groundtruther/`, so nothing gitignored can enter — which is what keeps
# `config/config.yaml` and its FastGIS API key structurally out of the artifact — then strips the
# six directories that are repo furniture rather than plugin code, and refuses to produce anything
# unless the result passes the assertions below.
#
# Properties that matter, and why:
#   * a TAG, never the working tree: the artifact is reproducible from history alone.
#   * the zip is assembled in a temp dir and moved into place only once every assertion passes, so a
#     failed build leaves NOTHING behind — nothing half-written, nothing stageable.
#   * the output goes to dist/ (gitignored), never the repo root, so `git add -A` can never commit a
#     6 MB release artifact.
#
# The upload is the owner's, by hand, every time (§6 Q5). This script never uploads.
set -euo pipefail

PLUGINNAME=groundtruther
REPO="$(cd "$(dirname "$0")/.." && pwd)"

# Repo furniture: present in git, no business inside a QGIS plugin install.
STRIP=(website tests PLANNING docs .claude .github .githooks help tmp)

# Individual files to drop, for a directory that is MOSTLY furniture but not
# entirely. scripts/ holds the session machinery (session.sh, hooks/, ci-wait,
# memory-repo, this script, mac-profile-install) — none of which means anything
# to someone who installed the plugin from the Plugin Manager.
#
# scripts/build_ribbon.py is the exception and MUST ship: it is a user-facing
# tool, documented command by command at website/docs/tools/seabed-ribbon.md
# ("It is scripts/build_ribbon.py in the plugin folder"), and gt/ribbon.py
# points at it. Stripping scripts/ wholesale would delete a documented feature
# from every install, which is why this is a file list and not another entry in
# STRIP above.
STRIP_FILES=(
  # Developer tooling, meaningless inside a user's plugin folder. CLAUDE.md is
  # agent instructions; the rest build, lint, test or package the repository.
  CLAUDE.md
  Makefile
  pb_tool.cfg
  pylintrc
  pytest.ini
  compile_ui.sh
  resources.qrc
  # The upload tool itself. It is for the maintainer, never for someone who
  # installed the plugin — and `import xmlrpc.client` in it is Bandit B411 at
  # HIGH severity, one of the three findings that blocked the 0.4 upload.
  # Stripping removes the finding rather than patching code nobody ships.
  plugin_upload.py
  scripts/adopt-inventory.sh
  scripts/ci-wait.sh
  scripts/import-memory-inbox.sh
  scripts/mac-profile-install.sh
  scripts/make-release-zip.sh
  scripts/memory-repo.sh
  scripts/session.sh
  scripts/smoke_mosaic.py
)
STRIP_DIRS_IN_FILES=(scripts/hooks)

# Must NOT exist in the artifact. config/config.yaml is the API key; the rest is bulk or private.
FORBIDDEN=(
  "$PLUGINNAME/config/config.yaml"
  "$PLUGINNAME/.venv"
  "$PLUGINNAME/PLANNING"
  "$PLUGINNAME/website"
  "$PLUGINNAME/tests"
  "$PLUGINNAME/docs"
  "$PLUGINNAME/.claude"
  "$PLUGINNAME/.github"
  "$PLUGINNAME/grassdata"
  "$PLUGINNAME/ribbon_work"
  "$PLUGINNAME/scripts/session.sh"
  "$PLUGINNAME/scripts/hooks"
  "$PLUGINNAME/scripts/make-release-zip.sh"
  "$PLUGINNAME/scripts/mac-profile-install.sh"
  "$PLUGINNAME/plugin_upload.py"
  "$PLUGINNAME/CLAUDE.md"
  "$PLUGINNAME/help"
  "$PLUGINNAME/.githooks"
)

# Must exist in the artifact. qtui/icons/ is the 81-icon set the old make_zip.sh silently dropped.
REQUIRED=(
  # `epsg` is 888 KB of PROJ definitions and looks exactly like the repo
  # furniture stripped above — but episg.py, search_epsg.py and pygui/epsg.py
  # all build a path to it beside their own module and read it at runtime.
  # It is asserted here so nobody "tidies away" the single biggest file in the
  # artifact and breaks CRS lookup.
  "$PLUGINNAME/epsg"
  # dependencies/requirements.txt is read by gt/deps_check.py's
  # parse_requirements, and every install page tells users to pip install from
  # it. environment.yml is read by setup_wsl.sh, which also ships.
  "$PLUGINNAME/dependencies/requirements.txt"
  "$PLUGINNAME/environment.yml"
  # plugins.qgis.org REJECTS an upload without it: "Cannot find LICENSE in the
  # plugin package. This file is required". Learnt the hard way on the 0.4
  # upload, after every other check passed.
  "$PLUGINNAME/LICENSE"
  "$PLUGINNAME/scripts/build_ribbon.py"
  "$PLUGINNAME/metadata.txt"
  "$PLUGINNAME/__init__.py"
  "$PLUGINNAME/groundtruther.py"
  "$PLUGINNAME/qtui/icons"
  "$PLUGINNAME/gt"
  "$PLUGINNAME/mixins"
  "$PLUGINNAME/pygui"
)

die() { echo "!! $*" >&2; exit 1; }

tag="${1:-}"
[[ -n "$tag" ]] || die "usage: scripts/make-release-zip.sh <tag> [outdir]   (a tag, not the working tree)"
outdir="${2:-$REPO/dist}"

git -C "$REPO" rev-parse --verify --quiet "refs/tags/$tag" >/dev/null \
  || die "no such tag: $tag — tag the release first (git tag -a $tag), or pass an existing tag"

tmp="$(mktemp -d "${TMPDIR:-/tmp}/groundtruther-release.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT

echo ">> exporting $tag"
git -C "$REPO" archive --format=tar --prefix="$PLUGINNAME/" "$tag" | tar -x -C "$tmp"

for d in "${STRIP[@]}"; do
  if [[ -e "$tmp/$PLUGINNAME/$d" ]]; then rm -rf "$tmp/$PLUGINNAME/$d"; echo ">> stripped $d/"; fi
done

for f in "${STRIP_FILES[@]}" "${STRIP_DIRS_IN_FILES[@]}"; do
  if [[ -e "$tmp/$PLUGINNAME/$f" ]]; then rm -rf "$tmp/$PLUGINNAME/$f"; echo ">> stripped $f"; fi
done

# Byte-reproducibility. Every FILE already carries the tag's commit time, which
# `git archive` stamps into the tar. The top-level directory entry did not: `tar
# -x` creates it and then writes into it, so its mtime was the moment of
# extraction and two builds of the same tag produced two different sha256 for
# byte-identical contents. Stamp it, and the only clock the artifact depends on
# is the one in the commit.
#
# `touch -t` rather than `-d`: BSD touch (macOS) rejects the ISO-8601 string git
# prints, so the epoch is converted with whichever `date` this machine has —
# `-r` on BSD, `-d @` on GNU.
commit_epoch="$(git -C "$REPO" log -1 --format=%ct "$tag")"
stamp="$(date -r "$commit_epoch" +%Y%m%d%H%M.%S 2>/dev/null \
        || date -d "@$commit_epoch" +%Y%m%d%H%M.%S)"
[[ -n "$stamp" ]] || die "could not convert the commit date to a touch timestamp"
find "$tmp/$PLUGINNAME" -type d -exec touch -t "$stamp" {} +

zip_tmp="$tmp/$PLUGINNAME.zip"
# -X drops uid/gid and the extra-field timestamps, which carry a finer-grained
# clock than the DOS time zip records in the entry itself.
( cd "$tmp" && zip -9qrX "$zip_tmp" "$PLUGINNAME" )

echo ">> verifying"
listing="$(unzip -Z1 "$zip_tmp")"
for p in "${FORBIDDEN[@]}"; do
  if printf '%s\n' "$listing" | grep -qE "^${p}(/|$)"; then die "the artifact contains $p — do not upload it"; fi
done
for p in "${REQUIRED[@]}"; do
  if ! printf '%s\n' "$listing" | grep -qE "^${p}(/|$)"; then die "the artifact is missing $p"; fi
done

# An api_key field with a real VALUE anywhere in the tree — the bug this package exists to prevent.
# Both forms a key is actually written in: quoted (yaml, json, python) and bare (yaml). It has to be
# a literal of 12+ characters, because the tree is full of `api_key=self.api_key` and
# `grass_api_key: ""`, which are identifiers and an empty template, not secrets.
SECRET_QUOTED='(grass_)?api_?key["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"'][A-Za-z0-9_.-]{12,}["'"'"']'
SECRET_BARE='(grass_)?api_?key[[:space:]]*:[[:space:]]*[A-Za-z0-9_.-]{12,}[[:space:]]*$'
leak="$(grep -rIlE "$SECRET_QUOTED|$SECRET_BARE" "$tmp/$PLUGINNAME" 2>/dev/null || true)"
[[ -z "$leak" ]] || die "an API key value appears in the artifact: $(printf '%s' "$leak" | sed "s#^$tmp/##" | tr '\n' ' ')"

mkdir -p "$outdir"
mv "$zip_tmp" "$outdir/$PLUGINNAME-$tag.zip"
echo ">> $outdir/$PLUGINNAME-$tag.zip ($(du -h "$outdir/$PLUGINNAME-$tag.zip" | cut -f1)), built from $tag"
echo ">> the upload is the owner's: plugins.qgis.org, or python plugin_upload.py <zip>"
