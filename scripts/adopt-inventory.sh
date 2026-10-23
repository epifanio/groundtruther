#!/usr/bin/env bash
#
# adopt-inventory.sh — list the knowledge a project already carries from agentic coding, so that the
# harvest session (/adopt-project; the kit's docs/adopting.md) knows what to read and the owner can say
# what still counts (PLANNING/WORKFLOW.md §12 Q13).
#
#   scripts/adopt-inventory.sh [--repo <checkout>]    # prints a Markdown inventory; reads only, changes nothing
#
# Sources: instruction files in the checkout; Claude Code's auto-memory directories and transcripts
# under ~/.claude/projects (every project on this machine: the owner says which are this project's);
# branches with unpushed commits and remote branches; open PRs and issues (gh, when it answers);
# roadmap, TODO, plan, decision and operations files in the checkout. Secrets are never printed: only
# paths, counts and dates. ENV: CLAUDE_CONFIG_DIR [~/.claude].
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
if [[ "${1:-}" == --repo ]]; then REPO="$(cd "${2:?--repo <checkout>}" && pwd)"; fi
CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
shopt -s nullglob

lines() { wc -l < "$1" 2>/dev/null | tr -d ' '; }

echo "# Inventory of existing knowledge: $(basename "$REPO"), $(date +%F)"
echo
echo "## Instruction files (the rules the agent followed)"
n=0
for f in CLAUDE.md CLAUDE.local.md .claude/CLAUDE.md AGENTS.md .cursorrules .github/copilot-instructions.md; do
  [[ -f "$REPO/$f" ]] && { echo "- \`$f\` ($(lines "$REPO/$f") lines)"; n=$((n+1)); }
done
while IFS= read -r f; do
  rel="${f#"$REPO"/}"; echo "- \`$rel\` ($(lines "$f") lines)"; n=$((n+1))
done < <(find "$REPO" -mindepth 2 -name CLAUDE.md -not -path '*/.git/*' -not -path '*/node_modules/*' -not -path '*/.claude/worktrees/*' 2>/dev/null | sort)
for f in "$REPO"/.claude/rules/*.md "$REPO"/.claude/rules/*/*.md "$REPO"/.cursor/rules/*; do
  rel="${f#"$REPO"/}"; echo "- \`$rel\` ($(lines "$f") lines)"; n=$((n+1))
done
[[ $n -gt 0 ]] || echo "- none"

echo
echo "## Claude Code auto memory on this machine (the owner says which is this project's)"
n=0
for d in "$CLAUDE_HOME"/projects/*/memory; do
  [[ -f "$d/MEMORY.md" ]] || continue
  files=0; for f in "$d"/*.md; do files=$((files+1)); done
  newest="$(ls -t "$d" 2>/dev/null | head -1)"
  echo "- \`$d\`: $(lines "$d/MEMORY.md") index lines, $files files, newest \`$newest\`"; n=$((n+1))
done
[[ $n -gt 0 ]] || echo "- none"

echo
echo "## Transcripts on this machine (read once by the harvest session; never committed)"
n=0
for d in "$CLAUDE_HOME"/projects/*/; do
  c=0; for f in "$d"*.jsonl; do c=$((c+1)); done
  [[ $c -gt 0 ]] || continue
  first="$(ls -tr "$d"*.jsonl | head -1)"; last="$(ls -t "$d"*.jsonl | head -1)"
  echo "- \`$d\`: $c transcript(s), $(date -r "$first" +%F 2>/dev/null || echo ?) to $(date -r "$last" +%F 2>/dev/null || echo ?)"; n=$((n+1))
done
[[ $n -gt 0 ]] || echo "- none"

echo
echo "## Work in flight"
n=0
if git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1; then
  while IFS= read -r b; do
    [[ -n "$b" ]] || continue
    if git -C "$REPO" rev-parse --verify -q "origin/$b" >/dev/null 2>&1; then
      ahead="$(git -C "$REPO" rev-list --count "origin/$b..$b" 2>/dev/null || echo 0)"
      [[ "$ahead" != 0 ]] && { echo "- local branch \`$b\`: $ahead commit(s) not on origin"; n=$((n+1)); }
    else
      echo "- local branch \`$b\`: not on origin ($(git -C "$REPO" log -1 --format=%cs "$b" 2>/dev/null))"; n=$((n+1))
    fi
  done < <(git -C "$REPO" for-each-ref --format='%(refname:short)' refs/heads 2>/dev/null)
  while IFS= read -r line; do
    [[ -n "$line" && "${line% *}" != origin && "$line" != *"/HEAD "* ]] || continue   # not the HEAD pointer
    echo "- remote branch \`${line% *}\` (last commit ${line##* })"; n=$((n+1))
  done < <(git -C "$REPO" for-each-ref --format='%(refname:short) %(committerdate:short)' refs/remotes/origin 2>/dev/null | grep -v -E '^origin/(main|master) ' || true)
  if command -v gh >/dev/null 2>&1; then
    prs="$(cd "$REPO" && gh pr list --state open --limit 100 --json number,title,headRefName,author \
           --jq '.[] | "- open PR #\(.number) \(.title) (`\(.headRefName)`, \(.author.login))"' 2>/dev/null || true)"
    [[ -z "$prs" ]] || { echo "$prs"; n=$((n+1)); }
    issues="$(cd "$REPO" && gh issue list --state open --limit 100 --json number,title \
              --jq '.[] | "- open issue #\(.number) \(.title)"' 2>/dev/null || true)"
    [[ -z "$issues" ]] || { echo "$issues"; n=$((n+1)); }
  fi
fi
[[ $n -gt 0 ]] || echo "- none found (gh may not have answered: check PRs and issues by hand)"

echo
echo "## Plans, roadmaps, decisions and operations notes in the checkout"
n=0
while IFS= read -r f; do
  rel="${f#"$REPO"/}"; echo "- \`$rel\` ($(lines "$f") lines)"; n=$((n+1))
done < <(find "$REPO" -maxdepth 4 -type f \( -iname 'ROADMAP*' -o -iname 'TODO*.md' -o -iname 'PLAN*.md' -o -iname 'DECISIONS*' \
         -o -iname 'ADR*' -o -ipath '*/adr/*' -o -ipath '*/adrs/*' -o -ipath '*/decisions/*' -o -ipath '*/rfcs/*' \
         -o -iname 'DEPLOY*' -o -iname 'RUNBOOK*' -o -iname 'OPERATIONS*' -o -iname 'CHANGELOG*' \) \
         -not -path '*/.git/*' -not -path '*/.github/*' -not -path '*/node_modules/*' -not -path "$REPO/PLANNING/*" -not -path '*/.claude/worktrees/*' 2>/dev/null | sort)
[[ $n -gt 0 ]] || echo "- none"
echo
echo "Next: the owner says which sources still count (Q13); then /adopt-project harvests them (the kit's docs/adopting.md)."
