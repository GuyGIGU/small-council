#!/usr/bin/env python3
"""Focused, no-model checks for run accounting and the plain-language status: `council seat`,
`council correct`, `council status [--widget | --json]`, scripts/status.py and the cockpit's reading.

Two halves:
- Accounting, through the helper. A token count is one number, stored as whole tokens. A repeated or
  resumed report never adds twice. A Workflow reports its agent count. Missing and older figures stay
  unknown, never zero. A correction keeps the original and its evidence.
- Status, from hand-made run folders read at a fixed time. It covers every state the widget shows
  (starting, running, waiting, a failing check, recovery, blocked, completed, interrupted, stale and
  unknown). A recovered failure is no current problem. A long run stays compact, and a record never
  reaches the widget unescaped. Reading a run writes nothing.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
BASH = os.environ.get("COUNCIL_EVAL_BASH") or shutil.which("bash")
GIT = shutil.which("git")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(ROOT / "scripts"))
import cockpit  # noqa: E402
import history  # noqa: E402
import status  # noqa: E402

checks = []
AT = "2026-09-27T12:00:00Z"                       # every hand-made run is read at this moment
NOW = status.utc_time(AT)


def check(name, good, detail=""):
    checks.append((name, bool(good), detail))


def council(repo, *args, timeout=90):
    env = os.environ.copy()
    for var in ("COUNCIL_RUN", "CLAUDE_CODE_SESSION_ID", "COUNCIL_ASCII"):
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
        return 124, "", "council {}: still running after {} s".format(" ".join(args), timeout)
    return result.returncode, result.stdout, result.stderr


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def read(path):
    return Path(path).read_text(encoding="utf-8")


def fingerprint(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(folder).rglob("*")) if p.is_file()}


def sourced(repo, script):
    """Run bash with the helper sourced (as the SessionStart hook sources it) and return stdout."""
    env = os.environ.copy()
    for var in ("COUNCIL_RUN", "CLAUDE_CODE_SESSION_ID"):
        env.pop(var, None)
    helper = str(ROOT / "bin" / "council").replace("\\", "/")
    result = subprocess.run([BASH, "-c", 'source "{}"; {}'.format(helper, script)], cwd=repo, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", env=env, timeout=90)
    return result.stdout


RUN_BASIS = {"older": "legacy"}         # the close line's word for what the snapshot calls legacy


def readers(repo, run):
    """The helper's and the snapshot's reading of one run: per seat (basis, agent runs, trusted tokens)
    and for the run (basis, agent runs, tokens). The two must be the same."""
    path = str(run).replace("\\", "/")
    bash_seats = {}
    for line in sourced(repo, 'seat_rows "{}"'.format(path)).splitlines():
        cells = line.split("\t")
        if len(cells) == 9:
            bash_seats[cells[0]] = (cells[2], int(cells[3]),
                                    int(cells[5]) if cells[2] in ("reported", "corrected") else None)
    words = sourced(repo, 'run_usage "{}"'.format(path)).split()
    bash_run = (RUN_BASIS.get(words[0], words[0]), int(words[1]), int(float(words[3]))) if len(words) == 8 else None
    snap = cockpit.snapshot(run, None, 8)
    py_seats = {x["slug"]: (x["tokens_basis"], x["agents"] if x["agents"] is not None else x["agents_at_least"],
                            x["tokens"] if x["tokens_basis"] in ("reported", "corrected") else None)
                for x in snap["seats"] if x["executed"]}
    usage = snap["usage"]
    py_run = (usage["tokens"]["basis"], usage["agents"]["total"] if usage["agents"]["total"] is not None
              else usage["agents"]["at_least"], usage["tokens"]["known"])
    return bash_seats, bash_run, py_seats, py_run


def seat_row(run, slug):
    for line in read(Path(run) / "seats.tsv").split("\n")[1:]:
        cells = line.split("\t")
        if cells and cells[0] == slug:
            return cells
    return []


def plan(run, seats):
    rows = [("schema", "plan", "version", "1"), ("run", "run", "id", Path(run).name), ("run", "run", "mode", "council-review"),
            ("run", "run", "size", "squad"), ("assessment", "run", "risk", "medium"),
            ("assessment", "run", "complexity", "medium"), ("assessment", "run", "uncertainty", "low"),
            ("budget", "run", "agent-cap", "10"), ("budget", "run", "estimated-tokens", "260000"),
            ("verification", "run", "level", "independent")]
    for slug in ("chair",) + tuple(seats):
        role = "chair" if slug == "chair" else ("verifier" if slug.startswith("verify-") else "worker")
        rows += [("seat", slug, "disposition", "selected"), ("seat", slug, "role", role),
                 ("context", slug, "level", "focused"), ("budget", slug, "tool-calls", "20")]
    write(Path(run) / "run-plan.tsv", "kind\tid\tfield\tvalue\treason\n"
          + "".join("{}\t{}\t{}\t{}\tbecause\n".format(*r) for r in rows))


# --- hand-made runs for the status half ---------------------------------------------------------------
def local(minutes_before):
    """A helper-style local stamp this many minutes before AT."""
    moment = NOW.astimezone().replace(tzinfo=None)
    from datetime import timedelta
    return (moment - timedelta(minutes=minutes_before)).strftime("%Y-%m-%d %H:%M:%S")


def make_run(base, name, status_value="in-progress", phase="work", seats=(), gates=(), repairs=(), extra_state="",
             events=None, seats_header="slug\tstate\tagent\ttokens\tupdated\tnote\tagents\treported", updated_min=5):
    run = Path(base) / ".council" / "runs" / name
    write(run / "session-state.md", "status: {}\nmode: council-review\nphase: {}\nupdated: {}\nopened: {}\n{}"
          "## Decisions so far\n".format(status_value, phase, local(updated_min)[:16], local(300), extra_state))
    write(run / "seats.tsv", seats_header + "\n" + "".join("\t".join(str(c) for c in s) + "\n" for s in seats))
    for n, (gate, code, minutes) in enumerate(gates):
        write(run / "gates" / "{}-{}.json".format(gate, n), json.dumps(
            {"gate": gate, "command": "true", "exit": code, "seconds": 1, "when": local(minutes)}))
    if repairs:
        write(run / "repairs.jsonl", "".join(json.dumps(r) + "\n" for r in repairs))
    if events is not None:
        write(run / "events.tsv", "schema\tseq\tat\ttype\tsubject\tvalue\tdetail\n" + "".join(
            "1\t{}\t{}\t{}\t{}\t{}\t{}\n".format(i + 1, *e) for i, e in enumerate(events)))
    return run


def reading(run, **kw):
    return status.interpret(cockpit.snapshot(run, None, 40), NOW, **kw)


def v2(slug, state, tokens, runs, reported, minutes=5, note=""):
    return (slug, state, "a-" + slug, tokens, local(minutes)[:16], note, runs, reported)


with tempfile.TemporaryDirectory(prefix="council-status-") as temporary:
    base = Path(temporary)

    # --- the states -----------------------------------------------------------------------------------
    r = reading(make_run(base, "starting", phase="convene", seats=()))
    check("state: a run with nothing dispatched yet is starting", r["state"]["key"] == "starting", r["state"])

    r = reading(make_run(base, "running", seats=[v2("hunt", "running", "", 1, 0, 3), v2("beck", "done", 50000, 1, 1, 4)]))
    check("state: an open run with work under way is running, and says who is working",
          r["state"]["key"] == "running" and "Hunt" in r["state"]["summary"] and not r["attention"], (r["state"], r["attention"]))
    check("progress: seats done and working, never a completion percentage",
          r["progress"]["seats"] == "1 of 2 done · 1 working" and "%" not in json.dumps(r["progress"]), r["progress"])

    r = reading(make_run(base, "waiting", seats=[v2("beck", "done", 50000, 1, 1, 200)], updated_min=200,
                         extra_state="waiting: approve the 3-seat plan (~300k tokens)?\n"))
    check("state: a run waiting on the user says what for, first in the attention list, and a wait is never stale",
          r["state"]["key"] == "waiting" and r["attention"][0]["kind"] == "waiting"
          and "approve the 3-seat plan" in r["attention"][0]["text"] and not any(a["kind"] == "stale" for a in r["attention"]),
          (r["state"], r["attention"]))
    notice = status.notification_line(r)
    check("notification: a waiting question leads one plain line under 200 characters",
          "Waiting for your answer" in notice and
          "approve the 3-seat plan" in notice and len(notice) < 200 and "\n" not in notice, notice)
    long_wait = make_run(base, "long-wait", extra_state="waiting: " + "*choose* <format> " * 35 + "\n")
    notice = status.notification_line(reading(long_wait))
    check("notification: long or marked-up questions are shortened to one plain line",
          len(notice) < 200 and "\n" not in notice and "*" not in notice and "<" not in notice and
          "..." == notice[-3:], notice)

    r = reading(make_run(base, "failing", seats=[v2("beck", "done", 50000, 1, 1)], gates=[("tests", 0, 30), ("lint", 1, 10)]))
    check("state: a check whose latest run failed, with no repair under way, is a failing check needing attention",
          r["state"]["key"] == "failing" and any(a["kind"] == "failure" and "lint" in a["text"] for a in r["attention"]),
          (r["state"], r["attention"]))

    rec = [{"task": "T2", "gate": "tests", "attempt": 1, "result": "failed", "category": "TEST_FAILURE",
            "action": "builder-diagnose"}]
    r = reading(make_run(base, "recovering", phase="build", gates=[("tests", 1, 10)], repairs=rec))
    check("state: a failed check with its repair under way is recovery in progress, attempt counted against the limit",
          r["state"]["key"] == "recovering" and any("attempt 1 of 3" in a["text"] for a in r["attention"])
          and not any(a["kind"] == "failure" for a in r["attention"]), (r["state"], r["attention"]))

    r = reading(make_run(base, "recovered", seats=[v2("beck", "done", 50000, 1, 1)],
                         gates=[("tests", 1, 60), ("tests", 0, 20), ("before-1", 1, 50), ("after-1", 0, 40)]))
    check("state: a failure that later passed is recovered — no longer a problem, still shown as history",
          r["state"]["key"] == "running" and not r["attention"] and "1 recovered after failing" in r["progress"]["checks"],
          (r["state"], r["attention"], r["progress"]))
    check("checks: a build's before-proof failing first is not a failure, and the latest check shown is a real one",
          r["latest_check"]["name"] == "tests" and all(c["name"] != "before-1" for c in r["checks"]), r["latest_check"])

    stop = rec + [{"task": "T2", "gate": "tests", "attempt": 2, "result": "failed", "action": "independent-diagnosis"},
                  {"task": "T2", "gate": "tests", "attempt": 3, "result": "failed", "action": "stop"}]
    r = reading(make_run(base, "blocked", phase="build", gates=[("tests", 1, 10)], repairs=stop))
    check("state: a build stopped at the repair limit is blocked, and that comes first",
          r["state"]["key"] == "blocked" and r["attention"][0]["kind"] == "blocked"
          and "needs your decision" in r["attention"][0]["text"], (r["state"], r["attention"]))
    check("notification: a blocked build leads with the stop", "build stopped" in status.notification_line(r),
          status.notification_line(r))

    r = reading(make_run(base, "completed", status_value="complete", phase="learn",
                         seats=[v2("beck", "done", 50000, 1, 1)], gates=[("tests", 0, 30)],
                         extra_state="next: nothing\nclosed: {}\n".format(local(20))))
    check("state: a completed run says so, and shows no next step", r["state"]["key"] == "completed"
          and not r["progress"]["next"] and r["state"]["label"] == "Completed", r["state"])
    check("notification: completion has one owner-facing line", "Run finished" in status.notification_line(r))

    closing_base = base / "closing"
    filed = closing_base / ".council" / "asks" / "filed.md"
    write(filed, "# Ask — Review the parser\nrun: closing\nmode: council-review\n\n"
          "## In your words\nFind the unsafe <script>alert(1)</script> path.\n")
    closed = make_run(closing_base, "closing", status_value="complete", phase="learn",
                      seats=[v2("beck", "done", 627000, 1, 1)], gates=[("tests", 0, 30)],
                      extra_state="ask: .council/asks/filed.md\ndeliverable: reviews/report-<final>.md\n"
                                  "closed: {}\n".format(local(20)))
    plan(closed, ("beck",))
    write(closed / "run-plan.tsv", read(closed / "run-plan.tsv").replace(
        "estimated-tokens\t260000", "estimated-tokens\t420000"))
    write(closed / "synthesis.md", "# Synthesis\n")
    write(closed / "claims.jsonl", "".join(json.dumps({"id": str(i), "verdict": verdict,
        "source": "synthesis.md:1"}) + "\n" for i, verdict in enumerate(
            ("CONFIRMED", "CONFIRMED", "REFUTED", "UNVERIFIED"), 1)))
    before = fingerprint(closing_base)
    r = reading(closed)
    card, plain = status.widget(r), status.text(r)
    final = r["closing"]
    check("closing card: request, deliverable, verdicts, checks, spend and agent limit are in every view",
          final["verdict_counts"] == {"confirmed": 2, "refuted": 1, "unverified": 1} and
          "Find the unsafe" in final["request"] and "reviews/report-<final>.md" == final["deliverable"] and
          "2 confirmed, 1 refuted, 1 not verified" in card and "1 passing" in card and
          "about 49% over estimate" in card and final["agent_runs"] == "1 (limit 10)" and
          all(word in plain for word in ("Asked:", "Delivered:", "Verified:", "Checks:", "Spend:",
                                        "Agent runs:", "Left for you:")) and
          "Rulings and next steps" in json.dumps(final), (final, plain, card[-1800:]))
    check("closing card: filed request and deliverable HTML are escaped",
          "&lt;script&gt;" in card and "&lt;final&gt;" in card and
          "<script>alert(1)</script>" not in card and "report-<final>" not in card, card[:1800])
    check("closing card: snapshot, text and widget write nothing", fingerprint(closing_base) == before)
    write(closed / "session-state.md", read(closed / "session-state.md").replace(
        "ask: .council/asks/filed.md", "ask: ../../outside.md"))
    check("closing card: unfiled paths never read arbitrary files", reading(closed)["closing"]["request"] ==
          "No filed request recorded.")

    r = reading(make_run(base, "paused", status_value="paused", seats=[v2("beck", "done", 50000, 1, 1)]))
    check("state: a paused run reads as interrupted ('Paused') with a note on how to go on",
          r["state"]["key"] == "interrupted" and r["state"]["label"] == "Paused"
          and any(a["kind"] == "paused" for a in r["attention"]), (r["state"], r["attention"]))
    r = reading(make_run(base, "abandoned", status_value="abandoned"))
    check("state: an abandoned run reads as stopped early", r["state"]["label"] == "Stopped early"
          and "Stopped early" in status.widget(r) and "Stopped early" in status.text(r), r["state"])

    r = reading(make_run(base, "stale", seats=[v2("hunt", "running", "", 1, 0, 190)], updated_min=190))
    check("state: an open run with nothing recorded for over an hour reads as quiet, with how long",
          r["state"]["key"] == "stale" and any(a["kind"] == "stale" and "3 h 10 min" in a["text"] for a in r["attention"]),
          (r["state"], r["attention"]))

    broken = make_run(base, "broken")
    write(broken / "session-state.md", "not a header at all\n")
    r = reading(broken)
    check("state: unreadable run records read as unknown, never as fine", r["state"]["key"] == "unknown"
          and any(a["kind"] == "data" for a in r["attention"]), r["state"])

    memorybase = base / "large-memory"
    write(memorybase / ".council" / "conventions.md", "x" * 30000)
    memoryrun = make_run(memorybase, "memory")
    r = reading(memoryrun)
    check("memory size: a 30 KB file is a note on the open card, without changing the file",
          any(a["kind"] == "memory-size" and a["severity"] == 1 and "30 KB" in a["text"]
              for a in r["attention"]) and (memorybase / ".council" / "conventions.md").stat().st_size == 30000,
          r["attention"])
    write(memorybase / ".council" / "conventions.md", "x" * 20000)
    r = reading(memoryrun)
    check("memory size: a 20 KB file has no warning",
          not any(a["kind"] == "memory-size" for a in r["attention"]), r["attention"])
    write(memorybase / ".council" / "council.config.md",
          "# Council config\n## Memory\n- conventions: docs/project-memory.md\n")
    write(memorybase / "docs" / "project-memory.md", "x" * 65864)
    r = reading(memoryrun)
    check("memory size: the card follows the configured memory path",
          any(a["kind"] == "memory-size" and "project-memory.md is 66 KB" in a["text"]
              for a in r["attention"]), r["attention"])

    # --- what the numbers may say ----------------------------------------------------------------------
    legacy = make_run(base, "legacy", seats=[("hunt", "done", "verifier", "160", local(5)[:16], "", "1"),
                                             ("beck", "done", "", "201000", local(4)[:16], "", "1")],
                      seats_header="slug\tstate\tagent\ttokens\tupdated\tnote\tagents")
    snap = cockpit.snapshot(legacy, None, 8)
    r = status.interpret(snap, NOW)
    check("tokens: an older record's figures are never totalled — its units were never checked",
          snap["usage"]["tokens"]["total"] is None and r["usage"]["basis"] == "legacy"
          and "not reliably recorded" in r["usage"]["text"], (snap["usage"], r["usage"]))
    check("agents: an older record gives a lower bound only", snap["usage"]["agents"]["total"] is None
          and r["usage"]["agent_runs_text"].startswith("at least 2"), r["usage"])
    edge = make_run(base, "edge", status_value="complete", seats=[v2("hunt", "done", 1000, 1, 1)])
    check("tokens: exactly 1,000 is a real count to the reader, not suspect",
          cockpit.snapshot(edge, None, 8)["usage"]["tokens"]["basis"] == "complete")
    suspect = make_run(base, "suspect", status_value="complete", seats=[v2("hunt", "done", 160, 1, 1), v2("beck", "done", 50000, 1, 1)])
    snap = cockpit.snapshot(suspect, None, 8)
    check("tokens: a count under a thousand for an agent run is suspect, not a total",
          snap["usage"]["tokens"]["basis"] == "suspect" and snap["usage"]["tokens"]["total"] is None
          and snap["usage"]["tokens"]["suspect_seats"] == ["hunt"], snap["usage"])
    partial = make_run(base, "partial", status_value="complete",
                       seats=[v2("hunt", "done", 50000, 2, 1), v2("beck", "done", "", 1, 0)])
    snap = cockpit.snapshot(partial, None, 8)
    r = status.interpret(snap, NOW)
    check("tokens: missing usage reports make the total a lower bound, and say how many",
          snap["usage"]["tokens"]["basis"] == "partial" and snap["usage"]["tokens"]["missing_runs"] == 2
          and r["usage"]["text"].startswith("at least 50k"), (snap["usage"], r["usage"]["text"]))
    whole = make_run(base, "whole", status_value="complete",
                     seats=[v2("hunt", "done", 50000, 1, 1), v2("verify-1", "done", 4625154, 38, 38)])
    snap = cockpit.snapshot(whole, None, 8)
    check("tokens: every agent run reported → an exact total, split workers from verifiers, with the exact run count",
          snap["usage"]["tokens"]["total"] == 4675154 and snap["usage"]["tokens"]["verifiers"] == 4625154
          and snap["usage"]["agents"]["total"] == 39, snap["usage"])
    write(legacy / "corrections.jsonl", "".join(json.dumps(c) + "\n" for c in (
        {"schema": 1, "seat": "hunt", "field": "tokens", "from": "160", "to": 160360, "evidence": "transcript A L1679 uuid be2f"},
        {"schema": 1, "seat": "hunt", "field": "agents", "from": "1", "to": 1, "evidence": "transcript A L1564 one Agent call"},
        {"schema": 1, "seat": "beck", "field": "tokens", "from": "201000", "to": 200958, "evidence": "transcript B L951"},
        {"schema": 1, "seat": "beck", "field": "agents", "from": "1", "to": 1, "evidence": "transcript B L868"},
        {"schema": 1, "seat": "beck", "field": "tokens", "from": "201000", "to": 99, "evidence": ""})))
    snap = cockpit.snapshot(legacy, None, 8)
    check("corrections: evidence-backed figures lay over an older record and make its totals exact; one without evidence is ignored",
          snap["usage"]["tokens"]["total"] == 361318 and snap["usage"]["agents"]["total"] == 2
          and sorted(snap["usage"]["tokens"]["corrected_seats"]) == ["beck", "hunt"], snap["usage"])

    # --- the agent cap ------------------------------------------------------------------------------------
    capbase = base / "capcfg"
    write(capbase / ".council" / "council.config.md", "# Council config\n- agent cap: 3\n")
    r = reading(make_run(capbase, "over", seats=[v2("wf", "done", 500000, 5, 5)]))
    check("cap: a run with no plan is held to the project's configured cap, and an open run over it needs the user",
          any(a["kind"] == "cap" and a["severity"] == 2 and "5 agent runs, over its limit of 3" in a["text"] for a in r["attention"])
          and r["usage"]["text"].endswith("(limit 3)"), (r["attention"], r["usage"]))
    r = reading(make_run(capbase, "over-closed", status_value="complete", phase="learn", seats=[v2("wf", "done", 500000, 5, 5)]))
    check("cap: a finished run over its cap keeps a note, not a call to act",
          any(a["kind"] == "cap" and a["severity"] == 1 and "used 5 agent runs" in a["text"] for a in r["attention"]), r["attention"])
    r = reading(make_run(capbase, "at-cap", seats=[v2("wf", "done", 300000, 3, 3)]))
    check("cap: a run exactly at its cap is not flagged", not any(a["kind"] == "cap" for a in r["attention"]), r["attention"])
    check("notification: reaching the cap gives an actionable line even before it is exceeded",
          "Agent limit reached (3)" in status.notification_line(r), status.notification_line(r))

    spendbase = base / "spend"
    under = make_run(spendbase, "under", seats=[v2("wf", "done", 300000, 1, 1)])
    plan(under, ("wf",))
    write(under / "run-plan.tsv", read(under / "run-plan.tsv").replace("estimated-tokens\t260000", "estimated-tokens\t420000")
          + "budget\trun\ttoken-ceiling\t600000\towner limit\n")
    r = reading(under)
    check("spend: below the estimate, the card and JSON show the plan without an alarm",
          r["usage"]["estimate"] == 420000 and r["usage"]["ceiling"] == 600000 and
          "spent 300k of estimated 420k" in r["usage"]["spend_text"] and
          not any(a["kind"] in ("estimate", "ceiling") for a in r["attention"]) and
          "Spend:" in status.widget(r), r["usage"])
    over = make_run(spendbase, "over", seats=[v2("wf", "done", 627000, 1, 1)])
    plan(over, ("wf",))
    write(over / "run-plan.tsv", read(over / "run-plan.tsv").replace("estimated-tokens\t260000", "estimated-tokens\t420000")
          + "budget\trun\ttoken-ceiling\t600000\towner limit\n")
    r = reading(over)
    check("spend: 627k against 420k is about 49% over in card, text and JSON",
          "about 49% over estimate" in r["usage"]["spend_text"] and
          "about 49% over estimate" in status.widget(r) and
          "about 49% over estimate" in status.text(r) and
          r["usage"]["estimate"] == 420000, r["usage"])
    check("spend: an open run over its ceiling asks before more work",
          any(a["kind"] == "estimate" and a["severity"] == 1 for a in r["attention"]) and
          any(a["kind"] == "ceiling" and a["severity"] == 2 and "only after you say so" in a["text"]
              for a in r["attention"]), r["attention"])
    partial = make_run(spendbase, "partial", seats=[v2("wf", "done", 627000, 2, 1)])
    plan(partial, ("wf",))
    write(partial / "run-plan.tsv", read(partial / "run-plan.tsv").replace("estimated-tokens\t260000", "estimated-tokens\t420000")
          + "budget\trun\ttoken-ceiling\t600000\towner limit\n")
    r = reading(partial)
    check("spend: missing usage makes the comparison a lower bound",
          r["usage"]["basis"] == "partial" and
          "at least 627k used" in r["usage"]["spend_text"] and
          "at least about 49% over" in r["usage"]["spend_text"], r["usage"])
    closed = make_run(spendbase, "closed", status_value="complete", seats=[v2("wf", "done", 627000, 1, 1)])
    plan(closed, ("wf",))
    write(closed / "run-plan.tsv", read(closed / "run-plan.tsv").replace("estimated-tokens\t260000", "estimated-tokens\t420000")
          + "budget\trun\ttoken-ceiling\t600000\towner limit\n")
    r = reading(closed)
    check("spend: a closed run over its ceiling keeps a note instead of asking to stop",
          any(a["kind"] == "ceiling" and a["severity"] == 1 for a in r["attention"]), r["attention"])

    # --- history leaves out what it can't count ------------------------------------------------------------
    home = base / "hist"
    for i in range(5):
        make_run(home.parent / "hist-root", "2026-09-2{}-000000-review".format(i), status_value="complete",
                 seats=[v2("hunt", "done", 60000, 1, 1), v2("beck", "done", 40000, 1, 1)])
    make_run(home.parent / "hist-root", "2026-09-19-000000-review", status_value="complete",
             seats=[("hunt", "done", "", "160", local(5)[:16], "", "1")], seats_header="slug\tstate\tagent\ttokens\tupdated\tnote\tagents")
    make_run(home.parent / "hist-root", "2026-09-18-000000-review", status_value="complete",
             seats=[("wf", "done", "a-wf", "2967380", local(5)[:16], "", "1", "")])
    inexact = make_run(home.parent / "hist-root", "2026-09-17-000000-review", status_value="complete",
                       seats=[("hunt", "done", "", "160", local(5)[:16], "", "1")],
                       seats_header="slug\tstate\tagent\ttokens\tupdated\tnote\tagents")
    write(inexact / "corrections.jsonl", json.dumps({"schema": 1, "seat": "hunt", "field": "tokens", "from": "160",
                                                     "to": 160360, "evidence": "transcript A L1679"}) + "\n")
    data = history.history(home.parent / "hist-root" / ".council")
    check("history: only runs with complete, exact records are costed; the rest are counted and named, never zeroes",
          data["cost"]["tokens_per_agent"]["enough"] and data["cost"]["tokens_per_agent"]["median"] == 50000
          and data["cost"]["tokens_per_agent"]["n"] == 5
          and data["cost"]["left_out"] == {"older records (units never checked)": 2,
                                           "agent-run count not exact": 1}, data["cost"])
    check("history: the report says five runs make a figure eligible, not reliable, and lists what was left out",
          "eligible, not reliable" in history.render(data) and "left out of cost figures" in history.render(data),
          history.render(data))

    # --- the widget --------------------------------------------------------------------------------------
    evil = make_run(base, "evil", seats=[v2("hunt", "running", "", 1, 0, 3,
                                            note='<img src=x onerror="alert(1)"> \x1b[2J</details><script>bad()</script>')],
                    extra_state="next: finish <b>now</b> & report\n")
    r = reading(evil)
    html = status.widget(r)
    check("widget: every value from the records is escaped, and control codes never reach it",
          "<img" not in html and "&lt;img" in html and "<script>bad" not in html and "\x1b" not in html
          and "&lt;/details&gt;" in html and "&lt;b&gt;now&lt;/b&gt; &amp; report" in html, html[:400])
    check("widget: no network, no page — only the host's own styles, one inline script, no external source",
          "http://" not in html and "https://" not in html and "<script src" not in html and html.count("<script>") == 1
          and "<html" not in html and "<body" not in html and "position:fixed" not in html.replace(" ", ""), html[-600:])
    check("widget: a screen-reader summary first, and the state in words and an icon, never colour alone",
          re.search(r'<h2 class="sr">[^<]*Running', html) is not None and ">Running</span>" in html and "ti-activity" in html,
          html[:700])
    check("widget: the snapshot carries its time, shows it, and turns its age into words in the page",
          'data-at="{}"'.format(AT) in html and 'id="sc-age"' in html and "sc-old" in html and "hidden" in html, html[-900:])
    check("widget: it says plainly that it is a snapshot you ask for again, never that it updates itself",
          "Ask for the council status" in html and not re.search(r"live|real-time|auto-?refresh", html, re.I), html[-900:])
    preview = status.widget(r, preview=True)
    check("widget: a preview says it is one, with the time of its fixed snapshot, and that it does not update",
          "Preview built from a fixed snapshot taken" in preview and "does not update" in preview, preview[:900])

    many = make_run(base, "long", phase="build",
                    seats=[v2("seat-{}".format(i), "done", 50000 + i, 1, 1, 400 - i) for i in range(120)],
                    gates=[("check-{}".format(i % 40), 1 if i % 7 == 0 else 0, 300 - i) for i in range(300)],
                    events=[("{}".format(AT), "seat.updated", "seat-{}".format(i), "done", "tokens=1") for i in range(250)])
    big = status.widget(reading(many))
    check("widget: a long run stays compact — capped lists, 'latest N of M', under 16 KB",
          len(big.encode("utf-8")) < 16 * 1024 and "latest 12 of 120" in big and big.count("<li>") <= 12 + 12 + 5 + 5 + 12,
          len(big.encode("utf-8")))

    # --- the cockpit keeps working ------------------------------------------------------------------------
    frame = cockpit.render(cockpit.snapshot(legacy, None, 8), reading=status.interpret(cockpit.snapshot(legacy, None, 8), NOW))
    check("tui: the terminal fallback still draws, with the shared status line on top",
          "Small Council —" in frame and "Status:" in frame and "Budget:" in frame, frame)
    old6 = make_run(base, "six-columns", seats=[("hunt", "done", "a1", "74000", local(5)[:16], "")],
                    seats_header="slug\tstate\tagent\ttokens\tupdated\tnote")
    try:
        frame = cockpit.render(cockpit.snapshot(old6, None, 8), reading=reading(old6))
        ok = "Small Council —" in frame and "74000?" in frame
    except Exception as exc:  # noqa: BLE001
        ok, frame = False, repr(exc)
    check("tui: a six-column record from before agent counting still draws, its figure marked unchecked", ok, frame)
    ghost = make_run(base, "ghost", seats=[v2("hunt", "done", 50000, 1, 1, note="part one part two\x1cthree")])
    snap = cockpit.snapshot(ghost, None, 8)
    check("records: a line break inside a note never becomes a seat of its own",
          [s["slug"] for s in snap["seats"]] == ["hunt"], [s["slug"] for s in snap["seats"]])

    # --- through the helper ------------------------------------------------------------------------------
    if not BASH or not GIT:
        print("[SKIP] bash or git unavailable — helper checks skipped")
        check("helper: bash and git are available (required for the helper half)", False, "missing")
    else:
        repo = base / "repo"
        repo.mkdir()
        subprocess.run([GIT, "init", "-q"], cwd=repo, check=True)
        write(repo / ".council" / "council.config.md", "# Council config\n")
        code, out, err = council(repo, "run", "open", "council-review")
        run = Path(out.strip())
        plan(run, ("hunt", "beck", "leach", "fowler", "wf", "verify-1"))
        check("setup: a run opens with the accounting columns", code == 0
              and read(run / "seats.tsv").startswith("slug\tstate\tagent\ttokens\tupdated\tnote\tagents\treported\n"), err)

        refused = [(council(repo, "seat", "hunt", "done", "agent=a1", "tokens=" + value), value) for value in (
            "12 tool uses, 45000 tokens", "-500", "1e5", "74,3k", "lots", "160", "0", "999", "74.3k", "160k", "1.2M")]
        check("seat: a token count must be one exact, plausible number — two numbers, a sign, an exponent, a decimal "
              "comma, a count under 1,000, or a rounded 74.3k are refused and nothing is written",
              all(code == 2 for (code, _, _), _ in refused) and not seat_row(run, "hunt"),
              [(v, c, e.strip()[-120:]) for (c, _, e), v in refused])
        for value, want in (("74,304", "74304"), ("74 304", "74304"), ("74304 tokens", "74304"), ("0074304", "74304")):
            slug = "fowler"
            write(run / "seats.tsv", read(run / "seats.tsv").split("\n")[0] + "\n")
            (run / "usage.tsv").unlink(missing_ok=True)
            council(repo, "seat", slug, "done", "agent=a9", "tokens=" + value)
            check("seat: tokens={} is stored as {} whole tokens".format(value, want), seat_row(run, slug)[3:4] == [want],
                  seat_row(run, slug))
        write(run / "seats.tsv", read(run / "seats.tsv").split("\n")[0] + "\n")
        (run / "usage.tsv").unlink(missing_ok=True)
        code, _, err = council(repo, "seat", "hunt", "running", "tokens=5000")
        check("seat: usage comes with a finished run — tokens= on running is refused", code == 2 and "finished" in err, err)
        code, _, err = council(repo, "seat", "hunt", "running", "agent=council-verifier")
        code2, _, err2 = council(repo, "seat", "hunt", "running", "agent=workflow")
        check("seat: a role name where the agent id belongs is refused (a real run recorded 'workflow')",
              code == 2 and code2 == 2 and "role, not an agent id" in err + err2, err + err2)

        council(repo, "seat", "hunt", "running", "agent=a1")
        council(repo, "seat", "hunt", "done", "tokens=50000")
        code, out, _ = council(repo, "seat", "hunt", "done", "tokens=50000")
        check("seat: the same usage report recorded twice counts once", seat_row(run, "hunt")[3:4] == ["50000"]
              and seat_row(run, "hunt")[6:8] == ["1", "1"], seat_row(run, "hunt"))
        council(repo, "seat", "hunt", "running", "agent=a1", "note=round 2")
        council(repo, "seat", "hunt", "done", "tokens=80000")
        check("seat: a resumed agent's later report is its running total — it replaces, and is still one agent run",
              seat_row(run, "hunt")[3:4] == ["80000"] and seat_row(run, "hunt")[6:8] == ["1", "1"], seat_row(run, "hunt"))
        council(repo, "seat", "hunt", "running", "agent=a2")
        code, out, _ = council(repo, "seat", "hunt", "done", "tokens=30000")
        check("seat: a re-dispatched agent is a second agent run and adds its own tokens",
              seat_row(run, "hunt")[3:4] == ["110000"] and seat_row(run, "hunt")[6:8] == ["2", "2"], seat_row(run, "hunt"))
        check("progress: the line counts seats as seats, not agents", out.startswith("seats: 1 of 1 done") and "~110k tokens so far" in out, out)
        council(repo, "seat", "wf", "running", "agent=wf_1b2fc8d3-b14")
        _, _, cap_err = council(repo, "seat", "wf", "done", "agents=38", "tokens=4625154")
        check("seat: a Workflow's report carries its agent count — 38 agent runs, not one",
              seat_row(run, "wf")[3:4] == ["4625154"] and seat_row(run, "wf")[6:8] == ["38", "38"], seat_row(run, "wf"))
        check("cap: the record that takes the run past its agent cap tells the Chair — every agent a Workflow started counts",
              "over its cap of 10" in cap_err and "ask before starting more" in cap_err, cap_err)
        council(repo, "seat", "beck", "queued")
        code, out, _ = council(repo, "seat", "leach", "running", "agent=a5")
        check("progress: queued seats are queued, not 'still working'", "queued: beck" in out and "still working: leach" in out, out)
        council(repo, "seat", "leach", "failed", "note=died with its session")
        council(repo, "seat", "beck", "skipped", "note=no surface")
        usage = read(run / "usage.tsv")
        check("usage.tsv: every dispatch and every report is its own row, the audit trail behind the seat totals",
              usage.startswith("at\tseat\tagent\tkind\truns\ttokens\n") and usage.count("\tdispatched\t") == 4
              and usage.count("\tfinished\t") == 5, usage)
        council(repo, "state", "waiting=approve the fix?")
        council(repo, "state", "waiting=")
        events = read(run / "events.tsv")
        check("state: setting and clearing what the run waits on the user for are events of their own",
              "\trun.waiting_changed\trun\ton\t" in events and "\trun.waiting_changed\trun\toff\t" in events, events[-400:])
        code, out, err = council(repo, "run", "events", "check")
        check("events: the stream with the new detail fields and event types still checks", code == 0, out + err)
        check("cap: passing the agent cap is recorded once, however many records follow",
              events.count("\trun.cap_passed\trun\t") == 1 and "\tcap=10\n" in events, events[-600:])

        council(repo, "gate", "smoke", "--", "false")
        failing = json.loads(council(repo, "status", "--json")[1])
        council(repo, "gate", "smoke", "--", "true")
        passing = json.loads(council(repo, "status", "--json")[1])
        check("status: a check re-run under the same name after failing reads as recovered — its saved result is "
              "overwritten, so the failure comes from the event stream (found on a real run)",
              failing["state"]["key"] == "failing" and passing["state"]["key"] == "running"
              and "1 recovered after failing" in passing["progress"]["checks"]
              and not any(a["kind"] in ("failure", "recovering") for a in passing["attention"]),
              (failing["state"], passing["progress"], passing["attention"]))
        cap_items = [a for a in passing["attention"] if a["kind"] == "cap"]
        check("cap: the card says the open run is over its agent limit, as something that needs the user",
              len(cap_items) == 1 and cap_items[0]["severity"] == 2 and "41 agent runs, over its limit of 10" in cap_items[0]["text"]
              and "(limit 10)" in passing["usage"]["agent_runs_text"] + passing["usage"]["text"],
              (passing["attention"], passing["usage"]))
        before = fingerprint(run)
        code, text_out, err = council(repo, "status")
        code_w, widget_out, err_w = council(repo, "status", "--widget")
        code_j, json_out, err_j = council(repo, "status", "--json")
        check("status: the summary names the state, what needs the user, and the exact terminal-view command",
              code == 0 and "Status:" in text_out and "Needs you:" in text_out and "tui --watch --run" in text_out
              and run.name in text_out, text_out + err)
        check("status: --widget prints one self-contained fragment; --json the same reading as data",
              code_w == 0 and widget_out.lstrip().startswith("<style>") and code_j == 0
              and json.loads(json_out)["schema"] == "council.run-status/1", (widget_out[:200], json_out[:200], err_w, err_j))
        code_l, line_out, err_l = council(repo, "status", "--line")
        check("status: --line prints a short plain owner notice through the helper",
              code_l == 0 and len(line_out.strip()) < 200 and "\n" not in line_out.strip() and
              "over its limit" in line_out, (code_l, line_out, err_l))
        config_path = repo / ".council" / "council.config.md"
        original_config = read(config_path)
        write(config_path, original_config + "\n- notifications: off\n")
        code_l, line_out, err_l = council(repo, "status", "--line")
        check("status: project off switch makes --line print nothing", code_l == 0 and line_out == "",
              (code_l, line_out, err_l))
        write(config_path, original_config)
        check("status: reading a run — summary, widget or data — writes nothing", fingerprint(run) == before, "changed")
        refusals = [(council(repo, "status", *w), want) for w, want in (
            (("--widget", "--json"), "not together"), (("--line", "--json"), "not together"),
            (("--preview",), "use it with --widget"), (("now",), "doesn't take"),
            (("--watch",), "doesn't take --watch"))]
        check("status: flag mistakes are refused, each saying why", all(c == 2 and want in e for (c, _, e), want in refusals),
              [(c, e) for (c, _, e), _ in refusals])

        capped = base / "capped"
        capped.mkdir()
        subprocess.run([GIT, "init", "-q"], cwd=capped, check=True)
        write(capped / ".council" / "council.config.md", "# Council config\n")
        crun = Path(council(capped, "run", "open", "council-review")[1].strip())
        plan(crun, ("a", "verify-1"))
        write(crun / "run-plan.tsv", read(crun / "run-plan.tsv").replace("agent-cap\t10", "agent-cap\t2"))
        _, _, e1 = council(capped, "seat", "a", "running", "agent=x1")
        _, _, e2 = council(capped, "seat", "verify-1", "running", "agent=x2")
        check("cap: reaching the cap tells the Chair to ask before starting more; below it, nothing is said",
              "agent runs" not in e1 and "used all 2 agent runs of its cap" in e2, (e1, e2))
        _, _, e3 = council(capped, "seat", "a", "done", "agents=3", "tokens=9000")
        council(capped, "seat", "verify-1", "done", "tokens=6000")
        cev = read(crun / "events.tsv")
        creading = json.loads(council(capped, "status", "--json")[1])
        citems = [x for x in creading["attention"] if x["kind"] == "cap"]
        check("cap: past the cap — once in the events, every time to the Chair, and on the card with the real count",
              "used 4 agent runs, over its cap of 2" in e3 and cev.count("\trun.cap_passed\t") == 1 and "\tcap=2\n" in cev
              and len(citems) == 1 and "4 agent runs, over its limit of 2" in citems[0]["text"],
              (e3, cev[-300:], creading["attention"]))
        code, out, err = council(capped, "run", "events", "check")
        check("cap: the stream with the cap event still checks", code == 0, out + err)

        rows_before = read(run / "seats.tsv")
        refused = [council(repo, "correct", *w) for w in (
            ("hunt", "tokens=160360"), ("hunt", "tokens=74.3k", "evidence=transcript A L1679"),
            ("hunt", "tokens=160", "evidence=transcript A L1679"), ("nobody", "tokens=160360", "evidence=transcript A L1679"),
            ("hunt", "evidence=transcript A L1679"))]
        check("correct: no evidence, a rounded or implausible figure, an unknown seat or no figure at all are refused",
              all(c == 2 for c, _, _ in refused), [e.strip()[-100:] for _, _, e in refused])
        code, out, err = council(repo, "correct", "leach", "tokens=41234", "agents=1", "evidence=transcript B L42 uuid 1234abcd")
        check("correct: an exact, evidenced figure is laid over the row — seats.tsv is untouched, the trail kept",
              code == 0 and read(run / "seats.tsv") == rows_before and '"field":"tokens","from":"","to":41234' in read(run / "corrections.jsonl")
              and "seat.usage_corrected" in read(run / "events.tsv"), out + err)
        code, out, err = council(repo, "run", "close")
        state = read(run / "session-state.md")
        check("close: the cost line is a total only when every agent run's usage is known — here, with the correction, it is",
              "actual: ~4.8M tokens across 41 agent run(s)" in state, re.findall(r"^actual:.*$", state, re.MULTILINE))
        ledger = read(repo / ".council" / "ledger.tsv")
        check("ledger: rows carry checked figures (accounting 2), and the verifiers row stays even with an unknown cost",
              ledger.startswith("date\trun\tmode\tseat\traised\tkept\tcut\trefuted\ttokens\taccounting\n")
              and "\thunt\t" in ledger and "\t110000\t2" in ledger and "\tleach\t" in ledger and "\t41234\t2" in ledger, ledger)

        # A run from before this accounting, carried on by the new helper
        code, out, err = council(repo, "run", "open", "council-review", "--alongside")
        old = Path(out.strip())
        plan(old, ("hunt", "beck"))
        write(old / "seats.tsv", "slug\tstate\tagent\ttokens\tupdated\tnote\tagents\nhunt\tdone\tverifier\t160\t2026-09-20 18:07\t\t1\n")
        council(repo, "seat", "beck", "done", "agent=b1", "tokens=90334", "--run", old.name)
        lines = read(old / "seats.tsv").split("\n")
        check("older record: the header gains the new column, the old row keeps its old shape, the new row is exact",
              lines[0].endswith("\tagents\treported") and lines[1].count("\t") == 6 and lines[2].split("\t")[6:8] == ["1", "1"],
              lines)
        code, out, err = council(repo, "run", "close", "--run", old.name)
        check("older record: its cost line says tokens aren't reliably recorded, and the agent count is a lower bound",
              "tokens not reliably recorded (1 older row(s)) · at least 2 agent run(s)" in read(old / "session-state.md"),
              read(old / "session-state.md"))


        # --- the two readers: one helper-written run per basis, read by both (review finding 1) --------------
        agree = base / "agree"
        agree.mkdir()
        subprocess.run([GIT, "init", "-q"], cwd=agree, check=True)
        write(agree / ".council" / "council.config.md", "# Council config\n")
        cases = {}

        def fresh(name, seats):
            code, out, err = council(agree, "run", "open", "council-review", "--alongside")
            folder = Path(out.strip())
            plan(folder, tuple(seats) + ("verify-1",))
            cases[name] = folder
            return folder

        run_a = fresh("complete", ("a",))
        council(agree, "seat", "a", "done", "agent=a1", "tokens=40000", "--run", run_a.name)
        run_b = fresh("no-agent seat", ("a", "gone"))
        council(agree, "seat", "a", "done", "agent=a1", "tokens=40000", "--run", run_b.name)
        council(agree, "seat", "gone", "failed", "--run", run_b.name)
        council(agree, "seat", "gone", "done", "--run", run_b.name)
        run_decl = fresh("declared no agent", ("a", "chair-work"))
        council(agree, "seat", "a", "done", "agent=a1", "tokens=40000", "--run", run_decl.name)
        council(agree, "seat", "chair-work", "running", "--run", run_decl.name)
        council(agree, "seat", "chair-work", "done", "agents=0", "--run", run_decl.name)
        run_c = fresh("missing usage", ("a", "b"))
        council(agree, "seat", "a", "done", "agent=a1", "tokens=40000", "--run", run_c.name)
        council(agree, "seat", "b", "running", "agent=b1", "--run", run_c.name)
        council(agree, "seat", "b", "done", "--run", run_c.name)
        run_d = fresh("still working", ("a", "b"))
        council(agree, "seat", "a", "done", "agent=a1", "tokens=40000", "--run", run_d.name)
        council(agree, "seat", "b", "running", "agent=b1", "--run", run_d.name)
        run_e = fresh("agents-only correction", ("wf",))
        council(agree, "seat", "wf", "done", "agent=wf_1", "tokens=400000", "--run", run_e.name)
        council(agree, "correct", "wf", "agents=5", "evidence=workflow notification agent_count=5, L12", "--run", run_e.name)
        run_f = fresh("corrected zero", ("a", "chair-task"))
        council(agree, "seat", "a", "done", "agent=a1", "tokens=40000", "--run", run_f.name)
        council(agree, "seat", "chair-task", "running", "agent=x1", "--run", run_f.name)
        council(agree, "seat", "chair-task", "done", "--run", run_f.name)
        council(agree, "correct", "chair-task", "tokens=0", "agents=0", "evidence=transcript L9: the Chair built it; no Agent call", "--run", run_f.name)
        run_g = fresh("suspect", ("a", "b"))
        council(agree, "seat", "a", "done", "agent=a1", "tokens=40000", "--run", run_g.name)
        council(agree, "seat", "b", "done", "agent=b1", "tokens=50000", "--run", run_g.name)
        text = read(run_g / "seats.tsv").replace("\tb1\t50000\t", "\tb1\t160\t")          # a hand edit
        write(run_g / "seats.tsv", text)
        run_h = fresh("thirteen digits", ("a",))
        council(agree, "seat", "a", "done", "agent=a1", "tokens=40000", "--run", run_h.name)
        write(run_h / "seats.tsv", read(run_h / "seats.tsv").replace("\ta1\t40000\t", "\ta1\t1234567890123\t"))
        run_m = fresh("malformed agents cell", ("a", "b"))
        council(agree, "seat", "a", "done", "agent=a1", "tokens=40000", "--run", run_m.name)
        council(agree, "seat", "b", "running", "--run", run_m.name)
        council(agree, "seat", "b", "done", "--run", run_m.name)
        cells = [line.split("\t") for line in read(run_m / "seats.tsv").split("\n")]
        write(run_m / "seats.tsv", "\n".join("\t".join(c[:6] + ["-"] + c[7:]) if c[0] == "b" else "\t".join(c)
                                              for c in cells))
        run_i = fresh("older", ("a",))
        write(run_i / "seats.tsv", "slug\tstate\tagent\ttokens\tupdated\tnote\tagents\na\tdone\tverifier\t160\t2026-09-20 18:07\t\t1\n")
        mismatch = []
        for name, folder in cases.items():
            try:
                bash_seats, bash_run, py_seats, py_run = readers(agree, folder)
            except Exception as exc:  # noqa: BLE001 — a crash is a disagreement too
                mismatch.append((name, "crash", repr(exc)))
                continue
            if bash_seats != py_seats or bash_run != py_run:
                mismatch.append((name, bash_seats, py_seats, bash_run, py_run))
        check("readers: the helper (close line, ledger) and the snapshot (widget, tui, history) read every basis the same — "
              "per seat and for the run (found in review: a finished seat with no agent split them)",
              not mismatch and len(cases) == 11, mismatch)
        expect = {"complete": "complete", "no-agent seat": "partial", "declared no agent": "complete", "missing usage": "partial",
                  "malformed agents cell": "partial",
                  "still working": "running", "agents-only correction": "partial", "corrected zero": "complete",
                  "suspect": "suspect", "thirteen digits": "suspect", "older": "legacy"}
        got = {name: cockpit.snapshot(folder, None, 8)["usage"]["tokens"]["basis"] for name, folder in cases.items()}
        check("readers: each case lands on the basis the accounting reference names — a seat with no agent on record is "
              "unknown (partial), never a zero; agents=0 or a corrected 0 is a real 0; an agents-only correction is partial "
              "(the ruling); 160 and 13 digits are suspect",
              got == expect, got)
        ledger = sourced(agree, 'ledger_tokens "{}"'.format(str(run_e).replace("\\", "/")))
        check("ledger: a seat every reader calls partial gets no price", ledger.strip() == "wf\t-", ledger)
        try:
            status.interpret(cockpit.snapshot(run_h, None, 8), NOW)
            crashed = False
        except Exception:  # noqa: BLE001
            crashed = True
        check("status: a 13-digit token cell reads as suspect, never a crash (review finding 3)", not crashed)
        display_cases = [(2500, "3k"), (994999, "995k"), (995000, "1M"), (1049999, "1M"),
                         (1050000, "1.1M"), (26430386, "26.4M")]
        display_mismatch = []
        for tokens, expected in display_cases:
            bash = sourced(agree, "usage_token_text {}".format(tokens)).strip()
            close = sourced(agree, 'usage_words "complete 1 1 {} 0 1 0 0"'.format(tokens)).strip()
            snapshot = {"usage": {"tokens": {"basis": "complete", "total": tokens},
                                  "agents": {"total": 1, "at_least": 1}}}
            card = status.tokens_text(tokens)
            status_line = status.usage_of(snapshot)["text"]
            tui = cockpit.k(tokens)
            history_line = history.k(tokens)
            display_dir = agree / "display"
            write(display_dir / "seats.tsv", "slug\tstate\tagent\ttokens\tupdated\tnote\tagents\treported\n"
                  "a\tdone\ta1\t{}\t-\t-\t1\t1\n".format(tokens))
            progress = sourced(agree, 'progress_line "{}"'.format(str(display_dir).replace("\\", "/")))
            progress_amount = "~{} tokens so far".format(expected)
            actual = (bash, card, "{} tokens across 1 agent run".format(card), tui, history_line,
                      close, progress_amount if progress_amount in progress else progress)
            wanted = (expected, expected, "{} tokens across 1 agent run".format(expected), expected,
                      "~" + expected, "~" + expected + " tokens across 1 agent run(s)",
                      "~" + expected + " tokens so far")
            if actual != wanted or expected not in status_line:
                display_mismatch.append((tokens, actual, wanted, status_line))
        check("display: progress, close, card, TUI and history use half-up rounding and the same M threshold",
              not display_mismatch, display_mismatch)

        # --- corrections are normalised and bounded, so both readers read the same line (review finding 2) ---
        run_j = fresh("corrections", ("a",))
        council(agree, "seat", "a", "done", "agent=a1", "tokens=40000", "--run", run_j.name)
        refused = [council(agree, "correct", "a", *w, "--run", run_j.name)[0] for w in (
            ("tokens=1234567890123", "evidence=transcript L1 uuid 1"),
            ("agents=1001", "evidence=transcript L1 uuid 1"),
            ("tokens=41234", "evidence=" + " " * 20),
            ("tokens=41234", "evidence=" + "\x7f" * 20))]
        council(agree, "correct", "a", "tokens=0041234", "evidence=transcript B L42 uuid 1234abcd", "--run", run_j.name)
        council(agree, "correct", "a", "tokens=41300", "evidence=transcript B L77: the later report", "--run", run_j.name)
        lines = read(run_j / "corrections.jsonl").splitlines()
        awk_view = sourced(agree, 'corrections_tsv "{}"'.format(str(run_j).replace("\\", "/"))).split()
        py_view = cockpit.corrections_of(run_j)
        check("correct: 13 digits, over 1,000 agent runs and evidence of spaces or control marks are refused; "
              "leading zeros are written as a plain number",
              refused == [2, 2, 2, 2] and len(lines) == 2 and '"to":41234,' in lines[0], (refused, lines))
        check("correct: the latest correction of a field counts, keeps the value it replaced, and both readers "
              "see it (review finding 5)",
              awk_view == ["a", "tokens", "41300", "0"] and py_view[("a", "tokens")]["to"] == 41300
              and '"from":"40000"' in lines[1], (awk_view, py_view, lines))

        # --- an agent run the record missed, added from evidence ---------------------------------------------------
        run_add = fresh("added", ("a",))
        council(agree, "seat", "a", "done", "agent=a1", "tokens=40000", "--run", run_add.name)
        refused_add = [council(agree, "correct", *w, "--run", run_add.name)[0] for w in (
            ("a", "tokens=1000", "agents=1", "unrecorded=yes", "evidence=transcript L3 an Agent call"),
            ("survey", "tokens=190883", "unrecorded=yes", "evidence=transcript L3 an Agent call"))]
        council(agree, "correct", "survey", "tokens=190883", "agents=1", "unrecorded=yes",
                "evidence=transcript A L3475 uuid 685ff6a5 subagent_tokens=190883", "--run", run_add.name)
        rows_after = read(run_add / "seats.tsv")
        bash_seats, bash_run, py_seats, py_run = readers(agree, run_add)
        check("correct unrecorded=yes: an agent run that never got a seat is added from evidence — seats.tsv untouched, "
              "both readers count it, an existing seat or a missing figure refused",
              refused_add == [2, 2] and "survey" not in rows_after and bash_seats == py_seats
              and bash_run == py_run == ("complete", 2, 230883) and bash_seats.get("survey") == ("corrected", 1, 190883),
              (refused_add, bash_seats, py_seats, bash_run, py_run))

        overwrite = council(agree, "seat", "survey", "done", "agent=z1", "tokens=30000", "--run", run_add.name)[0]
        twice = council(agree, "correct", "survey", "tokens=25000", "agents=1", "unrecorded=yes",
                        "evidence=transcript A L9999 uuid 1 another run", "--run", run_add.name)[0]
        zero_cost = council(agree, "correct", "q", "tokens=0", "agents=1", "unrecorded=yes",
                            "evidence=transcript A L42 an Agent call, usage not shown", "--run", run_add.name)[0]
        council(agree, "correct", "q", "agents=1", "unrecorded=yes", "evidence=transcript A L42 an Agent call, usage not shown",
                "--run", run_add.name)
        bash_seats, bash_run, py_seats, py_run = readers(agree, run_add)
        check("added runs: an added slug can't later be recorded or added again, a real agent run can't cost 0, and an "
              "added run with no figure is missing usage in both readers (second real run's review)",
              (overwrite, twice, zero_cost) == (2, 2, 2) and bash_seats == py_seats and bash_run == py_run
              and bash_seats.get("q") == ("missing", 1, None) and bash_run[0] == "partial",
              ((overwrite, twice, zero_cost), bash_seats, py_seats, bash_run, py_run))
        run_z = fresh("agents zero", ("c",))
        council(agree, "seat", "c", "failed", "agent=c1", "--run", run_z.name)
        declared = council(agree, "seat", "c", "done", "agents=0", "--run", run_z.name)
        check("seat: agents=0 is refused once an agent was dispatched for the seat — it can't erase that run",
              declared[0] == 2 and "agent id is on record" in declared[2], declared)
        run_h2 = fresh("hand-written add", ("a",))
        council(agree, "seat", "a", "done", "agent=a1", "tokens=40000", "--run", run_h2.name)
        write(run_h2 / "corrections.jsonl", "".join(json.dumps(c) + "\n" for c in (
            {"schema": 1, "seat": "s2", "field": "tokens", "from": "", "to": 500, "added": True, "evidence": "hand written A L1"},
            {"schema": 1, "seat": "s2", "field": "agents", "from": "", "to": 1, "added": True, "evidence": "hand written A L1"})))
        bash_seats, bash_run, py_seats, py_run = readers(agree, run_h2)
        check("added runs: a hand-written line (spaced JSON) is read by both readers, and a tiny figure is suspect in both",
              bash_seats == py_seats and bash_run == py_run and bash_seats.get("s2", ("",))[0] == "suspect",
              (bash_seats, py_seats, bash_run, py_run))
        spaced = [council(agree, "seat", slug, "done", "agent=" + slug + "1", "tokens=" + value, "--run", run_add.name)[0]
                  for slug, value in (("t1", "74304 Tokens"), ("t2", "74304 tokens "))]
        check("seat: an exact figure followed by 'Tokens' or a trailing space is accepted, not mistaken for a rounded one",
              spaced == [0, 0] and seat_row(run_add, "t1")[3:4] == ["74304"] and seat_row(run_add, "t2")[3:4] == ["74304"],
              (spaced, seat_row(run_add, "t1"), seat_row(run_add, "t2")))

        # --- the usage trail's own rules, focused (review finding 6) ---------------------------------------------
        run_k = fresh("trail", ("s", "n"))
        council(agree, "seat", "s", "running", "agent=s1", "--run", run_k.name)
        council(agree, "seat", "s", "done", "tokens=20000", "--run", run_k.name)
        council(agree, "seat", "s", "done", "tokens=6000", "--run", run_k.name)
        council(agree, "seat", "n", "done", "tokens=5000", "--run", run_k.name)
        council(agree, "seat", "n", "done", "tokens=5000", "--run", run_k.name)
        check("seat: a smaller later figure from the same agent is a count of its own and is added — still one agent run",
              seat_row(run_k, "s")[3:4] == ["26000"] and seat_row(run_k, "s")[6:8] == ["1", "1"], seat_row(run_k, "s"))
        check("seat: a report with no agent id stands alone, so the same one twice counts twice — record the id at dispatch",
              seat_row(run_k, "n")[3:4] == ["10000"] and seat_row(run_k, "n")[6:8] == ["2", "2"], seat_row(run_k, "n"))
        code, _, _ = council(agree, "seat", "s", "done", "tokens=1000", "--run", run_k.name)
        check("seat: exactly 1,000 tokens is accepted — the floor is 'under 1,000' (review finding 12)", code == 0)
        with open(run_k / "usage.tsv", "a", encoding="utf-8", newline="\n") as trail:
            trail.write("2026-09-27T12:00:00Z\tn\tn9\tfinished\t1\t12abc\n")
        council(agree, "seat", "n", "done", "--run", run_k.name)
        check("seat: a usage.tsv cell that is not a count (a hand edit) is never read as one (review finding 8)",
              seat_row(run_k, "n")[3:4] == ["10000"] and seat_row(run_k, "n")[6:8] == ["2", "2"], seat_row(run_k, "n"))

        # --- one reading of the waiting: key (review finding 9) ---------------------------------------------------
        run_l = fresh("waiting", ("a",))
        text = read(run_l / "session-state.md").replace("## Decisions so far", "waiting:   # only a note\n## Decisions so far")
        write(run_l / "session-state.md", text + "waiting: this line is below the heading\n")
        helper_view = sourced(agree, 'state_field waiting "{}/session-state.md"'.format(str(run_l).replace("\\", "/"))).strip()
        check("state: the helper and the snapshot read the waiting: header the same way",
              helper_view == cockpit.header(run_l).get("waiting", "") == "# only a note",
              (helper_view, cockpit.header(run_l).get("waiting")))

        # --- a pasted command runs nothing (review finding 10) ---------------------------------------------------
        quoted = sourced(agree, "sh_quote \"a'b\\$c\\`d\"; echo; ps_quote \"a'b\\$c\\`d\"").splitlines()
        check("status: the terminal-view command quotes paths literally for bash and PowerShell",
              quoted == ["'a'\\''b$c`d'", "'a''b$c`d'"], quoted)

        # --- failing, recovery and blocked, driven through the helper (review finding 7) ---------------------------
        code, out, err = council(agree, "run", "open", "council-implement", "--alongside")
        build = Path(out.strip())
        plan(build, ("verify-1",))
        states = []
        for attempt in range(3):
            council(agree, "gate", "tests", "--run", build.name, "--", "false")
            if attempt == 0:
                states.append(json.loads(council(agree, "status", "--json", "--run", build.name)[1])["state"]["key"])
            council(agree, "repair", "record", "T1", "tests", "--run", build.name)
            states.append(json.loads(council(agree, "status", "--json", "--run", build.name)[1])["state"]["key"])
        check("status through the helper: a failing check, then recovery attempts 1 and 2, then blocked at the limit",
              states == ["failing", "recovering", "recovering", "blocked"], states)

        # Pausing while an agent still works: its usage is pending, not missing; resuming drops the stale cost
        code, out, err = council(repo, "run", "open", "council-review", "--alongside")
        paused = Path(out.strip())
        plan(paused, ("hunt", "verify-1"))
        council(repo, "seat", "hunt", "running", "agent=a1", "--run", paused.name)
        council(repo, "run", "close", "--status", "paused", "--run", paused.name)
        state = read(paused / "session-state.md")
        check("close: a run paused while an agent works says it is still working, not that its usage is missing (found on a real run)",
              "still working" in state and "without a usage report" not in state, re.findall(r"^actual:.*$", state, re.MULTILINE))
        council(repo, "run", "resume", "--run", paused.name)
        check("resume: the closing cost line goes with the closing time — no stale cost on a live run",
              "\nactual:" not in read(paused / "session-state.md") and "\nclosed:" not in read(paused / "session-state.md"),
              read(paused / "session-state.md"))

with tempfile.TemporaryDirectory(prefix="council-stale-status-") as temporary:
    stale_run = Path(temporary)
    write(stale_run / "session-state.md", "status: in-progress\nmode: council-review\nphase: challenge\n")
    write(stale_run / "claims.jsonl", '{"id":"1","source":"synthesis.md:3","verdict":"CONFIRMED",'
          '"verification":[{"ref":"verify-1-a.md:4","verdict":"CONFIRMED"}]}\n')
    index_at = (stale_run / "claims.jsonl").stat().st_mtime
    write(stale_run / "verify-1-a.md", "# Verification\n")
    for source in ("synthesis.md", "verify-1-a.md"):
        write(stale_run / source, "# Source\n")
        os.utime(stale_run / source, (index_at + 5, index_at + 5))
        before = fingerprint(stale_run)
        snap = cockpit.snapshot(stale_run)
        reading = status.interpret(snap, now=NOW)
        labels = [item["label"] for item in reading["evidence"]]
        check("status: newer " + source + " hides stale verdicts and labels the index",
              snap["claims"]["stale"] and not snap["claims"]["by_verdict"] and
              "Claims index out of date" in labels, labels)
        check("status: stale " + source + " read writes nothing", before == fingerprint(stale_run))
        os.utime(stale_run / source, (index_at - 5, index_at - 5))
    check("status: a current index keeps its verdicts", cockpit.claims_of(stale_run)["by_verdict"] == {"CONFIRMED": 1})
    (stale_run / "verify-1-a.md").unlink()
    deleted_verifier = cockpit.claims_of(stale_run)
    check("status: a deleted verifier referenced by the index marks claims stale",
          deleted_verifier["stale"] and not deleted_verifier["by_verdict"], deleted_verifier)
    (stale_run / "verify-1-a.md").write_text("# Verification\n", encoding="utf-8")
    (stale_run / "synthesis.md").unlink()
    deleted_synthesis = cockpit.claims_of(stale_run)
    check("status: a deleted synthesis referenced by the index marks claims stale",
          deleted_synthesis["stale"] and not deleted_synthesis["by_verdict"], deleted_synthesis)
    (stale_run / "claims.jsonl").unlink()
    check("status: missing claim index is visible", cockpit.claims_of(stale_run)["stale"])

passed = sum(good for _, good, _ in checks)
for name, good, detail in checks:
    print("[{}] {}".format("PASS" if good else "FAIL", name))
    if not good:
        print("       " + str(detail)[:900].replace("\n", "\n       "))
print("\n{}/{} checks passed".format(passed, len(checks)))
sys.exit(0 if passed == len(checks) else 1)
