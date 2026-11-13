import unittest
from pathlib import Path

import support

from council.records import config


class ConfiguredTest(support.Scratch):
    """The configured_* readers, against what bin/council's functions print for the same file."""

    def home(self, text: str) -> Path:
        self.write(".council/council.config.md", text)
        return self.tmp / ".council"

    def test_defaults_without_a_config(self) -> None:
        home = self.tmp / "none"
        self.assertEqual(config.agent_cap(home), 10)
        self.assertEqual(config.agent_cap(None), 10)
        self.assertEqual(config.build_tier(home), "light (default)")
        self.assertEqual(config.checking(home), "one per batch (default)")
        self.assertIsNone(config.worker_estimate(home))
        self.assertEqual(config.seat_models(home), "off")
        self.assertEqual(config.sharing(home), "team")
        self.assertEqual(config.gate_time_limit(home), (None, ""))
        self.assertFalse(config.notifications_off(home))
        self.assertEqual(config.memory_path(home), "")
        self.assertEqual(config.roster(home), [])

    def test_agent_cap(self) -> None:
        lower = self.home("## Run preferences\n  - agent cap: 7 (lower)\r\n- agent cap: 3\n")
        self.assertEqual(config.agent_cap(lower), 7)
        self.assertEqual(config.agent_cap(self.home("- agent cap: 0\n")), 10)
        self.assertEqual(config.agent_cap(self.home("- agent cap: 99999999999999999999\n")), 10)
        self.assertEqual(config.agent_cap(self.home("- agent cap: many\n- agent cap: 4\n")), 4)

    def test_build_tier(self) -> None:
        self.assertEqual(config.build_tier(self.home("- build tier: FULL\n")), "full (config)")
        self.assertEqual(config.build_tier(self.home("- build tier: heavy\n")),
                         "light (default; 'heavy' is not a tier — light or full)")
        self.assertEqual(config.build_tier(self.home("- build tier:\n")), "light (default)")

    def test_checking(self) -> None:
        self.assertEqual(config.checking(self.home("- checking: Per  Task <!-- or one per batch -->\r\n")),
                         "per task (config)")
        self.assertEqual(config.checking(self.home("  - checking: one per batch\n- checking: per task\n")),
                         "one per batch (config)")
        self.assertEqual(config.checking(self.home("- checking: twice\n")),
                         "one per batch (default; 'twice' is not a setting — one per batch or per task)")
        self.assertEqual(config.checking(self.home("- checking:\n- checking: per task\n")), "one per batch (default)")

    def test_worker_estimate(self) -> None:
        self.assertEqual(config.worker_estimate(self.home("- estimate per worker: 150k\n")), 150000)
        self.assertEqual(config.worker_estimate(self.home("- estimate per worker: 120,000 tokens\r\n")), 120000)
        self.assertIsNone(config.worker_estimate(self.home("- estimate per worker: 500\n")))
        self.assertIsNone(config.worker_estimate(self.home("- estimate per worker: 2M\n")))
        self.assertIsNone(config.worker_estimate(self.home("- estimate per worker: 1,50k\n")))

    def test_worker_estimate_in_a_crlf_file_has_no_carriage_return_in_its_figure(self) -> None:
        """A line's CR is not part of its last cell: 150000 and 150,000 read as the helper reads them."""
        for figure in ("150000", "150,000", "150k", "0.9M"):
            lf = config.worker_estimate(self.home("- estimate per worker: {}\n".format(figure)))
            crlf = config.worker_estimate(self.home("- estimate per worker: {}\r\n".format(figure)))
            self.assertIsNotNone(crlf, figure)
            self.assertEqual(crlf, lf, figure)

    def test_seat_models_and_sharing(self) -> None:
        self.assertEqual(config.seat_models(self.home("- seat models: on\r\n")), "on")
        self.assertEqual(config.seat_models(self.home("- seat models: on # yes\n")), "off")
        self.assertEqual(config.seat_models(self.home("- seat models: On\n")), "off")
        for line, want in (("Just Me", "just me"), ("just-me (this laptop)", "just me"), ("private", "just me"),
                           ("team", "team"), ("just meh", "team"), ("", "team")):
            self.assertEqual(config.sharing(self.home("- sharing: {}\r\n".format(line))), want, line)

    def test_gate_time_limit(self) -> None:
        self.assertEqual(config.gate_time_limit(self.home("- gate time limit: 15 min\n")), (900, "15 min"))
        self.assertEqual(config.gate_time_limit(self.home("- gate time limit: 010\n")), (10, "010"))
        self.assertEqual(config.gate_time_limit(self.home("- gate time limit: soon\n")), (None, "soon"))
        self.assertIsNone(config.limit_seconds("0"))
        self.assertIsNone(config.limit_seconds("12345678"))
        self.assertEqual(config.limit_seconds("2 Hours"), 7200)


