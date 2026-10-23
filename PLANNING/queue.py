#!/usr/bin/env python3
"""Edit PLANNING/TODO_session_sequence.md the way WORKFLOW.md §6 says, instead of editing a row by hand.

    python3 PLANNING/queue.py next [--slot N] [--paste]   what each slot runs next, and whether it is free
    python3 PLANNING/queue.py prompt <session>            the prompt block to paste, verbatim
    python3 PLANNING/queue.py row <session>               the session's row and its table
    python3 PLANNING/queue.py claim <session> [--who <handle>] [--date YYYY-MM-DD]
                                              [--beside --work "<what>"]
    python3 PLANNING/queue.py close <session> --mark done|open-ends --prs "#12, #13" --verified "…"
                                              [--shipped "…"] --note <memory note file>
                                              [--open-end "<due> | <what> | <closes when>"]…
                                              [--next <session>] [--date YYYY-MM-DD] [--force]

claim: the row becomes ▶ with "started <date>" and, where the table has a Who column, the handle
(default: `gh api user -q .login`, else git's user.name); if the row was ⏭, ⏭ moves to the first ⬜
row below it. A session with no row claims with --beside --work: a ▶ row is added under *Beside the
queue*. A row already ▶ under another name is refused: that is the race of §6.1, and the second
session stops.

close: the row becomes ✅ (done) or ◐ (open-ends) with the receipts (date · PRs · verified · shipped
as · memory note); each --open-end becomes a row of *Open ends* from this session; the slot gets a ⏭
if it has none (--next names the row, else the first ⬜ below); the session's prompt block leaves §2
and its heading is marked closed; order rules about the session are deleted. The State table, later
prompts, the next prompt when the slot runs dry, the plan's banner and the memory note stay the
session's own work.

Every edit is followed by the checker and exits 1 on an error it reports. The file is parsed with
check_planning.py's own parser, so an edit made here is one the checker accepts. scripts/session.sh
wraps claim and close with the git and gh steps.

This file shares its name with the standard library's queue module; it never imports that module,
and it keeps its own directory at the end of sys.path so nothing else resolves to it by mistake.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

PLANNING = Path(__file__).resolve().parent
if sys.path and Path(sys.path[0] or ".").resolve() == PLANNING:
    sys.path.pop(0)
sys.path.append(str(PLANNING))
import check_planning as cp  # noqa: E402

MARK = {"done": cp.DONE, "open-ends": cp.OPEN_ENDS}
COLUMNS = ("mark", "session", "who", "work", "prompt", "receipt")   # header words, matched by prefix


class QueueError(Exception):
    pass


def today() -> str:
    return dt.date.today().isoformat()


def whoami() -> str:
    for cmd in (["gh", "api", "user", "-q", ".login"], ["git", "config", "user.name"]):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    raise QueueError("--who <handle> is needed: gh is not logged in here and git has no user.name")


# ---------------------------------------------------------------------------- the file as lines

class Queue:
    """The queue file as lines, with edits by row and by table; parsing is the checker's."""

    def __init__(self, planning: Path):
        self.planning = planning
        self.path = planning / cp.SEQUENCE
        if not self.path.exists():
            raise QueueError(f"{self.path} is missing")
        self.lines = self.path.read_text(encoding="utf-8").split("\n")

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def save(self) -> None:
        self.path.write_text(self.text, encoding="utf-8")

    def rows(self) -> list[cp.Row]:
        return cp.parse_queue(self.text)[0]

    def slots(self) -> dict[str, int]:
        return cp.parse_queue(self.text)[1]

    def row(self, session: str) -> cp.Row | None:
        return next((r for r in self.rows() if r.session == session), None)

    def prompt(self, session: str) -> cp.Prompt | None:
        return next((p for p in cp.parse_prompts(self.text) if p.session == session and p.has_block), None)

    # tables -----------------------------------------------------------------

    @staticmethod
    def _col(hdr: list[str], key: str) -> int | None:
        for i, h in enumerate(hdr):
            if h == key or h.startswith(key):
                return i
        return None

    def header_of(self, line: int) -> list[str]:
        """Header cells (lower-cased) of the table that holds the 1-based line."""
        i = line - 1
        while i > 0 and self.lines[i - 1].lstrip().startswith("|"):
            i -= 1
        return [h.lower() for h in cp._cells(self.lines[i])]

    def cell(self, line: int, key: str) -> str | None:
        idx = self._col(self.header_of(line), key)
        if idx is None:
            return None
        cells = cp._cells(self.lines[line - 1])
        return cells[idx] if idx < len(cells) else ""

    def set_cells(self, line: int, **changes: str) -> None:
        hdr = self.header_of(line)
        cells = cp._cells(self.lines[line - 1])
        while len(cells) < len(hdr):
            cells.append("")
        for key, value in changes.items():
            idx = self._col(hdr, key)
            if idx is not None:
                cells[idx] = value
        self.lines[line - 1] = "| " + " | ".join(cells) + " |"

    def section(self, prefix: str, level: str = "## ") -> tuple[int, int]:
        """(start, end) line indexes of the section whose heading text starts with prefix; end exclusive,
        at the next heading of the same or a higher level."""
        for i, l in enumerate(self.lines):
            if l.startswith(level) and l[len(level):].strip().startswith(prefix):
                end = len(self.lines)
                for j in range(i + 1, len(self.lines)):
                    if self.lines[j].startswith("## ") or (level == "### " and self.lines[j].startswith("### ")):
                        end = j
                        break
                return i, end
        raise QueueError(f"no '{level}{prefix}…' heading in {cp.SEQUENCE}")

    def append_row(self, prefix: str, values: dict[str, str]) -> int:
        """Add a row to the first table under the '### <prefix>…' heading, cells placed by header."""
        s, e = self.section(prefix, "### ")
        i = s + 1
        while i < e and not self.lines[i].lstrip().startswith("|"):
            i += 1
        if i >= e:
            raise QueueError(f"no table under '### {prefix}'")
        hdr = [h.lower() for h in cp._cells(self.lines[i])]
        cells = []
        for h in hdr:
            key = next((k for k in COLUMNS if h == k or h.startswith(k)), None)
            cells.append(values.get(key or h, values.get(h, "")))
        while i < e and self.lines[i].lstrip().startswith("|"):
            i += 1
        self.lines.insert(i, "| " + " | ".join(cells) + " |")
        return i + 1

    # §2 and the order rules -------------------------------------------------

    def close_prompt(self, session: str, date: str) -> str | None:
        """Remove the session's prompt block and mark its heading closed; the heading's number, or None."""
        s, e = self.section("2.")
        rx = re.compile(r"^### (\d+\.\d+[a-z]?) `" + re.escape(session) + r"`\s*$")
        for i in range(s, e):
            m = rx.match(self.lines[i])
            if m:
                j = i + 1
                while j < e and not self.lines[j].startswith("### "):
                    j += 1
                self.lines[i:j] = [f"### {m.group(1)} `{session}` (closed {date}; its prompt is in git history)", ""]
                return m.group(1)
        return None

    def drop_order_rules(self, session: str) -> int:
        """Delete the order rules that name the session; how many went."""
        s, e = self.section("1.")
        for i in range(s, e):
            if self.lines[i].lstrip().startswith("**") and "Order rules" in self.lines[i]:
                j = i + 1
                while j < e and not self.lines[j].strip():
                    j += 1
                k = j
                while k < e and self.lines[k].lstrip().startswith("- "):
                    k += 1
                items = self.lines[j:k]
                keep = [l for l in items if f"`{session}`" not in l]
                if len(keep) == len(items):
                    return 0
                self.lines[j:k] = keep or ["- none yet"]
                return len(items) - len(keep)
        return 0


