#!/usr/bin/env python3
"""Record bounded, evidence-linked repair attempts for a council build run.

Classification and routing are advisory. This command never runs a gate, dispatches an
agent, edits project code, or claims that a failure was caused by the current change.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCHEMA = 1
MAX_FILE = 4 * 1024 * 1024
TASK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
EVENT_HEADER = "schema\tseq\tat\ttype\tsubject\tvalue\tdetail"
PATTERNS = (
    # bin/council's own last line for a gate it stopped at its time limit: a hang, whatever it printed before.
    ("TIMEOUT_FAILURE", r"^council: timed out after [0-9]+s", "quality-concurrency.md"),
    ("ENVIRONMENT_FAILURE", r"command not found|no such file or directory|modulenotfounderror|permission denied|connection refused|credential|authentication failed", "quality-operability.md"),
    ("SCHEMA_FAILURE", r"migration (?:failed|error)|schema (?:mismatch|error)|unknown column|relation .* does not exist", "quality-postgres.md"),
    ("DATA_FAILURE", r"constraint failed|duplicate key|foreign key|data corruption|integrityerror", "quality-postgres.md"),
    ("CONCURRENCY_FAILURE", r"deadlock|data race|race detected|concurrent modification", "quality-concurrency.md"),
    ("TYPE_FAILURE", r"\bts[0-9]{4}\b|\btypeerror\b|\bmypy\b|incompatible types", "quality-backend.md"),
    ("LINT_FAILURE", r"\b(?:ruff|eslint|flake8|pylint)\b|lint(?:ing)? (?:failed|error)", "quality-testing.md"),
    ("TEST_FAILURE", r"\bassertionerror\b|^failed [^ ]+::|^failed tests[/\\]|\b[1-9][0-9]* failed(?:,| in|$)", "quality-testing.md"),
    ("BUILD_FAILURE", r"build failed|compilation failed|compiler error|linker error", "quality-operability.md"),
    ("PERFORMANCE_FAILURE", r"benchmark regression|performance regression|timeout exceeded", "quality-performance.md"),
    ("CONFIG_FAILURE", r"invalid config|configuration error|missing environment variable", "quality-operability.md"),
    ("RUNTIME_FAILURE", r"^traceback \(most recent call last\)|\bpanic:|unhandled exception|segmentation fault", "quality-backend.md"),
)
NAME_HINTS = (
    ("type", "TYPE_FAILURE", "quality-backend.md"),
    ("lint", "LINT_FAILURE", "quality-testing.md"),
    ("test", "TEST_FAILURE", "quality-testing.md"),
    ("build", "BUILD_FAILURE", "quality-operability.md"),
)


class RepairError(Exception):
    """The repair record cannot be trusted or safely updated."""


def artifact(path, required=True):
    if path.is_symlink() or path.parent.is_symlink():
        raise RepairError("symlink artifact is not allowed: " + str(path))
    if not path.exists():
        if required:
            raise RepairError("missing artifact: " + str(path))
        return None
    if not path.is_file() or path.stat().st_size > MAX_FILE:
        raise RepairError("artifact is not a regular file under 4 MB: " + str(path))
    return path.read_bytes()


def decode(data, label):
    try:
        return data.decode("utf-8-sig")
    except UnicodeError as exc:
        raise RepairError("non-UTF-8 artifact: " + label) from exc


def event_rows(run):
    text = decode(artifact(run / "events.tsv"), "events.tsv")
    lines = text.splitlines()
    if not lines or lines[0] != EVENT_HEADER:
        raise RepairError("events.tsv has no v1 header")
    rows = []
    for expected, line in enumerate(lines[1:], 1):
        cells = line.split("\t")
        if len(cells) != 7 or cells[0] != "1" or cells[1] != str(expected):
            raise RepairError("events.tsv is malformed; run council run events check")
        rows.append({"seq": expected, "type": cells[3], "subject": cells[4],
                     "value": cells[5], "detail": cells[6]})
    return rows


def event_for(run, gate):
    latest = next((row for row in reversed(event_rows(run))
                   if row["type"] == "gate.finished" and row["subject"] == gate), None)
    if latest is None:
        raise RepairError("no recorded gate.finished event for " + gate)
    return latest


def gate_result(run, gate):
    # Match bin/council's byte-wise `tr -c 'A-Za-z0-9._-' '_'` exactly, including UTF-8 names.
    slug = "".join(chr(byte) if (65 <= byte <= 90 or 97 <= byte <= 122 or
                                 48 <= byte <= 57 or byte in (46, 95, 45)) else "_"
                   for byte in gate.encode("utf-8"))
    if not slug or slug in (".", ".."):
        raise RepairError("invalid gate name")
    verdict_path = run / "gates" / (slug + ".json")
    output_path = run / "gates" / (slug + ".txt")
    verdict_bytes = artifact(verdict_path)
    output_bytes = artifact(output_path)
    try:
        verdict = json.loads(decode(verdict_bytes, verdict_path.name))
    except (ValueError, TypeError) as exc:
        raise RepairError("malformed gate verdict: " + verdict_path.name) from exc
    if (not isinstance(verdict, dict) or verdict.get("gate") != gate or
            not isinstance(verdict.get("command"), str) or
            type(verdict.get("exit")) is not int):
        raise RepairError("gate verdict does not match the requested gate")
    event = event_for(run, gate)
    if event["value"] != ("passed" if verdict["exit"] == 0 else "failed"):
        raise RepairError("latest gate event and verdict disagree")
    detail = dict(part.split("=", 1) for part in event["detail"].split(";") if "=" in part)
    if detail.get("exit") != str(verdict["exit"]):
        raise RepairError("latest gate event and exit code disagree")
    return slug, verdict_bytes, output_bytes, verdict, event, detail


def classify(gate, output):
    lines = output.splitlines()
    for category, pattern, lens in PATTERNS:
        regex = re.compile(pattern, re.IGNORECASE)
        for number, line in enumerate(lines, 1):
            if regex.search(line):
                return category, lens, "output:{}: {}".format(number, line.strip()[:200])
    for fragment, category, lens in NAME_HINTS:
        if fragment in gate.lower():
            return category, lens, "gate name: " + gate
    return "UNKNOWN", "governing task reference", "no recognized failure signal"


def load_ledger(run):
    data = artifact(run / "repairs.jsonl", required=False)
    if data is None:
        return []
    rows = []
    for number, line in enumerate(decode(data, "repairs.jsonl").splitlines(), 1):
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise RepairError("malformed repairs.jsonl line " + str(number)) from exc
        if not isinstance(row, dict) or row.get("schema") != SCHEMA:
            raise RepairError("unsupported repairs.jsonl row " + str(number))
        rows.append(row)
    return rows


def atomic_bytes(path, data):
    if path.is_symlink():
        raise RepairError("symlink output is not allowed: " + str(path))
    fd, temporary = tempfile.mkstemp(prefix=".repair-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def baseline(run, slug, gate):
    data = artifact(run / "gates" / "baseline" / (slug + ".json"), required=False)
    if data is None:
        return "unknown"
    try:
        verdict = json.loads(decode(data, "baseline verdict"))
        code = verdict["exit"]
        if verdict.get("gate") != gate:
            raise RepairError("baseline verdict belongs to a different gate")
    except (ValueError, TypeError, KeyError) as exc:
        raise RepairError("malformed baseline gate verdict") from exc
    if type(code) is not int:
        raise RepairError("malformed baseline gate exit")
    if code != 0:
        return "red"
    output = artifact(run / "gates" / "baseline" / (slug + ".txt"), required=False)
    if output is None:
        return "unknown"
    return "empty" if b"changed: no files matched" in output else "green"


def record(run, task, gate):
    if not TASK.fullmatch(task) or not gate:
        raise RepairError("task must be a short safe id and gate must be named")
    slug, verdict_bytes, output_bytes, verdict, event, detail = gate_result(run, gate)
    rows = load_ledger(run)
    if rows:
        inspect_rows(run, rows, check=True)
    prior = [row for row in rows if row.get("task") == task]
    if any(row.get("gate") != gate for row in prior):
        raise RepairError("use the same gate for every attempt on task " + task)
    if any(row.get("event_seq") == event["seq"] for row in rows):
        print("repair: this gate run is already recorded — council gate records a build's attempts itself")
        return 0
    if prior and prior[-1].get("action") in ("resolved", "stop"):
        raise RepairError("task repair is closed; do not retry under the same task id")
    if verdict["exit"] == 0 and not prior:
        raise RepairError("a passing first gate is not a repair attempt")
    if verdict["exit"] == 0 and (detail.get("empty") == "1" or
                                 b"changed: no files matched" in output_bytes):
        raise RepairError("an empty gate cannot close a repair")
    failures = sum(row.get("result") == "failed" for row in prior)
    if verdict["exit"] != 0:
        failures += 1
        action = {1: "builder-diagnose", 2: "independent-diagnosis", 3: "stop"}.get(failures)
        if action is None:
            raise RepairError("three failures already reached the stop limit")
        category, lens, signal = classify(gate, output_bytes.decode("utf-8", errors="replace"))
        result = "failed"
    else:
        action, category, lens, signal, result = "resolved", "RESOLVED", "-", "gate exit 0", "passed"
    attempt = len(prior) + 1
    folder = run / "repairs"
    if folder.is_symlink():
        raise RepairError("symlink repairs folder is not allowed")
    folder.mkdir(exist_ok=True)
    proof_base = "repairs/{}-{}-{}".format(task, attempt, slug)
    proof_json = run / (proof_base + ".json")
    proof_text = run / (proof_base + ".txt")
    if proof_json.exists() or proof_text.exists():
        raise RepairError("attempt proof already exists; inspect before retrying")
    row = {
        "schema": SCHEMA, "task": task, "attempt": attempt, "gate": gate,
        "event_seq": event["seq"], "result": result, "exit": verdict["exit"],
        "category": category, "classification": "advisory", "signal": signal,
        "lens": lens, "baseline": baseline(run, slug, gate), "action": action,
        "proof_json": proof_base + ".json", "proof_text": proof_base + ".txt",
        "proof_sha256": hashlib.sha256(verdict_bytes + b"\n" + output_bytes).hexdigest(),
    }
    atomic_bytes(proof_json, verdict_bytes)
    atomic_bytes(proof_text, output_bytes)
    data = "".join(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
                   for item in rows + [row]).encode("utf-8")
    atomic_bytes(run / "repairs.jsonl", data)
    print("repair: task {} attempt {} — {} / {} (advisory); baseline {}".format(
        task, attempt, result, category, row["baseline"]))
    print("repair: lens {} · next {} · proof {}".format(lens, action, row["proof_text"]))
    if action == "stop":
        print("repair: stop mutation and report the blocker; do not start a fourth attempt")
    return 0


def inspect_rows(run, rows, check=False):
    if not rows:
        raise RepairError("no repair attempts recorded")
    seen = set()
    events = {event["seq"]: event for event in event_rows(run)} if check else {}
    counts = {}
    failures = {}
    closed = set()
    gates = {}
    lines = []
    for row in rows:
        key = row.get("task")
        counts[key] = counts.get(key, 0) + 1
        if (not isinstance(key, str) or not TASK.fullmatch(key) or
                row.get("attempt") != counts[key] or
                type(row.get("event_seq")) is not int or row["event_seq"] < 1 or
                type(row.get("exit")) is not int or row.get("classification") != "advisory" or
                row.get("baseline") not in ("green", "red", "empty", "unknown") or
                row.get("event_seq") in seen or
                row.get("action") not in ("builder-diagnose", "independent-diagnosis", "stop", "resolved")):
            raise RepairError("invalid or duplicate repair attempt")
        seen.add(row["event_seq"])
        if key in closed or (key in gates and gates[key] != row.get("gate")):
            raise RepairError("repair trail changed gate or continued after closure")
        gates[key] = row.get("gate")
        if row.get("result") == "failed":
            failures[key] = failures.get(key, 0) + 1
            expected = {1: "builder-diagnose", 2: "independent-diagnosis", 3: "stop"}.get(failures[key])
            if expected is None or row.get("action") != expected or row.get("exit") == 0:
                raise RepairError("invalid repair escalation")
        elif row.get("result") == "passed":
            if failures.get(key, 0) == 0 or row.get("action") != "resolved" or row.get("exit") != 0:
                raise RepairError("invalid repair resolution")
        else:
            raise RepairError("invalid repair result")
        if row["action"] in ("stop", "resolved"):
            closed.add(key)
        if check:
            event = events.get(row["event_seq"])
            if (event is None or event["type"] != "gate.finished" or
                    event["subject"] != row.get("gate") or
                    event["value"] != ("passed" if row["result"] == "passed" else "failed")):
                raise RepairError("repair row has no matching gate execution event")
            detail = dict(part.split("=", 1) for part in event["detail"].split(";") if "=" in part)
            if detail.get("exit") != str(row.get("exit")):
                raise RepairError("repair row and gate event exit disagree")
            proof_json = row.get("proof_json", "")
            proof_text = row.get("proof_text", "")
            prefix = "repairs/{}-{}-".format(key, row["attempt"])
            if (not proof_json.startswith(prefix) or not proof_text.startswith(prefix) or
                    not proof_json.endswith(".json") or not proof_text.endswith(".txt") or
                    ".." in proof_json or ".." in proof_text):
                raise RepairError("unsafe proof path in repair record")
            verdict = artifact(run / proof_json)
            output = artifact(run / proof_text)
            if hashlib.sha256(verdict + b"\n" + output).hexdigest() != row.get("proof_sha256"):
                raise RepairError("repair proof changed: " + proof_text)
            try:
                saved = json.loads(decode(verdict, proof_json))
            except (ValueError, TypeError) as exc:
                raise RepairError("invalid saved repair verdict") from exc
            if (not isinstance(saved, dict) or saved.get("gate") != row.get("gate") or
                    saved.get("exit") != row.get("exit")):
                raise RepairError("repair row and saved verdict disagree")
            if row["result"] == "failed":
                category, lens, signal = classify(row["gate"], output.decode("utf-8", errors="replace"))
                if (row.get("category"), row.get("lens"), row.get("signal")) != (category, lens, signal):
                    raise RepairError("repair classification changed from saved output")
            elif ((row.get("category"), row.get("lens"), row.get("signal")) !=
                  ("RESOLVED", "-", "gate exit 0") or detail.get("empty") == "1" or
                  b"changed: no files matched" in output):
                raise RepairError("repair resolution did not check anything")
        lines.append("{} #{} {} {} → {} [{}]".format(key, row["attempt"], row["result"],
                                                     row["category"], row["action"], row["proof_text"]))
    return lines


def allowances(run):
    """The user's recorded go for stopped gates (bin/council `repair allow`): (gate, stop event seq) pairs."""
    data = artifact(run / "repair-allowances.tsv", required=False)
    if data is None:
        return set()
    rows = [line.split("\t") for line in decode(data, "repair-allowances.tsv").splitlines()[1:]]
    return {(cells[1], cells[3]) for cells in rows if len(cells) >= 5}


