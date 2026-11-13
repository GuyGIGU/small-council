"""council route recommend: the advisory route, its refusals and its rows."""
from __future__ import annotations

import unittest

import support  # noqa: F401  (src/ on the path)

from council.commands import cli, route


def asked(*argv: str, cap: int = 10) -> route.Asked:
    return route.read(cli.parse(["route", "recommend", *argv]), cap)


def rows(*argv: str, cap: int = 10, per: int | None = None) -> dict[tuple[str, str, str], tuple[str, str]]:
    return {row[:3]: row[3:] for row in route.recommend(asked(*argv, cap=cap), per)}


class ReadTest(unittest.TestCase):
    def refused(self, *argv: str, cap: int = 10) -> str:
        with self.assertRaises(cli.Refusal) as caught:
            asked(*argv, cap=cap)
        return str(caught.exception)

    def test_refusals_come_in_the_helpers_order(self) -> None:
        self.assertEqual(self.refused("--risk", "huge"), "route recommend needs --task TEXT")
        self.assertEqual(self.refused("--task", " \t"), "route recommend needs --task TEXT")
        self.assertEqual(self.refused("--task", "x", "--agent-cap", "12"),
                         "--agent-cap cannot exceed the configured cap (10)")
        self.assertEqual(self.refused("--task", "x", "--agent-cap", "0000000"),
                         "--agent-cap must be between 1 and 9999999")
        self.assertEqual(self.refused("--task", "x", "--complexity", "abc"), "--complexity needs a positive integer")
        self.assertEqual(self.refused("--task", "x", "--complexity", "11"), "--complexity must be 1..10")
        self.assertEqual(self.refused("--task", "x", "--surface", " \t"), "--surface needs a non-empty name")
        self.assertEqual(self.refused("--task", "x", cap=12345678), "--agent-cap must be between 1 and 9999999")

    def test_values_are_kept_as_typed_and_cells_are_one_line(self) -> None:
        got = asked("--task", "a\tb\nc", "--agent-cap", "007", "--complexity", "05")
        self.assertEqual((got.task, got.cap, got.complexity), ("a b c", "007", "05"))


class SignalsTest(unittest.TestCase):
    def test_words_are_matched_whole_and_byte_by_byte(self) -> None:
        self.assertFalse(route.signals(asked("--task", "author a rapid note"))["security"])
        self.assertTrue(route.signals(asked("--task", "API-key leak"))["security"])
        self.assertTrue(route.signals(asked("--task", "access token"))["security"])
        self.assertFalse(route.signals(asked("--task", "access—token"))["security"])   # three bytes, three spaces

    def test_a_data_surface_counts_by_its_name(self) -> None:
        self.assertTrue(route.signals(asked("--task", "x", "--surface", "DB"))["data"])
        self.assertFalse(route.signals(asked("--task", "x", "--surface", "metadata"))["data"])


class RecommendTest(unittest.TestCase):
    def test_tiny_work_stays_solo(self) -> None:
        got = rows("--task", "tiny fix")
        self.assertEqual(got[("run", "route", "size")][0], "solo")
        self.assertEqual(got[("budget", "route", "selected-agents")][0], "0")
        self.assertEqual(got[("seat", "testing", "disposition")], ("skipped", "Solo uses no delegated agents"))
        self.assertEqual(got[("budget", "route", "estimated-tokens")], (
            "20000", "no-history estimate: 80k per selected agent plus 20k Chair; not measured or enforced"))

    def test_high_risk_work_goes_full_with_its_lenses(self) -> None:
        got = rows("--task", "rotate refresh tokens in the database", per=150000)
        self.assertEqual(got[("run", "route", "size")][0], "full")
        self.assertEqual(got[("verification", "route", "level")][0], "adversarial")
        self.assertEqual(got[("seat", "security", "disposition")],
                         ("selected", "task or surface indicates a security lens"))
        self.assertEqual(got[("seat", "architecture", "disposition")],
                         ("selected", "full council needs a structural lens"))
        self.assertEqual(got[("budget", "route", "estimated-tokens")][0], str(20000 + 5 * 150000 + 150000))

    def test_a_small_cap_shrinks_the_run_and_says_verification_cannot_fit(self) -> None:
        got = rows("--task", "delete production data", "--agent-cap", "2")
        self.assertEqual(got[("run", "route", "size")][0], "solo")
        self.assertEqual(got[("run", "route", "status")][0], "needs-rescope")
        self.assertEqual(got[("verification", "route", "status")][0], "unavailable")

    def test_a_cap_that_omits_a_wanted_lens_is_constrained(self) -> None:
        got = rows("--task", "auth db ui api latency", "--agent-cap", "5")
        self.assertEqual(got[("run", "route", "status")][0], "constrained")
        self.assertEqual(got[("seat", "performance", "disposition")],
                         ("skipped", "agent cap reserved for higher-priority lenses"))

    def test_a_ceiling_is_copied_and_can_force_a_rescope(self) -> None:
        got = rows("--task", "security audit", "--budget-tokens", "300000")
        self.assertEqual(got[("budget", "run", "token-ceiling")][0], "300000")
        self.assertEqual(got[("run", "route", "status")][0], "needs-rescope")

    def test_classic_keeps_its_fixed_roster(self) -> None:
        got = rows("--task", "auth db", "--classic")
        self.assertEqual(got[("run", "route", "policy")][0], "classic")
        self.assertEqual(got[("seat", "security", "disposition")],
                         ("skipped", "classic policy keeps a fixed implementation, testing and verification roster"))


if __name__ == "__main__":
    unittest.main()
