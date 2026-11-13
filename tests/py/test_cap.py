"""The agent stop's commands: where a run stands (council cap), the gate's decision (council cap check),
the build loop's verifier rules, and the run a command acts on."""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

import support

from council.commands import agent_gate, cap, resolve, rounds
from council.records import usage

STATE = "mode: council-implement\nstatus: in-progress\nplan-schema: 1\n\n## Decisions so far\n"
EVENTS = "schema\tseq\tat\ttype\tsubject\tvalue\tdetail\n"


def event(seq: int, subject: str, value: str, at: str = "2026-01-02T03:04:05Z") -> str:
    return "1\t%d\t%s\tseat.updated\t%s\t%s\t-\n" % (seq, at, subject, value)


class RunPathTest(support.Scratch):
    def test_a_bare_name_and_a_runs_path_are_looked_up_under_the_home(self) -> None:
        run = self.run_folder()
        (run / "session-state.md").write_text(STATE, encoding="utf-8")
        home = str(self.tmp / ".council").replace("\\", "/")
        self.assertEqual(resolve.run_path(run.name, home), home + "/runs/" + run.name)
        self.assertEqual(resolve.run_path(".council/runs/" + run.name + "//", home), home + "/runs/" + run.name)
        absolute = str(run).replace("\\", "/")
        self.assertEqual(resolve.run_path(str(run) + "\\", home), absolute)
        self.assertEqual(resolve.run_path("missing", home), "missing")

    def test_a_relative_run_folder_is_made_absolute(self) -> None:
        run = self.run_folder()
        (run / "session-state.md").write_text(STATE, encoding="utf-8")
        here = os.getcwd()
        os.chdir(str(self.tmp))
        self.addCleanup(os.chdir, here)
        self.assertEqual(resolve.run_path(".council/runs/" + run.name, "/elsewhere"),
                         str(run.resolve()).replace("\\", "/") if os.name == "nt" else str(run.resolve()))


class WordsTest(unittest.TestCase):
    def test_tokens_shown_only_past_the_ceiling_and_as_numbers_when_rounding_hides_it(self) -> None:
        plain = usage.Standing(12, 12, 10, 0, None, None, True, True)
        self.assertEqual(cap.words("r", plain), "run r has used 12 of its 10 agent runs")
        over = usage.Standing(3, 3, 10, 1500000, 1200000, 5, True, True)
        self.assertEqual(cap.words("r", over), "run r has used 3 of its 10 agent runs and 1.5M tokens, over its 1.2M "
                                               "ceiling; the user's last go allowed up to 5")
        close = usage.Standing(3, 3, 10, 600400, 600000, None, True, True)
        self.assertIn("600400 tokens, over its 600000 ceiling", cap.words("r", close))


class RoundsTest(support.Scratch):
    def build(self, events: str, state: str = STATE) -> Path:
        run = self.run_folder("2026-01-02-030405-council-implement")
        (run / "session-state.md").write_text(state, encoding="utf-8")
        (run / "events.tsv").write_text(EVENTS + events, encoding="utf-8")
        return run

    def test_a_third_check_waits_for_a_diagnosis_or_the_users_go(self) -> None:
        run = self.build(event(1, "verify-2", "done") + event(2, "verify-2b", "running")
                         + event(3, "verify-2b", "done"))
        (run / "seats.tsv").write_text("slug\tstate\nverify-2\tdone\nverify-2b\tdone\n", encoding="utf-8")
        why = rounds.check_round(run, "verify-2c")
        self.assertTrue(why and why.startswith("cannot start verify-2c — it would be the third check of task 2"))
        with open(str(run / "events.tsv"), "a", encoding="utf-8") as stream:
            stream.write(event(4, "diagnose-2", "running"))
        self.assertIsNone(rounds.check_round(run, "verify-2c"))
        self.assertIsNone(rounds.check_round(run, "hunt"))

    def test_a_decision_after_the_last_verdict_lets_a_check_start(self) -> None:
        verdicts = event(1, "verify-1", "done") + event(2, "verify-1b", "done") + event(3, "verify-1c", "done")
        run = self.build(verdicts)
        (run / "seats.tsv").write_text("slug\tstate\nverify-1\tdone\n", encoding="utf-8")
        self.assertIn("task 1 has 3 verdicts", rounds.check_round(run, "verify-1d") or "")
        with open(str(run / "session-state.md"), "a", encoding="utf-8") as state:
            state.write('- 2999-01-01 00:00: "go on"\n')
        self.assertIsNone(rounds.check_round(run, "verify-1d"))

    def test_one_checker_per_batch_counts_starts_and_wants_a_go_for_each(self) -> None:
        run = self.build(event(1, "verify-1", "running") + event(2, "verify-1", "done"))
        home = str(self.tmp / ".council")
        self.assertIn("already started 1 verifier(s) (verify-1)", rounds.batch_check(run, "verify-2", home) or "")
        self.assertIsNone(rounds.batch_check(run, "hunt", home))
        (self.tmp / ".council" / "council.config.md").write_text("- checking: per task\n", encoding="utf-8")
        self.assertIsNone(rounds.batch_check(run, "verify-2", home))

    def test_a_verifier_still_running_is_the_same_start(self) -> None:
        run = self.build(event(1, "verify-1", "running"))
        self.assertIsNone(rounds.batch_check(run, "verify-1", str(self.tmp / ".council")))

    def test_decisions_are_counted_from_a_minute_on(self) -> None:
        run = self.build("", STATE + '- 2026-01-02 10:00: "a"\n- 2026-01-02 11:00: "b"\nnot one\n')
        self.assertEqual((rounds.decisions_since(run, ""), rounds.decisions_since(run, "2026-01-02 10:30")), (2, 1))

    def test_local_minute(self) -> None:
        self.assertEqual(rounds.local_minute("nonsense"), "")
        self.assertEqual(len(rounds.local_minute("2026-01-02T03:04:05Z")), 16)


