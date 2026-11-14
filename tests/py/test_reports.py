"""The pieces behind council fingerprint, map status, ledger and ask save: the stack summary's sums, the map's
stamp and areas, the ledger's cells as awk read them, a filed request's sections, and the one-line fields."""
from __future__ import annotations

import os
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


class LedgerTest(support.Scratch):
    def test_cells_as_awk_reads_them(self) -> None:
        self.assertEqual([ledger_command.number(c) for c in ("12abc", "-3.5", "x", "")], [12.0, -3.5, 0.0, 0.0])
        self.assertEqual([ledger_command.above_zero(c) for c in ("1", "0", "x", "-1", "")],
                         [True, False, True, False, False])

    def test_raw_rows_keep_the_header_and_every_line(self) -> None:
        self.assertIsNone(ledger.raw_rows(self.tmp))
        self.write("ledger.tsv", b"date\trun\tseat\r\n2026\tr1\thunt\r\n\r\nx\n", binary=True)
        cr = "" if os.name == "nt" else "\r"           # Git Bash's awk read a CR LF as LF
        self.assertEqual(ledger.raw_rows(self.tmp), [["date", "run", "seat" + cr], ["2026", "r1", "hunt" + cr],
                                                     [cr], ["x"]])


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

    def test_field_reads_the_first_key_line(self) -> None:
        self.assertEqual(cells.field("title: x\nmode:  review  \nmode: other\n", "mode"), "review  ")
        self.assertEqual(cells.field("a\n", "mode"), "")


if __name__ == "__main__":
    unittest.main()
