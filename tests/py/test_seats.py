import json
import unittest

import support

from council.records import seats


class SeatsTest(support.Scratch):
    def test_rows_and_usage_rows(self) -> None:
        run = self.run_folder()
        (run / "seats.tsv").write_bytes(b"slug\tstate\tagent\ttokens\tupdated\tnote\tagents\treported\n"
                                        b"hunt\tdone\ta1\t52000\t2026-01-01 10:00\tok\t1\t1\n")
        (run / "usage.tsv").write_bytes(b"at\tseat\tagent\tkind\truns\ttokens\nT\thunt\ta1\tdispatched\t\t\n")
        self.assertEqual(seats.rows(run)[0]["tokens"], "52000")
        self.assertEqual(seats.usage_rows(run)[0]["kind"], "dispatched")
        self.assertEqual(seats.rows(self.tmp), [])

    def test_agent_starts_count_a_seed_row_as_its_number(self) -> None:
        run = self.run_folder()
        (run / "agent-starts.tsv").write_bytes(b"at\ttool\tsession\nT\tbefore:3\nT\tAgent\ts\n\nT\tbefore:x\n")
        self.assertEqual(seats.agent_starts(run), 5)
        self.assertEqual(len(seats.start_rows(run)), 3)
        self.assertEqual(seats.agent_starts(self.tmp), 0)

    def test_workflow_extra_counts_runs_past_the_first(self) -> None:
        run = self.run_folder()
        (run / "usage.tsv").write_bytes(b"at\tseat\tagent\tkind\truns\ttokens\n"
                                        b"T\tw\tid1\tfinished\t3\t9000\n"
                                        b"T\tw\tid1\tfinished\t4\t9000\n"      # the latest per id counts
                                        b"T\tw\t\tfinished\t2\t1\n"
                                        b"T\tw\tid2\tdispatched\t9\t\n")
        self.assertEqual(seats.workflow_extra(run), 3 + 1)

    def test_allowed_until_takes_the_last_readable_go(self) -> None:
        run = self.run_folder()
        (run / "cap-allowances.tsv").write_bytes(b"at\tused\tn\tuntil\tsaid\nT\t10\t2\t12\tyes\nT\t12\t2\tbad\tno\n")
        self.assertEqual(seats.allowed_until(run), 12)
        self.assertEqual(seats.allowance_rows(run)[0]["until"], "12")
        self.assertIsNone(seats.allowed_until(self.tmp))

    def test_a_crlf_file_counts_as_its_lf_copy_when_the_figure_is_the_last_cell(self) -> None:
        """The helper's awk drops each line's CR, so the last cell of a hand-edited CRLF file is a plain figure."""
        run = self.run_folder()
        (run / "agent-starts.tsv").write_bytes(b"at\tseed\r\nT\tbefore:3\r\nT\tAgent\r\n")
        (run / "usage.tsv").write_bytes(b"at\tseat\tagent\tkind\truns\r\n"
                                        + b"T\tw\tid1\tfinished\t4\r\nT\tw\t\tfinished\t3\r\n")
        (run / "cap-allowances.tsv").write_bytes(b"at\tused\tn\tuntil\r\nT\t5\t1\t12\r\n")
        self.assertEqual(seats.agent_starts(run), 4)
        self.assertEqual(seats.workflow_extra(run), 3 + 2)
        self.assertEqual(seats.allowed_until(run), 12)

    def test_corrections_keep_the_latest_with_evidence(self) -> None:
        run = self.run_folder()
        rows = [{"seat": "hunt", "field": "tokens", "to": 50000, "evidence": "transcript line 4", "from": "5"},
                {"seat": "hunt", "field": "tokens", "to": 61000, "evidence": "agent footer"},
                {"seat": "map", "field": "agents", "to": 1, "evidence": "  ", "added": True},
                {"seat": "map", "field": "colour", "to": 1, "evidence": "x"},
                {"seat": "lint", "field": "agents", "to": 2, "evidence": "log", "added": True}]
        (run / "corrections.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        found = seats.corrections(run)
        self.assertEqual(sorted(found), [("hunt", "tokens"), ("lint", "agents")])
        self.assertEqual(found[("hunt", "tokens")]["to"], 61000)
        self.assertTrue(found[("lint", "agents")]["added"])
        self.assertFalse(seats.evidenced("  -  "))

    def test_a_count_written_as_a_string_is_no_correction(self) -> None:
        # The helper's corrections_tsv takes only a bare JSON whole number after "to":, so a figure
        # written as "2" is ignored there; reading it here would show a total the ledger never counts.
        run = self.run_folder()
        (run / "corrections.jsonl").write_text(
            '{"seat": "lint", "field": "agents", "to": "2", "evidence": "log"}\n'
            '{"seat": "map", "field": "tokens", "to": 7.0, "evidence": "log"}\n'
            '{"seat": "hunt", "field": "tokens", "to": 9, "evidence": "log"}\n')
        self.assertEqual(sorted(seats.corrections(run)), [("hunt", "tokens")])


if __name__ == "__main__":
    unittest.main()
