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
        rows = ledger.raw_rows(self.tmp)
        self.assertEqual(len(rows), 91)                      # the header and 90 rows
        self.assertFalse((self.tmp / "ledger.tsv.lock").exists())

    def test_no_ledger(self) -> None:
        self.assertIsNone(ledger.raw_rows(self.tmp))
        self.assertEqual(ledger.path(self.tmp), self.tmp / "ledger.tsv")


if __name__ == "__main__":
    unittest.main()
