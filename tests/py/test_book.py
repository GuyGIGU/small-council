"""The project's book (records/book.py, D52, D55): where each page is, and the one writer of a known-problems line."""
from __future__ import annotations

import unittest

import support

from council.records import book, paths

TEMPLATE = ("# Known problems — p\n<!-- about it,\n     - <YYYY-MM-DD>: an example in a comment -->\n\n"
            "## Found, not fixed\n<!-- - <YYYY-MM-DD>: <what> -->\n\n## Not to raise again\n<!-- - <the kind> -->\n")


class PagesTest(support.Scratch):
    def home(self, config: str) -> str:
        self.write(".council/council.config.md", config)
        return (self.tmp / ".council").as_posix()

    def test_defaults_under_the_home_and_the_memory_file_for_decisions(self) -> None:
        home = self.home("# c\n## Memory\n- conventions: docs/c.md\n")
        self.write("docs/c.md", "# memory\n")
        found = {page.name: page for page in book.pages(home)}
        self.assertEqual([page.name for page in book.pages(home)], list(book.PAGES))
        self.assertEqual(found["design"].path, home + "/design.md")
        self.assertEqual(found["known problems"].path, home + "/known-problems.md")
        self.assertEqual(found["decisions"].path, self.tmp.as_posix() + "/docs/c.md")
        self.assertTrue(found["decisions"].memory and found["decisions"].there)
        self.assertFalse(found["design"].there or found["design"].configured)

    def test_the_book_section_names_the_projects_own_files(self) -> None:
        home = self.home("# c\n## Book\n- design: `docs/architecture.md` (adopted)\n- Stack: ./STACK.md\n"
                         "- decisions: docs/adr\n- known problems: memory\n## Notes\n- design: elsewhere.md\n")
        self.write("docs/architecture.md", "# a\n")
        (self.tmp / "docs" / "adr").mkdir()
        found = {page.name: page for page in book.pages(home)}
        root = self.tmp.as_posix()
        self.assertEqual(found["design"].path, root + "/docs/architecture.md")
        self.assertTrue(found["design"].there and found["design"].configured)
        self.assertEqual(found["stack"].path, root + "/STACK.md")
        self.assertEqual(found["decisions"].path, root + "/docs/adr")
        self.assertTrue(found["decisions"].there and not found["decisions"].memory)
        self.assertEqual(found["known problems"].path, root + "/memory")   # only the decisions log takes the word

    def test_decisions_memory_word_is_the_memory_file(self) -> None:
        home = self.home("# c\n## Book\n- decisions: Memory\n")
        self.assertTrue(book.page(home, "decisions").memory)
        self.assertEqual(book.page(home, "decisions").path, home + "/conventions.md")


class AddTest(support.Scratch):
    def setUp(self) -> None:
        super().setUp()
        self.write(".council/council.config.md", "# c\n")
        self.home = (self.tmp / ".council").as_posix()
        self.file = self.tmp / ".council" / "known-problems.md"

    def test_the_first_line_makes_the_file_and_goes_under_its_section_above_the_comment(self) -> None:
        added = book.add(self.home, book.FOUND, "the total is off by one — a.py:3", TEMPLATE, "2026-11-19")
        self.assertTrue(added.made and not added.already)
        text = self.file.read_text(encoding="utf-8")
        self.assertIn("## Found, not fixed\n- 2026-11-19: the total is off by one — a.py:3\n<!-- -", text)
        book.add(self.home, book.FOUND, "a second", TEMPLATE, "2026-11-20")
        self.assertIn("a.py:3\n- 2026-11-20: a second\n<!--", self.file.read_text(encoding="utf-8"))

    def test_the_same_words_are_written_once_in_any_capitals_but_another_section_takes_them(self) -> None:
        book.add(self.home, book.FOUND, "Style nits", TEMPLATE, "2026-11-19")
        again = book.add(self.home, book.FOUND, "style nits ", TEMPLATE, "2026-11-20")
        self.assertTrue(again.already)
        self.assertFalse(book.add(self.home, book.WAIVED, "style nits", TEMPLATE, "2026-11-20").already)
        self.assertEqual(self.file.read_text(encoding="utf-8").count("tyle nits"), 2)

    def test_a_comment_line_is_no_entry(self) -> None:
        self.assertFalse(book.add(self.home, book.FOUND, "<what> -->", TEMPLATE, "2026-11-19").already)

    def test_crlf_kept_and_a_missing_section_added_at_the_end(self) -> None:
        self.file.write_bytes(b"# Known problems\r\n\r\n## Found, not fixed\r\n- 2026-01-01: old\r\n")
        book.add(self.home, book.WAIVED, "renames", TEMPLATE, "2026-11-19")
        self.assertEqual(self.file.read_bytes(), b"# Known problems\r\n\r\n## Found, not fixed\r\n- 2026-01-01: old\r\n"
                                                 b"\r\n## Not to raise again\r\n- 2026-11-19: renames\r\n")

    def test_a_path_outside_the_project_or_a_folder_is_refused(self) -> None:
        self.write(".council/council.config.md", "# c\n## Book\n- known problems: ../outside.md\n")
        with self.assertRaises(paths.RecordError):
            book.add(self.home, book.FOUND, "x", TEMPLATE, "2026-11-19")
        self.write(".council/council.config.md", "# c\n## Book\n- known problems: notes\n")
        (self.tmp / "notes").mkdir()
        with self.assertRaises(paths.RecordError):
            book.add(self.home, book.FOUND, "x", TEMPLATE, "2026-11-19")


if __name__ == "__main__":
    unittest.main()
