"""The pieces of `council check` and `council index` in Python (S7): what a proof's command reached, a proof's
status, the just-me hygiene rules, the definitions a diff names, and an event whose failure is only said."""
from __future__ import annotations

import os
import shutil
import subprocess
import time
import unittest
from unittest import mock

import support

from council.commands import check, check_proofs, event_note, hygiene, index, index_symbols, proof_reach
from council.records import events


def git(folder: object, *args: str) -> None:
    subprocess.run(["git", "-C", str(folder)] + list(args), check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)


@unittest.skipIf(shutil.which("git") is None, "git is not on PATH")
class TestPathTest(support.Scratch):
    def setUp(self) -> None:
        super().setUp()
        git(self.tmp, "init", "-q")
        self.write("tests/test_a.py", "x\n")
        self.write("src/app.py", "x\n")
        self.write("evals/run_x.py", "x\n")
        git(self.tmp, "add", ".")

    def test_the_first_test_the_project_keeps(self) -> None:
        top = str(self.tmp)
        self.assertEqual(proof_reach.test_path(top, "python -m pytest tests/test_a.py -q"), "tests/test_a.py")
        self.assertEqual(proof_reach.test_path(top, "(cd src && python ../tests/test_a.py)"), "tests/test_a.py")
        self.assertEqual(proof_reach.test_path(top, "python evals/run_x.py --block y"), "evals/run_x.py")
        self.assertEqual(proof_reach.test_path(top, "python src/app.py"), "")          # not a test by name or folder
        self.assertEqual(proof_reach.test_path(top, "pytest tests/missing_test.py"), "")
        self.assertEqual(proof_reach.test_path(top, "cd .. && pytest tests/test_a.py"), "")  # left the project

    def test_an_untracked_test_counts_unless_ignored(self) -> None:
        self.write("tests/test_new.py", "x\n")
        self.write(".gitignore", "tests/test_skip.py\n")
        self.write("tests/test_skip.py", "x\n")
        self.assertEqual(proof_reach.test_path(str(self.tmp), "pytest tests/test_new.py"), "tests/test_new.py")
        self.assertEqual(proof_reach.test_path(str(self.tmp), "pytest tests/test_skip.py"), "")


class RunFolderTest(unittest.TestCase):
    def test_only_run_folder_scripts(self) -> None:
        self.assertTrue(proof_reach.run_folder_only("python .council/runs/r/check.py"))
        self.assertTrue(proof_reach.run_folder_only("cd .council/runs/r && bash ./t.sh > out 2>&1 && grep ok out"))
        self.assertFalse(proof_reach.run_folder_only("python .council/runs/r/check.py && pytest"))
        self.assertFalse(proof_reach.run_folder_only("pytest tests"))
        self.assertFalse(proof_reach.run_folder_only(""))


class ProofTest(support.Scratch):
    def gate(self, name: str, json: str, output: str | None = "5 passed\n") -> None:
        self.write("run/gates/%s.json" % name, json + "\n")
        if output is not None:
            self.write("run/gates/%s.txt" % name, output)

    def test_the_status_chain(self) -> None:
        gates = self.tmp / "run" / "gates"
        self.gate("before-1", '{"gate": "before-1", "command": "pytest", "exit": 1}')
        self.gate("after-1", '{"gate": "after-1", "command": "pytest", "exit": 0}')
        self.assertEqual(check_proofs.status(gates / "before-1.json", gates / "after-1.json", "1"), "ok")
        self.gate("before-2", '{"command": "pytest", "exit": 0}')
        self.gate("after-2", '{"command": "pytest", "exit": 0}')
        self.assertEqual(check_proofs.status(gates / "before-2.json", gates / "after-2.json", "2"), "BEFORE-PASSED")
        self.gate("before-3", '{"command": "pytest", "exit": 0, "proof": "preserve"}', "collected 0 items\n")
        self.gate("after-3", '{"command": "pytest", "exit": 0, "proof": "preserve"}')
        self.assertEqual(check_proofs.status(gates / "before-3.json", gates / "after-3.json", "3"), "NOTHING-RAN")
        self.gate("after-4", '{"command": "pytest -x", "exit": 0}')
        self.assertEqual(check_proofs.status(gates / "before-1.json", gates / "after-4.json", "4"),
                         "DIFFERENT-COMMAND")

    def test_a_red_that_proves_nothing(self) -> None:
        gates = self.tmp / "run" / "gates"
        self.gate("before-1", '{"exit": 1, "invalid": "flaky"}')
        self.gate("before-2", '{"exit": 1, "seconds": 9, "timed_out": true}')
        self.gate("before-3", '{"exit": 127}')
        self.gate("before-4", '{"exit": 1}', "/usr/bin/python: No module named pytest\n")
        self.gate("before-5", '{"exit": 1}')
        self.assertEqual([check_proofs.void(gates / ("before-%d.json" % n)) for n in range(1, 6)],
                         ["marked invalid (flaky)", "timed out after 9s",
                          "never ran: a command it calls was not found (exit 127)",
                          "never ran: Python has no module pytest", ""])

    def test_proofs_in_name_order_and_an_after_with_nothing_before(self) -> None:
        self.gate("before-1", '{"command": "pytest", "exit": 1}')
        self.gate("regress-1", '{"command": "pytest", "exit": 1}')            # a task's own re-proof: skipped
        self.gate("regress-2", '{"command": "pytest", "exit": 1}')
        self.gate("after-3", '{"command": "pytest", "exit": 0}')
        with mock.patch("council.commands.cli.say"):
            tally = check_proofs.proofs(self.tmp / "run", str(self.tmp))
        self.assertEqual([(row.who, row.status) for row in tally.rows],
                         [("task 1", "NO-AFTER"), ("review fix 2", "NO-AFTER"), ("task 3", "NO-BEFORE")])
        self.assertEqual(tally.broke, 3)


