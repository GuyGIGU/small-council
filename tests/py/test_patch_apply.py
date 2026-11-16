"""The one way a saved round's patch comes off or goes on a folder's files (patch_apply.undo and redo), the round
council patch apply|revert picks, and the words of git apply's refusals read back as the files they name."""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

import support

from council.commands import cli, patch, patch_apply
from council.records import patches


def git(folder: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(folder)] + list(args), check=True, capture_output=True).stdout


def text(path: Path) -> bytes:
    """A file's bytes, line ends as LF: git apply writes a file as a checkout would, CRLF under core.autocrlf."""
    return path.read_bytes().replace(b"\r\n", b"\n")


class UndoTest(support.Scratch):
    """A round's diff, taken in a repository, comes off and goes back on a copy of its files outside any repo."""

    def setUp(self) -> None:
        super().setUp()
        repo = self.tmp / "repo"
        repo.mkdir()
        git(repo, "init", "-q")
        self.write("repo/src/a.sh", "echo old\n")
        git(repo, "add", "-A")
        git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "a")
        self.write("repo/src/a.sh", "echo new\n")
        self.write("repo/tests/test_a.sh", "test\n")
        git(repo, "add", "-A")
        self.patch = self.write("T1-1.patch", git(repo, "diff", "--binary", "--cached", "HEAD"), binary=True)
        self.copy = self.tmp / "copy"
        self.write("copy/src/a.sh", "echo new\n")
        self.write("copy/tests/test_a.sh", "test\n")

    def test_a_round_comes_off_and_goes_back_on_outside_any_repository(self) -> None:
        self.assertEqual(patch_apply.undo(self.copy, self.patch), [])
        self.assertEqual(text(self.copy / "src" / "a.sh"), b"echo old\n")
        self.assertFalse((self.copy / "tests" / "test_a.sh").exists())
        self.assertEqual(patch_apply.redo(self.copy, self.patch), [])
        self.assertEqual(text(self.copy / "src" / "a.sh"), b"echo new\n")

    def test_the_paths_kept_are_left_as_they_are(self) -> None:
        self.assertEqual(patch_apply.undo(self.copy, self.patch, ("tests/test_a.sh",)), [])
        self.assertEqual(text(self.copy / "src" / "a.sh"), b"echo old\n")
        self.assertEqual(text(self.copy / "tests" / "test_a.sh"), b"test\n")

    def test_a_patch_that_will_not_go_on_changes_nothing_and_names_its_files(self) -> None:
        self.write("copy/src/a.sh", "echo changed since\n")
        self.assertEqual(patch_apply.undo(self.copy, self.patch), ["src/a.sh"])
        self.assertEqual(text(self.copy / "tests" / "test_a.sh"), b"test\n")    # all or nothing


class NamedTest(unittest.TestCase):
    def test_each_file_once_in_order_else_git_own_first_line(self) -> None:
        said = ("error: patch failed: src/a.py:3\nerror: src/a.py: patch does not apply\n"
                "error: tests/t.py: already exists in working directory")
        self.assertEqual(patch_apply.files_named(said), ["src/a.py", "tests/t.py"])
        self.assertEqual(patch_apply.files_named("error: corrupt patch at line 4\nmore"),
                         ["error: corrupt patch at line 4"])


class RoundTest(support.Scratch):
    """--round names a saved round; without it, the task's last."""

    def setUp(self) -> None:
        super().setUp()
        self.run = self.run_folder("2026-01-02-030405-implement")
        for number, seq in ((1, 1), (2, 3)):
            patches.write(self.run, patches.Round(3, number, seq, "2026-01-02T03:04:0%dZ" % seq, "a", "b", ["x"], 1,
                                                  0, {}, [], [], "skipped"), b"")

    def test_the_last_round_unless_one_is_named(self) -> None:
        self.assertEqual(patch_apply.round_of(self.run, 3, "", "apply").round, 2)
        self.assertEqual(patch_apply.round_of(self.run, 3, "1", "revert").round, 1)

    def test_a_round_or_a_task_with_none_is_refused_naming_the_rounds_there_are(self) -> None:
        with self.assertRaisesRegex(cli.Refusal, r"task 3 has no round '5' — its saved rounds are 1, 2"):
            patch_apply.round_of(self.run, 3, "5", "apply")
        with self.assertRaisesRegex(cli.Refusal, r"task 4 has no saved rounds — council patch save 4"):
            patch_apply.round_of(self.run, 4, "", "revert")

    def test_save_and_show_take_no_round(self) -> None:
        args = cli.Args(["patch", "save", "3"], ["round"], {"round": "1"}, {}, [])
        with self.assertRaisesRegex(cli.Refusal, "patch save doesn't take --round"):
            patch.main(args, ["save", "3"])


if __name__ == "__main__":
    unittest.main()