# ---------------------------------------------------------------------------- the commands

def claim(planning: Path, session: str, who: str | None = None, date: str | None = None,
          beside: bool = False, work: str | None = None) -> str:
    q = Queue(planning)
    date = date or today()
    r = q.row(session)
    if r is None:
        if not beside:
            raise QueueError(f"`{session}` has no row in §1. A side session claims with --beside --work \"<what>\"")
        who = who or whoami()
        q.append_row("Beside the queue", {"mark": cp.RUNNING, "session": f"`{session}`", "who": who,
                                          "work": work or "", "prompt": "—", "receipt": f"started {date}"})
        q.save()
        return f"registered `{session}` ▶ under Beside the queue, started {date}, Who {who}"
    if r.mark == cp.RUNNING:
        who = who or (r.who if r.who else whoami())
        if r.who and r.who != who:
            raise QueueError(f"`{session}` is already ▶, claimed by {r.who} (line {r.line}): the slot is taken, "
                             "stop and report (§6.1, two people, one prompt)")
        return f"`{session}` is already ▶ (line {r.line}): nothing to do"
    if r.mark not in {cp.NEXT, cp.LATER}:
        raise QueueError(f"`{session}` is {r.mark} (line {r.line}): only a ⏭ or ⬜ row can be claimed")
    who = who or whoami()
    old = (q.cell(r.line, "receipt") or "").strip()
    receipt = f"started {date}" + (f" · {old}" if old and old != "—" else "")
    q.set_cells(r.line, mark=cp.RUNNING, who=who, receipt=receipt)
    msg = f"claimed `{session}` ▶ started {date}" + (f", Who {who}" if r.who is not None else "")
    if r.mark == cp.NEXT:
        below = [x for x in q.rows() if x.table == r.table and x.line > r.line and x.mark == cp.LATER]
        if below:
            q.set_cells(below[0].line, mark=cp.NEXT)
            msg += f"; ⏭ moved to `{below[0].session}`"
        else:
            msg += f"; no ⬜ row below it: {r.table} has no ⏭ now"
    q.save()
    return msg


