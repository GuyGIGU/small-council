"""The one per-seat usage rule and the agent stop's standing (records/usage.py)."""
from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

import support

from council.records import usage

HEAD = b"slug\tstate\tagent\ttokens\tupdated\tnote\tagents\treported\n"
PLANNED = "mode: council-review\nstatus: in-progress\nplan-schema: 1\n\n## Notes\n"


class SeatUsageTest(support.Scratch):
    def seats(self, rows: bytes, fixes: bytes = b"") -> dict[str, Any]:
        run = self.run_folder()
        (run / "seats.tsv").write_bytes(HEAD + rows)
        if fixes:
            (run / "corrections.jsonl").write_bytes(fixes)
        return {s["slug"]: s for s in usage.seat_list(run)}

    def test_each_basis(self) -> None:
        got = self.seats(b"rep\tdone\ta\t52000\tT\t\t1\t1\n"
                         b"part\tdone\ta\t40000\tT\t\t2\t1\n"
                         b"miss\tfailed\ta\t\tT\t\t1\t0\n"
                         b"pend\trunning\ta\t\tT\t\t1\t0\n"
                         b"none\tdone\t\t\tT\t\t0\t0\n"
                         b"unrec\tdone\t\t\tT\t\t\t0\n"
                         b"sus\tdone\ta\t500\tT\t\t1\t1\n"
                         b"old\tdone\ta\t9000\tT\t\t0\n"
                         b"q\tqueued\t\t\tT\t\t\t0\n")
        self.assertEqual({slug: s["tokens_basis"] for slug, s in got.items()},
                         {"rep": "reported", "part": "partial", "miss": "missing", "pend": "pending",
                          "none": "no-agent", "unrec": "unrecorded", "sus": "suspect", "old": "legacy", "q": "none"})
        self.assertEqual((got["part"]["tokens"], got["part"]["missing_runs"]), (40000, 1))
        self.assertEqual(got["pend"]["pending_runs"], 1)
        self.assertIsNone(got["sus"]["tokens"])
        self.assertEqual(got["old"]["agents_at_least"], 1)      # an older row counts at least one agent run

    def test_a_correction_lies_over_the_row_and_an_added_run_is_a_seat(self) -> None:
        fixes = (b'{"schema":1,"seat":"rep","field":"tokens","from":"52000","to":61000,"evidence":"line 4 of t"}\n'
                 b'{"schema":1,"seat":"lost","field":"agents","from":"","to":2,"added":true,"evidence":"line 9 of x"}\n'
                 b'{"schema":1,"seat":"rep","field":"agents","from":"1","to":3,"evidence":""}\n')
        got = self.seats(b"rep\tdone\ta\t52000\tT\t\t1\t1\n", fixes)
        self.assertEqual((got["rep"]["tokens"], got["rep"]["tokens_basis"], got["rep"]["agents"]),
                         (61000, "corrected", 1))         # the agents fix names no source: ignored
        self.assertEqual((got["lost"]["state"], got["lost"]["tokens_basis"], got["lost"]["agents"]),
                         ("done", "missing", 2))


class TotalsTest(support.Scratch):
    made = 0

    def totals(self, rows: bytes) -> dict[str, Any]:
        self.made += 1
        run = self.run_folder("2026-01-02-03040%d-council-review" % self.made)
        (run / "seats.tsv").write_bytes(HEAD + rows)
        return usage.usage_totals(usage.seat_list(run))

    def basis(self, rows: bytes) -> str:
        return str(self.totals(rows)["tokens"]["basis"])

    def test_the_least_complete_seat_sets_the_basis(self) -> None:
        self.assertEqual(self.basis(b"a\tdone\tx\t52000\tT\t\t1\t1\nb\tdone\tx\t9000\tT\t\t1\n"), "legacy")
        self.assertEqual(self.basis(b"a\tdone\tx\t500\tT\t\t1\t1\nb\tdone\t\t\tT\t\t\t0\n"), "suspect")
        self.assertEqual(self.basis(b"a\tdone\tx\t52000\tT\t\t1\t1\nb\tdone\t\t\tT\t\t\t0\n"), "partial")
        self.assertEqual(self.basis(b"a\trunning\tx\t52000\tT\t\t1\t1\n"), "running")
        self.assertEqual(self.basis(b"a\tdone\t\t\tT\t\t0\t0\n"), "none")
        self.assertEqual(self.basis(b""), "none")

    def test_a_complete_total_splits_workers_and_verifiers(self) -> None:
        done = self.totals(b"a\tdone\tx\t52000\tT\t\t1\t1\nverify-1\tdone\ty\t8000\tT\t\t1\t1\n")
        self.assertEqual((done["tokens"]["total"], done["tokens"]["workers"], done["tokens"]["verifiers"]),
                         (60000, 52000, 8000))
        self.assertEqual(done["agents"], {"total": 2, "at_least": 2, "basis": "exact"})


