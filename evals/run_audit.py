#!/usr/bin/env python3
"""Checks for `council run audit` (scripts/audit.py): a finished run read against what the method promises.

Every other suite tests the helper; this one tests the check that reads what a Chair actually did. Two
runs are built here from nothing (no real project's content):
- one with the pattern of the first real run (a review, 2026-09-30): a stage never entered, the
  verifier written down only when it finished, two copies of the checks at once, no record of the
  Chair's own seat — and a session transcript where the helper goes through a shell variable, its
  output is cut by `| tail`, no status card follows the first dispatch or the close, and a refused
  call is never tried again. Its records are written as the 0.17.0 helper wrote them: today's helper
  refuses a second gate call, so it can no longer make that pattern itself.
- one clean run driven through the real helper, and the transcript of a Chair who does what the
  method says. It must pass every item.
Reading must write nothing, in the runs, the council homes or the transcripts. It also checks the
paid suite's graders for `council status` and `council run close` on synthetic traces, and that a
suite which checked nothing never passes: with no bash or git on PATH the suites that need them exit
3 unless given --allow-skip, and run_all.py fails a job that reports no checks. About a minute.

    python evals/run_audit.py
    python evals/run_audit.py --allow-skip   # exit 0 when bash or git is missing (nothing is checked)
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
from datetime import datetime, timedelta, timezone

sys.dont_write_bytecode = True                      # importing the grader reader leaves no __pycache__
ROOT = Path(__file__).resolve().parent.parent
BASH = os.environ.get("COUNCIL_EVAL_BASH") or shutil.which("bash")
GIT = shutil.which("git")
AUDIT = ROOT / "scripts" / "audit.py"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
checks = []


def check(name, good, detail=""):
    checks.append((name, bool(good), detail))


def council(repo, *args, timeout=120):
    env = os.environ.copy()
    for var in ("COUNCIL_RUN", "CLAUDE_CODE_SESSION_ID", "COUNCIL_ASCII"):
        env.pop(var, None)
    env.update(GIT_AUTHOR_NAME="eval", GIT_AUTHOR_EMAIL="eval@example.invalid",
               GIT_COMMITTER_NAME="eval", GIT_COMMITTER_EMAIL="eval@example.invalid")
    if os.environ.get("COUNCIL_EVAL_BASH"):
        env["PATH"] = str(Path(BASH).parent) + os.pathsep + env.get("PATH", "")
    words = [BASH, str(ROOT / "bin" / "council"), *args]
    if os.name == "nt":
        words = " ".join('"{}"'.format(word.replace('"', '\\"')) for word in words)
    try:
        result = subprocess.run(words, cwd=str(repo), capture_output=True, text=True, encoding="utf-8",
                                errors="replace", env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "", "council {}: still running after {} s".format(" ".join(args), timeout)
    return result.returncode, result.stdout, result.stderr


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def fingerprint(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


def item(out, label):
    """The verdict the audit gave one item ("pass", "warn", "FAIL"), and its words."""
    match = re.search(r"^  (pass|warn|FAIL)\s+%s: (.*)$" % re.escape(label), out, re.MULTILINE)
    return (match.group(1), match.group(2)) if match else (None, "")


def utc(text):
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


class Transcript:
    """A Claude Code session transcript, one JSON object per line, as the main thread writes it."""

    def __init__(self, session, start):
        self.session, self.t, self.lines, self.n = session, start, [], 0

    def _line(self, kind, content, step):
        self.t += timedelta(seconds=step)
        self.lines.append({"type": kind, "timestamp": self.t.strftime("%Y-%m-%dT%H:%M:%S.123Z"), "isSidechain": False,
                           "sessionId": self.session, "message": {"role": kind, "content": content}})

    def at(self, when):
        self.t = when
        return self

    def prompt(self, text, step=1):
        self._line("user", text, step)

    def text(self, words, step=1):
        self._line("assistant", [{"type": "text", "text": words}], step)

    def call(self, name, given, output="", step=1, error=False):
        self.n += 1
        ident = "toolu_%03d" % self.n
        self._line("assistant", [{"type": "tool_use", "id": ident, "name": name, "input": given}], step)
        self._line("user", [{"type": "tool_result", "tool_use_id": ident, "content": output, "is_error": error}], 0)

    def bash(self, command, output="", step=1, background=False):
        given = {"command": command, "description": "x"}
        if background:
            given["run_in_background"] = True
        self.call("Bash", given, output, step)

    def subagent(self, command):
        """A subagent's own call, in the same file: never the Chair's."""
        self.lines.append({"type": "assistant", "timestamp": self.lines[-1]["timestamp"], "isSidechain": True,
                           "sessionId": self.session, "message": {"role": "assistant", "content": [
                               {"type": "tool_use", "id": "sub%d" % len(self.lines), "name": "Bash",
                                "input": {"command": command}}]}})

    def save(self, path):
        write(path, "".join(json.dumps(line) + "\n" for line in self.lines))


# --- the first real run's pattern, written as the 0.17.0 helper wrote it ---------------------------------------
RUN1 = "2026-09-30-131416-review"
RUN1_EVENTS = [
    ("2026-09-30T10:14:16Z", "run.opened", "run", "council-review", "phase=convene"),
    ("2026-09-30T10:14:34Z", "run.phase_changed", "run", "prepare", "from=convene"),
    ("2026-09-30T10:19:21Z", "verification.finished", "run", "passed", "items=4;broken=0;other=0"),
    ("2026-09-30T10:19:23Z", "run.phase_changed", "run", "challenge", "from=prepare"),
    ("2026-09-30T10:23:13Z", "seat.updated", "verify-1", "done", "tokens=94152;agent_runs=1;reported=1"),
    ("2026-09-30T10:25:14Z", "gate.finished", "tests", "failed", "exit=127;seconds=57;empty=0"),     # the second copy
    ("2026-09-30T10:25:20Z", "gate.finished", "lint", "passed", "exit=0;seconds=4;empty=0"),
    ("2026-09-30T10:36:23Z", "gate.finished", "tests", "passed", "exit=0;seconds=1290;empty=0"),     # the first, from 10:14:53
    ("2026-09-30T10:36:29Z", "gate.finished", "lint", "passed", "exit=0;seconds=6;empty=0"),
    ("2026-09-30T10:39:22Z", "run.phase_changed", "run", "deliver", "from=challenge"),
    ("2026-09-30T10:39:23Z", "run.phase_changed", "run", "learn", "from=deliver"),
    ("2026-09-30T10:39:40Z", "run.status_changed", "run", "complete", "from=in-progress"),
    ("2026-09-30T10:39:41Z", "run.closed", "run", "complete", "agent_runs=1;reported=1;tokens=94152;basis=complete"),
]
PLAN1 = [("schema", "plan", "version", "1"), ("run", "run", "id", RUN1), ("run", "run", "mode", "council-review"),
         ("run", "run", "size", "squad"), ("assessment", "run", "risk", "low"), ("assessment", "run", "complexity", "low"),
         ("assessment", "run", "uncertainty", "medium"), ("budget", "run", "agent-cap", "10"),
         ("budget", "run", "estimated-tokens", "120000"), ("verification", "run", "level", "independent"),
         ("seat", "chair", "disposition", "selected"), ("seat", "chair", "role", "chair"), ("context", "chair", "level", "full"),
         ("budget", "chair", "tool-calls", "40"), ("seat", "verify-1", "disposition", "selected"),
         ("seat", "verify-1", "role", "verifier"), ("context", "verify-1", "level", "focused"),
         ("budget", "verify-1", "tool-calls", "40"), ("seat", "structure", "disposition", "skipped"),
         ("seat", "structure", "role", "worker"), ("seat", "tests", "disposition", "skipped"), ("seat", "tests", "role", "worker")]


def plan_text(rows):
    return "# Small Council run plan v1.\nkind\tid\tfield\tvalue\treason\n" + "".join(
        "%s\t%s\t%s\t%s\tbecause\n" % row for row in rows)


def build_run1(base):
    project = base / "run1-project"
    run = project / ".council" / "runs" / RUN1
    write(run / "session-state.md", "\n".join([
        "status: complete", "mode: council-review", "phase: learn", "updated: 2026-09-30 13:39",
        "opened: 2026-09-30 13:14:16", "code-root: %s" % project.as_posix(), "session: session-run-1",
        "plan-schema: 1", "events-schema: 1", "size: squad — Chair inline + 1 verifier, est. ~120k tokens",
        "deliverable: .council/reviews/2026-09-30-sample-review.md", "next: size the run and ask for the go-ahead",
        "ask-saved: 2026-09-30 13:25", "closed: 2026-09-30 13:39:39",
        "actual: ~94k tokens across 1 agent run(s) · estimated ~120k", "## Decisions so far", ""]))
    write(run / "events.tsv", "schema\tseq\tat\ttype\tsubject\tvalue\tdetail\n" + "".join(
        "1\t%d\t%s\n" % (n, "\t".join(row)) for n, row in enumerate(RUN1_EVENTS, 1)))
    write(run / "run-plan.tsv", plan_text(PLAN1))
    write(run / "seats.tsv", "slug\tstate\tagent\ttokens\tupdated\tnote\tagents\treported\n"
                             "verify-1\tdone\ta4c08e8e07813e7ee\t94152\t2026-09-30 13:23\t\t1\t1\n")
    write(run / "usage.tsv", "at\tseat\tagent\tkind\truns\ttokens\n"
                             "2026-09-30T10:23:13Z\tverify-1\ta4c08e8e07813e7ee\tdispatched\t\t\n"
                             "2026-09-30T10:23:13Z\tverify-1\ta4c08e8e07813e7ee\tfinished\t1\t94152\n")
    write(run / "synthesis.md", "# Synthesis\n## Kept\n"
          "1 · P3 · Principle 4 · notes.md:5 · A rule names a setting that was deleted · state: OBSERVED · from: chair\n"
          "## Cut\nC1 · P3 · Principle 1 · notes.md:9 · A header will go stale · why: not yet · state: INFERRED · from: chair\n")
    write(run / "verify-1.md", "# Verification\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
                               "| 1 | A rule names a deleted setting | CONFIRMED | notes.md:5 still names it |\n")
    write(run / "claims.jsonl", "".join(json.dumps(claim) + "\n" for claim in (
        {"id": "1", "disposition": "kept", "verdict": "CONFIRMED", "citation": "notes.md:5"},
        {"id": "2", "disposition": "kept", "verdict": "CONFIRMED", "citation": "notes.md:7"},
        {"id": "C1", "disposition": "cut", "verdict": "UNVERIFIED", "citation": "notes.md:9"})))
    later = (run / "claims.jsonl").stat().st_mtime
    for name in ("synthesis.md", "verify-1.md"):
        os.utime(str(run / name), (later - 60, later - 60))
    write(project / ".council" / "reviews" / "2026-09-30-sample-review.md", "# Review\n")
    return project, run


def transcript_run1(path, project, run):
    council_path = "/home/user/.claude/plugins/small-council/bin/council"
    use = 'C="bash %s"; ' % council_path
    log = Transcript("session-run-1", utc("2026-09-30T10:13:52Z"))
    log.prompt("<command-message>council-review</command-message>\n<command-args>the last commit</command-args>")
    log.at(utc("2026-09-30T10:14:07Z")).bash(use + '$C run status; $C route recommend --task "review the last commit" 2>&1 | head -30',
                                            "kind\tid\tfield\tvalue\treason")
    log.at(utc("2026-09-30T10:14:14Z")).bash(use + "$C run open council-review",
                                            "council: save the user's request word for word in %s/ask.md before anything else\n%s"
                                            % (run.as_posix(), run.as_posix()))
    log.at(utc("2026-09-30T10:14:39Z")).bash('bash %s gate --all --at grounding; echo "exit=$?"' % council_path,
                                            "Command running in background with ID: b1.", background=True)
    log.at(utc("2026-09-30T10:20:04Z")).call("Agent", {"subagent_type": "small-council:council-verifier",
                                                       "description": "Verify review claims blind", "prompt": "Check each claim."},
                                            "The verifier's report: 2 confirmed.")
    log.at(utc("2026-09-30T10:23:11Z")).bash(use + "$C seat verify-1 done tokens=94152 agent=a4c08e8e07813e7ee 2>&1 | tail -1",
                                            "seats: 1 of 1 done · ~94k tokens so far")
    log.at(utc("2026-09-30T10:24:13Z")).bash(use + "$C gate --all --at grounding >/dev/null 2>&1", "")
    log.at(utc("2026-09-30T10:39:19Z")).bash(
        use + "$C state phase=deliver | tail -1; $C state phase=learn | tail -1; $C status 2>&1 | tail -12",
        "state: phase learn · in-progress · %s\nProject · Review · %s\n"
        "Status: A check is failing. Stage: Recording lessons (stage 10 of 10).\nSpend: spent 94k of estimated 120k" % (RUN1, RUN1))
    log.text("The gates are recorded; spent 94k of an estimated 120k.")
    log.at(utc("2026-09-30T10:39:37Z")).bash(
        use + "$C run close --status complete 2>&1 | tail -4; $C status 2>&1 | sed -n '1,9p'",
        "closed %s — complete · ~94k tokens across 1 agent run(s) · estimated ~120k\n"
        "council: no open run on this working tree — open one with: council run open <mode>   (or pass --run <folder>)" % RUN1)
    log.at(utc("2026-09-30T10:39:55Z")).text("## Council Review — 2 findings")
    log.at(utc("2026-09-30T10:58:32Z")).prompt("yes to both, fix all four")
    # After the user's next message: outside the run's window, so this card is not the closing card.
    log.bash("council status --widget --run %s" % RUN1, "<div>card</div>")
    log.call("mcp__visualize__show_widget", {"widget_code": "<div>card</div>"}, "shown")
    log.save(path)


def transcript_resumed(path, start):
    """A second session that carries run 1 on: it sends one more verifier and shows no card."""
    log = Transcript("session-two", start)
    log.prompt("carry on with the review")
    log.bash("council run resume --run %s" % RUN1, "resumed %s — in progress · phase challenge" % RUN1)
    log.call("Agent", {"subagent_type": "small-council:council-verifier", "description": "Verify", "prompt": "claims"},
             "Async agent launched. agentId: v2")
    log.bash("council seat verify-2 running agent=v2", "seats: 1 of 2 done · still working: verify-2", step=60)
    log.save(path)


# --- a clean run, through the real helper ------------------------------------------------------------------------
PLAN2 = [("schema", "plan", "version", "1"), ("run", "run", "size", "squad"), ("run", "run", "mode", "council-review"),
         ("assessment", "run", "risk", "medium"), ("assessment", "run", "complexity", "medium"),
         ("assessment", "run", "uncertainty", "low"), ("budget", "run", "agent-cap", "10"),
         ("budget", "run", "estimated-tokens", "260000"), ("verification", "run", "level", "independent"),
         ("seat", "chair", "disposition", "selected"), ("seat", "chair", "role", "chair"), ("context", "chair", "level", "full"),
         ("budget", "chair", "tool-calls", "80"), ("seat", "hunt", "disposition", "selected"), ("seat", "hunt", "role", "worker"),
         ("context", "hunt", "level", "focused"), ("budget", "hunt", "tool-calls", "40"),
         ("seat", "verify-1", "disposition", "selected"), ("seat", "verify-1", "role", "verifier"),
         ("context", "verify-1", "level", "focused"), ("budget", "verify-1", "tool-calls", "30"),
         ("seat", "nygard", "disposition", "skipped"), ("seat", "nygard", "role", "worker")]


def build_clean(base):
    repo = base / "clean-project"
    repo.mkdir()
    subprocess.run([GIT, "init", "-q"], cwd=str(repo), check=True)
    write(repo / ".council" / "council.config.md", "# Council config\n")
    steps = []

    def step(*args):
        code, out, err = council(repo, *args)
        steps.append((args, code, err.strip()[:200]))
        return code, out, err

    code, out, err = step("run", "open", "council-review")
    run = Path(out.strip().splitlines()[-1]) if code == 0 and out.strip() else None
    if run is None:
        return repo, None, steps
    write(run / "run-plan.tsv", plan_text([(k, i, f, v) for k, i, f, v in PLAN2] + [("run", "run", "id", run.name)]))
    step("run", "plan", "check")
    step("state", "phase=prepare")
    step("gate", "tests", "--", "true")
    for phase in ("assign", "brief", "work"):
        step("state", "phase=" + phase)
    step("seat", "hunt", "running", "agent=a1b2c3d4e5f6a7b8c")
    step("seat", "hunt", "done", "tokens=58000")
    write(run / "seats" / "hunt.md", "# Hunt\n## Index\n1 · P1 · Principle 1 · src/auth.py:4 · Expiry skipped\n")
    step("state", "phase=collect")
    step("state", "phase=judge")
    write(run / "synthesis.md", "# Synthesis\n## Kept\n"
          "1 · P1 · Principle 1 · src/auth.py:4 · Expiry skipped · state: OBSERVED · from: hunt#1\n")
    step("state", "phase=challenge")
    step("seat", "verify-1", "running", "agent=v9f8e7d6c5b4a3f2e")
    write(run / "verify-1.md", "# Verification\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
                               "| 1 | Expiry skipped | CONFIRMED | src/auth.py:4 never reads the expiry |\n")
    step("seat", "verify-1", "done", "tokens=40000")
    step("evidence", "build")
    step("state", "phase=deliver")
    write(repo / ".council" / "reviews" / "2026-10-01-clean.md", "# Review\n")
    step("state", "deliverable=.council/reviews/2026-10-01-clean.md")
    step("seat", "chair", "done", "agents=0")
    step("state", "phase=learn")
    step("run", "close")
    return repo, run, steps


def transcript_clean(path, run):
    events = [line.split("\t") for line in (run / "events.tsv").read_text(encoding="utf-8").splitlines()[1:]]
    opened, closed = utc(events[0][2]), utc(events[-1][2])
    log = Transcript("session-clean", opened - timedelta(seconds=30))
    log.prompt("/council-review the change on this branch")
    log.at(opened - timedelta(seconds=2)).bash("council run open council-review", str(run))
    log.bash("council gate tests -- true", "gate tests: pass (exit 0, 0s)")
    log.call("Agent", {"subagent_type": "small-council:council-worker", "description": "Hunt", "prompt": "orders",
                       "run_in_background": True}, "Async agent launched. agentId: a1b2c3d4e5f6a7b8c")
    log.bash("council seat hunt running agent=a1b2c3d4e5f6a7b8c",
             "seats: 0 of 3 done · still working: hunt\ncouncil: first dispatch of this run — show the user its "
             "status now, once: hand the output of `council status --widget` to a show_widget tool, else relay `council status`")
    log.bash("council status --widget", "<div>status card</div>")
    log.call("mcp__visualize__show_widget", {"widget_code": "<div>status card</div>"}, "shown")
    log.bash("council seat hunt done tokens=58k",
             "council: tokens=58k is a rounded figure — pass the exact count the usage report gives (like 159812)")
    log.bash("council seat hunt done tokens=58000", "seats: 1 of 3 done · ~58k tokens so far")
    log.call("Agent", {"subagent_type": "small-council:council-verifier", "description": "Verify", "prompt": "claims",
                       "run_in_background": True}, "Async agent launched. agentId: v9f8e7d6c5b4a3f2e")
    log.bash("council seat verify-1 running agent=v9f8e7d6c5b4a3f2e", "seats: 1 of 3 done · still working: verify-1")
    log.subagent('C="bash /x/bin/council"; $C seat verify-1 done | tail -1')
    log.bash("council seat verify-1 done tokens=40000", "seats: 2 of 3 done · ~98k tokens so far")
    log.bash("council evidence build", "evidence: 1 claim(s) indexed")
    log.at(closed - timedelta(seconds=1)).bash("council run close", "closed %s — complete\ncouncil: run closed — show "
                                                "the user its closing card now, once" % run.name)
    log.bash("council status --run %s" % run.name, "Project · Review · %s\nStatus: Done. The review is finished.\n"
                                                    "Next: nothing" % run.name)
    log.text("**Status:** Done. The review is finished. One finding, confirmed.")
    log.bash("council status --line --run %s" % run.name, "Review done: 1 finding")
    log.at(closed + timedelta(minutes=5)).prompt("thanks")
    log.save(path)


def transcript_refused_close(path, run, card_after_real):
    """Another run's close and this run's refused close, each followed by a card, then this run's real close —
    with a card after it or not. A refused call is written as a real transcript writes a failed Bash call:
    is_error, its output starting "Exit code 2"."""
    events = [line.split("\t") for line in (run / "events.tsv").read_text(encoding="utf-8").splitlines()[1:]]
    opened, closed = utc(events[0][2]), utc(events[-1][2])
    other = "2026-10-01-190000-init"
    log = Transcript("session-clean", opened - timedelta(seconds=30))
    log.prompt("/council-review the change on this branch")
    log.at(opened - timedelta(seconds=2)).bash("council run open council-review", str(run))
    log.at(closed - timedelta(seconds=40)).bash("council run close --run %s" % other, "closed %s — complete" % other)
    log.bash("council status --run %s" % other, "Project · Setup · %s\nStatus: Done. Setup is finished." % other)
    log.text("**Status:** Done. Setup is finished.")
    log.call("Bash", {"command": "council run close", "description": "Close the run"},
             "Exit code 2\ncouncil: the event stream is torn (its last line is cut off) — mend it: council run events "
             "repair --run %s" % run.name, error=True)
    log.bash("council status", "Project · Review · %s\nStatus: Working. Its event stream needs a repair." % run.name)
    log.text("**Status:** Working. Its event stream needs a repair.")
    log.at(closed - timedelta(seconds=1)).bash("council run close", "closed %s — complete" % run.name)
    if card_after_real:
        log.bash("council status --run %s" % run.name, "Project · Review · %s\nStatus: Done. The review is finished." % run.name)
        log.text("**Status:** Done. The review is finished.")
    log.at(closed + timedelta(minutes=5)).prompt("thanks")
    log.save(path)


def transcript_pause_then_close(path, run):
    """One session pauses the run (a card after it), then closes it complete in a call whose last command
    fails — so the result is an error, though its output says the run closed — with no card after."""
    events = [line.split("\t") for line in (run / "events.tsv").read_text(encoding="utf-8").splitlines()[1:]]
    opened, closed = utc(events[0][2]), utc(events[-1][2])
    log = Transcript("session-clean", opened - timedelta(seconds=30))
    log.prompt("/council-review the change on this branch")
    log.at(opened - timedelta(seconds=2)).bash("council run open council-review", str(run))
    log.at(closed - timedelta(seconds=60)).bash("council run close --status paused", "closed %s — paused" % run.name)
    log.bash("council status --run %s" % run.name, "Project · Review · %s\nStatus: Paused. The review waits." % run.name)
    log.text("**Status:** Paused. The review waits.")
    log.at(closed - timedelta(seconds=1)).call("Bash", {"command": "council run close && council nosuch", "description": "x"},
                                               "Exit code 2\nclosed %s — complete\ncouncil: unknown command: nosuch" % run.name,
                                               error=True)
    log.at(closed + timedelta(minutes=5)).prompt("thanks")
    log.save(path)


# --- one session, several runs: each run's window is its own (the night audit counted a pipe under several runs)
def minimal_run(base, name, events, session="session-multi"):
    """A closed review run with only what the transcript items read: its state and its open/close events."""
    run = base / "multi" / ".council" / "runs" / name
    write(run / "session-state.md", "\n".join([
        "status: complete", "mode: council-review", "phase: learn", "session: %s" % session, "events-schema: 1",
        "## Decisions so far", ""]))
    write(run / "events.tsv", "schema\tseq\tat\ttype\tsubject\tvalue\tdetail\n" + "".join(
        "1\t%d\t%s\n" % (n, "\t".join(row)) for n, row in enumerate(events, 1)))
    return run


def transcript_two_runs(path, first, second, t0):
    """One turn drives two runs: the first is opened, dispatched with a card, piped and closed with a card;
    then the second is opened, dispatched with no card, piped and closed."""
    log = Transcript("session-multi", t0)
    log.prompt("review both changes")
    log.at(t0 + timedelta(seconds=10)).bash("council run open council-review", str(first))
    log.call("Agent", {"subagent_type": "small-council:council-worker", "description": "A", "prompt": "x"}, "done")
    log.bash("council seat hunt running agent=a1", "seats: 0 of 1 done")
    log.bash("council status --widget", "<div>card</div>")
    log.call("mcp__visualize__show_widget", {"widget_code": "<div>card</div>"}, "shown")
    log.bash("council gate tests 2>&1 | tail -3", "gate tests: pass")
    log.bash("council seat hunt done tokens=1000", "seats: 1 of 1 done")
    log.at(t0 + timedelta(seconds=99)).bash("council run close", "closed %s — complete" % first.name)
    log.call("mcp__visualize__show_widget", {"widget_code": "<div>done</div>"}, "shown")
    log.at(t0 + timedelta(seconds=200)).bash("council run open council-review", str(second))
    log.call("Agent", {"subagent_type": "small-council:council-worker", "description": "B", "prompt": "y"}, "done")
    log.bash("council seat fowler running agent=b2", "seats: 0 of 1 done")
    log.bash("council run status | head -5", "runs")
    log.bash("council seat fowler done tokens=1000", "seats: 1 of 1 done")
    log.at(t0 + timedelta(seconds=299)).bash("council run close", "closed %s — complete" % second.name)
    log.call("mcp__visualize__show_widget", {"widget_code": "<div>done</div>"}, "shown")
    log.at(t0 + timedelta(minutes=20)).prompt("thanks")
    log.save(path)


# --- the paid suite's graders, on synthetic traces ---------------------------------------------------------------
def graded(rows):
    sys.path.insert(0, str(ROOT / "evals"))
    import check_repair_trace as trace                       # the suite's own tool_used reading, run locally
    found = trace.graders(ROOT / "evals" / "suite" / "squad-review-dispatch")
    return found, trace.grade(rows, found)


def trace_rows(commands):
    return [{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t%d" % n, "name": "Bash",
                                                            "input": {"command": c, "description": "x"}}]}}
            for n, c in enumerate(commands)]


if not BASH or not GIT:
    print("[SKIP] bash or git not on PATH — the audit evals need both; nothing was checked")
    sys.exit(0 if "--allow-skip" in sys.argv else 3)

with tempfile.TemporaryDirectory(prefix="council-audit-") as temporary:
    base = Path(os.path.realpath(temporary))
    project, run1 = build_run1(base)
    log1 = base / "run1-session.jsonl"
    transcript_run1(log1, project, run1)
    repo, run2, steps = build_clean(base)
    check("setup: the clean run goes through the real helper, open to close",
          run2 is not None and all(code == 0 for _, code, _ in steps), [s for s in steps if s[1] != 0])
    log2, log3, far = base / "clean-session.jsonl", base / "silent-session.jsonl", base / "no-window.jsonl"
    if run2 is not None:
        transcript_clean(log2, run2)
        silent = [json.loads(line) for line in log2.read_text(encoding="utf-8").splitlines()]
        for line in silent:                             # the same Chair, who passes on none of the status text
            for block in line["message"]["content"] if isinstance(line["message"]["content"], list) else []:
                if block.get("type") == "text":
                    block["text"] = "One finding, confirmed."
        write(log3, "".join(json.dumps(line) + "\n" for line in silent))
    write(far, json.dumps({"type": "user", "timestamp": "2026-01-01T00:00:00Z", "sessionId": "another",
                           "message": {"role": "user", "content": "hello"}}) + "\n")
    before = fingerprint(base)

    # The first real run's pattern: every known problem is named, and the rest passes.
    code, out, err = council(base, "run", "audit", "--run", str(run1), "--transcript", str(log1))
    check("run 1's pattern: the audit exits 1 because something failed", code == 1, out + err)
    verdict, words = item(out, "Stages")
    check("run 1's pattern: a stage never entered (judge), with why 3-6 are not needed", verdict == "FAIL"
          and "convene > prepare > challenge > deliver > learn" in words and "never entered: judge" in words
          and "no worker seat was selected" in words, words)
    verdict, words = item(out, "Agents on record while they ran")
    check("run 1's pattern: the verifier was written down only when it finished, so the limit could not count it",
          verdict == "FAIL" and "verify-1" in words and "only when it finished" in words, words)
    verdict, words = item(out, "Checks one at a time")
    check("run 1's pattern: two copies of the checks at once", verdict == "FAIL" and "tests" in words
          and "was still running" in words, words)
    verdict, words = item(out, "Each check once per stage")
    check("run 1's pattern: a check run twice in one stage is a warning", verdict == "warn"
          and "lint 2 times in challenge" in words, words)
    verdict, words = item(out, "Every seat on record")
    check("run 1's pattern: no record of the Chair's own seat, with the command that makes one",
          verdict == "FAIL" and "council seat chair done agents=0" in words, words)
    check("run 1's pattern: what it did do passes (closed after Deliver, deliverable, claim index, agent limit)",
          all(item(out, label)[0] == "pass" for label in ("Closed after Deliver", "Deliverable", "Claim index", "Agent limit"))
          and "1 of 10 agent runs" in item(out, "Agent limit")[1], out)
    verdict, words = item(out, "Status card at the first dispatch")
    check("run 1's pattern: no status card at the first dispatch", verdict == "FAIL" and "not shown" in words, words)
    verdict, words = item(out, "Closing card")
    check("run 1's pattern: no closing card; a card after the user's next message is outside the run and doesn't count",
          verdict == "FAIL" and "not shown after the close" in words, words)
    verdict, words = item(out, "Helper called as plain council")
    check("run 1's pattern: the helper through a shell variable and a full path, never by its plain name",
          verdict == "FAIL" and words.startswith("0 of ") and "through a shell variable" in words
          and "by the full path" in words, words)
    verdict, words = item(out, "Helper output shown whole")
    check("run 1's pattern: helper output cut by | tail and | head is named, call by call (the rule was words only)",
          verdict == "FAIL" and "route recommend | head -30" in words and "seat | tail -1" in words, words)
    verdict, words = item(out, "Helper refusals tried again")
    check("run 1's pattern: the refused status after close was never tried again",
          verdict == "warn" and "no open run on this working tree" in words, words)

    # The clean run: every item passes, through the helper, with no --run once it is closed.
    code, out, err = council(repo, "run", "audit", "--transcript", str(log2))
    listed = re.findall(r"^  (pass|warn|FAIL)\s+([^:]+):", out, re.MULTILINE)
    check("clean run: with no --run the audit reads this tree's newest run, the one just closed",
          run2 is not None and "Run audit: %s (council-review, complete)" % run2.name in out, out + err)
    check("clean run: every item passes and the audit exits 0 (a subagent's call in the file is not the Chair's)",
          code == 0 and len(listed) >= 14
          and all(v == "pass" for v, _ in listed), out + err)
    check("clean run: the ten stages, the widget at the first dispatch, the relayed status after close",
          "convene > prepare > assign > brief > work > collect > judge > challenge > deliver > learn"
          in item(out, "Stages")[1] and item(out, "Closing card")[0] == "pass"
          and item(out, "Status card at the first dispatch")[0] == "pass", out)
    check("clean run: a refusal tried again, the Chair's own seat on record",
          "1 refusal(s), each followed by another try" in item(out, "Helper refusals tried again")[1]
          and "the Chair's own included" in item(out, "Every seat on record")[1], out)
    code, out, err = council(repo, "run", "audit")
    check("clean run: without a transcript it says how to add one, and which session drove the run",
          code == 0 and "No transcript given: pass --transcript" in out, out + err)

    # The same Chair, who ran council status after the close but passed none of it on: no closing card.
    code, out, err = council(repo, "run", "audit", "--transcript", str(log3))
    check("a council status the Chair ran but did not pass on is not a closing card",
          code == 1 and item(out, "Closing card")[0] == "FAIL", out + err)
    check("reading leaves no bytecode beside the script", not (ROOT / "scripts" / "__pycache__").exists()
          or not any(p.name.startswith("audit.") for p in (ROOT / "scripts" / "__pycache__").iterdir()))

    code, out, err = council(base, "run", "audit", "--run", str(run1), "--transcript", str(base / "missing.jsonl"))
    check("a transcript that isn't there is refused (exit 2), not read as empty", code == 2 and "no such transcript" in err,
          out + err)
    code, out, err = council(base, "run", "audit", "--run", str(run1), "--json")
    check("run audit refuses a flag it doesn't take", code == 2 and "run audit doesn't take --json" in err, err)
    code, out, err = council(base, "run", "audit", "--run", str(run1), "--transcript", str(far))
    check("a transcript from another session or day says so rather than passing its items",
          item(out, "Transcript")[0] == "warn" and "Status card" not in out, out + err)
    check("reading writes nothing: the runs, both council homes and the transcripts are unchanged",
          fingerprint(base) == before, "")

    # A setup run follows its own phases: no Deliver, no deliverable, no record of the Chair's seat is due.
    init = base / "more" / "init-project"
    init.mkdir(parents=True)
    subprocess.run([GIT, "init", "-q"], cwd=str(init), check=True)
    write(init / ".council" / "council.config.md", "# Council config\n")
    codes = [council(init, *a)[0] for a in (("run", "open", "council-init"), ("state", "phase=detect"),
                                            ("state", "phase=propose"), ("run", "close"))]
    code, out, err = council(init, "run", "audit")
    check("a council-init run closed after its own phases fails nothing (no Deliver, deliverable or Chair record due)",
          codes == [0, 0, 0, 0] and code == 0 and all(item(out, label)[0] == "pass" for label in
                                                      ("Closed after Deliver", "Deliverable", "Every seat on record")),
          "%s exit %s: %s %s" % (codes, code, re.findall(r"^  (?:warn|FAIL) .*$", out, re.MULTILINE), err))

    # The close the audit judges is this run's own, as the helper did it: a refused close, or another run's
    # close earlier in the window, is not it (run 2's setup: the card after the first close in the window was
    # judged). And a complete run whose stream lost its close event reads the state's own stamp.
    if run2 is not None:
        for name, shown in (("refused-close.jsonl", False), ("refused-close-shown.jsonl", True)):
            transcript_refused_close(base / "more" / name, run2, shown)
        code, out, err = council(repo, "run", "audit", "--transcript", str(base / "more" / "refused-close.jsonl"))
        verdict, words = item(out, "Closing card")
        check("closing card: judged after this run's real close — not after a refused close or another run's close, "
              "though a card followed each", verdict == "FAIL" and "not shown after the close" in words, words)
        code, out, err = council(repo, "run", "audit", "--transcript", str(base / "more" / "refused-close-shown.jsonl"))
        check("closing card: a card after this run's real close passes", item(out, "Closing card")[0] == "pass",
              item(out, "Closing card")[1])
        transcript_pause_then_close(base / "more" / "pause-then-close.jsonl", run2)
        code, out, err = council(repo, "run", "audit", "--transcript", str(base / "more" / "pause-then-close.jsonl"))
        verdict, words = item(out, "Closing card")
        check("closing card: judged after this run's last close — not its pause — even when the close's call ended in "
              "an error after the close printed its line", verdict == "FAIL" and "not shown after the close" in words, words)
        lost = base / "more" / "no-close-event" / ".council" / "runs" / run2.name
        shutil.copytree(str(run2), str(lost))
        rows = (lost / "events.tsv").read_text(encoding="utf-8").splitlines(True)
        write(lost / "events.tsv", "".join(r for r in rows if "\trun.closed\t" not in r))
        stamped = re.search(r"^closed: (.+)$", (lost / "session-state.md").read_text(encoding="utf-8"), re.MULTILINE).group(1)
        code, out, err = council(base, "run", "audit", "--run", str(lost))
        verdict, words = item(out, "Closed after Deliver")
        check("a complete run whose stream holds no close event reads the state's closed: stamp, and warns rather than fails",
              verdict == "warn" and stamped.strip() in words, words)
        notes = base / "more" / "closed-in-notes" / ".council" / "runs" / run2.name
        shutil.copytree(str(lost), str(notes))
        state = (notes / "session-state.md").read_text(encoding="utf-8")
        write(notes / "session-state.md", re.sub(r"^closed: .*\n", "", state, flags=re.MULTILINE)
              + "## Notes\nclosed: when the owner says so\n")
        code, out, err = council(base, "run", "audit", "--run", str(notes))
        verdict, words = item(out, "Closed after Deliver")
        check("a 'closed:' line in a run's notes is not its close stamp — the audit reads the state's header only "
              "(converge of the leftovers build: it read 'closed complete at when the owner says so')",
              verdict == "FAIL" and "no close is recorded" in words and "when the owner says so" not in words, words)

    # Run 1's records with the changes the review asked about, in a copy.
    def run1_copy(name, synthesis=None, claims=None):
        folder = base / "more" / name / ".council" / "runs" / RUN1
        shutil.copytree(str(run1), str(folder))
        if synthesis is not None:
            write(folder / "synthesis.md", synthesis)
        if claims is not None:
            write(folder / "claims.jsonl", "".join(json.dumps(c) + "\n" for c in claims))
        return folder
    judged = run1_copy("judged", synthesis=(run1 / "synthesis.md").read_text(encoding="utf-8").replace("from: chair", "from: hunt#1"))
    code, out, err = council(base, "run", "audit", "--run", str(judged), "--transcript", str(log1))
    check("a Squad Chair that only judged (no finding from: chair) needs no record of its own seat",
          item(out, "Every seat on record")[0] == "pass", item(out, "Every seat on record")[1])
    cut = run1_copy("cut-confirmed", claims=[{"id": "1", "disposition": "kept", "verdict": "CONFIRMED", "citation": "notes.md:5"},
                                             {"id": "C1", "disposition": "cut", "verdict": "CONFIRMED", "citation": "notes.md:9"}])
    code, out, err = council(base, "run", "audit", "--run", str(cut), "--transcript", str(log1))
    check("a cut claim a verifier CONFIRMED fails the claim index, as council evidence check does",
          item(out, "Claim index")[0] == "FAIL" and "cut, but a verifier CONFIRMED it: C1" in item(out, "Claim index")[1],
          item(out, "Claim index")[1])
    # council run close runs this audit as it closes: the closing card comes after, so it is not judged yet —
    # every other FAIL still is (the night's one audit printed four FAILs the user never heard).
    at_close = subprocess.run([sys.executable, str(AUDIT), "--run", str(run1), "--transcript", str(log1), "--at-close"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
    check("--at-close: the closing card reads 'not checked yet', counted apart; the other FAILs stand and exit 1",
          at_close.returncode == 1 and re.search(r"^  later  Closing card: not checked yet", at_close.stdout, re.MULTILINE)
          and item(at_close.stdout, "Closing card")[0] is None and item(at_close.stdout, "Stages")[0] == "FAIL"
          and re.search(r"^\d+ failed, \d+ warning\(s\), \d+ passed, 1 not checked yet$", at_close.stdout, re.MULTILINE),
          at_close.stdout + at_close.stderr)
    skipped = run1_copy("skipped")
    rows = (skipped / "events.tsv").read_text(encoding="utf-8").replace(
        "\tchallenge\tfrom=prepare\n", "\tchallenge\tfrom=prepare;skipped=judge;reason=the user ruled it\n")
    write(skipped / "events.tsv", rows)
    verdict, words = item(council(base, "run", "audit", "--run", str(skipped))[1], "Stages")
    check("a stage skipped through council state skip= still fails Stages, and names the reason given",
          verdict == "FAIL" and "never entered: judge" in words and "judge skipped on purpose: the user ruled it" in words, words)
    paused = run1_copy("paused")
    state = (paused / "session-state.md").read_text(encoding="utf-8")
    write(paused / "session-state.md", state.replace("status: complete", "status: paused"))
    (paused / "claims.jsonl").unlink()
    verdict, words = item(council(base, "run", "audit", "--run", str(paused))[1], "Claim index")
    check("a paused run owes no claim index yet (the close now audits a pause too)", verdict == "pass" and "not due" in words, words)
    found_log = base / "more" / "config" / "projects" / "some-project" / "session-run-1.jsonl"
    found_log.parent.mkdir(parents=True)
    shutil.copyfile(str(log1), str(found_log))
    os.environ["CLAUDE_CONFIG_DIR"] = str(base / "more" / "config")
    try:
        code, out, err = council(base, "run", "audit", "--run", str(run1))
    finally:
        del os.environ["CLAUDE_CONFIG_DIR"]
    check("with no --transcript, the session's own transcript is found from the run's session id and read",
          "(found from the run's session id)" in out and item(out, "Status card at the first dispatch")[0] == "FAIL", out + err)

    # One session drove several runs. Each run reads only its own open-to-close part of the session: a pipe
    # is counted under the run it belongs to, and one run's status card is never another run's.
    t0 = utc("2026-10-08T10:00:00Z")

    def at(seconds):
        return (t0 + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_a = minimal_run(base, "2026-10-08-130000-review", [(at(11), "run.opened", "run", "council-review", "phase=convene"),
                                                          (at(100), "run.closed", "run", "complete", "agent_runs=1")])
    run_b = minimal_run(base, "2026-10-08-130320-review", [(at(201), "run.opened", "run", "council-review", "phase=convene"),
                                                          (at(300), "run.closed", "run", "complete", "agent_runs=1")])
    multi_log = base / "multi" / "two-runs.jsonl"
    transcript_two_runs(multi_log, run_a, run_b, t0)
    code, out_a, err = council(base, "run", "audit", "--run", str(run_a), "--transcript", str(multi_log))
    code, out_b, err_b = council(base, "run", "audit", "--run", str(run_b), "--transcript", str(multi_log))
    verdict_a, words_a = item(out_a, "Helper output shown whole")
    verdict_b, words_b = item(out_b, "Helper output shown whole")
    check("one session, two runs: each run's piped calls are its own — the first run's audit names only its gate | tail, "
          "the second's only its run status | head (the night audit counted one pipe under several runs)",
          verdict_a == "FAIL" and words_a.startswith("1 call(s)") and "gate | tail -3" in words_a and "| head" not in words_a
          and verdict_b == "FAIL" and words_b.startswith("1 call(s)") and "run status | head -5" in words_b
          and "| tail" not in words_b, "A: %s\nB: %s" % (words_a, words_b))
    check("one session, two runs: the first run's status card is not credited to the second run's first dispatch",
          item(out_a, "Status card at the first dispatch")[0] == "pass"
          and item(out_b, "Status card at the first dispatch")[0] == "FAIL", out_a + "\n" + out_b)
    check("one session, two runs: each run's closing card is judged after its own close",
          item(out_a, "Closing card")[0] == "pass" and item(out_b, "Closing card")[0] == "pass", out_a + "\n" + out_b)

    # A run opened in another session, paused, and resumed in this one reads only the part after its resume:
    # an earlier run's pipe in the same file is not its.
    run_c = minimal_run(base, "2026-10-08-090000-review", [
        ("2026-10-08T06:00:00Z", "run.opened", "run", "council-review", "phase=convene"),
        ("2026-10-08T06:30:00Z", "run.paused", "run", "paused", "agent_runs=0"),
        (at(201), "run.resumed", "run", "in-progress", "from=paused"),
        (at(300), "run.closed", "run", "complete", "agent_runs=1")])
    resumed_log = base / "multi" / "resumed.jsonl"
    log = Transcript("session-multi", t0)
    log.prompt("one more check first")
    log.at(t0 + timedelta(seconds=10)).bash("council run open council-review", str(run_a))
    log.bash('for g in tests lint; do council gate "$g" | tail -2; done', "gate tests: pass\ngate lint: pass")
    log.at(t0 + timedelta(seconds=99)).bash("council run close", "closed %s — complete" % run_a.name)
    log.at(t0 + timedelta(seconds=150)).prompt("now carry on with the paused review")
    log.at(t0 + timedelta(seconds=200)).bash("council run resume --run %s" % run_c.name, "resumed %s" % run_c.name)
    log.bash("council gate tests", "gate tests: pass")
    log.at(t0 + timedelta(seconds=299)).bash("council run close", "closed %s — complete" % run_c.name)
    log.at(t0 + timedelta(minutes=20)).prompt("thanks")
    log.save(resumed_log)
    code, out_c, err = council(base, "run", "audit", "--run", str(run_c), "--transcript", str(resumed_log))
    code, out_a2, err = council(base, "run", "audit", "--run", str(run_a), "--transcript", str(resumed_log))
    check("a resumed run reads only its own part of the session: another run's loop of piped gates before its "
          "resume is not counted under it, and is counted under that run",
          item(out_c, "Helper output shown whole")[0] == "pass"
          and item(out_a2, "Helper output shown whole")[0] == "FAIL"
          and item(out_a2, "Helper output shown whole")[1].startswith("1 call(s)")
          and "gate | tail -2" in item(out_a2, "Helper output shown whole")[1], out_c + "\n" + out_a2)

    # The first card is owed once per run, at the run's first dispatch: a later session that carries the run on and
    # sends another agent owes none — and its transcript passes, saying why.
    resumed = run1_copy("resumed")
    later = base / "more" / "session-two.jsonl"
    transcript_resumed(later, utc("2026-09-30T10:30:00Z"))
    code, out, err = council(base, "run", "audit", "--run", str(resumed), "--transcript", str(later))
    verdict, words = item(out, "Status card at the first dispatch")
    check("status card: a later session's transcript, the run's first dispatch (10:23) made before it began, passes and says why",
          verdict == "pass" and "first dispatch" in words and "an earlier session" in words and "once per run" in words, words)
    write(resumed / "agent-starts.tsv", "at\ttool\tsession\n2026-09-30T10:31:00Z\tbefore:1\t-\n"
                                        "2026-09-30T10:16:05Z\tAgent\tsession-run-1\n")
    transcript_resumed(later, utc("2026-09-30T10:15:00Z"))       # alongside the first session, from before its dispatch
    code, out, err = council(base, "run", "audit", "--run", str(resumed), "--transcript", str(later))
    verdict, words = item(out, "Status card at the first dispatch")
    check("status card: the agent gate's record names the session that made the first dispatch — another session's "
          "transcript passes", verdict == "pass" and "session session-run-1" in words, words)
    write(resumed / "agent-starts.tsv", "at\ttool\tsession\n2026-09-30T10:16:05Z\tAgent\tsession-two\n")
    code, out, err = council(base, "run", "audit", "--run", str(resumed), "--transcript", str(later))
    check("status card: the session that did make the first dispatch, with no card after it, still fails",
          item(out, "Status card at the first dispatch")[0] == "FAIL", item(out, "Status card at the first dispatch")[1])

# The helper's advisory lines the audit does not count as refusals must still be the helper's words.
sys.path.insert(0, str(ROOT / "scripts"))
import audit                                                         # noqa: E402  (bytecode is off)
helper = (ROOT / "bin" / "council").read_text(encoding="utf-8")
stale = [lead for lead in audit.NOTE_LEADS if lead not in helper]
check("every advisory line the audit lets pass is still one the helper prints", not stale, stale)

# How the helper was called, in the forms a real night used: 29 of 124 piped calls were seen before.
FORMS = [
    ('C="/home/u/.claude/plugins/small-council/bin/council"; bash "$C" gate --all 2>&1 | tail -4',
     [("variable", "gate", "tail -4")], "bash \"$C\" … once C is the helper, piped"),
    ('C=/x/bin/council; for s in a b; do n="${s%%|*}"; bash "$C" gate "probe-$n" -- "true" 2>&1 | tail -4; done',
     [("variable", "gate", "tail -4")], "a call inside a loop body"),
    ('for g in tests lint; do council gate "$g"; done | tail -2',
     [("plain", "gate", "tail -2")], "a loop whose whole output is piped"),
    ('( council run status; council cap ) 2>&1 | tail -1',
     [("plain", "run status", "tail -1"), ("plain", "cap", "tail -1")], "a ( ) group piped"),
    ('{ council run status; council cap; } | head -3',
     [("plain", "run status", "head -3"), ("plain", "cap", "head -3")], "a { } group piped"),
    ('if council gate tests; then echo ok; fi | head -1',
     [("plain", "gate", "head -1")], "an if around a call, piped"),
    ('while council gate tests | tail -1; do sleep 1; done',
     [("plain", "gate", "tail -1")], "a while condition piped"),
    ('C=/x/bin/council; RUN=$(bash "$C" run open council-plan 2>&1 | head -1); echo "$RUN"',
     [("variable", "run open", "head -1")], "a call captured in $( ), piped inside"),
    ('R=/x/plugins/small-council/0.20.1; bash "$R/bin/council" version 2>&1 | head -3',
     [("path", "version", "head -3")], "council version (a helper word too), by its path"),
    ('C="$(command -v council)"; $C gate tests |& tail -2',
     [("variable", "gate", "tail -2")], "a variable set from command -v, piped with |&"),
    ('council gate tests > gate.out 2>&1; tail -5 gate.out',
     [("plain", "gate", None)], "near miss: output to a file, then read — no cut"),
    ('case "$x" in a) council gate a;; b) council gate b | tail -1;; esac',
     [("plain", "gate", None), ("plain", "gate", "tail -1")], "near miss: a case pattern's ) is not a group"),
    ('for f in *.md; do grep -c x "$f" | head -1; done; council run status',
     [("plain", "run status", None)], "near miss: a loop that pipes something else"),
]
for command, want, what in FORMS:
    got = [(i["form"], i["sub"], i["cut"]) for i in audit.invocations(command)]
    check("audit parser: %s" % what, got == want, "%r → %r" % (command, got))

# The paid dispatch case's graders for the status card and the close.
found, failed = graded(trace_rows(["council run open council-review", "council seat hunt running agent=a1",
                                   "council status --widget", "council run close",
                                   'bash "${CLAUDE_PLUGIN_ROOT}/bin/council" status --widget --run r1',
                                   "council status --line --run r1"]))
check("graders: status-shown and run-closed exist as tool_used graders on Bash",
      found.get("status-shown", (None,))[0] == "Bash" and found.get("run-closed", (None,))[0] == "Bash", found)
check("graders: a Chair that shows the card at dispatch and after close, and closes, passes both",
      "status-shown" not in failed and "run-closed" not in failed, failed)
found, failed = graded(trace_rows(["council run open council-review", "council seat hunt running agent=a1",
                                   "council run status", "council tui"]))
check("graders: no card at all and no close fails both (run status and tui are not the card)",
      "status-shown" in failed and "run-closed" in failed, failed)
found, failed = graded(trace_rows(["council status"] * 3 + ["council status --widget"] * 4 + ["council run close"]))
check("graders: a card per progress line (seven) fails status-shown", "status-shown" in failed, failed)

# A suite that checked nothing never passes: without bash and git the five suites that need them
# stop at once — exit 3, unless --allow-skip — and run_all.py fails a job that reports no checks.
with tempfile.TemporaryDirectory(prefix="council-noshell-") as empty:
    env = {"PATH": empty, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    for var in ("SYSTEMROOT", "TEMP", "TMP"):              # Windows needs these to start Python at all
        if os.environ.get(var):
            env[var] = os.environ[var]
    if shutil.which("bash", path=empty) or shutil.which("git", path=empty):
        check("no-shell: an empty PATH hides bash and git", False, empty)
    else:
        runs = {}
        for suite in ("run_cli.py", "run_hook.py", "run_memory.py", "run_tui.py", "run_tune.py"):
            for extra in ([], ["--allow-skip"]):
                try:
                    done = subprocess.run([sys.executable, str(ROOT / "evals" / suite), *extra], cwd=str(ROOT), env=env,
                                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
                    runs[suite, bool(extra)] = (done.returncode, done.stdout + done.stderr)
                except subprocess.TimeoutExpired:
                    runs[suite, bool(extra)] = (124, "still running after 60 s")
        check("no-shell: each suite that needs bash and git says it checked nothing and exits 3, not 0",
              all(runs[s, False][0] == 3 and "nothing was checked" in runs[s, False][1] for s, a in runs if not a),
              dict((s, r) for (s, a), r in runs.items() if not a))
        check("no-shell: --allow-skip is the one way such a run exits 0",
              all(runs[s, True][0] == 0 for s, a in runs if a), dict((s, r) for (s, a), r in runs.items() if a))
sys.path.insert(0, str(ROOT / "evals"))
import run_all                                                       # noqa: E402  (bytecode is off)


def job_result(script, code, output):
    job = run_all.Job("x", [script], False)
    job.code, job.output = code, output
    return job.ok, job.verdict


check("run_all: a suite that exits 0 with no 'N/N checks passed' line, or 0/0, fails; a counted pass passes",
      job_result("evals/run_tui.py", 0, b"[SKIP] bash or git unavailable\n") == (False, "FAILED (no checks ran)")
      and not job_result("evals/run_tui.py", 0, b"\n0/0 checks passed\n")[0]
      and job_result("evals/run_tui.py", 0, b"\n12/12 checks passed\n") == (True, "passed")
      and job_result("evals/run_tui.py", 1, b"\n11/12 checks passed\n") == (False, "FAILED (exit 1)"))
check("run_all: only the suites that report their own way are spared the count, and each is on the list",
      run_all.NO_COUNT <= set(args[0] for _, args, _ in run_all.SUITES)
      and job_result("scripts/quick_validate.py", 0, b"validation OK: 0 warning(s)\n")[0])

passed = sum(1 for _, good, _ in checks if good)
for name, good, detail in checks:
    print("[{}] {}".format("PASS" if good else "FAIL", name) + ("" if good or not detail else "  ({})".format(str(detail)[:400])))
print("\n{}/{} checks passed".format(passed, len(checks)))
sys.exit(0 if passed == len(checks) else 1)
