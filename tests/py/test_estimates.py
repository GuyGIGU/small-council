"""The `- estimates:` line (issue 44): read like `- models:`, and each mode's roles."""
from __future__ import annotations

import unittest
from pathlib import Path

import support

from council.records import estimates


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


class RolesTest(unittest.TestCase):
    def test_a_mode_gives_its_workers_and_its_verifiers_a_role(self) -> None:
        self.assertEqual(estimates.mode_roles("council-review"), ("review", "verifier"))
        self.assertEqual(estimates.mode_roles("plan"), ("plan", "verifier"))
        self.assertEqual(estimates.mode_roles("council-implement"), ("builder", "converge"))
        self.assertEqual(estimates.mode_roles("council-research"), ("", "verifier"))


if __name__ == "__main__":
    unittest.main()
