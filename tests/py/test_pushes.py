from __future__ import annotations

import unittest
from datetime import date

import support

from council.records import pushes

TODAY = date(2026, 11, 13)
HELD = "push and PR held by the freeze"


class PushesTest(support.Scratch):
    """The `- pushes:` reader: on, off, off until a date; anything else is on, and the reading says why."""

    def read(self, text: str) -> tuple[str, str]:
        self.write(".council/council.config.md", text)
        return pushes.pushes(self.tmp / ".council", TODAY)

    def test_missing_and_on(self) -> None:
        self.assertEqual(pushes.pushes(self.tmp / "none", TODAY), ("", "on (default)"))
        self.assertEqual(pushes.pushes(None, TODAY), ("", "on (default)"))
        self.assertEqual(self.read("# Council config\n"), ("", "on (default)"))
        self.assertEqual(self.read("- pushes: on\n"), ("", "on (config)"))

    def test_off_holds_push_and_pr(self) -> None:
        self.assertEqual(self.read("## Run preferences\n  - pushes:  OFF  <!-- a team freeze -->\r\n- pushes: on\n"),
                         (HELD, "off (config)"))

    def test_off_until_a_date(self) -> None:
        self.assertEqual(self.read("- pushes: off until 2026-11-14\n"),
                         (HELD + " until 2026-11-14", "off until 2026-11-14 (config)"))
        self.assertEqual(self.read("- pushes: Off  Until 2026-11-13\n"),      # from the date on, pushes are on
                         ("", "on (config: the freeze ended 2026-11-13)"))
        self.assertEqual(self.read("- pushes: off until 2026-01-05\n")[0], "")

    def test_a_value_it_cannot_read_is_on_and_says_so(self) -> None:
        for value in ("of", "off until next week", "off until 2026-02-30", "off until 2026-12-1", "Maybe"):
            unread = "on (default; '{}' is not a setting — on, off or off until <YYYY-MM-DD>)".format(value.lower())
            self.assertEqual(self.read("- pushes: {}\n".format(value)), ("", unread), value)

    def test_only_the_first_list_item_counts(self) -> None:
        self.assertEqual(self.read("- pushes:\n- pushes: off\n"), ("", "on (default)"))
        self.assertEqual(self.read("pushes: off\n"), ("", "on (default)"))


if __name__ == "__main__":
    unittest.main()
