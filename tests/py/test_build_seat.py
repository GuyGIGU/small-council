"""The build seat's rules (D42): task-<n> in a build is a build seat; one runs at a time; its done needs its report
unless it stopped with NEEDS:; and a start is a seat neither queued nor running before."""
from __future__ import annotations

from pathlib import Path
from unittest import mock

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

    def test_a_queued_build_seat_is_taken_and_a_done_one_is_not(self) -> None:
        run = self.build(seats=b"task-1\tdone\ta1\t\tT\t\t\t\ntask-3\tqueued\t\t\tT\t\t\t\n")
        why = build_seat.start_refusal(run, "task-2")
        self.assertIn("cannot start task-2 — task-3 is queued, and one builder at a time", why)
        self.assertIsNone(build_seat.start_refusal(run, "task-3"))        # its own dispatch, or its running
        done = self.build(seats=b"task-1\tdone\ta1\t\tT\t\t\t\ntask-3\tskipped\t\t\tT\t\t\t\n")
        self.assertIsNone(build_seat.start_refusal(done, "task-2"))

    def test_a_builder_goes_out_only_from_a_queued_seat_and_takes_it(self) -> None:
        from council.commands import seat
        run = self.build(seats=b"task-1\tqueued\t\t\tT\t\t\t\n")
        self.assertIsNone(build_seat.dispatch_refusal(run, "task-1"))
        self.assertIsNone(seat.taken(run, "task-1"))
        row = (run / "seats.tsv").read_text(encoding="utf-8").splitlines()[1]
        self.assertTrue(row.startswith("task-1\trunning\t\t"), row)
        why = seat.taken(run, "task-1")
        self.assertIn("a builder went out for it already", why or "")
        self.assertIn("no agent on record yet", why or "")
        self.assertIn('council seat task-1 failed note="dispatch failed", then council seat task-1 queued', why or "")
        named = self.build(seats=b"task-1\trunning\tb1\t\tT\t\t\t\n")
        self.assertIn("agent b1", build_seat.dispatch_refusal(named, "task-1") or "")
        self.assertIn("its seat isn't queued", build_seat.dispatch_refusal(self.build(), "task-1") or "")
        self.assertIsNone(seat.taken(self.build("council-review", b"task-1\tqueued\t\t\tT\t\t\t\n"), "task-1"))

    def test_a_take_that_comes_while_another_holds_the_seat_lock_waits_for_it_and_is_refused(self) -> None:
        # EVALS-1 (M13): two builders for one queued seat, the second's take arriving while the first is between its
        # reading of the seat and its record. The seam fixes that order (no race to win by luck): the first take's
        # reading starts the second and waits until the second has read the seat or 2 s have passed. Under the seat
        # lock the second can't read until the first has recorded running, so it is refused; without the lock both
        # read queued and both go out.
        import threading
        from council.commands import seat
        run = self.build(seats=b"task-1\tqueued\t\t\tT\t\t\t\n")
        read, second, results = build_seat.dispatch_refusal, threading.Event(), {}

        def reading(at: Path, slug: str) -> str | None:
            why = read(at, slug)
            if threading.current_thread() is not first:
                second.set()                                   # the second take has read the seat
            elif "second" not in results:
                results["second"] = None
                other.start()
                second.wait(2)
            return why

        def take(name: str) -> None:
            results[name] = seat.taken(run, "task-1")

        first = threading.Thread(target=take, args=("first",))
        other = threading.Thread(target=take, args=("second",))
        with mock.patch.object(build_seat, "dispatch_refusal", side_effect=reading):
            first.start()
            first.join(60)
            other.join(60)
        self.assertIsNone(results["first"])
        self.assertIn("a builder went out for it already", results["second"] or "")
        rows = (run / "seats.tsv").read_text(encoding="utf-8").splitlines()[1:]
        self.assertEqual([row.split("\t")[1] for row in rows], ["running"])

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


STOP = "NEEDS: fix src/a.py:2 · does: x · should: y · seen: z"
PLAN = ("# Plan\n## Task Sequence\n### 1. One\n| | |\n|---|---|\n| **Depends on** | — |\n\n"
        "### 2. Two\n| | |\n|---|---|\n| **Depends on** | 1 |\n\n### 3. Three\n| | |\n|---|---|\n"
        "| **Depends on** | — |\n\n### 4. Four\n| | |\n|---|---|\n| **Depends on** | 2 |\n")
EVENTS = "schema\tseq\tat\ttype\tsubject\tvalue\tdetail\n"


