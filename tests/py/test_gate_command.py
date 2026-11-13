"""council gate, gates and changed in Python (S6): the pieces that read a gate's config, command and output, the
lock, the time limit, and the stop of a whole process tree."""
from __future__ import annotations

import os
import time
import unittest
from pathlib import Path
from unittest import mock

import support

from council.commands import changed, cli, gate, gate_exec, gate_list, gate_lock, gate_notes, gate_output, \
    gate_run, gate_wait, shell
from council.records import config, events

HEAD = "| Gate | Command | Run at | Mandatory | Checked | Probe | Side effects | Needs |\n|---|---|---|---|---|---|---|---|\n"


class ConfigGatesTest(support.Scratch):
    def config(self, body: str) -> str:
        self.write(".council/council.config.md", "# Council config\n\n## Gates\n" + body + "\n## Hard rules\n| x | y |\n")
        return str(self.tmp / ".council")

    def test_rows_read_by_their_header(self) -> None:
        home = self.config(HEAD + "| tests | `pytest -q` | Grounding, verify | yes | ✓ 2026 | `true` | none | - |\n"
                                  "| lint | `a \\| b` | manual | maybe | later | `true` | writes the tree | a GPU |\n"
                                  "| empty |  |  | no | ✗ no GPU | `true` |  | - |\n")
        rows = config.gates(home)
        self.assertEqual([(g.name, g.command, g.stages, g.must, g.ran) for g in rows],
                         [("tests", "pytest -q", "gv", "yes", "ok"), ("lint", "a | b", "m", "?", "?"),
                          ("empty", "-", "-", "no", "not")])
        self.assertEqual((rows[1].side, rows[1].needs, rows[2].side, rows[0].has_side), ("writes the tree", "a GPU", "-",
                                                                                          True))

    def test_an_older_table_and_a_list(self) -> None:
        home = self.config("| Gate | Command | Run at | Mandatory |\n|---|---|---|---|\n| t | `true` | verify | yes |\n")
        row = config.gates(home)[0]
        self.assertEqual((row.has_side, row.side, row.cells, row.header_cells), (False, "-", 6, 6))
        home = self.config("- `make test` runs the tests\n")
        self.assertEqual((config.gates(home), config.gates_listed(home)), ([], True))
        home = self.config("- run `council gate --all`\n")
        self.assertFalse(config.gates_listed(home))


class NotesTest(unittest.TestCase):
    def test_backslash_and_switch(self) -> None:
        self.assertTrue(gate_notes.backslash(r"tools\run.ps1"))
        self.assertFalse(gate_notes.backslash(r"echo 'a\b'"))
        self.assertTrue(gate_notes.winswitch("msbuild /p:Configuration=Release"))
        self.assertFalse(gate_notes.winswitch("msbuild -p:Configuration=Release"))

    def test_shapes(self) -> None:
        self.assertEqual(gate_notes.shapes("pytest | tee out"), ["pipe"])
        self.assertEqual(gate_notes.shapes("set -o pipefail; pytest | tee out"), [])
        self.assertEqual(gate_notes.shapes("false; echo done"), ["masked"])
        self.assertEqual(gate_notes.shapes("out=$(pytest); case $out in *ok*) exit 0;; esac"), ["capture"])
        self.assertEqual(gate_notes.shapes("pytest -q && ruff check ."), [])
        self.assertEqual(len(gate_notes.notes("a | b; true")), 2)


class OutputTest(unittest.TestCase):
    def test_zero_tests_unless_tests_ran(self) -> None:
        self.assertEqual(gate_output.zero_tests("collected 0 items\n"), "collected 0 items")
        self.assertEqual(gate_output.zero_tests("collected 0 items\nran 3 tests\n"), "")
        self.assertEqual(gate_output.zero_tests("skipped: 0 tests\n"), "")

    def test_failure_ids(self) -> None:
        out = ("FAILED tests/a.py::t1 - AssertionError: x\n--- FAIL: TestGo (0.01s)\nnot ok 3 - tap name\n"
               "test x::y ... FAILED\nERROR 2026-09-30 10:07:44 cache\n\033[31m✖ node test\033[0m\nFAILED tests/a.py::t1\n")
        self.assertEqual(gate_output.failure_ids(out), ["tests/a.py::t1", "TestGo", "tap name", "x::y", "node test"])

    def test_never_ran_and_missing_module(self) -> None:
        self.assertTrue(gate_output.never_ran("Microsoft Windows [Version 10]\r\n(c) x\r\n\r\nC:\\x>"))
        self.assertFalse(gate_output.never_ran("hello\n"))
        self.assertEqual(gate_output.missing_module("changed: 2 file(s)\npython: No module named ruff\n"), "ruff")
        self.assertEqual(gate_output.missing_module("ModuleNotFoundError: No module named 'x'\n"), "")

    def test_test_gate_clip_and_tail(self) -> None:
        self.assertTrue(gate_output.is_test_gate("Unit", "go test ./..."))
        self.assertFalse(gate_output.is_test_gate("lint", "ruff src tests"))
        self.assertEqual(gate_output.clip("aaa bbb ccc", 9), "aaa bbb …")
        self.assertEqual(gate_output.tail("a\nb\nc\n\n", 2), ["c"])


