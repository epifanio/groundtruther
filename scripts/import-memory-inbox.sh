#!/usr/bin/env bash
#
# import-memory-inbox.sh — install notes a session left in PLANNING/memory_inbox/ (because it could not
# reach the memory repo) into the memory clone, then optionally sync the memory repo.
#
#   scripts/import-memory-inbox.sh            # install, add index lines, `git rm` the imported files
#   scripts/import-memory-inbox.sh --commit   # ...and commit that removal
#   scripts/import-memory-inbox.sh --push     # ...and run scripts/memory-repo.sh sync
#   scripts/import-memory-inbox.sh --keep     # install but leave the inbox files
#   scripts/import-memory-inbox.sh -n         # dry run
#
# Never overwrites: a same-named file with different content is installed as
# <name>.incoming-<date>.md for a human to merge. Every copy is verified byte-identical before its
# source may leave the inbox.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
INBOX="$REPO/PLANNING/memory_inbox"
MEMORY_CLONE="${MEMORY_CLONE:-$HOME/dev/groundtruther-memory}"
MEM="${MEMORY_DIR:-$MEMORY_CLONE}"   # the memory clone: Claude Code reads it there (autoMemoryDirectory)

PUSH=0 DRY=0 KEEP=0 COMMIT=0
for a in "$@"; do
  case "$a" in
    --push) PUSH=1 ;; --commit) COMMIT=1 ;; --keep) KEEP=1 ;; -n|--dry-run) DRY=1 ;;
    -h|--help) sed -n '2,/^set -euo/p' "$0" | sed '$d'; exit 0 ;;
    *) echo "unknown arg: $a" >&2; exit 2 ;;
  esac
done

echo ">> memory dir: $MEM"
[[ $DRY == 1 ]] || mkdir -p "$MEM"
index="$MEM/MEMORY.md"
[[ -f "$index" || $DRY == 1 ]] || printf '# Memory index\n\n' > "$index"
today="$(date +%F)"; installed=(); failed=()
shopt -s nullglob
for f in "$INBOX"/*.md; do
  base="$(basename "$f")"; [[ "$base" == README.md ]] && continue
  desc="$(sed -n 's/^description: //p' "$f" | head -1)"; target="$base"
  if [[ -f "$MEM/$base" ]] && cmp -s "$f" "$MEM/$base"; then echo "   same      $base"
  elif [[ -f "$MEM/$base" ]]; then
    target="${base%.md}.incoming-$today.md"; echo "   CONFLICT  $base: installed as $target — merge by hand"
    [[ $DRY == 1 ]] || cp "$f" "$MEM/$target"
  else echo "   new       $base"; [[ $DRY == 1 ]] || cp "$f" "$MEM/$base"; fi
  if ! { [[ -f "$index" ]] && grep -qF "($target)" "$index"; }; then
    echo "   index +   - [$target]($target) — $desc"
    [[ $DRY == 1 ]] || printf -- '- [%s](%s) — %s\n' "$target" "$target" "$desc" >> "$index"
  fi
  if [[ $DRY == 1 ]] || cmp -s "$f" "$MEM/$target"; then installed+=("$f")
  else echo "   !! NOT INSTALLED  $base — left in the inbox" >&2; failed+=("$base"); fi
done

if [[ $DRY == 0 && $KEEP == 0 && ${#installed[@]} -gt 0 ]]; then
  tracked=()
  for f in "${installed[@]}"; do
    if git -C "$REPO" ls-files --error-unmatch -- "$f" >/dev/null 2>&1; then tracked+=("$f"); else rm -f -- "$f"; fi
  done
  if [[ ${#tracked[@]} -gt 0 ]]; then
    git -C "$REPO" rm -q -- "${tracked[@]}"; echo ">> removed ${#tracked[@]} imported file(s) from the inbox (staged)"
    if [[ $COMMIT == 1 ]]; then
      git -C "$REPO" commit -q -m "memory inbox: imported ${#tracked[@]} file(s)" -m "Imported $today: $(printf '%s ' "${tracked[@]##*/}")" -- "${tracked[@]}"
      echo ">> committed the removal — push this branch / open a PR"
    fi
  fi
fi
[[ ${#failed[@]} -eq 0 ]] || { echo "!! ${#failed[@]} file(s) did not arrive: ${failed[*]}" >&2; exit 1; }

if [[ $PUSH == 1 && $DRY == 0 ]]; then
  [[ -d "$MEM/.git" ]] || { echo "!! $MEM is not the memory clone: scripts/memory-repo.sh init <url>" >&2; exit 1; }
  MEMORY_CLONE="$MEM" "$REPO/scripts/memory-repo.sh" sync
fi
echo ">> done."
