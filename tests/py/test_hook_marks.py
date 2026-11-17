"""The marks a hook leaves for its session (issue 69), and what `council doctor hooks` makes of them."""
from __future__ import annotations

import os
import time
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  (src/ on the path)

from council.commands import cli, doctor_hooks
from council.records import hook_marks


class MarksTest(support.Scratch):
    def setUp(self) -> None:
        super().setUp()
        where = {"XDG_CACHE_HOME": str(self.tmp / "xdg"), "HOME": str(self.tmp / "home")}
        self.env = mock.patch.dict(os.environ, where)
        self.env.start()
        self.addCleanup(self.env.stop)

    def names(self, folder: Path) -> list:
        return sorted(p.name for p in folder.iterdir() if p.name != hook_marks.PRUNED) if folder.is_dir() else []

    def test_a_mark_goes_to_both_folders_with_the_bare_one_beside_it(self) -> None:
        hook_marks.put("s1", "agent-gate")
        for folder in (self.tmp / "xdg" / "small-council" / "sessions",
                       self.tmp / "home" / ".cache" / "small-council" / "sessions"):
            self.assertEqual(self.names(folder), ["s1", "s1.agent-gate"])

    def test_one_folder_when_the_cache_is_home_dot_cache(self) -> None:
        with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": str(self.tmp / "home") + "/.cache"}):
            self.assertEqual(len(hook_marks.folders()), 1)

    def test_what_is_seen_comes_back_in_the_order_doctor_says_it(self) -> None:
        for hook in ("seat-gate", "session-start", "bash-gate"):
            hook_marks.put("s2", hook)
        self.assertEqual(hook_marks.seen("s2"), ["session-start", "bash-gate", "seat-gate"])
        self.assertEqual(hook_marks.seen("other"), [])

    def test_an_id_that_cannot_be_a_file_name_leaves_and_finds_nothing(self) -> None:
        for bad in ("", "../x", ".hidden", "a/b", "a b"):
            hook_marks.put(bad, "turn-end")
            self.assertEqual(hook_marks.seen(bad), [])
        self.assertFalse((self.tmp / "xdg").exists())

    def test_marks_over_30_days_old_are_cleared_at_most_once_a_day(self) -> None:
        folder = self.tmp / "xdg" / "small-council" / "sessions"
        folder.mkdir(parents=True)
        old = time.time() - 40 * 86400
        for name in ("gone", "gone.turn-end"):
            (folder / name).touch()
            os.utime(folder / name, (old, old))
        hook_marks.put("s7", "turn-end")
        self.assertEqual(self.names(folder), ["s7", "s7.turn-end"])
        (folder / "late").touch()
        os.utime(folder / "late", (old, old))
        hook_marks.put("s8", "turn-end")                  # trimmed less than a day ago: no walk
        self.assertIn("late", self.names(folder))
        hook_marks.trim(folder, now=time.time() + 2 * 86400)
        self.assertNotIn("late", self.names(folder))

    def test_a_folder_that_cannot_be_made_is_skipped_silently(self) -> None:
        (self.tmp / "xdg").write_text("a file where a folder should go")
        hook_marks.put("s3", "turn-end")                  # no exception; the other folder still takes it
        self.assertEqual(hook_marks.seen("s3"), ["turn-end"])


class ReportTest(MarksTest):
    def run_doctor(self, session: str) -> list:
        said: list = []
        doc = mock.Mock()
        with mock.patch.object(cli, "say", said.append):
            doctor_hooks.report(doc, session)
        return said + [c.args[1] for c in doc.warn.call_args_list]

    def test_each_hook_is_live_or_not_seen_and_the_count_follows(self) -> None:
        hook_marks.put("s4", "session-start")
        hook_marks.put("s4", "bash-gate")
        said = self.run_doctor("s4")
        self.assertEqual(said[0], "hook SessionStart  live")
        self.assertEqual(said[1], "hook Stop          not seen in this session (runs when a turn ends)")
        self.assertEqual(said[5], "hooks: 2 of 5 live — the rest show as they fire (council doctor lists them)")
        self.assertEqual(len(said), 6)                    # no finding: both hooks that must have run did

    def test_all_five_live_is_said_plainly(self) -> None:
        for hook, _, _ in hook_marks.HOOKS:
            hook_marks.put("s5", hook)
        self.assertEqual(self.run_doctor("s5")[5], "hooks: 5 of 5 live")

    def test_a_hook_that_must_have_run_by_now_is_a_finding_naming_the_fix(self) -> None:
        said = self.run_doctor("s6")
        self.assertEqual(said[5].split(" — ")[0], "hooks: 0 of 5 live")
        self.assertEqual(said[6:], ["restart the session", "restart the session"])

    def test_with_no_session_it_says_it_cannot_know(self) -> None:
        self.assertEqual(self.run_doctor("")[0], doctor_hooks.NO_SESSION)


if __name__ == "__main__":
    unittest.main()
