"""The run plan check (council run plan check and show), as the helper's awk judged a plan."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

import support

from council.commands import plan, plan_check

RUN = "2026-01-02-030405-council-review"
PLAN = """kind\tid\tfield\tvalue\treason
schema\tplan\tversion\t1\tv
run\trun\tid\t%s\tr
run\trun\tmode\tcouncil-review\tm
run\trun\tsize\tsquad\ts
assessment\trun\trisk\tmedium\tr
assessment\trun\tcomplexity\tmedium\tc
assessment\trun\tuncertainty\tlow\tu
budget\trun\tagent-cap\t5\tc
budget\trun\testimated-tokens\t200000\te
verification\trun\tlevel\tindependent\tv
seat\tchair\tdisposition\tselected\tlead
seat\tchair\trole\tchair\tlead
context\tchair\tlevel\tfull\tall
budget\tchair\ttool-calls\t50\tt
seat\timpl\tdisposition\tselected\tbuild
seat\timpl\trole\tworker\tw
context\timpl\tlevel\tfocused\tf
budget\timpl\ttool-calls\t30\tt
seat\tverify-1\tdisposition\tselected\tcheck
seat\tverify-1\trole\tverifier\tv
context\tverify-1\tlevel\tminimal\tm
budget\tverify-1\ttool-calls\t20\tt
seat\tsecurity\tdisposition\tskipped\tno signal
seat\tsecurity\trole\tworker\tw
""" % RUN
GIVEN = plan_check.Settings(RUN, "council-review", 10, None, "off", False)


def judged(text: str = PLAN, **changes: object) -> plan_check.Verdict:
    return plan_check.judge(text, GIVEN._replace(**changes))


class JudgeTest(unittest.TestCase):
    def test_a_valid_plan_gets_its_line(self) -> None:
        self.assertEqual(judged(), plan_check.Verdict(
            [], "plan: valid · squad · 3 selected, 1 skipped · 2 agent run(s) of cap 5"))

    def test_line_numbers_count_comments_and_blank_lines(self) -> None:
        text = "# a\n\n" + PLAN.replace("tool-calls\t30", "tool-calls\t0")
        self.assertEqual(judged(text).problems, ["ERROR line 21: tool-calls must be an integer from 1 to 200"])

    def test_a_lines_carriage_returns_are_dropped(self) -> None:          # cells.lines_of, as awk on Windows
        self.assertEqual(judged(PLAN.replace("\n", "\r\n")).problems, [])
        self.assertEqual(judged(PLAN.replace("\n", "\r\r\n")).problems, [])

    def test_a_byte_order_mark_is_not_part_of_the_header(self) -> None:
        self.assertEqual(judged("﻿" + PLAN).problems[0], "ERROR line 1: header must be exactly: "
                         "kind\tid\tfield\tvalue\treason")

    def test_an_empty_plan_names_each_missing_row(self) -> None:
        problems = judged("").problems
        self.assertEqual(problems[:2], ["ERROR: missing header",
                                        "ERROR: missing schema version row (schema/plan/version)"])
        self.assertEqual(problems[-2:], [
            "ERROR: add at least one considered seat with a selected or skipped disposition",
            "ERROR: select exactly one Chair; found 0"])

    def test_a_problem_found_twice_is_said_once(self) -> None:
        problems = judged(PLAN + "seat\tghost\tdisposition\tselected\tx\n").problems
        self.assertEqual(problems.count("ERROR: seat ghost has no role row"), 1)
        self.assertIn("ERROR: selected  ghost has no budget/tool-calls row", problems)    # no role: awk printed ""

    def test_a_padded_number_compares_as_text_as_awk_did(self) -> None:
        self.assertEqual(judged(PLAN.replace("agent-cap\t5", "agent-cap\t 9")).problems,
                         ["ERROR line 9: agent-cap 9 exceeds the configured cap 10"])
        self.assertEqual(judged(PLAN.replace("agent-cap\t5", "agent-cap\t9")).problems, [])
        self.assertEqual(judged(PLAN.replace("agent-cap\t5", "agent-cap\t05")).problems, [])

    def test_the_users_go_lets_the_plan_past_the_cap(self) -> None:
        over = PLAN.replace("agent-cap\t5", "agent-cap\t12")
        self.assertEqual(judged(over).problems, ["ERROR line 9: agent-cap 12 exceeds the configured cap 10"])
        self.assertEqual(judged(over, go=11).problems,
                         ["ERROR line 9: agent-cap 12 exceeds the configured cap 10 or the user's go up to 11 "
                          "agent runs (council cap allow)"])
        self.assertEqual(judged(over, go=12).valid,
                         "plan: valid · squad · 3 selected, 1 skipped · 2 agent run(s) of cap 12 — past the cap under "
                         "the user's go, up to 12 (council cap allow)")

    def test_a_workflow_seat_counts_its_agents(self) -> None:
        problems = judged(PLAN + "budget\timpl\tagent-runs\t9\tw\n").problems
        self.assertEqual(problems, ["ERROR: 10 planned agent runs exceed the plan cap 5 (a Workflow seat counts every "
                                    "agent it starts: budget/<seat>/agent-runs)"])

    def test_full_needs_the_users_go(self) -> None:
        full = PLAN.replace("size\tsquad", "size\tfull")
        self.assertIn("ERROR: Full needs the user's explicit size-and-cost go: ask them, then record their words with "
                      "council state decision=\"…\"", judged(full).problems)
        self.assertNotIn("Full needs the user", " ".join(judged(full, full_go=True).problems))

    def test_another_model_needs_the_setting_a_worker_and_a_purpose(self) -> None:
        text = PLAN + "seat\tverify-1\tmodel\tsonnet\tm\n"
        self.assertEqual(judged(text).problems, [
            "ERROR line 26: only worker seats can use sonnet or haiku; verify-1 has role verifier",
            "ERROR line 26: seat model overrides are off; enable seat models: on in council.config.md",
            "ERROR line 26: sonnet or haiku needs seat/verify-1/purpose = mapping or survey"])
        self.assertNotIn("overrides are off", " ".join(judged(text, seat_models="closed").problems))

    def test_a_number_reads_and_writes_as_awk_does(self) -> None:
        self.assertEqual([plan_check.number(s) for s in ("12", " 7x", "1e3", "abc", "-3", ".5")],
                         [12.0, 7.0, 1000.0, 0.0, -3.0, 0.5])
        self.assertEqual([plan_check.number_text(n) for n in (12.0, 2.5, 1e20)], ["12", "2.5", "100000000000000000000"])


class ShownTest(unittest.TestCase):
    def test_the_summary_names_the_budget_and_each_seat(self) -> None:
        lines = plan.shown(PLAN + "budget\trun\tchair-tokens\t20000\tc\n")
        self.assertEqual(lines[0], "Run plan — " + RUN)
        self.assertIn("  the Chair's own share: 20000 tokens (agents are compared with the rest)", lines)
        self.assertEqual(lines[-4:], ["    selected — chair (chair) · context full · 50 tool calls — lead",
                                      "    selected — impl (worker) · context focused · 30 tool calls — build",
                                      "    selected — verify-1 (verifier) · context minimal · 20 tool calls — check",
                                      "    skipped — security (worker) — no signal"])

    def test_models_are_shown_once_a_seat_asks_for_another(self) -> None:
        lines = plan.shown(PLAN + "seat\timpl\tmodel\tsonnet\tm\nseat\timpl\tpurpose\tmapping\tp\n")
        self.assertIn("    selected — impl (worker) · context focused · 30 tool calls · purpose mapping · model sonnet "
                      "— build", lines)
        self.assertIn("    selected — chair (chair) · context full · 50 tool calls · model inherit — lead", lines)

    def test_cells_are_shown_as_written_without_a_carriage_return(self) -> None:
        padded = PLAN.replace("\tno signal", "\tno signal ").replace("\n", "\r\n")
        self.assertEqual(plan.shown(padded)[-1], "    skipped — security (worker) — no signal ")


class SettingsTest(support.Scratch):
    def state(self, text: str) -> Path:
        run = self.run_folder(RUN)
        (run / "session-state.md").write_text(text, encoding="utf-8")
        return run

    def test_an_open_run_counts_decisions_from_the_minute_it_opened(self) -> None:
        run = self.state("status: in-progress\nmode: council-review\nopened: 2026-01-02 03:04:05\n\n"
                         "## Decisions so far\n- 2026-01-02 03:04: \"go\"\n")
        self.assertEqual(plan.settings(run, str(self.tmp / ".council")),
                         plan_check.Settings(RUN, "council-review", 10, None, "off", True))

    def test_a_decision_before_the_run_opened_is_no_go(self) -> None:
        run = self.state("status: in-progress\nopened: 2026-01-02 03:05:00\n\n## Decisions so far\n"
                         "- 2026-01-02 03:04: \"go\"\n")
        self.assertFalse(plan.settings(run, str(self.tmp / ".council")).full_go)

    def test_a_closed_run_keeps_the_settings_of_its_day(self) -> None:
        run = self.state("status: complete\nmode: council-review\n")
        (self.tmp / ".council" / "council.config.md").write_text("- agent cap: 4\n", encoding="utf-8")
        (run / "cap-allowances.tsv").write_text("at\tused\tn\tuntil\tsaid\nx\t4\t2\t6\tgo\n", encoding="utf-8")
        self.assertEqual(plan.settings(run, str(self.tmp / ".council")),
                         plan_check.Settings(RUN, "council-review", 4, 6, "closed", True))


class CommandTest(support.Scratch):
    def test_check_prints_the_problems_and_their_count(self) -> None:
        run = self.run_folder(RUN)
        (run / "session-state.md").write_text("status: complete\nmode: council-review\n", encoding="utf-8")
        (run / "run-plan.tsv").write_bytes(PLAN.replace("tool-calls\t30", "tool-calls\t0").encode("utf-8"))
        said: list[str] = []
        with mock.patch.object(plan.where, "council_home", return_value=str(self.tmp / ".council")), \
                mock.patch.object(plan.cli, "say", said.append):
            self.assertEqual(plan.check(run, quiet=True), 1)
            self.assertEqual(said, ["ERROR line 19: tool-calls must be an integer from 1 to 200",
                                    "plan: 1 error(s) · run-plan.tsv"])

    def test_the_plan_is_read_whole_with_its_bytes(self) -> None:
        run = self.run_folder(RUN)
        (run / "run-plan.tsv").write_bytes(b"\xef\xbb\xbfkind\xe9\n")
        self.assertEqual(plan.whole(run), "﻿kind\udce9\n")


if __name__ == "__main__":
    unittest.main()
