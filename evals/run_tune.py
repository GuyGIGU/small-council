#!/usr/bin/env python3
"""Focused, no-model checks for conservative self-tuning: `council tune` and scripts/tune.py.

Tuning must propose only from enough of the project's own record; change one line of the config only
with the user's (redacted) words and only to the value they were shown; log every change with the
exact line it replaced; undo it byte for byte; refuse an undo over a hand edit; never leave a log
entry for a change that failed; keep the file's BOM, line endings and permissions; and never touch
the roster or behaviour. The route must budget with the value, and only a ceiling the user gave may
shrink a run.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
BASH = os.environ.get("COUNCIL_EVAL_BASH") or shutil.which("bash")
GIT = shutil.which("git")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(ROOT / "scripts"))
import tune  # noqa: E402

checks = []
CONFIG = ("# Council config\n\n## Run preferences\n- approve without asking: up to squad\n- agent cap: 10\n"
          "- context packs: off\n\n## Roster\n| Seat | Slug |\n|---|---|\n")


def check(name, good, detail=""):
    checks.append((name, good, detail))


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def make_runs(home, n, per_agent, start=1):
    """n completed runs whose three agents (two workers and a verifier) each spent per_agent tokens."""
    for i in range(n):
        run = home / "runs" / "2026-09-{:02d}-1000{:02d}-review".format(start + i, i)
        write(run / "session-state.md", "status: complete\nmode: council-review\nphase: deliver\n## Decisions so far\n")
        write(run / "run-plan.tsv", "kind\tid\tfield\tvalue\treason\nrun\trun\tsize\tsquad\tr\n"
              "budget\trun\testimated-tokens\t260000\tr\n")
        write(run / "seats.tsv", "slug\tstate\tagent\ttokens\tupdated\tnote\tagents\treported\n" + "".join(
            "{}\tdone\ta\t{}\t-\t-\t1\t1\n".format(slug, per_agent) for slug in ("hunt", "beck", "verify-1")))


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


def new_repo(base, name, config=CONFIG, raw=None):
    repo = base / name
    (repo / ".council").mkdir(parents=True)
    subprocess.run([GIT, "init", "-q"], cwd=repo, check=True)
    if raw is not None:
        (repo / ".council" / "council.config.md").write_bytes(raw)
    else:
        write(repo / ".council" / "council.config.md", config)
    return repo


def route(repo, *extra):
    code, out, _ = council(repo, "route", "recommend", "--task", "refactor the auth module", *extra)
    rows = {tuple(line.split("\t")[:3]): line.split("\t")[3] for line in out.splitlines() if line.count("\t") >= 4}
    return rows


def others(home):
    return {p.relative_to(home).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(home.rglob("*"))
            if p.is_file() and p.name not in ("council.config.md", "tuning.md")}


def round_trip(base, name, config_bytes, per_agent=150000, value="150k"):
    """Apply then revert; return (apply code, the config after revert, error text)."""
    repo = new_repo(base, name, raw=config_bytes)
    make_runs(repo / ".council", 5, per_agent)
    code, out, err = council(repo, "tune", "apply", "budget", value, "--user-said", "yes")
    code2, out2, err2 = council(repo, "tune", "revert", "budget", "--user-said", "undo")
    return code, code2, (repo / ".council" / "council.config.md").read_bytes(), out + err + out2 + err2


if not BASH or not GIT:        # nothing checked is not a pass, unless asked for (--allow-skip)
    print("[SKIP] bash or git unavailable; nothing was checked")
    raise SystemExit(0 if "--allow-skip" in sys.argv else 3)

with tempfile.TemporaryDirectory(prefix="council-tune-") as temporary:
    base = Path(temporary)

    repo = new_repo(base, "empty")
    code, out, err = council(repo, "tune")
    check("no record: the budget waits (0 of 5 needed), behaviour is held, no roster change",
          code == 0 and "waiting: too few completed runs with agents" in out and "(0 of 5 needed)" in out
          and "held — behaviour is never tuned" in out and "context packs" in out and "no seat's record clears" in out,
          out + err)

    repo = new_repo(base, "close")
    make_runs(repo / ".council", 5, 85000)
    code, out, err = council(repo, "tune")
    check("agents measuring 85k against the 80k estimate: no change proposed",
          code == 0 and "no change: the estimate (80k) is within a quarter" in out, out + err)

    repo = new_repo(base, "measured")
    home = repo / ".council"
    make_runs(home, 5, 150000)
    code, out, err = council(repo, "tune")
    check("agents measuring 150k: the estimate is proposed, with its evidence and the exact command to apply it",
          code == 0 and "PROPOSED: set it to 150k" in out and "median 150k tokens per agent over 5 completed runs" in out
          and "council tune apply budget 150k --user-said" in out, out + err)
    code, out, err = council(repo, "tune", "--json")
    try:
        data = json.loads(out)
    except ValueError:
        data = {}
    check("tune --json: the same proposals as data",
          code == 0 and data.get("schema") == "council.tune/2" and data["budget"]["status"] == "proposed"
          and data["budget"]["value"] == 150000 and len(data["held"]) == 3, out[:400] + err)
    before_other = others(home)
    before_config = (home / "council.config.md").read_bytes()
    refusals = [(council(repo, *w), want) for w, want in (
        (("tune", "apply", "budget", "150k"), "needs --user-said"),
        (("tune", "apply", "budget", "--user-said", "yes"), "usage: council tune apply budget <the value"),
        (("tune", "apply", "budget", "200k", "--user-said", "yes"), "not the 200k the user was shown"),
        (("tune", "apply", "context-packs", "150k", "--user-said", "yes"), "context-packs is held"),
        (("tune", "apply", "roster:hunt", "150k", "--user-said", "yes"), "goes through a council-init refresh"),
        (("tune", "apply", "budget", "150k", "--user-said", "   "), "the user's words are empty"),
        (("tune", "--run", "x"), "does not take --run"), (("tune", "bogus"), "usage: council tune"),
        (("tune", "revert", "budget", "--user-said", "undo it"), "no applied change"))]
    check("refusals: no words, no value, a value the user was not shown, a held knob, a roster change, blank words, "
          "--run, an unknown action, nothing to revert — each says why",
          all(c == 2 and want in e for (c, _, e), want in refusals), [(c, e) for (c, _, e), _ in refusals])
    check("…and none of them wrote anything",
          (home / "council.config.md").read_bytes() == before_config and not (home / "tuning.md").exists())

    before_route = route(repo)
    code, out, err = council(repo, "tune", "apply", "budget", "150k", "--user-said",
                             "yes, use 150k. my db password is\nZq8vT3xKp2Lm and the api token:\n"
                             "9f8e7d6c5b4a39281706f5e4d3c2b1a0")
    config = (home / "council.config.md").read_text(encoding="utf-8")
    log = (home / "tuning.md").read_text(encoding="utf-8") if (home / "tuning.md").exists() else ""
    check("apply: one line under ## Run preferences, logged as T-1 with the evidence, the words and the exact change",
          code == 0 and "T-1 applied" in out and "- context packs: off\n- estimate per worker: 150k\n\n## Roster" in config
          and "applied · estimate per worker: none → 150k" in log and "evidence: median 150k tokens per agent" in log
          and "yes, use 150k" in log and '- exact: {"after": "- estimate per worker: 150k"' in log, out + err + log)
    check("apply: a secret the user's words split across lines is still redacted before the tracked log",
          "Zq8vT3xKp2Lm" not in log and "9f8e7d6c5b4a39281706f5e4d3c2b1a0" not in log and "redacted" in log.lower(), log)
    after_route = route(repo)
    check("apply: the route budgets 150k per agent (a squad of four agents plus the Chair: 620k)",
          before_route.get(("budget", "verification", "estimated-tokens")) == "80000"
          and after_route.get(("budget", "verification", "estimated-tokens")) == "150000", after_route)
    check("apply: nothing else in the council home changed", others(home) == before_other)
    code, out, err = council(repo, "tune")
    check("after apply: nothing more is proposed, and the change is listed",
          "no change: the estimate (150k) is within a quarter" in out and "T-1 applied none → 150k" in out, out + err)

    capped = route(repo, "--budget-tokens", "600000")
    check("route: with the 150k estimate a full council needs 620k, so a 600k ceiling the user gave shrinks it to a squad",
          capped.get(("run", "route", "size")) == "squad", capped)

    code, out, err = council(repo, "tune", "revert", "budget", "--user-said", "undo that")
    log = (home / "tuning.md").read_text(encoding="utf-8")
    check("revert: the config is byte-for-byte what it was, and T-2 records it with the user's words",
          code == 0 and "T-2 reverted T-1" in out and (home / "council.config.md").read_bytes() == before_config
          and "reverted T-1 · estimate per worker: 150k → none" in log and "undo that" in log, out + err + log)
    check("revert: the route is back on its no-history estimate",
          route(repo).get(("budget", "verification", "estimated-tokens")) == "80000")
    code, out, err = council(repo, "tune", "revert", "budget", "--user-said", "again")
    check("revert twice: refused, nothing left to revert", code == 2 and "no applied change" in err, err)

    council(repo, "tune", "apply", "budget", "150k", "--user-said", "ok")
    path = home / "council.config.md"
    path.write_text(path.read_text(encoding="utf-8").replace("150k", "120k"), encoding="utf-8", newline="\n")
    code, out, err = council(repo, "tune", "revert", "budget", "--user-said", "undo")
    check("revert over a hand edit: refused, and the hand edit stays",
          code == 2 and "edited since" in err and "estimate per worker: 120k" in path.read_text(encoding="utf-8"), err)

    # Exact undo, whatever was there: a hand value the rounding would change, a unit, an unreadable value,
    # no final newline, the section at the end of the file, a BOM and CRLF.
    cases = {
        "a hand-set 92500 with a note": CONFIG.replace("- agent cap: 10\n", "- agent cap: 10\n- estimate per worker: 92500  (by hand)\n"),
        "a hand-set 1.5M": CONFIG.replace("- agent cap: 10\n", "- agent cap: 10\n- estimate per worker: 1.5M\n"),
        "an unreadable value": CONFIG.replace("- agent cap: 10\n", "- agent cap: 10\n- estimate per worker: abc\n"),
        "no final newline": CONFIG.rstrip("\n"),
        "the section at the end": "# Council config\n\n## Run preferences\n- agent cap: 10",
        "a BOM and CRLF": None,
    }
    results = {}
    for n, (label, text) in enumerate(cases.items()):
        raw = (b"\xef\xbb\xbf" + CONFIG.replace("\n", "\r\n").encode("utf-8")) if text is None else text.encode("utf-8")
        results[label] = round_trip(base, "exact{}".format(n), raw)
        results[label] = results[label] + (raw,)
    check("apply then revert restores the config byte for byte: " + ", ".join(results),
          all(r[0] == 0 and r[1] == 0 and r[2] == r[4] for r in results.values()),
          {label: (r[0], r[1], r[3][-300:]) for label, r in results.items() if not (r[0] == 0 and r[1] == 0 and r[2] == r[4])})
    repo = new_repo(base, "unreadable", CONFIG.replace("- agent cap: 10\n", "- agent cap: 10\n- estimate per worker: abc\n"))
    make_runs(repo / ".council", 5, 150000)
    council(repo, "tune", "apply", "budget", "150k", "--user-said", "fix it")
    text = (repo / ".council" / "council.config.md").read_text(encoding="utf-8")
    check("apply over an unreadable value replaces that line — never a second estimate line the route would ignore",
          text.count("estimate per worker") == 1 and "- estimate per worker: 150k" in text, text)

    repo = new_repo(base, "bomsection", raw=b"\xef\xbb\xbf## Run preferences\n- agent cap: 10\n")
    make_runs(repo / ".council", 5, 150000)
    code, out, err = council(repo, "tune", "apply", "budget", "150k", "--user-said", "yes")
    check("a BOM right before a first-line ## Run preferences is still that section",
          code == 0 and (repo / ".council" / "council.config.md").read_bytes()
          == b"\xef\xbb\xbf## Run preferences\n- agent cap: 10\n- estimate per worker: 150k\n", out + err)
    repo = new_repo(base, "comment", "## Run preferences\n- agent cap: 10\n<!-- notes\n- a bullet inside a comment\n-->\n\n## Roster\n")
    make_runs(repo / ".council", 5, 150000)
    council(repo, "tune", "apply", "budget", "150k", "--user-said", "yes")
    text = (repo / ".council" / "council.config.md").read_text(encoding="utf-8")
    check("the new line goes after the section's last real item, never inside an HTML comment",
          "- agent cap: 10\n- estimate per worker: 150k\n<!-- notes" in text, text)

    repo = new_repo(base, "crlflog")
    make_runs(repo / ".council", 5, 150000)
    (repo / ".council" / "tuning.md").write_bytes(b"# Tuning log\r\n\r\nKept by hand.\r\n")
    council(repo, "tune", "apply", "budget", "150k", "--user-said", "yes")
    raw = (repo / ".council" / "tuning.md").read_bytes()
    check("a CRLF tuning.md keeps CRLF when an entry is added", raw.count(b"\n") == raw.count(b"\r\n") and b"T-1" in raw, raw)

    if os.name != "nt":
        repo = new_repo(base, "mode")
        make_runs(repo / ".council", 5, 150000)
        os.chmod(str(repo / ".council" / "council.config.md"), 0o640)
        council(repo, "tune", "apply", "budget", "150k", "--user-said", "yes")
        check("apply keeps the config's permissions",
              stat.S_IMODE(os.stat(str(repo / ".council" / "council.config.md")).st_mode) == 0o640)

    # The log and the config are written as a pair
    home = base / "pair"
    home.mkdir()
    (home / "tuning.md").write_text("# Tuning log\n", encoding="utf-8")
    blocked = home / "council.config.md.d"
    blocked.mkdir()
    try:
        tune.write_pair(home, ["## T-? · 2026-09-26 · applied · estimate per worker: none → 150k"], blocked, "x")
        failed = False
    except OSError:
        failed = True
    check("a config that cannot be written leaves tuning.md as it was", failed and
          (home / "tuning.md").read_text(encoding="utf-8") == "# Tuning log\n")

    # The route: only a ceiling the user gave shrinks a run; implausible estimates are ignored
    repo = new_repo(base, "route", CONFIG.replace("- agent cap: 10\n", "- agent cap: 10\n- estimate per worker: 900k\n"))
    rows = route(repo)
    check("route: a large estimate with no ceiling from the user leaves the run full and ready",
          rows.get(("run", "route", "size")) == "full" and rows.get(("run", "route", "status")) == "ready", rows)
    repo = new_repo(base, "implausible", CONFIG.replace("- agent cap: 10\n", "- agent cap: 10\n- estimate per worker: 3000k\n"))
    rows = route(repo)
    check("route: an estimate over 1M is ignored, as tune.py ignores it",
          rows.get(("budget", "verification", "estimated-tokens")) == "80000" and tune.tokens("3000k") is None, rows)

    repo = new_repo(base, "nosection", "# Council config\n\n## Roster\n")
    make_runs(repo / ".council", 5, 150000)
    code, out, err = council(repo, "tune", "apply", "budget", "150k", "--user-said", "yes")
    check("a config without ## Run preferences: refused, nothing written",
          code == 2 and "no ## Run preferences section" in err and not (repo / ".council" / "tuning.md").exists(), err)

passed = sum(good for _, good, _ in checks)
for name, good, detail in checks:
    print(f"[{'PASS' if good else 'FAIL'}] {name}" + ("" if good else f"\n        {str(detail)[:1200]}"))
print(f"\n{passed}/{len(checks)} checks passed")
sys.exit(0 if passed == len(checks) else 1)
