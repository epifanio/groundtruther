#!/usr/bin/env bash
#
# ci-wait.sh — wait for a PR's checks and exit with their status (PLANNING/WORKFLOW.md §6.3).
#
#   scripts/ci-wait.sh <pr-number>    exit 0 when every check passed; 1 when one failed or the wait
#                                     could not be done; one line of output either way
#
# Uses `gh pr checks --watch --fail-fast` where gh has it; on an older gh, `gh run watch
# --exit-status` for every run of the PR's head commit. Checks take a moment to appear after a push:
# while the repo has workflows and GitHub reports none yet, it retries for up to a minute. A repo
# with no workflows is green by definition. Read this script's exit status; never pipe it (`| tail`
# under `set -e` once hid a red run and a merge went ahead).
set -uo pipefail

n="${1:?usage: ci-wait.sh <pr-number>}"
root="$(cd "$(dirname "$0")/.." && pwd)"
has_workflows=0; [[ -d "$root/.github/workflows" ]] && has_workflows=1
st=1

if gh pr checks --help 2>/dev/null | grep -q -- '--watch'; then
  out=""
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do
    out="$(gh pr checks "$n" 2>&1 || true)"
    if grep -qi 'no checks reported' <<<"$out"; then
      [[ $has_workflows -eq 1 ]] || { echo "ci-wait: PR #$n has no checks and the repo has no workflows: green"; exit 0; }
      sleep 5; continue
    fi
    break
  done
  if grep -qi 'no checks reported' <<<"$out"; then echo "ci-wait: PR #$n: no checks reported after a minute"; exit 1; fi
  gh pr checks "$n" --watch --fail-fast >/dev/null 2>&1; st=$?
else
  sha="$(gh pr view "$n" --json headRefOid -q .headRefOid 2>/dev/null)" || { echo "ci-wait: cannot read PR #$n"; exit 1; }
  ids=""
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do
    ids="$(gh api "repos/{owner}/{repo}/actions/runs?head_sha=$sha" -q '.workflow_runs[].id' 2>/dev/null || true)"
    [[ -n "$ids" || $has_workflows -eq 0 ]] && break
    sleep 5
  done
  if [[ -z "$ids" ]]; then
    [[ $has_workflows -eq 1 ]] && { echo "ci-wait: no runs for ${sha:0:10} after a minute"; exit 1; }
    echo "ci-wait: PR #$n has no runs and the repo has no workflows: green"; exit 0
  fi
  st=0
  for id in $ids; do gh run watch "$id" --exit-status >/dev/null 2>&1 || st=1; done
fi

if [[ $st -eq 0 ]]; then echo "ci-wait: PR #$n checks green"; else echo "ci-wait: PR #$n checks RED (exit $st)"; fi
exit "$st"
