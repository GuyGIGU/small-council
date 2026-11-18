"""The state and event pieces no command reaches yet: the close's own state write (closing, events_lost), the
stream's ready codes, the stage table, the status nudge and card-due mark (held to bin/council's own lines), the
two flattenings of said(), open runs of any status, the newest run and stopped_short."""
from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr
from unittest import mock

import support  # noqa: F401  (src/ on the path)
from council import clock
from council.commands import event_note, cli, nudges, resolve
from council.records import closing, events, redact, stages, state_write

OPENED = events.HEADER + "\n1\t1\t2026-01-01T00:00:00Z\trun.opened\trun\tcouncil-review\tphase=convene\n"
STATE = ("mode: council-review\nstatus: in-progress\nphase: judge\nwaiting: q\nnext: n\nupdated: x\nevents-schema: 1\n"
         "code-root: -\n\n## Decisions so far\n")


class Spine(support.Scratch):
    def setUp(self) -> None:
        super().setUp()
        self.run = self.run_folder()
        self.write(".council/runs/%s/session-state.md" % self.run.name, STATE)
        self.write(".council/runs/%s/events.tsv" % self.run.name, OPENED)

    def rows(self) -> list:
        return [line.split("\t")[3:] for line in (self.run / "events.tsv").read_text().splitlines()[2:]]


class ChangeTest(Spine):
    def test_a_close_writes_a_closed_run_and_lets_a_lost_status_event_go(self) -> None:
        changed = state_write.change(self.run, ["status=complete", "closed=2026-01-01 00:00:00", "waiting="],
                                     closing=True)
        self.assertEqual((changed.status, changed.warnings), ("complete", []))
        self.assertTrue(state_write.closed(self.run))
        with mock.patch.object(events, "append", side_effect=[events.EventError("could not append"), True]):
            changed = state_write.change(self.run, ["status=abandoned", "waiting=w"], closing=True)
        self.assertEqual(changed.warnings, ["could not append", "the status event could not be recorded; the close "
                                            "goes on — council run events check --run " + self.run.name])
        self.assertFalse((self.run / "session-state.md.lock").exists())

    def test_a_wait_event_lost_after_a_close_note_says_both(self) -> None:
        with mock.patch.object(events, "append", side_effect=events.EventError("held")), \
                self.assertRaises(state_write.StateError) as caught:
            state_write.change(self.run, ["status=abandoned", "closed=now"], closing=True)
        self.assertEqual(str(caught.exception).split("\ncouncil: "), [
            "held", "the status event could not be recorded; the close goes on — council run events check --run "
            + self.run.name, "held", "state changed, but the waiting event could not be recorded"])

    def test_a_lost_stream_takes_the_close_without_phase_or_status_events(self) -> None:
        (self.run / "session-state.md").write_text(STATE.replace("waiting: q", "waiting: "))
        (self.run / "events.tsv").write_bytes(b"torn")
        state_write.change(self.run, ["phase=learn", "status=paused"], events_lost=True, closing=True)
        self.assertIn("phase: learn\nwaiting: \n", (self.run / "session-state.md").read_text())
        self.assertEqual((self.run / "events.tsv").read_bytes(), b"torn")

    def test_without_closing_a_lost_status_event_refuses(self) -> None:
        with mock.patch.object(events, "append", side_effect=events.EventError("no")), \
                self.assertRaises(state_write.StateError) as caught:
            state_write.change(self.run, ["status=paused", "waiting=x"])
        self.assertEqual(str(caught.exception),
                         "no\ncouncil: state changed, but the status event could not be recorded")


