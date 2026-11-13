"""Seats that were agent runs with no token figure (records/usage_gaps.py), over the one per-seat rule."""
from __future__ import annotations

from typing import Any

import support

from council.records import usage, usage_gaps

HEAD = b"slug\tstate\tagent\ttokens\tupdated\tnote\tagents\treported\n"


class UnfiguredTest(support.Scratch):
    def gaps(self, rows: bytes, fixes: bytes = b"", skip: tuple[str, ...] = ()) -> dict[str, Any]:
        run = self.run_folder()
        (run / "seats.tsv").write_bytes(HEAD + rows)
        if fixes:
            (run / "corrections.jsonl").write_bytes(fixes)
        return {gap["seat"]: gap for gap in usage_gaps.unfigured(usage.seat_list(run), skip)}

    def test_only_agent_runs_without_a_trusted_figure_are_gaps(self) -> None:
        got = self.gaps(b"rep\tdone\ta\t52000\tT\t\t1\t1\n"            # reported: a figure
                        b"part\tdone\tabcdef123456\t40000\tT\t\t2\t1\n"  # one of two agent runs without usage
                        b"miss\tfailed\tabcdef123456\t\tT\t\t1\t0\n"     # finished, no usage report
                        b"pend\trunning\ta\t\tT\t\t1\t0\n"               # still working: not yet a gap
                        b"none\tdone\t\t\tT\t\t0\t0\n"                   # the Chair did it: not an agent run
                        b"unrec\tdone\t\t\tT\t\t\t0\n"                   # no agent on record
                        b"sus\tdone\ta\t500\tT\t\t1\t1\n"                # a figure no agent run has
                        b"old\tdone\ta\t9000\tT\t\t0\n"                  # an older row: not judged here
                        b"q\tqueued\t\t\tT\t\t\t0\n")                    # never ran
        self.assertEqual(sorted(got), ["miss", "part", "sus", "unrec"])
        self.assertEqual({seat: gap["kind"] for seat, gap in got.items()},
                         {"miss": usage_gaps.NO_REPORT, "part": usage_gaps.NO_REPORT, "sus": usage_gaps.UNUSABLE,
                          "unrec": usage_gaps.NO_ID})

    def test_each_gap_says_why(self) -> None:
        got = self.gaps(b"miss\tdone\tabcdef123456\t\tT\t\t1\t0\n"
                        b"part\tdone\tabcdef123456\t40000\tT\t\t3\t1\n"
                        b"noid\tdone\t\t\tT\t\t1\t0\n"
                        b"unrec\tdone\t\t\tT\t\t\t0\n")
        self.assertEqual(got["miss"]["why"], "agent abcdef1234 finished with no usage report")
        self.assertEqual(got["part"]["why"], "2 of 3 agent runs have no usage report")
        self.assertIn("no agent id recorded", got["noid"]["why"])
        self.assertIn("no agent id recorded", got["unrec"]["why"])

    def test_a_correction_with_evidence_makes_the_figure(self) -> None:
        fix = b'{"schema":1,"seat":"miss","field":"tokens","from":"","to":61000,"evidence":"line 4 of a transcript"}\n'
        self.assertEqual(self.gaps(b"miss\tdone\tabcdef123456\t\tT\t\t1\t0\n", fix), {})

    def test_the_chair_is_skipped(self) -> None:
        rows = b"chair\tdone\t\t\tT\t\t\t0\nlead\tdone\t\t\tT\t\t\t0\nw1\tdone\t\t\tT\t\t\t0\n"
        self.assertEqual(sorted(self.gaps(rows, skip=tuple(usage_gaps.chairs({"lead": "chair", "w1": "worker"})))),
                         ["w1"])
        self.assertEqual(usage_gaps.chairs({}), {"chair"})

    def test_words_name_each_seat_and_count_the_rest(self) -> None:
        gaps = [{"seat": "s%d" % n, "why": "w"} for n in range(8)]
        self.assertEqual(usage_gaps.words(gaps[:2]), "s0 (w); s1 (w)")
        self.assertTrue(usage_gaps.words(gaps).endswith("s5 (w); and 2 more"))


class LeftOutTest(support.Scratch):
    made = 0

    def snapshot(self, rows: bytes, plan: dict[str, Any] | None = None) -> dict[str, Any]:
        self.made += 1
        run = self.run_folder("2026-01-02-0304%02d-council-review" % self.made)
        (run / "seats.tsv").write_bytes(HEAD + rows)
        return {"seats": usage.seat_list(run), "plan": {"seats": plan or {}}}

    def test_seats_runs_and_kinds_across_completed_runs(self) -> None:
        bad = self.snapshot(b"a\tdone\tabcdef123456\t\tT\t\t1\t0\nb\tdone\t\t\tT\t\t\t0\nchair\tdone\t\t\tT\t\t\t0\n")
        good = self.snapshot(b"a\tdone\tx\t52000\tT\t\t1\t1\n")
        gone = usage_gaps.left_out([bad, good])
        self.assertEqual(gone, {"seats": 2, "runs": 1, "kinds": {"no agent id recorded": 1, "no usage report": 1}})
        self.assertEqual(usage_gaps.left_out([good]), {"seats": 0, "runs": 0, "kinds": {}})

    def test_the_plans_chair_is_not_counted(self) -> None:
        snap = self.snapshot(b"lead\tdone\t\t\tT\t\t\t0\n", {"lead": {"role": "chair"}})
        self.assertEqual(usage_gaps.left_out([snap])["seats"], 0)

    def test_the_note_is_one_line_or_none(self) -> None:
        self.assertEqual(usage_gaps.note({"seats": 0, "runs": 0, "kinds": {}}), [])
        line = usage_gaps.note({"seats": 3, "runs": 2, "kinds": {"no agent id recorded": 1, "no usage report": 2}})
        self.assertEqual(len(line), 1)
        self.assertIn("3 seat(s) in 2 completed run(s)", line[0])
        self.assertIn("(1 no agent id recorded, 2 no usage report)", line[0])


if __name__ == "__main__":
    import unittest
    unittest.main()
