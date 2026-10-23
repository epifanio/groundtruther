#!/usr/bin/env bash
#
# memory-repo.sh — keep the Claude project memory in its OWN private git repo, so every machine and
# every cloud session shares it through git (epifanio/groundtruther-memory; PLANNING/WORKFLOW.md §5.2 rule 5).
#
# Claude Code reads and writes this project's auto memory straight in the clone: the project's
# .claude/settings.json sets `autoMemoryDirectory` to ~/dev/groundtruther-memory. No symlink, no per-machine
# memory directory to find. A machine that keeps the clone elsewhere overrides the setting in
# .claude/settings.local.json (personal, not committed) and runs this script with MEMORY_CLONE set.
#
#   scripts/memory-repo.sh init <git-url> [--import <dir>]
#                                           # first time on a machine: clone; copy an older memory dir's
#                                           # files INTO the clone (nothing overwritten); check the wiring; sync
#   scripts/memory-repo.sh sync             # commit local changes, pull --rebase, push
#   scripts/memory-repo.sh sync-if-changed  # the Stop hook: sync only when a note changed or a commit waits
#   scripts/memory-repo.sh prune [--keep N] [--no-sync]
#                                           # move older session-note lines out of MEMORY.md (N kept, default 40)
#                                           # into index_session_notes_<yyyy-mm>.md, leave a pointer line, sync
#   scripts/memory-repo.sh scan             # look for secrets in the clone (file:line, never the value)
#   scripts/memory-repo.sh status           # the clone, the wiring (autoMemoryDirectory), changes, ahead/behind
#
# ENV: MEMORY_CLONE [~/dev/groundtruther-memory] · PROJECT_ROOT [the MAIN checkout of this repo, also from a worktree]
#
# Several accounts/machines: each runs `init` once (own $HOME, own clone), all share one remote. The
# installed hooks run `sync` at the start and `sync-if-changed` at the end of a session.
#
# Conflict copies (<name>.local-<date>.md from init --import, <name>.incoming-<date>.md from the inbox
# import) are for a human to merge and delete. They are git-ignored, never pushed.
#
# Size: Claude Code loads only the first 200 lines or 25 KB of MEMORY.md. `sync` warns at 150 lines or
# 16 KB and prunes by itself at 190 lines or 20 KB.
#
# Secrets: `sync` REFUSES to commit a file holding a well-known credential format and WARNS on
# `password: <long value>`-style lines. A heuristic, not a guarantee. MEMORY_ALLOW_SECRETS=1 overrides once.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
main_checkout() {   # the main checkout, also when run from a linked worktree
  local c
  c="$(git -C "$1" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || { printf '%s' "$1"; return; }
  if [[ "$(basename "$c")" == .git ]]; then dirname "$c"; else printf '%s' "$1"; fi
}
PROJECT_ROOT="${PROJECT_ROOT:-$(main_checkout "$REPO")}"
MEMORY_CLONE="${MEMORY_CLONE:-$HOME/dev/groundtruther-memory}"

SECRET_BLOCK='ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|(^|[^A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|://[^:/ @]+:[^@ /]+@'
SECRET_WARN='(password|passwd|secret|api[_-]?key|token)[A-Za-z_-]{0,10}[[:space:]]*[:=][[:space:]]*[A-Za-z0-9+/_.-]{20,}'

scan_stream() {   # prints "BLOCK label" / "warn label (line n)"; never the value
  local label="$1" data hit
  data="$(cat)"
  if grep -qE "$SECRET_BLOCK" <<<"$data"; then echo "BLOCK $label"; return 1; fi
  hit="$(grep -nIiE "$SECRET_WARN" <<<"$data" | cut -d: -f1 | paste -sd, - || true)"
  [[ -z "$hit" ]] || echo "warn  $label (line $hit)"
  return 0
}

CONFLICT_PATTERNS=('*.local-[0-9]*.md' '*.incoming-[0-9]*.md')
ensure_gitignore() {
  local gi="$MEMORY_CLONE/.gitignore" pat
  touch "$gi"
  for pat in "${CONFLICT_PATTERNS[@]}"; do grep -qxF "$pat" "$gi" || printf '%s\n' "$pat" >> "$gi"; done
}

