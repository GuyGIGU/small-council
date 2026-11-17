"""seats.tsv's row rewrite: a NEEDS: note ends when its seat, started again, is recorded done with no note;
every other note is kept or replaced as before."""
from __future__ import annotations

import support

from council.records import seat_write, seats

HEADER = "slug\tstate\tagent\ttokens\tupdated\tnote\tagents\treported\n"
STOP = "NEEDS: fix a.py:2 · does: x · should: y · seen: z"


class AddTest(support.Scratch):
    def test_appends_at_once_keep_every_row_and_one_header(self) -> None:
        """CODE-RECORDS-8: four seats reporting tool calls at once, 50 rows each, into one fresh tools.tsv."""
        run = self.run_folder()
        script = ("from pathlib import Path\nfrom council.records import seat_write\nfile = Path(%r)\n"
                  "for n in range(50):\n"
                  "    seat_write.add(file, [['t', sys.argv[1], 'a%%d' %% n, '3']], 'at\\tseat\\tagent\\ttools')\n"
                  % str(run / "tools.tsv"))
        self.assertEqual(self.together(script, "s1", "s2", "s3", "s4"), ["", "", "", ""])
        lines = (run / "tools.tsv").read_text(encoding="utf-8").split("\n")
        self.assertEqual((len(lines), lines.count("at\tseat\tagent\ttools"), lines[-1]), (202, 1, ""))
        self.assertTrue(all(len(line.split("\t")) == 4 for line in lines[:-1]))

    def test_a_torn_last_line_is_never_joined(self) -> None:
        run = self.run_folder()
        (run / "tools.tsv").write_bytes(b"at\tseat\tagent\ttools\nt\ts1\ta")
        seat_write.add(run / "tools.tsv", [["t", "s2", "a2", "4"]], "at\tseat\tagent\ttools")
        self.assertEqual((run / "tools.tsv").read_bytes(), b"at\tseat\tagent\ttools\nt\ts1\ta\nt\ts2\ta2\t4\n")

    def test_a_bom_on_the_header_stays_the_header(self) -> None:
        """CODE-RECORDS-5: seats.tsv saved once with a BOM (PowerShell 5.1) keeps one header through a rewrite."""
        run = self.run_folder()
        (run / "seats.tsv").write_bytes(b"\xef\xbb\xbf" + HEADER.encode("utf-8") + b"hunt\tdone\ta1\t\tT\t\t1\t0\n")
        seat_write.rewrite(run, "map", {"state": "queued", "agent": "", "total": "", "updated": "U", "note": "",
                                        "agents": "", "reported": "0", "tokens": ""})
        text = (run / "seats.tsv").read_text(encoding="utf-8")
        self.assertEqual(text.count("slug\tstate"), 1, text)
        self.assertEqual([row["slug"] for row in seats.rows(run)], ["hunt", "map"])


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
