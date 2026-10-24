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

"""Check the planning files against the rules of PLANNING/WORKFLOW.md (§9).

Run it before every PR that touches PLANNING/ (standard library only):

    python3 PLANNING/check_planning.py          # the rules; exit 1 on an ERROR
    python3 PLANNING/check_planning.py --live   # also compare the queue with GitHub's open PRs

Every finding names its rule: S = the session sequence, I = the index, D = the decisions registry,
L = live (warnings only).
Installed by agent-session-kit; its docs/checker.md explains each rule and why it exists.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

PLANNING = Path(__file__).resolve().parent
SEQUENCE = "TODO_session_sequence.md"
INDEX = "TODO_INDEX.md"
SYSTEM_FILES = {SEQUENCE, INDEX}

DONE, RUNNING, NEXT, LATER, WAITING = "✅", "▶", "⏭", "⬜", "⏸"
OPEN_ENDS, DEFERRED, DROPPED = "◐", "💤", "🚫"
MARKS = {DONE, RUNNING, NEXT, LATER, WAITING, OPEN_ENDS, DEFERRED, DROPPED}
PASTABLE = {RUNNING, NEXT, LATER}            # someone will still paste these: they need a prompt
CLOSED = {DONE, OPEN_ENDS, DROPPED}          # the session is over: its prompt has left the file
DATED = CLOSED | {DEFERRED}
WHO_NEEDED = {RUNNING, DONE, OPEN_ENDS}      # in a table with a Who column, these rows say whose they are

MAX_QUEUE_LINE = 1200
DEFAULT_RUNNING_PER_SLOT = 1
SLOT_OWNER_LIMIT = re.compile(r"Slot (\d+) runs (\d+) sessions at once \(owner, \d{4}-\d\d-\d\d")

DATE = re.compile(r"\b20\d\d-\d\d-\d\d\b")
# A ⏸ row's due date: the date right after "Waits on", "by" or "until". Other dates in the row
# (when an upstream issue was filed) are not the wait's due date, and L5 must not read them.
WAIT_DUE = re.compile(r"\b(?:waits on|by|until)\b[\s:*_]*(20\d\d-\d\d-\d\d)\b", re.IGNORECASE)
SESSION = re.compile(r"`([^`]+)`")
PROMPT_HEADING = re.compile(r"^### (\d+\.\d+[a-z]?) `([^`]+)`(.*)$")
SECTION_HEADING = re.compile(r"^#{2,3} (\d+(?:\.\d+[a-z]?)?)[.\s]")
SECTION_REF = re.compile(r"(?:TODO_session_sequence\.md|the queue's) §(\d+(?:\.\d+[a-z]?)?)")
TODO_FILE = re.compile(r"\bTODO_[A-Za-z0-9_.-]+?\.md\b")
PR_REF = re.compile(r"(?<![\w/])#(\d{1,6})\b")

# Decisions: PLANNING/DECISIONS.md (the index) and PLANNING/decisions/D-<nnn>_<slug>.md (rules D1–D4).
DECISIONS = "DECISIONS.md"
DECISIONS_DIR = "decisions"
DECISION_ID = re.compile(r"\bD-\d{3,}\b")
DECISION_FILE = re.compile(r"^(D-\d{3,})_[A-Za-z0-9][A-Za-z0-9._-]*\.md$")
DECISION_STATUS = re.compile(r"^(proposed|accepted|rejected|superseded by (D-\d{3,}))$")
DECISION_REQUIRED = ("id", "date", "status", "decided-by")
BINDING = "accepted"                 # the one status a ⏭, ▶ or ⬜ row, or its prompt, may cite
# D4, the enforce lint: an accepted record's `enforce: <regex> in <path prefix or glob>` lines are run over
# the project's files (git ls-files, so ignored files and build output never enter it); PLANNING/ is skipped.
ENFORCE = re.compile(r"^(?P<rx>.+?)\s+in\s+(?P<scope>\S+)$")
LINT_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
MAX_LINT_BYTES = 1_000_000

# The short prompt form: the build-session skill carries the worktree, the claim, the memory step and
# the close; the prompt itself only has to invoke it with its own session name (S11).
SHORT_FORM = re.compile(r"^\s*/build-session\s+`?([^\s`]+)`?[ \t]*$", re.M)

# Rulebook section references (S17): "WORKFLOW.md §N" anywhere, and a bare "§N" inside the rulebook
# itself; "the queue's §N" and "TODO_session_sequence.md §N" are S15's.
RULEBOOK = "WORKFLOW.md"
RULEBOOK_HEADING = re.compile(r"^(?:## (\d+)\.|### (\d+\.\d+)\b)")
RULEBOOK_REF = re.compile(r"WORKFLOW\.md[^\n§]{0,12}§(\d+(?:\.\d+)?)(?:\s*[–-]\s*§(\d+(?:\.\d+)?))?")
BARE_REF = re.compile(r"(?<!queue's )(?<!sequence\.md )§(\d+(?:\.\d+)?)")

PROMPT_MUST_HAVE = {
    "the worktree command": re.compile(r"git worktree add"),
    "the claim PR (\"Claim first: a PR that only sets your row … to ▶\")":
        re.compile(r"Claim first: a PR that only sets your row[^\n]*" + RUNNING),
    "the memory step": re.compile(r"memory", re.IGNORECASE),
    "the close by the queue's §6.1": re.compile(r"§6\.1"),
}


@dataclass(frozen=True)
class Finding:
    rule: str
    message: str
    level: str = "ERROR"

    def __str__(self) -> str:
        return f"{self.level} [{self.rule}] {self.message}"


@dataclass
class Row:
    table: str          # "Slot 1", "Beside the queue"
    mark: str
    session: str
    text: str
    line: int
    who: str | None = None   # the Who cell; None when the table has no Who column


@dataclass
class Prompt:
    number: str
    session: str
    has_block: bool
    body: str


@dataclass
class Decision:
    id: str
    file: str
    status: str                # the whole value: "accepted", "superseded by D-004", …
    fields: dict[str, str]


# ---------------------------------------------------------------------------- parsing

def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_separator(line: str) -> bool:
    return bool(re.fullmatch(r"\|?[\s:|-]+\|?", line.strip())) and "-" in line


def sections(text: str, level: str = "## ") -> dict[str, tuple[int, str]]:
    """Heading text -> (line number of the heading, body until the next heading of that level)."""
    out: dict[str, tuple[int, str]] = {}
    lines = text.splitlines()
    starts = [i for i, l in enumerate(lines) if l.startswith(level)]
    for k, i in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(lines)
        out[lines[i][len(level):].strip()] = (i + 1, "\n".join(lines[i + 1:end]))
    return out


def _section(text: str, prefix: str, level: str = "## ") -> tuple[int, str] | None:
    for title, val in sections(text, level).items():
        if title.startswith(prefix):
            return val
    return None


def table_rows(body: str, first_line: int) -> list[tuple[int, list[str], str]]:
    """Data rows of the first table in body: (line number, cells, raw line). Header and separator skipped."""
    rows, seen_header = [], False
    for i, line in enumerate(body.splitlines()):
        if not line.lstrip().startswith("|"):
            continue
        if _is_separator(line):
            continue
        if not seen_header:
            seen_header = True
            continue
        rows.append((first_line + i + 1, _cells(line), line))
    return rows


def table_header(body: str) -> list[str]:
    """The header cells of the first table in body, or [] when there is no table."""
    for line in body.splitlines():
        if line.lstrip().startswith("|") and not _is_separator(line):
            return _cells(line)
    return []


def parse_queue(text: str) -> tuple[list[Row], dict[str, int], list[str], str]:
    """Rows, slot name -> allowed ▶ count, the Open ends rows (raw), and the §1 text."""
    q = _section(text, "1.")
    if q is None:
        return [], {}, [], ""
    q_line, q_body = q
    rows: list[Row] = []
    slots: dict[str, int] = {}
    open_ends: list[str] = []
    for title, (line, body) in sections(q_body, "### ").items():
        start = q_line + line
        if title.startswith("Slot"):
            name = re.match(r"Slot \d+", title)
            name = name.group(0) if name else title
            slots[name] = DEFAULT_RUNNING_PER_SLOT
            table = name
        elif title.startswith("Beside the queue"):
            table = "Beside the queue"
        elif title.startswith("Open ends"):
            open_ends = [raw for _, _, raw in table_rows(body, start)]
            continue
        else:
            continue
        hdr = [h.lower() for h in table_header(body)]
        who_idx = hdr.index("who") if "who" in hdr else -1
        for n, cells, raw in table_rows(body, start):
            if not any(cells):
                continue
            m = SESSION.search(cells[1]) if len(cells) > 1 else None
            who = None if who_idx < 0 else (cells[who_idx] if who_idx < len(cells) else "")
            rows.append(Row(table, cells[0], m.group(1) if m else "", raw, n, who))
    for slot, limit in SLOT_OWNER_LIMIT.findall(q_body):
        key = f"Slot {slot}"
        if key in slots:
            slots[key] = int(limit)
    return rows, slots, open_ends, q_body


def parse_prompts(text: str) -> list[Prompt]:
    p = _section(text, "2.")
    if p is None:
        return []
    prompts: list[Prompt] = []
    lines = p[1].splitlines()
    heads = [i for i, l in enumerate(lines) if l.startswith("### ")]
    for k, i in enumerate(heads):
        m = PROMPT_HEADING.match(lines[i])
        if not m:
            continue
        end = heads[k + 1] if k + 1 < len(heads) else len(lines)
        body = "\n".join(lines[i + 1:end])
        block = re.search(r"```text\n(.*?)```", body, re.S)
        prompts.append(Prompt(m.group(1), m.group(2), bool(block), block.group(1) if block else ""))
    return prompts


# ---------------------------------------------------------------------------- the rules

def check_sequence(text: str, planning: Path) -> list[Finding]:
    f: list[Finding] = []
    rows, slots, open_ends, q_body = parse_queue(text)
    if _section(text, "1.") is None:
        return [Finding("S0", f"{SEQUENCE} has no '## 1. The queue' section")]
    q_titles = list(sections(q_body, "### "))
    if not any(t.startswith("State") for t in q_titles):
        f.append(Finding("S0", "§1 has no '### State' table"))
    if not slots:
        f.append(Finding("S0", "§1 has no '### Slot <n>' table"))

    prompts = parse_prompts(text)
    with_block = {p.session: p for p in prompts if p.has_block}

    seen: dict[str, int] = {}
    for r in rows:
        where = f"line {r.line} ({r.table})"
        if r.mark not in MARKS:
            f.append(Finding("S1", f"{where}: unknown mark {r.mark!r}"))
        if not r.session:
            f.append(Finding("S2", f"{where}: no session name in backticks"))
            continue
        if r.session in seen:
            f.append(Finding("S2", f"{where}: `{r.session}` already has a row (line {seen[r.session]})"))
        seen.setdefault(r.session, r.line)
        if r.table != "Beside the queue" and r.mark in PASTABLE and r.session not in with_block:
            f.append(Finding("S5", f"{where}: `{r.session}` is {r.mark} but has no prompt in §2"))
        if r.mark == WAITING and "waits on" not in r.text.lower():
            f.append(Finding("S6", f"{where}: `{r.session}` is ⏸ but does not say what it waits on"))
        if r.mark in DATED and not DATE.search(r.text):
            f.append(Finding("S7", f"{where}: `{r.session}` is {r.mark} but carries no date"))
        if r.mark in CLOSED and r.session in with_block:
            f.append(Finding("S8", f"{where}: `{r.session}` is closed but its prompt is still in §2"))
        if r.mark == OPEN_ENDS and not any(r.session in oe for oe in open_ends):
            f.append(Finding("S9", f"{where}: `{r.session}` is ◐ but no line of Open ends names it"))
        if r.who is not None and r.mark in WHO_NEEDED and not r.who:
            f.append(Finding("S16", f"{where}: `{r.session}` is {r.mark} but its Who cell is empty"))

    for slot, limit in slots.items():
        in_slot = [r for r in rows if r.table == slot]
        nxt = [r.session for r in in_slot if r.mark == NEXT]
        if len(nxt) > 1:
            f.append(Finding("S3", f"{slot} has {len(nxt)} ⏭ rows: {', '.join(nxt)}"))
        run = [r.session for r in in_slot if r.mark == RUNNING]
        if len(run) > limit:
            f.append(Finding("S4", f"{slot} has {len(run)} ▶ rows (allowed {limit}): {', '.join(run)}"))

    for p in prompts:
        if not p.has_block:
            continue
        if p.session not in seen:
            f.append(Finding("S10", f"§{p.number} `{p.session}` has a prompt but no row in §1"))
        short = SHORT_FORM.search(p.body)
        if short and short.group(1) == p.session:
            pass                      # /build-session <session>: the skill carries the invariant part
        else:
            for what, rx in PROMPT_MUST_HAVE.items():
                if not rx.search(p.body):
                    f.append(Finding("S11", f"§{p.number} `{p.session}`: the prompt lacks {what}"))
        if p.session not in p.body:
            f.append(Finding("S11", f"§{p.number} `{p.session}`: the prompt does not name its own session"))

    for raw in open_ends:
        cells = _cells(raw)
        if len(cells) < 4 or not all(cells[:4]):
            f.append(Finding("S12", f"Open ends row lacks Due, What, From or Closes when: {raw[:80]}"))

    q = _section(text, "1.")
    assert q is not None
    for i, line in enumerate(q[1].splitlines()):
        if len(line) > MAX_QUEUE_LINE:
            f.append(Finding("S13", f"line {q[0] + i + 1} of §1 is {len(line)} characters (max {MAX_QUEUE_LINE})"))
    for name in sorted(set(TODO_FILE.findall(q[1]))):
        if not (planning / name).exists():
            f.append(Finding("S14", f"§1 names {name}, which is not in PLANNING/"))

    headings = {m.group(1) for l in text.splitlines() if (m := SECTION_HEADING.match(l))}
    for path in sorted(planning.glob("*.md")):
        for ref in sorted(set(SECTION_REF.findall(path.read_text(encoding="utf-8")))):
            if ref not in headings:
                f.append(Finding("S15", f"{path.name} cites {SEQUENCE} §{ref}, which has no heading"))
    return f


STRUCK = re.compile(r"~~.*?~~", re.S)
QUOTED = re.compile(r'"[^"\n]*"|“[^”\n]*”|`[^`\n]*`')
CLOSED_WORD = re.compile(r"\b(SUPERSEDED|RETIRED|ABSORBED)\b")


def banner(text: str) -> str:
    head = text.split("\n## ", 1)[0]
    return QUOTED.sub("", STRUCK.sub("", head))


def check_index(planning: Path) -> list[Finding]:
    f: list[Finding] = []
    index_path = planning / INDEX
    index = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
    if not index:
        f.append(Finding("I1", f"{INDEX} is missing"))
    linked = set(re.findall(r"\]\(([^)#\s]+\.md)", index))
    for name in sorted(linked):
        if not (planning / name).exists():
            f.append(Finding("I2", f"{INDEX} links {name}, which is not on disk"))
    for path in sorted(planning.glob("TODO_*.md")):
        if path.name in SYSTEM_FILES:
            continue
        if path.name not in linked:
            f.append(Finding("I1", f"{path.name} is an open plan with no link in {INDEX}"))
        closed = planning / path.name[len("TODO_"):]
        if closed.exists():
            f.append(Finding("I3", f"{path.name} and {closed.name} are both on disk"))
        m = CLOSED_WORD.search(banner(path.read_text(encoding="utf-8")))
        if m:
            f.append(Finding("I4", f"{path.name}'s banner says {m.group(1)}: close it (WORKFLOW.md §5.3)"))
    return f


# ---------------------------------------------------------------------------- decisions

def front_matter(text: str) -> dict[str, str] | None:
    """The `key: value` lines between the leading --- markers (keys lower-cased, trailing # comments
    dropped), or None when the file has no closed front-matter block."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    out: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return out
        if ":" in line and not line.startswith((" ", "\t", "#")):
            k, v = line.split(":", 1)
            k, v = k.strip().lower(), re.sub(r"\s+#.*$", "", v).strip()
            out[k] = out[k] + "\n" + v if k in out else v      # a repeated key (enforce) keeps every line
    return None


