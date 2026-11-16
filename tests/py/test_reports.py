"""The pieces behind council fingerprint, map status, ledger and ask save: the stack summary's sums, the map's
stamp and areas, the ledger's cells as awk read them, a filed request's sections, and the one-line fields."""
from __future__ import annotations

import unittest

import support

from council.commands import fingerprint, ledger as ledger_command, map_status
from council.records import cells, ledger, map_file, request

ASK = (b"# Ask\r\n## In your words\r\nfirst\r\n## Summary\r\nkept\r\n## Later, in your words\r\n\r\nlater one\r\n"
       b"## 2026-01-01 \xe2\x80\x94 review, run 2026-01-01-101010-council-review\r\nx\r\n"
       b"## 2026-01-02 \xe2\x80\x94 review, run 2026-01-01-101010-council-review-2\r\n"
       b"## 2026-01-03 in my own words, run late\r\n")


class FingerprintTest(unittest.TestCase):
    def test_minus_lists_what_the_other_summary_lacks(self) -> None:
        self.assertEqual(fingerprint.minus("manifests: Makefile, go.mod · languages: go, py",
                                           "manifests: go.mod · languages: py"), "Makefile, go")
        self.assertEqual(fingerprint.minus("manifests: none · languages: none", "manifests: none · languages: none"),
                         "")

    def test_digest_is_git_hash_object_cut_to_twelve(self) -> None:
        self.assertEqual(fingerprint.digest("manifests: none · languages: none"), "e947b75bec95")


class MapTest(support.Scratch):
    def test_the_first_stamp_with_a_commit(self) -> None:
        self.assertEqual(map_file.commit(self.tmp), "")
        self.write("map.md", "# Map\nnote map-commit: zz\nmap-commit:  deadbeefcafe (built)\nmap-commit: 1234567\n")
        self.assertEqual(map_file.commit(self.tmp), "deadbeefcafe")
        self.write("map.md", "# Map\nmap-commit: xyz123\n")
        self.assertEqual(map_file.commit(self.tmp), "")

    def test_areas_busiest_first_the_home_left_out(self) -> None:
        self.assertEqual(map_status.by_area(["src/a.py", "src/b.py", "docs/x.md", "README.md", ".council/map.md",
                                             "tests/t.py", "tests/u.py"]),
                         ["     2  tests/", "     2  src/", "     1  docs/", "     1  README.md"])
        self.assertEqual(map_file.areas(["src/a.py", "docs/x.md", "src/b.py", ".council/map.md"]),
                         [("src/", 2), ("docs/", 1)])
        self.assertEqual(len(map_status.by_area(["a%d/x" % n for n in range(20)])), map_status.AREAS)

    def test_touch_adds_a_dated_section_and_leaves_the_rest(self) -> None:
        head, built = "f" * 40, "0" * 40
        table = map_file.TABLE + "\n| Job | Owner | The one way | Anchor path |\n|---|---|---|---|\n"
        before = "# Map\nmap-commit: %s (built)\nupdated: 2026-09-15\n\n%s| Parse | src/ | the reader | src/a.py |" % (
            built, table)
        self.write("map.md", before)
        touched = map_file.touch(self.tmp, [("src/", "moved")], head, ["src/", "docs/"], "2026-11-16")
        self.assertEqual(touched, map_file.Touched(False, ["docs/"]))
        after = (self.tmp / "map.md").read_text(encoding="utf-8")
        self.assertEqual(after, before + "\n\n## Changes 2026-11-16\n- src/: moved\n")
        self.assertEqual(map_file.ways(after), [map_file.Way("Parse", "src/", "the reader", "src/a.py")])
        touched = map_file.touch(self.tmp, [("docs/", "grew")], head, ["docs/"], "2026-11-16")
        self.assertEqual(touched, map_file.Touched(True, []))
        self.assertEqual((self.tmp / "map.md").read_text(encoding="utf-8"),
                         before.replace(built, head) + "\n\n## Changes 2026-11-16\n- src/: moved\n- docs/: grew\n")
        map_file.touch(self.tmp, [("src/", "again")], head, [], "2026-11-17")
        self.assertTrue((self.tmp / "map.md").read_text(encoding="utf-8").endswith(
            "- docs/: grew\n\n## Changes 2026-11-17\n- src/: again\n"))
        self.assertEqual(map_file.noted(self.tmp, "2026-11-17"), {"src/"})
        self.assertEqual(map_file.noted(self.tmp, "2026-11-16"), {"src/", "docs/"})

    def test_touch_keeps_crlf_and_the_stamps_own_words(self) -> None:
        self.write("map.md", "# Map\r\nmap-commit: abcdef1 (built)\r\n")
        map_file.touch(self.tmp, [("README.md", "said")], "e" * 40, [], "2026-11-16")
        self.assertEqual((self.tmp / "map.md").read_bytes(),
                         b"# Map\r\nmap-commit: " + b"e" * 40 + b" (built)\r\n\r\n## Changes 2026-11-16\r\n"
                         b"- README.md: said\r\n")


