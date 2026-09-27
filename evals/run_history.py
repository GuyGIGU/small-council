#!/usr/bin/env python3
"""Focused, no-model checks for run history: `council history` and scripts/history.py.

History must count everything but show a median, share or ratio only when enough runs carry its
data; keep a build's before/after proofs and gate probes apart from the project's gates; say what
data is missing; survive odd run folders; and write nothing.
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
sys.path.insert(0, str(ROOT / "scripts"))
import history  # noqa: E402

checks = []


def check(name, good, detail=""):
    checks.append((name, good, detail))


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def make_run(home, name, status="complete", mode="council-review", size="squad", estimate="200000",
             seats=(("hunt", "done", 60000), ("verify-1", "done", 20000)), gates=(("tests", 0),),
             repairs=(), claims=(), events=True, plan=True, older=False):
    run = home / "runs" / name
    write(run / "session-state.md", "status: {}\nmode: {}\nphase: deliver\n## Decisions so far\n".format(status, mode))
    if plan:
        write(run / "run-plan.tsv", "kind\tid\tfield\tvalue\treason\nrun\trun\tsize\t{}\tr\n"
              "budget\trun\testimated-tokens\t{}\tr\n".format(size, estimate))
    if older:     # a record from before usage.tsv: its token figures were never checked for units
        write(run / "seats.tsv", "slug\tstate\tagent\ttokens\tupdated\tnote\tagents\n"
              + "".join("{}\t{}\ta\t{}\t-\t-\t1\n".format(s, st, t) for s, st, t in seats))
    else:         # every agent run reported its usage (references/run-accounting.md)
        write(run / "seats.tsv", "slug\tstate\tagent\ttokens\tupdated\tnote\tagents\treported\n"
              + "".join("{}\t{}\ta\t{}\t-\t-\t1\t{}\n".format(s, st, t, 1 if st != "running" else 0)
                        for s, st, t in seats))
    for gate, code in gates:
        write(run / "gates" / (gate + ".json"), json.dumps({"gate": gate, "command": "x", "exit": code, "seconds": 1,
                                                           "when": name[:10] + " 10:00:00"}) + "\n")
    if repairs:
        rows = []
        for task, action, category in repairs:
            rows.append({"task": task, "gate": "tests", "attempt": 1, "result": "failed", "category": category,
                         "action": "builder-diagnose" if action == "resolved" else "stop"})
            if action == "resolved":
                rows.append({"task": task, "gate": "tests", "attempt": 2, "result": "passed", "category": "RESOLVED",
                             "action": "resolved"})
        write(run / "repairs.jsonl", "".join(json.dumps(row) + "\n" for row in rows))
    if claims:
        write(run / "claims.jsonl", "".join(json.dumps({"id": str(i), "verdict": v}) + "\n" for i, v in enumerate(claims)))
    if events:
        write(run / "events.tsv", "schema\tseq\tat\ttype\tsubject\tvalue\tdetail\n1\t1\t2026-09-01T10:00:00Z\trun.opened\trun\t{}\t-\n"
              .format(mode))
    return run


def fingerprint(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


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


with tempfile.TemporaryDirectory(prefix="council-history-") as temporary:
    home = Path(temporary) / "few" / ".council"
    home.mkdir(parents=True)
    check("no runs: said plainly", history.render(history.history(home)).startswith("no council runs yet"))
    for n in range(4):
        make_run(home, "2026-09-0{}-100000-review".format(n + 1))
    data = history.history(home)
    out = history.render(data)
    check("four completed runs: counts shown, but no median — 'too few (4 of 5 needed)'",
          data["runs"]["total"] == 4 and not data["cost"]["tokens_per_run"]["enough"]
          and "too few completed runs with a recorded cost (4 of 5 needed)" in out and "median ~" not in out, out)

    home = Path(temporary) / "many" / ".council"
    home.mkdir(parents=True)
    for n in range(5):
        make_run(home, "2026-09-{:02d}-100000-review".format(n + 1),
                 gates=(("tests", 1 if n == 0 else 0), ("before-1", 1), ("after-1", 0), ("probe-lint", 0)),
                 repairs=((("T1", "resolved", "TEST_FAILURE"),) if n < 4 else (("T1", "stop", "TEST_FAILURE"),
                                                                                ("T2", "stop", "LINT_FAILURE"))),
                 claims=("CONFIRMED", "CONFIRMED", "REFUTED") if n < 4 else ("MISCITED", "UNVERIFIED"))
    make_run(home, "2026-09-20-100000-implement", status="in-progress", mode="council-implement", plan=False,
             events=False, seats=(("builder", "running", 0),), gates=())
    make_run(home, "2026-10-01-100000-plan", status="abandoned", mode="council-plan", seats=(), gates=())
    before = fingerprint(home.parent)
    data = history.history(home)
    out = history.render(data)
    cost = data["cost"]
    check("five completed runs: median cost, agents and tokens per agent are shown",
          cost["tokens_per_run"]["enough"] and cost["tokens_per_run"]["median"] == 80000 and cost["agents_per_run"]["median"] == 2
          and cost["tokens_per_agent"]["median"] == 40000 and "median ~80k tokens" in out, (cost, out))
    check("estimates: agents' tokens over the plan's estimate less the Chair's 20k (80k of 180k)",
          data["estimates"]["actual_over_estimate"]["median"] == 0.444 and "0.44× the plan's estimate less the Chair" in out,
          out)
    mixed = Path(temporary) / "mixed" / ".council"
    for n in range(5):
        make_run(mixed, "2026-09-{:02d}-100000-review".format(n + 1))
    for n in range(2):
        make_run(mixed, "2026-08-{:02d}-100000-review".format(n + 1), older=True, seats=(("hunt", "done", 160),))
    mixed_data = history.history(mixed)
    mixed_out = history.render(mixed_data)
    check("older-format completed runs are left out of cost figures and named, never counted as tiny costs",
          mixed_data["cost"]["tokens_per_agent"]["median"] == 40000 and mixed_data["cost"]["left_out"] == {
              "older records (units never checked)": 2} and "2 completed run(s) left out of cost figures" in mixed_out,
          (mixed_data["cost"], mixed_out))
    check("a build's before/after proofs and gate probes are kept apart from the project's gates",
          data["gates"] == {"tests": {"runs": 5, "failed_runs": 1}}
          and data["proofs"]["before_failed_as_intended"] == 5 and data["proofs"]["probes"] == 5
          and "5 before-check(s), 5 failing as intended" in out, (data["gates"], data["proofs"]))
    repairs = data["repairs"]
    check("repairs: resolved and stopped trails, with a range once five runs have finished ones; failure categories "
          "come from the failed attempts, never the RESOLVED row",
          repairs["tasks"] == 6 and repairs["resolved"] == 4 and repairs["stopped"] == 2 and repairs["resolved_share"]["enough"]
          and repairs["resolved_share"]["runs"] == 5 and repairs["categories"] == {"LINT_FAILURE": 1, "TEST_FAILURE": 5}
          and "RESOLVED" not in out and "4 resolved · 2 stopped" in out, repairs)
    claims = data["claims"]
    check("claims: verdict totals and the verifier's catches among checked claims",
          claims["verdicts"] == {"CONFIRMED": 8, "MISCITED": 1, "REFUTED": 4, "UNVERIFIED": 1}
          and claims["caught_share"]["k"] == 5 and claims["caught_share"]["n"] == 13 and claims["caught_share"]["enough"], claims)
    check("runs by status, mode and month, and the open run, are counted",
          data["runs"]["by_status"] == {"abandoned": 1, "complete": 5, "in-progress": 1}
          and data["runs"]["by_month"] == {"2026-09": 6, "2026-10": 1} and data["quality"]["open"] == 1, data["runs"])
    check("missing data is named: a run with no plan and no events.tsv",
          data["quality"]["no_plan"] == 1 and data["quality"]["no_events"] == 1
          and "1 run(s) have no filled run plan" in out and "no events.tsv" in out, data["quality"])
    check("reading history changes nothing", fingerprint(home.parent) == before)

    one = Path(temporary) / "one" / ".council"
    one.mkdir(parents=True)
    make_run(one, "2026-09-01-100000-review", repairs=tuple(("T{}".format(i), "resolved", "TEST_FAILURE") for i in range(5)),
             claims=("CONFIRMED", "REFUTED", "REFUTED", "CONFIRMED", "MISCITED"))
    data = history.history(one)
    out = history.render(data)
    check("one run with five repair trails and five checked claims shows no share: 'too few runs (1 of 5 needed)'",
          not data["repairs"]["resolved_share"]["enough"] and not data["claims"]["caught_share"]["enough"]
          and "too few runs with a finished repair trail (1 of 5 needed)" in out
          and "too few runs with checked claims (1 of 5 needed)" in out and "%" not in out, out)
    write(one / "runs" / "2026-09-01-100000-review" / "claims.jsonl", "[" * 200000 + "\n")
    try:
        history.render(history.history(one))
        deep_ok = True
    except RecursionError:
        deep_ok = False
    check("200,000-deep JSON in a run's claims is survived", deep_ok)
    write(one / "ledger.tsv", "date\trun\tmode\tseat\traised\tkept\tcut\trefuted\ttokens\n" + "".join(
        "2026-09-{:02d}\t2026-09-{:02d}-000000-review\tcouncil-review\thunt\t5\t5\t0\t0\t9000\n".format(i, i)
        for i in range(1, 7)))
    data = history.history(one)
    check("seat evidence reads the ledger's last 20 runs, as council ledger advice does, not just the runs on disk",
          data["seats"]["weighed"] == ["hunt"], data["seats"])

    odd = make_run(home, "2026-10-02-100000-review")
    write(odd / "seats.tsv", "garbage\n\x00\x01\n")
    write(odd / "gates" / "x.json", "{broken")
    write(odd / "repairs.jsonl", "[1, 2]\nnot json\n")
    write(odd / "events.tsv", "wrong header\n1\t2\n")
    (home / "runs" / "not-a-run").mkdir()
    try:
        data = history.history(home)
        odd_ok = data["runs"]["total"] == 8 and data["quality"]["bad_events"] == 1
    except Exception as exc:  # noqa: BLE001 — the check is that nothing escapes
        odd_ok, data = False, str(exc)
    check("malformed files in a run are survived, a folder without session-state.md is not a run, and a bad "
          "events.tsv is named", odd_ok, data if not odd_ok else "")
    link = home / "runs" / "2026-10-03-100000-review"
    try:
        os.symlink(str(odd), str(link), target_is_directory=True)
        linked = True
    except (OSError, NotImplementedError):
        linked = False
    if linked:
        check("a symlinked run folder is not read", history.history(home)["runs"]["total"] == 8)

    if BASH and GIT:
        repo = Path(temporary) / "repo"
        (repo / ".council").mkdir(parents=True)
        subprocess.run([GIT, "init", "-q"], cwd=repo, check=True)
        write(repo / ".council" / "council.config.md", "# Council config\n")
        for n in range(2):
            make_run(repo / ".council", "2026-09-0{}-100000-review".format(n + 1))
        code, out, err = council(repo, "history")
        check("helper: council history prints the report", code == 0 and "council history · 2 run(s)" in out, out + err)
        code, out, err = council(repo, "history", "--json")
        try:
            parsed = json.loads(out)
        except ValueError:
            parsed = {}
        check("helper: --json is the same report as data", code == 0 and parsed.get("schema") == "council.history/3"
              and parsed["runs"]["total"] == 2, out[:300] + err)
        refusals = [(council(repo, *w), want) for w, want in (
            (("history", "--run", "x"), "does not take --run"), (("history", "x"), "history doesn't take 'x'"),
            (("history", "--watch"), "history doesn't take --watch"))]
        check("helper: --run, an extra word and --watch are refused, each saying why",
              all(c == 2 and want in e for (c, _, e), want in refusals), [(c, e) for (c, _, e), _ in refusals])
    else:
        print("[SKIP] bash or git unavailable — helper checks skipped")

passed = sum(good for _, good, _ in checks)
for name, good, detail in checks:
    print(f"[{'PASS' if good else 'FAIL'}] {name}" + ("" if good else f"\n        {str(detail)[:900]}"))
print(f"\n{passed}/{len(checks)} checks passed")
sys.exit(0 if passed == len(checks) else 1)