def parse_decisions(planning: Path) -> tuple[dict[str, Decision], list[Finding], bool]:
    """The records in decisions/ by id, the D1/D2 findings about them and the index, and whether a
    registry exists at all (a project installed before the registry has none, and nothing to check)."""
    f: list[Finding] = []
    ddir = planning / DECISIONS_DIR
    files = sorted(p for p in ddir.glob("*.md") if p.name != "README.md") if ddir.is_dir() else []
    index_path = planning / DECISIONS
    if not files and not index_path.exists():
        return {}, [], False
    decisions: dict[str, Decision] = {}
    for path in files:
        where = f"{DECISIONS_DIR}/{path.name}"
        m = DECISION_FILE.match(path.name)
        if not m:
            f.append(Finding("D1", f"{where} is not named D-<nnn>_<slug>.md"))
            continue
        fid = m.group(1)
        fm = front_matter(path.read_text(encoding="utf-8"))
        if fm is None:
            f.append(Finding("D2", f"{where} has no front matter block (--- … ---)"))
            fm = {}
        missing = [k for k in DECISION_REQUIRED if not fm.get(k)]
        if missing:
            f.append(Finding("D2", f"{where}: front matter lacks {', '.join(missing)}"))
        if fm.get("id") and fm["id"] != fid:
            f.append(Finding("D1", f"{where}: id {fm['id']} is not the file's {fid}"))
        status = fm.get("status", "")
        if status and not DECISION_STATUS.match(status):
            f.append(Finding("D2", f"{where}: unknown status {status!r} "
                             "(proposed, accepted, rejected, superseded by D-<nnn>)"))
        if fm.get("date") and not re.fullmatch(r"20\d\d-\d\d-\d\d", fm["date"]):
            f.append(Finding("D2", f"{where}: date {fm['date']!r} is not YYYY-MM-DD"))
        if fid in decisions:
            f.append(Finding("D1", f"{where}: {fid} is also {DECISIONS_DIR}/{decisions[fid].file}"))
            continue
        decisions[fid] = Decision(fid, path.name, status, fm)
    for d in decisions.values():
        refs = [("supersedes", r) for r in DECISION_ID.findall(d.fields.get("supersedes", ""))]
        m = DECISION_STATUS.match(d.status)
        if m and m.group(2):
            refs.append(("is superseded by", m.group(2)))
        for what, ref in refs:
            if ref not in decisions:
                f.append(Finding("D2", f"{DECISIONS_DIR}/{d.file} {what} {ref}, which is not in {DECISIONS_DIR}/"))
    index = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
    if not index_path.exists():
        f.append(Finding("D1", f"{DECISIONS} is missing, but {DECISIONS_DIR}/ holds records"))
    indexed: dict[str, int] = {}
    for n, cells, raw in table_rows(index, 0):
        if not any(cells):
            continue
        m = DECISION_ID.search(cells[0])
        if not m:
            f.append(Finding("D1", f"{DECISIONS} line {n}: the first cell names no D-<nnn>"))
            continue
        did = m.group(0)
        if did in indexed:
            f.append(Finding("D1", f"{DECISIONS} line {n}: {did} already has a row (line {indexed[did]})"))
            continue
        indexed[did] = n
        d = decisions.get(did)
        if d is None:
            f.append(Finding("D1", f"{DECISIONS} line {n}: {did} has no record in {DECISIONS_DIR}/"))
            continue
        if len(cells) > 1 and d.status and cells[1] != d.status:
            f.append(Finding("D2", f"{DECISIONS} line {n}: {did} says {cells[1]!r}, its record says {d.status!r}"))
        if d.file not in raw:
            f.append(Finding("D1", f"{DECISIONS} line {n}: {did} does not link {DECISIONS_DIR}/{d.file}"))
    for did, d in decisions.items():
        if did not in indexed:
            f.append(Finding("D1", f"{DECISIONS_DIR}/{d.file} has no row in {DECISIONS}"))
    return decisions, f, True


