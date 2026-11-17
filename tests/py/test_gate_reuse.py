"""#68: a configured gate's verdict names the tree it ran on and its seat (git.files_tree), and `gate --all` takes
a green on the same tree (verdicts.green). #47: or on another tree with nothing changed under its Covers paths
(git.unchanged_under, gate_reuse). These pin the reader, the tree id and the rule."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import support

from council import git
from council.commands import gate_reuse
from council.records import gate_table, verdicts

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


class SpanTest(unittest.TestCase):
    def test_the_time_saved_in_words(self) -> None:
        self.assertEqual([gate_reuse.span(s) for s in (0, 45, 60, 1170, 3600, 3900)],
                         ["0s", "45s", "1m 00s", "19m 30s", "1h 00m", "1h 05m"])


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

    def test_python_bytecode_is_left_out_ignored_or_not(self) -> None:
        self.write("kept.pyc", "committed\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "a committed pyc")
        before = git.files_tree(self.tmp)
        self.write("tests/__pycache__/t.cpython-314.pyc", "x")
        self.write("__pycache__/top.cpython-314.pyc", "x")
        self.write("old.pyc", "x")
        self.write("kept.pyc", "rewritten\n")
        self.assertEqual(git.files_tree(self.tmp), before, "untracked bytecode stays out, a committed one as it was")
        self.write(".gitignore", "__pycache__/\n")
        self.assertRegex(git.files_tree(self.tmp), "^[0-9a-f]{40,64}$", "an ignore rule naming it too is no fault")

    def test_the_council_home_is_left_out_committed_or_not(self) -> None:
        before = git.files_tree(self.tmp)
        self.write(".council/logs/x.md", "a log line\n")
        self.write(".council/council.config.md", "# config, edited\n")
        self.assertEqual(git.files_tree(self.tmp), before)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "council files")
        self.assertEqual(git.files_tree(self.tmp), before)

    def test_a_just_me_council_gives_the_team_tree(self) -> None:
        """council sharing just-me puts /.council/ in .git/info/exclude: the tree is still taken, and is the same."""
        team = git.files_tree(self.tmp)
        self.write(".council/logs/x.md", "a log line\n")
        exclude = self.tmp / ".git" / "info" / "exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open("a", encoding="utf-8") as listed:
            listed.write("/.council/\n")
        self.assertRegex(team, "^[0-9a-f]{40,64}$")
        self.assertEqual(git.files_tree(self.tmp), team)
        self.git("rm", "-r", "-q", "--cached", ".council")
        self.git("commit", "-q", "-m", "the council stays on this machine")
        self.assertEqual(git.files_tree(self.tmp), team)

    def test_the_real_index_is_never_touched(self) -> None:
        self.write("a.txt", "b\n")
        self.write("new.py", "x = 1\n")
        status = self.git("status", "--porcelain")
        git.files_tree(self.tmp)
        self.assertEqual(self.git("status", "--porcelain"), status)

    def test_unchanged_under_reads_only_the_paths_given(self) -> None:
        self.write("app/ui/view.kt", "v\n")
        self.write("app/core/model.kt", "m\n")
        old = git.files_tree(self.tmp)
        self.write("app/core/model.kt", "m, edited\n")
        new = git.files_tree(self.tmp)
        self.assertTrue(git.unchanged_under(self.tmp, old, new, ("app/ui/", "tests/")))
        self.assertFalse(git.unchanged_under(self.tmp, old, new, ("app/",)))
        self.assertFalse(git.unchanged_under(self.tmp, old, new, ("*.kt",)), "a bare * crosses folders, as in git")

    def test_a_file_moved_out_from_under_the_paths_is_a_change(self) -> None:
        self.write("app/ui/view.kt", "v\n")
        old = git.files_tree(self.tmp)
        (self.tmp / "app" / "ui" / "view.kt").rename(self.tmp / "app" / "view.kt")
        self.assertFalse(git.unchanged_under(self.tmp, old, git.files_tree(self.tmp), ("app/ui/",)))

    def test_a_fault_is_never_unchanged(self) -> None:
        now = git.files_tree(self.tmp)
        for old, specs in ((("0" * 40), ("a.txt",)), ("", ("a.txt",)), (now, ())):
            with self.subTest(old=old, specs=specs):
                self.assertFalse(git.unchanged_under(self.tmp, old, now, specs))
        self.assertTrue(git.unchanged_under(self.tmp, now, now, ("a.txt",)))

    def test_a_green_is_taken_on_this_tree_or_under_unchanged_paths_only(self) -> None:
        self.write("app/ui/view.kt", "v\n")
        old = git.files_tree(self.tmp)
        run = self.tmp / ".council" / "runs" / "r"      # the council home is never part of the tree
        line = GREEN.replace("a" * 40, old).replace('"command": "pytest -q"', '"command": "true"')
        self.write(".council/runs/r/gates/ui.json", line)
        row = gate_table.Gate("ui", "true", "verify", "yes", 9, "ok", "none", "-", 9, True, "v", "yes", "ok",
                              ("app/ui/",))
        same = gate_reuse.taken(run, row, str(self.tmp))
        self.assertEqual((same.same, same.seconds) if same else None, (True, 3))
        self.write("a.txt", "edited\n")
        other = gate_reuse.taken(run, row, str(self.tmp))
        self.assertEqual(other.same if other else None, False)
        self.assertIn("not rerun — nothing under app/ui/ changed since its green run (builder-1, tree %s, "
                      % old[:12], gate_reuse.not_rerun(row, other))
        self.assertIsNone(gate_reuse.taken(run, row._replace(covers=()), str(self.tmp)), "no Covers: the whole tree")
        self.write("app/ui/view.kt", "v, edited\n")
        self.assertIsNone(gate_reuse.taken(run, row, str(self.tmp)), "a change under its paths")

    def test_outside_git_there_is_no_tree(self) -> None:
        plain = Path(tempfile.mkdtemp(prefix="council-plain-"))
        self.addCleanup(shutil.rmtree, str(plain), True)
        (plain / "a.txt").write_text("a")
        self.assertEqual(git.files_tree(plain), "")


if __name__ == "__main__":
    unittest.main()
