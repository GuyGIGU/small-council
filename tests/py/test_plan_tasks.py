"""A plan's tasks and the plan check's task rules: the request's words, the map's one-way-per-job table, the task
rows, and the rules on Serves, Owner, Rests on and the probe an unchecked outside fact needs first."""
from __future__ import annotations

import unittest

import support

from council.commands import plan_tasks
from council.records import map_file, request, tasks

REQUEST = "Charge the card once, even when the payment provider retries the webhook. Keep the receipt email."
MAP = """# Codebase map — x
## Where things live
| Area | Path | Responsibility | Entry points |
|---|---|---|---|
| Payments | src/pay/ | charges | api |

## One way per job
| Job | Owner | The one way | Anchor path |
|---|---|---|---|
| Charge a card | src/pay/ | `charge()` through the gateway client | src/pay/charge.py |
| Send an email | src/mail/ | the outbox queue | src/mail/outbox.py |

## Hot spots
| not | a | way | row |
"""


def plan(*bodies: str) -> str:
    """A plan deliverable with these task bodies under ## Task Sequence."""
    return "# Council Plan: x\n\n## Task Sequence\n" + "".join(bodies) + "\n## Risks & Watchpoints\n- none\n"


def task(n: int, serves: str = '"Charge the card once"', owner: str = "src/pay/ — Charge a card",
         rests: str = "the charge table has a unique key (OBSERVED)", depends: str = "—") -> str:
    rows = [("Depends on", depends), ("Serves", serves), ("Owner", owner), ("Rests on", rests),
            ("Done when", "a retried webhook charges once")]
    return "### %d. Task %d\n| | |\n|---|---|\n" % (n, n) + "".join(
        "| **%s** | %s |\n" % (k, v) for k, v in rows if v is not None) + "\nWhy.\n\n"


def judged(text: str, ways: str | None = MAP) -> plan_tasks.Verdict:
    return plan_tasks.judge(tasks.read(text), request.fold(REQUEST), None if ways is None else map_file.ways(ways),
                            ".council/plans/x.md")


class RequestTest(unittest.TestCase):
    def test_a_quote_is_whole_words_from_the_request(self) -> None:
        self.assertEqual(request.verdict('"Charge the card once"', REQUEST), "ok")
        self.assertEqual(request.verdict('"harge the card once"', REQUEST), "NOT-IN-THE-REQUEST")
        self.assertEqual(request.verdict('"Charge the card twice"', REQUEST), "NOT-IN-THE-REQUEST")
        self.assertEqual(request.verdict("Charge the card once", REQUEST), "NO-QUOTE")
        self.assertEqual(request.verdict('"the card"', REQUEST), "TOO-SHORT")
        self.assertEqual(request.verdict('"Fix typos"', "Fix typos"), "ok")

    def test_curly_quotes_odd_spaces_and_an_ellipsis_fold(self) -> None:
        self.assertEqual(request.verdict("“Charge the card once…”", REQUEST), "ok")

    def test_a_quote_holding_quotes_runs_to_its_own_closing_mark(self) -> None:
        said = 'The button should say "Save" not "OK" here.'
        self.assertEqual(request.verdict('"say "Save" not "OK" here."', said), "ok")
        # as bash's: the first closing mark ends "say", under three words
        self.assertEqual(request.verdict('"say "Save" or "Store""', said), "TOO-SHORT")


class WordsTest(support.Scratch):
    def test_the_words_come_from_ask_md_and_the_filed_request(self) -> None:
        run = self.run_folder("2026-01-02-030405-council-plan")
        self.write(".council/asks/first.md", "# Ask\n## In your words\nKeep the receipt email.\n")
        self.write(".council/runs/2026-01-02-030405-council-plan/ask.md",
                   "# Ask\ncontinues: `.council/asks/first.md`\n\n## In your words\nCharge the card\n  once.\n"
                   "## Later, in your words\n(no new words)\n")
        self.assertEqual(request.words(run), "Charge the card once. Keep the receipt email.")


class MapTest(unittest.TestCase):
    def test_the_table_rows_are_read_and_other_tables_are_not(self) -> None:
        ways = map_file.ways(MAP)
        self.assertEqual([w.job for w in ways], ["Charge a card", "Send an email"])
        self.assertEqual(ways[0].way, "charge() through the gateway client")

    def test_no_table_is_none_and_an_empty_table_is_no_rows(self) -> None:
        self.assertIsNone(map_file.ways("# Map\n## Shape\nx\n"))
        empty = "## One way per job\n| Job | Owner | The one way | Anchor path |\n|---|---|---|---|\n"
        self.assertEqual(map_file.ways(empty), [])


class TaskRowsTest(unittest.TestCase):
    def test_tasks_and_their_rows_under_the_sequence_only(self) -> None:
        found = tasks.read("## Summary\n### 9. Not a task\n" + plan(task(1), task(2, depends="Task 1")))
        self.assertEqual([(t.number, t.title) for t in found], [(1, "Task 1"), (2, "Task 2")])
        self.assertEqual(found[1].rows["depends on"], "Task 1")
        self.assertEqual(found[0].rows["serves"], '"Charge the card once"')

    def test_facts_states_and_outside(self) -> None:
        self.assertEqual(tasks.facts("—"), [])
        self.assertIsNone(tasks.facts(None))
        self.assertEqual(tasks.facts("the API returns 409 (assumed, outside); rows are unique (OBSERVED); a guess"),
                         [tasks.Fact("the API returns 409", "ASSUMED", True),
                          tasks.Fact("rows are unique", "OBSERVED", False), tasks.Fact("a guess", "", False)])

    def test_depends_and_kind(self) -> None:
        self.assertEqual(tasks.depends("Task 1, Task 3"), [1, 3])
        self.assertEqual(tasks.depends("—"), [])
        self.assertEqual([tasks.kind(o) for o in ("Probe: does it 409?", "**Research:** x", "New way: none fits",
                                                  "src/pay/ — Charge a card", None)],
                         ["probe", "research", "new", "way", "way"])


