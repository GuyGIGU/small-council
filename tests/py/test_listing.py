"""The run listing (state.listing), the seat summary and a mode's skill: the readers council run status and
run resume use, against what bin/council's list_runs, seat_summary and mode_skill print."""
import unittest

import support

from council.records import runs


class ListingTest(support.Scratch):
    def home(self) -> str:
        return str(self.tmp / ".council").replace("\\", "/")

    def state(self, name: str, text: str) -> None:
        self.write(".council/runs/%s/session-state.md" % name, text)

    def test_open_runs_newest_first_by_full_path(self) -> None:
        self.state("a", "status: in-progress\nmode: council-review\n")
        self.state("a-b", "status: paused\n")
        self.state("b", "status: complete\n")
        self.state(".hidden", "status: in-progress\n")
        listed = runs.listing(self.home(), 30, "open")
        # sort -r over ".../a/session-state.md" and ".../a-b/session-state.md": "/" sorts after "-".
        self.assertEqual([run.folder.split("/")[-1] for run in listed], ["a", "a-b"])
        self.assertEqual(listed[0].folder, self.home() + "/runs/a")
        self.assertEqual((listed[0].mode, listed[0].status), ("council-review", "in-progress"))

    def test_all_runs_newest_first_by_name_and_limited(self) -> None:
        for name in ("2026-01-01-000000-review", "2026-01-02-000000-plan", "2026-01-03-000000-review"):
            self.state(name, "status: complete\n")
        self.write(".council/runs/no-state/notes.md", "x")
        listed = runs.listing(self.home(), 2, "all")
        self.assertEqual([run.folder.split("/")[-1] for run in listed],
                         ["2026-01-03-000000-review", "2026-01-02-000000-plan"])

    def test_a_status_line_anywhere_opens_the_run_and_the_first_status_is_shown(self) -> None:
        self.state("r", "status: complete\n## Notes\nstatus: in-progress\n")
        listed = runs.listing(self.home(), 30, "open")
        self.assertEqual([run.status for run in listed], ["complete"])

    def test_fields_as_list_runs_reads_them(self) -> None:
        fields = runs.listed_fields("﻿status: in-progress    # note\r\nphase:\tconvene\r\n"
                                     "Mode: x\nmode: a\tb  # cut\nmode: second\n## Body\nactual: 1 agent\n")
        self.assertEqual(fields["status"], "in-progress")
        self.assertEqual(fields["phase"], "convene")              # leading space and tab dropped
        self.assertEqual(fields["mode"], "a b")                    # tabs made spaces, comment cut, first wins
        self.assertNotIn("Mode", fields)                           # keys are lower case
        self.assertEqual(fields["actual"], "1 agent")              # below the header too
        self.assertIsNone(runs.listed_fields(""))
        self.assertEqual(runs.listed_fields("\n"), {})

    def test_status_is_its_first_word(self) -> None:
        self.state("r", "status: paused by the user\n")
        self.assertEqual(runs.listing(self.home(), 30, "open")[0].status, "paused")

    def test_no_runs_folder(self) -> None:
        self.assertEqual(runs.listing(self.home(), 30, "open"), [])
        self.assertEqual(runs.listing(self.home(), 30, "all"), [])

    def test_skill_of_a_mode(self) -> None:
        self.assertEqual(runs.skill("council-review"), "council-review")
        self.assertEqual(runs.skill("review"), "council-review")
        self.assertEqual(runs.skill("spec-writer"), "spec-writer")
        self.assertEqual(runs.skill("odd"), "context-core")
        self.assertEqual(runs.skill(""), "context-core")


class SummaryTest(support.Scratch):
    def test_working_done_failed(self) -> None:
        run = self.run_folder()
        self.write(str(run.relative_to(self.tmp) / "seats.tsv"),
                   "slug\tstate\tagent\ttokens\tupdated\tnote\n"
                   "a\trunning\t-\t-\t-\twar-room round 2\n"
                   "b\tqueued\n"
                   "c\tdone\t-\t-\t-\t-\n"
                   "d\tblocked\t-\t-\t-\t-\n"
                   "e\tskipped\t-\t-\t-\t-\n")
        self.assertEqual(runs.seat_summary(run), "still working: a (war-room round 2), b · done: c · failed: d")
        self.assertEqual(runs.seat_summary(run, "working"), "working: a (war-room round 2), b · done: c · failed: d")

    def test_nothing_to_say(self) -> None:
        run = self.run_folder()
        self.assertEqual(runs.seat_summary(run), "")
        self.write(str(run.relative_to(self.tmp) / "seats.tsv"), "slug\tstate\n")
        self.assertEqual(runs.seat_summary(run), "")


if __name__ == "__main__":
    unittest.main()
