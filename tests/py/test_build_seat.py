"""The build seat's rules (D42): task-<n> in a build is a build seat; one runs at a time; its done needs its report
unless it stopped with NEEDS:; and a start is a seat neither queued nor running before."""
from __future__ import annotations

from pathlib import Path

import support

from council.commands import build_seat

HEADER = b"slug\tstate\tagent\ttokens\tupdated\tnote\tagents\treported\n"


class BuildSeatTest(support.Scratch):
    def build(self, mode: str = "council-implement", seats: bytes = b"") -> Path:
        run = self.run_folder("2026-01-02-03040%d-%s" % (len(list(self.tmp.glob(".council/runs/*"))), mode))
        (run / "session-state.md").write_bytes(b"status: in-progress\nmode: %s\nphase: build\n" % mode.encode())
        (run / "seats.tsv").write_bytes(HEADER + seats)
        return run

    def test_only_task_n_in_a_build_is_a_build_seat(self) -> None:
        run = self.build()
        self.assertEqual(build_seat.task_of(run, "task-3"), 3)
        for slug in ("task-", "task-3b", "T3", "3", "build-3", "verify-3", "task-x"):
            self.assertIsNone(build_seat.task_of(run, slug), slug)
        self.assertIsNone(build_seat.task_of(self.build("council-review"), "task-3"))

    def test_another_running_build_seat_refuses_a_start_naming_it(self) -> None:
        run = self.build(seats=b"task-1\trunning\ta1\t\tT\t\t\t\nverify-1\trunning\tv1\t\tT\t\t\t\n")
        why = build_seat.start_refusal(run, "task-2")
        self.assertIn("cannot start task-2 — task-1 is running, and one builder at a time", why)
        self.assertIn("council seat task-1 failed note=", why)
        self.assertIsNone(build_seat.start_refusal(run, "task-1"))        # the same seat again is no second start
        self.assertIsNone(build_seat.start_refusal(run, "verify-2"))
        self.assertIsNone(build_seat.start_refusal(self.build("council-review", b"task-1\trunning\t\t\tT\t\t\t\n"),
                                                   "task-2"))

    def test_done_and_queued_build_seats_do_not_refuse(self) -> None:
        run = self.build(seats=b"task-1\tdone\ta1\t\tT\t\t\t\ntask-3\tqueued\t\t\tT\t\t\t\n")
        self.assertIsNone(build_seat.start_refusal(run, "task-2"))

    def test_done_needs_the_report_unless_the_builder_stopped_with_needs(self) -> None:
        run = self.build()
        self.assertEqual(build_seat.missing_report(run, "task-2", ""), (run / "report-2.md").as_posix())
        self.assertEqual(build_seat.missing_report(run, "task-2", "NEEDS: which table?"), "")
        self.assertEqual(build_seat.missing_report(run, "verify-2", ""), "")
        (run / "report-2.md").write_bytes(b"")
        self.assertEqual(build_seat.missing_report(run, "task-2", "done"), (run / "report-2.md").as_posix())
        (run / "report-2.md").write_bytes(b"Cause: none\n")
        self.assertEqual(build_seat.missing_report(run, "task-2", ""), "")
        self.assertEqual(build_seat.missing_report(self.build("council-review"), "task-2", ""), "")

    def test_a_start_is_queued_or_running_from_neither(self) -> None:
        run = self.build(seats=b"task-1\trunning\ta1\t\tT\t\t\t\ntask-2\tqueued\t\t\tT\t\t\t\n"
                               b"task-3\tdone\ta3\t\tT\t\t\t\n")
        self.assertFalse(build_seat.starts(run, "task-1", "running"))
        self.assertFalse(build_seat.starts(run, "task-2", "running"))
        self.assertTrue(build_seat.starts(run, "task-3", "running"))       # a fix round: the same seat again
        self.assertTrue(build_seat.starts(run, "task-4", "queued"))
        self.assertFalse(build_seat.starts(run, "task-4", "done"))
        self.assertFalse(build_seat.starts(run, "verify-4", "running"))

    def test_no_line_when_the_run_has_no_round_and_no_commit_it_opened_on(self) -> None:
        self.assertEqual(build_seat.outside_round(self.build(), "task-1"), [])