class RulesTest(unittest.TestCase):
    def test_a_good_plan_passes_with_its_line(self) -> None:
        verdict = judged(plan(task(1), task(2, serves='"Keep the receipt email."', owner="Send an email")))
        self.assertEqual(verdict.problems, [])
        self.assertEqual(verdict.notes, ["tasks: 2 checked against the request · .council/plans/x.md"])

    def test_serves_missing_or_not_the_request(self) -> None:
        problems = judged(plan(task(1, serves=None), task(2, serves='"charge it twice please"'))).problems
        self.assertEqual(len(problems), 2)
        self.assertIn("task 1 has no Serves row", problems[0])
        self.assertIn("task 2's Serves quotes words the request never said", problems[1])

    def test_owner_names_a_row_or_says_new_way(self) -> None:
        problems = judged(plan(task(1, owner="src/pay/"), task(2, owner="New way: no queue exists"),
                               task(3, owner="New way:"), task(4, owner=None))).problems
        self.assertEqual(len(problems), 3)
        self.assertIn("task 1's Owner names no row", problems[0])
        self.assertIn("Charge a card; Send an email", problems[0])
        self.assertIn("task 3 says New way: but not why", problems[1])
        self.assertIn("task 4 has no Owner row", problems[2])

    def test_with_no_table_the_owner_check_is_skipped_and_said(self) -> None:
        for ways in (None, "## One way per job\n| Job | Owner | The one way | Anchor path |\n|---|---|---|---|\n"):
            verdict = judged(plan(task(1, owner="src/pay/")), ways)
            self.assertEqual(verdict.problems, [])
            self.assertIn("tasks: owner check skipped", verdict.notes[0])

    def test_a_new_way_is_named_for_the_user(self) -> None:
        self.assertIn("New way in task 1: put it to the user as a ruling",
                      judged(plan(task(1, owner="New way: no gateway client exists"))).notes[-1])

    def test_rests_on_needs_states(self) -> None:
        problems = judged(plan(task(1, rests=None), task(2, rests="the key is unique"))).problems
        self.assertIn("task 1 has no Rests on row", problems[0])
        self.assertIn("task 2 rests on 'the key is unique' with no evidence state", problems[1])

    def test_an_unchecked_outside_fact_needs_a_probe_before_it(self) -> None:
        guess = "the provider retries for 3 days (ASSUMED, outside)"
        refused = judged(plan(task(1, rests=guess)))
        self.assertEqual(len(refused.problems), 1)
        self.assertIn("with no probe or research task before it", refused.problems[0])
        probe = task(1, owner="Probe: how long does the provider retry?", rests=guess)
        self.assertEqual(judged(plan(probe, task(2, rests=guess, depends="Task 1"))).problems, [])
        through = plan(probe, task(2, depends="Task 1"), task(3, rests=guess, depends="Task 2"))
        self.assertEqual(judged(through).problems, [])                # through another task is still before it
        inside = "the charge table is keyed by id (ASSUMED)"
        self.assertEqual(judged(plan(task(1, rests=inside))).problems, [])   # inside the repo: a builder reads it
        self.assertEqual(judged(plan(task(1, rests="the provider signs it (OBSERVED, outside)"))).problems, [])

    def test_a_plan_with_no_tasks_is_refused(self) -> None:
        self.assertIn("has no tasks under ## Task Sequence", judged("# Plan\n## Summary\n").problems[0])


class RunTest(support.Scratch):
    def test_only_an_open_plan_runs_recorded_deliverable_is_judged(self) -> None:
        run = self.run_folder("2026-01-02-030405-council-plan")
        self.write(".council/runs/2026-01-02-030405-council-plan/session-state.md",
                   "status: in-progress\nmode: council-plan\n\n## Decisions so far\n")
        self.assertEqual(plan_tasks.judge_run(run), plan_tasks.Verdict([], []))
        self.write(".council/runs/2026-01-02-030405-council-plan/session-state.md",
                   "status: in-progress\nmode: council-plan\ndeliverable: .council/plans/x.md\n")
        self.assertEqual(len(plan_tasks.judge_run(run).problems), 2)          # the problem and its count line
        self.assertIn("can't be read", plan_tasks.judge_run(run).problems[0])
        self.write(".council/runs/2026-01-02-030405-council-plan/ask.md", "# Ask\n## In your words\n" + REQUEST + "\n")
        self.write(".council/plans/x.md", plan(task(1)))
        self.write(".council/map.md", MAP)
        self.assertEqual(plan_tasks.judge_run(run).problems, [])
        self.write(".council/runs/2026-01-02-030405-council-plan/session-state.md",
                   "status: complete\nmode: council-plan\ndeliverable: .council/plans/gone.md\n")
        self.assertEqual(plan_tasks.judge_run(run), plan_tasks.Verdict([], []))


if __name__ == "__main__":
    unittest.main()
