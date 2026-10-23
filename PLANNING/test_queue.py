"""Tests for PLANNING/queue.py: claim, close and next edit the queue the way WORKFLOW.md §6 says, and
the checker accepts what they write.

    python3 -m unittest PLANNING/test_queue.py -v
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name: str, register_as: str | None = None):
    spec = importlib.util.spec_from_file_location(register_as or name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[register_as or name] = mod   # check_planning's dataclasses need it registered (Python ≤ 3.13)
    spec.loader.exec_module(mod)
    return mod


cp = sys.modules.get("check_planning") or _load("check_planning")
fx = _load("test_check_planning")                 # its queue fixtures: sequence(), prompt(), INDEX
q = _load("queue", register_as="planning_queue")   # not under "queue": that name is the standard library's


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Path(self.tmp.name)

    def make(self, seq: str) -> Path:
        (self.p / cp.SEQUENCE).write_text(seq, encoding="utf-8")
        (self.p / cp.INDEX).write_text(fx.INDEX, encoding="utf-8")
        (self.p / "TODO_demo.md").write_text("# Demo\n\n**Status:** open.\n\n## 1. x\n", encoding="utf-8")
        return self.p

    def text(self) -> str:
        return (self.p / cp.SEQUENCE).read_text(encoding="utf-8")

    def errors(self) -> list[str]:
        return [str(f) for f in cp.check(self.p) if f.level == "ERROR"]


class Claim(Base):
    def test_claim_marks_running_writes_who_and_moves_next(self):
        self.make(fx.sequence(slot1="| ⏭ | `a1` | | x | §2.1 | |\n| ⬜ | `a2` | | y | §2.2 | |",
                              prompts=fx.prompt("2.1", "a1") + fx.prompt("2.2", "a2"), who=True))
        msg = q.claim(self.p, "a1", who="alice", date="2026-01-05")
        self.assertIn("| ▶ | `a1` | alice | x | §2.1 | started 2026-01-05 |", self.text())
        self.assertIn("| ⏭ | `a2` |", self.text())
        self.assertIn("⏭ moved to `a2`", msg)
        self.assertEqual(self.errors(), [])

    def test_claim_without_who_column_still_works(self):
        self.make(fx.sequence(slot1="| ⏭ | `a1` | x | §2.1 | |", prompts=fx.prompt("2.1", "a1")))
        q.claim(self.p, "a1", who="alice", date="2026-01-05")
        self.assertIn("| ▶ | `a1` | x | §2.1 | started 2026-01-05 |", self.text())
        self.assertEqual(self.errors(), [])

    def test_claim_refuses_a_row_taken_by_another(self):
        self.make(fx.sequence(slot1="| ▶ | `a1` | bob | x | §2.1 | started 2026-01-04 |",
                              prompts=fx.prompt("2.1", "a1"), who=True))
        with self.assertRaises(q.QueueError):
            q.claim(self.p, "a1", who="alice", date="2026-01-05")
        self.assertIn("| ▶ | `a1` | bob |", self.text())

    def test_claim_is_idempotent_for_the_same_person(self):
        self.make(fx.sequence(slot1="| ▶ | `a1` | alice | x | §2.1 | started 2026-01-04 |",
                              prompts=fx.prompt("2.1", "a1"), who=True))
        self.assertIn("nothing to do", q.claim(self.p, "a1", who="alice"))

    def test_claim_refuses_a_closed_or_waiting_row(self):
        self.make(fx.sequence(slot1="| ⏸ | `a1` | | x | §2.1 | Waits on #7 |", prompts=fx.prompt("2.1", "a1"), who=True))
        with self.assertRaises(q.QueueError):
            q.claim(self.p, "a1", who="alice")

    def test_claim_beside_adds_a_row(self):
        self.make(fx.sequence(who=True))
        msg = q.claim(self.p, "hotfix-1", who="alice", date="2026-01-05", beside=True, work="a crash on login")
        self.assertIn("Beside the queue", msg)
        self.assertIn("| ▶ | `hotfix-1` | alice | a crash on login | — | started 2026-01-05 |", self.text())
        self.assertEqual(self.errors(), [])

    def test_claim_without_a_row_and_without_beside_is_refused(self):
        self.make(fx.sequence(who=True))
        with self.assertRaises(q.QueueError):
            q.claim(self.p, "ghost", who="alice")


class Close(Base):
    def test_close_done_writes_receipts_moves_next_closes_prompt_drops_rules(self):
        self.make(fx.sequence(slot1="| ▶ | `a1` | alice | x | §2.1 | started 2026-01-04 |\n| ⬜ | `a2` | | y | §2.2 | |",
                              prompts=fx.prompt("2.1", "a1") + fx.prompt("2.2", "a2"),
                              order="- `a1` before `a2`: both touch the schema.", who=True))
        msg = q.close(self.p, "a1", "done", prs="#4, #5", verified="the login flow on a phone",
                      note="2026-01-06_a1.md", shipped="v1.2", date="2026-01-06")
        t = self.text()
        self.assertIn("| ✅ | `a1` | alice | x | §2.1 | 2026-01-06 · #4, #5 · verified: the login flow on a phone"
                      " · shipped as: v1.2 · memory note: 2026-01-06_a1.md |", t)
        self.assertIn("| ⏭ | `a2` |", t)
        self.assertIn("### 2.1 `a1` (closed 2026-01-06; its prompt is in git history)", t)
        self.assertNotIn("as session `a1`", t)                       # its prompt block is gone
        self.assertIn("### 2.2 `a2`\n\n```text", t)                  # the next one is untouched
        self.assertIn("- none yet", t)
        self.assertNotIn("`a1` before `a2`", t)
        self.assertIn("⏭ now on `a2`", msg)
        self.assertEqual(self.errors(), [])

    def test_close_with_open_ends(self):
        self.make(fx.sequence(slot1="| ▶ | `a1` | alice | x | §2.1 | started 2026-01-04 |",
                              prompts=fx.prompt("2.1", "a1"), who=True))
        msg = q.close(self.p, "a1", "open-ends", prs="#4", verified="on staging", note="n.md",
                      open_ends=["2026-02-01 | a device check | the owner has looked"], date="2026-01-06")
        t = self.text()
        self.assertIn("| ◐ | `a1` |", t)
        self.assertIn("| 2026-02-01 | a device check | `a1` | the owner has looked |", t)
        self.assertIn("no row left in Slot 1", msg)
        self.assertEqual(self.errors(), [])

    def test_close_open_ends_needs_one(self):
        self.make(fx.sequence(slot1="| ▶ | `a1` | alice | x | §2.1 | started 2026-01-04 |",
                              prompts=fx.prompt("2.1", "a1"), who=True))
        with self.assertRaises(q.QueueError):
            q.close(self.p, "a1", "open-ends", prs="#4", verified="x", note="n.md")

    def test_close_requires_a_claimed_row(self):
        self.make(fx.sequence(slot1="| ⏭ | `a1` | | x | §2.1 | |", prompts=fx.prompt("2.1", "a1"), who=True))
        with self.assertRaises(q.QueueError):
            q.close(self.p, "a1", "done", prs="#4", verified="x", note="n.md")
        q.close(self.p, "a1", "done", prs="#4", verified="x", note="n.md", date="2026-01-06", force=True)
        self.assertIn("| ✅ | `a1` |", self.text())

    def test_close_next_names_the_row(self):
        self.make(fx.sequence(slot1="| ▶ | `a1` | alice | x | §2.1 | started 2026-01-04 |\n"
                                    "| ⬜ | `a2` | | y | §2.2 | |\n| ⬜ | `a3` | | z | §2.3 | |",
                              prompts=fx.prompt("2.1", "a1") + fx.prompt("2.2", "a2") + fx.prompt("2.3", "a3"), who=True))
        q.close(self.p, "a1", "done", prs="#4", verified="x", note="n.md", next_session="a3", date="2026-01-06")
        self.assertIn("| ⏭ | `a3` |", self.text())
        self.assertIn("| ⬜ | `a2` |", self.text())
        self.assertEqual(self.errors(), [])


class Next(Base):
    def test_next_lists_slots_and_names_what_to_paste(self):
        self.make(fx.sequence(slot1="| ⏭ | `a1` | | x | §2.1 | |",
                              slot2="| ▶ | `b1` | bob | x | §2.2 | started 2026-01-04 |\n| ⏭ | `b2` | | y | §2.3 | |",
                              prompts=fx.prompt("2.1", "a1") + fx.prompt("2.2", "b1") + fx.prompt("2.3", "b2"), who=True))
        lines, paste = q.next_up(self.p)
        self.assertEqual(lines, ["Slot 1: paste `a1` (§2.1)", "Slot 2: busy (▶ `b1`); next is ⏭ `b2` when it closes"])
        self.assertEqual(paste, "a1")

    def test_next_on_an_empty_queue(self):
        self.make(fx.sequence(who=True))
        lines, paste = q.next_up(self.p)
        self.assertEqual(lines, ["Slot 1: nothing queued", "Slot 2: nothing queued"])
        self.assertIsNone(paste)

    def test_prompt_and_row(self):
        self.make(fx.sequence(slot1="| ⏭ | `a1` | | x | §2.1 | |", prompts=fx.prompt("2.1", "a1"), who=True))
        qq = q.Queue(self.p)
        self.assertIn("as session `a1`", qq.prompt("a1").body)
        self.assertEqual(qq.row("a1").mark, "⏭")
        self.assertIsNone(qq.prompt("nobody"))


class Cli(Base):
    def test_cli_round_trip_runs_the_checker(self):
        self.make(fx.sequence(slot1="| ⏭ | `a1` | | x | §2.1 | |", prompts=fx.prompt("2.1", "a1"), who=True))
        base = ["--planning", str(self.p)]
        self.assertEqual(q.main(base + ["claim", "a1", "--who", "alice", "--date", "2026-01-05"]), 0)
        self.assertEqual(q.main(base + ["close", "a1", "--mark", "done", "--prs", "#4", "--verified", "x",
                                        "--note", "n.md", "--date", "2026-01-06"]), 0)
        self.assertEqual(q.main(base + ["next"]), 0)
        self.assertEqual(q.main(base + ["next", "--paste"]), 1)
        self.assertEqual(q.main(base + ["claim", "a1"]), 2)          # closed: refused, exit 2


if __name__ == "__main__":
    unittest.main()
