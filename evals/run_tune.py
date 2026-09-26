#!/usr/bin/env python3
"""Focused, no-model checks for conservative self-tuning: `council tune` and scripts/tune.py.

Tuning must propose only from enough of the project's own record, change one line of the config
only with the user's (redacted) words, log every change, undo it exactly, refuse an undo over a hand
edit, keep the file's BOM and line endings, and never touch the roster or behaviour.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
BASH = os.environ.get("COUNCIL_EVAL_BASH") or shutil.which("bash")
GIT = shutil.which("git")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
checks = []
CONFIG = ("# Council config\n\n## Run preferences\n- approve without asking: up to squad\n- agent cap: 10\n"
          "- context packs: off\n\n## Roster\n| Seat | Slug |\n|---|---|\n")


def check(name, good, detail=""):
    checks.append((name, good, detail))


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def make_runs(home, n, worker_tokens, start=1):
    for i in range(n):
        run = home / "runs" / "2026-09-{:02d}-1000{:02d}-review".format(start + i, i)
        write(run / "session-state.md", "status: complete\nmode: council-review\nphase: deliver\n## Decisions so far\n")
        write(run / "run-plan.tsv", "kind\tid\tfield\tvalue\treason\nrun\trun\tsize\tsquad\tr\n"
              "budget\trun\testimated-tokens\t260000\tr\n")
        write(run / "seats.tsv", "slug\tstate\tagent\ttokens\tupdated\tnote\tagents\n"
              "hunt\tdone\ta\t{}\t-\t-\t1\nbeck\tdone\tb\t{}\t-\t-\t1\nverify-1\tdone\tv\t30000\t-\t-\t1\n".format(
                  worker_tokens, worker_tokens))


def council(repo, *args, timeout=60):
    env = os.environ.copy()
    for var in ("COUNCIL_RUN", "CLAUDE_CODE_SESSION_ID"):
        env.pop(var, None)
    if os.environ.get("COUNCIL_EVAL_BASH"):
        env["PATH"] = str(Path(BASH).parent) + os.pathsep + env.get("PATH", "")
    words = [BASH, str(ROOT / "bin" / "council"), *args]
    if os.name == "nt":
        words = " ".join('"{}"'.format(word.replace('"', '\\"')) for word in words)
    try:
        result = subprocess.run(words, cwd=repo, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "", "still running after {} s".format(timeout)
    return result.returncode, result.stdout, result.stderr


def new_repo(base, name, config=CONFIG):
    repo = base / name
    (repo / ".council").mkdir(parents=True)
    subprocess.run([GIT, "init", "-q"], cwd=repo, check=True)
    write(repo / ".council" / "council.config.md", config)
    return repo


def route_estimate(repo):
    code, out, _ = council(repo, "route", "recommend", "--task", "refactor the auth module")
    row = next((line.split("\t") for line in out.splitlines() if line.startswith("budget\tverification\testimated-tokens")), [])
    return row[3] if len(row) > 3 else None


def others(home):
    return {p.relative_to(home).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(home.rglob("*"))
            if p.is_file() and p.name not in ("council.config.md", "tuning.md")}


if not BASH or not GIT:
    print("[SKIP] bash or git unavailable")
    raise SystemExit(0)

with tempfile.TemporaryDirectory(prefix="council-tune-") as temporary:
    base = Path(temporary)

    repo = new_repo(base, "empty")
    code, out, err = council(repo, "tune")
    check("no record: the budget waits (0 of 5 needed), behaviour is held, no roster change",
          code == 0 and "waiting: too few completed runs with workers" in out and "(0 of 5 needed)" in out
          and "held — behaviour is never tuned" in out and "context packs" in out and "no seat's record clears" in out,
          out + err)

    repo = new_repo(base, "close")
    make_runs(repo / ".council", 5, 85000)
    code, out, err = council(repo, "tune")
    check("workers measuring 85k against the 80k estimate: no change proposed",
          code == 0 and "no change: the estimate (80k) is within a quarter" in out, out + err)

    repo = new_repo(base, "measured")
    home = repo / ".council"
    make_runs(home, 5, 150000)
    code, out, err = council(repo, "tune")
    check("workers measuring 150k: the estimate per worker is proposed, with its evidence and the command",
          code == 0 and "PROPOSED: set it to 150k" in out and "median 150k tokens per worker over 5 completed runs" in out
          and "council tune apply budget --user-said" in out, out + err)
    code, out, err = council(repo, "tune", "--json")
    try:
        data = json.loads(out)
    except ValueError:
        data = {}
    check("tune --json: the same proposals as data",
          code == 0 and data.get("schema") == "council.tune/1" and data["budget"]["status"] == "proposed"
          and data["budget"]["value"] == 150000 and len(data["held"]) == 3, out[:400] + err)
    before_other = others(home)
    before_config = (home / "council.config.md").read_bytes()
    refusals = [(council(repo, *w), want) for w, want in (
        (("tune", "apply", "budget"), "needs --user-said"),
        (("tune", "apply", "context-packs", "--user-said", "yes"), "context-packs is held"),
        (("tune", "apply", "roster:hunt", "--user-said", "yes"), "goes through a council-init refresh"),
        (("tune", "apply", "budget", "--user-said", "   "), "the user's words are empty"),
        (("tune", "--run", "x"), "does not take --run"), (("tune", "bogus"), "usage: council tune"),
        (("tune", "revert", "budget", "--user-said", "undo it"), "no applied change"))]
    check("refusals: no words, a held knob, a roster change, blank words, --run, an unknown action, nothing to revert",
          all(c == 2 and want in e for (c, _, e), want in refusals), [(c, e) for (c, _, e), _ in refusals])
    check("…and none of them wrote anything",
          (home / "council.config.md").read_bytes() == before_config and not (home / "tuning.md").exists())

    route_before = route_estimate(repo)
    code, out, err = council(repo, "tune", "apply", "budget", "--user-said",
                             "yes, use 150k — my key api_key=sk_live_not-a-real-key-000000 is irrelevant")
    config = (home / "council.config.md").read_text(encoding="utf-8")
    log = (home / "tuning.md").read_text(encoding="utf-8") if (home / "tuning.md").exists() else ""
    check("apply: one line under ## Run preferences, logged as T-1 with the evidence and the user's words",
          code == 0 and "T-1 applied" in out and "- context packs: off\n- estimate per worker: 150k\n\n## Roster" in config
          and "## T-1 · " in log and "applied · estimate per worker: none → 150k" in log
          and "evidence: median 150k tokens per worker" in log and "yes, use 150k" in log, out + err + config + log)
    check("apply: secret-looking text in the user's words is redacted before it reaches the tracked log",
          "sk_live" not in log and "redacted" in log.lower(), log)
    check("apply: the route now budgets with the measured estimate (150k for the verifier's share)",
          route_before == "80000" and route_estimate(repo) == "150000", (route_before, route_estimate(repo)))
    check("apply: nothing else in the council home changed", others(home) == before_other)
    code, out, err = council(repo, "tune")
    check("after apply: the estimate matches the record, so nothing more is proposed",
          "no change: the estimate (150k) is within a quarter" in out and "T-1 applied none → 150k" in out, out + err)
    code, out, err = council(repo, "tune", "apply", "budget", "--user-said", "again")
    check("apply twice: refused, nothing to apply", code == 2 and "nothing to apply" in err, err)

    code, out, err = council(repo, "tune", "revert", "budget", "--user-said", "undo that")
    config = (home / "council.config.md").read_text(encoding="utf-8")
    log = (home / "tuning.md").read_text(encoding="utf-8")
    check("revert: the line is gone, the config is byte-for-byte what it was, and T-2 records it",
          code == 0 and "T-2 reverted T-1" in out and (home / "council.config.md").read_bytes() == before_config
          and "reverted T-1 · estimate per worker: 150k → none" in log and "undo that" in log, out + err + log)
    check("revert: the route is back on its no-history estimate", route_estimate(repo) == "80000")
    code, out, err = council(repo, "tune", "revert", "budget", "--user-said", "again")
    check("revert twice: refused, nothing left to revert", code == 2 and "no applied change" in err, err)

    council(repo, "tune", "apply", "budget", "--user-said", "ok")
    path = home / "council.config.md"
    path.write_text(path.read_text(encoding="utf-8").replace("150k", "120k"), encoding="utf-8", newline="\n")
    code, out, err = council(repo, "tune", "revert", "budget", "--user-said", "undo")
    check("revert over a hand edit: refused, and the hand edit stays",
          code == 2 and "edited since" in err and "estimate per worker: 120k" in path.read_text(encoding="utf-8"), err)

    repo = new_repo(base, "replace", CONFIG.replace("- agent cap: 10\n", "- agent cap: 10\n- estimate per worker: 90k  (by hand)\n"))
    home = repo / ".council"
    make_runs(home, 6, 150000)
    code, out, err = council(repo, "tune", "apply", "budget", "--user-said", "go")
    text = (home / "council.config.md").read_text(encoding="utf-8")
    check("apply over an existing value: replaced in place, its note kept, 90k logged as before",
          code == 0 and "- estimate per worker: 150k  (by hand)\n- context packs" in text
          and "90k → 150k" in (home / "tuning.md").read_text(encoding="utf-8"), out + err + text)
    council(repo, "tune", "revert", "budget", "--user-said", "back")
    check("revert restores the earlier hand-set value", "- estimate per worker: 90k  (by hand)" in
          (home / "council.config.md").read_text(encoding="utf-8"))

    repo = new_repo(base, "crlf")
    home = repo / ".council"
    (home / "council.config.md").write_bytes(b"\xef\xbb\xbf" + CONFIG.replace("\n", "\r\n").encode("utf-8"))
    make_runs(home, 5, 150000)
    code, out, err = council(repo, "tune", "apply", "budget", "--user-said", "yes")
    raw = (home / "council.config.md").read_bytes()
    check("a BOM and CRLF config keeps both after apply, the new line included",
          code == 0 and raw.startswith(b"\xef\xbb\xbf") and b"- estimate per worker: 150k\r\n" in raw
          and raw.count(b"\n") == raw.count(b"\r\n"), raw[:200])

    repo = new_repo(base, "nosection", "# Council config\n\n## Roster\n")
    make_runs(repo / ".council", 5, 150000)
    code, out, err = council(repo, "tune", "apply", "budget", "--user-said", "yes")
    check("a config without ## Run preferences: refused, nothing written",
          code == 2 and "no ## Run preferences section" in err and not (repo / ".council" / "tuning.md").exists(), err)

passed = sum(good for _, good, _ in checks)
for name, good, detail in checks:
    print(f"[{'PASS' if good else 'FAIL'}] {name}" + ("" if good else f"\n        {str(detail)[:900]}"))
print(f"\n{passed}/{len(checks)} checks passed")
sys.exit(0 if passed == len(checks) else 1)
