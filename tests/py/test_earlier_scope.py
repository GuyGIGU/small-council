"""How a scope matches (records/scope.py), earlier council work on some paths (records/earlier.py) and the C-locale
text both read (records/bytewise.py)."""
from __future__ import annotations

import os
import unittest

import support

from council.records import bytewise, earlier, scope


class BytewiseTest(unittest.TestCase):
    def test_each_byte_is_one_character_and_comes_back(self) -> None:
        text = bytewise.read("café\n".encode("utf-8"))
        self.assertEqual(len(text), 6)
        self.assertEqual(bytewise.bytes_of(text), "café\n".encode("utf-8"))
        self.assertEqual(bytewise.shown(text), "café\n")
        self.assertEqual(bytewise.text("café"), text[:-1])

    def test_only_ascii_letters_change_case_and_blanks_are_space_and_tab(self) -> None:
        self.assertEqual(bytewise.lower("AB\xc3\x89"), "ab\xc3\x89")
        self.assertEqual(bytewise.upper("ab\xe9"), "AB\xe9")
        self.assertEqual(bytewise.trim(" \tx \t"), "x")
        self.assertEqual(bytewise.trim("\rx\r"), "\rx\r")

    def test_records_split_as_awk_reads_a_file(self) -> None:
        self.assertEqual(bytewise.records("a\nb"), ["a", "b"])
        self.assertEqual(bytewise.records("a\nb\n"), ["a", "b"])
        self.assertEqual(bytewise.records("a\r\nb\r\n"), ["a", "b"] if os.name == "nt" else ["a\r", "b\r"])


class ScopeTest(unittest.TestCase):
    def test_items_and_paths(self) -> None:
        self.assertEqual([i.text for i in scope.items("src/auth/**, `beck`, council-review (and its notes); a b")],
                         ["src/auth/**", "beck", "council-review", "a b"])
        self.assertEqual(scope.normp("'./src/x/'"), "src/x")
        self.assertEqual(scope.normp("res://scenes/a.tscn"), "scenes/a.tscn")
        self.assertEqual(scope.normp("src\\win\\a.py."), "src/win/a.py")
        self.assertEqual(scope.expand("src/{a,b}/*.py"), ["src/a/*.py", "src/b/*.py"])

    def test_covers_a_path_a_folder_and_a_slug(self) -> None:
        self.assertTrue(scope.covers("src/auth/x.py", "src/auth/**", ".*", False))
        self.assertFalse(scope.covers("src/authx.py", "src/auth", ".*", False))
        self.assertTrue(scope.covers("src", "src/auth/**", ".*", True))
        self.assertTrue(scope.covers("beck", "beck", "[^/]*", False))

    def test_every_run(self) -> None:
        self.assertEqual([scope.everyrun(s) for s in ("**", "all", "every run", "src/**")], [True, True, True, False])


class EarlierTest(support.Scratch):
    def setUp(self) -> None:
        super().setUp()
        self.write(".council/reviews/2026-01-01-a.md",
                   "---\nareas: src/auth/**\n---\n# R\nsee src/cache/x.py:4 for it\n")
        self.write(".council/plans/p.md", "# P\n" + "word " * 40 + "src/cache/x.py\n")
        self.home = (self.tmp / ".council").as_posix()

    def test_deliverables_folder_by_folder(self) -> None:
        self.assertEqual(earlier.deliverables(self.home), ["reviews/2026-01-01-a.md", "plans/p.md"])

    def test_a_line_that_names_a_path_or_areas_that_cover_it(self) -> None:
        hits = earlier.hits(self.home, ["src/cache/x.py", "src/auth/session.py", "nothing.py"])
        self.assertEqual(hits[0], "src/cache/x.py\treviews/2026-01-01-a.md:5\tsee src/cache/x.py:4 for it")
        self.assertEqual(hits[1], "src/auth/session.py\treviews/2026-01-01-a.md\t(its areas cover src/auth/**)")
        self.assertTrue(hits[2].startswith("src/cache/x.py\tplans/p.md:2\tword word") and
                        hits[2].endswith(bytewise.ELLIPSIS))
        self.assertEqual(len(hits), 3)
        self.assertEqual(earlier.line(hits[1]), bytewise.EM.join(hits[1].split("\t")).replace(
            bytewise.EM, " " + bytewise.EM + " "))

    def test_clip_cuts_at_a_space(self) -> None:
        clipped = earlier.clip("a " * 80)
        self.assertTrue(clipped.endswith(" " + bytewise.ELLIPSIS) and len(clipped) <= 120 + len(bytewise.ELLIPSIS) + 1)

    def test_the_paths_an_index_lists(self) -> None:
        run = self.run_folder()
        self.assertEqual(earlier.indexed(run), [])
        (run / "index.md").write_text("# Index\n## src/a.py  (modified)\nx\n## sp ace/b.py  (added)\n")
        self.assertEqual(earlier.indexed(run), ["src/a.py", "sp ace/b.py"])


if __name__ == "__main__":
    unittest.main()
