"""How a ported command starts (D24): the entry refuses an old Python itself, in syntax an old Python can
parse, and the dispatcher imports only the command it runs."""
from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
import unittest

import support

ENTRY = support.SRC / "council" / "__main__.py"


def started(*words: str) -> list[str]:
    """Run the dispatcher for one command line in a fresh interpreter (in an empty folder); the modules it
    then holds of the commands' package, and tempfile and shutil, which only a writing command needs (glob
    comes with pathlib on 3.13 and later, which every command uses)."""
    script = ("import sys; sys.path.insert(0, sys.argv[1]); from council.commands import dispatch; "
              "dispatch.main(sys.argv[2:]); sys.stdout.flush(); "
              "print('|'.join(sorted(m for m in sys.modules if m.startswith('council.commands') "
              "or m in ('tempfile', 'shutil'))))")
    with tempfile.TemporaryDirectory() as folder:
        done = subprocess.run([sys.executable, "-E", "-s", "-c", script, str(support.SRC), *words], cwd=folder,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return done.stdout.decode("utf-8").strip().splitlines()[-1].split("|")


class DispatchTest(unittest.TestCase):
    def test_a_command_loads_only_its_own_module(self) -> None:
        base = ["council.commands", "council.commands.cli", "council.commands.dispatch"]
        self.assertEqual(started("home", "rule"), sorted(base + ["council.commands.home"]))
        self.assertEqual(started("run", "status"), sorted(base + ["council.commands.runs"]))
        self.assertEqual(started("sharing"), sorted(base + ["council.commands.sharing"]))
        self.assertEqual(started("cap"), sorted(base + ["council.commands.cap", "council.commands.resolve"]))
        self.assertEqual(started("cap", "check", "Agent"),           # the build loop's rules wait for a verifier
                         sorted(base + ["council.commands.agent_gate", "council.commands.cap",
                                        "council.commands.gate_writable", "council.commands.resolve"]))
        self.assertEqual(started("run", "plan", "check"),     # rounds (datetime) waits for an open run's decisions
                         sorted(base + ["council.commands.plan", "council.commands.plan_check",
                                        "council.commands.plan_models", "council.commands.plan_tasks",
                                        "council.commands.resolve"]))
        self.assertEqual(started("route", "recommend", "--task", "x"), sorted(base + ["council.commands.route"]))
        gate = base + ["council.commands." + name for name in ("closed", "event_note", "gate", "gate_exec",
                                                                "gate_lock", "gate_output", "gate_repair",
                                                                "gate_run", "resolve", "shell")]
        self.assertEqual(started("gate", "x"), sorted(gate + ["shutil"]))       # gate_set, gate_failed: on use
        self.assertEqual(started("gate", "--all"), sorted(gate + ["shutil"]))
        self.assertEqual(started("gates"), sorted(base + ["council.commands.gate_list"]))
        self.assertEqual(started("changed"), sorted(base + ["council.commands.changed", "council.commands.shell"]))
        cites = ["council.commands." + name for name in ("cite_check", "event_note", "gate_output", "resolve")]
        self.assertEqual(started("collect"), sorted(base + cites + ["council.commands.collect"]))
        self.assertEqual(started("check"), sorted(base + cites + ["council.commands." + name for name in (
            "check", "check_proofs", "cite_origin", "hygiene", "proof_reach")]))
        self.assertEqual(started("index"), sorted(base + ["council.commands." + name for name in (
            "changed", "closed", "index", "index_symbols", "resolve", "shell")]))

    def test_an_unported_command_loads_none(self) -> None:
        self.assertEqual(started("run", "open"),
                         ["council.commands", "council.commands.cli", "council.commands.dispatch"])


class EntryTest(unittest.TestCase):
    def test_the_entry_parses_under_old_syntax_rules(self) -> None:
        data = ENTRY.read_bytes()
        data.decode("ascii")                                   # Python 2 reads source as ASCII by default
        tree = ast.parse(data)
        old = (ast.JoinedStr, ast.AnnAssign, ast.NamedExpr, ast.AsyncFunctionDef, ast.Await)
        self.assertEqual([type(node).__name__ for node in ast.walk(tree) if isinstance(node, old)], [])
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                self.assertIsNone(node.returns)
                self.assertTrue(all(arg.annotation is None for arg in node.args.args))

    def test_nothing_but_sys_is_imported_before_the_version_check(self) -> None:
        body = ast.parse(ENTRY.read_bytes()).body
        check = next(i for i, node in enumerate(body) if isinstance(node, ast.If))
        before = [node for node in body[:check] if not isinstance(node, ast.Expr)]    # the docstring aside
        self.assertEqual([ast.dump(node) for node in before], [ast.dump(ast.parse("import sys").body[0])])

    def test_an_older_python_is_refused_with_exit_85(self) -> None:
        script = ("import runpy, sys; sys.version_info = (3, 7, 9, 'final', 0); "
                  "runpy.run_path(sys.argv[1], run_name='__main__')")
        done = subprocess.run([sys.executable, "-E", "-s", "-c", script, str(ENTRY)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual((done.returncode, done.stdout, done.stderr), (85, b"", b""))

    def test_the_entry_runs_a_command_from_its_own_path(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            done = subprocess.run([sys.executable, "-E", "-s", str(ENTRY), "home", "rule", "x"], cwd=folder,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=dict(os.environ))
        self.assertEqual(done.returncode, 2)
        self.assertIn(b"doesn't take", done.stderr)


if __name__ == "__main__":
    unittest.main()
