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
STRIP=(website tests PLANNING docs .claude .github)

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
)

# Must exist in the artifact. qtui/icons/ is the 81-icon set the old make_zip.sh silently dropped.
REQUIRED=(
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

zip_tmp="$tmp/$PLUGINNAME.zip"
( cd "$tmp" && zip -9qr "$zip_tmp" "$PLUGINNAME" )

echo ">> verifying"
listing="$(unzip -Z1 "$zip_tmp")"
for p in "${FORBIDDEN[@]}"; do
  if printf '%s\n' "$listing" | grep -qE "^${p}(/|$)"; then die "the artifact contains $p — do not upload it"; fi
done
for p in "${REQUIRED[@]}"; do
  if ! printf '%s\n' "$listing" | grep -qE "^${p}(/|$)"; then die "the artifact is missing $p"; fi
done

# A set-but-nonempty secret field anywhere in the tree. `grass_api_key: ""` in
# config/config.example.yaml is the template and is expected; a filled-in one is the bug this
# package exists to prevent.
if leak="$(grep -rIlE '(grass_)?api_?key[[:space:]]*[:=][[:space:]]*["'"'"']?[A-Za-z0-9_.-]{8,}' "$tmp/$PLUGINNAME" 2>/dev/null)"; then
  [[ -z "$leak" ]] || die "a non-empty API key appears in the artifact: $(printf '%s' "$leak" | tr '\n' ' ')"
fi

mkdir -p "$outdir"
mv "$zip_tmp" "$outdir/$PLUGINNAME-$tag.zip"
echo ">> $outdir/$PLUGINNAME-$tag.zip ($(du -h "$outdir/$PLUGINNAME-$tag.zip" | cut -f1)), built from $tag"
echo ">> the upload is the owner's: plugins.qgis.org, or python plugin_upload.py <zip>"