class ReadyTest(Spine):
    def test_each_stream_shape_has_its_code_and_reason(self) -> None:
        unnumbered = (2, "its last row is not a numbered event")
        for data, want in ((OPENED, (0, "")), (OPENED + "1\t2\tx", (1, "its last line is torn")),
                           (events.HEADER + "\r\n", (2, "it holds no events")), ("", unnumbered),
                           (OPENED + "junk\n", unnumbered)):
            (self.run / "events.tsv").write_bytes(data.encode())
            self.assertEqual(events.ready(self.run), want, data)
        (self.run / "events.tsv").unlink()
        self.assertEqual(events.ready(self.run), (2, "events.tsv is missing"))
        with self.assertRaises(events.EventError) as caught:
            events.writable(self.run)
        self.assertIn("is lost (events.tsv is missing), so nothing was written", str(caught.exception))
        (self.run / "session-state.md").write_text("status: in-progress\n")
        self.assertEqual(events.ready(self.run), (0, ""))           # a run from before the stream

    def test_need_refuses_with_the_reason_first(self) -> None:
        (self.run / "events.tsv").write_bytes(b"x")
        with self.assertRaises(cli.Refusal) as caught:
            event_note.need(self.run, "run.x", "run", "v", "d", "it failed")
        self.assertTrue(str(caught.exception).startswith("could not append a valid event to "))
        self.assertTrue(str(caught.exception).endswith("\ncouncil: it failed"))


class StagesTest(Spine):
    def plan(self, *rows: str) -> None:
        (self.run / "run-plan.tsv").write_bytes("".join(row + "\n" for row in rows).encode())

    def mode(self, mode: str) -> None:
        self.write(".council/runs/%s/session-state.md" % self.run.name, STATE.replace("council-review", mode))

    def test_a_review_takes_its_own_path_whatever_its_plan(self) -> None:          # the reader and the runner (D50)
        review = ["convene", "prepare", "work", "judge", "challenge", "deliver", "learn"]
        self.assertEqual(stages.required(self.run), review)
        self.plan("seat\treader\trole\tworker", "seat\treader\tdisposition\tselected", "run\trun\tsize\tsolo")
        self.assertEqual(stages.required(self.run), review)
        self.assertEqual(stages.skipped(self.run, "prepare", "judge"), ["work"])

    def test_the_path_a_run_must_take(self) -> None:
        self.mode("council-plan")
        self.assertEqual(stages.required(self.run), stages.SHORT.split())  # noqa: SIM905
        self.plan("seat\thunt\trole\t worker ", "seat\thunt\tdisposition\tselected\r", "run\trun\tsize\tsquad")
        self.assertEqual(len(stages.required(self.run)), 10)
        self.assertEqual(stages.skipped(self.run, "prepare", "judge"), ["assign", "brief", "work", "collect"])
        self.plan("seat\thunt\trole\tworker", "seat\thunt\tdisposition\tselected", "run\trun\tsize\tsolo")
        self.assertEqual(stages.skipped(self.run, "prepare", "deliver"), ["judge", "challenge"])
        self.plan("seat\thunt\trole\tworker", "seat\thunt\tdisposition\tselected", "run\trun\tsize\tsolo",
                  "run\trun\tsize\tfull")                                           # the first row of a key wins
        self.assertEqual(stages.required(self.run), stages.SHORT.split())  # noqa: SIM905
        self.assertEqual(stages.skipped(self.run, "deliver", "prepare"), [])
        self.assertEqual(stages.skipped(self.run, "my-step", "learn"), [])
        self.assertEqual((stages.rank("build"), stages.next_text("build"), stages.rank("x")),
                         (5, "task 1 — the first task of the plan", 0))
        self.assertTrue(stages.name_ok("a-b", "test-architect") and not stages.name_ok("a-b", "council-review"))

    def test_the_method_a_mode_loads(self) -> None:
        build = stages.REQUIRED["council-implement"].split()
        self.assertEqual(stages.method_files("council-implement", build),   # the build loop has no doctrine file
                         ["skills/context-core/SKILL.md", "skills/council-implement/SKILL.md"] +
                         ["references/doctrine/%s.md" % n for n in ("01-convene", "02-prepare", "08-challenge",
                                                                   "09-deliver", "10-learn")])
        self.assertEqual(len(stages.method_files("council-plan")), 12)                        # none named: all ten
        self.assertEqual(stages.method_files("council-review", ["convene", "work"]),         # its one page (D47)
                         ["skills/council-review/SKILL.md"])
        self.assertEqual(stages.method_files("council-init", []), ["skills/context-core/SKILL.md",
                                                                   "skills/council-init/SKILL.md"])
        self.assertEqual(stages.method_files("context-core", ["learn", "learn", "x"]),
                         ["skills/context-core/SKILL.md", "references/doctrine/10-learn.md"])
        root = self.tmp / "plugin"
        self.write("plugin/skills/context-core/SKILL.md", "a\r\nb\n")                         # CRLF read as LF
        self.write("plugin/references/doctrine/01-convene.md", "é")                      # bytes, not characters
        self.assertEqual(stages.method_bytes("council-plan", ["convene", "prepare"], root.as_posix()), 4 + 2)
        self.write("plugin/skills/council-review/SKILL.md", "c\r\n")
        self.assertEqual(stages.method_bytes("council-review", ["convene", "prepare"], root.as_posix()), 2)


