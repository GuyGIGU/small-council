"""seats.tsv's row rewrite: a NEEDS: note ends when its seat, started again, is recorded done with no note;
every other note is kept or replaced as before."""
from __future__ import annotations

import support

from council.records import seat_write, seats

HEADER = "slug\tstate\tagent\ttokens\tupdated\tnote\tagents\treported\n"
STOP = "NEEDS: fix a.py:2 · does: x · should: y · seen: z"


class RowTest(support.Scratch):
    def note_after(self, state: str, note: str, now: str, given: str = "", short: bool = False) -> str:
        """The note task-1's row holds after it was <state> with <note> and is recorded <now> with note=<given>."""
        run = self.tmp / ".council" / "runs" / "r"
        run.mkdir(parents=True, exist_ok=True)
        cells = ["task-1", state, "a1", "20000", "T", note, "1", "1"]
        (run / "seats.tsv").write_bytes((HEADER + "\t".join(cells[:6] if short else cells) + "\n").encode("utf-8"))
        seat_write.rewrite(run, "task-1", {"state": now, "agent": "", "total": "", "updated": "U", "note": given,
                                           "agents": "", "reported": "0", "tokens": ""})
        return seats.rows(run)[0]["note"]

    def test_a_needs_note_ends_when_its_rerun_is_recorded_done_with_no_note(self) -> None:
        for state in ("queued", "running"):
            self.assertEqual(self.note_after(state, STOP, "done"), "", state)
            self.assertEqual(self.note_after(state, STOP, "done", short=True), "", state)

    def test_the_note_stays_through_the_restart_and_a_late_report(self) -> None:
        for old, now in (("done", "queued"), ("done", "running"), ("done", "done"), ("running", "running"),
                         ("running", "failed"), ("running", "blocked"), ("queued", "skipped")):
            self.assertEqual(self.note_after(old, STOP, now), STOP, (old, now))

    def test_a_new_note_replaces_it_and_other_notes_behave_as_before(self) -> None:
        self.assertEqual(self.note_after("running", STOP, "done", "NEEDS: which?"), "NEEDS: which?")
        self.assertEqual(self.note_after("running", "round 2", "done"), "round 2")
        self.assertEqual(self.note_after("running", "needs: lower case", "done"), "needs: lower case")