class LedgerTest(support.Scratch):
    def test_a_cell_that_is_not_a_number_adds_nothing(self) -> None:
        rows = [["date", "run", "mode", "seat", "raised", "kept", "cut", "refuted", "tokens", "basis"],
                ["d", "r1", "m", "hunt", "12abc", "1e3", "", "", "", ""],
                ["d", "r1", "m", "beck", "x", "2", "", "", "", ""]]
        lines = ledger_command.Table(rows, 10).lines()
        self.assertEqual(lines[1].split(), ["hunt", "1", "0", "0", "0", "0", "-", "-"])
        self.assertFalse(any(line.startswith("raised counts every run") for line in lines))  # "x" is not above 0

    def test_raw_rows_keep_the_header_and_every_line(self) -> None:
        self.assertIsNone(ledger.raw_rows(self.tmp))
        self.write("ledger.tsv", b"date\trun\tseat\r\n2026\tr1\thunt\r\n\r\nx\n", binary=True)
        self.assertEqual(ledger.raw_rows(self.tmp), [["date", "run", "seat"], ["2026", "r1", "hunt"], [""], ["x"]])


class RequestTest(support.Scratch):
    def test_words_and_later_byte_for_byte(self) -> None:
        self.assertEqual(request.ask_words(ASK), b"first\r\n## Summary\r\nkept\r\n")
        self.assertTrue(request.ask_later(ASK).startswith(b"later one\r\n## 2026-01-01"))
        self.assertEqual(request.lines_kept(b"a\nb"), [b"a\n", b"b"])

    def test_sections_are_a_run_folders_own(self) -> None:
        self.assertEqual(request.ask_sections(ASK), [9, 11])
        self.assertEqual(request.ask_sections(ASK, "2026-01-01-101010-council-review"), [9])

    def test_continued_from_the_state_else_ask_md(self) -> None:
        run = self.run_folder()
        (run / "session-state.md").write_text("status: in-progress\nask: \n# x\n")
        (run / "ask.md").write_text("# Ask\ncontinues: `<.council/asks/a b.md>` more\n")
        self.assertEqual(request.continued(run), ".council/asks/a")
        (run / "session-state.md").write_text("status: in-progress\nask: .council/asks/x.md\n")
        self.assertEqual(request.continued(run), ".council/asks/x.md")

    def test_filed_only_inside_the_projects_asks_folder(self) -> None:
        run = self.run_folder()
        inside = self.write(".council/asks/x.md", "# Ask\n")
        self.write("out.md", "# Ask\n")
        (run / "session-state.md").write_text("status: in-progress\n")
        (run / "ask.md").write_text("# Ask\ncontinues: .council/asks/x.md\n")
        self.assertEqual(request.filed(run), inside)
        for named in ("out.md", ".council/asks/../../out.md", str(self.tmp / "out.md")):
            (run / "session-state.md").write_text("status: in-progress\nask: %s\n" % named)
            self.assertIsNone(request.filed(run), named)
        elsewhere = self.tmp / "a" / "b" / "c"
        elsewhere.mkdir(parents=True)
        (elsewhere / "session-state.md").write_text("status: in-progress\nask: .council/asks/x.md\n")
        self.assertIsNone(request.filed(elsewhere))      # a run in no runs/ folder belongs to no project

    def test_filed_never_through_an_asks_folder_that_is_a_link(self) -> None:
        run = self.run_folder()
        self.write("real/x.md", "# Ask\n")
        support.symlink_or_skip(self, self.tmp / ".council" / "asks", self.tmp / "real", directory=True)
        (run / "session-state.md").write_text("status: in-progress\nask: .council/asks/x.md\n")
        self.assertIsNone(request.filed(run))

    def test_field_reads_the_first_key_line(self) -> None:
        self.assertEqual(cells.field("title: x\nmode:  review  \nmode: other\n", "mode"), "review  ")
        self.assertEqual(cells.field("a\n", "mode"), "")


if __name__ == "__main__":
    unittest.main()
