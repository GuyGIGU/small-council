"""The citation reader (records/citations.py) and the quote reader (records/quotes.py) that `council check` and
`council collect` read seat files with (S7). Their outputs were compared with bin/council's awk on generated
inputs when they were ported; these pin the rules a reader of the code would expect."""
from __future__ import annotations

import unittest

import support

from council.records import citations, quotes


class ParseTest(unittest.TestCase):
    def test_a_path_with_lines_and_one_without(self) -> None:
        self.assertEqual(citations.parse("src/a.py:12"), [("L", "src/a.py", "12")])
        self.assertEqual(citations.parse("README.md"), [("P", "README.md")])
        self.assertEqual(citations.parse("a.py:12..14 and 20"), [("L", "a.py", "12-14,20")])

    def test_nothing_to_check_says_why(self) -> None:
        self.assertEqual(citations.parse("-"), [("N", "-")])
        self.assertEqual(citations.parse("npm test"), [("N", "no path")])
        self.assertEqual(citations.parse("https://x.y/z"), [("N", "link")])

    def test_a_line_part_it_cannot_read(self) -> None:
        self.assertEqual(citations.parse("a.py:5x"), [("U", "a.py:5x")])

    def test_a_whole_field_with_a_blank_is_used_only_when_it_is_there(self) -> None:
        self.assertEqual(citations.parse("my dir/a b.py:3"), [("WL", "my dir/a b.py", "3"), ("L", "b.py", "3")])
        self.assertEqual(citations.rows("/nowhere-at-all", "my dir/a b.py:3"), [("L", "b.py", "3")])


class LinesTest(unittest.TestCase):
    def test_ranges_and_their_verdicts(self) -> None:
        self.assertEqual(citations.ranges("7-9,40"), [(7, 9), (40, 40)])
        self.assertIsNone(citations.ranges("9-7"))
        self.assertIsNone(citations.ranges("5", 4))
        self.assertEqual(citations.line_verdict("3", 10), "ok")
        self.assertEqual(citations.line_verdict("0", 10), "bad-line (there is no line 0)")
        self.assertEqual(citations.line_verdict("9-7", 10), "bad-line (9-7 runs backwards)")
        self.assertEqual(citations.line_verdict("12", 10), "bad-line (the file has 10 lines)")

    def test_numbers_read_as_bash_test_reads_them(self) -> None:
        self.assertEqual([citations.bash_int(t) for t in (" 12 ", "+3", "1 2", str(2 ** 63))], [12, 3, None, None])

    def test_line_count_is_awks(self) -> None:
        self.assertEqual([citations.count_lines(d) for d in (b"", b"a\n", b"a\nb", None)], [0, 1, 2, 0])


class QuoteTest(unittest.TestCase):
    SAID = "please port the helper to python"

    def test_status(self) -> None:
        self.assertEqual(quotes.status("port the helper", self.SAID), "ok")
        self.assertEqual(quotes.status("Port The helper", self.SAID), quotes.NOT_EXACT)
        self.assertEqual(quotes.status("not there at all", self.SAID), "NOT-IN-THE-REQUEST")
        self.assertEqual(quotes.status("a b", self.SAID), "TOO-SHORT")
        self.assertEqual(quotes.status("", self.SAID), "NO-QUOTE")

    def test_whole_words_only(self) -> None:
        self.assertEqual(quotes.status("port the help", self.SAID), "NOT-IN-THE-REQUEST")

    def test_the_last_quote_that_opens_one_counts(self) -> None:
        line = '1 · m · ask · c · Quote: x · quote: "a b c"'
        at = quotes.opened_at(line)
        self.assertEqual(quotes.quoted(line, at), "a b c")
        self.assertEqual(quotes.opened_at("1 · m · ask · c · requote: \"x\""), -1)
        self.assertEqual(quotes.quoted("quote: “a b” c”", 0), "a b” c")


class ItemQuotesTest(support.Scratch):
    def test_a_request_part_and_a_postgame_must(self) -> None:
        path = self.write("s.md", '## Index\n1 · high · ask · a.py:1 · t · quote: "port the helper"\n'
                                  "2 · must · P1 · a.py:2 · t\n3 · low · P2 · a.py:3 · t\n")
        said = "please port the helper to python"
        self.assertEqual(quotes.item_quotes(path, said, "council-review"),
                         [quotes.Quote("1", "ok", "port the helper")])
        self.assertEqual(quotes.item_quotes(path, said, "council-postgame"),
                         [quotes.Quote("1", "ok", "port the helper"), quotes.Quote("2", "NO-QUOTE", "")])

    def test_next_tasks_need_a_done_when_that_quotes_the_request(self) -> None:
        path = self.write("d.md", "### Next tasks\n#### 1. Port it\n| Done when | \"port the helper to python\" |\n"
                                  "#### 2) Tidy\n| x | y |\n## Other\n#### 3. Not a task\n")
        self.assertEqual(quotes.next_tasks(path, "please port the helper to python"),
                         [quotes.Task("1", "ok", "Port it"), quotes.Task("2", "NO-DONE-WHEN", "Tidy")])


if __name__ == "__main__":
    unittest.main()
