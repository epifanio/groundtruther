#!/usr/bin/env python3
# GroundTruther — a toolset for seafloor characterization
#
# Copyright (C) 2023-2026 Massimo Di Stefano <epiesasha@me.com>
# https://github.com/epifanio/groundtruther
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <https://www.gnu.org/licenses/>.

"""PreToolUse hook on Bash (.claude/settings.json): block, before it runs, a command that would break
one of the git rules every session keeps (CLAUDE.md; WORKFLOW.md §10). Exit 2 blocks the call and
the line on stderr is what the session reads; exit 0 lets it through.

1. Never switch branches in a checkout you did not create: `git checkout <branch>` or `git switch`
   in the MAIN checkout (where .git is a directory, not a worktree's file). A session works in its
   own worktree (scripts/session.sh start). Restoring a file (`git checkout -- <path>`) is fine.
2. Never delete branches from `git branch` output: `git branch -d/-D` or `git push --delete` fed by
   a pipe, xargs, $(…), backticks or a for loop. Branches named one by one are fine.
3. A branch with an open PR is not rebased and force-pushed: `git push --force|-f|--force-with-lease`
   when `gh pr list` shows an open PR for the branch, or when gh cannot be asked.
4. No clean-up until the owner declares the session done: `git worktree remove|prune`, and `rm -r` of
   a registered worktree, unless the command carries SESSION_DONE=<session>, which a session writes
   only on the owner's word.
5. No merge by hand: `gh pr merge`, or the same call through `gh api .../pulls/<n>/merge`, unless the
   command carries OWNER_MERGE=<pr> naming that same PR, which a session writes only once the owner
   has said to merge that PR. `scripts/session.sh close … --merge` is the path, and the guard it
   carries (MERGE_POLICY, DOCS_PATHS) is the whole point: a hand-run `gh pr merge` walked past it
   twice (docs/lessons.md). The token does not make the merge safe; it makes it deliberate, named and
   greppable, the way SESSION_DONE= does for a worktree.

By hand:
  echo '{"tool_name":"Bash","tool_input":{"command":"git switch -c x"},"cwd":"."}' | python3 scripts/hooks/guard-git.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

SEG = r"[^|;&]*"   # within one simple command of a pipeline or list


def run(args: list[str], cwd: str | None = None, timeout: int = 20) -> str | None:
    try:
        out = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def block(msg: str) -> None:
    print(f"blocked by scripts/hooks/guard-git.py: {msg}", file=sys.stderr)
    sys.exit(2)


def is_main_checkout(d: str) -> bool:
    gd = run(["git", "-C", d, "rev-parse", "--path-format=absolute", "--git-dir"])
    cd = run(["git", "-C", d, "rev-parse", "--path-format=absolute", "--git-common-dir"])
    return bool(gd and cd) and os.path.realpath(gd) == os.path.realpath(cd)


def pushed_branch(cmd: str, d: str) -> str:
    """The branch a `git push` targets: the refspec's destination, else the current branch."""
    seg = next((s for s in re.split(r"[|;&]+", cmd) if re.search(r"\bgit\b.*\bpush\b", s)), "")
    toks = seg.split()
    if "push" in toks:
        rest = [t for t in toks[toks.index("push") + 1:] if not t.startswith("-")]
        if len(rest) >= 2:
            return rest[1].split(":")[-1].lstrip("+")
    return run(["git", "-C", d, "rev-parse", "--abbrev-ref", "HEAD"]) or ""


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("tool_name") != "Bash":
        return 0
    cmd = (data.get("tool_input") or {}).get("command") or ""
    cwd = data.get("cwd") or os.getcwd()
    m = re.match(r"\s*cd\s+(\S+)\s*(?:&&|;)", cmd)                 # `cd <dir> && git …`
    if m:
        cwd = os.path.join(cwd, os.path.expanduser(m.group(1).strip("\"'")))
    m = re.search(r"\bgit\s+-C\s+(\S+)", cmd)                        # `git -C <dir> …`
    gitdir = os.path.join(cwd, os.path.expanduser(m.group(1).strip("\"'"))) if m else cwd

    # 1. a branch switch in the main checkout
    if re.search(r"\bgit\b(?:\s+-C\s+\S+)?\s+(checkout|switch)\b", cmd) \
            and not re.search(r"\bcheckout\b" + SEG + r"\s--\s", cmd) and is_main_checkout(gitdir):
        block("never switch branches in a checkout you did not create, and this is the main checkout. "
              "Work in your session's worktree (scripts/session.sh start <session>); to restore a file, "
              "`git checkout -- <path>`.")

    # 2. branches deleted from `git branch` output
    if re.search(r"\bgit\b" + SEG + r"\bbranch\b" + SEG + r"\s(-[dD]|--delete)\b", cmd) \
            or re.search(r"\bgit\b" + SEG + r"\bpush\b" + SEG + r"--delete\b", cmd):
        fed = (re.search(r"\|\s*(xargs\s+)?git\b", cmd) or re.search(r"\$\(|`", cmd)
               or re.search(r"\bfor\b.*\bin\b.*\bgit\s+branch", cmd))
        if fed:
            block("never delete branches from `git branch` output: it lists every session's branches "
                  "(one loop once deleted 815). Delete only the branches you name, by name.")

    # 3. a force push onto an open PR
    if re.search(r"\bgit\b" + SEG + r"\bpush\b" + SEG + r"(\s--force\b|\s-f\b|\s--force-with-lease)", cmd):
        branch = pushed_branch(cmd, gitdir)
        prs = run(["gh", "pr", "list", "--head", branch, "--state", "open", "--json", "number",
                   "--jq", "length"], cwd=gitdir) if branch else None
        if prs is None:
            block(f"a force push of {branch or 'this branch'} cannot be checked against open PRs (gh did not "
                  "answer), and a branch with an open PR is never rebased and force-pushed (WORKFLOW.md §6.3). "
                  "Merge origin/<default branch> in and push normally.")
        if prs != "0":
            block(f"{branch} has an open PR: a branch with an open PR is never rebased and force-pushed "
                  "(WORKFLOW.md §6.3). Merge origin/<default branch> in and push normally.")

    # 4. a clean-up before the owner declared the session done
    if "SESSION_DONE=" not in cmd:
        if re.search(r"\bgit\b" + SEG + r"\bworktree\s+(remove|prune)\b", cmd):
            block("worktrees are live workspaces: no clean-up until the owner declares that session done. "
                  "On their word, prefix the command with SESSION_DONE=<session>.")
        m = re.search(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*\s+(\S+)", cmd)
        if m:
            target = os.path.realpath(os.path.join(cwd, os.path.expanduser(m.group(1).strip("\"'"))))
            listing = run(["git", "worktree", "list", "--porcelain"], cwd=gitdir) or ""
            paths = [os.path.realpath(l[len("worktree "):]) for l in listing.splitlines() if l.startswith("worktree ")]
            if target in paths:
                block(f"{m.group(1)} is a registered worktree, a live workspace: no clean-up until the owner "
                      "declares that session done. On their word, prefix the command with SESSION_DONE=<session>.")

    # 5. a merge run by hand, past scripts/session.sh and past the owner's go-ahead
    if re.search(r"\bgh\b" + SEG + r"\bpr\b" + SEG + r"\bmerge\b", cmd) \
            or re.search(r"\bgh\b" + SEG + r"\bapi\b" + SEG + r"/pulls/\d+/merge\b", cmd):
        seg = next((s for s in re.split(r"[|;&]+", cmd) if re.search(r"\bgh\b.*merge", s)), cmd)
        want = re.search(r"\bOWNER_MERGE=(\d+)\b", cmd)
        m = re.search(r"\bmerge\s+(?:-\S+\s+)*(\d+)\b", seg) or re.search(r"/pulls/(\d+)/merge\b", seg)
        pr = m.group(1) if m else None
        if not want:
            block("no session merges a PR by hand: `scripts/session.sh close <session> … --merge` is the "
                  "path, and the merge policy it enforces is the point of it (WORKFLOW.md §6.3, §7). Once "
                  "the owner has said to merge this PR, in so many words, prefix the command with "
                  "OWNER_MERGE=<pr> naming that same PR.")
        if pr is None:
            block("a merge names its PR: OWNER_MERGE=<pr> is a go-ahead for one PR, so say which one "
                  "(`gh pr merge <pr> --merge`) rather than merging whatever PR this branch has.")
        if pr != want.group(1):
            block(f"OWNER_MERGE={want.group(1)} does not name PR #{pr}: a go-ahead is per PR (WORKFLOW.md "
                  "§7). Merge the PR the owner named, or ask them about this one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