CARD = ("show the user its %s now, once: hand the output of `council status --widget%s` to a show_widget tool (it may "
        "be a deferred tool: search the tools for it before deciding there is none), else relay `council status%s` — "
        "and if the card fails to render, give that text and carry on")


class NudgeTest(Spine):
    def said(self, when: str, named: bool = False, alert: bool = False) -> str:
        """What bin/council's status_nudge said."""
        at = " --run " + self.run.name if named or when == "close" else ""
        if when == "dispatch":
            return "council: first dispatch of this run — " + CARD % ("status", at, at) + "\n"
        said = "council: run closed — " + CARD % ("closing card", at, at)
        if alert:
            said += ("; then send the owner the line `council status --line%s` prints, once, with a PushNotification "
                     "tool" % at)
        return said + "\n"

    def python(self, *args: object) -> str:
        said = io.StringIO()
        with redirect_stderr(said):
            nudges.status_nudge(self.run, *args)
        return said.getvalue()

    def test_the_status_nudge_says_what_bin_council_says(self) -> None:
        for when, named, alert, status in (("dispatch", False, False, "in-progress"), ("dispatch", True, False, "x"),
                                           ("close", False, True, "complete"), ("close", True, False, "x")):
            (self.run / "session-state.md").write_text(STATE.replace("in-progress", status))
            self.assertEqual(self.python(when, named), self.said(when, named, alert), when)
            self.assertEqual(nudges.card_due(self.run), when == "dispatch")
            (self.run / "card-due").unlink() if when == "dispatch" else None
        (self.tmp / ".council" / "council.config.md").write_text("- notifications: off\n")
        (self.run / "session-state.md").write_text(STATE.replace("in-progress", "complete"))
        self.assertEqual(self.python("close", False), self.said("close"))

    def test_the_card_due_mark(self) -> None:
        self.assertFalse(nudges.card_due(self.run))
        self.assertTrue(nudges.mark_card(self.run, "reminded") and not nudges.card_due(self.run))
        nudges.clear_card(self.run)
        nudges.clear_card(self.run)
        self.assertFalse((self.run / "card-due").exists())


class SmallPiecesTest(Spine):
    def test_said_flattens_the_line(self) -> None:
        self.assertEqual(redact.said("a\tb\r\nc\x0bd\x0ce"), "a b  c d e")
        self.assertIn("[redacted]", redact.said("token=sk-abcdefghijklmnopqrstuvwxyz123456"))

    def test_open_runs_of_any_status_and_the_newest(self) -> None:
        home = (self.tmp / ".council").as_posix()
        older = self.run_folder("2026-01-01-000000-council-plan")
        (older / "session-state.md").write_text("mode: council-plan\nstatus: paused\ncode-root: /t\n")
        self.assertEqual(len(resolve.open_runs(home, "/t")), 2)
        self.assertEqual(len(resolve.open_runs(home, "/t", "paused")), 1)
        (self.run / "session-state.md").write_text(STATE.replace("in-progress", "complete"))
        self.assertTrue(resolve.newest_run(home, "/t").endswith(self.run.name))
        self.assertEqual(resolve.newest_run(home + "/none", "/t"), "")

    def test_stopped_short_and_the_clock(self) -> None:
        self.assertTrue(closing.stopped_short(self.run))
        (self.run / "session-state.md").write_text(STATE.replace("judge", "learn"))
        self.assertFalse(closing.stopped_short(self.run))
        self.assertRegex(clock.now_sec(), r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$")
        self.assertRegex(clock.now_utc(), r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(len(clock.now_min()), 16)


if __name__ == "__main__":
    unittest.main()