class HygieneTest(unittest.TestCase):
    def test_the_rules_and_where_they_count(self) -> None:
        self.assertEqual(hygiene.kind(b"src/a.py", b"x = 1  # see .council/runs/x"), "a .council/ path")
        self.assertEqual(hygiene.kind(b"src/a.py", b"# per ruling 2"), "a council ruling")
        self.assertEqual(hygiene.kind(b"src/a.py", b"// fixes F-12"), "a council id (D-, F-, AP-, EC-)")
        self.assertEqual(hygiene.kind(b"src/a.py", b"y = D-1"), "")                  # code: a subtraction
        self.assertEqual(hygiene.kind(b"notes.md", b"as in plan task 4"), "a council task")
        self.assertEqual(hygiene.kind(b"commit abc", b"see verify-3"), "a council verifier file")
        self.assertEqual(hygiene.kind(b"src/a.py", b"print('fine')"), "")

    def test_the_opened_time_as_touch_reads_it(self) -> None:
        self.assertEqual(hygiene.stamp("2026-01-02 03:04:05"),
                         time.mktime(time.strptime("20260102030405", "%Y%m%d%H%M%S")))
        self.assertIsNone(hygiene.stamp("not a time"))


class IndexTest(unittest.TestCase):
    def test_definitions_a_diff_names(self) -> None:
        self.assertEqual(index_symbols.definition("def parse_rows(x):"), "parse_rows")
        self.assertEqual(index_symbols.definition("func (r *Reader) ReadAll() error {"), "ReadAll")
        self.assertEqual(index_symbols.definition("export const loadIt = async (a) => {"), "loadIt")
        self.assertEqual(index_symbols.definition("cmd_check() {"), "cmd_check")
        self.assertEqual(index_symbols.definition("static int count_lines(char *s)"), "count_lines")
        self.assertEqual(index_symbols.definition("    return helper(x);"), "")
        diff = ["@@ -1 +1 @@ def outer():", "+def inner():", "-class Old:", "+print('x')", "+++ b/x.py"]
        self.assertEqual(index_symbols.symbols(diff), ["outer", "inner", "Old"])
        self.assertEqual(len(index_symbols.symbols(["+def name%d():" % n for n in range(20)])), 8)

    def test_paths_left_out_and_hunks(self) -> None:
        self.assertTrue(index_symbols.not_indexed("web/node_modules/x.js"))
        self.assertTrue(index_symbols.no_symbols("README.md"))
        self.assertTrue(index_symbols.is_test_path("pkg/foo_test.go"))
        self.assertFalse(index_symbols.not_indexed("src/app.py"))
        self.assertEqual(index.hunks(["@@ -1,2 +3,0 @@", "@@ -9 +12 @@", "@@ -20 +30,5 @@", "+@@ not one"]),
                         "removed near 3, 12, 30-34")


class SmallTest(support.Scratch):
    def test_a_files_label(self) -> None:
        self.assertEqual([check.label(p) for p in ("run/seats/beck.md", "notes.txt", "a/.md")],
                         ["beck", "notes.txt", ".md"])

    def test_an_event_that_fails_is_said_and_the_result_stands(self) -> None:
        run = self.run_folder()
        with mock.patch.object(events, "append", side_effect=events.EventError("no room")), \
                mock.patch("council.commands.cli.warn") as warn:
            self.assertFalse(event_note.append(run, "collect.finished", "run", "passed", "seats=1", "it went on"))
        self.assertEqual([call.args[0] for call in warn.call_args_list], ["council: no room", "council: it went on"])
        self.assertFalse(os.path.exists(run / "events.tsv"))


if __name__ == "__main__":
    unittest.main()
