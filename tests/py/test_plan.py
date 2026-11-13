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

    def test_budget_takes_the_last_row_without_spaces(self) -> None:
        self.assertEqual(plan.budget(self.run, "agent-cap"), "6")
        self.assertEqual(plan.budget(self.run, "token-ceiling"), "")
        self.assertEqual(plan.budget(self.tmp, "agent-cap"), "")

    def test_keyed(self) -> None:
        keyed = plan.keyed(plan.text(self.run))
        self.assertEqual(keyed[("verification", "run", "level")], "self")
        self.assertEqual(keyed[("budget", "run", "agent-cap")], "6")
        self.assertEqual(plan.text(self.run, read=lambda path: None), "")

    def test_keyed_reads_lines_as_summary_does(self) -> None:
        # A reason holding U+2028 is one row to the helper and to summary(); it must not become two here.
        content = "seat\thunt\tnote\tw\tfirst\u2028budget\trun\tagent-cap\t3\t-\n"
        self.assertNotIn(("budget", "run", "agent-cap"), plan.keyed(content))
        self.assertEqual(plan.keyed(content)[("seat", "hunt", "note")], "w")


if __name__ == "__main__":
    unittest.main()
