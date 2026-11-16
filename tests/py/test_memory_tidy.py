"""council memory tidy's two readings (commands/memory_tidy.py) over the parser's rows and the section each entry
sits under (records/memory.placed)."""
from __future__ import annotations

import unittest

import support

from council.commands import memory_tidy
from council.records import memory


class TidyTest(support.Scratch):
    def entries(self, text: str) -> list[tuple[str, str]]:
        return memory.placed(self.write("conventions.md", text).as_posix())

    def test_places_keep_the_section_a_retired_mark_hides(self) -> None:
        found = self.entries("## Accepted Patterns\n### AP-1: a\n**Retired:** yes\n## Retired\n### AP-2: b\n"
                             "**Retired:** 2026-10-30 — by AP-1\n")
        self.assertEqual([(row.split("\t")[5], section) for row, section in found],
                         [("marked retired", "## Accepted Patterns"), ("marked retired", "## Retired")])

    def test_the_same_rule_text_is_a_merge_into_the_first(self) -> None:
        found = self.entries("## Accepted Patterns\n- **AP-1 — Keep raw numbers.** text\n"
                             "- **AP-2 — keep  RAW numbers** other text\n- **AP-3 — keep raw numbers, rounded.**\n"
                             "### AP-4: Keep raw numbers\n## Proposed\n### AP-5: keep raw numbers\n")
        self.assertEqual(memory_tidy.merges(found), ["merge AP-2 into AP-1", "merge AP-4 into AP-1"])

    def test_a_rule_that_differs_is_no_merge(self) -> None:
        found = self.entries("## Accepted Patterns\n### AP-1: one title\n**Pattern:** a\n"
                             "### AP-2: one title\n**Pattern:** b\n")
        self.assertEqual(memory_tidy.merges(found), [])

    def test_retirements(self) -> None:
        found = self.entries("## Accepted Patterns\n### AP-1: follows EC-2 and AP-9\n### AP-2: kept\n"
                             "**Superseded by:** AP-1\n### AP-3: no mark\n**Retired:** no\n"
                             "## Retired\n### EC-2: gone\n**Retired:** 2026-10-30 — superseded by AP-1\n")
        self.assertEqual(memory_tidy.retirements(found), [
            "retire AP-1 \xe2\x80\x94 it names EC-2, which is retired",
            "retire AP-2 \xe2\x80\x94 marked retired, but it still sits under ## Accepted Patterns; move it under "
            "## Retired"])


if __name__ == "__main__":
    unittest.main()
