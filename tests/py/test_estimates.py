"""The `- estimates:` line (issue 44): read like `- models:`, edited without touching its other pieces, and measured
from the ledger by role."""
from __future__ import annotations

import unittest
from pathlib import Path

import support

from council.records import estimates


def row(mode: str, seat: str, tokens: int | None, run: str = "r1") -> dict:
    return {"mode": mode, "seat": seat, "tokens": tokens, "run": run}


class ReadTest(support.Scratch):
    def home(self, text: str) -> Path:
        self.write(".council/council.config.md", text)
        return self.tmp / ".council"

    def test_each_role_reads_its_own_figure(self) -> None:
        line = "- estimates: Builder=450k, review = 100000 ,converge=60k <!-- measured -->\r\n"
        got = estimates.read(self.home(line))
        self.assertEqual(got, {"builder": 450000, "review": 100000, "converge": 60000})

    def test_no_line_a_wrong_role_and_an_unreadable_figure_read_as_nothing_for_that_role(self) -> None:
        self.assertEqual(estimates.read(self.home("- agent cap: 10\n")), {})
        self.assertEqual(estimates.read(self.tmp / "none"), {})
        odd = "- estimates: chair=90k, builder=2M, plan=1,50k, verifier=70k, review\n"
        self.assertEqual(estimates.read(self.home(odd)),
                         {"verifier": 70000})

    def test_the_first_line_and_the_first_piece_for_a_role_stand(self) -> None:
        got = estimates.read(self.home("- estimates: plan=90k, plan=300k\n- estimates: plan=500k, builder=400k\n"))
        self.assertEqual(got, {"plan": 90000})


class EditTest(unittest.TestCase):
    def test_a_role_is_added_to_the_line_and_its_comment_stays(self) -> None:
        text = "## Run preferences\n- agent cap: 10\n- estimates: review=100k  <!-- hand set -->\n"
        changed, record = estimates.with_role(text, "builder", "450k")
        self.assertEqual(changed, "## Run preferences\n- agent cap: 10\n"
                                  "- estimates: review=100k, builder=450k  <!-- hand set -->\n")
        self.assertEqual(record, {"before": "- estimates: review=100k  <!-- hand set -->",
                                  "after": "- estimates: review=100k, builder=450k  <!-- hand set -->",
                                  "inserted": None})
        self.assertEqual(estimates.figure(changed, "builder"), 450000)

    def test_a_role_already_there_is_replaced_in_place(self) -> None:
        changed, _ = estimates.with_role("- estimates: builder=300k, review=90k\n", "BUILDER".lower(), "450k")
        self.assertEqual(changed, "- estimates: builder=450k, review=90k\n")

    def test_no_line_inserts_one_as_the_last_item_of_run_preferences(self) -> None:
        text = "## Run preferences\n- agent cap: 10\n\n## Roster\n"
        changed, record = estimates.with_role(text, "plan", "90k")
        self.assertEqual(changed, "## Run preferences\n- agent cap: 10\n- estimates: plan=90k\n\n## Roster\n")
        self.assertEqual(record["before"], None)
        self.assertEqual(record["inserted"], "- estimates: plan=90k\n")

    def test_an_empty_line_takes_the_first_piece(self) -> None:
        changed, _ = estimates.with_role("- estimates:\n", "verifier", "70k")
        self.assertEqual(changed, "- estimates: verifier=70k\n")


class MeasuredTest(unittest.TestCase):
    def test_a_mode_gives_its_workers_and_its_verifiers_a_role(self) -> None:
        self.assertEqual(estimates.mode_roles("council-review"), ("review", "verifier"))
        self.assertEqual(estimates.mode_roles("plan"), ("plan", "verifier"))
        self.assertEqual(estimates.mode_roles("council-implement"), ("builder", "converge"))
        self.assertEqual(estimates.mode_roles("council-research"), ("", "verifier"))

    def test_workers_are_a_mean_per_agent_and_verifiers_one_figure_per_run(self) -> None:
        rows = [row("council-implement", "task-1", 400000), row("council-implement", "task-2", 600000),
                row("council-implement", "(verifiers)", 50000), row("council-implement", "task-1", 300000, "r2"),
                row("council-review", "security", 90000), row("council-review", "(verifiers)", 40000)]
        self.assertEqual(estimates.measured(rows),
                         {"builder": [500000, 300000], "converge": [50000], "review": [90000], "verifier": [40000]})

    def test_an_unknown_figure_is_left_out_never_counted_as_zero(self) -> None:
        rows = [row("council-implement", "task-1", None), row("council-implement", "task-2", 200000)]
        self.assertEqual(estimates.measured(rows), {"builder": [200000]})

    def test_a_mode_with_no_worker_role_adds_none(self) -> None:
        self.assertEqual(estimates.measured([row("council-research", "perf", 120000), row("-", "x", 5000)]), {})


if __name__ == "__main__":
    unittest.main()
