"""The run plan check's model rules (D37): a seat's model is its role's, and a verifier is never weaker than
the builder it checks."""
from __future__ import annotations

import unittest

from council.commands import plan_check
from council.records import models

RUN = "2026-01-02-030405-council-implement"
PLAN = """kind\tid\tfield\tvalue\treason
schema\tplan\tversion\t1\tv
run\trun\tid\t%s\tr
run\trun\tmode\tcouncil-implement\tm
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
seat\tbuild-1\tdisposition\tselected\tbuild
seat\tbuild-1\trole\tworker\tw
context\tbuild-1\tlevel\tfocused\tf
budget\tbuild-1\ttool-calls\t30\tt
seat\tverify-1\tdisposition\tselected\tcheck
seat\tverify-1\trole\tverifier\tv
context\tverify-1\tlevel\tminimal\tm
budget\tverify-1\ttool-calls\t20\tt
""" % RUN
GIVEN = plan_check.Settings(RUN, "council-implement", 10, None, "off", False)
SPLIT = models.Models("sonnet", "haiku", "fable", True)


def problems(rows: str = "", **changes: object) -> list[str]:
    return plan_check.judge(PLAN + rows, GIVEN._replace(**changes)).problems


def rows(**chosen: str) -> str:
    return "".join("seat\t%s\tmodel\t%s\tm\n" % (seat.replace("_", "-"), model) for seat, model in chosen.items())


class SeatModelTest(unittest.TestCase):
    def test_no_line_and_no_rows_change_nothing(self) -> None:
        self.assertEqual(problems(), [])
        self.assertEqual(problems(rows(build_1="inherit", verify_1="inherit")), [])

    def test_each_role_may_run_on_its_configured_model(self) -> None:
        self.assertEqual(problems(rows(build_1="sonnet", verify_1="fable"), models=SPLIT), [])
        review = PLAN.replace("council-implement", "council-review")
        self.assertEqual(plan_check.judge(review + rows(build_1="haiku", verify_1="fable"),
                                          GIVEN._replace(mode="council-review", run=RUN.replace(
                                              "implement", "review"), models=SPLIT)).problems, [])

    def test_a_model_its_role_is_not_configured_for_is_refused_with_the_fix(self) -> None:
        self.assertEqual(problems(rows(build_1="opus"), models=SPLIT), [
            "ERROR line 24: opus is not the builder model in council.config.md (- models: builder=sonnet) — set "
            "builder=opus there, or make seat/build-1/model sonnet"])
        self.assertEqual(problems(rows(build_1="fable")), [
            "ERROR line 24: fable is not the builder model in council.config.md (- models: builder=inherit) — set "
            "builder=fable there, or make seat/build-1/model inherit"])

    def test_the_chair_stays_on_the_sessions_model(self) -> None:
        self.assertEqual(problems(rows(chair="opus"), models=SPLIT), [
            "ERROR line 24: the Chair stays on the session's model — make seat/chair/model inherit"])

    def test_sonnet_or_haiku_outside_a_role_keeps_the_seat_models_rules(self) -> None:
        self.assertEqual(problems(rows(chair="sonnet")), [
            "ERROR line 24: only worker seats can use sonnet or haiku; chair has role chair",
            "ERROR line 24: seat model overrides are off; enable seat models: on in council.config.md",
            "ERROR line 24: sonnet or haiku needs seat/chair/purpose = mapping or survey"])
        mapper = "seat\tbuild-1\tpurpose\tmapping\tp\n" + rows(build_1="haiku")
        self.assertEqual(problems(mapper, seat_models="on"), [])
        self.assertEqual(problems(mapper, seat_models="off", models=SPLIT), [
            "ERROR line 25: seat model overrides are off; enable seat models: on in council.config.md"])

    def test_an_unknown_name_is_refused_on_its_row(self) -> None:
        self.assertEqual(problems(rows(verify_1="gpt")), [
            "ERROR line 24: seat model must be inherit, fable, opus, sonnet or haiku",
            "ERROR line 24: only worker seats can use sonnet or haiku; verify-1 has role verifier",
            "ERROR line 24: seat model overrides are off; enable seat models: on in council.config.md",
            "ERROR line 24: sonnet or haiku needs seat/verify-1/purpose = mapping or survey"])

    def test_the_configs_own_problem_is_refused_while_the_run_is_open(self) -> None:
        bad = models.Models(written=True, problem="council.config.md's `- models:` line: 'gpt' is not a model")
        self.assertEqual(problems(models=bad), ["ERROR: council.config.md's `- models:` line: 'gpt' is not a model"])
        self.assertEqual(problems(models=bad, seat_models="closed"), [])

    def test_a_closed_run_keeps_the_role_models_of_its_day(self) -> None:
        self.assertEqual(problems(rows(build_1="opus", verify_1="fable"), seat_models="closed"), [])


class VerifierTest(unittest.TestCase):
    CHAIR = ("the Chair, which builds, on inherit — put the verifier on inherit, as its builder is (seat/verify-1/"
             "model, and verifier= in council.config.md's - models:)")

    def test_a_weaker_verifier_is_refused_naming_the_fix(self) -> None:
        inverted = models.Models("opus", "inherit", "sonnet", True)
        self.assertEqual(problems(rows(build_1="opus", verify_1="sonnet"), models=inverted), [
            "ERROR line 25: verifier verify-1 on sonnet is weaker than builder build-1 on opus — put the verifier "
            "on opus or stronger (seat/verify-1/model, and verifier= in council.config.md's - models:)",
            "ERROR line 25: verifier verify-1 on sonnet is weaker than " + self.CHAIR])

    def test_a_builds_verifier_is_judged_against_the_chair_on_the_sessions_model(self) -> None:
        cheap = models.Models(verifier="opus", written=True)
        self.assertEqual(problems(rows(verify_1="opus"), models=cheap), [
            "ERROR line 24: verifier verify-1 on opus is weaker than builder build-1 on inherit — put the verifier on "
            "inherit, as its builder is (seat/verify-1/model, and verifier= in council.config.md's - models:)",
            "ERROR line 24: verifier verify-1 on opus is weaker than " + self.CHAIR])
        alone = "".join(line + "\n" for line in PLAN.splitlines() if "build-1" not in line)
        self.assertEqual(plan_check.judge(alone + rows(verify_1="opus"), GIVEN._replace(models=cheap)).problems, [
            "ERROR line 20: verifier verify-1 on opus is weaker than " + self.CHAIR])

    def test_an_equal_or_stronger_verifier_passes(self) -> None:
        for builder, verifier in (("inherit", "inherit"), ("haiku", "inherit"), ("opus", "fable"),
                                  ("sonnet", "fable"), ("inherit", "fable")):
            given = models.Models(builder, "inherit", verifier, True)
            self.assertEqual(problems(rows(build_1=builder, verify_1=verifier), models=given), [],
                             (builder, verifier))

    def test_a_review_has_no_builder_so_its_verifier_may_be_cheaper(self) -> None:
        mapper = "seat\tbuild-1\tpurpose\tmapping\tp\n" + rows(build_1="haiku")
        self.assertEqual(problems(mapper, seat_models="on"), [])          # a mapping seat is not checked work
        review = PLAN.replace("council-implement", "council-review")
        given = GIVEN._replace(mode="council-review", run=RUN.replace("implement", "review"),
                               models=models.Models("inherit", "opus", "sonnet", True))
        self.assertEqual(plan_check.judge(review + rows(build_1="opus", verify_1="sonnet"), given).problems, [])


if __name__ == "__main__":
    unittest.main()
