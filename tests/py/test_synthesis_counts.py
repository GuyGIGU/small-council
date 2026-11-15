"""The synthesis tokenizer and the ledger's row bytes, which no eval scenario reaches form by form. The expected
values are what bin/council's synthesis_counts and ledger_record gave (spine-b's pair test, before the bash went)."""
import unittest

import support

from council.records import ledger, synthesis_counts


class TokenizerTest(unittest.TestCase):
    def test_a_from_field_names_these_items(self) -> None:
        known = ("hunt", "beck", "edge").__contains__
        for field, want in (("hunt#1, #2", ["hunt#1", "hunt#2"]), ("beck#1,2", ["beck#1", "beck#2"]),
                            ("hunt#3 and beck#3", ["hunt#3", "beck#3"]), ("hunt#4/beck#4", ["hunt#4", "beck#4"]),
                            ("hunt #1", ["hunt#1"]), ("beck 1, 3", ["beck#1", "beck#3"]), ("hunt", ["hunt#7"]),
                            ("ghost", []), ("[hunt]", []), ("hunt#C2", ["hunt#C2"]),
                            ("edge#1a; hunt", ["edge#1a", "hunt#7"])):
            self.assertEqual([key for _, key in synthesis_counts.named(field, "7", known)], want, field)

    def test_the_from_field_is_the_last_after_a_dot(self) -> None:
        for line, want in (("1 · P1 · a.py:1 · title · from: hunt#1", " hunt#1"),
                           ("2 · P2 · t · from: x — from: beck#2", " x — from: beck#2"),
                           ("3 · title holding from: here · from: edge", " edge"), ("4 · P1 · no field", None)):
            self.assertEqual(synthesis_counts.provenance(line), want, line)


class LedgerRowsTest(support.Scratch):
    def test_record_rewrites_the_runs_rows_and_forget_takes_them_out(self) -> None:
        name = "2026-09-01-100000-review"
        run = self.run_folder(name)
        self.write(".council/runs/%s/session-state.md" % name, "status: complete\nmode: council-review\n")
        self.write(".council/runs/%s/seats.tsv" % name, "slug\tstate\tagent\ttokens\tupdated\tnote\tagents\treported\n"
                   "hunt\tdone\ta1\t52000\t-\t-\t1\t1\nverify-1\tdone\tv1\t9000\t-\t-\t1\t1\n")
        self.write(".council/runs/%s/synthesis.md" % name, "## Kept\n1 · P1 · a.py:1 · t · from: hunt#1\n"
                   "## Cut\n2 · P2 · b.py:2 · t · from: hunt#2\n")
        other = "2026-08-01\tother\tcouncil-plan\tx\t1\t0\t0\t0\t-\t2"
        self.write(".council/ledger.tsv", ledger.HEADER + "2026-09-01\t%s\tcouncil-review\told\t0\t0\t0\t0\t-\t2\n"
                   % name + other)
        self.assertEqual(ledger.record(run), 1)
        self.assertEqual((self.tmp / ".council" / "ledger.tsv").read_bytes().decode("utf-8"), ledger.HEADER + other
                         + "\n2026-09-01\t%s\tcouncil-review\thunt\t0\t1\t1\t0\t52000\t2\n"
                         "2026-09-01\t%s\tcouncil-review\t(verifiers)\t-\t-\t-\t-\t9000\t2\n" % (name, name))
        ledger.forget(run)
        self.assertEqual((self.tmp / ".council" / "ledger.tsv").read_bytes().decode("utf-8"), ledger.HEADER + other
                         + "\n")


if __name__ == "__main__":
    unittest.main()
