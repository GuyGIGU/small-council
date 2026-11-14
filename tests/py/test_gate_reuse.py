"""#68: a configured gate's verdict names the tree it ran on and its seat (git.files_tree), and `gate --all` takes
a green on the same tree (verdicts.green). These pin the reader and the tree id."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import support

from council import git
from council.records import verdicts

GREEN = ('{"gate": "tests", "command": "pytest -q", "exit": 0, "seconds": 3, "when": "2026-11-14 10:00:00", '
         '"limit": 120, "tree": "%s", "seat": "builder-1"}\n' % ("a" * 40))


class GreenTest(support.Scratch):
    def verdict(self, line: str) -> str:
        return str(self.write("gates/tests.json", line))

    def test_a_green_on_record_is_its_tree_seat_and_time(self) -> None:
        self.assertEqual(verdicts.green(self.verdict(GREEN), "pytest -q"),
                         verdicts.Green("a" * 40, "builder-1", "2026-11-14 10:00:00"))

    def test_what_never_counts_as_green(self) -> None:
        cases = {
            "a red": GREEN.replace('"exit": 0', '"exit": 1'),
            "a time-out": GREEN.replace('"exit": 0', '"exit": 124').replace("}\n", ', "timed_out": true}\n'),
            "a time-out recorded green": GREEN.replace("}\n", ', "timed_out": true}\n'),
            "a pass with nothing run": GREEN.replace("}\n", ', "note": "exit 0, but its output says no test ran"}\n'),
            "a record marked invalid": GREEN.replace("}\n", ', "invalid": "wrong tree"}\n'),
            "no tree (outside git, or the files changed while it ran)": GREEN.replace("a" * 40, ""),
            "no seat (a verdict from before #68)": GREEN.replace(', "seat": "builder-1"', ""),
            "no tree field at all": GREEN.replace(', "tree": "%s"' % ("a" * 40), ""),
        }
        for why, line in cases.items():
            with self.subTest(why):
                self.assertIsNone(verdicts.green(self.verdict(line), "pytest -q"))

    def test_another_command_under_the_name_is_no_green(self) -> None:
        self.assertIsNone(verdicts.green(self.verdict(GREEN), "pytest -q -k one"))

    def test_the_command_is_compared_as_the_verdict_writes_it(self) -> None:
        line = GREEN.replace('"command": "pytest -q"', '"command": "echo \\"a b\\""')
        self.assertIsNotNone(verdicts.green(self.verdict(line), 'echo \\"a b\\"'))

    def test_a_command_that_spells_a_tree_cannot_forge_one(self) -> None:
        line = GREEN.replace('"command": "pytest -q"', '"command": "echo \\"tree\\": \\"%s\\""' % ("b" * 40))
        found = verdicts.green(self.verdict(line), 'echo \\"tree\\": \\"%s\\"' % ("b" * 40))
        self.assertEqual(found.tree if found else "", "a" * 40)

    def test_no_file_is_no_green(self) -> None:
        self.assertIsNone(verdicts.green(str(self.tmp / "gates" / "none.json"), "pytest -q"))


@unittest.skipUnless(shutil.which("git"), "git is not on PATH")
class FilesTreeTest(support.Scratch):
    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-c", "core.autocrlf=false", "-C", str(self.tmp)] + list(args), check=True,
                              capture_output=True, text=True).stdout.strip()

    def setUp(self) -> None:
        super().setUp()
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.write("a.txt", "a\n")
        self.write(".council/council.config.md", "# config\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

    def test_the_same_files_give_the_same_tree_whatever_was_committed(self) -> None:
        clean = git.files_tree(self.tmp)
        self.assertRegex(clean, "^[0-9a-f]{40,64}$")
        self.write("a.txt", "b\n")
        edited = git.files_tree(self.tmp)
        self.assertNotEqual(edited, clean, "an unstaged edit changes the tree")
        self.git("add", "a.txt")
        self.assertEqual(git.files_tree(self.tmp), edited, "staging it changes nothing")
        self.git("commit", "-q", "-m", "b")
        self.assertEqual(git.files_tree(self.tmp), edited, "nor does committing it")
        self.write("a.txt", "a\n")
        self.assertEqual(git.files_tree(self.tmp), clean, "the first files again: the first tree")

    def test_untracked_files_count_and_ignored_ones_do_not(self) -> None:
        self.write(".gitignore", "build/\n")
        before = git.files_tree(self.tmp)
        self.write("build/out.bin", "x")
        self.assertEqual(git.files_tree(self.tmp), before)
        self.write("new.py", "x = 1\n")
        self.assertNotEqual(git.files_tree(self.tmp), before)

    def test_the_council_home_is_left_out_committed_or_not(self) -> None:
        before = git.files_tree(self.tmp)
        self.write(".council/logs/x.md", "a log line\n")
        self.write(".council/council.config.md", "# config, edited\n")
        self.assertEqual(git.files_tree(self.tmp), before)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "council files")
        self.assertEqual(git.files_tree(self.tmp), before)

    def test_the_real_index_is_never_touched(self) -> None:
        self.write("a.txt", "b\n")
        self.write("new.py", "x = 1\n")
        status = self.git("status", "--porcelain")
        git.files_tree(self.tmp)
        self.assertEqual(self.git("status", "--porcelain"), status)

    def test_outside_git_there_is_no_tree(self) -> None:
        plain = Path(tempfile.mkdtemp(prefix="council-plain-"))
        self.addCleanup(shutil.rmtree, str(plain), True)
        (plain / "a.txt").write_text("a")
        self.assertEqual(git.files_tree(plain), "")


if __name__ == "__main__":
    unittest.main()
