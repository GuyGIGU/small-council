"""How a scope matches (records/scope.py), earlier council work on some paths (records/earlier.py) and the C-locale
text both read (records/bytewise.py)."""
from __future__ import annotations

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
        self.assertEqual(bytewise.records("a\r\nb\r\n"), ["a", "b"])           # on every OS
        self.assertEqual(bytewise.records("a\r\nb\r"), ["a", "b\r"])            # an unterminated last line keeps its CR
        self.assertEqual(bytewise.records(""), [])
        self.assertEqual(bytewise.records("\n"), [""])

    def test_records_keep_the_carriage_return_everywhere_when_not_folded(self) -> None:
        self.assertEqual(bytewise.records("a\r\nb\r\n", fold=False), ["a\r", "b\r"])
        self.assertEqual(bytewise.records("a\r\nb", fold=False), ["a\r", "b"])


    def test_clip_cuts_at_the_last_space_or_at_the_width(self) -> None:
        self.assertEqual(bytewise.clip("aaa bbb", 7), "aaa bbb")
        self.assertEqual(bytewise.clip("aaa bbb ccc", 9), "aaa bbb " + bytewise.ELLIPSIS)
        self.assertEqual(bytewise.clip("aaaaaaaaaa", 4, "…"), "aaaa …")


class FileLinesTest(support.Scratch):
    def test_a_file_reads_as_utf8_with_a_stray_byte_kept_and_its_bom_off(self) -> None:
        file = self.write("f.txt", b"\xef\xbb\xbfcaf\xc3\xa9\r\n\xff\n", binary=True)
        self.assertEqual(bytewise.file_lines(file), ["café", "\udcff"])
        self.assertEqual(bytewise.file_lines(file, fold=False), ["café\r", "\udcff"])

    def test_an_unreadable_file_has_no_lines(self) -> None:
        self.assertEqual(bytewise.file_lines(self.tmp / "missing"), [])
        self.assertEqual(bytewise.file_lines(self.tmp), [])


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
        self.assertEqual(hits[0], ("src/cache/x.py", "reviews/2026-01-01-a.md:5", "see src/cache/x.py:4 for it"))
        self.assertEqual(hits[1], ("src/auth/session.py", "reviews/2026-01-01-a.md", "(its areas cover src/auth/**)"))
        self.assertEqual(hits[2][:2], ("src/cache/x.py", "plans/p.md:2"))
        self.assertTrue(hits[2].text.startswith("word word") and hits[2].text.endswith(bytewise.ELLIPSIS))
        self.assertEqual(len(hits), 3)
        self.assertEqual(earlier.line(hits[1]), (" %s " % bytewise.EM).join(
            ["src/auth/session.py", "reviews/2026-01-01-a.md", "(its areas cover src/auth/**)"]))

    def test_a_mentioned_line_with_a_tab_is_shown_whole_and_a_path_is_taken_as_given(self) -> None:
        self.write(".council/logs/t.md", "# L\nsee src/t.py\tand then\tmore\n")
        found = [hit for hit in earlier.hits(self.home, ["src/t.py"]) if hit.where.startswith("logs/")]
        self.assertEqual(found, [("src/t.py", "logs/t.md:2", "see src/t.py\tand then\tmore")])
        self.assertEqual(earlier.hits(self.home, ["src/t.py\nsrc/cache/x.py"]), [])
        self.assertEqual(earlier.hits(self.home, ["", ""]), [])

    def test_clip_cuts_at_a_space(self) -> None:
        clipped = bytewise.clip("a " * 80, 120)
        self.assertTrue(clipped.endswith(" " + bytewise.ELLIPSIS) and len(clipped) <= 120 + len(bytewise.ELLIPSIS) + 1)

    def test_the_paths_an_index_lists(self) -> None:
        run = self.run_folder()
        self.assertEqual(earlier.indexed(run), [])
        (run / "index.md").write_text("# Index\n## src/a.py  (modified)\nx\n## sp ace/b.py  (added)\n")
        self.assertEqual(earlier.indexed(run), ["src/a.py", "sp ace/b.py"])


if __name__ == "__main__":
    unittest.main()
