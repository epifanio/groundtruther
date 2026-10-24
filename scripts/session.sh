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
#                          [--next <session>] [--merge] [--issue <n>]
#       from the session's worktree: the mechanical close (PLANNING/queue.py close: the receipts, ⏭,
#       open ends, the prompt block, order rules), the checker, commit (with whatever is already
#       staged: the plan's banner, docs), push, a PR "[<session>] close", scripts/ci-wait.sh — and
#       there it stops, with the PR open. --merge merges it, and is yours to pass only when the owner
#       has said to merge this PR, in so many words; with --issue <n>, close that GitHub issue of the
#       project with a comment once the close has landed.
#
# When the planning files live in their own repo (PLANNING_HOME=separate: PLANNING/ is a link into the
# planning clone), claim and close commit there, pull with rebase and push to its main instead of
# opening a PR; start links PLANNING/ into the new worktree.
#   scripts/session.sh next [--slot N]
#       what each slot runs next, and the prompt of the first free slot, to paste.
#
# No session merges on its own. close leaves its PR open whatever MERGE_POLICY says, docs-only or
# not: --merge is the owner's go-ahead carried on the command line, and under MERGE_POLICY=owner-code
# even --merge is refused on a PR that reaches outside DOCS_PATHS. The one merge still automatic is
# the claim, because the claim is the slot lock and no work can start without it — and before merging
# it the script asks GitHub what that PR holds and refuses anything but the queue file. (With
# PLANNING_HOME=separate nothing is merged at all: claim and close push to the planning repo's main.)
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
MERGE_POLICY="owner-code"   # session, or owner-code: under owner-code, --merge is refused off the docs lane
DOCS_PATHS="PLANNING/ website/ docs/"   # the docs-only lane (§6.3): the only paths --merge may touch under owner-code

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

outside_lane() {   # $1 the lane: space-separated path prefixes and exact paths. Paths on stdin;
                   # prints those outside it, one per line.
  local lane="$1" path prefix inside
  while IFS= read -r path; do
    [[ -n "$path" ]] || continue
    inside=no
    for prefix in $lane; do
      prefix="${prefix%/}"
      if [[ "$path" == "$prefix" || "$path" == "$prefix"/* ]]; then inside=yes; break; fi
    done
    [[ "$inside" == yes ]] || printf '%s\n' "$path"
  done
}

outside_docs_lane() { outside_lane "$DOCS_PATHS"; }

pr_files() { (cd "$REPO" && gh pr view "$1" --json files -q '.files[].path'); }

pr_outside_lane() {   # $1 PR number, $2 the lane: 0 if every file the PR touches is inside it, else 1
                      # and the stray paths on stdout; 2 if GitHub could not be asked.
  local files stray
  files="$(pr_files "$1")" || return 2
  stray="$(printf '%s\n' "$files" | outside_lane "$2" | sort -u | tr '\n' ' ')"
  stray="${stray% }"
  [[ -z "$stray" ]] && return 0
  printf '%s\n' "$stray"; return 1
}

docs_only_pr() { pr_outside_lane "$1" "$DOCS_PATHS"; }   # §6.3: the lane --merge may touch under owner-code

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

land() {   # $1 session, $2 title, $3 yes|no (merge), $4 the lane the PR must stay inside for that merge
           # (empty: no lane check), $5 what to print when it does not: commit the queue and what is
           # staged, push, PR, CI, merge.
  local s="$1" title="$2" merge="$3" lane="${4:-}" hint="${5:-}" n url qroot
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
  if [[ "$merge" == yes && -n "$lane" ]]; then
    # The commit rides whatever branch the session used, so a reused branch puts its code in this PR
    # too — ask GitHub what is in it, never assume, and never merge past the lane.
    local stray rc=0
    stray="$(pr_outside_lane "$n" "$lane")" || rc=$?
    [[ $rc != 2 ]] || die "could not list PR #$n's files: gh pr view $n --json files"
    if [[ $rc == 1 ]]; then
      merge=no
      echo "!! PR #$n reaches outside the lane this merge may touch ($lane) — it changes: $stray" >&2
      [[ -z "$hint" ]] || printf '%s\n' "$hint" >&2
    fi
  fi
  if [[ "$merge" == yes ]]; then
    (cd "$REPO" && gh pr merge "$n" --merge) || die "merge of PR #$n failed. If $QUEUE_FILE conflicted, another session edited it: git fetch origin && git merge origin/$DEFAULT_BRANCH, take its side of the file, redo the edit (§6.3)"
    echo ">> PR #$n merged"
  else
    echo ">> PR #$n left open. Merging it is the owner's call, not yours (§6.3): say it is ready, and"
    echo ">> merge it only once they have said to — then:  gh pr merge $n --merge"
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
    # The claim is the only merge left automatic (it is the slot lock), and only ever the queue file.
    land "$s" "[$s] claim" yes "$QUEUE_FILE" \
      "!! a claim PR holds $QUEUE_FILE and nothing else. Put the rest on your own branch and claim again."
    ;;
  close)
    s="${1:?usage: session.sh close <session> <queue.py close arguments> [--merge]}"; shift
    in_session_worktree "$s"
    # Not merging is the default: a close PR is merged only on the owner's word, carried here as --merge.
    merge=no; issue=""; args=(); skip=0
    for a in "$@"; do
      if [[ $skip == 1 ]]; then issue="$a"; skip=0
      elif [[ "$a" == --merge ]]; then merge=yes
      elif [[ "$a" == --no-merge ]]; then merge=no   # now the default; still accepted
      elif [[ "$a" == --issue ]]; then skip=1
      else args+=("$a"); fi
    done
    lane=""
    if [[ "$MERGE_POLICY" == owner-code ]]; then lane="$DOCS_PATHS"; fi
    "$PY" "$REPO/PLANNING/queue.py" close "$s" ${args[@]+"${args[@]}"}
    land "$s" "[$s] close" "$merge" "$lane" \
      "!! a PR that changes code is the owner's to review and merge (§6.3, §12 Q3), go-ahead or not.
!! close this row ◐, with that review and merge as its open end.
!! to land the close on its own docs-only PR instead, put it on a fresh branch:
!!   git switch -c claude/$s-close origin/$DEFAULT_BRANCH && git cherry-pick claude/$s"
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
