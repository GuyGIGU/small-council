"""The agent gate's writability check (issue 51): the probe that tries to make a file, and the refusal built on it."""
from __future__ import annotations

import errno
import os
import unittest
from typing import Any
from unittest import mock

import support

from council.commands import gate_writable
from council.records import writable

WORKER = "council-worker"


def failing(code: int) -> Any:
    """os.open as it fails when the system says no (or anything else) to making a file."""
    return mock.patch.object(writable.os, "open", side_effect=OSError(code, os.strerror(code)))


class ProbeTest(support.Scratch):
    def test_a_writable_folder_is_not_blocked_and_the_probe_leaves_nothing(self) -> None:
        self.assertFalse(writable.blocked(str(self.tmp)))
        self.assertEqual(os.listdir(str(self.tmp)), [])

    def test_a_folder_that_is_not_there_is_no_answer(self) -> None:
        self.assertFalse(writable.blocked(str(self.tmp / "missing")))

    def test_a_refusal_by_the_system_is_blocked(self) -> None:
        for code in (errno.EACCES, errno.EPERM, errno.EROFS):
            with failing(code):
                self.assertTrue(writable.blocked(str(self.tmp)), errno.errorcode[code])

    def test_any_other_failure_of_the_probe_lets_the_call_through(self) -> None:
        for code in (errno.ENOSPC, errno.EEXIST, errno.EIO, errno.EINVAL):
            with failing(code):
                self.assertFalse(writable.blocked(str(self.tmp)), errno.errorcode[code])

    def test_a_probe_file_that_will_not_go_is_still_a_writable_folder(self) -> None:
        with mock.patch.object(writable.os, "unlink", side_effect=PermissionError(errno.EACCES, "no")):
            self.assertFalse(writable.blocked(str(self.tmp)))


class RefusalTest(support.Scratch):
    def setUp(self) -> None:
        super().setUp()
        self.run = self.run_folder()
        self.home = str(self.tmp / ".council").replace("\\", "/")
        (self.run / "session-state.md").write_text("mode: council-review\nstatus: in-progress\n", encoding="utf-8")

    def test_no_refusal_while_everything_is_writable(self) -> None:
        self.assertIsNone(gate_writable.refusal(WORKER, self.home, self.run.name))

    def test_only_a_small_council_agent_is_judged(self) -> None:
        with failing(errno.EACCES):
            self.assertIsNone(gate_writable.refusal(None, self.home, self.run.name))

    def test_the_refusal_names_the_folder_and_the_next_step(self) -> None:
        with failing(errno.EACCES):
            why = gate_writable.refusal(WORKER, self.home, "")
        self.assertTrue(why and why.startswith("Small Council: "), why)
        self.assertIn(self.home, why)
        self.assertIn("main checkout", why)
        self.assertIn("permissions", why)

    def test_a_run_folder_the_dispatch_names_is_tried_too(self) -> None:
        real = writable.blocked
        folders = []

        def only_the_run(folder: str) -> bool:
            folders.append(folder)
            return folder.endswith(self.run.name) and real(folder)

        with mock.patch.object(gate_writable.writable, "blocked", side_effect=only_the_run):
            self.assertIsNone(gate_writable.refusal(WORKER, self.home, self.run.name))
        self.assertEqual(folders, [self.home, self.home + "/runs/" + self.run.name])

    def test_a_blocked_run_folder_is_named_as_the_run_folder(self) -> None:
        with mock.patch.object(gate_writable.writable, "blocked", side_effect=lambda folder: "/runs/" in folder):
            why = gate_writable.refusal(WORKER, self.home, self.run.name)
        self.assertIn("the run folder " + self.home + "/runs/" + self.run.name, why)

    def test_a_run_name_that_is_not_a_run_is_never_tried(self) -> None:
        tried = []
        with mock.patch.object(gate_writable.writable, "blocked", side_effect=tried.append):
            for named in ("", ".", "..", "../x", "a/b", "no-such-run"):
                gate_writable.refusal(WORKER, self.home, named)
        self.assertEqual(set(tried), {self.home})


if __name__ == "__main__":
    unittest.main()