def trail(run, gate):
    """One gate's repair state for bin/council, which refuses a stopped gate and names the task to
    record a failure under: none, open (its task), resolved, stop (its task and the stop's event seq)
    or allowed (the user's go is on record; a fresh task id, since the stopped trail stays closed)."""
    ledger = load_ledger(run)
    rows = [row for row in ledger if row.get("gate") == gate]
    if not rows or rows[-1].get("action") == "resolved":
        return ("none" if not rows else "resolved"), "-", "-"
    task = str(rows[-1].get("task"))
    if rows[-1].get("action") != "stop":
        return "open", task, "-"
    seq = str(rows[-1].get("event_seq"))
    if (gate, seq) not in allowances(run):
        return "stop", task, seq
    used = {row.get("task") for row in ledger}
    stem = re.sub(r"-[0-9]+$", "", task)[:60]
    fresh = next(stem + "-" + str(n) for n in range(2, 10000) if stem + "-" + str(n) not in used)
    return "allowed", fresh, seq


def free(run, task, gate):
    """The task id to record a first failure of <gate> under, from the task the Chair is on: that id
    while no trail uses it, else one of its own (T1-logs, then T1-logs-2…), so a second gate failing
    in the same task never gets an id record() refuses."""
    if not TASK.fullmatch(task):
        raise RepairError("task must be a short safe id")
    used = {row.get("task") for row in load_ledger(run)}
    if task not in used:
        return task
    stem = (task + "-" + (re.sub(r"[^A-Za-z0-9._-]+", "-", gate).strip("-") or "gate"))[:60]
    return next(c for c in [stem] + [stem + "-" + str(n) for n in range(2, 10000)] if c not in used)