def _scope_regex(scope: str) -> re.Pattern:
    """A path prefix (`src/`) or a glob (`src/**/*.py`, `*` within one segment) as a regex on posix paths."""
    if not any(ch in scope for ch in "*?["):
        return re.compile("^" + re.escape(scope))
    out, i = "", 0
    while i < len(scope):
        if scope.startswith("**/", i):
            out, i = out + r"(?:.*/)?", i + 3
        elif scope.startswith("**", i):
            out, i = out + r".*", i + 2
        elif scope[i] == "*":
            out, i = out + r"[^/]*", i + 1
        elif scope[i] == "?":
            out, i = out + r"[^/]", i + 1
        else:
            out, i = out + re.escape(scope[i]), i + 1
    return re.compile("^" + out + "$")


def project_files(root: Path) -> list[Path]:
    """The project's files: git's tracked and untracked-but-not-ignored ones; a plain walk outside git."""
    try:
        out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                             cwd=root, capture_output=True, text=True, timeout=60)
        if out.returncode == 0:
            return [root / name for name in out.stdout.split("\0") if name]
    except (OSError, subprocess.TimeoutExpired):
        pass
    files = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and not any(part in LINT_SKIP_DIRS for part in p.relative_to(root).parts):
            files.append(p)
    return files


def check_enforce(planning: Path, decisions: dict[str, Decision]) -> list[Finding]:
    """D4 (and D2 for a bad line): the enforce lines of accepted records, run over the project's files."""
    f: list[Finding] = []
    rules = []
    for d in decisions.values():
        for line in [l.strip() for l in d.fields.get("enforce", "").split("\n") if l.strip()]:
            m = ENFORCE.match(line)
            if not m:
                f.append(Finding("D2", f"{DECISIONS_DIR}/{d.file}: enforce needs '<regex> in <path prefix or glob>', "
                                 f"got {line!r}"))
                continue
            rx_text = m.group("rx").strip().strip("'\"")
            try:
                rx = re.compile(rx_text, re.M)
            except re.error as e:
                f.append(Finding("D2", f"{DECISIONS_DIR}/{d.file}: enforce regex {rx_text!r} does not compile: {e}"))
                continue
            if d.status == BINDING:
                rules.append((d, rx, rx_text, _scope_regex(m.group("scope")), m.group("scope")))
    if not rules:
        return f
    root = planning.parent
    for path in project_files(root):
        rel = path.relative_to(root).as_posix()
        if rel.split("/")[0] in LINT_SKIP_DIRS or rel.startswith(planning.name + "/"):
            continue
        applicable = [r for r in rules if r[3].match(rel)]
        if not applicable:
            continue
        try:
            if path.stat().st_size > MAX_LINT_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for d, rx, rx_text, _, scope in applicable:
            m = rx.search(text)
            if m:
                line = text.count("\n", 0, m.start()) + 1
                f.append(Finding("D4", f"{rel}:{line} matches `{rx_text}` in {scope}, which {d.id} forbids"))
    return f


