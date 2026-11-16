"""The memory budget (records/config.memory_budget) and the one sentence that says a memory file is over it
(records/memory.size_note)."""
from __future__ import annotations

import unittest

import support

from council.records import config, memory


class BudgetTest(support.Scratch):
    def home(self, text: str) -> str:
        self.write(".council/council.config.md", text)
        return (self.tmp / ".council").as_posix()

    def test_the_line_under_memory_in_kb(self) -> None:
        self.assertEqual(config.memory_budget(self.home("## Memory\n- memory budget: 40 KB\n")), (40960, "40 KB"))
        self.assertEqual(config.memory_budget(self.home("## Memory\n* memory budget: 1024kb <!-- max -->\r\n")),
                         (1048576, "1024kb"))
        self.assertEqual(config.memory_budget(self.home("## Memory\n- memory budget: 1\n")), (1024, "1"))

    def test_the_default_without_the_line_or_outside_memory(self) -> None:
        self.assertEqual(memory.COUNCIL_MEMORY_SIZE_LIMIT, 25600)
        self.assertEqual(config.memory_budget(self.tmp / "none"), (25600, ""))
        self.assertEqual(config.memory_budget(self.home("## Run preferences\n- memory budget: 40 KB\n")), (25600, ""))
        self.assertEqual(config.memory_budget(self.home("## Memory\n- conventions: c.md\n")), (25600, ""))

    def test_words_it_cant_read_are_the_default_with_the_words_kept(self) -> None:
        for raw in ("lots", "0 KB", "1025 KB", "40 MB", "4.5 KB", "-3", "40 KB each"):
            with self.subTest(raw=raw):
                self.assertEqual(config.memory_budget(self.home("## Memory\n- memory budget: %s\n" % raw)),
                                 (25600, raw))
                self.assertIsNone(config.memory_kb(raw))

    def test_the_conventions_line_still_reads_beside_it(self) -> None:
        home = self.home("## Memory\n- memory budget: 30 KB\n- conventions: docs/c.md\n")
        self.assertEqual(config.memory_line(home), ("docs/c.md", "docs/c.md"))


class SizeNoteTest(support.Scratch):
    def note(self, config_text: str, size: int) -> str:
        self.write(".council/council.config.md", config_text)
        self.write(".council/conventions.md", "x" * size)
        return memory.size_note((self.tmp / ".council").as_posix())

    def test_over_the_budget_rounded_by_thousands(self) -> None:
        self.assertEqual(self.note("# c\n", 30000), "conventions.md is 30 KB, over the ~25 KB the council expects — "
                         "every run reads it; at Learn, propose a consolidation (council memory tidy lists the merges "
                         "and retirements it finds)")
        self.assertEqual(self.note("# c\n", 25600), "")
        self.assertTrue(self.note("# c\n", 25601).startswith("conventions.md is 26 KB, over the ~25 KB"))

    def test_a_configured_budget_and_one_it_cant_read(self) -> None:
        self.assertEqual(self.note("## Memory\n- memory budget: 40 KB\n", 30000), "")
        self.assertTrue(self.note("## Memory\n- memory budget: 20 KB\n", 30000).startswith(
            "conventions.md is 30 KB, over the ~20 KB the council expects — every run reads it"))
        self.assertIn("over the ~25 KB the council expects (the config's memory budget, 'big', is not a whole number "
                      "of KB from 1 to 1024, so the default holds) — every run",
                      self.note("## Memory\n- memory budget: big\n", 30000))

    def test_oversized_takes_the_budget(self) -> None:
        path = self.write("m.md", "x" * 100).as_posix()
        self.assertEqual(memory.oversized(path, 99), 100)
        self.assertEqual(memory.oversized(path, 100), 0)
        self.assertEqual(memory.oversized((self.tmp / "none.md").as_posix(), 0), 0)


if __name__ == "__main__":
    unittest.main()