class CallTest(unittest.TestCase):
    def test_details_after_the_tool_a_later_one_winning(self) -> None:
        call = agent_gate.read_call(["Agent", "type=t", "seat=a", "seat=b", "workflow=verifier", "hunt=any route"])
        self.assertEqual(call, agent_gate.Call("Agent", "t", "b", "", "", "any route", True))
        self.assertEqual(agent_gate.read_call([]).tool, "")


class GateTest(support.Scratch):
    def setUp(self) -> None:
        super().setUp()
        self.home = str(self.tmp / ".council").replace("\\", "/")

    def planned(self, name: str, rows: str, state: str = STATE) -> str:
        run = self.run_folder(name)
        (run / "session-state.md").write_text(state, encoding="utf-8")
        (run / "run-plan.tsv").write_text("kind\tid\tfield\tvalue\treason\n" + rows, encoding="utf-8")
        return self.home + "/runs/" + name

    def test_seat_runs_counts_a_recheck_as_its_base_seat(self) -> None:
        run = self.planned("2026-01-02-030405-council-implement", "seat\tverify-1\tdisposition\tselected\t-\n")
        old = self.planned("2026-01-01-030405-council-review", "", state="status: in-progress\n")
        self.assertEqual(agent_gate.seat_runs([run, old], "verify-1b", "council-verifier"),
                         agent_gate.Planned(1, run, True))
        self.assertEqual(agent_gate.seat_runs([run], "verify-1-a", "council-verifier").count, 1)
        self.assertEqual(agent_gate.seat_runs([run], "verify-1b", "council-worker").count, 0)

    def test_a_worker_for_an_unplanned_seat_is_refused_by_slug_only(self) -> None:
        run = self.planned("2026-01-02-030405-council-implement", "seat\thunt\tdisposition\tselected\t-\n")
        here = agent_gate.Where(self.home, "/no/tree", "")
        call = agent_gate.Call("Agent", "small-council:council-worker", "perf", run.split("/")[-1], "perf", "", False)
        refusal = agent_gate.dispatch_refusal(call, here) or ""
        self.assertTrue(refusal.startswith("Small Council: seat perf has no selected row in the run plan of "
                                           "2026-01-02-030405-council-implement"))
        shown = call._replace(seat="Security", file="")
        self.assertIsNone(agent_gate.dispatch_refusal(shown, here))           # a display name is never refused
        self.assertIsNone(agent_gate.dispatch_refusal(call._replace(seat="hunt"), here))
        self.assertIsNone(agent_gate.dispatch_refusal(call._replace(agent_type="Explore"), here))

    def test_a_closed_or_paused_run_named_with_none_open(self) -> None:
        name = "2026-01-02-030405-council-review"
        self.planned(name, "", state="status: complete\nplan-schema: 1\n")
        call = agent_gate.Call("Agent", "small-council:council-worker", "hunt", name, "", "", False)
        refusal = agent_gate.dispatch_refusal(call, agent_gate.Where(self.home, "/no/tree", "s1")) or ""
        self.assertIn("which is closed (complete)", refusal)

    def test_a_start_is_counted_once_with_a_seed_and_never_joins_a_torn_line(self) -> None:
        run = self.run_folder()
        (run / "session-state.md").write_text(STATE, encoding="utf-8")
        (run / "seats.tsv").write_text("slug\tstate\tagent\ttokens\tupdated\tnote\tagents\treported\n"
                                       "a\tdone\tx\t52000\tT\t\t2\t2\n", encoding="utf-8")
        here = agent_gate.Where(self.home, "/no/tree", "s\t1")
        with mock.patch.object(cap, "stamp", return_value="NOW"):
            agent_gate.count_start(run, "Agent", here, False)
            self.assertEqual((run / "agent-starts.tsv").read_text(),
                             "at\ttool\tsession\nNOW\tbefore:2\t-\nNOW\tAgent\ts 1\n")
            with open(str(run / "agent-starts.tsv"), "a", encoding="utf-8") as starts:
                starts.write("torn")
            agent_gate.count_start(run, "Task", here, False)
            self.assertTrue((run / "agent-starts.tsv").read_text().endswith("torn\nNOW\tTask\ts 1\n"))
            agent_gate.count_start(run, "Task", here, True)                 # refused by another run: not counted
        self.assertEqual((run / "agent-starts.tsv").read_text().count("\n"), 5)


if __name__ == "__main__":
    unittest.main()
