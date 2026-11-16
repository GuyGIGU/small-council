import unittest

import support

from council.records import plan

PLAN = ("# Small Council run plan v1.\n"
        "kind\tid\tfield\tvalue\treason\n"
        "run\trun\tsize\tsquad\tthe change is small\n"
        "plan\tplan\trisk\tlow\t-\n"
        "seat\thunt\trole\tworker\t-\n"
        "seat\thunt\tdisposition\tselected\tit owns the change\n"
        "context\thunt\tlevel\tfocused\t-\n"
        "budget\trun\tagent-cap\t 8 \t-\n"
        "budget\trun\tagent-cap\t6\r\n"
        "verification\trun\tlevel\tSELF\t-\n"
        "short\trow\n")


class PlanTest(support.Scratch):
    def setUp(self) -> None:
        super().setUp()
        self.run = self.run_folder()
        (self.run / "run-plan.tsv").write_bytes(PLAN.encode())

    def test_rows_skip_comments(self) -> None:
        rows = plan.rows(self.run)
        self.assertEqual(rows[0], {"kind": "run", "id": "run", "field": "size", "value": "squad",
                                   "reason": "the change is small"})
        self.assertEqual(rows[-1]["kind"], "short")

    def test_summary(self) -> None:
        summary = plan.summary(self.run)
        self.assertEqual((summary["size"], summary["risk"]), ("squad", "low"))
        self.assertEqual(summary["seats"]["hunt"], {"role": "worker", "disposition": "selected",
                                                    "reason": "it owns the change", "context": "focused"})

    def test_budget_takes_the_first_row_trimmed(self) -> None:
        self.assertEqual(plan.budget(self.run, "agent-cap"), "8")
        self.assertEqual(plan.budget(self.run, "token-ceiling"), "")
        self.assertEqual(plan.budget(self.tmp, "agent-cap"), "")

    def test_keyed(self) -> None:
        keyed = plan.keyed(plan.text(self.run))
        self.assertEqual(keyed[("verification", "run", "level")], "SELF")     # as written: never lower-cased
        self.assertEqual(keyed[("budget", "run", "agent-cap")], "8")          # the first row wins
        self.assertEqual(plan.text(self.run, read=lambda path: None), "")

    def test_keyed_reads_lines_as_summary_does(self) -> None:
        # A reason holding U+2028 is one row to the helper and to summary(); it must not become two here.
        content = "seat\thunt\tnote\tw\tfirst\u2028budget\trun\tagent-cap\t3\t-\n"
        self.assertNotIn(("budget", "run", "agent-cap"), plan.keyed(content))
        self.assertEqual(plan.keyed(content)[("seat", "hunt", "note")], "w")

    def test_one_rule_for_every_reader(self) -> None:
        # A value is trimmed of spaces and tabs only, the first row of a key wins, and a budget is plain digits.
        (self.run / "run-plan.tsv").write_bytes(b"budget\trun\tagent-cap\t1 0\t-\r\nbudget\trun\tagent-cap\t5\n"
                                                b"seat\tHunt\tdisposition\t selected \t-\n"
                                                b"seat\tHunt\tdisposition\tskipped\n"
                                                b"seat\tv\trole\t\xc2\xa0verifier\n")
        self.assertEqual(plan.budget(self.run, "agent-cap"), "")
        self.assertTrue(plan.selected(self.run, "Hunt"))
        self.assertFalse(plan.selected(self.run, "hunt"))
        self.assertEqual(plan.keyed(plan.text(self.run))[("seat", "v", "role")], " verifier")


if __name__ == "__main__":
    unittest.main()
