"""audit.md: where it is, how it is written, and the audit's report text (records/audit_file.py)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import support

from council.records import audit_file


class FakeRun:
    name = "2026-01-02-030405-council-review"
    mode = "council-review"
    status = "complete"

    def __init__(self, session: str = "") -> None:
        self.session = session

    def field(self, key: str) -> str:
        return self.session if key == "session" else ""


ITEMS = [("pass", "Stages", "all"), ("FAIL", "Deliverable", "none"), ("warn", "Gates", "none ran"),
         ("later", "Closing card", "not checked yet"), ("FAIL", "Helper called", "by variable")]


class SaveTest(support.Scratch):
    def test_save_writes_the_text_whole_and_names_the_path(self) -> None:
        run = self.run_folder()
        said = audit_file.save(run, "report")
        self.assertEqual(said, "Saved: %s" % (run / "audit.md"))
        self.assertEqual((run / "audit.md").read_text(encoding="utf-8"), "report\n")
        audit_file.save(run, "second")
        self.assertEqual((run / "audit.md").read_text(encoding="utf-8"), "second\n")
        self.assertEqual(os.listdir(str(run)), ["audit.md"])         # no temporary file left

    def test_save_says_when_it_cannot(self) -> None:
        run = self.run_folder()
        (run / "audit.md").mkdir()                                     # a folder where the file goes
        self.assertTrue(audit_file.save(run, "x").startswith("Not saved: "))
        self.assertTrue(audit_file.save(run / "gone", "x").startswith("Not saved: "))

    def test_save_never_writes_through_a_link(self) -> None:
        run = self.run_folder()
        target = self.write("elsewhere.md", "keep")
        support.symlink_or_skip(self, run / "audit.md", target)
        self.assertTrue(audit_file.save(run, "x").startswith("Not saved: "))
        self.assertEqual(target.read_text(encoding="utf-8"), "keep")

    def test_present_mention_card_line_and_said(self) -> None:
        run = self.run_folder()
        self.assertFalse(audit_file.present(run))
        self.assertEqual(audit_file.mention(run), "")
        self.assertEqual(audit_file.said(run), "")
        none = "none saved: council run audit --run %s reads the run now"
        self.assertEqual(audit_file.card_line(run), none % run.name)
        audit_file.save(run, "x")
        self.assertTrue(audit_file.present(run))
        self.assertEqual(audit_file.mention(run), "runs/%s/audit.md" % run.name)
        self.assertEqual(audit_file.said(str(run)), "audit: runs/%s/audit.md" % run.name)
        self.assertEqual(audit_file.card_line(run), "runs/%s/audit.md" % run.name)


class RenderTest(support.Scratch):
    def render(self, items: list[Any] | None = None, **given: Any) -> tuple[str, int]:
        args: dict[str, Any] = {"run": FakeRun("sess-1"), "items": ITEMS if items is None else items, "split": 3,
                                "span": "10:00:00 to 10:30:00", "transcript": None, "found": False, "saving": False}
        args.update(given)
        return audit_file.render(**args)

    def test_a_report_counts_failures_and_says_it_wrote_nothing(self) -> None:
        text, failed = self.render()
        self.assertEqual(failed, 2)
        lead = "Run audit: %s (council-review, complete). %s" % (FakeRun.name, audit_file.READ_ONLY)
        self.assertTrue(text.startswith(lead))
        records = "\nFrom the run's records\n  pass  Stages: all\n  FAIL  Deliverable: none\n  warn  Gates: none ran\n"
        self.assertIn(records, text)
        self.assertIn("\nFrom the session transcript (10:00:00 to 10:30:00)\n  later  Closing card:", text)
        self.assertTrue(text.endswith("\n2 failed, 1 warning(s), 1 passed, 1 not checked yet"))
        self.assertIn("No transcript given: pass --transcript <session .jsonl>", text)
        self.assertIn("(this run's session: sess-1)", text)

    def test_a_saved_report_says_so_and_names_the_transcript_it_read(self) -> None:
        where = Path("t.jsonl")
        text, _ = self.render(saving=True, transcript=where, found=True)
        self.assertIn("Saved as audit.md by council run close", text)
        self.assertNotIn(audit_file.READ_ONLY, text)
        self.assertRegex(text, r"\nTaken at: \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\n")
        self.assertIn("\nTranscript: t.jsonl (found from the run's session id)\n", text)
        self.assertNotIn("No transcript given", text)
        self.assertIn("\nTranscript: t.jsonl\n", self.render(transcript=where)[0])

    def test_no_items_after_the_split_reads_nothing_to_check(self) -> None:
        text, failed = self.render(items=ITEMS[:1], split=1)
        self.assertEqual(failed, 0)
        self.assertIn("\nFrom the session transcript (10:00:00 to 10:30:00): nothing to check\n", text)


if __name__ == "__main__":
    import unittest
    unittest.main()
