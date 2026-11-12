import unittest

import support  # noqa: F401  (puts src/ on the path)

from council.records import cells


class CellsTest(unittest.TestCase):
    def test_clean_makes_one_line(self) -> None:
        self.assertEqual(cells.clean("a\tb\n\x1b[2Jc  d "), "a b [2Jc d")

    def test_lines_split_on_newline_only(self) -> None:
        self.assertEqual(cells.lines_of("a\r\nb\x0cc\nd"), ["a", "b\x0cc", "d"])

    def test_integer_takes_ints_and_digit_strings_only(self) -> None:
        self.assertEqual(cells.integer(5), 5)
        self.assertEqual(cells.integer(" -12 "), -12)
        self.assertIsNone(cells.integer(True))
        self.assertIsNone(cells.integer([1]))
        self.assertIsNone(cells.integer(10 ** 12))
        self.assertIsNone(cells.integer("1.5"))

    def test_number_and_optional_number(self) -> None:
        self.assertEqual(cells.number(" 42 "), 42)
        self.assertEqual(cells.number(""), 0)
        self.assertEqual(cells.number("x"), 0)
        self.assertIsNone(cells.optional_number(""))
        self.assertIsNone(cells.optional_number(None))
        self.assertEqual(cells.optional_number("0"), 0)

    def test_token_count_reads_the_helpers_forms(self) -> None:
        for text, want in (("74300", 74300), ("74,300", 74300), ("74 300", 74300), ("74.3k", 74300),
                           ("1.2M", 1200000), ("80k tokens", 80000), ("007", 7), ("0", 0)):
            self.assertEqual(cells.token_count(text), want, text)
        for text in ("74,3k", "1,50k", "-5", "12 tool uses, 45000", "1e5", "", "1234567890123"):
            self.assertIsNone(cells.token_count(text), text)

    def test_tsv_rows_skip_comments_and_pad_short_rows(self) -> None:
        rows = cells.tsv_rows("# note\nslug\tstate\tagent\n\nhunt\trunning\nmap\tdone\tabc\textra\n")
        self.assertEqual(rows, [{"slug": "hunt", "state": "running", "agent": ""},
                                {"slug": "map", "state": "done", "agent": "abc"}])
        self.assertEqual(cells.tsv_rows(""), [])

    def test_jsonl_rows_keep_objects_only(self) -> None:
        self.assertEqual(cells.jsonl_rows('{"a": 1}\n[1]\nnot json\n{"b": 2}\r\n'), [{"a": 1}, {"b": 2}])


if __name__ == "__main__":
    unittest.main()