wired_dir() {   # the directory Claude Code will use here: settings.local.json over settings.json, ~ expanded
  python3 - "$REPO" "$PROJECT_ROOT" <<'PY'
import json, os, sys
for root in dict.fromkeys(sys.argv[1:]):
    for name in ("settings.local.json", "settings.json"):
        path = os.path.join(root, ".claude", name)
        try:
            with open(path, encoding="utf-8") as f:
                value = json.load(f).get("autoMemoryDirectory")
        except (OSError, ValueError):
            continue
        if value:
            print(os.path.expanduser(value))
            sys.exit(0)
print("")
PY
}
warn_unwired() {
  local w; w="$(wired_dir)"
  if [[ -z "$w" ]]; then
    echo "!! no autoMemoryDirectory in .claude/settings.json: Claude Code keeps this project's memory elsewhere." >&2
    echo "!! Add to .claude/settings.json: \"autoMemoryDirectory\": \"$MEMORY_CLONE\"" >&2
  elif [[ "${w%/}" != "${MEMORY_CLONE%/}" ]]; then
    echo "!! Claude Code's auto memory here is $w, not the clone $MEMORY_CLONE." >&2
    echo "!! Point autoMemoryDirectory at the clone in .claude/settings.local.json, or run this script with MEMORY_CLONE=$w" >&2
  fi
}

