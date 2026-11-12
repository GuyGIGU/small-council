import re
import threading
import unittest
from pathlib import Path

import support

from council.records import events, locks

HEADER = "schema\tseq\tat\ttype\tsubject\tvalue\tdetail\n"


class ReadTest(support.Scratch):
    def test_table_counts_rows_and_checks_the_header(self) -> None:
        run = self.run_folder()
        self.write(str(run.relative_to(self.tmp) / "events.tsv"),
                   HEADER + "1\t1\t2026-01-01T00:00:00Z\trun.opened\trun\tcouncil-review\tphase=convene\n\nbroken\r\n")
        table = events.table(run)
        self.assertTrue(table.present and table.header_ok and not table.too_large)
        self.assertEqual([len(row) for row in table.rows], [7, 1])
        self.assertEqual(events.table(self.tmp).present, False)

    def test_table_skips_a_stream_over_its_limit(self) -> None:
        run = self.run_folder()
        (run / "events.tsv").write_text(HEADER + "x" * 100)
        self.assertTrue(events.table(run, limit=50).too_large)

    def test_records_key_by_the_header(self) -> None:
        run = self.run_folder()
        (run / "events.tsv").write_text(HEADER + "1\t1\tat\tgate.finished\ttests\tpassed\texit=0;seconds=4\n")
        row = events.records(run)[0]
        self.assertEqual((row["type"], row["subject"]), ("gate.finished", "tests"))
        self.assertEqual(events.details(row["detail"]), {"exit": "0", "seconds": "4"})

    def test_strict_rows_refuse_a_broken_stream(self) -> None:
        run = self.run_folder()
        read = lambda path: path.read_text() if path.exists() else None  # noqa: E731
        with self.assertRaisesRegex(events.EventError, "no v1 header"):
            events.strict_rows(run, read)
        (run / "events.tsv").write_text(HEADER + "1\t2\tat\tt\ts\tv\td\n")
        with self.assertRaisesRegex(events.EventError, "malformed"):
            events.strict_rows(run, read)
        (run / "events.tsv").write_text(HEADER + "1\t1\tat\tt\ts\tv\td\n")
        self.assertEqual(events.strict_rows(run, read),
                         [{"seq": 1, "type": "t", "subject": "s", "value": "v", "detail": "d"}])


class AppendTest(support.Scratch):
    def stamped(self, extra: str = "events-schema: 1\n") -> Path:
        run = self.run_folder()
        (run / "session-state.md").write_text("status: in-progress\n" + extra + "## Decisions so far\n")
        return run

    def test_cell_strips_controls(self) -> None:
        self.assertEqual(events.cell("a\tb\r\nc\x00d\x7fé"), "a b  cdé")

    def test_append_opens_the_stream_and_numbers_rows(self) -> None:
        run = self.stamped()
        with self.assertRaisesRegex(events.EventError, "could not append"):
            events.append(run, "seat.updated", "hunt", "running", "")        # only run.opened starts a stream
        self.assertTrue(events.append(run, "run.opened", "run", "council-review", "phase=convene"))
        self.assertTrue(events.append(run, "seat.updated", "hunt\tx", "running", "a\nb"))
        lines = (run / "events.tsv").read_text().split("\n")
        self.assertEqual(lines[0] + "\n", HEADER)
        self.assertRegex(lines[2], r"^1\t2\t\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\tseat\.updated\thunt x\trunning\ta b$")
        self.assertFalse((run / "events.tsv.lock").exists())

    def test_once_records_a_type_only_the_first_time(self) -> None:
        run = self.stamped()
        events.append(run, "run.opened", "run", "m", "")
        self.assertTrue(events.append(run, "run.cap_passed", "run", "11", "cap=10", once=True))
        self.assertFalse(events.append(run, "run.cap_passed", "run", "12", "cap=10", once=True))
        self.assertEqual((run / "events.tsv").read_text().count("run.cap_passed"), 1)

    def test_a_torn_last_line_is_never_joined(self) -> None:
        run = self.stamped()
        (run / "events.tsv").write_text(HEADER + "1\t1\tat\trun.opened\trun\tm\tx")
        with self.assertRaisesRegex(events.EventError, "could not append"):
            events.append(run, "seat.updated", "a", "b", "c")
        self.assertTrue((run / "events.tsv").read_text().endswith("\tx"))

    def test_schema_stamp_rules(self) -> None:
        old = self.stamped(extra="")
        self.assertFalse(events.append(old, "run.opened", "run", "m", ""))   # a run from before the stream
        self.assertFalse((old / "events.tsv").exists())
        (old / "events.tsv").write_text(HEADER)
        with self.assertRaisesRegex(events.EventError, "without an events-schema stamp"):
            events.append(old, "x", "y", "z", "")
        newer = self.run_folder("2026-01-02-030406-council-plan")
        (newer / "session-state.md").write_text("events-schema: 2\n")
        with self.assertRaisesRegex(events.EventError, "unsupported events schema: 2"):
            events.append(newer, "x", "y", "z", "")

    def test_a_held_lock_stops_the_append(self) -> None:
        run = self.stamped()
        events.append(run, "run.opened", "run", "m", "")
        lock = run / "events.tsv.lock"
        self.assertTrue(locks.acquire(lock))
        try:
            with self.assertRaisesRegex(events.EventError, "event lock unavailable"):
                events.append(run, "seat.updated", "a", "b", "c", tries=1)
        finally:
            locks.release(lock)
        self.assertEqual(len((run / "events.tsv").read_text().splitlines()), 2)

    def test_two_threads_get_distinct_sequence_numbers(self) -> None:
        run = self.stamped()
        events.append(run, "run.opened", "run", "m", "")

        def work(name: str) -> None:
            for n in range(15):
                events.append(run, "seat.updated", name, str(n), "")

        threads = [threading.Thread(target=work, args=(name,)) for name in ("a", "b")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        seqs = [int(line.split("\t")[1]) for line in (run / "events.tsv").read_text().splitlines()[1:]]
        self.assertEqual(seqs, list(range(1, 32)))
        self.assertTrue(all(re.match(r"1\t\d+\t", line) for line in (run / "events.tsv").read_text().splitlines()[1:]))


if __name__ == "__main__":
    unittest.main()
