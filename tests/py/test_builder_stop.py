"""Whether a builder may stop (builder_stop): BLOCKED and a one-line NEEDS: let it; any other reply is the one
Wrote line naming a report whose head the helper reads and whose round was saved from that head."""
from __future__ import annotations

import json
from pathlib import Path

import support

from council.commands import builder_stop
from council.records import patches, report_head

HEAD = "Cause: none\nOwner: src/pay.py\nRemoved: none\nAssumed: nothing\n\nThe prose.\n"


class BuilderStopTest(support.Scratch):
    def stop(self, reply: object, cwd: str = "") -> str:
        fields = {"agent_type": "small-council:council-builder", "cwd": cwd, "stop_hook_active": False}
        if reply is not None:
            fields["last_assistant_message"] = reply
        return builder_stop.reason(json.dumps(fields).encode("utf-8"))

    def saved(self) -> Path:
        """A build run whose report-1.md has the head HEAD, and round 1 of task 1 saved from it."""
        report = self.write(".council/runs/2026-01-02-030405-council-implement/report-1.md", HEAD)
        read, _ = report_head.read(report)
        self.assertIsNotNone(read)
        patches.write(report.parent, patches.Round(1, 1, 1, "t", "a", "b", ["src/pay.py"], 1, 0, read._asdict(), [],
                                                   [], ""), b"")
        return report

    def test_input_it_cannot_read_or_no_reply_field_lets_it_stop(self) -> None:
        self.assertEqual(builder_stop.reason(b"\x00not json"), "")
        self.assertEqual(builder_stop.reason(b"[1, 2]"), "")
        self.assertEqual(self.stop(None), "")

    def test_an_empty_reply_is_sent_back_with_the_one_line(self) -> None:
        why = self.stop(" \n ")
        self.assertIn("you stopped without a reply", why)
        self.assertIn(builder_stop.ONE_LINE, why)

    def test_blocked_as_the_seat_gate_reads_it_lets_it_stop(self) -> None:
        for reply in ("BLOCKED: task 2 — after-2 failed three times: x", "Tried.\n**BLOCKED:** no gate",
                      "Blocked: the plan is gone", "> BLOCKED"):
            self.assertEqual(self.stop(reply), "", reply)
        self.assertNotEqual(self.stop("I was not BLOCKED, I stopped"), "")
        self.assertNotEqual(self.stop("Done.\nBlocked: 0 of 3"), "")

    def test_a_one_line_needs_lets_it_stop_and_more_lines_are_sent_back(self) -> None:
        self.assertEqual(self.stop("NEEDS: which of the two caches is the owner?"), "")
        fix = "NEEDS: fix src/a.py:12 · does: drops x · should: keep x · seen: pytest -k a: 1 failed"
        self.assertEqual(self.stop(fix), "")
        self.assertIn("exactly one line", self.stop("NEEDS: which cache?\nI looked at both."))

    def test_a_needs_fix_without_its_four_parts_is_sent_back_with_the_form(self) -> None:
        why = self.stop("NEEDS: fix the parser drops the last field · does: drops it")
        self.assertIn("has no file:line, should:, seen:", why)
        self.assertIn(builder_stop.FIX_FORM, why)
        self.assertEqual(self.stop("NEEDS: fixed width or flexible columns?"), "")

    def test_the_wrote_line_with_its_round_saved_from_this_head_lets_it_stop(self) -> None:
        report = self.saved()
        self.assertEqual(self.stop("Wrote %s — task 1, round 1 saved" % report), "")
        self.assertEqual(self.stop("Wrote `%s` — task 1, round 1 saved" % report), "")

    def test_a_relative_name_is_joined_to_cwd_and_one_it_cannot_find_asks_for_the_full_path(self) -> None:
        report = self.saved()
        self.assertEqual(self.stop("Wrote report-1.md — task 1, round 1 saved", cwd=str(report.parent)), "")
        self.assertIn("full path", self.stop("Wrote report-1.md — task 1, round 1 saved", cwd=str(self.tmp)))

    def test_a_reply_naming_no_report_is_sent_back_for_the_one_line(self) -> None:
        for reply in ("All done, the tests pass.", "Wrote the change to src/pay.py", "Wrote notes.md"):
            self.assertEqual(self.stop(reply), builder_stop.FINISH, reply)

    def test_a_missing_or_empty_report_is_sent_back_to_write_it(self) -> None:
        run = self.run_folder("2026-01-02-030405-council-implement")
        why = self.stop("Wrote %s — task 1, round 1 saved" % (run / "report-1.md"))
        self.assertIn("isn't there or is empty", why)
        self.assertIn("council patch save 1", why)

    def test_a_head_the_helper_cannot_read_is_sent_back_with_what_it_says(self) -> None:
        run = self.run_folder("2026-01-02-030405-council-implement")
        report = self.write(".council/runs/%s/report-2.md" % run.name, "Cause: none\nOwner: x\n\nprose\n")
        why = self.stop("Wrote %s — task 2, round 1 saved" % report)
        self.assertIn("the report has no Removed: line in its head", why)
        self.assertIn("Fix the head, run council patch save 2", why)

    def test_no_saved_round_or_one_saved_from_another_head_is_sent_back_to_save(self) -> None:
        report = self.saved()
        for name in ("T1-1.json", "T1-1.patch"):
            (report.parent / "patches" / name).unlink()
        self.assertIn("task 1 has no saved round", self.stop("Wrote %s — task 1, round 1 saved" % report))
        report = self.saved()
        report.write_text(HEAD.replace("src/pay.py", "src/bill.py"), encoding="utf-8")
        why = self.stop("Wrote %s — task 1, round 1 saved" % report)
        self.assertIn("not the one task 1's last saved round (round 1) was saved from", why)

    def test_all_in_order_but_more_than_one_line_is_sent_back_for_the_one_line(self) -> None:
        report = self.saved()
        why = self.stop("Wrote %s — task 1, round 1 saved\nThe gates pass." % report)
        self.assertIn("is in order and task 1 round 1 is saved", why)
        self.assertIn("exactly one line", why)
