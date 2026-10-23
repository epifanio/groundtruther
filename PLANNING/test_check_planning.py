"""Tests for PLANNING/check_planning.py: the real files pass, and each rule catches its case.

    python3 -m unittest PLANNING/test_check_planning.py -v
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("check_planning", HERE / "check_planning.py")
cp = importlib.util.module_from_spec(_spec)
sys.modules["check_planning"] = cp   # dataclasses look the module up here (Python ≤ 3.13)
_spec.loader.exec_module(cp)

PROMPT = textwrap.dedent("""\
    Work on demo WP-{n} of PLANNING/TODO_demo.md, as session `{s}`. First command:
    `git fetch origin && git worktree add ../proj-{s} -b claude/{s} origin/main`.
    Claim first: a PR that only sets your row in §1 to ▶ ("started" and the date) and moves ⏭ on.
    Memory: read MEMORY.md.
    Close by PLANNING/TODO_session_sequence.md §6.1.
    """)


def sequence(slot1: str = "", slot2: str = "", prompts: str = "", open_ends: str = "",
             order: str = "- none yet", who: bool = False) -> str:
    hdr = ("| Mark | Session | Who | Work | Prompt | Receipt / notes |\n|---|---|---|---|---|---|" if who
           else "| Mark | Session | Work | Prompt | Receipt / notes |\n|---|---|---|---|---|")
    return textwrap.dedent("""\
        # Queue

        ## 1. The queue

        ### State — what is deployed now

        | Unit | Now | Since (UTC) | Recorded by | Rollback · notes |
        |---|---|---|---|---|
        | App | v1 | 2026-01-01 | `setup` | — |

        ### Slot 1 — A

        {hdr}
        {slot1}

        ### Slot 2 — B

        {hdr}
        {slot2}

        **Order rules**:

        {order}

        ### Beside the queue

        {hdr}

        ### Open ends (owed by a closed session)

        | Due | What | From | Closes when |
        |---|---|---|---|
        {open_ends}

        ## 2. Prompts

        {prompts}

        ## 6. Rules every session follows

        ### 6.1 Keeping this file current
        """).format(slot1=slot1, slot2=slot2, prompts=prompts, open_ends=open_ends, order=order, hdr=hdr)


def prompt(num: str, session: str, body: str | None = None) -> str:
    body = PROMPT.format(n=num, s=session) if body is None else body
    return f"### {num} `{session}`\n\n```text\n{body}```\n"


INDEX = "# Index\n\n## Open\n\n| Added | Plan | What | State |\n|---|---|---|---|\n| 2026-01-01 | [demo](TODO_demo.md) | x | open |\n"


class Base(unittest.TestCase):
    def run_check(self, seq: str, files: dict[str, str] | None = None) -> list[str]:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / cp.SEQUENCE).write_text(seq, encoding="utf-8")
            (p / cp.INDEX).write_text(INDEX, encoding="utf-8")
            (p / "TODO_demo.md").write_text("# Demo\n\n**Status:** open.\n\n## 1. x\n", encoding="utf-8")
            for name, text in (files or {}).items():
                (p / name).parent.mkdir(parents=True, exist_ok=True)
                (p / name).write_text(text, encoding="utf-8")
            return [x.rule for x in cp.check(p)]


class RealFiles(unittest.TestCase):
    def test_the_installed_planning_files_pass(self):
        errors = [str(x) for x in cp.check(HERE) if x.level == "ERROR"]
        self.assertEqual(errors, [])


class Rules(Base):
    def test_a_good_queue_passes(self):
        seq = sequence(
            slot1="| ✅ | `a1` | x | — | 2026-01-02 · #1 |\n| ▶ | `a2` | x | §2.2 | started 2026-01-03 |\n| ⏭ | `a3` | x | §2.3 | |",
            slot2="| ⏸ | `b1` | x | §2.4 | Waits on `a2` |\n| ◐ | `b0` | x | — | 2026-01-02 |",
            open_ends="| 2026-02-01 | a check | `b0` | the owner has looked |",
            prompts="### 2.1 `a1` (closed 2026-01-02; its prompt is in git history)\n\n"
                    + prompt("2.2", "a2") + prompt("2.3", "a3") + prompt("2.4", "b1"))
        self.assertEqual(self.run_check(seq), [])

    def test_S0_no_slot(self):
        self.assertIn("S0", self.run_check("# Q\n\n## 1. The queue\n\n### State\n\n## 2. Prompts\n"))

    def test_S1_unknown_mark(self):
        self.assertIn("S1", self.run_check(sequence(slot1="| ?? | `a1` | x | — | 2026-01-01 |")))

    def test_S2_duplicate_session(self):
        seq = sequence(slot1="| ✅ | `a1` | x | — | 2026-01-01 |", slot2="| ✅ | `a1` | x | — | 2026-01-01 |")
        self.assertIn("S2", self.run_check(seq))

    def test_S3_two_next(self):
        seq = sequence(slot1="| ⏭ | `a1` | x | §2.1 | |\n| ⏭ | `a2` | x | §2.2 | |",
                       prompts=prompt("2.1", "a1") + prompt("2.2", "a2"))
        self.assertIn("S3", self.run_check(seq))

    def test_S4_two_running_and_the_owner_lifts_it(self):
        rows = "| ▶ | `a1` | x | §2.1 | started 2026-01-01 |\n| ▶ | `a2` | x | §2.2 | started 2026-01-01 |"
        prompts = prompt("2.1", "a1") + prompt("2.2", "a2")
        self.assertIn("S4", self.run_check(sequence(slot1=rows, prompts=prompts)))
        lifted = sequence(slot1=rows, prompts=prompts, order="- Slot 1 runs 2 sessions at once (owner, 2026-01-01).")
        self.assertNotIn("S4", self.run_check(lifted))

    def test_S5_queued_without_prompt(self):
        self.assertIn("S5", self.run_check(sequence(slot1="| ⬜ | `a1` | x | §2.1 | |")))

    def test_S6_waiting_without_reason(self):
        seq = sequence(slot1="| ⏸ | `a1` | x | §2.1 | later |", prompts=prompt("2.1", "a1"))
        self.assertIn("S6", self.run_check(seq))

    def test_S7_closed_without_date(self):
        self.assertIn("S7", self.run_check(sequence(slot1="| ✅ | `a1` | x | — | #3 |")))

    def test_S8_closed_with_prompt(self):
        seq = sequence(slot1="| ✅ | `a1` | x | — | 2026-01-01 |", prompts=prompt("2.1", "a1"))
        self.assertIn("S8", self.run_check(seq))

    def test_S9_open_ends_missing(self):
        self.assertIn("S9", self.run_check(sequence(slot1="| ◐ | `a1` | x | — | 2026-01-01 |")))

    def test_S10_prompt_without_row(self):
        self.assertIn("S10", self.run_check(sequence(prompts=prompt("2.1", "ghost"))))

    def test_S11_prompt_missing_the_claim(self):
        bad = PROMPT.format(n=1, s="a1").replace("Claim first", "Maybe")
        seq = sequence(slot1="| ⏭ | `a1` | x | §2.1 | |", prompts=prompt("2.1", "a1", bad))
        self.assertIn("S11", self.run_check(seq))

    def test_S11_accepts_the_short_form(self):
        short = "/build-session a1\nPlan: TODO_demo.md WP-1 (x), slot 1. Scope: y. Verify: z.\n"
        seq = sequence(slot1="| ⏭ | `a1` | x | §2.1 | |", prompts=prompt("2.1", "a1", short))
        self.assertNotIn("S11", self.run_check(seq))
        other = sequence(slot1="| ⏭ | `a1` | x | §2.1 | |", prompts=prompt("2.1", "a1", "/build-session a2\nScope: y.\n"))
        self.assertIn("S11", self.run_check(other))      # another session's name: the long form's parts are needed

    def test_S12_open_end_with_empty_cell(self):
        seq = sequence(slot1="| ◐ | `a1` | x | — | 2026-01-01 |", open_ends="| 2026-02-01 | a check | `a1` | |")
        self.assertIn("S12", self.run_check(seq))

    def test_S13_long_line(self):
        self.assertIn("S13", self.run_check(sequence(slot1="| ✅ | `a1` | x | — | 2026-01-01 " + "y" * 1300 + " |")))

    def test_S14_missing_plan(self):
        self.assertIn("S14", self.run_check(sequence(slot1="| ✅ | `a1` | TODO_gone.md | — | 2026-01-01 |")))

    def test_S15_cites_a_missing_section(self):
        files = {"WORKFLOW.md": "Close by TODO_session_sequence.md §9.9.\n"}
        self.assertIn("S15", self.run_check(sequence(), files))

    def test_S16_who_column(self):
        def seq(row: str, who: bool = True) -> str:
            return sequence(slot1=row, prompts=prompt("2.1", "a1"), who=who)
        self.assertIn("S16", self.run_check(seq("| ▶ | `a1` | | x | §2.1 | started 2026-01-01 |")))
        self.assertIn("S16", self.run_check(seq("| ✅ | `a1` | | x | — | 2026-01-02 · #1 |")))
        self.assertNotIn("S16", self.run_check(seq("| ▶ | `a1` | alice | x | §2.1 | started 2026-01-01 |")))
        # a queued row has no Who yet; a table without the column is not checked
        self.assertNotIn("S16", self.run_check(seq("| ⏭ | `a1` | | x | §2.1 | |")))
        self.assertNotIn("S16", self.run_check(seq("| ▶ | `a1` | x | §2.1 | started 2026-01-01 |", who=False)))

    def test_S17_rulebook_references(self):
        wf = "# Rules\n\n## 1. The files\n\n### 1.1 Truth\n\nSee §1.1 and the queue's §9 (S15's business).\n\n## 2. Kinds\n"
        self.assertNotIn("S17", self.run_check(sequence(), {"WORKFLOW.md": wf, "notes.md": "By `WORKFLOW.md` §1–§2.\n"}))
        self.assertIn("S17", self.run_check(sequence(), {"WORKFLOW.md": wf, "notes.md": "By WORKFLOW.md §9.\n"}))
        self.assertIn("S17", self.run_check(sequence(), {"WORKFLOW.md": wf + "\nSee §7.3.\n"}))

    def test_I1_plan_not_indexed(self):
        self.assertIn("I1", self.run_check(sequence(), {"TODO_other.md": "# Other\n"}))

    def test_I2_index_link_missing(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / cp.SEQUENCE).write_text(sequence(), encoding="utf-8")
            (p / cp.INDEX).write_text(INDEX + "| x | [gone](TODO_gone.md) | x | x |\n", encoding="utf-8")
            (p / "TODO_demo.md").write_text("# Demo\n", encoding="utf-8")
            self.assertIn("I2", [x.rule for x in cp.check(p)])

    def test_I3_open_and_closed(self):
        self.assertIn("I3", self.run_check(sequence(), {"demo.md": "# Demo, closed\n"}))

    def test_I4_superseded_banner(self):
        files = {"TODO_demo.md": "# Demo\n\n**Status:** SUPERSEDED by TODO_x.md.\n\n## 1. x\n"}
        self.assertIn("I4", self.run_check(sequence(), files))
        quoted = {"TODO_demo.md": "# Demo\n\n**Status:** open; the old \"SUPERSEDED\" label is gone.\n\n## 1\n"}
        self.assertNotIn("I4", self.run_check(sequence(), quoted))


RECORD = "---\nid: {id}\ndate: 2026-01-01\nstatus: {status}\ndecided-by: me, 2026-01-01 (TODO_demo.md §6 Q1)\n{extra}---\n**Decision.** x\n"
DECISIONS_HEAD = "# Decisions\n\n| ID | Status | Date | Decision | Record |\n|---|---|---|---|---|\n"


def record(did: str, status: str = "accepted", extra: str = "") -> str:
    return RECORD.format(id=did, status=status, extra=extra)


def drow(did: str, status: str = "accepted", file: str | None = None) -> str:
    file = file or f"{did}_x.md"
    return f"| {did} | {status} | 2026-01-01 | x | [{file}](decisions/{file}) |\n"


class Decisions(Base):
    """D1–D3: the registry (DECISIONS.md and decisions/D-<nnn>_<slug>.md) and who may cite what."""

    def registry(self, records: dict[str, str], index: str, seq: str | None = None) -> list[str]:
        files = {cp.DECISIONS: DECISIONS_HEAD + index, f"{cp.DECISIONS_DIR}/README.md": "# how to write one\n"}
        files.update({f"{cp.DECISIONS_DIR}/{name}": text for name, text in records.items()})
        return [r for r in self.run_check(seq or sequence(), files) if r.startswith("D")]

    def test_no_registry_means_no_findings(self):
        self.assertEqual([r for r in self.run_check(sequence()) if r.startswith("D")], [])

    def test_a_good_registry_passes_and_an_accepted_record_may_be_cited(self):
        body = PROMPT.format(n=1, s="a1") + "Decisions that bind this work: D-001.\n"
        seq = sequence(slot1="| ⏭ | `a1` | x (D-001) | §2.1 | |", prompts=prompt("2.1", "a1", body))
        records = {"D-001_x.md": record("D-001"), "D-002_y.md": record("D-002", "superseded by D-003"),
                   "D-003_z.md": record("D-003", extra="supersedes: D-002\nlanes: A\nenforced-by: a lint\n")}
        index = drow("D-001") + drow("D-002", "superseded by D-003", "D-002_y.md") + drow("D-003", file="D-003_z.md")
        self.assertEqual(self.registry(records, index, seq), [])

    def test_D1_record_without_row(self):
        self.assertIn("D1", self.registry({"D-001_x.md": record("D-001")}, ""))

    def test_D1_row_without_record(self):
        self.assertIn("D1", self.registry({}, drow("D-001")))

    def test_D1_two_records_with_one_id(self):
        records = {"D-001_x.md": record("D-001"), "D-001_y.md": record("D-001")}
        self.assertIn("D1", self.registry(records, drow("D-001")))

    def test_D1_id_differs_from_the_file_name(self):
        self.assertIn("D1", self.registry({"D-002_x.md": record("D-001")}, drow("D-002")))

    def test_D1_row_does_not_link_its_record(self):
        index = "| D-001 | accepted | 2026-01-01 | x | — |\n"
        self.assertIn("D1", self.registry({"D-001_x.md": record("D-001")}, index))

    def test_D2_missing_fields(self):
        bare = "---\nid: D-001\nstatus: accepted\n---\nx\n"      # no date, no decided-by
        self.assertIn("D2", self.registry({"D-001_x.md": bare}, drow("D-001")))

    def test_D2_unknown_status(self):
        self.assertIn("D2", self.registry({"D-001_x.md": record("D-001", "maybe")}, drow("D-001", "maybe")))

    def test_D2_superseded_by_a_missing_record(self):
        records = {"D-001_x.md": record("D-001", "superseded by D-009")}
        self.assertIn("D2", self.registry(records, drow("D-001", "superseded by D-009")))

    def test_D2_index_status_differs_from_the_record(self):
        self.assertIn("D2", self.registry({"D-001_x.md": record("D-001")}, drow("D-001", "proposed")))

    def test_D3_pastable_row_cites_a_proposed_record(self):
        seq = sequence(slot1="| ⏭ | `a1` | x (D-001) | §2.1 | |", prompts=prompt("2.1", "a1"))
        self.assertIn("D3", self.registry({"D-001_x.md": record("D-001", "proposed")}, drow("D-001", "proposed"), seq))

    def test_D3_prompt_cites_a_superseded_record(self):
        body = PROMPT.format(n=1, s="a1") + "Decisions that bind this work: D-001.\n"
        seq = sequence(slot1="| ⬜ | `a1` | x | §2.1 | |", prompts=prompt("2.1", "a1", body))
        records = {"D-001_x.md": record("D-001", "superseded by D-002"), "D-002_y.md": record("D-002")}
        index = drow("D-001", "superseded by D-002") + drow("D-002", file="D-002_y.md")
        self.assertIn("D3", self.registry(records, index, seq))

    def test_D3_waiting_row_may_cite_a_proposed_record(self):
        seq = sequence(slot1="| ⏸ | `a1` | x | §2.1 | Waits on D-001 |", prompts=prompt("2.1", "a1"))
        self.assertNotIn("D3", self.registry({"D-001_x.md": record("D-001", "proposed")}, drow("D-001", "proposed"), seq))

    def test_D4_enforce_lint(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            planning = root / "PLANNING"
            (planning / cp.DECISIONS_DIR).mkdir(parents=True)
            (planning / cp.SEQUENCE).write_text(sequence(who=True), encoding="utf-8")
            (planning / cp.INDEX).write_text(INDEX, encoding="utf-8")
            (planning / "TODO_demo.md").write_text("# Demo\n\n**Status:** open.\n\n## 1. x\n", encoding="utf-8")
            rec = planning / cp.DECISIONS_DIR / "D-001_x.md"
            (root / "src").mkdir()
            (root / "src" / "a.py").write_text("x = 1\nimport prisma\n", encoding="utf-8")
            (root / "lib").mkdir()
            (root / "lib" / "b.py").write_text("import prisma\n", encoding="utf-8")      # outside the scope
            (root / "docs").mkdir()
            (root / "docs" / "c.md").write_text("TODO later\n", encoding="utf-8")

            def run(status="accepted", enforce="enforce: import .*prisma in src/\nenforce: TODO in **/*.md\n"):
                rec.write_text(record("D-001", status, extra=enforce), encoding="utf-8")
                (planning / cp.DECISIONS).write_text(DECISIONS_HEAD + drow("D-001", status), encoding="utf-8")
                return [str(x) for x in cp.check(planning)]

            found = [m for m in run() if "[D4]" in m]
            self.assertEqual(len(found), 2, found)
            self.assertTrue(any("src/a.py:2" in m and "D-001" in m for m in found), found)
            self.assertTrue(any("docs/c.md:1" in m for m in found), found)
            self.assertFalse(any("lib/b.py" in m for m in found), found)       # the scope holds
            self.assertFalse(any("PLANNING/" in m for m in found), found)      # the records are never scanned
            self.assertEqual([m for m in run("proposed") if "[D4]" in m], [])   # only an accepted record enforces
            self.assertTrue(any("[D2]" in m for m in run(enforce="enforce: import prisma\n")))   # no scope
            self.assertTrue(any("[D2]" in m for m in run(enforce="enforce: ( in src/\n")))        # bad regex

    def test_D3_unknown_record(self):
        seq = sequence(slot1="| ⏭ | `a1` | x (D-777) | §2.1 | |", prompts=prompt("2.1", "a1"))
        self.assertIn("D3", self.registry({"D-001_x.md": record("D-001")}, drow("D-001"), seq))


class Live(unittest.TestCase):
    def live(self, seq: str, prs: list[dict], today: str = "2026-01-10", merged: set[str] = frozenset()):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / cp.SEQUENCE).write_text(seq, encoding="utf-8")
            found = cp.check_live(p, prs=prs, today=dt.date.fromisoformat(today),
                                  state_of=lambda n: "MERGED" if n in merged else "OPEN")
            return [x.rule for x in found]

    def test_L1_queued_but_running(self):
        seq = sequence(slot1="| ⏭ | `a1` | x | §2.1 | |", prompts=prompt("2.1", "a1"))
        self.assertIn("L1", self.live(seq, [{"number": 5, "title": "[a1] x", "headRefName": "claude/a1"}]))

    def test_L3_running_without_pr(self):
        seq = sequence(slot1="| ▶ | `a1` | x | §2.1 | started 2026-01-01 |", prompts=prompt("2.1", "a1"))
        self.assertIn("L3", self.live(seq, []))

    def test_L4_and_L5_waits(self):
        seq = sequence(slot1="| ⏸ | `a1` | x | §2.1 | Waits on #7, by 2026-01-05 |", prompts=prompt("2.1", "a1"))
        rules = self.live(seq, [], merged={"7"})
        self.assertIn("L4", rules)
        self.assertIn("L5", rules)

    def test_L5_reads_only_the_date_after_waits_on_by_or_until(self):
        def row(text: str) -> str:
            return sequence(slot1=f"| ⏸ | `a1` | x | §2.1 | {text} |", prompts=prompt("2.1", "a1"))
        for due in ("Waits on 2026-01-05", "**Waits on**: 2026-01-05", "Waits on #7 by 2026-01-05",
                    "Waits on the owner's answer, until 2026-01-05"):
            self.assertIn("L5", self.live(row(due), []), due)
        # the date a row mentions for another reason is not the due date: it must not warn forever
        for other in ("Waits on upstream issue #7 (filed 2026-01-05)", "Waits on #7, opened 2026-01-05",
                      "Waits on #7 by 2026-02-01"):
            self.assertNotIn("L5", self.live(row(other), []), other)

    def test_L6_open_end_due(self):
        seq = sequence(slot1="| ◐ | `a1` | x | — | 2026-01-01 |", open_ends="| 2026-01-09 | x | `a1` | y |")
        self.assertIn("L6", self.live(seq, []))


if __name__ == "__main__":
    unittest.main()
