"""council gate, gates and changed in Python (S6): the pieces that read a gate's config, command and output, the
lock, the time limit, and the stop of a whole process tree."""
from __future__ import annotations

import os
import shutil
import subprocess
import time
import unittest
from pathlib import Path
from unittest import mock

import support

from council.commands import changed, cli, gate, gate_exec, gate_list, gate_lock, gate_output, gate_run, shell
from council.records import events, gate_notes, gate_table, locks, state_write, verdicts

HEAD = ("| Gate | Command | Run at | Mandatory | Checked | Probe | Side effects | Needs |\n"
        "|---|---|---|---|---|---|---|---|\n")
HELPER = Path(__file__).resolve().parents[2] / "bin" / "council"


class ConfigGatesTest(support.Scratch):
    def config(self, body: str) -> str:
        self.write(".council/council.config.md",
                   "# Council config\n\n## Gates\n" + body + "\n## Hard rules\n| x | y |\n")
        return str(self.tmp / ".council")

    def test_rows_read_by_their_header(self) -> None:
        home = self.config(HEAD + "| tests | `pytest -q` | Grounding, verify | yes | ✓ 2026 | `true` | none | - |\n"
                                  "| lint | `a \\| b` | manual | maybe | later | `true` | writes the tree | a GPU |\n"
                                  "| empty |  |  | no | ✗ no GPU | `true` |  | - |\n")
        rows = gate_table.gates(home)
        self.assertEqual([(g.name, g.command, g.stages, g.must, g.ran) for g in rows],
                         [("tests", "pytest -q", "gv", "yes", "ok"), ("lint", "a | b", "m", "?", "?"),
                          ("empty", "-", "-", "no", "not")])
        self.assertEqual((rows[1].side, rows[1].needs, rows[2].side, rows[0].has_side),
                         ("writes the tree", "a GPU", "-", True))

    def test_an_older_table_and_a_list(self) -> None:
        home = self.config("| Gate | Command | Run at | Mandatory |\n|---|---|---|---|\n"
                           "| t | `true` | verify | yes |\n")
        row = gate_table.gates(home)[0]
        self.assertEqual((row.has_side, row.side, row.cells, row.header_cells), (False, "-", 6, 6))
        home = self.config("- `make test` runs the tests\n")
        self.assertEqual((gate_table.gates(home), gate_table.gates_listed(home)), ([], True))
        home = self.config("- run `council gate --all`\n")
        self.assertFalse(gate_table.gates_listed(home))

    def test_bash_and_python_read_one_table_alike(self) -> None:
        """Until run close is ported, bin/council's config_gates reads the same table (S8b): the two must agree,
        cell for cell. The notes are Python's alone since doctor moved (S8); each row's are pinned as the helper's
        gate_shape, gate_backslash and gate_winswitch gave them."""
        bash = shutil.which("bash")
        if bash is None:
            self.skipTest("no bash")
        home = self.config(
            HEAD + "| tests | `pytest -q \\| tee x` | Grounding, Verify | yes | ✓ 2026-09-15 | `true` | none | - |\n"
            "| lint | `ruff . ; echo ok` | verification | **Yes** | ✔ | `true` | writes the tree, network | - |\n"
            "| win | `msbuild /p:x=y tools\\run.ps1` | manual | not mandatory | ✗ no GPU | `true` |  | an API key |\n"
            "| cap | `o=$(pytest); case $o in *ok*) exit 0;; esac` | both | always | later | `true` | deploys | - |\n"
            "| empty |  |  | no | ok | `true` | none | - |\n"
            "| typo | `true` | grounding, verfy | n | broken | `true` | none | - |\n"
            "| shifted | `a | b` | grounding | yes | ok | `true` | none | - |\n"
            "| é ü | `echo ü` | – | non-blocking | ✅ | `true` | none | — |\n")
        cfg = (Path(home) / "council.config.md").as_posix()
        script = '. "$1"; config_gates "$2"'
        rows = subprocess.run(shell.argv_for([bash, "-c", script, "council", HELPER.as_posix(), cfg]),
                              stdout=subprocess.PIPE, check=True).stdout.decode("utf-8")
        python = gate_table.gates(home)
        self.assertEqual(rows.splitlines(), ["\t".join([g.name, g.command, g.at, g.mandatory, str(g.cells), g.checked,
                                                        g.side, g.needs, str(g.header_cells),
                                                        "1" if g.has_side else "0", g.stages, g.must, g.ran])
                                             for g in python])
        pinned = [("tests", ["pipe"], False, False), ("lint", ["masked"], False, False), ("win", [], True, True),
                  ("cap", ["capture"], False, False), ("empty", [], False, False), ("typo", [], False, False),
                  ("shifted", ["pipe"], False, False), ("é ü", [], False, False)]
        self.assertEqual([(g.name, gate_notes.shapes(g.command), gate_notes.backslash(g.command),
                           gate_notes.winswitch(g.command)) for g in python], pinned)
        self.assertEqual(len(python), 8)


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

    def test_an_excerpt_line_ends_as_awk_printed_it(self) -> None:
        from council.commands import gate_failed
        with mock.patch.object(cli, "say") as said:
            gate_failed.indent(["x: No module named y\r", "z"], "  ")
        kept = "" if os.name == "nt" else "\r"           # Git Bash's awk reads in text mode; elsewhere the CR stays
        self.assertEqual([c.args[0] for c in said.call_args_list], ["  x: No module named y" + kept, "  z"])

    def test_failure_ids(self) -> None:
        out = ("FAILED tests/a.py::t1 - AssertionError: x\n--- FAIL: TestGo (0.01s)\nnot ok 3 - tap name\n"
               "test x::y ... FAILED\nERROR 2026-09-30 10:07:44 cache\n\033[31m✖ node test\033[0m\n"
               "FAILED tests/a.py::t1\n")
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
        self.assertEqual((verdicts.number(path, "exit"), verdicts.number(path, "seconds")), ("0", "70"))
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
        for argv, said in ((["gate", "--all", "x"], "doesn't take 'x'"),
                           (["gate", "--all", "--", "true"], "no command"),
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
        row = gate_table.Gate("t", "a | b", "verify", "yes", 8, "ok", "none", "-", 8, True, "v", "yes", "ok")
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
        self.assertEqual([name for chunk in found for name in chunk], files)
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
        self.write(".council/runs/2026-01-02-030405-council-review/gates.lock/owner",
                   "999999999\n2026-01-01 00:00:00\n")
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
        self.assertTrue(state_write.clear_waiting(run))
        text = (run / "session-state.md").read_text(encoding="utf-8")
        self.assertIn("waiting: \nnext:\nupdated: ", text)
        self.assertTrue(text.startswith("mode:") and text.endswith("## Notes\nnext: kept\n"))
        self.assertIn("run.waiting_changed\trun\toff\tfrom=on", (run / "events.tsv").read_text())

    def test_a_stream_that_takes_no_event_or_a_held_lock_leaves_the_state(self) -> None:
        run = self.run_folder()
        held = "status: in-progress\r\nwaiting: q\r\nevents-schema: 1\r\n"
        self.write(".council/runs/2026-01-02-030405-council-review/session-state.md", held)
        self.write(".council/runs/2026-01-02-030405-council-review/events.tsv", events.HEADER + "\n")
        self.assertFalse(state_write.clear_waiting(run))
        self.assertEqual((run / "session-state.md").read_bytes(), held.encode())
        self.write(".council/runs/2026-01-02-030405-council-review/events.tsv",
                   events.HEADER + "\n1\t1\t2026-01-01T00:00:00Z\trun.opened\trun\tx\t-\n")
        self.write(".council/runs/2026-01-02-030405-council-review/session-state.md.lock/owner", "%d\n" % os.getpid())
        acquire = locks.acquire
        with mock.patch.object(locks, "acquire", lambda lock, tries=200: acquire(lock, 2)):
            self.assertFalse(state_write.clear_waiting(run))
        self.assertEqual((run / "session-state.md").read_bytes(), held.encode())
        (run / "session-state.md.lock" / "owner").unlink()
        (run / "session-state.md.lock").rmdir()
        self.assertTrue(state_write.clear_waiting(run))      # a CRLF file, as awk rewrites it: Git Bash's awk reads
        crlf = b"\n" if os.name == "nt" else b"\r\n"         # in text mode, so every CR goes; elsewhere only the
        self.assertEqual((run / "session-state.md").read_bytes(),     # rewritten line loses its own
                         b"status: in-progress" + crlf + b"waiting: \nevents-schema: 1" + crlf)


if __name__ == "__main__":
    unittest.main()
