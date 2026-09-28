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
    council(repo, "seat", "hunt", "done", "agent=a1", "tokens=58000")
    council(repo, "seat", "verify-1", "running", "agent=v1")
    council(repo, "gate", "tests", "--", "true")
    council(repo, "gate", "lint", "--", "false")
    write(run / "repairs.jsonl", json.dumps({"task": "T1", "gate": "tests", "attempt": 2, "result": "failed",
                                             "category": "TEST_FAILURE", "action": "independent-diagnosis"}) + "\n")
    write(run / "synthesis.md", "# Synthesis\n## Kept\n(none)\n")
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
    check("tui: budget is estimated against spent so far (a seat still runs), with agent runs against the cap",
          "estimated 260k" in out and "spent 58k so far" in out and "2 agent run(s) (cap 10)" in out, out)
    check("tui: the shared plain-language status heads the screen, with what needs attention",
          "Status: Fixing a failed check" in out and "Check lint failed" in out and "attempt 2 of 3" in out, out)
    code, out, err = council(repo, "tui", "--json")
    try:
        snap = json.loads(out)
    except ValueError:
        snap = {}
    check("tui --json: the same facts as data, under a versioned schema",
          code == 0 and snap.get("schema") == "council.run-snapshot/2" and snap["usage"]["tokens"]["known"] == 58000
          and snap["usage"]["tokens"]["basis"] == "running" and snap["usage"]["tokens"]["total"] is None
          and snap["plan"]["seats"]["nygard"]["disposition"] == "skipped" and snap["events"]["header_ok"]
          and snap["claims"]["total"] == 4, out[:600] + err)
    code, out, err = council(repo, "tui", env_extra={"COUNCIL_ASCII": "1"})
    check("tui: COUNCIL_ASCII=1 prints plain ASCII for a console that can't show UTF-8",
          code == 0 and out.isascii() and "+ hunt" in out and "x lint" in out, out)
    check("tui: reading never changes the run or the council home",
          fingerprint(run) == before and fingerprint(repo / ".council") == home_before, "")

    write(run / "synthesis.md", "# Synthesis\n## Kept\n(none)\n")
    index_time = (run / "claims.jsonl").stat().st_mtime
    os.utime(run / "synthesis.md", (index_time + 5, index_time + 5))
    before_stale = fingerprint(repo / ".council")
    code, out, err = council(repo, "tui")
    check("tui: stale claims are labelled instead of displaying obsolete verdicts",
          code == 0 and "Claims index out of date" in out and "2 CONFIRMED" not in out, out + err)
    check("tui: a stale-index read writes nothing", before_stale == fingerprint(repo / ".council"))
    os.utime(run / "synthesis.md", (index_time - 5, index_time - 5))

    refusals = [(council(repo, *w), want) for w, want in (
        (("tui", "--watch", "--json"), "tui takes --watch or --json, not both"), (("tui", "x"), "tui doesn't take 'x'"),
        (("tui", "--watch=1"), "--watch takes no value"), (("tui", "--all"), "tui doesn't take --all"),
        (("gates", "--watch"), "gates doesn't take --watch"))]
    check("tui: --watch with --json, an extra word, --watch=…, a flag it doesn't take, and --watch elsewhere are "
          "refused, each saying why", all(c == 2 and want in e for (c, _, e), want in refusals),
          [(c, e) for (c, _, e), _ in refusals])

    # Control codes in the files never reach the terminal: not in a name, a number field, a note or a verdict
    ESC, BEL, CSI = chr(27), chr(7), chr(0x9B)
    write(run / "gates" / "evil.json", json.dumps({"gate": "ev" + ESC + "[2Jil", "command": "x",
                                                   "exit": ESC + "]0;PWNED" + BEL, "seconds": ESC + "[31m",
                                                   "when": "2026-09-26 20:00:00", "note": "line1\n\n FAKE LINE\tTAB"}) + "\n")
    write(run / "repairs.jsonl", json.dumps({"task": "T1", "gate": "tests", "attempt": ESC + "]52;c;cHduZWQ=" + BEL,
                                             "result": "failed", "category": "X" + CSI + "2J", "action": "stop"}) + "\n")
    write(run / "claims.jsonl", json.dumps({"id": "1", "verdict": "REFUTED" + ESC + "[8m"}) + "\n")
    code, out, err = council(repo, "tui")
    check("tui: escape, bell and C1 codes in names, numbers, notes and verdicts never reach the terminal, and a "
          "note's newline cannot draw a line of its own",
          code == 0 and not any(c in out for c in (ESC, BEL, CSI)) and "ev [2Jil" in out
          and not any(line.lstrip().startswith("FAKE LINE") for line in out.splitlines()), repr(out[-600:]))
    code, out, err = council(repo, "tui", "--json")
    check("tui --json: the same values are escaped in the data", code == 0 and ESC not in out and BEL not in out, repr(out[:300]))
    (run / "gates" / "evil.json").unlink()

    # Malformed values and deeply nested JSON are survived, on screen and as data
    write(run / "gates" / "nulls.json", json.dumps({"gate": "nulls", "exit": None, "seconds": [1]}) + "\n")
    write(run / "gates" / "list.json", json.dumps({"gate": "list", "exit": [1], "seconds": {"a": 1}}) + "\n")
    write(run / "gates" / "deep.json", "[" * 200000 + "]" * 200000)
    write(run / "claims.jsonl", "[" * 200000 + "\n" + json.dumps({"id": "2", "verdict": "CONFIRMED",
                                                        "verification": None}) + "\n")
    code, out, err = council(repo, "tui")
    code2, out2, err2 = council(repo, "tui", "--json")
    check("tui: a null or list exit, a list of seconds and 200,000-deep JSON draw as unknown instead of crashing",
          code == 0 and code2 == 0 and "? nulls" in out and "exit ?" in out and "1 claim(s)" in out
          and "Traceback" not in err + err2, (out[-500:], err, err2))
    for name in ("nulls.json", "list.json", "deep.json"):
        (run / "gates" / name).unlink()
    write(run / "repairs.jsonl", json.dumps({"task": "T1", "gate": "tests", "attempt": 2, "result": "failed",
                                             "category": "TEST_FAILURE", "action": "independent-diagnosis"}) + "\n")
    write(run / "claims.jsonl", "".join(json.dumps({"id": str(n), "verdict": v}) + "\n"
                                        for n, v in enumerate(["CONFIRMED", "CONFIRMED", "REFUTED", "UNVERIFIED"])))

    # An events.tsv too large to read is said to be too large, not missing
    big = run / "events.tsv"
    saved_events = big.read_bytes()
    big.write_bytes(saved_events + b"1\t2\t2026-09-26T00:00:00Z\tx\ty\tz\tw\n" * 130000)
    code, out, err = council(repo, "tui")
    check("tui: an events.tsv over 4 MB is reported as too large, not as missing",
          code == 0 and "over 4 MB and was not read" in out and "no events.tsv" not in out, out[-300:])
    big.write_bytes(saved_events)

    # A linked gates folder, or a linked run folder, is not followed
    outside = Path(temporary) / "outside"
    write(outside / "stolen.json", json.dumps({"gate": "stolen", "exit": 0, "seconds": 1, "when": "x"}) + "\n")
    shutil.move(str(run / "gates"), str(Path(temporary) / "gates-saved"))
    made = False
    try:
        if os.name == "nt":
            made = subprocess.run(["cmd", "/c", "mklink", "/J", str(run / "gates"), str(outside)],
                                  capture_output=True).returncode == 0
        else:
            os.symlink(str(outside), str(run / "gates"))
            made = True
    except OSError:
        made = False
    if made:
        code, out, err = council(repo, "tui")
        check("tui: a gates folder that is a link or junction to elsewhere is not read", code == 0 and "stolen" not in out, out)
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "rmdir", str(run / "gates")], capture_output=True)
        else:
            (run / "gates").unlink()
    shutil.move(str(Path(temporary) / "gates-saved"), str(run / "gates"))
    alias = repo / ".council" / "runs" / "alias-review"
    try:
        if os.name == "nt":
            made = subprocess.run(["cmd", "/c", "mklink", "/J", str(alias), str(run)], capture_output=True).returncode == 0
        else:
            os.symlink(str(run), str(alias))
            made = True
    except OSError:
        made = False
    if made:
        result = subprocess.run([sys.executable, str(COCKPIT), "--run", str(alias)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        check("cockpit: a run folder that is a link or junction is refused", result.returncode == 2
              and "link" in result.stderr, result.stderr)
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "rmdir", str(alias)], capture_output=True)
        else:
            alias.unlink()

    # On Windows, reading never makes the helper's own rename (Git Bash mv) of a state file fail. A plain
    # reader in the same tight loop is the control: it must make some renames fail, or the test proves nothing.
    if os.name == "nt":
        loop = ('fail=0; i=0; while [ $i -lt 300 ]; do printf "status: in-progress\\nn: %s\\n" "$i" > "$1.tmp"; '
                'mv -f "$1.tmp" "$1" 2>/dev/null || { fail=$((fail + 1)); rm -f "$1.tmp"; }; i=$((i + 1)); done; echo "$fail"')
        readers = {"cockpit": "sys.path.insert(0, sys.argv[2]); import cockpit; read = lambda: cockpit.text_of(Path(sys.argv[1]))",
                   "plain": "read = lambda: open(sys.argv[1], 'rb').close()"}
        failures = {}
        for name, setup in readers.items():
            target = Path(temporary) / "renamed-{}.md".format(name)
            target.write_text("status: in-progress\n", encoding="utf-8")
            code = ("import sys, time\nfrom pathlib import Path\n" + setup + "\nend = time.time() + 120\n"
                    "while time.time() < end:\n    try:\n        read()\n    except OSError:\n        pass\n")
            reader = subprocess.Popen([sys.executable, "-c", code, str(target), str(ROOT / "scripts")])
            time.sleep(0.5)
            result = subprocess.run([BASH, "-c", loop, "loop", target.as_posix()], capture_output=True, text=True, encoding="utf-8", errors="replace")
            reader.kill()
            reader.wait()
            failures[name] = int(result.stdout.strip() or -1)
        check("tui on Windows: 300 of the helper's own renames over a file it reads in a tight loop all succeed "
              "(a plain reader, the control, makes some fail)", failures["cockpit"] == 0 and failures["plain"] > 0,
              failures)

    # Watching survives a state file that is briefly gone, and stops by itself once the run is closed
    proc = subprocess.Popen([sys.executable, str(COCKPIT), "--run", str(run), "--watch", "--interval", "0.5"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    time.sleep(1.2)
    state_file = run / "session-state.md"
    kept = state_file.read_bytes()
    state_file.unlink()
    time.sleep(1.3)
    state_file.write_bytes(kept)
    time.sleep(1.0)
    still_running = proc.poll() is None
    council(repo, "run", "close", "--run", run.name, "--status", "abandoned")
    try:
        out, err = proc.communicate(timeout=15)
        stopped = proc.returncode == 0
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        stopped = False
    check("tui --watch: keeps watching through a moment with no state file, redraws, and stops by itself once "
          "the run closes", still_running and stopped and out.count("Small Council —") >= 4
          and "the run is abandoned" in out, (still_running, out[-400:], err))

    # A legacy run, and malformed files, still draw
    legacy = repo / ".council" / "runs" / "2026-01-01-000000-review"
    write(legacy / "session-state.md", "status: complete\nmode: council-review\nphase: deliver\n## Decisions so far\n")
    write(legacy / "seats.tsv", "slug\tstate\ngarbage\n\t\t\n")
    write(legacy / "gates" / "broken.json", "{not json")
    code, out, err = council(repo, "tui", "--run", legacy.name)
    check("tui: a legacy run with no events, no plan and malformed files still draws",
          code == 0 and "no events.tsv" in out and "garbage" in out, out + err)
    code, out, err = council(repo, "tui", "--watch", "--run", legacy.name)
    check("tui --watch on a closed run reads it closed twice and stops", code == 0 and "the run is complete" in out, out + err)
    result = subprocess.run([sys.executable, str(COCKPIT), "--run", str(repo)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    check("cockpit: a folder that is not a run is refused", result.returncode == 2 and "not a council run" in result.stderr,
          result.stderr)

passed = sum(good for _, good, _ in checks)
for name, good, detail in checks:
    print(f"[{'PASS' if good else 'FAIL'}] {name}" + ("" if good else f"\n        {str(detail)[:900]}"))
print(f"\n{passed}/{len(checks)} checks passed")
sys.exit(0 if passed == len(checks) else 1)