class TokenTextTest(unittest.TestCase):
    def test_half_up_and_m_from_995000(self) -> None:
        self.assertEqual([usage.token_text(n) for n in (0, 499, 500, 74304, 994999, 995000, 1049999, 1050000, 2000000)],
                         ["0k", "0k", "1k", "74k", "995k", "1M", "1M", "1.1M", "2M"])


class StandingTest(support.Scratch):
    def run_with(self, plan: str = "", state: str = PLANNED, rows: bytes = b"", starts: bytes = b"",
                 allowances: bytes = b"", name: str = "2026-01-02-030405-council-review") -> Path:
        run = self.run_folder(name)
        (run / "session-state.md").write_text(state, encoding="utf-8")
        if plan:
            (run / "run-plan.tsv").write_text("kind\tid\tfield\tvalue\treason\n" + plan, encoding="utf-8")
        (run / "seats.tsv").write_bytes(HEAD + rows)
        if starts:
            (run / "agent-starts.tsv").write_bytes(b"at\ttool\tsession\n" + starts)
        if allowances:
            (run / "cap-allowances.tsv").write_bytes(b"at\tused\tn\tuntil\tsaid\n" + allowances)
        return run

    def test_at_the_cap_is_over_and_stopped(self) -> None:
        run = self.run_with("budget\trun\tagent-cap\t2\t-\n", rows=b"a\tdone\tx\t52000\tT\t\t2\t2\n")
        self.assertEqual(usage.standing(run, self.tmp / ".council"),
                         usage.Standing(2, 2, 2, 52000, None, None, True, True))

    def test_a_go_covers_the_next_agent_and_starts_count_when_more(self) -> None:
        run = self.run_with("budget\trun\tagent-cap\t2\t-\n", rows=b"a\tdone\tx\t52000\tT\t\t1\t1\n",
                            starts=b"T\tAgent\ts\nT\tAgent\ts\n", allowances=b"T\t2\t2\t4\tgo on\n")
        got = usage.standing(run, self.tmp / ".council")
        self.assertEqual((got.used, got.recorded, got.until, got.over, got.stopped), (2, 1, 4, True, False))

    def test_past_the_ceiling_is_over_and_an_older_run_is_never_stopped(self) -> None:
        plan = "budget\trun\tagent-cap\t9\t-\nbudget\trun\ttoken-ceiling\t50000\t-\n"
        run = self.run_with(plan, rows=b"a\tdone\tx\t52000\tT\t\t1\t1\n")
        got = usage.standing(run, self.tmp / ".council")
        self.assertEqual((got.ceiling, got.over, got.stopped), (50000, True, True))
        older = self.run_with(plan, state="status: in-progress\n## Notes\nplan-schema: 1\n",   # below the header
                              rows=b"a\tdone\tx\t52000\tT\t\t1\t1\n", name="2026-01-02-030406-council-review")
        got = usage.standing(older, self.tmp / ".council")
        self.assertEqual((got.over, got.stopped), (True, False))

    def test_the_configured_cap_without_a_plan_cap(self) -> None:
        run = self.run_with()
        (self.tmp / ".council" / "council.config.md").write_text("- agent cap: 3\n", encoding="utf-8")
        self.assertEqual(usage.standing(run, self.tmp / ".council").cap, 3)
        self.assertEqual(usage.agent_cap(run, self.tmp / "nowhere"), 10)

    def test_budget_values(self) -> None:
        run = self.run_with("budget\trun\testimated-tokens\t0\t-\nbudget\trun\ttoken-ceiling\t0\t-\n"
                            "budget\trun\tchair-tokens\t9" + "9" * 20 + "\t-\n")
        self.assertEqual(usage.budget_value(run, "estimated-tokens"), 0)
        self.assertIsNone(usage.budget_value(run, "token-ceiling"))     # a zero ceiling is none
        self.assertIsNone(usage.budget_value(run, "chair-tokens"))      # past what bash reads


if __name__ == "__main__":
    unittest.main()
