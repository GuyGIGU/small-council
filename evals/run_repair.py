#!/usr/bin/env python3
"""No-network behavioral checks for the Phase 7 bounded repair trail."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "scripts" / "repair.py"
CLI = ROOT / "bin" / "council"
BASH = (os.environ.get("COUNCIL_EVAL_BASH") or shutil.which("bash") or
        (r"C:\Program Files\Git\bin\bash.exe" if Path(r"C:\Program Files\Git\bin\bash.exe").is_file() else None))
results = []


def check(name, okay):
    results.append((name, bool(okay)))


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def invoke(run, action, *words, via_cli=False):
    prefix = (BASH, str(CLI), "repair") if via_cli else (sys.executable, str(ENGINE))
    return subprocess.run(prefix + (action,) + words + ("--run", str(run)), cwd=run,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def rows(run):
    return [json.loads(line) for line in (run / "repairs.jsonl").read_text(encoding="utf-8").splitlines()]


with tempfile.TemporaryDirectory() as folder:
    run = Path(folder) / "runs" / "build"
    run.mkdir(parents=True)
    write(run / "session-state.md", "mode: council-implement\nstatus: in-progress\n")
    write(run / "events.tsv", "schema\tseq\tat\ttype\tsubject\tvalue\tdetail\n")
    seq = [0]

    def gate(name, code, output, empty=0):
        seq[0] += 1
        slug = "".join(chr(byte) if (65 <= byte <= 90 or 97 <= byte <= 122 or
                                     48 <= byte <= 57 or byte in (46, 95, 45)) else "_"
                       for byte in name.encode("utf-8"))
        write(run / "gates" / (slug + ".json"), json.dumps({
            "gate": name, "command": "python -m pytest tests/test_repair.py", "exit": code,
            "seconds": 1, "when": "fixture"}) + "\n")
        write(run / "gates" / (slug + ".txt"), output)
        with (run / "events.tsv").open("a", encoding="utf-8") as stream:
            stream.write("1\t{}\t2026-09-24T00:00:00Z\tgate.finished\t{}\t{}\texit={};seconds=1;empty={}\n".format(
                seq[0], name, "passed" if code == 0 else "failed", code, empty))

    write(run / "gates/baseline/tests.json", '{"gate":"tests","exit":0}\n')
    write(run / "gates/baseline/tests.txt", "100 tests passed\n")
    gate("tests", 1, "FAILED tests/test_repair.py::test_case - AssertionError\n")
    first = invoke(run, "record", "T1", "tests")
    check("first failure is classified and sent to the builder", first.returncode == 0 and
          rows(run)[0]["category"] == "TEST_FAILURE" and rows(run)[0]["lens"] == "quality-testing.md" and
          rows(run)[0]["action"] == "builder-diagnose" and rows(run)[0]["baseline"] == "green")
    again = invoke(run, "record", "T1", "tests")
    check("gate execution cannot be counted twice: recording the same run again says so and adds no row",
          again.returncode == 0 and "already recorded" in again.stdout and len(rows(run)) == 1)
    check("saved proof is inspectable", invoke(run, "check", "T1").returncode == 0 and
          (run / rows(run)[0]["proof_text"]).is_file())
    check("show names category and next action", "builder-diagnose" in invoke(run, "show", "T1").stdout)
    original = (run / rows(run)[0]["proof_text"]).read_text(encoding="utf-8")
    gate("tests", 1, "FAILED tests/test_repair.py::test_case - still wrong\n")
    second = invoke(run, "record", "T1", "tests")
    check("second failure requests independent diagnosis", second.returncode == 0 and
          rows(run)[1]["action"] == "independent-diagnosis")
    check("first output survives gate overwrite", (run / rows(run)[0]["proof_text"]).read_text(encoding="utf-8") == original)
    gate("tests", 1, "FAILED tests/test_repair.py::test_case - third time\n")
    third = invoke(run, "record", "T1", "tests")
    check("third failure stops mutation", third.returncode == 0 and rows(run)[2]["action"] == "stop" and
          "stop mutation" in third.stdout)
    gate("tests", 1, "FAILED tests/test_repair.py::test_case - fourth time\n")
    check("stopped task rejects a fourth attempt", invoke(run, "record", "T1", "tests").returncode == 2 and
          len(rows(run)) == 3)
    write(run / rows(run)[0]["proof_text"], "changed old proof\n")
    check("check detects altered proof", invoke(run, "check", "T1").returncode == 2)
    write(run / rows(run)[0]["proof_text"], original)
    recorded = rows(run)
    recorded[0]["category"] = "BUILD_FAILURE"
    write(run / "repairs.jsonl", "".join(json.dumps(row) + "\n" for row in recorded))
    check("check detects a category detached from saved output", invoke(run, "check", "T1").returncode == 2)
    check("a damaged trail cannot accept another attempt", invoke(run, "record", "T2", "tests").returncode == 2)
    recorded[0]["category"] = "TEST_FAILURE"
    write(run / "repairs.jsonl", "".join(json.dumps(row) + "\n" for row in recorded))
    recorded[0]["event_seq"] = 999
    write(run / "repairs.jsonl", "".join(json.dumps(row) + "\n" for row in recorded))
    check("check detects a missing gate execution event", invoke(run, "check", "T1").returncode == 2)
    recorded[0]["event_seq"] = 1
    write(run / "repairs.jsonl", "".join(json.dumps(row) + "\n" for row in recorded))

    gate("lint", 1, "ruff found a rule violation\n")
    gate("tests", 0, "1 passed\n")
    check("a passing first gate is not a repair", invoke(run, "record", "T2", "tests").returncode == 2)
    first_lint = invoke(run, "record", "T2", "lint")
    check("lint category chooses testing lens", first_lint.returncode == 0 and rows(run)[3]["category"] == "LINT_FAILURE")
    check("one task cannot change its tracked gate", invoke(run, "record", "T2", "tests").returncode == 2)
    gate("lint", 0, "changed: no files matched\n", empty=1)
    check("an empty pass cannot close the task", invoke(run, "record", "T2", "lint").returncode == 2)
    gate("lint", 0, "all checked files pass\n")
    resolved = invoke(run, "record", "T2", "lint")
    check("nonempty pass closes the trail", resolved.returncode == 0 and rows(run)[4]["action"] == "resolved")
    gate("lint", 1, "ruff failed again\n")
    check("resolved task cannot reopen", invoke(run, "record", "T2", "lint").returncode == 2)

    gate("setup", 127, "bash: pytest: command not found\n")
    environment = invoke(run, "record", "T3", "setup")
    check("missing tool routes to operability, not product code", environment.returncode == 0 and
          rows(run)[5]["category"] == "ENVIRONMENT_FAILURE" and rows(run)[5]["lens"] == "quality-operability.md")
    gate("mystery", 9, "opaque failure\n")
    unknown = invoke(run, "record", "T4", "mystery")
    check("unknown failure stays unknown", unknown.returncode == 0 and rows(run)[6]["category"] == "UNKNOWN")
    write(run / "gates/baseline/schema.json", '{"gate":"schema","exit":1}\n')
    gate("schema", 1, "migration failed on old database\n")
    old = invoke(run, "record", "T5", "schema")
    check("red baseline is not labelled a task regression", old.returncode == 0 and
          rows(run)[7]["baseline"] == "red" and rows(run)[7]["category"] == "SCHEMA_FAILURE")

    check("unsafe task id is refused", invoke(run, "record", "../escape", "schema").returncode == 2)
    if BASH:
        gate("types", 1, "error TS2345: argument type differs\n")
        via_helper = invoke(run, "record", "T6", "types", via_cli=True)
        check("CLI records and classifies a gate failure", via_helper.returncode == 0 and
              rows(run)[8]["category"] == "TYPE_FAILURE")
        check("CLI reads the same repair trail", invoke(run, "show", "T6", via_cli=True).returncode == 0)
    else:
        check("CLI unavailable without bash", True)
    gate("café", 1, "opaque failure\n")
    check("non-ASCII gate name follows the helper's byte-wise artifact naming",
          invoke(run, "record", "T7", "café").returncode == 0)
    gate("unit tests", 1, "FAILED tests/test_repair.py::test_named\n")
    check("gate names with spaces remain one CLI argument",
          invoke(run, "record", "T7-spaced", "unit tests", via_cli=bool(BASH)).returncode == 0)
    gate("mismatch", 1, "opaque failure\n")
    write(run / "gates/mismatch.json", '{"gate":"mismatch","command":"fixture","exit":0}\n')
    check("event and overwritten verdict cannot disagree silently",
          invoke(run, "record", "T8", "mismatch").returncode == 2)
    gate("broken", 1, "opaque failure\n")
    write(run / "gates/broken.json", "not json\n")
    check("malformed gate verdict is refused", invoke(run, "record", "T9", "broken").returncode == 2)
    examples = (
        ("T10", "compile", "build failed: compiler error\n", "BUILD_FAILURE"),
        ("T11", "queries", "foreign key constraint failed\n", "DATA_FAILURE"),
        ("T12", "threads", "deadlock detected\n", "CONCURRENCY_FAILURE"),
        ("T13", "settings", "invalid config value\n", "CONFIG_FAILURE"),
        ("T14", "speed", "benchmark regression on hot path\n", "PERFORMANCE_FAILURE"),
        ("T15", "service", "Traceback (most recent call last):\n", "RUNTIME_FAILURE"),
        ("T17", "hang", "FAILED tests/test_lock.py::test_wait\n\ncouncil: TIMED OUT after 207s — stopped at its time limit, "
         "207s (3× its 69s green baseline), with every process it started\n", "TIMEOUT_FAILURE"),
    )
    for task, name, output, expected in examples:
        gate(name, 1, output)
        response = invoke(run, "record", task, name)
        check("{} classifier signal".format(expected.lower()),
              response.returncode == 0 and rows(run)[-1]["category"] == expected)
    write(run / "gates/baseline/empty-base.json", '{"gate":"empty-base","exit":0}\n')
    write(run / "gates/baseline/empty-base.txt", "changed: no files matched\n")
    gate("empty-base", 1, "opaque failure\n")
    check("an empty baseline is not called green",
          invoke(run, "record", "T16", "empty-base").returncode == 0 and
          rows(run)[-1]["baseline"] == "empty")
    check("all saved attempts pass integrity check", invoke(run, "check").returncode == 0)

    other = Path(folder) / "runs" / "review"
    other.mkdir()
    write(other / "session-state.md", "mode: council-review\n")
    check("review runs cannot use build repair tracking", invoke(other, "show").returncode == 2)

for name, okay in results:
    print("[{}] {}".format("PASS" if okay else "FAIL", name))
passed = sum(okay for _, okay in results)
print("\n{}/{} checks passed".format(passed, len(results)))
sys.exit(0 if passed == len(results) else 1)
