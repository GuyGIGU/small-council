"""Seat files and the rows about a seat (records/seat_files.py, seat_rows.py), a gate's saved verdict
(records/verdicts.py) and a header field set without an event (records/state_set.py): the records `council
collect`, `check` and `index` read and write (S7)."""
from __future__ import annotations

import os
import unittest

import support

from council.records import seat_files, seat_rows, state_set, verdicts


class SeatFilesTest(support.Scratch):
    def test_brief_seats_join_paired_refs_and_default_the_rest(self) -> None:
        path = self.write("brief.md", "# B\n## Seats\n### security — lane\n- ref: references/a.md\n- **Ref:** `b.md`\n"
                                      "- out: seats/x.md\n- cap: 5 items\n### beck\n## Other\n### not-a-seat\n")
        self.assertEqual(seat_files.brief_seats(path),
                         [seat_files.Seat("security", "references/a.md ;; b.md", "seats/x.md", "5"),
                          seat_files.Seat("beck", "none", "seats/beck.md", "8")])

    def test_a_title_is_compared_on_letters_and_digits(self) -> None:
        path = self.write("ref.md", "\ufeff# Héllo — World\nbody\n")
        self.assertEqual(seat_files.ref_title(path), "hlloworld")
        self.assertEqual(seat_files.norm("Héllo — World"), "hlloworld")
        self.assertEqual(seat_files.norm_wide("שלום — x"), "שלוםx")          # a title no ASCII rule knows

    def test_items_and_the_shape_of_their_section(self) -> None:
        path = self.write("seat.md", "# S — l\nref: x\n## Index\n1 · high · P1 · src/a.py:3 · title\n"
                                     "- 2 · low · P2 · a.py · t · extra\n4 · bad\n## Notes\n5 · m · p · c · t\n")
        self.assertEqual([(i.n, i.cite, i.section) for i in seat_files.items(path)],
                         [("1", "src/a.py:3", "index"), ("2", "a.py", "index"), ("5", "c", "notes")])
        self.assertEqual(seat_files.shape(path), seat_files.Shape(2, 1, False))
        self.assertEqual(seat_files.shape(path, "Notes"), seat_files.Shape(1, 0, False))
        self.assertEqual(seat_files.shape(self.write("n.md", "## Index\n(none) — nothing\n")),
                         seat_files.Shape(0, 0, True))

    def test_a_verify_file_out_of_shape_says_each_problem(self) -> None:
        problems = seat_files.verify_problems(self.write("verify-1.md", "nothing\n"))
        self.assertIn("line 1 isn't '# Verification — <run title>'; ", problems)
        self.assertTrue(problems.endswith("; "))
        self.assertEqual(seat_files.verify_problems(self.write(
            "verify-2.md", "# Verification — r\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
                           "| 1 | x | CONFIRMED | a.py:1 |\n")), "")

    def test_listed_is_a_bash_glob(self) -> None:
        for name in ("b.md", "A.md", ".h.md", "c.txt"):
            self.write("seats/" + name, "")
        self.assertEqual(seat_files.listed(self.tmp / "seats", "*.md"), ["A.md", "b.md"])


class SeatRowsTest(support.Scratch):
    def test_cells_tool_calls_and_the_plans_word(self) -> None:
        run = self.run_folder()
        self.write(".council/runs/%s/seats.tsv" % run.name,
                   "slug\tstate\tagent\ttokens\tupdated\tnote\tagents\treported\nbeck\tdone\ta1\t900\tx\tsat out\t\t\n")
        self.write(".council/runs/%s/tools.tsv" % run.name,
                   "at\tslug\tagent\tcalls\nt\tbeck\ta1\t5\nt\tbeck\ta1\t9\nt\tbeck\t\t2\nt\tother\ta2\t7\n")
        self.write(".council/runs/%s/run-plan.tsv" % run.name,
                   "budget\tbeck\ttool-calls\t30\nbudget\tbeck\ttool-calls\t40\nseat\tv1\trole\tverifier\n")
        self.assertEqual(seat_rows.cell(run, "beck", "note"), "sat out")
        self.assertEqual(seat_rows.cell(run, "nobody", "note"), "")
        self.assertEqual(seat_rows.tool_calls(run, "beck"), "11")        # a1's latest total, and the one with no id
        self.assertEqual(seat_rows.tool_calls(run, "nobody"), "")
        self.assertEqual(seat_rows.tool_budget(run, "beck"), "40")
        self.assertTrue(seat_rows.is_verifier(run, "v1"))
        self.assertFalse(seat_rows.is_verifier(run, "beck"))


class VerdictsTest(support.Scratch):
    def test_a_verdict_line_read_as_the_helpers_sed_read_it(self) -> None:
        path = self.write("v.json", '{"gate": "t", "command": "pytest \\"tests/a b.py\\"", "exit": -1, '
                                    '"seconds": 12, "proof": "change", "invalid": "flaky"}\n')
        self.assertEqual(verdicts.number(path, "exit"), "-1")
        self.assertEqual(verdicts.number(path, "seconds"), "12")
        self.assertEqual(verdicts.text(path, "proof"), "change")
        self.assertEqual(verdicts.text(path, "invalid"), "flaky")
        self.assertEqual(verdicts.command(path), 'pytest "tests/a b.py"')
        self.assertTrue(verdicts.holds(path, '"proof": "change"'))
        self.assertEqual(verdicts.number(self.tmp / "missing.json", "exit"), "")


class StateSetTest(support.Scratch):
    def test_a_header_field_is_set_and_updated_stamped(self) -> None:
        run = self.run_folder()
        state = self.write(".council/runs/%s/session-state.md" % run.name,
                           "mode: council-review\nphase: work\nnext: size the run and ask for the go-ahead\n"
                           "updated: old\n## Notes\nbase: in the body\n")
        state_set.put(run, "base", "abc123")
        lines = state.read_text(encoding="utf-8").split("\n")
        self.assertEqual(lines[:3], ["mode: council-review", "phase: work", "next:"])    # a stale Convene next
        self.assertTrue(lines[3].startswith("updated: 20"))
        self.assertEqual(lines[4:], ["base: abc123", "## Notes", "base: in the body", ""])
        state_set.put(run, "base", "def")
        self.assertIn("base: def\n## Notes", state.read_text(encoding="utf-8"))
        self.assertFalse(os.path.exists(str(state) + ".lock"))

    def test_a_closed_run_is_not_written(self) -> None:
        run = self.run_folder()
        self.write(".council/runs/%s/session-state.md" % run.name, "status: complete\nclosed: 2026-01-02 03:04\n")
        with self.assertRaises(state_set.StateError):
            state_set.put(run, "base", "x")


if __name__ == "__main__":
    unittest.main()