class RunHelpersTest(support.Scratch):
    def test_qname_json_and_windows_switch(self) -> None:
        self.assertEqual((gate_run.qname("unit tests"), gate_run.qname("lint")), ('"unit tests"', "lint"))
        self.assertEqual(gate_run.json_esc('a\\b "c"\td'), 'a\\\\b \\"c\\" d')
        self.assertEqual(gate_run.windows_command('cmd /c "x" && CMD.EXE  /K y'), 'cmd //c "x" && CMD.EXE  //K y')
        self.assertEqual(gate_run.windows_command("echo /c/x"), "echo /c/x")

    def test_recorded_and_limit(self) -> None:
        run = self.run_folder()
        self.write(".council/runs/2026-01-02-030405-council-review/gates/baseline/t.json",
                   '{"gate": "t", "exit": 0, "seconds": 70}\n')
        path = str(run / "gates" / "baseline" / "t.json")
        self.assertEqual((gate_run.recorded(path, "exit"), gate_run.recorded(path, "seconds")), ("0", "70"))
        call = gate_run.Call(run.as_posix(), str(self.tmp / ".council"), str(self.tmp), False, None, "", False)
        self.assertEqual(gate_run.limit(call, "t"), (210, "3× its 70s green baseline"))
        self.assertEqual(gate_run.limit(call, "u"), (1800, "the default, with no green baseline to go by"))
        self.assertEqual(gate_run.limit(call._replace(given=True), "u")[0], 540)
        self.assertEqual(gate_run.limit(call._replace(timeout=5), "t"), (5, "set by --timeout"))


class QuoteTest(unittest.TestCase):
    def test_words_as_printf_q_writes_them(self) -> None:
        with mock.patch.dict(os.environ, {"LC_ALL": "C.UTF-8"}):
            self.assertEqual(shell.quote(["printf", "%s\\n", "a b", "c'd", "~x", "x=~", "#a", "a#", "", "é"]),
                             "printf %s\\\\n a\\ b c\\'d \\~x x=\\~ \\#a a# '' é")
            self.assertEqual(shell.quote(["a\tb", "\x1b"]), "$'a\\tb' $'\\E'")
        with mock.patch.dict(os.environ, {"LC_ALL": "C"}):
            self.assertEqual(shell.quote(["é"]), "$'\\303\\251'")

    def test_child_env_gives_the_callers_setting_back(self) -> None:
        with mock.patch.dict(os.environ, {"COUNCIL_ARG_CONV_EXCL": "set:--x", "MSYS2_ARG_CONV_EXCL": "*"}):
            self.assertEqual(shell.child_env().get("MSYS2_ARG_CONV_EXCL"), "--x")
        with mock.patch.dict(os.environ, {"COUNCIL_ARG_CONV_EXCL": "", "MSYS2_ARG_CONV_EXCL": "*"}):
            self.assertNotIn("MSYS2_ARG_CONV_EXCL", shell.child_env({"COUNCIL_BASE": "b"}))
        self.assertEqual((shell.status(-15), shell.status(3)), (143, 3))


class GateTest(unittest.TestCase):
    def test_safe_to_run_unasked(self) -> None:
        self.assertTrue(gate.safe("none", "-", True))
        self.assertTrue(gate.safe("Writes the tree, network", "-", True))
        self.assertFalse(gate.safe("deploys", "-", True))
        self.assertFalse(gate.safe("none", "an API key", True))
        self.assertFalse(gate.safe("none", "-", False))
        self.assertFalse(gate.safe("-", "-", True))

    def test_the_command_after_the_dashes(self) -> None:
        self.assertEqual(gate.given(["pytest -q | tee x"]), "pytest -q | tee x")
        self.assertEqual(gate.given(["pytest", "-k", "a b"]), "pytest -k a\\ b")
        self.assertEqual(gate.given([]), "")

    def test_flags_are_checked_before_a_run_is_looked_for(self) -> None:
        for argv, said in ((["gate", "--all", "x"], "doesn't take 'x'"), (["gate", "--all", "--", "true"], "no command"),
                           (["gate", "x", "--at", "verify"], "only with gate --all"),
                           (["gate", "x", "--json"], "doesn't take --json")):
            with self.assertRaises(cli.Refusal) as caught:
                args = cli.parse(argv)
                gate.main(args, args.words[1:])
            self.assertIn(said, str(caught.exception))

    def test_wait_with_seconds_is_told_from_plain_wait(self) -> None:
        self.assertEqual((cli.parse(["--wait"]).value("wait"), cli.parse(["--wait=1"]).value("wait")), ("1", "=1"))
        with self.assertRaises(cli.Refusal):
            cli.parse(["--wait="])

    def test_gates_line(self) -> None:
        row = config.Gate("t", "a | b", "verify", "yes", 8, "ok", "none", "-", 8, True, "v", "yes", "ok")
        self.assertEqual(gate_list.line(row), "t · a | b · run at: verify · mandatory: yes · side effects: none"
                                              " · note: the command " + gate_notes.SHAPES["pipe"])
        self.assertIn("(no command:", gate_list.line(row._replace(command="-")))


