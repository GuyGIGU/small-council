import contextlib
import io
import unittest
from pathlib import Path

import support

from council.records import config, sharing

config.hush()          # a reader's note on stderr is one test's business (test_a_reader_says_once_what_it_used)


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
        self.assertEqual(sharing.sharing(home), "team")
        self.assertEqual(config.gate_time_limit(home), (None, ""))
        self.assertFalse(config.notifications_off(home))
        self.assertIsNone(config.memory_line(home))
        self.assertEqual(config.old_roster(home), [])

    def test_an_old_context_packs_line_changes_nothing(self) -> None:
        """Context packs were removed on 2026-11-15: a config that still says `context packs: on` reads as one
        without the line."""
        prefs = "## Run preferences\n- agent cap: 6\n- build tier: full\n- seat models: on\n- sharing: just me\n"
        readers = (config.agent_cap, config.build_tier, config.checking,
                   sharing.sharing, config.gate_time_limit, config.notifications_off, config.memory_line,
                   config.old_roster)
        without = [reader(self.home(prefs)) for reader in readers]
        self.assertEqual([reader(self.home(prefs + "- context packs: on\n")) for reader in readers], without)

    def test_agent_cap(self) -> None:
        lower = self.home("## Run preferences\n  - agent cap: 7 (lower)\r\n- agent cap: 3\n")
        self.assertEqual(config.agent_cap(lower), 7)
        self.assertEqual(config.agent_cap(self.home("- agent cap: 0\n")), 10)
        self.assertEqual(config.agent_cap(self.home("- agent cap: 99999999999999999999\n")), 10)
        self.assertEqual(config.agent_cap(self.home("- agent cap: many\n- agent cap: 4\n")), 10)   # the first counts
        self.assertEqual(config.agent_cap(self.home("- agent cap: " + "9" * 5000 + "\n")), 10)   # past int()'s limit

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

    def test_estimate_per_worker(self) -> None:
        """No command reads the figure since route recommend went (1.2.0): the Chair does, and council doctor names
        a line it can't read, a CR at the end of the line no part of it."""
        def unread(line: str):
            return [p.said for p in config.problems(self.home(line))]
        for figure in ("150k", "120,000 tokens", "150000", "150,000", "0.9M"):
            self.assertEqual(unread("- estimate per worker: {}\n".format(figure)), [], figure)
            self.assertEqual(unread("- estimate per worker: {}\r\n".format(figure)), [], figure)
        for figure in ("500", "2M", "1,50k"):
            self.assertEqual(unread("- estimate per worker: {}\n".format(figure)), [figure], figure)

    def test_an_old_seat_models_line_changes_nothing(self) -> None:
        """`- seat models:` is no longer read (D74): a config that says `on` reads as one without the line, and the
        line is a retired key, not a bad value."""
        prefs = "## Run preferences\n- agent cap: 6\n- build tier: full\n- sharing: just me\n"
        readers = (config.agent_cap, config.build_tier, config.checking, sharing.sharing, config.old_roster,
                   config.problems)
        without = [reader(self.home(prefs)) for reader in readers]
        self.assertEqual([reader(self.home(prefs + "- seat models: on\n")) for reader in readers], without)
        self.assertIn("seat models", config.RETIRED)
        self.assertFalse(hasattr(config, "seat_models"))

    def test_sharing(self) -> None:
        for line, want in (("Just Me", "just me"), ("just-me (this laptop)", "just me"), ("private", "just me"),
                           ("team", "team"), ("just meh", "team"), ("", "team")):
            self.assertEqual(sharing.sharing(self.home("- sharing: {}\r\n".format(line))), want, line)

    def test_gate_time_limit(self) -> None:
        self.assertEqual(config.gate_time_limit(self.home("- gate time limit: 15 min\n")), (900, "15 min"))
        self.assertEqual(config.gate_time_limit(self.home("- gate time limit: 010\n")), (10, "010"))
        self.assertEqual(config.gate_time_limit(self.home("- gate time limit: soon\n")), (None, "soon"))
        self.assertIsNone(config.limit_seconds("0"))
        self.assertIsNone(config.limit_seconds("12345678"))
        self.assertEqual(config.limit_seconds("2 Hours"), 7200)


