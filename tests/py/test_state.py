import unittest

import support

from council.records import state

STATE = ("\ufeffstatus: in-progress\n"
         " mode : council-review\n"
         "phase: work    # in the middle\n"
         "phase: judge\n"
         "events-schema: 1\n"
         "plan-schema: 1\n"
         "next:\n"
         "## Decisions so far\n"
         '- 2026-01-02 10:00: "go \\"full\\" C:\\\\temp"\n'
         "- 2026-01-02 11:00: raw words\n"
         "closed: 2026-01-03 09:00\n"
         "mode: council-implement\n")


class StateTest(support.Scratch):
    def test_header_reads_above_the_first_heading_only(self) -> None:
        fields = state.header(STATE.lstrip("\ufeff"))
        self.assertEqual(fields["status"], "in-progress")
        self.assertEqual(fields["mode"], "council-review")           # space around the key allowed
        self.assertEqual(fields["phase"], "work")                    # the first wins, its comment dropped
        self.assertEqual(fields["next"], "")
        self.assertNotIn("closed", fields)

    def test_exact_keys_and_comments(self) -> None:
        content = STATE.lstrip("\ufeff")
        self.assertNotIn("mode", state.header(content, exact_keys=True))
        self.assertEqual(state.header(content, comments=False)["phase"], "work    # in the middle")

    def test_values_anywhere(self) -> None:
        content = STATE.lstrip("\ufeff")
        self.assertEqual(state.values(content, "closed"), ["2026-01-03 09:00"])
        self.assertEqual(state.first_value(content, "phase"), "work")
        self.assertEqual(state.first_word(content, "mode"), "council-implement")
        self.assertEqual(state.first_value(content, "absent"), "")
        self.assertTrue(state.is_build_run(content))
        self.assertTrue(state.planned(content))
        self.assertFalse(state.planned("plan-schema:\n"))

    def test_values_of_a_crlf_file_carry_no_carriage_return(self) -> None:
        content = "mode: council-review\r\nstatus: in-progress\r\n## Notes\r\nclosed: never\r\n"
        self.assertEqual(state.values(content, "status"), ["in-progress"])
        self.assertEqual(state.values(content, "closed"), ["never"])

    def test_decisions_are_unquoted(self) -> None:
        self.assertEqual(state.decisions(STATE),
                         ['2026-01-02 10:00: "go "full" C:\\temp"', "2026-01-02 11:00: raw words"])
        self.assertEqual(state.unquote('t: "a\\nb"'), 't: "a\\nb"')            # only \" and \\ are the helper's

    def test_text_and_in_progress(self) -> None:
        home = self.tmp / ".council"
        for name, status in (("2026-01-01-000000-a", "in-progress"), ("2026-01-02-000000-b", "complete"),
                             ("2026-01-03-000000-c", "in-progress (resumed)")):
            self.write(".council/runs/{}/session-state.md".format(name),
                       "status: {}\ncode-root: /p\nsession: s-{}\n".format(status, name[-1]))
        (home / "runs" / "empty").mkdir()
        self.assertEqual(state.text(home / "runs" / "2026-01-02-000000-b"),
                         "status: complete\ncode-root: /p\nsession: s-b\n")
        self.assertEqual(state.text(home / "runs" / "empty"), "")
        self.assertEqual(state.text(home / "runs" / "empty", read=lambda path: "x: " + path.name),
                         "x: session-state.md")
        self.assertEqual(state.in_progress(home), [(home / "runs" / "2026-01-03-000000-c", "/p", "s-c"),
                                                   (home / "runs" / "2026-01-01-000000-a", "/p", "s-a")])
        self.assertEqual(state.in_progress(self.tmp / "nowhere"), [])


if __name__ == "__main__":
    unittest.main()