def check_decisions(planning: Path, sequence_text: str = "") -> list[Finding]:
    """D1–D4: the registry is consistent, what will still be pasted cites only accepted records, and
    the accepted records' enforce lines hold over the project's files."""
    decisions, f, present = parse_decisions(planning)
    if not present:
        return []
    f += check_enforce(planning, decisions)
    rows, _, _, _ = parse_queue(sequence_text)
    prompts = {p.session: p for p in parse_prompts(sequence_text) if p.has_block}

    def state(did: str) -> str:
        return decisions[did].status if did in decisions else "not a record"

    for r in rows:
        if r.mark not in PASTABLE or not r.session:
            continue
        cited = set(DECISION_ID.findall(r.text))
        if r.session in prompts:
            cited |= set(DECISION_ID.findall(prompts[r.session].body))
        for did in sorted(cited):
            if state(did) != BINDING:
                f.append(Finding("D3", f"line {r.line} ({r.table}): `{r.session}` is {r.mark} and its row or "
                                 f"prompt cites {did}, which is {state(did)}: only an accepted record binds"))
    return f


def check_rulebook(planning: Path) -> list[Finding]:
    """S17: every WORKFLOW.md §N cited in PLANNING/, CLAUDE.md or the skills, and every bare §N inside
    the rulebook, names a heading that exists."""
    f: list[Finding] = []
    rulebook = planning / RULEBOOK
    if not rulebook.exists():
        return f
    heads: set[str] = set()
    for line in rulebook.read_text(encoding="utf-8").splitlines():
        m = RULEBOOK_HEADING.match(line)
        if m:
            heads.add(m.group(1) or m.group(2))
    root = planning.parent
    files = sorted(planning.glob("*.md")) + [root / "CLAUDE.md"] + sorted((root / ".claude" / "skills").glob("*/SKILL.md"))
    for path in files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        refs: set[str] = set()
        for m in RULEBOOK_REF.finditer(text):
            refs.add(m.group(1))
            if m.group(2):
                refs.add(m.group(2))
        if path.name == RULEBOOK:
            refs |= {m.group(1) for m in BARE_REF.finditer(text)}
        for ref in sorted(refs - heads):
            where = path.relative_to(root) if root in path.parents else path.name
            f.append(Finding("S17", f"{where} cites {RULEBOOK} §{ref}, which has no heading"))
    return f