class OneLineReaderTest(support.Scratch):
    """Every setting through one `- key: value` reader (CODE-RECORDS-1, -2, -3): the key in any capitals, a `# note`
    or `(note)` after the value left out, the value in any capitals; a value it still can't read is named."""

    def home(self, text: str) -> Path:
        self.write(".council/council.config.md", text)
        return self.tmp / ".council"

    def test_capitals_and_notes(self) -> None:
        self.assertEqual(config.agent_cap(self.home("- Agent cap: 3\n")), 3)
        self.assertEqual(config.agent_cap(self.home("* agent CAP: 3  # tight\n")), 3)
        self.assertEqual(config.build_tier(self.home("- Build tier: full\n")), "full (config)")
        self.assertEqual(config.checking(self.home("- checking: per task  # risky\n")), "per task (config)")
        self.assertEqual(sharing.sharing(self.home("- Sharing: just me\n")), "just me")
        self.assertTrue(config.notifications_off(self.home("- NOTIFICATIONS: off (phone)\n")))
        self.assertEqual(config.gate_time_limit(self.home("- Gate time limit: 15m  # ci is slow\n")), (900, "15m"))
        self.assertEqual(config.problems(self.home("- Estimate per worker: 150k (measured)\n")), [])

    def test_headings_in_any_capitals_with_a_note(self) -> None:
        for head in ("## Hard rules", "## Hard Rules", "## HARD RULES", "## Hard rules (non-negotiable)"):
            self.assertEqual(config.hard_rules(self.home(head + "\n- never write to prod\n## Notes\n")),
                             ["- never write to prod"], head)
        roster = "## ROSTER (twelve)\n| Seat | Slug |\n|---|---|\n| Docs | doc |\n"
        self.assertEqual(config.old_roster(self.home(roster)), [""])      # one seat row, no Reference column

    def test_a_value_it_cannot_read_is_named(self) -> None:
        home = self.home("# c\n## Run preferences\n- agent cap: three\n- build tier: heavy\n- sharing: everyone\n"
                         "- pushes: on\n- open items: later\n- models: builder=gpt\n")
        self.assertEqual([(p.key, p.said, p.line) for p in config.problems(home)],
                         [("agent cap", "three", 3), ("build tier", "heavy", 4), ("sharing", "everyone", 5),
                          ("open items", "later", 7), ("models", "builder=gpt", 8)])
        template = (support.SRC.parent / "references" / "templates" / config.NAME).read_text(encoding="utf-8")
        self.assertEqual(config.problems(self.home(template)), [])

    def test_a_reader_says_once_what_it_used(self) -> None:
        config.speak()
        said = io.StringIO()
        with contextlib.redirect_stderr(said):
            self.assertEqual(config.agent_cap(self.home("- agent cap: three\n")), 10)
            config.agent_cap(self.tmp / ".council")
        config.hush()
        self.assertEqual(said.getvalue(), "council: council.config.md line 1, `- agent cap: three`, isn't a whole "
                         "number of agents, such as 10 — 10 is used; council doctor lists such lines\n")


class StatusReadingTest(support.Scratch):
    """The settings status.py reads, by its own rules."""

    def home(self, text: str) -> Path:
        self.write(".council/council.config.md", text)
        return self.tmp / ".council"

    def test_notifications_off(self) -> None:
        self.assertTrue(config.notifications_off(self.home("- Notifications: OFF  # quiet\n")))
        self.assertFalse(config.notifications_off(self.home("- notifications: on\n")))
        # the helper strips the carriage return first
        self.assertTrue(config.notifications_off(self.home("- notifications: off\r\n")))
        self.assertTrue(config.notifications_off(self.home("- notifications: off  # quiet\r\n")))
        self.assertFalse(config.notifications_off(self.home("- notifications: of\r\n")))

    def test_notifications_off_past_64_kb(self) -> None:
        """The helper reads the whole file: a switch past 64 KB is still off."""
        filler = "- note: " + "x" * 70000 + "\n"
        self.assertTrue(config.notifications_off(self.home(filler + "- notifications: off\n")))
        self.assertTrue(config.notifications_off(self.home(filler.replace("\n", "\r\n") + "- notifications: off\r\n")))
        self.assertFalse(config.notifications_off(self.home(filler + "- notifications: on\n")))

    def test_memory_line(self) -> None:
        """The one reading of the memory path (records/memory.locate builds on it): the key is exact, lower case."""
        self.assertEqual(config.memory_line(self.home("## Memory\n- conventions: docs/conv.md (the team's)\n")),
                         ("docs/conv.md", "docs/conv.md"))
        self.assertIsNone(config.memory_line(self.home("## Memory notes\n* Conventions: docs/c.md — by hand\n")))
        self.assertIsNone(config.memory_line(self.home("- conventions: elsewhere.md\n")))

    def test_roster(self) -> None:
        table = ("| Seat | Slug | Lens |\n|---|---|---|\n| **Security** | `sec` | *auth* |\n| | x | y |\n"
                 "| Docs | doc | |\n")
        self.assertEqual(config.old_roster(self.home("## Roster\n" + table)), ["", ""])   # two seat rows (D72)
        self.assertEqual(config.old_roster(self.home("## Seats\n" + table)), [])     # only under ## Roster


class EstimateTokensTest(unittest.TestCase):
    def test_estimate_tokens(self) -> None:
        self.assertIsNone(config.estimate_tokens("1,50k"))
        self.assertEqual(config.estimate_tokens("150,000"), 150000)
        self.assertEqual(config.estimate_tokens("1.5k"), 1500)
        self.assertIsNone(config.estimate_tokens("150 000"))
        self.assertIsNone(config.estimate_tokens("999"))
        self.assertIsNone(config.estimate_tokens("9" * 400 + "k"))


class RosterRowsTest(support.Scratch):
    def test_rows_as_the_helper_read_them(self) -> None:
        self.write(".council/council.config.md", "﻿# c\r\n## Roster\r\n"
                   "| Seat | Slug | Lens | Reference | Recast note |\r\n|---|---|---|---|---|\r\n"
                   "| **Martin Fowler** | `fowler` | Structure | references/refactoring.md | kept |\r\n"
                   "| No Slug |  | x |  | x |\r\n| <placeholder> | x | x | x | x |\r\n"
                   "| Café Seat | café | x | - | x |\r\n|  | ghost | x | x | x |\r\n## Gates\r\n| Gate | x |\r\n")
        self.assertEqual(config.old_roster(self.tmp / ".council"),      # each seat row's Reference cell, all that
                         ["references/refactoring.md", "", ""])         # council doctor reads of a roster (D76)

    def test_no_roster_and_no_config(self) -> None:
        self.assertEqual(config.old_roster(self.tmp / ".council"), [])
        self.write(".council/council.config.md", "# c\n## Roster\nnone\n")
        self.assertEqual(config.old_roster(self.tmp / ".council"), [])


if __name__ == "__main__":
    unittest.main()
