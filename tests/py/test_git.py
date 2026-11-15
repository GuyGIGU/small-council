"""council.git.run: git's exit code and stdout, the input it is given, names as they are, and 127 without git."""
from __future__ import annotations

import os
import shutil
import unittest
from unittest import mock

import support

from council import git


@unittest.skipIf(shutil.which("git") is None, "git is not on PATH")
class RunTest(support.Scratch):
    def setUp(self) -> None:
        super().setUp()
        self.assertEqual(git.run(self.tmp, "init", "-q")[0], 0)
        self.write("café.txt", "x\n")
        git.run(self.tmp, "add", ".")

    def test_the_code_and_the_bytes_with_stderr_dropped(self) -> None:
        self.assertEqual(git.run(self.tmp, "rev-parse", "--is-inside-work-tree"), (0, b"true\n"))
        code, out = git.run(self.tmp, "cat-file", "-e", "nothing")
        self.assertNotEqual(code, 0)
        self.assertEqual(out, b"")

    def test_names_turns_quoting_off(self) -> None:
        self.assertEqual(git.run(self.tmp, "-c", "core.quotePath=true", "ls-files")[1], b'"caf\\303\\251.txt"\n')
        self.assertEqual(git.run(self.tmp, "ls-files", names=True)[1], "café.txt\n".encode())

    def test_given_is_the_input(self) -> None:
        blob = git.run(self.tmp, "hash-object", "--stdin", given=b"x\n")[1]
        self.assertEqual(blob, git.run(self.tmp, "hash-object", "café.txt")[1])
        self.assertEqual(git.run(self.tmp, "hash-object", "--stdin")[1],
                         b"e69de29bb2d1d6434b8b29ae775ad8c2e48c5391\n")        # no input: the empty blob


class NoGitTest(unittest.TestCase):
    def test_git_that_cannot_start_is_127(self) -> None:
        with mock.patch.dict(os.environ, {"PATH": ""}):
            self.assertEqual(git.run(".", "status"), (127, b""))


if __name__ == "__main__":
    unittest.main()
