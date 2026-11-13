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

    def test_field_reads_the_header_only(self) -> None:
        """The helper's state_field: a `mode:` line below a heading is a note, never the field."""
        content = STATE.lstrip("\ufeff")
        self.assertEqual(state.field(content, "phase"), "work")           # the first wins, its comment dropped
        self.assertEqual(state.field(content, "closed"), "")             # it is only below the heading
        self.assertEqual(state.field(content, "absent"), "")
        self.assertEqual(state.field(content, "mode"), "")               # " mode :" does not start the line
        below = "status: in-progress\n## Decisions so far\nmode: council-implement\n"
        self.assertEqual(state.field(below, "mode"), "")
        self.assertEqual(state.field("mode:   council-review  # why\r\n## Notes\r\n", "mode"), "council-review")
        self.assertEqual(state.field("mode:\nmode: council-review\n", "mode"), "")   # the first line wins, empty too

    def test_build_and_plan_marks(self) -> None:
        content = STATE.lstrip("\ufeff")
        self.assertFalse(state.is_build_run(content))                    # its `mode: council-implement` is below a heading
        self.assertTrue(state.is_build_run("mode: council-implement\nstatus: in-progress\n"))
        self.assertTrue(state.is_build_run("mode: council-implement  # build\r\n## Notes\r\n"))
        self.assertFalse(state.is_build_run("status: in-progress\n## Notes\nmode: council-implement\n"))
        self.assertFalse(state.is_build_run("mode: council-implementation\n"))
        self.assertTrue(state.planned(content))
        self.assertFalse(state.planned("plan-schema:\n"))
        self.assertFalse(state.planned("status: in-progress\n## Notes\nplan-schema: 1\n"))   # a note, not the header

    def test_a_byte_order_mark_on_line_one_is_not_part_of_its_key(self) -> None:
        """The helper's state_field drops the BOM from line 1, so a key there reads (repair.py's own read keeps it)."""
        self.assertTrue(state.planned("﻿plan-schema: 1\nstatus: in-progress\n"))
        self.assertTrue(state.is_build_run("﻿mode: council-implement\nstatus: in-progress\n"))
        self.assertEqual(state.field("﻿mode: council-review\r\n", "mode"), "council-review")
        self.assertEqual(state.header("﻿status: in-progress\nmode: x\n", exact_keys=True)["status"], "in-progress")

    def test_a_crlf_file_carries_no_carriage_return(self) -> None:
        content = "mode: council-review\r\nstatus: in-progress\r\n## Notes\r\nclosed: never\r\n"
        self.assertEqual(state.field(content, "status"), "in-progress")
        self.assertEqual(state.field(content, "closed"), "")

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