class StatusReadingTest(support.Scratch):
    """The settings status.py reads, by its own rules."""

    def home(self, text: str) -> Path:
        self.write(".council/council.config.md", text)
        return self.tmp / ".council"

    def test_notifications_off(self) -> None:
        self.assertTrue(config.notifications_off(self.home("- Notifications: OFF  # quiet\n")))
        self.assertFalse(config.notifications_off(self.home("- notifications: on\n")))
        self.assertTrue(config.notifications_off(self.home("- notifications: off\r\n")))    # the helper strips the CR first
        self.assertTrue(config.notifications_off(self.home("- notifications: off  # quiet\r\n")))
        self.assertFalse(config.notifications_off(self.home("- notifications: of\r\n")))

    def test_memory_path(self) -> None:
        self.assertEqual(config.memory_path(self.home("## Memory\n- conventions: docs/conv.md (the team's)\n")),
                         "docs/conv.md")
        self.assertEqual(config.memory_path(self.home("## Memory notes\n* Conventions: docs/c.md — by hand\n")),
                         "docs/c.md")
        self.assertEqual(config.memory_path(self.home("- conventions: elsewhere.md\n")), "")

    def test_roster(self) -> None:
        home = self.home("| Seat | Slug | Lens |\n|---|---|---|\n| Security | `sec` | auth |\n| | x | y |\n\n| a |\n")
        self.assertEqual(config.roster(home), [("Security", "sec", "auth")])


class TuneEditTest(support.Scratch):
    def test_editable_refuses_what_tune_must_not_edit(self) -> None:
        with self.assertRaisesRegex(config.ConfigError, "run council-init"):
            config.editable(self.tmp)
        self.write("council.config.md", "x" * (1024 * 1024 + 1))
        with self.assertRaisesRegex(config.ConfigError, "over 1 MB"):
            config.editable(self.tmp)
        self.write("council.config.md", "ok\n")
        self.assertEqual(config.editable(self.tmp), (self.tmp / "council.config.md", "ok\n"))

    def test_estimate_line_and_tokens(self) -> None:
        self.assertEqual(config.estimate_line("a\n  - estimate per worker: 150k (measured)\nb"),
                         (150000, "  - estimate per worker: 150k (measured)"))
        self.assertEqual(config.estimate_line("- estimate per worker: lots\n"), (None, "- estimate per worker: lots"))
        self.assertEqual(config.estimate_line("nothing\n"), (None, None))
        self.assertEqual(config.estimate_tokens("1,50k"), 150000)       # tune's reading; the route's is None
        self.assertIsNone(config.estimate_tokens("999"))

    def test_preferences_insertion(self) -> None:
        text = "## Run preferences\n- agent cap: 10\n<!-- - hidden: x -->\n## Gates\n"
        at, piece = config.preferences_insertion(text, "- estimate per worker: 90k")
        self.assertEqual(text[:at] + piece + text[at:],
                         "## Run preferences\n- agent cap: 10\n- estimate per worker: 90k\n"
                         "<!-- - hidden: x -->\n## Gates\n")
        with self.assertRaises(config.ConfigError):
            config.preferences_insertion("## Gates\n", "- x")


if __name__ == "__main__":
    unittest.main()