def check(planning: Path = PLANNING) -> list[Finding]:
    seq = planning / SEQUENCE
    if not seq.exists():
        return [Finding("S0", f"{SEQUENCE} is missing")]
    text = seq.read_text(encoding="utf-8")
    return (check_sequence(text, planning) + check_index(planning) + check_decisions(planning, text)
            + check_rulebook(planning))


# ---------------------------------------------------------------------------- live (warnings)

def _gh(args: list[str], cwd: Path):
    out = subprocess.run(["gh", *args], cwd=cwd, capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "gh failed")
    return json.loads(out.stdout or "null")


def open_prs(cwd: Path) -> list[dict] | None:
    try:
        return _gh(["pr", "list", "--state", "open", "--limit", "300", "--json", "number,title,headRefName"], cwd)
    except Exception:
        pass
    try:  # GraphQL refused (some cloud sessions): the REST API
        prs = _gh(["api", "repos/{owner}/{repo}/pulls?state=open&per_page=100"], cwd)
        return [{"number": p["number"], "title": p["title"], "headRefName": p["head"]["ref"]} for p in prs]
    except Exception:
        return None


def belongs(pr: dict, session: str) -> bool:
    ref = pr.get("headRefName", "")
    return ref == session or ref.endswith("/" + session) or pr.get("title", "").startswith(f"[{session}]")


