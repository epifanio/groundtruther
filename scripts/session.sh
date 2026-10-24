#!/usr/bin/env bash
#
# session.sh — the mechanical parts of a session (PLANNING/WORKFLOW.md §6), done the same way every
# time, so the session spends its words on the work.
#
#   scripts/session.sh start <session>
#       git fetch; the worktree ../groundtruther-<session> on claude/<session> (from
#       origin/master, or on the branch if it already exists); the hooks path, and the
#       commit identity if that module is installed; scripts/memory-repo.sh sync; then prints the session's
#       row, its prompt, and the plan files the prompt names.
#   scripts/session.sh claim <session> [--who <handle>] [--beside --work "<what>"]
#       from the session's worktree: the row to ▶ with the date and Who (⏭ moved on), the checker,
#       commit, push, a PR "[<session>] claim", scripts/ci-wait.sh, merge. The claim of §6.1, merged
#       before any other work. A row already ▶ under another name stops it.
#   scripts/session.sh close <session> --mark done|open-ends --prs "#12, #13" --verified "…"
#                          [--shipped "…"] --note <memory note> [--open-end "<due> | <what> | <closes when>"]…
#                          [--next <session>] [--no-merge] [--issue <n>]
#       from the session's worktree: the mechanical close (PLANNING/queue.py close: the receipts, ⏭,
#       open ends, the prompt block, order rules), the checker, commit (with whatever is already
#       staged: the plan's banner, docs), push, a PR "[<session>] close", scripts/ci-wait.sh, merge
#       unless --no-merge; with --issue <n>, close that GitHub issue of the project with a comment
#       once the close has landed.
#
# When the planning files live in their own repo (PLANNING_HOME=separate: PLANNING/ is a link into the
# planning clone), claim and close commit there, pull with rebase and push to its main instead of
# opening a PR; start links PLANNING/ into the new worktree.
#   scripts/session.sh next [--slot N]
#       what each slot runs next, and the prompt of the first free slot, to paste.
#
# Under MERGE_POLICY=owner-code, claim and close never merge a PR that is not docs-only: before
# merging they ask GitHub what the PR touches and refuse if anything falls outside DOCS_PATHS. A
# session that reuses one branch for its code and its close puts both in one PR, and --no-merge is
# then a flag it has to remember; this does not depend on remembering.
#
# The queue edits are PLANNING/queue.py (it uses the checker's parser). The CI wait is
# scripts/ci-wait.sh. What stays the session's own: the State table, later prompts, the next prompt
# when the slot runs dry, the plan's banner and work-package row, the docs check, the memory note.
set -euo pipefail

# BASH_SOURCE, not $0: $0 is the calling shell when this file is sourced (the kit's tests source it).
REPO="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
PY="${PYTHON:-python3}"
PROJECT="groundtruther"
DEFAULT_BRANCH="master"
IDENTITY_CONFIG=""   # the identity module's git config for a new worktree, or empty
PLANNING_CLONE=""   # the planning repo's clone when PLANNING_HOME=separate, else empty
QUEUE_FILE="PLANNING/TODO_session_sequence.md"
MERGE_POLICY="owner-code"   # session, or owner-code: only docs-only PRs are the session's to merge
DOCS_PATHS="PLANNING/ website/ docs/"   # the docs-only lane (§6.3): path prefixes a session may merge itself

main_checkout() {   # the main checkout, also when run from a linked worktree
  local c
  c="$(git -C "$1" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || { printf '%s' "$1"; return; }
  if [[ "$(basename "$c")" == .git ]]; then dirname "$c"; else printf '%s' "$1"; fi
}
usage() { sed -n '2,/^set -euo/p' "$0" | sed '$d'; }
die() { echo "!! $*" >&2; exit 1; }

in_session_worktree() {   # the current checkout must be the session's own worktree
  local want="claude/$1" have
  have="$(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  [[ "$have" == "$want" ]] || die "run this from the session's worktree (branch $want; this is ${have:-no branch})"
}

