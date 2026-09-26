#!/usr/bin/env python3
"""Focused, no-model checks for the read-only run cockpit: `council tui` and scripts/cockpit.py.

The cockpit must show what the run's own files say, keep terminal control codes out of the screen,
survive malformed or legacy runs, stop watching once the run closes, and never write a byte.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
BASH = os.environ.get("COUNCIL_EVAL_BASH") or shutil.which("bash")
GIT = shutil.which("git")
COCKPIT = ROOT / "scripts" / "cockpit.py"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
checks = []


def check(name, good, detail=""):
    checks.append((name, good, detail))


def council(repo, *args, env_extra=None, timeout=60):
    env = os.environ.copy()
    for var in ("COUNCIL_RUN", "CLAUDE_CODE_SESSION_ID", "COUNCIL_ASCII"):
        env.pop(var, None)
    env.update(env_extra or {})
    if os.environ.get("COUNCIL_EVAL_BASH"):
        env["PATH"] = str(Path(BASH).parent) + os.pathsep + env.get("PATH", "")
    words = [BASH, str(ROOT / "bin" / "council"), *args]
    if os.name == "nt":
        words = " ".join('"{}"'.format(word.replace('"', '\\"')) for word in words)
    try:
        result = subprocess.run(words, cwd=repo, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "", "council {}: still running after {} s".format(" ".join(args), timeout)
    return result.returncode, result.stdout, result.stderr


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def fingerprint(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


PLAN = [("schema", "plan", "version", "1"), ("run", "run", "size", "squad"), ("run", "run", "mode", "council-review"),
        ("assessment", "run", "risk", "medium"), ("assessment", "run", "complexity", "medium"),
        ("assessment", "run", "uncertainty", "low"), ("budget", "run", "agent-cap", "10"),
        ("budget", "run", "estimated-tokens", "260000"), ("verification", "run", "level", "independent"),
        ("seat", "chair", "disposition", "selected"), ("seat", "chair", "role", "chair"), ("context", "chair", "level", "full"),
        ("budget", "chair", "tool-calls", "80"), ("seat", "hunt", "disposition", "selected"), ("seat", "hunt", "role", "worker"),
        ("context", "hunt", "level", "focused"), ("budget", "hunt", "tool-calls", "40"),
        ("seat", "verify-1", "disposition", "selected"), ("seat", "verify-1", "role", "verifier"),
        ("context", "verify-1", "level", "focused"), ("budget", "verify-1", "tool-calls", "30"),
        ("seat", "nygard", "disposition", "skipped"), ("seat", "nygard", "role", "worker")]

if not BASH or not GIT:
    print("[SKIP] bash or git unavailable")
    raise SystemExit(0)

with tempfile.TemporaryDirectory(prefix="council-tui-") as temporary:
    repo = Path(temporary) / "repo"
    repo.mkdir()
    subprocess.run([GIT, "init", "-q"], cwd=repo, check=True)
    write(repo / ".council" / "council.config.md", "# Council config\n")
    write(repo / ".council" / "conventions.md",
          "# Memory\n## Accepted Patterns\n### AP-1: x\n## Proposed\n### F-3: a drafted failure\n"
          "- PROPOSED accepted pattern: stop flagging y\n## Rejected\n### R-1: no\n")
    code, out, err = council(repo, "run", "open", "council-review")
    run = Path(out.strip())
    check("setup: a run opens", code == 0 and run.is_dir(), out + err)
    rows = [(k, i, f, (run.name if (k, f) == ("run", "id") else v)) for k, i, f, v in PLAN] + [("run", "run", "id", run.name)]
    write(run / "run-plan.tsv", "kind\tid\tfield\tvalue\treason\n" + "".join(
        "{}\t{}\t{}\t{}\t{}\n".format(k, i, f, v, "no performance signal" if (i, f) == ("nygard", "disposition") else "because")
        for k, i, f, v in dict.fromkeys(rows)))
    code, out, err = council(repo, "run", "plan", "check")
    check("setup: the plan is valid", code == 0, out + err)
    council(repo, "seat", "hunt", "done", "agent=a1", "tokens=58k")
    council(repo, "seat", "verify-1", "running", "agent=v1")
    council(repo, "gate", "tests", "--", "true")
    council(repo, "gate", "lint", "--", "false")
    write(run / "repairs.jsonl", json.dumps({"task": "T1", "gate": "tests", "attempt": 2, "result": "failed",
                                             "category": "TEST_FAILURE", "action": "independent-diagnosis"}) + "\n")
    write(run / "claims.jsonl", "".join(json.dumps({"id": str(n), "verdict": v}) + "\n"
                                        for n, v in enumerate(["CONFIRMED", "CONFIRMED", "REFUTED", "UNVERIFIED"]))
          + "not json\n")
    before = fingerprint(run)
    home_before = fingerprint(repo / ".council")

    code, out, err = council(repo, "tui")
    check("tui: the plan, both seats' states and tokens, the skipped seat and its reason",
          code == 0 and "squad · risk medium" in out and "✓ hunt" in out and "58k" in out and "● verify-1" in out
          and "– nygard" in out and "no performance signal" in out, out + err)
    check("tui: gates with pass and fail, the repair's next step, evidence counts, memory proposals",
          "✓ tests" in out and "✗ lint" in out and "T1 tests: attempt 2 failed" in out and "independent-diagnosis" in out
          and "4 claim(s)" in out and "2 CONFIRMED" in out and "1 REFUTED" in out
          and "2 proposal(s) wait" in out, out)
    check("tui: the timeline shows the recorded events", "gate.finished" in out and "seat.updated" in out, out)
    check("tui: budget is estimated against spent, with agents against the cap",
          "estimated 260k" in out and "spent 58k" in out and "of 10" in out, out)
    code, out, err = council(repo, "tui", "--json")
    try:
        snap = json.loads(out)
    except ValueError:
        snap = {}
    check("tui --json: the same facts as data, under a versioned schema",
          code == 0 and snap.get("schema") == "council.run-snapshot/1" and snap["tokens"]["total"] == 58000
          and snap["plan"]["seats"]["nygard"]["disposition"] == "skipped" and snap["events"]["header_ok"]
          and snap["claims"]["total"] == 4, out[:600] + err)
    code, out, err = council(repo, "tui", env_extra={"COUNCIL_ASCII": "1"})
    check("tui: COUNCIL_ASCII=1 prints plain ASCII for a console that can't show UTF-8",
          code == 0 and out.isascii() and "+ hunt" in out and "x lint" in out, out)
    check("tui: reading never changes the run or the council home",
          fingerprint(run) == before and fingerprint(repo / ".council") == home_before, "")

    refusals = [(council(repo, *w), want) for w, want in (
        (("tui", "--watch", "--json"), "tui takes --watch or --json, not both"), (("tui", "x"), "tui doesn't take 'x'"),
        (("tui", "--watch=1"), "--watch takes no value"), (("tui", "--all"), "tui doesn't take --all"),
        (("gates", "--watch"), "gates doesn't take --watch"))]
    check("tui: --watch with --json, an extra word, --watch=…, a flag it doesn't take, and --watch elsewhere are "
          "refused, each saying why", all(c == 2 and want in e for (c, _, e), want in refusals),
          [(c, e) for (c, _, e), _ in refusals])

    # Control codes in the files never reach the terminal
    write(run / "gates" / "evil.json", json.dumps({"gate": "ev\u001b[2Jil", "command": "x", "exit": 3, "seconds": 1,
                                                   "when": "2026-09-26 20:00:00"}) + "\n")
    code, out, err = council(repo, "tui")
    check("tui: an escape sequence in a gate's name is neutralised", code == 0 and "\u001b" not in out and "ev [2Jil"[:4] in out, repr(out[-300:]))
    (run / "gates" / "evil.json").unlink()

    # Watching stops by itself once the run is no longer in progress
    proc = subprocess.Popen([sys.executable, str(COCKPIT), "--run", str(run), "--watch", "--interval", "0.5"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    time.sleep(1.5)
    council(repo, "run", "close", "--run", run.name, "--status", "abandoned")
    try:
        out, err = proc.communicate(timeout=15)
        stopped = proc.returncode == 0
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        stopped = False
    check("tui --watch: redraws while the run is open and stops by itself once it closes",
          stopped and out.count("Small Council —") >= 2 and "the run is abandoned" in out, (out[-400:], err))

    # A legacy run, and malformed files, still draw
    legacy = repo / ".council" / "runs" / "2026-01-01-000000-review"
    write(legacy / "session-state.md", "status: complete\nmode: council-review\nphase: deliver\n## Decisions so far\n")
    write(legacy / "seats.tsv", "slug\tstate\ngarbage\n\t\t\n")
    write(legacy / "gates" / "broken.json", "{not json")
    code, out, err = council(repo, "tui", "--run", legacy.name)
    check("tui: a legacy run with no events, no plan and malformed files still draws",
          code == 0 and "no events.tsv" in out and "garbage" in out, out + err)
    code, out, err = council(repo, "tui", "--watch", "--run", legacy.name)
    check("tui --watch on a closed run draws once and stops", code == 0 and "the run is complete" in out, out + err)
    result = subprocess.run([sys.executable, str(COCKPIT), "--run", str(repo)], capture_output=True, text=True)
    check("cockpit: a folder that is not a run is refused", result.returncode == 2 and "not a council run" in result.stderr,
          result.stderr)

passed = sum(good for _, good, _ in checks)
for name, good, detail in checks:
    print(f"[{'PASS' if good else 'FAIL'}] {name}" + ("" if good else f"\n        {str(detail)[:900]}"))
print(f"\n{passed}/{len(checks)} checks passed")
sys.exit(0 if passed == len(checks) else 1)