def close(planning: Path, session: str, mark: str, prs: str, verified: str, note: str,
          shipped: str | None = None, open_ends: list[str] = (), next_session: str | None = None,
          date: str | None = None, force: bool = False) -> str:
    q = Queue(planning)
    date = date or today()
    r = q.row(session)
    if r is None:
        raise QueueError(f"`{session}` has no row in §1")
    if r.mark != cp.RUNNING and not force:
        raise QueueError(f"`{session}` is {r.mark}, not ▶: claim first (§6.1), or pass --force")
    m = MARK[mark]
    if m == cp.OPEN_ENDS and not open_ends:
        raise QueueError("a ◐ close needs at least one --open-end \"<due> | <what> | <closes when>\"")
    parts = [date, prs, f"verified: {verified}"] + ([f"shipped as: {shipped}"] if shipped else []) \
        + [f"memory note: {note}"]
    q.set_cells(r.line, mark=m, receipt=" · ".join(parts))
    notes: list[str] = []
    for oe in open_ends:
        cells = [c.strip() for c in oe.split("|")]
        if len(cells) != 3 or not all(cells):
            raise QueueError(f"--open-end needs \"<due> | <what> | <closes when>\", got {oe!r}")
        q.append_row("Open ends", {"due": cells[0], "what": cells[1], "from": f"`{session}`", "closes when": cells[2]})
    if open_ends:
        notes.append(f"{len(open_ends)} open end(s) added")
    if r.table.startswith("Slot"):
        in_slot = [x for x in q.rows() if x.table == r.table]
        if not any(x.mark == cp.NEXT for x in in_slot):
            if next_session:
                cand = next((x for x in in_slot if x.session == next_session), None)
                if cand is None or cand.mark not in {cp.LATER, cp.WAITING}:
                    raise QueueError(f"--next `{next_session}` is not a ⬜ or ⏸ row of {r.table}")
                if cand.mark == cp.WAITING:
                    notes.append(f"`{cand.session}` was ⏸: reword its row, its wait is met")
            else:
                cand = next((x for x in in_slot if x.line > r.line and x.mark == cp.LATER), None)
            if cand:
                q.set_cells(cand.line, mark=cp.NEXT)
                notes.append(f"⏭ now on `{cand.session}`")
            else:
                notes.append(f"no row left in {r.table}: ask the owner what comes next (§6.1 step 6)")
    num = q.close_prompt(session, date)
    notes.append(f"prompt §{num} marked closed" if num else "no open prompt block for it in §2")
    dropped = q.drop_order_rules(session)
    if dropped:
        notes.append(f"{dropped} order rule(s) about it deleted")
    q.save()
    return f"closed `{session}` {m} {date}; " + "; ".join(notes)


