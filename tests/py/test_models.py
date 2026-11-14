"""The `- models:` reader (D37) and the order a verifier is judged by."""
from __future__ import annotations

import unittest
from pathlib import Path

import support

from council.records import models

WHERE = "council.config.md's `- models:` line"


class ReadTest(support.Scratch):
    def home(self, text: str) -> Path:
        self.write(".council/council.config.md", text)
        return self.tmp / ".council"

    def test_no_line_and_no_config_read_as_inherit_for_every_role(self) -> None:
        self.assertEqual(models.models(self.tmp / "none"), models.Models())
        self.assertEqual(models.models(None), models.Models())
        found = models.models(self.home("## Run preferences\n- seat models: on\n"))
        self.assertEqual((found.builder, found.review, found.verifier, found.written), ("inherit",) * 3 + (False,))
        self.assertEqual(models.shown(found), [])

    def test_a_split_is_read_and_shown(self) -> None:
        found = models.models(self.home("- seat models: off\n  - models: Builder=Sonnet,review = haiku ,"
                                        "verifier=opus <!-- confirmed -->\r\n- models: builder=fable\n"))
        self.assertEqual(found, models.Models("sonnet", "haiku", "opus", True, ""))
        self.assertEqual(models.shown(found),
                         ["  models: builder=sonnet · review=haiku · verifier=opus (council.config.md)"])

    def test_a_role_left_out_is_inherit(self) -> None:
        self.assertEqual(models.models(self.home("- models: verifier=fable\n")),
                         models.Models(verifier="fable", written=True))
        self.assertEqual(models.models(self.home("- models:\n")), models.Models(written=True))

    def test_a_word_it_cannot_take_is_its_problem_naming_the_fix(self) -> None:
        for line, problem in (
                ("builder=gpt-5", "%s: 'gpt-5' is not a model for builder — use inherit, fable, opus, sonnet or "
                                  "haiku" % WHERE),
                ("builder=claude-opus-4-1", "%s: 'claude-opus-4-1' is not a model for builder — use inherit, fable, "
                                            "opus, sonnet or haiku" % WHERE),
                ("lead=opus", "%s: 'lead' is not a role — use builder, review or verifier" % WHERE),
                ("opus", "%s: 'opus' is not role=model — write builder=, review= or verifier= with a model" % WHERE),
                ("builder=opus, builder=sonnet", "%s names builder twice — keep one" % WHERE)):
            found = models.models(self.home("- models: %s\n" % line))
            self.assertEqual(found.problem, problem, line)
            self.assertEqual((found.builder, found.verifier, found.written), ("inherit", "inherit", True))
            self.assertEqual(models.shown(found), [])

    def test_the_seat_models_line_is_not_this_line(self) -> None:
        self.assertEqual(models.models(self.home("- seat models: builder=opus\n")), models.Models())


class WeakerTest(unittest.TestCase):
    def test_named_models_compare_by_their_order(self) -> None:
        self.assertTrue(models.weaker("sonnet", "opus"))
        self.assertTrue(models.weaker("haiku", "sonnet"))
        self.assertTrue(models.weaker("opus", "fable"))
        self.assertFalse(models.weaker("opus", "opus"))
        self.assertFalse(models.weaker("fable", "haiku"))

    def test_inherit_is_the_sessions_model(self) -> None:
        self.assertFalse(models.weaker("inherit", "inherit"))
        self.assertFalse(models.weaker("inherit", "fable"))      # the Chair dispatches no builder above itself
        self.assertTrue(models.weaker("opus", "inherit"))        # the session may be on fable
        self.assertFalse(models.weaker("fable", "inherit"))

    def test_an_unknown_name_is_left_to_its_own_row(self) -> None:
        self.assertFalse(models.weaker("gpt", "opus"))
        self.assertFalse(models.weaker("haiku", "gpt"))


if __name__ == "__main__":
    unittest.main()