class ChangedTest(unittest.TestCase):
    def test_expand(self) -> None:
        self.assertEqual(changed.expand("*.{js,jsx}"), ["*.js", "*.jsx"])
        self.assertEqual(changed.expand("{a,b}/*.{c,d}"), ["a/*.c", "a/*.d", "b/*.c", "b/*.d"])
        self.assertEqual(changed.expand("*.{js}"), ["*.{js}"])
        self.assertEqual(changed.expand("*.{a,{b,c}}"), ["*.{a,{b,c}}"])

    def test_batches_keep_a_command_line_short(self) -> None:
        files = ["f%04d.py" % n for n in range(2000)]
        found = changed.batches(files, 10)
        self.assertEqual(sum(found, []), files)
        self.assertTrue(all(sum(len(f) + 3 for f in chunk) <= changed.LINE_BUDGET - 10 for chunk in found))
        self.assertEqual(changed.batches(["a"], 10), [["a"]])

    def test_options(self) -> None:
        self.assertEqual(changed.options(["--glob", "*.{a,b}", "--each", "--glob=c"]), (["*.a", "*.b", "c"], True))
        with self.assertRaises(cli.Refusal):
            changed.options(["--glob"])


class LockTest(support.Scratch):
    def test_take_refuse_and_release(self) -> None:
        run = self.run_folder().as_posix()
        gate_lock.take(run, False)
        owner = Path(run, "gates.lock", "owner").read_text().split("\n")
        self.assertEqual(owner[0], str(os.getpid()))
        with self.assertRaises(cli.Refusal) as caught:            # this process holds it, and is alive
            gate_lock.HELD.clear()
            gate_lock.take(run, False)
        self.assertIn("checks are already running for this run", str(caught.exception))
        gate_lock.HELD.append(Path(run, "gates.lock"))
        gate_lock.release()
        self.assertFalse(Path(run, "gates.lock").exists())

    def test_a_lock_whose_process_is_gone_is_cleared(self) -> None:
        run = self.run_folder().as_posix()
        self.write(".council/runs/2026-01-02-030405-council-review/gates.lock/owner", "999999999\n2026-01-01 00:00:00\n")
        with mock.patch.object(cli, "warn") as said:
            gate_lock.take(run, False)
        gate_lock.release()
        self.assertIn("cleared a gate lock left by a call that is no longer running (process 999999999",
                      said.call_args[0][0])


class ExecTest(support.Scratch):
    def test_a_hang_is_stopped_with_its_children(self) -> None:
        out = str(self.tmp / "out.txt")
        started = time.time()
        code, timed_out = gate_exec.execute(str(self.tmp), "", "echo up; sleep 30 & sleep 30; echo never", out, 2)
        self.assertEqual((code, timed_out), (gate_exec.TIMED_OUT, True))
        self.assertLess(time.time() - started, 15)
        self.assertEqual(Path(out).read_text().strip(), "up")

    def test_exit_code_output_and_base(self) -> None:
        out = str(self.tmp / "out.txt")
        self.assertEqual(gate_exec.execute(str(self.tmp), "abc", 'echo "[$COUNCIL_BASE]" >&2; exit 3', out, 30),
                         (3, False))
        self.assertEqual(Path(out).read_text().strip(), "[abc]")
        self.assertEqual(gate_exec.execute(str(self.tmp / "nowhere"), "", "true", out, 30)[0], gate_exec.NO_ROOT)


class WaitTest(support.Scratch):
    def test_a_wait_is_cleared_with_its_event(self) -> None:
        run = self.run_folder()
        self.write(".council/runs/2026-01-02-030405-council-review/session-state.md",
                   "﻿mode: council-review\nphase: judge\nstatus: in-progress\nwaiting: which way?\n"
                   "next: size the run and ask for the go-ahead\nupdated: 2026-01-01 00:00\nevents-schema: 1\n\n"
                   "## Notes\nnext: kept\n")
        self.write(".council/runs/2026-01-02-030405-council-review/events.tsv",
                   events.HEADER + "\n1\t1\t2026-01-01T00:00:00Z\trun.opened\trun\tx\t-\n")
        gate_wait.over(run)
        text = (run / "session-state.md").read_text(encoding="utf-8")
        self.assertIn("waiting: \nnext:\nupdated: ", text)
        self.assertTrue(text.startswith("mode:") and text.endswith("## Notes\nnext: kept\n"))
        self.assertIn("run.waiting_changed\trun\toff\tfrom=on", (run / "events.tsv").read_text())

    def test_a_stream_that_takes_no_event_leaves_the_state(self) -> None:
        run = self.run_folder()
        state = "status: in-progress\nwaiting: q\nevents-schema: 1\n"
        self.write(".council/runs/2026-01-02-030405-council-review/session-state.md", state)
        self.write(".council/runs/2026-01-02-030405-council-review/events.tsv", events.HEADER + "\n")
        gate_wait.over(run)
        self.assertEqual((run / "session-state.md").read_text(), state)
        self.assertFalse(gate_wait.ready(run))


if __name__ == "__main__":
    unittest.main()