def show(run, task, check=False):
    rows = load_ledger(run)
    if task:
        rows = [row for row in rows if row.get("task") == task]
    if not rows:
        raise RepairError("no repair attempts recorded" + (" for " + task if task else ""))
    for line in inspect_rows(run, rows, check):
        print(line)
    print("repair: {} recorded attempt(s){}".format(len(rows), "; proof intact" if check else ""))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "show", "check", "trail", "free"))
    parser.add_argument("task", nargs="?")
    parser.add_argument("gate", nargs="?")
    parser.add_argument("--run", required=True, type=Path)
    args = parser.parse_args()
    run = args.run.absolute()
    if run.is_symlink() or not run.is_dir():
        raise RepairError("run must be a real directory")
    state = artifact(run / "session-state.md")
    if not re.search(r"^mode: council-implement\s*$", decode(state, "session-state.md"), re.MULTILINE):
        raise RepairError("repair tracking is for council-implement runs only")
    if args.action == "record":
        if args.task is None or args.gate is None:
            parser.error("record needs a task id and gate name")
        return record(run, args.task, args.gate)
    if args.action == "trail":                 # bin/council's question: trail <gate>
        if args.task is None or args.gate is not None:
            parser.error("trail takes one gate name")
        print("\t".join(trail(run, args.task)))
        return 0
    if args.action == "free":                  # bin/council's question: free <task> <gate>
        if args.task is None or args.gate is None:
            parser.error("free takes a task id and a gate name")
        print(free(run, args.task, args.gate))
        return 0
    if args.gate is not None:
        parser.error("show/check take at most a task id")
    return show(run, args.task, check=args.action == "check")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RepairError, OSError, UnicodeError, ValueError, TypeError) as exc:
        print("repair: " + str(exc), file=sys.stderr)
        sys.exit(2)