cmd="${1:-}"; shift || true
case "$cmd" in
  init)
    url="${1:?usage: memory-repo.sh init <git-url> [--import <dir>]}"; shift
    import=""
    while [[ $# -gt 0 ]]; do
      case "$1" in --import) import="${2:?--import <dir>}"; shift 2 ;; *) echo "unknown arg: $1" >&2; exit 2 ;; esac
    done
    if [[ -d "$MEMORY_CLONE/.git" ]]; then
      echo ">> clone exists: $MEMORY_CLONE"
    else
      mkdir -p "$(dirname "$MEMORY_CLONE")"; git clone -q "$url" "$MEMORY_CLONE"; echo ">> cloned $url -> $MEMORY_CLONE"
    fi
    if [[ -n "$import" ]]; then
      [[ -d "$import" ]] || { echo "!! --import: no such directory: $import" >&2; exit 1; }
      n=0; shopt -s dotglob nullglob
      for f in "$import"/*; do
        b="$(basename "$f")"; [[ "$b" == .git ]] && continue
        if [[ ! -e "$MEMORY_CLONE/$b" ]]; then
          cp -a "$f" "$MEMORY_CLONE/$b"; n=$((n+1))
        elif [[ -f "$f" ]] && ! cmp -s "$f" "$MEMORY_CLONE/$b"; then
          cp -a "$f" "$MEMORY_CLONE/${b%.md}.local-$(date +%F).md"; echo "   CLASH  $b -> kept as ${b%.md}.local-$(date +%F).md"
        fi
      done
      shopt -u dotglob nullglob
      echo ">> imported $n file(s) from $import (nothing overwritten; $import itself is untouched)"
    fi
    [[ -f "$MEMORY_CLONE/.gitignore" ]] || printf '*.bak-*\n.DS_Store\n' > "$MEMORY_CLONE/.gitignore"
    ensure_gitignore
    w="$(wired_dir)"
    if [[ "${w%/}" == "${MEMORY_CLONE%/}" ]]; then echo ">> wired: autoMemoryDirectory = $MEMORY_CLONE"; else warn_unwired; fi
    "$0" sync
    ;;
  sync)
    [[ -d "$MEMORY_CLONE/.git" ]] || { echo "!! no clone at $MEMORY_CLONE — run: $0 init <git-url>" >&2; exit 1; }
    if [[ -f "$MEMORY_CLONE/MEMORY.md" && -z "${MEMORY_PRUNING:-}" ]]; then
      n=$(wc -l < "$MEMORY_CLONE/MEMORY.md"); b=$(wc -c < "$MEMORY_CLONE/MEMORY.md")
      if (( n > 190 || b > 20000 )); then
        echo "!! MEMORY.md is $n lines / $b bytes; Claude Code loads only the first 200 lines or 25 KB: pruning" >&2
        MEMORY_PRUNING=1 "$0" prune --no-sync
        n=$(wc -l < "$MEMORY_CLONE/MEMORY.md"); b=$(wc -c < "$MEMORY_CLONE/MEMORY.md")
        (( n > 190 || b > 20000 )) && echo "!! MEMORY.md is still $n lines / $b bytes: shorten the Rules, Project and People sections by hand" >&2
      elif (( n > 150 || b > 16000 )); then
        echo "!! MEMORY.md is $n lines / $b bytes, near the 200-line / 25 KB load limit: run $0 prune soon" >&2
      fi
    fi
    ensure_gitignore; cd "$MEMORY_CLONE"; git add -A
    if [[ "${MEMORY_ALLOW_SECRETS:-0}" != 1 ]]; then
      bad=()
      while IFS= read -r f; do
        out="$(git show ":$f" 2>/dev/null | scan_stream "$f")" || { bad+=("$f"); continue; }
        [[ -z "$out" ]] || echo "$out"
      done < <(git diff --cached --name-only --diff-filter=AM)
      if [[ ${#bad[@]} -gt 0 ]]; then
        git reset -q
        echo "!! NOT synced: ${#bad[@]} file(s) look like they hold a credential: ${bad[*]}" >&2
        exit 1
      fi
    fi
    git diff --cached --quiet || git commit -q -m "memory sync $(hostname -s 2>/dev/null || echo host) $(date +%F)"
    if git ls-remote --exit-code --heads origin >/dev/null 2>&1; then
      git pull -q --rebase --autostash || { echo "!! pull failed (conflict?): resolve in $MEMORY_CLONE, re-run sync" >&2; exit 1; }
    fi
    if git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then git push -q; else git push -q -u origin "$(git branch --show-current)"; fi
    echo ">> memory repo in sync ($(git rev-parse --short HEAD))"
    warn_unwired
    ;;
  sync-if-changed)   # for the Stop and SessionEnd hooks: sync only when there is something to push
    [[ -d "$MEMORY_CLONE/.git" ]] || { echo ">> memory: no clone at $MEMORY_CLONE, nothing to sync"; exit 0; }
    cd "$MEMORY_CLONE"
    ahead="$(git rev-list --count '@{u}..HEAD' 2>/dev/null || echo 0)"
    if [[ -n "$(git status --porcelain)" || "$ahead" != 0 ]]; then exec "$0" sync; fi
    echo ">> memory: nothing to sync"
    ;;
  prune)
    [[ -d "$MEMORY_CLONE/.git" ]] || { echo "!! no clone at $MEMORY_CLONE" >&2; exit 1; }
    keep=40; dosync=1
    while [[ $# -gt 0 ]]; do case "$1" in --keep) keep="${2:?--keep N}"; shift 2 ;; --no-sync) dosync=0; shift ;; *) echo "unknown arg: $1" >&2; exit 2 ;; esac; done
    python3 - "$MEMORY_CLONE/MEMORY.md" "$keep" "$(date +%Y-%m)" <<'PY'
import pathlib, sys
idx, keep, month = pathlib.Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
if not idx.exists():
    print(">> memory: no MEMORY.md; nothing to prune"); sys.exit(0)
lines = idx.read_text(encoding="utf-8").split("\n")
start = next((i for i, l in enumerate(lines) if l.startswith("## Session notes")), None)
if start is None:
    print(">> memory: no '## Session notes' section; nothing to prune"); sys.exit(0)
body = lines[start + 1:]
notes = [i for i, l in enumerate(body) if l.startswith("- [") and "index_session_notes_" not in l]
if len(notes) <= keep:
    print(f">> memory: {len(notes)} session-note line(s), {keep} kept: nothing to prune"); sys.exit(0)
move = set(notes[:len(notes) - keep])
archive = idx.parent / f"index_session_notes_{month}.md"
fresh = not archive.exists() or archive.stat().st_size == 0
with archive.open("a", encoding="utf-8") as f:
    if fresh:
        f.write(f"# Session notes moved out of MEMORY.md ({month})\n\nOne line per note, oldest first; the notes themselves are unchanged.\n\n")
    f.write("\n".join(body[i] for i in sorted(move)) + "\n")
body = [l for i, l in enumerate(body) if i not in move]
pointer = f"- [{archive.name}]({archive.name}) — older session notes, moved out of the index"
if not any(archive.name in l for l in body):
    j = next((k for k, l in enumerate(body) if l.strip()), len(body))
    body.insert(j, pointer)
idx.write_text("\n".join(lines[:start + 1] + body), encoding="utf-8")
print(f">> memory: moved {len(move)} session-note line(s) to {archive.name}; {keep} kept in MEMORY.md")
PY
    [[ $dosync -eq 0 ]] || "$0" sync
    ;;
  scan)
    [[ -d "$MEMORY_CLONE/.git" ]] || { echo "!! no clone at $MEMORY_CLONE" >&2; exit 1; }
    cd "$MEMORY_CLONE"; n=0
    while IFS= read -r f; do
      [[ -f "$f" ]] || continue
      out="$(scan_stream "$f" < "$f")" || n=$((n+1))
      [[ -z "$out" ]] || echo "$out"
    done < <(git ls-files --cached --others --exclude-standard)
    echo ">> scan done: $n file(s) blocked"; [[ $n -eq 0 ]] || exit 1
    ;;
  status)
    echo "clone:   $MEMORY_CLONE"
    w="$(wired_dir)"; echo "wired:   autoMemoryDirectory = ${w:-(not set)}"
    [[ -d "$MEMORY_CLONE/.git" ]] || { echo "(no clone yet: $0 init <git-url>)"; exit 0; }
    git -C "$MEMORY_CLONE" status -sb; warn_unwired
    ;;
  -h|--help|"") sed -n '2,/^set -euo/p' "$0" | sed '$d' ;;
  *) echo "unknown command: $cmd" >&2; exit 2 ;;
esac
