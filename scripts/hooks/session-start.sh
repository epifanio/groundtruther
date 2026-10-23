#!/usr/bin/env bash
# SessionStart hook (.claude/settings.json): sync the memory repo, then say what the queue runs next
# and which worktrees exist. What it prints becomes context for the session, so it stays short. It
# never fails the session start.
root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$root" 2>/dev/null || exit 0
PLANNING_CLONE=""   # the planning repo's clone when PLANNING_HOME=separate, else empty
if [[ -n "$PLANNING_CLONE" ]]; then
  if [[ -d "$PLANNING_CLONE/.git" ]]; then
    git -C "$PLANNING_CLONE" pull -q --rebase --autostash 2>/dev/null || echo "planning: pull failed (scripts/planning-repo.sh status)"
    [[ -e PLANNING ]] || { ln -s "$PLANNING_CLONE/PLANNING" PLANNING && echo "planning: linked PLANNING -> $PLANNING_CLONE/PLANNING"; }
  else
    echo "planning: no clone at $PLANNING_CLONE; run scripts/planning-repo.sh init <url>"
  fi
fi
if [[ -x scripts/memory-repo.sh ]]; then
  if out="$(scripts/memory-repo.sh sync 2>&1)"; then
    echo "memory: ${out##*$'\n'}"
  else
    echo "memory: NOT synced (${out##*$'\n'}); run scripts/memory-repo.sh status"
  fi
fi
if [[ -f PLANNING/queue.py ]]; then
  echo "queue (scripts/session.sh next):"
  python3 PLANNING/queue.py next 2>/dev/null | sed 's/^/  /' || true
fi
echo "worktrees:"
git worktree list 2>/dev/null | sed 's/^/  /' || true
exit 0