def next_up(planning: Path, slot: int | None = None) -> tuple[list[str], str | None]:
    """One line per slot, and the session to paste next (the first free slot's ⏭), if any."""
    q = Queue(planning)
    rows, slots = q.rows(), q.slots()
    lines: list[str] = []
    paste: str | None = None
    for name, limit in sorted(slots.items(), key=lambda kv: int(kv[0].split()[1])):
        if slot is not None and name != f"Slot {slot}":
            continue
        in_slot = [r for r in rows if r.table == name]
        running = [r for r in in_slot if r.mark == cp.RUNNING]
        nxt = next((r for r in in_slot if r.mark == cp.NEXT), None)
        later = next((r for r in in_slot if r.mark == cp.LATER), None)
        busy = ", ".join(f"`{r.session}`" for r in running)
        if nxt and len(running) < limit:
            lines.append(f"{name}: paste `{nxt.session}` ({q.cell(nxt.line, 'prompt') or '§2'})")
            paste = paste or nxt.session
        elif nxt:
            lines.append(f"{name}: busy (▶ {busy}); next is ⏭ `{nxt.session}` when it closes")
        elif running:
            lines.append(f"{name}: busy (▶ {busy}); nothing queued after it")
        elif later:
            lines.append(f"{name}: no ⏭; the first ⬜ is `{later.session}` (a planning session sets ⏭)")
        else:
            lines.append(f"{name}: nothing queued")
    return lines, paste


# ---------------------------------------------------------------------------- the CLI

def _checked(planning: Path, msg: str) -> int:
    print(msg)
    errs = [str(f) for f in cp.check(planning) if f.level == "ERROR"]
    if errs:
        print("check_planning reports:\n  " + "\n  ".join(errs))
        print("the edit is on disk: fix it, then python3 PLANNING/check_planning.py")
        return 1
    print("check_planning: clean")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--planning", type=Path, default=PLANNING, help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("next", help="what each slot runs next")
    n.add_argument("--slot", type=int)
    n.add_argument("--paste", action="store_true", help="print only the session to paste, exit 1 if none")
    p = sub.add_parser("prompt", help="the prompt block to paste")
    p.add_argument("session")
    w = sub.add_parser("row", help="the session's row")
    w.add_argument("session")
    c = sub.add_parser("claim", help="the row to ▶ with the date and Who; ⏭ moved on")
    c.add_argument("session")
    c.add_argument("--who")
    c.add_argument("--date")
    c.add_argument("--beside", action="store_true", help="a side session: add a ▶ row under Beside the queue")
    c.add_argument("--work", help="with --beside: what the session does")
    k = sub.add_parser("close", help="the row to ✅ or ◐ with receipts; ⏭, open ends, the prompt block, order rules")
    k.add_argument("session")
    k.add_argument("--mark", choices=sorted(MARK), required=True)
    k.add_argument("--prs", required=True, help='e.g. "#12, #13"')
    k.add_argument("--verified", required=True, help="how it was verified, on the real thing")
    k.add_argument("--shipped", help="what it shipped as (a version, a release)")
    k.add_argument("--note", required=True, help="the memory note's file name")
    k.add_argument("--open-end", action="append", default=[], metavar='"<due> | <what> | <closes when>"')
    k.add_argument("--next", dest="next_session", help="the row that gets ⏭ (default: the first ⬜ below)")
    k.add_argument("--date")
    k.add_argument("--force", action="store_true", help="close a row that is not ▶")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "next":
            lines, paste = next_up(a.planning, a.slot)
            if a.paste:
                if not paste:
                    return 1
                print(paste)
                return 0
            print("\n".join(lines))
            return 0
        if a.cmd == "prompt":
            pr = Queue(a.planning).prompt(a.session)
            if pr is None:
                raise QueueError(f"`{a.session}` has no prompt block in §2")
            sys.stdout.write(pr.body if pr.body.endswith("\n") else pr.body + "\n")
            return 0
        if a.cmd == "row":
            r = Queue(a.planning).row(a.session)
            if r is None:
                raise QueueError(f"`{a.session}` has no row in §1")
            print(f"{r.table}, line {r.line}: {r.text.strip()}")
            return 0
        if a.cmd == "claim":
            if a.beside and not a.work:
                raise QueueError("--beside needs --work \"<what>\"")
            return _checked(a.planning, claim(a.planning, a.session, a.who, a.date, a.beside, a.work))
        if a.cmd == "close":
            return _checked(a.planning, close(a.planning, a.session, a.mark, a.prs, a.verified, a.note,
                                              a.shipped, a.open_end, a.next_session, a.date, a.force))
    except QueueError as e:
        print(f"queue: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