class StopTest(support.Scratch):
    def stopped(self, note: str = STOP, decided: str = "", plan: bool = True, stream: bool = True) -> Path:
        """A build run whose task-1 started at 10:00 and stopped (done, then a late report) at 10:05 UTC."""
        run = self.run_folder("2026-01-02-030405-council-implement")
        self.write("plan.md", PLAN)
        header = "status: in-progress\nmode: council-implement\n" + ("input: %s\n" % (self.tmp / "plan.md").as_posix()
                                                                    if plan else "")
        (run / "session-state.md").write_bytes((header + "\n## Decisions so far\n" + decided).encode("utf-8"))
        (run / "seats.tsv").write_bytes(HEADER + ("task-1\tdone\ta1\t20000\tT\t%s\t1\t1\n" % note).encode("utf-8"))
        rows = [("2026-01-02T10:00:00Z", "running"), ("2026-01-02T10:05:00Z", "done"), ("2026-01-02T11:00:00Z", "done")]
        if stream:
            lines = ["1\t%d\t%s\tseat.updated\ttask-1\t%s\t\n" % (n, at, v) for n, (at, v) in enumerate(rows, 1)]
            (run / "events.tsv").write_bytes((EVENTS + "".join(lines)).encode())
        return run

    def minute(self, utc: str) -> str:
        from council.commands import rounds
        return rounds.local_minute(utc)

    def test_a_stop_with_no_decision_since_stands_and_refuses_its_task_and_its_dependants(self) -> None:
        run = self.stopped(decided='- %s: "an older word"\n' % self.minute("2026-01-02T10:04:00Z"))
        self.assertEqual(build_seat.stop_of(run, "task-1"), build_seat.STANDS)
        self.assertIn("cannot start task-1 — task 1 stopped with NEEDS: fix at src/a.py:2 (seat task-1), and this is "
                      "that task", build_seat.start_refusal(run, "task-1"))
        self.assertIn("and task 4 depends on it", build_seat.start_refusal(run, "task-4"))     # 4 → 2 → 1
        self.assertIn('council state decision="…"', build_seat.start_refusal(run, "task-2"))
        self.assertIsNone(build_seat.start_refusal(run, "task-3"))
        self.assertEqual(build_seat.depends_on(run, 4), {1, 2, 4})

    def test_a_decision_from_the_stops_minute_on_releases_it_and_a_late_report_does_not_move_the_stop(self) -> None:
        run = self.stopped(decided='- %s: "fix the cache first"\n' % self.minute("2026-01-02T10:05:00Z"))
        self.assertEqual(build_seat.stop_of(run, "task-1"), build_seat.RELEASED)
        self.assertIsNone(build_seat.start_refusal(run, "task-2"))

    def test_only_an_after_gate_passed_after_the_stop_resolves_it(self) -> None:
        run = self.stopped()
        self.write(".council/runs/%s/gates/after-1.json" % run.name, '{"gate": "after-1", "exit": 0, "when": "w"}')
        stream = (run / "events.tsv").read_bytes().decode()
        before = stream.replace("1\t2\t", "1\t0\t2026-01-02T09:00:00Z\tgate.finished\tafter-1\tpassed\t\n1\t2\t", 1)
        (run / "events.tsv").write_bytes(before.encode())
        self.assertEqual(build_seat.stop_of(run, "task-1"), build_seat.STANDS)     # an older pass: a fix round's stop
        self.assertEqual(build_seat.resolved_tasks(run, build_seat.verdicts(run)), set())
        self.assertIsNotNone(build_seat.start_refusal(run, "task-2"))
        (run / "events.tsv").write_bytes((before + "1\t4\t2026-01-02T11:30:00Z\tgate.finished\tafter-1\tfailed\t\n"
                                          "1\t5\t2026-01-02T11:40:00Z\tgate.finished\tafter-2\tpassed\t\n").encode())
        self.assertEqual(build_seat.stop_of(run, "task-1"), build_seat.STANDS)     # a red, or another task's pass
        (run / "events.tsv").write_bytes((before + "1\t4\t2026-01-02T11:30:00Z\tgate.finished\tafter-1\tpassed\t\n")
                                         .encode())
        self.assertEqual(build_seat.stop_of(run, "task-1"), build_seat.RESOLVED)
        self.assertEqual(build_seat.resolved_tasks(run, build_seat.verdicts(run)), {1})
        self.assertIsNone(build_seat.start_refusal(run, "task-2"))

    def test_with_no_stream_the_after_gates_last_verdict_resolves_it(self) -> None:
        run = self.stopped(stream=False)
        self.write(".council/runs/%s/gates/after-1.json" % run.name, '{"gate": "after-1", "exit": 0, "when": "w"}')
        self.assertEqual(build_seat.stop_of(run, "task-1"), build_seat.RESOLVED)
        self.assertEqual(build_seat.resolved_tasks(run, build_seat.verdicts(run)), {1})

    def test_a_question_reads_as_a_stop_but_refuses_nothing(self) -> None:
        run = self.stopped(note="NEEDS: which table?")
        self.assertEqual(build_seat.stop_of(run, "task-1"), build_seat.STANDS)
        self.assertIsNone(build_seat.start_refusal(run, "task-2"))
        self.assertEqual(build_seat.stop_of(run, "task-2"), "")

    def test_what_cannot_be_read_never_refuses_more(self) -> None:
        run = self.stopped(stream=False)
        self.assertEqual(build_seat.stop_of(run, "task-1"), build_seat.RELEASED)
        stop = "1\t1\t2026-01-02T10:05:00Z\tseat.updated\ttask-1\tdone\t\n"
        (run / "events.tsv").write_bytes((EVENTS + stop).encode())
        self.assertIsNotNone(build_seat.start_refusal(run, "task-1"))
        state = (run / "session-state.md").read_bytes().replace(b"input: ", b"former: ")
        (run / "session-state.md").write_bytes(state)
        self.assertIsNotNone(build_seat.start_refusal(run, "task-1"))
        self.assertIsNone(build_seat.start_refusal(run, "task-2"))            # no plan: only the task itself