outside_docs_lane() {   # paths on stdin; prints those outside DOCS_PATHS, one per line
  local path prefix inside
  while IFS= read -r path; do
    [[ -n "$path" ]] || continue
    inside=no
    for prefix in $DOCS_PATHS; do
      prefix="${prefix%/}"
      if [[ "$path" == "$prefix" || "$path" == "$prefix"/* ]]; then inside=yes; break; fi
    done
    [[ "$inside" == yes ]] || printf '%s\n' "$path"
  done
}

pr_files() { (cd "$REPO" && gh pr view "$1" --json files -q '.files[].path'); }

docs_only_pr() {   # $1 PR number: 0 if every file it touches is in the docs lane, else 1 and the
                   # stray paths on stdout. §6.3: only such a PR is the session's own to merge.
  local files stray
  files="$(pr_files "$1")" || return 2
  stray="$(printf '%s\n' "$files" | outside_docs_lane | sort -u | tr '\n' ' ')"
  stray="${stray% }"
  [[ -z "$stray" ]] && return 0
  printf '%s\n' "$stray"; return 1
}

land_planning_repo() {   # PLANNING/ is a link into the planning clone: commit there, pull --rebase, push to its main
  local root="$1" title="$2"
  git -C "$root" add "$QUEUE_FILE"
  if git -C "$root" diff --cached --quiet; then echo ">> nothing to commit in the planning repo"; return 0; fi
  git -C "$root" commit -q -m "$title"
  git -C "$root" pull -q --rebase --autostash \
    || die "the planning repo moved under you and $QUEUE_FILE conflicts: take its main's version of the file, look at your row (▶ under another name: the slot is taken, stop), redo the edit, git -C $root rebase --continue, then push (§6.3)"
  git -C "$root" push -q
  echo ">> pushed to the planning repo: $title ($(git -C "$root" rev-parse --short HEAD))"
}

land() {   # $1 session, $2 title, $3 yes|no (merge): commit the queue and what is staged, push, PR, CI, merge
  local s="$1" title="$2" merge="$3" n url qroot
  qroot="$(cd "$(dirname "$(realpath "$REPO/$QUEUE_FILE")")/.." && pwd)"
  if [[ "$qroot" != "$REPO" ]]; then land_planning_repo "$qroot" "$title"; return; fi
  git -C "$REPO" add "$QUEUE_FILE"
  if git -C "$REPO" diff --cached --quiet; then echo ">> nothing to commit"; return 0; fi
  git -C "$REPO" commit -q -m "$title"
  git -C "$REPO" push -q -u origin "claude/$s"
  n="$(cd "$REPO" && gh pr list --head "claude/$s" --state open --json number -q '.[0].number' 2>/dev/null || true)"
  if [[ -z "$n" ]]; then
    url="$(cd "$REPO" && gh pr create --base "$DEFAULT_BRANCH" --head "claude/$s" --title "$title" \
           --body "$title (PLANNING/WORKFLOW.md §6.1), by scripts/session.sh." | tail -1)"
    n="${url##*/}"
    echo ">> PR #$n: $url"
  else
    echo ">> PR #$n (already open) updated"
  fi
  "$REPO/scripts/ci-wait.sh" "$n" || die "CI is red on PR #$n: fix it, push, then: gh pr merge $n --merge"
  if [[ "$merge" == yes && "$MERGE_POLICY" == owner-code ]]; then
    # §6.3: only a docs-only PR is the session's to merge. The close commit rides whatever branch the
    # session used, so a reused branch puts code in this PR — ask GitHub what is in it, never assume.
    local stray rc=0
    stray="$(docs_only_pr "$n")" || rc=$?
    [[ $rc != 2 ]] || die "could not list PR #$n's files: gh pr view $n --json files"
    if [[ $rc == 1 ]]; then
      merge=no
      echo "!! PR #$n is NOT docs-only — it changes: $stray" >&2
      echo "!! not merging it: a PR that changes code is the owner's to review and merge (§6.3, §12 Q3)." >&2
      echo "!! close this row ◐, with that review and merge as its open end." >&2
      echo "!! to land the close on its own docs-only PR instead, put it on a fresh branch:" >&2
      echo "!!   git switch -c claude/$s-close origin/$DEFAULT_BRANCH && git cherry-pick claude/$s" >&2
    fi
  fi
  if [[ "$merge" == yes ]]; then
    (cd "$REPO" && gh pr merge "$n" --merge) || die "merge of PR #$n failed. If $QUEUE_FILE conflicted, another session edited it: git fetch origin && git merge origin/$DEFAULT_BRANCH, take its side of the file, redo the edit (§6.3)"
    echo ">> PR #$n merged"
  else
    echo ">> PR #$n left open (--no-merge)"
  fi
}

# sourced (by the kit's tests) rather than run: define the functions and stop.
if [[ "${BASH_SOURCE[0]:-}" != "${0}" ]]; then return 0; fi

cmd="${1:-}"; shift || true
case "$cmd" in
  start)
    s="${1:?usage: session.sh start <session>}"
    main="$(main_checkout "$REPO")"
    wt="$(dirname "$main")/$PROJECT-$s"; br="claude/$s"
    git -C "$main" fetch -q origin
    if [[ -d "$wt" ]]; then
      echo ">> worktree exists: $wt (branch $(git -C "$wt" rev-parse --abbrev-ref HEAD))"
    elif git -C "$main" show-ref --verify -q "refs/heads/$br"; then
      git -C "$main" worktree add -q "$wt" "$br"
      echo ">> worktree $wt on existing branch $br: carry on from what it holds"
    elif git -C "$main" show-ref --verify -q "refs/remotes/origin/$br"; then
      git -C "$main" worktree add -q "$wt" -b "$br" "origin/$br"
      echo ">> worktree $wt on $br from origin: carry on from what it holds"
    else
      git -C "$main" worktree add -q "$wt" -b "$br" "origin/$DEFAULT_BRANCH"
      echo ">> worktree $wt on new branch $br from origin/$DEFAULT_BRANCH"
    fi
    if [[ -d "$wt/.githooks" ]]; then git -C "$wt" config core.hooksPath .githooks; fi
    if [[ -n "$PLANNING_CLONE" && ! -e "$wt/PLANNING" ]]; then
      [[ -d "$PLANNING_CLONE/PLANNING" ]] || die "no planning clone at $PLANNING_CLONE: scripts/planning-repo.sh init <url>"
      git -C "$PLANNING_CLONE" pull -q --rebase --autostash 2>/dev/null || echo "!! planning repo: pull failed" >&2
      ln -s "$PLANNING_CLONE/PLANNING" "$wt/PLANNING"; echo ">> PLANNING linked to $PLANNING_CLONE/PLANNING"
    fi
    if [[ -n "$IDENTITY_CONFIG" ]]; then (cd "$wt" && eval "$IDENTITY_CONFIG"); fi
    [[ -n "$(git -C "$wt" config user.email 2>/dev/null || true)" ]] \
      || echo "!! no git identity here yet: git -C $wt config user.name <you> && git -C $wt config user.email <yours>" >&2
    "$wt/scripts/memory-repo.sh" sync || echo "!! memory sync failed: scripts/memory-repo.sh status" >&2
    "$PY" "$wt/PLANNING/queue.py" row "$s" \
      || echo "!! no row for \`$s\`: a side session claims with: scripts/session.sh claim $s --beside --work \"<what>\"" >&2
    tmp="$(mktemp)"
    if "$PY" "$wt/PLANNING/queue.py" prompt "$s" > "$tmp" 2>/dev/null; then
      echo "---- the prompt"; cat "$tmp"
      echo "---- read first"; grep -oE 'PLANNING/TODO_[A-Za-z0-9_.-]+\.md' "$tmp" | sort -u || true
    fi
    rm -f "$tmp"
    echo ">> next: cd $wt && scripts/session.sh claim $s"
    ;;
  claim)
    s="${1:?usage: session.sh claim <session> [--who <handle>] [--beside --work \"<what>\"]}"; shift
    in_session_worktree "$s"
    "$PY" "$REPO/PLANNING/queue.py" claim "$s" "$@"
    land "$s" "[$s] claim" yes
    ;;
  close)
    s="${1:?usage: session.sh close <session> <queue.py close arguments> [--no-merge]}"; shift
    in_session_worktree "$s"
    merge=yes; issue=""; args=(); skip=0
    for a in "$@"; do
      if [[ $skip == 1 ]]; then issue="$a"; skip=0
      elif [[ "$a" == --no-merge ]]; then merge=no
      elif [[ "$a" == --issue ]]; then skip=1
      else args+=("$a"); fi
    done
    "$PY" "$REPO/PLANNING/queue.py" close "$s" ${args[@]+"${args[@]}"}
    land "$s" "[$s] close" "$merge"
    if [[ -n "$issue" ]]; then
      (cd "$REPO" && gh issue close "$issue" --comment "Closed by session \`$s\` (PLANNING/WORKFLOW.md §6.1); the receipts are on its row in PLANNING/TODO_session_sequence.md.") \
        && echo ">> issue #$issue closed" || echo "!! issue #$issue not closed: gh issue close $issue --comment '…'" >&2
    fi
    ;;
  next)
    "$PY" "$REPO/PLANNING/queue.py" next "$@"
    if s="$("$PY" "$REPO/PLANNING/queue.py" next --paste "$@" 2>/dev/null)"; then
      echo "---- paste into a fresh session: \`$s\`"
      "$PY" "$REPO/PLANNING/queue.py" prompt "$s"
    fi
    ;;
  -h|--help|"") usage ;;
  *) echo "unknown command: $cmd" >&2; usage; exit 2 ;;
esac
