import unittest

import support

from council.records import ledger


class LedgerTest(support.Scratch):
    def test_writers_at_once_keep_each_others_rows(self) -> None:
        """CODE-RECORDS-4: three runs closing in one home at once, each rewriting the ledger 30 times, keep 90 rows."""
        script = ("from pathlib import Path\nfrom council.records import ledger\nrun = sys.argv[1]\n"
                  "for n in range(30):\n"
                  "    row = '2026-01-01\\t%s-%d\\tcouncil-review\\thunt\\t1\\t1\\t0\\t0\\t9000\\t2\\n' % (run, n)\n"
                  "    assert ledger._rewrite(Path('ledger.tsv'), 'none', row.encode(), 'x')\n")
        self.assertEqual(self.together(script, "a", "b", "c"), ["", "", ""])
        rows, bad = ledger.read(self.tmp / "ledger.tsv")
        self.assertEqual((len(rows), bad), (90, 0))
        self.assertFalse((self.tmp / "ledger.tsv.lock").exists())

    def test_no_ledger(self) -> None:
        self.assertEqual(ledger.read(self.tmp / "ledger.tsv"), (None, 0))
        self.assertEqual(ledger.path(self.tmp), self.tmp / "ledger.tsv")

    def test_rows_bad_lines_and_checked_tokens(self) -> None:
        text = ("﻿date\trun\tmode\tseat\traised\tkept\tcut\trefuted\ttokens\taccounting\n"
                "2026-01-01\tr1\tcouncil-review\thunt\t5\t3\t1\t0\t52000\t2\r\n"
                "2026-01-01\tr1\t\tmap\t2\t1\t0\t0\t9000\n"                 # an older row: tokens unchecked
                "2026-01-01\tr1\tcouncil-review\t(verifiers)\t-\t-\t-\t-\t-\t2\n"
                "2026-01-01\tr1\tcouncil-review\tlint\tx\t0\t0\t0\t1\t2\n"  # not a count
                "short\trow\n"
                "\n")
        where = self.write("ledger.tsv", text)
        rows, bad = ledger.read(where)
        self.assertEqual(bad, 2)
        self.assertEqual([(r["seat"], r["tokens"]) for r in rows],
                         [("hunt", 52000), ("map", None), ("(verifiers)", None)])
        self.assertEqual(rows[1]["mode"], "-")
        self.assertEqual(rows[0]["kept"], 3)

    def test_a_folder_or_huge_file_is_refused(self) -> None:
        (self.tmp / "ledger.tsv").mkdir()
        with self.assertRaisesRegex(ledger.LedgerError, "not a regular file under 8 MB"):
            ledger.read(self.tmp / "ledger.tsv")

    def test_cells(self) -> None:
        self.assertEqual(ledger.count(" 7 "), 7)
        with self.assertRaises(ValueError):
            ledger.count("-1")
        cells = ["d", "r", "m", "s", "1", "1", "0", "0", "-"]
        with self.assertRaises(ValueError):
            ledger.tokens_of(cells)                       # "-" on an unchecked row is no figure
        self.assertIsNone(ledger.tokens_of(cells + ["2"]))


if __name__ == "__main__":
    unittest.main()