def pr_state(number: str, cwd: Path) -> str:
    try:
        return _gh(["pr", "view", number, "--json", "state"], cwd)["state"]
    except Exception:
        return ""


def check_live(planning: Path = PLANNING, prs: list[dict] | None = None,
               today: dt.date | None = None, state_of=None) -> list[Finding]:
    today = today or dt.date.today()
    text = (planning / SEQUENCE).read_text(encoding="utf-8")
    rows, _, open_ends, _ = parse_queue(text)
    f: list[Finding] = []
    if prs is None:
        prs = open_prs(planning)
    state_of = state_of or (lambda n: pr_state(n, planning))
    if prs is None:
        f.append(Finding("L0", "GitHub could not be asked (gh missing or not logged in): L1–L4 skipped", "WARN"))
    else:
        for r in rows:
            if not r.session:
                continue
            mine = [p for p in prs if belongs(p, r.session)]
            nums = ", ".join(f"#{p['number']}" for p in mine)
            if r.mark in {NEXT, LATER, WAITING, DEFERRED} and mine:
                f.append(Finding("L1", f"`{r.session}` is {r.mark} but has open PRs ({nums}): running unclaimed?", "WARN"))
            if r.mark in CLOSED and mine:
                f.append(Finding("L2", f"`{r.session}` is closed but has open PRs ({nums})", "WARN"))
            if r.mark == RUNNING and not mine:
                f.append(Finding("L3", f"`{r.session}` is ▶ with no open PR: between PRs, or stopped early", "WARN"))
            if r.mark == WAITING:
                for n in PR_REF.findall(r.text):
                    if state_of(n) == "MERGED":
                        f.append(Finding("L4", f"`{r.session}` waits on #{n}, which has merged", "WARN"))
    for r in rows:
        if r.mark == WAITING:
            due = [d for d in WAIT_DUE.findall(r.text) if dt.date.fromisoformat(d) <= today]
            if due:
                f.append(Finding("L5", f"`{r.session}` is ⏸ with a wait due {due[-1]}, which has come: is the wait met?", "WARN"))
    for raw in open_ends:
        cells = _cells(raw)
        m = DATE.search(cells[0]) if cells else None
        if m and dt.date.fromisoformat(m.group(0)) <= today:
            f.append(Finding("L6", f"open end due {m.group(0)}: {cells[1][:70] if len(cells) > 1 else ''}", "WARN"))
    return f


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true", help="also compare the queue with GitHub's open PRs")
    ap.add_argument("--planning", type=Path, default=PLANNING, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    findings = check(a.planning)
    if a.live and not any(x.rule == "S0" for x in findings):
        findings += check_live(a.planning)
    for x in findings:
        print(x)
    errors = sum(1 for x in findings if x.level == "ERROR")
    warns = len(findings) - errors
    print(f"check_planning: {errors} error(s), {warns} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
