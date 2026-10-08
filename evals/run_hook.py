#!/usr/bin/env python3
"""Hook evals for the Small Council — run both hooks against fixture projects (bash + git, no LLM).

SessionStart (hooks/session-start.sh):
  - silent (exit 0) in a project with no .council/;
  - orients a council project: missing config, the map, memory, pending proposals, the helper;
  - finds open runs by scanning runs/*/session-state.md, several at once, and flags each one:
    unfinished on startup (its running seats died with the old session); paused as paused, even right
    after a compaction; a run in another working tree as "leave it alone";
  - after a compaction, resumes only the run this session was driving — the one whose session: matches
    (also after `council run resume` in a new session, and when its code is in a linked worktree), else
    the newest recent in-progress run that recorded none — never a paused one or another session's run
    in another tree, and only lists the rest;
  - never offers to re-dispatch or close a run another session updated in the last 2 hours;
  - stays fast and short with many open runs: other trees' runs summed up, gone trees named, at most 5
    of this tree's runs described;
  - says nothing about complete or abandoned runs; keeps a 0.2 run's fields in place (no code-root);
  - still finds a legacy run through the old active-run pointer (no status line, CRLF, <mode>-output),
    offers a finished one to close as complete, and never claims an old one after a compaction;
  - finds the MAIN checkout's .council/ from a linked worktree; reports a stale or rewritten map;
    survives garbage;
  - warns first when the session's own cwd is a linked worktree and an open run's code is elsewhere;
  - marks its session id, council or not, and `council run open` refuses a session with no mark (unless
    there is no session id, or COUNCIL_ALLOW_NO_HOOKS=1).
SubagentStop (hooks/seat-gate.sh):
  - lets a valid worker or verifier file through, including list-style index lines and prose;
  - blocks once (exit 2, reason on stderr) on a missing, malformed, oversized or empty file, an index
    line it can't read, a verifier table the claim index can't read, or a reply with no "Wrote" line;
  - never blocks when stop_hook_active is set, on a line that starts with BLOCKED, or for other agents.
PreToolUse (hooks/agent-gate.sh), fed through hooks.json's own command and matcher:
  - silent (exit 0) with no council, no open run, a run under its cap, a paused run, another session's
    run, or input it can't read;
  - refuses a new agent (exit 2, the reason on stderr, stdout empty) at the cap, past the token ceiling,
    and for a session-less run on this tree, naming council cap allow; lets the agents a recorded go
    covers through, then stops again;
  - counts each agent start it lets through for the run this session drives, so agents started with
    nothing recorded (together, too) meet the stop, and the same agents recorded later count once; a
    run opened before plans and agent limits is never stopped;
  - reads session_id and cwd from the top level only (a Windows cwd with escaped backslashes too), never
    from text inside another value;
  - holds the council's own agents (tool_input's subagent_type) to the record: a council-worker with no
    open run, an agent for a closed run, a seat the plan doesn't select, a build task's third check — read
    from the Seat: line or the file the dispatch writes; never an ordinary agent, a Workflow, a verifier
    outside any run, or a cut-off input.
Stop (hooks/turn-end.sh): sends the Chair back once while the run's first status card is still due.
PreToolUse (hooks/bash-gate.sh), fed through hooks.json's own command and matcher:
  - refuses (exit 2, one line on stderr) a command that pipes the helper into head, tail or grep —
    `2>&1 |`, `|&`, bash <path>/bin/council, a loop or group piped whole, a variable set to the helper;
  - lets through a redirect to a file, `| tee`, grep or head over files or other commands, the word
    council in quotes, a comment or a heredoc, and anything it can't parse.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "hooks", "session-start.sh")
GATE = os.path.join(ROOT, "hooks", "seat-gate.sh")
BASH = os.environ.get("COUNCIL_EVAL_BASH") or shutil.which("bash")   # CI's macOS leg: /bin/bash (3.2)
GIT = shutil.which("git")
GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME="eval", GIT_AUTHOR_EMAIL="eval@example.invalid",
               GIT_COMMITTER_NAME="eval", GIT_COMMITTER_EMAIL="eval@example.invalid")
GIT_ENV.pop("CLAUDE_CODE_SESSION_ID", None)
GIT_ENV.pop("COUNCIL_ALLOW_NO_HOOKS", None)
if os.environ.get("COUNCIL_EVAL_BASH"):                  # nested `bash` calls use that bash too
    GIT_ENV["PATH"] = os.path.dirname(BASH) + os.pathsep + GIT_ENV.get("PATH", "")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
results = []


def check(name, ok, detail=""):
    results.append((ok, name, detail))


def run_hook(project, source="startup", payload=None, session="eval", raw=False):
    env = dict(GIT_ENV, CLAUDE_PROJECT_DIR=project, CLAUDE_PLUGIN_ROOT=ROOT)
    if payload is None:
        payload = json.dumps({"session_id": session, "hook_event_name": "SessionStart", "source": source})
    try:
        if raw:   # bytes, as the session receives them: text mode would turn every \r into \n
            p = subprocess.run([BASH, HOOK], input=payload.encode("utf-8"), capture_output=True, env=env, cwd=project,
                               timeout=60)
            return p.returncode, p.stdout
        p = subprocess.run([BASH, HOOK], input=payload, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env, cwd=project, timeout=60)
    except subprocess.TimeoutExpired:   # Claude Code gives up after 15 s and drops everything the hook printed
        return 124, b"" if raw else "(the hook ran for over 60 s)"
    return p.returncode, p.stdout


def marks():
    """Where the SessionStart hook marks a session whose hooks run (bin/council's sessions_dir): under the
    eval's own XDG_CACHE_HOME, set when the blocks start, never the user's cache."""
    return os.path.join(GIT_ENV["XDG_CACHE_HOME"], "small-council", "sessions")


def hooks_ran(session):
    """As if this session's SessionStart hook had run: council run open refuses a session with no mark."""
    os.makedirs(marks(), exist_ok=True)
    open(os.path.join(marks(), session), "w").close()


def council(cwd, *args, session="", hooks=True, env=None):
    """session: run as that Claude Code session, marked as one whose hooks run unless hooks=False."""
    if session and hooks:
        hooks_ran(session)
    env = dict(GIT_ENV, **(env or {}))
    if session:
        env["CLAUDE_CODE_SESSION_ID"] = session
    p = subprocess.run([BASH, os.path.join(ROOT, "bin", "council"), *args], cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=120)
    return p.returncode, p.stdout.strip(), p.stderr


def line_with(out, text):
    return next((line for line in out.splitlines() if text in line), "")


def lines_with(out, text):
    return [line for line in out.splitlines() if text in line]


def age(path, seconds):
    t = time.time() - seconds
    os.utime(path, (t, t))


def run_gate(agent, message, active=False, cwd=None, compact=False, payload=None, command=None, env=None):
    """compact: JSON with no spaces, as JavaScript's JSON.stringify writes it. payload: the raw stdin.
    command: a hooks.json command line, run with bash -c (env sets CLAUDE_PLUGIN_ROOT)."""
    if payload is None:
        fields = {"hook_event_name": "SubagentStop", "agent_type": agent, "agent_id": "a1",
                  "last_assistant_message": message, "stop_hook_active": active, "cwd": cwd or ""}
        payload = json.dumps(fields, separators=(",", ":")) if compact else json.dumps(fields)
    argv = [BASH, "-c", command] if command else [BASH, GATE]
    p = subprocess.run(argv, input=payload, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=60, env=dict(os.environ, **(env or {})))
    return p.returncode, p.stderr


def pre_tool(session="sA", cwd="", tool="Agent", before=None, prompt="Review the change"):
    """A PreToolUse input as Claude Code writes it: compact JSON. session=None leaves session_id out;
    before: fields placed ahead of session_id and cwd."""
    fields = dict(before or {})
    if session is not None:
        fields["session_id"] = session
    fields.update({"transcript_path": "/x/t.jsonl", "cwd": cwd, "permission_mode": "default",
                   "hook_event_name": "PreToolUse", "tool_name": tool,
                   "tool_input": {"description": "d", "prompt": prompt, "subagent_type": "general-purpose"}})
    return json.dumps(fields, separators=(",", ":"))


def dispatch_input(session, cwd, subagent, prompt, tool="Agent", before=None):
    """A PreToolUse input for an Agent call of one subagent type, as Claude Code writes it: compact JSON."""
    fields = dict(before or {})
    fields.update({"session_id": session, "transcript_path": "/x/t.jsonl", "cwd": cwd, "permission_mode": "default",
                   "hook_event_name": "PreToolUse", "tool_name": tool,
                   "tool_input": {"description": "d", "prompt": prompt, "subagent_type": subagent}})
    return json.dumps(fields, separators=(",", ":"))


def run_agent_gate(command, payload, cwd):
    """hooks.json's PreToolUse command, run with bash -c from cwd; returns (exit code, stdout, stderr, seconds)."""
    t0 = time.time()
    p = subprocess.run([BASH, "-c", command], input=payload, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=60, cwd=cwd, env=dict(GIT_ENV, CLAUDE_PLUGIN_ROOT=ROOT))
    return p.returncode, p.stdout, p.stderr, time.time() - t0


def stop_input(session="sA", cwd="", active=False, message="Which of the two should I build first?"):
    """A Stop input as Claude Code writes it: compact JSON."""
    return json.dumps({"session_id": session, "transcript_path": "/x/t.jsonl", "cwd": cwd, "permission_mode": "default",
                       "hook_event_name": "Stop", "stop_hook_active": active, "last_assistant_message": message},
                      separators=(",", ":"))


def valid_plan(run, seats=("chair", "w1"), mode="council-review"):
    """A complete run-plan v1, so the helper starts the seats a test names."""
    rows = [("kind", "id", "field", "value", "reason"), ("schema", "plan", "version", "1", "test"),
            ("run", "run", "id", os.path.basename(run), "test"), ("run", "run", "mode", mode, "test"),
            ("run", "run", "size", "squad", "test"), ("assessment", "run", "risk", "low", "test"),
            ("assessment", "run", "complexity", "low", "test"), ("assessment", "run", "uncertainty", "low", "test"),
            ("budget", "run", "agent-cap", "10", "test"), ("budget", "run", "estimated-tokens", "100000", "test"),
            ("verification", "run", "level", "independent", "test")]
    for slug in list(seats) + ["verify-plan"]:
        role = "chair" if slug == "chair" else ("verifier" if slug.startswith("verify-") else "worker")
        rows += [("seat", slug, "disposition", "selected", "test"), ("seat", slug, "role", role, "test"),
                 ("context", slug, "level", "focused", "test"), ("budget", slug, "tool-calls", "15", "test")]
    write(os.path.join(run, "run-plan.tsv"), "\n".join("\t".join(r) for r in rows) + "\n")


def git(cwd, *args):
    return subprocess.run([GIT, "-c", "core.autocrlf=false", *args], cwd=cwd, check=True,
                          capture_output=True, text=True, env=GIT_ENV).stdout.strip()


def write(path, text, crlf=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text.replace("\n", "\r\n") if crlf else text)


def new_repo(base, name):
    repo = os.path.join(base, name)
    os.makedirs(repo)
    git(repo, "init", "-q")
    write(os.path.join(repo, "app.txt"), "v1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def state(status, mode="council-review", phase="work", code_root=None, session=None):
    lines = [f"status: {status}"] if status else []
    lines += [f"mode: {mode}", f"phase: {phase}", "updated: 2026-09-15 10:00"]
    if code_root is not None:
        lines.append(f"code-root: {code_root}")
    if session is not None:
        lines.append(f"session: {session}")
    lines.append("next: collect seats")
    return "\n".join(lines) + "\n"


def compacted(out):
    return [line for line in out.splitlines() if "COMPACTED DURING A COUNCIL RUN" in line]


PARTS = []                   # (group, block), in file order
ALONE = {"timing"}           # groups that must run with nothing else running (see evals/run_all.py)


def part(group):
    """Adds the block below to a group. A group runs in one process, its blocks in file order, and
    what one block leaves for a later one stays inside its group, so each group runs on its own.
    With no options every block runs, in file order, in this one process."""
    def add(block):
        PARTS.append((group, block))
        return block
    return add


@part("main")
def session_start(tmp):
    global full   # the memory-file block carries on with it
    # --- SessionStart --------------------------------------------------------------------------
    plain = new_repo(tmp, "plain")
    code, out = run_hook(plain)
    check("no .council/: exits 0", code == 0, str(code))
    check("no .council/: prints nothing", out.strip() == "", out)

    bare = new_repo(tmp, "bare")
    os.makedirs(os.path.join(bare, ".council"))
    code, out = run_hook(bare)
    check("council without config: says run council-init", "council-init" in out and "No council.config.md" in out, out)
    check("council without config (a post-game's folder): one line, no mode nudge", "Substantial work?" not in out, out)

    full = new_repo(tmp, "full")
    top = git(full, "rev-parse", "--show-toplevel")
    head = git(full, "rev-parse", "HEAD")
    write(os.path.join(full, ".council", "council.config.md"), "# Council config\n")
    write(os.path.join(full, ".council", "map.md"), f"# Codebase map\nmap-commit: {head}\nupdated: 2026-09-15\n")
    write(os.path.join(full, ".council", "conventions.md"),
          "# Conventions\n## Proposed\n<!-- Format: - PROPOSED accepted pattern: ... -->\n"
          "- PROPOSED accepted pattern: a — x (from r1, d)\n- PROPOSED enforced convention: b — y (from r1, d)\n")
    code, out = run_hook(full)
    check("full council: exits 0", code == 0, str(code))
    check("full council: orientation line", "[Small Council]" in out and "map.md" in out, out)
    check("full council: points at the helper", "council run status" in out and "bin/council" in out, out)
    check("full council: the helper runs in the Bash tool (Git Bash on Windows), never from PowerShell",
          "Bash tool (Git Bash on Windows)" in line_with(out, "plain `council <command>`")
          and "PowerShell" in line_with(out, "plain `council <command>`"), out)
    check("full council, team by default: no just-me line", "Just me:" not in out, out)
    check("full council: fresh map is not 'behind'", "behind" not in out, out)
    check("full council: counts 2 pending proposals (ignores the comment)", "2 memory proposal(s)" in out, out)
    check("full council: lists council-postgame among the modes", "council-postgame" in out, out)
    check("full council: no open-run warning", "UNFINISHED" not in out and "COMPACTED" not in out, out)
    check("no open run: no status card commands", "council status --run" not in out and
          "council status --widget" not in out, out)

    runs = os.path.join(full, ".council", "runs")
    run_a = os.path.join(runs, "2026-09-15-100000-review")
    write(os.path.join(run_a, "session-state.md"), state("in-progress", code_root=top))
    write(os.path.join(run_a, "seats.tsv"), "slug\tstate\tagent\ttokens\tupdated\tnote\nhunt\trunning\ta1\t\t10:00\tround 2\nbeck\tdone\ta2\t50000\t10:05\t\n")
    code, out = run_hook(full, "startup")
    check("open run found by scanning (no pointer needed)", "UNFINISHED COUNCIL RUN" in out, out)
    check("open run: status text, widget and read_me instructions", "council status --run <name>" in out and
          "council status --widget" in out and "call its read_me first" in out, out)
    check("open run: shows the mode and phase", "council-review" in out and "phase: work" in out, out)
    check("open run, new session: running seats are gone, done ones listed",
          "were running when that session ended" in out and "hunt" in out and "done: beck" in out, out)
    check("open run: a seat lost mid war-room says which round", "hunt (war-room round 2)" in out, out)
    code, out = run_hook(full, "clear")
    check("after /clear: running seats aren't declared gone", "still working: hunt" in out and "gone" not in out, out)
    code, out = run_hook(full, "compact")
    check("after compaction: says resume", "COMPACTED DURING A COUNCIL RUN" in out and "Do not restart" in out, out)
    check("after compaction: re-invoke the run's own mode", "Re-invoke the council-review skill" in out, out)
    check("after compaction: don't re-dispatch running seats", "do not re-dispatch seats that are running" in out, out)
    code, out = run_hook(full, payload='{"session_id":"eval","source":"compact"}')
    check("after compaction: compact JSON without spaces is recognised too", len(compacted(out)) == 1, out)
    for closed in ("complete", "abandoned"):
        write(os.path.join(run_a, "session-state.md"), state(closed, code_root=top))
        code, out = run_hook(full, "startup")
        check(f"{closed} run: no warning", "UNFINISHED" not in out and "PAUSED" not in out, out)
        check(f"{closed} run: no status card commands", "council status --run" not in out and
              "council status --widget" not in out, out)
    write(os.path.join(run_a, "session-state.md"), state("paused", code_root=top))
    code, out = run_hook(full, "startup")
    check("paused run: reported as paused, not unfinished", "PAUSED COUNCIL RUN" in out and "UNFINISHED" not in out, out)
    code, out = run_hook(full, "compact")
    check("paused run: stays paused right after a compaction", "PAUSED COUNCIL RUN" in out and not compacted(out), out)

    write(os.path.join(run_a, "session-state.md"), state("in-progress", code_root=top))
    run_b = os.path.join(runs, "2026-09-15-110000-implement")
    elsewhere = os.path.join(tmp, "elsewhere", "tree").replace("\\", "/")   # another working tree that exists
    os.makedirs(elsewhere)
    write(os.path.join(run_b, "session-state.md"), state("in-progress", mode="council-implement", code_root=elsewhere))
    code, out = run_hook(full, "startup")
    check("several open runs: all reported", "UNFINISHED COUNCIL RUN" in out and "2026-09-15-110000-implement" in out, out)
    check("a run in another working tree: leave it alone", "different working tree" in out and "Leave it alone" in out, out)
    code, out = run_hook(full, "compact")
    c = compacted(out)
    check("after compaction: only this tree's run is resumed", len(c) == 1 and "council-review" in c[0], out)

    run_c = os.path.join(runs, "2026-09-14-090000-plan")
    write(os.path.join(run_c, "session-state.md"), state("in-progress", mode="plan"))
    code, out = run_hook(full, "startup")
    check("0.2 run with no code-root: treated as this tree's, its fields in place",
          "2026-09-14-090000-plan (council-plan, phase: work, updated: 2026-09-15 10:00)" in out, out)
    check("two runs open on this tree: says to pass --run", "pass --run 2026-09-15-100000-review" in out, out)

    write(os.path.join(full, ".council", "active-run"), ".council/runs/2026-09-15-100000-review\n")
    code, out = run_hook(full, "startup")
    check("old pointer into runs/: the run is reported once", out.count("2026-09-15-100000-review (") == 1, out)

    # Which run a compaction resumes
    sess = new_repo(tmp, "sess")
    stop = git(sess, "rev-parse", "--show-toplevel")
    write(os.path.join(sess, ".council", "council.config.md"), "# Council config\n")
    mine = os.path.join(sess, ".council", "runs", "2026-09-15-090000-review")
    theirs = os.path.join(sess, ".council", "runs", "2026-09-15-120000-plan")
    write(os.path.join(mine, "session-state.md"), state("in-progress", code_root=stop, session="eval"))
    write(os.path.join(theirs, "session-state.md"), state("in-progress", mode="council-plan", code_root=stop, session="someone-else"))
    code, out = run_hook(sess, "compact", session="eval")
    c = compacted(out)
    check("after compaction: resumes the run this session opened, not the newest", len(c) == 1 and "2026-09-15-090000-review" in c[0], out)
    check("after compaction: another session's run is only listed", "not this session's run: 2026-09-15-120000-plan" in out, out)
    check("after compaction: with two runs here, says to pass --run", "pass --run 2026-09-15-090000-review" in out, out)
    # A second run this same session opened (council run open … --alongside) is its own work too.
    write(os.path.join(theirs, "session-state.md"), state("in-progress", mode="council-plan", code_root=stop, session="eval"))
    code, out = run_hook(sess, "compact", session="eval")
    line = line_with(out, "2026-09-15-090000-review")
    check("after compaction: a run this same session opened alongside is not called someone else's",
          "not this session's run" not in line and "opened alongside by this same session" in line
          and "--run 2026-09-15-090000-review" in line, out)
    write(os.path.join(theirs, "session-state.md"), state("in-progress", mode="council-plan", code_root=stop, session="someone-else"))
    write(os.path.join(theirs, "session-state.md"), state("in-progress", mode="council-plan", code_root=stop))
    code, out = run_hook(sess, "compact", session="a-new-id")
    c = compacted(out)
    check("after compaction: no match → the newest recent run that recorded no session", len(c) == 1 and "2026-09-15-120000-plan" in c[0], out)
    stale = time.time() - 3 * 86400
    os.utime(os.path.join(theirs, "session-state.md"), (stale, stale))
    code, out = run_hook(sess, "compact", session="a-new-id")
    check("after compaction: a stale run is never resumed on a guess",
          not compacted(out) and "not this session's run: 2026-09-15-120000-plan" in out, out)

    two = new_repo(tmp, "two-sessionless")
    ttop = git(two, "rev-parse", "--show-toplevel")
    write(os.path.join(two, ".council", "council.config.md"), "# Council config\n")
    for name, mode in (("2026-09-15-090000-review", "council-review"), ("2026-09-15-100000-plan", "council-plan")):
        write(os.path.join(two, ".council", "runs", name, "session-state.md"), state("in-progress", mode=mode, code_root=ttop))
    code, out = run_hook(two, "compact", session="a-new-id")
    c = compacted(out)
    check("after compaction: of two recent runs that recorded no session, the newest is resumed and the other only listed",
          len(c) == 1 and "2026-09-15-100000-plan" in c[0] and "not this session's run: 2026-09-15-090000-review" in out, out)

    sib = new_repo(tmp, "paused-sibling")
    btop = git(sib, "rev-parse", "--show-toplevel")
    write(os.path.join(sib, ".council", "council.config.md"), "# Council config\n")
    write(os.path.join(sib, ".council", "runs", "2026-09-15-090000-review", "session-state.md"),
          state("in-progress", code_root=btop, session="eval"))
    write(os.path.join(sib, ".council", "runs", "2026-09-15-100000-plan", "session-state.md"),
          state("paused", mode="council-plan", code_root=btop, session="eval"))
    code, out = run_hook(sib, "compact", session="eval")
    c = compacted(out)
    check("after compaction: a paused run of the same session never takes the place of the run it was driving",
          len(c) == 1 and "2026-09-15-090000-review" in c[0] and "PAUSED COUNCIL RUN" in line_with(out, "2026-09-15-100000-plan"), out)

    # A run carried into a new session: council run resume makes it that session's run
    ho = new_repo(tmp, "handover")
    write(os.path.join(ho, ".council", "council.config.md"), "# Council config\n")
    code, hrun, _ = council(ho, "run", "open", "council-review", session="session-A")
    hname = os.path.basename(hrun)
    code, out = run_hook(ho, "clear", session="session-B")
    check("after /clear: a run another session id was driving is offered with council run resume",
          f"council run resume --run {hname}" in line_with(out, hname), out)
    council(ho, "run", "resume", "--run", hname, session="session-B")
    code, out = run_hook(ho, "compact", session="session-B")
    c = compacted(out)
    check("a run resumed in a new session (council run resume) is that session's run at its next compaction",
          len(c) == 1 and hname in c[0], out)

    # A build whose code lives in a linked worktree, driven by a session whose project dir is the main
    # checkout (the real Chrollo build: nine compactions, each told to leave its own run alone).
    wmain = new_repo(tmp, "wt-main")
    write(os.path.join(wmain, ".council", "council.config.md"), "# Council config\n")
    wtree = os.path.join(wmain, ".claude", "worktrees", "feat")
    git(wmain, "worktree", "add", "-q", wtree, "-b", "feat")
    wtop = git(wtree, "rev-parse", "--show-toplevel")
    code, wrun, _ = council(wtree, "run", "open", "council-implement", session="S1")
    wname = os.path.basename(wrun)
    code, out = run_hook(wmain, "compact", session="S1")
    c = compacted(out) or [""]
    check("after compaction: this session's run whose code is in a linked worktree is resumed, never 'left alone'",
          len(c) == 1 and wname in c[0] and "Re-invoke the council-implement skill" in c[0]
          and "different working tree" not in out and "Leave it alone" not in out, out)
    check("after compaction: ... and it says where the run's code is, with --run",
          f"another working tree, {wtop}" in c[0] and f"--run {wname}" in c[0], out)
    code, out = run_hook(wmain, "startup", session="S1")
    check("on startup or resume: this session's worktree run is offered to resume, not called another tree's",
          "UNFINISHED COUNCIL RUN" in line_with(out, wname) and "Leave it alone" not in out, out)
    code, out = run_hook(wmain, "compact", session="S2")
    check("after compaction: another session's worktree run is still left alone",
          not compacted(out) and "Leave it alone" in line_with(out, wname), out)

    # A run another session updated recently may still be live there
    live = new_repo(tmp, "live")
    ltop = git(live, "rev-parse", "--show-toplevel")
    write(os.path.join(live, ".council", "council.config.md"), "# Council config\n")
    lrun = os.path.join(live, ".council", "runs", "2026-09-15-130000-review")
    write(os.path.join(lrun, "session-state.md"), state("in-progress", phase="collect", code_root=ltop, session="live-session"))
    write(os.path.join(lrun, "seats.tsv"), "slug\tstate\tagent\ttokens\tupdated\tnote\nhunt\trunning\ta1\t\t13:30\t\nbeck\tdone\ta2\t5000\t13:20\t\n")
    code, out = run_hook(live, "startup", session="another-session")
    line = line_with(out, "2026-09-15-130000-review")
    check("a run another session updated recently: may still be live there — no re-dispatch, no close offered",
          "another session" in line and "gone" not in line and "re-dispatch each once" not in line
          and "--status abandoned" not in line, out)
    code, out = run_hook(live, "clear", session="another-session")
    line = line_with(out, "2026-09-15-130000-review")
    check("after /clear, a recent run with another session id: resume it if this window drove it, else leave it",
          "council run resume --run 2026-09-15-130000-review" in line and "another session" in line
          and "--status abandoned" not in line, out)
    check("after /clear: workers of the cleared session are never something to wait for",
          "wait for their notifications" not in line and "died with the old session" in line
          and "re-dispatch each once" in line, out)
    for f in ("session-state.md", "seats.tsv"):
        age(os.path.join(lrun, f), 3 * 3600)
    code, out = run_hook(live, "startup", session="another-session")
    line = line_with(out, "2026-09-15-130000-review")
    check("a run another session left hours ago: unfinished, its running seats gone, resume or close offered",
          "UNFINISHED COUNCIL RUN" in line and "were running when that session ended" in line
          and "council run resume --run 2026-09-15-130000-review" in line and "--status abandoned" in line, out)

    private = new_repo(tmp, "just-me")
    write(os.path.join(private, ".council", "council.config.md"),
          "# Council config\n\n## Run preferences\n- sharing: just me\n", crlf=True)
    code, out = run_hook(private)
    check("a just-me council: the session hears that teammates never meet it — no council runs, ids or paths in commits, PRs or shared docs",
          code == 0 and "commit messages" in line_with(out, "Just me:") and ".council/ paths" in line_with(out, "Just me:"), out)

@part("timing")
def many_open_runs(tmp):
    # Many open runs: other trees' runs never hide this tree's, and the hook stays fast and short
    crowd = new_repo(tmp, "crowd")
    ctop = git(crowd, "rev-parse", "--show-toplevel")
    write(os.path.join(crowd, ".council", "council.config.md"), "# Council config\n")
    cruns = os.path.join(crowd, ".council", "runs")
    write(os.path.join(cruns, "2026-09-15-000000-review", "session-state.md"), state("in-progress", code_root=ctop, session="eval"))
    gone_root = os.path.join(tmp, "deleted-worktree").replace("\\", "/")        # never created
    other_root = os.path.join(tmp, "crowd-other").replace("\\", "/")
    os.makedirs(other_root)
    for i in range(30):
        write(os.path.join(cruns, f"2026-09-15-1{i:05d}-plan", "session-state.md"),
              state("in-progress", mode="council-plan", code_root=gone_root if i < 2 else other_root, session=f"o{i}"))
    t0 = time.time()
    code, out = run_hook(crowd, "compact", session="eval")
    took = time.time() - t0
    c = compacted(out)
    check("30 newer open runs in other working trees: this tree's run is still resumed after a compaction",
          len(c) == 1 and "2026-09-15-000000-review" in c[0], out)
    check("30 open runs in other working trees: summed up in a line or two, not a line each",
          sum(1 for line in out.splitlines() if "working tree" in line) <= 2 and len(out) < 4000, out)
    gone = line_with(out, "no longer exists")
    check("runs whose working tree no longer exists: said so, with the command to close them",
          "2026-09-15-100000-plan" in gone and "2026-09-15-100001-plan" in gone and "council run close --run" in gone
          and "--status abandoned" in gone, out)
    check("30 open runs: the hook finishes well inside its 15 s limit", took < 10, f"{took:.1f} s")
    for i in range(12):
        write(os.path.join(cruns, f"2026-09-16-1{i:05d}-research", "session-state.md"),
              state("paused", mode="council-research", code_root=ctop))
    code, out = run_hook(crowd, "startup", session="eval")
    described = [line for line in out.splitlines() if "COUNCIL RUN" in line]
    check("13 open runs on this tree: the in-progress one and 4 more described, the other 8 counted with a pointer to council run status",
          len(described) == 5 and "2026-09-15-000000-review" in described[0]
          and "8 more" in out and "council run status" in line_with(out, "8 more"), out)

    legacy = new_repo(tmp, "legacy")
    write(os.path.join(legacy, ".council", "council.config.md"), "# Council config\n", crlf=True)
    write(os.path.join(legacy, "conventions.md"), "# Project Conventions\n", crlf=True)
    old_rel = ".council/review-output/2026-09-07-1200"
    write(os.path.join(legacy, ".council", "active-run"), old_rel + "\n", crlf=True)
    write(os.path.join(legacy, old_rel, "session-state.md"), "# Session state\nphase: 5 — awaiting worker returns\n", crlf=True)
    code, out = run_hook(legacy, "startup")
    check("legacy run without status: flagged unfinished", "UNFINISHED COUNCIL RUN" in out, out)
    check("legacy run: mode inferred from the old folder name", "council-review (legacy run)" in out, out)
    code, raw = run_hook(legacy, "startup", raw=True)
    check("legacy CRLF state: no carriage returns leak into output", b"\r" not in raw, repr(raw))
    check("legacy root conventions.md: found", "Settled decisions:" in out and "conventions.md" in out, out)
    age(os.path.join(legacy, old_rel, "session-state.md"), 3 * 86400)
    code, out = run_hook(legacy, "compact")
    check("legacy run untouched for days: a compaction never says this session was running it",
          not compacted(out) and "2026-09-07-1200" in out, out)
    # A build's log is written after every task, so it is evidence of work, never of a finished run.
    write(os.path.join(legacy, old_rel, "implementation-log.md"),
          "# Implementation log\n**Tasks completed:** 3/15\nNext session resumes at Task 11.\n")
    code, out = run_hook(legacy, "startup")
    line = line_with(out, "2026-09-07-1200")
    check("legacy run holding only a build log: never called probably finished, and never offered as complete",
          "probably finished" not in line and "--status complete" not in line
          and "council run resume" in line and "--status abandoned" in line, out)
    write(os.path.join(legacy, old_rel, "FINAL-REVIEW.md"), "# Final review\n")
    code, out = run_hook(legacy, "startup")
    line = line_with(out, "2026-09-07-1200")
    check("legacy run holding its final deliverable: offered to close as complete, not abandoned",
          "--status complete" in line and "--status abandoned" not in line and "FINAL-REVIEW.md" in line, out)

@part("main")
def seat_gate_replies(tmp):
    # The seat check reads the reply honestly: a reply that is there but empty (an agent stopped at its turn
    # limit before answering) is sent back once; a missing field is the host's and passes; more than one line
    # is sent back once; a "Wrote" that names no file, or a relative name it can't find, asks for the full path.
    folder = os.path.join(tmp, "seat-replies")
    good = os.path.join(folder, "seats", "w1.md")
    write(good, "# Tests — tests (review)\nref: x\n## Index\n1 · P2 · Principle 1 · a.py:1 · a thing\n")
    worker = "small-council:council-worker"
    code, err = run_gate(worker, "")
    check("seat check: a reply that is there but empty is sent back once, with the file rule", code == 2 and "Wrote" in err, err)
    bare = json.dumps({"hook_event_name": "SubagentStop", "agent_type": worker, "agent_id": "a1", "stop_hook_active": False, "cwd": ""})
    code, err = run_gate(worker, "", payload=bare)
    check("seat check: no reply field at all (an older host) lets the agent stop", code == 0 and not err, err)
    code, err = run_gate(worker, "Wrote %s — 1 item (1 P2)\nAlso, a summary of what I found." % good)
    check("seat check: a good file with a reply of more than one line is sent back once for the one line",
          code == 2 and "exactly one line" in err, err)
    code, err = run_gate(worker, "Wrote my findings — 1 item")
    check("seat check: a Wrote line that names no file asks for the file's full path", code == 2 and "full path" in err, err)
    code, err = run_gate(worker, "Wrote seats/nowhere.md — 1 item", cwd=folder)
    check("seat check: a relative name it can't find is sent back once for the full path", code == 2 and "full path" in err, err)
    code, err = run_gate(worker, "Wrote %s — 1 item (1 P2)" % good)
    check("seat check: a good file and a one-line reply pass", code == 0 and not err, err)

@part("main")
def memory_file_and_seat_check(tmp):
    # The hook names the memory file every council command reads — the config's own path included —
    # and says when a second one holds entries nobody reads.
    memcfg = new_repo(tmp, "memcfg")
    write(os.path.join(memcfg, ".council", "council.config.md"),
          "# Council config\n## Memory\n- conventions: docs/conventions.md\n")
    write(os.path.join(memcfg, "docs", "conventions.md"), "# m\n## Accepted Patterns\n### AP-1: the one in docs\n")
    write(os.path.join(memcfg, "conventions.md"), "# m\n## Accepted Patterns\n### AP-1: an older copy\n### AP-2: and another\n")
    code, out = run_hook(memcfg, "startup")
    check("settled decisions: the hook names the file the config points at",
          "docs/conventions.md (respect them" in out.replace("\\", "/"), out)
    check("settled decisions: a second memory file with entries nobody reads is reported",
          "second memory file" in out and "2 entries" in out, out)
    write(os.path.join(memcfg, "docs", "conventions.md"),
          "# m\n## Proposed — awaiting the user's yes/no\n### AP-3: a proposal written as a heading\n"
          "- PROPOSED enforced convention: never X (evidence: a.py:1)\n")
    os.remove(os.path.join(memcfg, "conventions.md"))
    code, out = run_hook(memcfg, "startup")
    check("settled decisions: proposals written as a heading are counted too, as doctor counts them",
          "2 memory proposal(s)" in out, out)

    wt = os.path.join(tmp, "full-wt")
    git(full, "worktree", "add", "-q", "-b", "feature", wt)
    code, out = run_hook(wt, "startup")
    first = out.splitlines()[0] if out.strip() else ""
    check("linked worktree: finds the main checkout's council", "[Small Council]" in first
          and first.replace("\\", "/").rstrip("/").endswith("full/.council"), first)
    check("linked worktree: the main checkout's run is someone else's",
          any("2026-09-15-100000-review" in line for line in lines_with(out, "different working tree")), out)
    code, out = run_hook(wt, "compact")
    check("linked worktree, after compaction: the main checkout's run is never resumed, and is named as another tree's",
          not any("2026-09-15-100000-review" in line for line in compacted(out))
          and any("2026-09-15-100000-review" in line for line in lines_with(out, "different working tree")), out)

    for n in (2, 3):
        write(os.path.join(full, "app.txt"), f"v{n}\n")
        git(full, "commit", "-q", "-am", f"change {n}")
    code, out = run_hook(full, "startup")
    check("stale map: reports commits behind", "2 commits behind HEAD" in out, out)
    write(os.path.join(full, ".council", "map.md"), "# Codebase map\nmap-commit: 0123456789abcdef0123456789abcdef01234567\n")
    code, out = run_hook(full, "startup")
    check("map built on a commit no longer in history: said so, not presented as current",
          "no longer in this repo's history" in line_with(out, "Orientation"), out)

    pgr = new_repo(tmp, "pg")
    ptop = git(pgr, "rev-parse", "--show-toplevel")
    write(os.path.join(pgr, ".council", "runs", "2026-09-15-130000-postgame", "session-state.md"),
          state("in-progress", mode="council-postgame", phase="judge", code_root=ptop, session="eval"))
    code, out = run_hook(pgr, "compact", session="eval")
    check("after compaction in a post-game: re-invoke council-postgame and re-read ask.md",
          "Re-invoke the council-postgame skill" in out and "and ask.md, if present" in out, out)
    bld = new_repo(tmp, "build")
    write(os.path.join(bld, ".council", "council.config.md"), "# Council config\n")
    write(os.path.join(bld, ".council", "runs", "2026-09-15-140000-implement", "session-state.md"),
          state("in-progress", mode="council-implement", phase="build", code_root=git(bld, "rev-parse", "--show-toplevel"), session="eval"))
    code, out = run_hook(bld, "compact", session="eval")
    c = compacted(out)
    check("after compaction mid-build: points at the build loop, not at a stage doctrine a build skips",
          len(c) == 1 and "build loop" in c[0] and "doctrine for that phase" not in c[0], out)

    code, out = run_hook(full, payload="\x00not json at all")
    check("garbage stdin: exits 0", code == 0, str(code))

    # --- SubagentStop seat check ---------------------------------------------------------------
    seats = os.path.join(tmp, "run", "seats")
    good = os.path.join(seats, "hunt.md")
    write(good, "# Hunt — Security (council-review)\nref: Security Reference\nquestion: q\n## Index\n1 · P2 · Principle 3 · a.py:1 · x\n")
    worker, verifier = "small-council:council-worker", "small-council:council-verifier"
    code, err = run_gate(worker, f"Wrote {good} — 1 items (P2 1)")
    check("seat check: a valid worker file passes", code == 0, err)
    code, err = run_gate(worker, "Wrote seats/hunt.md — 1 items", cwd=os.path.join(tmp, "run"))
    check("seat check: a path relative to the worker's cwd passes", code == 0, err)
    session_dir = os.path.join(tmp, "session")                        # Claude Code sends the session's folder
    os.makedirs(session_dir)
    code, err = run_gate(worker, "Wrote seats/hunt.md — 1 items", cwd=session_dir)
    check("seat check: a relative path it can't find from the session's folder is sent back once for the full path "
          "(the next stop always passes, so it can't trap the agent)", code == 2 and "full path" in err, err)
    nope = os.path.join(seats, "nope.md")
    code, err = run_gate(worker, f"Wrote {nope} — 0 items")
    check("seat check: a missing file blocks (exit 2)", code == 2 and "doesn't exist" in err, err)
    code, err = run_gate(worker, f"Wrote {nope} — 0 items (brief.md had no slice for me)")
    check("seat check: a missing file is named exactly, even when the counts mention another .md",
          code == 2 and f"({nope}) doesn't exist" in err, err)
    code, err = run_gate(worker, f"Wrote {good} — 1 items (P2 1; brief.md had no slice for me)")
    check("seat check: another .md in the counts doesn't hide a valid file", code == 0, err)
    for label, reply in [("'Wrote:'", f"Wrote: {good} — 1 items (P2 1)"), ("'**Wrote**'", f"**Wrote** {good} — 1 items"),
                         ("lowercase 'wrote'", f"wrote {good} — 1 items"),
                         ("a markdown link", f"Wrote [hunt.md]({good}) — 1 items"),
                         ("a backticked path", f"Wrote `{good}` — 1 items")]:
        code, err = run_gate(worker, reply)
        check(f"seat check: a Wrote line written with {label} is read", code == 0, err)
    missing = os.path.join(seats, "missing.md")
    for label, reply in [("a markdown link to a missing file", f"Wrote [hunt.md]({missing}) — 1 items"),
                         ("'Wrote the file to <a missing path>'", f"Wrote the file to {missing}")]:
        code, err = run_gate(worker, reply)
        check(f"seat check: {label} blocks, naming that file", code == 2 and f"({missing}) doesn't exist" in err, err)
    code, err = run_gate(worker, "I wrote up my notes above")
    check("seat check: 'wrote' in a sentence with no file still asks for the file", code == 2 and "Wrote <output path>" in err, err)
    bom = os.path.join(seats, "bom.md")
    write(bom, "﻿# Bom — Security (council-review)\nref: none\n## Index\n1 · P2 · Principle 3 · a.py:1 · x\n")
    code, err = run_gate(worker, f"Wrote {bom} — 1 items (P2 1)")
    check("seat check: a byte-order mark before line 1 is fine", code == 0, err)
    bad = os.path.join(seats, "bad.md")
    write(bad, "# Bad\nnot a ref line\n")
    code, err = run_gate(worker, f"Wrote {bad} — 1 items")
    check("seat check: a malformed file blocks and names the fixes", code == 2 and "line 2" in err and "## Index" in err, err)
    for label, reply in [("words before the path", f"Wrote my findings to {bad} — 1 items (P2 1)"),
                         ("'Wrote the file <path>'", f"Wrote the file {bad}"),
                         ("a backticked path after words", f"Wrote findings to `{bad}` — 1 items"),
                         ("a full stop after the path", f"Wrote {bad}.")]:
        code, err = run_gate(worker, reply)
        check(f"seat check: the file is still read when the Wrote line has {label}", code == 2 and "line 2" in err, err)
    big = os.path.join(seats, "big.md")
    write(big, "# Big — x (council-review)\nref: none\n## Index\n" + ("x" * 17000) + "\n")
    code, err = run_gate(worker, f"Wrote {big} — 1 items")
    check("seat check: an oversized file blocks", code == 2 and "16 KB" in err, err)
    check("seat check: the size is shown to one decimal, never as the limit itself", "the file is 16.7 KB" in err, err)
    listy = os.path.join(seats, "listy.md")
    write(listy, "# Listy — Security (council-review)\nref: none\n## Index\nMost important first:\n"
                 "- 1 · P2 · Principle 3 · a.py:1 · x\n\n### 1. x\nThe body.\n")
    code, err = run_gate(worker, f"Wrote {listy} — 1 items (P2 1)")
    check("seat check: list-style index lines and prose under the Index pass", code == 0, err)
    messy = os.path.join(seats, "messy.md")
    write(messy, "# Messy — x (council-review)\nref: none\n## Index\n1) P2 — no separators at all\n")
    code, err = run_gate(worker, f"Wrote {messy} — 1 items")
    check("seat check: an index line it can't read blocks", code == 2 and "aren't in the index format" in err, err)
    thin = os.path.join(seats, "thin.md")
    write(thin, "# Thin — x (council-review)\nref: none\n## Index\n1 · P2 · just a title\n")
    code, err = run_gate(worker, f"Wrote {thin} — 1 items")
    check("seat check: an index line with no citation field blocks", code == 2 and "aren't in the index format" in err, err)
    check("seat check: ... and it never also says the Index is empty — the line is there, it can't be read",
          "the Index is empty" not in err, err)
    grouped = os.path.join(seats, "grouped.md")
    write(grouped, "# Grouped — x (council-review)\nref: none\n## Index\n### P1\n**1** · P1 · Principle 1 · a.py:1 · x\n"
                   "### P2 — lower\n2a · P2 · Principle 1 · a.py:2 · y\n\n### 1. x\nThe body · with a dot · and more.\n")
    code, err = run_gate(worker, f"Wrote {grouped} — 2 items")
    check("seat check: items grouped under ### P1 / ### P2, with bold or lettered numbers, pass", code == 0, err)
    # A worker may group its items any way it likes: by area, by file, with an emoji. Telling it the
    # Index is empty when the items are right there sends it to fix what isn't broken.
    for name, heads in [("area", "### Backend"), ("byfile", "### `a.py`"), ("emoji", "### 🔴 P1"),
                        ("nice", "### Nice to have")]:
        own = os.path.join(seats, f"{name}.md")
        write(own, f"# Own — x (council-review)\nref: none\n## Index\n{heads}\n1 · P1 · Principle 1 · a.py:1 · x\n")
        code, err = run_gate(worker, f"Wrote {own} — 1 items")
        check(f"seat check: items grouped under '{heads}' are items, not an empty Index", code == 0, err)
    note = os.path.join(seats, "note.md")
    write(note, "# Note — x (council-review)\nref: none\n## Index\n1 · P1 · Principle 1 · a.py:1 · x\n"
                "   - 3 callers reach it · origin: introduced\n")
    code, err = run_gate(worker, f"Wrote {note} — 1 items")
    check("seat check: an indented note under an item is not an unreadable index line", code == 0, err)
    hollow = os.path.join(seats, "hollow.md")
    write(hollow, "# Hollow — x (council-review)\nref: none\n## Index\n")
    code, err = run_gate(worker, f"Wrote {hollow} — 0 items")
    check("seat check: an empty Index blocks", code == 2 and "the Index is empty" in err, err)
    quiet = os.path.join(seats, "quiet.md")
    write(quiet, "# Quiet — x (council-review)\nref: none\n## Index\n(none) — nothing in my slice\n")
    code, err = run_gate(worker, f"Wrote {quiet} — 0 items")
    check("seat check: an empty lane with a (none) line passes", code == 0, err)
    write(quiet, "# Quiet — x (council-review)\nref: none\n## Index\n- (none) — nothing in my slice\n")
    code, err = run_gate(worker, f"Wrote {quiet} — 0 items")
    check("seat check: an empty lane written as a list line, '- (none)', passes too", code == 0, err)
    uncited = os.path.join(seats, "uncited.md")
    write(uncited, "# Uncited — x (council-review)\nref: none\n## Index\n1 · P1 · Principle 3 · Login has no rate limit\n"
                   "2 · P2 · Principle 1 · src/a.py:12 · Retries forever\n")
    code, err = run_gate(worker, f"Wrote {uncited} — 2 items")
    check("seat check: a review item that names no place blocks, and only that one is counted",
          code == 2 and "1 review item(s) name no place" in err, err)
    write(uncited, "# Uncited — x (council-plan)\nref: none\n## Index\n1 · P1 · Principle 3 · Login has no rate limit\n")
    code, err = run_gate(worker, f"Wrote {uncited} — 1 items")
    check("seat check: ... but in a plan an item may name an area, so the same line passes", code == 0, err)
    code, err = run_gate(worker, "I looked at some things")
    check("seat check: no 'Wrote' line blocks", code == 2 and "Wrote <output path>" in err, err)
    check("seat check: the block message offers the BLOCKED way out", "BLOCKED: <reason>" in err, err)
    code, err = run_gate(worker, "I looked at some things", active=True)
    check("seat check: never blocks twice (stop_hook_active)", code == 0, err)
    code, err = run_gate(worker, "I looked at some things", active=True, compact=True)
    check("seat check: never blocks twice — compact JSON, as Claude Code writes it", code == 0, err)
    for label, raw in [("a space before the colon", '{"stop_hook_active" : true, "agent_type":"%s","last_assistant_message":"x"}'),
                       ("a line break after the colon", '{"agent_type":"%s","last_assistant_message":"x","stop_hook_active":\ntrue}')]:
        code, err = run_gate(worker, "", payload=raw % worker)
        check(f"seat check: never blocks twice — {label}", code == 0, err)
    code, err = run_gate(worker, 'I set "stop_hook_active": true myself', compact=True)
    check("seat check: stop_hook_active written inside the reply doesn't count", code == 2, err)
    code, err = run_gate(worker, "BLOCKED: cannot read the brief")
    check("seat check: BLOCKED passes through", code == 0, err)
    code, err = run_gate(worker, "Read the dispatch.\nBLOCKED: the brief is missing")
    check("seat check: a BLOCKED line after other text passes", code == 0, err)
    for form in ["**BLOCKED:** the brief is missing", "Blocked: the brief is missing", "  BLOCKED: the brief is missing",
                 "> BLOCKED: the brief is missing"]:
        code, err = run_gate(worker, form)
        check(f"seat check: a BLOCKED reply written as {form.split(' the')[0]!r} passes", code == 0, err)
    code, err = run_gate(worker, "I was not BLOCKED, I just stopped early")
    check("seat check: 'BLOCKED' mid-sentence is not a BLOCKED reply", code == 2, err)
    code, err = run_gate(worker, "Unblocked the queue; nothing else to report")
    check("seat check: a word that only contains 'blocked' is not a BLOCKED reply", code == 2, err)
    for label, reply in [("a finding bullet that starts with 'Blocked'",
                          "I reviewed the auth module and found 3 issues:\n* Blocked users can still log in (P1)\n* Tokens never expire (P2)"),
                         ("a bold 'Blocked' in a later line", "1 CONFIRMED — the retry loop\n**Blocked** accounts: not relevant"),
                         ("a 'Blocked:' tally after a heading", "Summary\nBlocked: 0, allowed: 12")]:
        code, err = run_gate(worker, reply)
        check(f"seat check: {label} is not a BLOCKED reply", code == 2 and "Wrote <output path>" in err, err)
    spaced = os.path.join(tmp, "plugin root", "John Smith")          # a user name with a space
    for d in ("hooks", "bin"):
        shutil.copytree(os.path.join(ROOT, d), os.path.join(spaced, d))
    with open(os.path.join(ROOT, "hooks", "hooks.json"), encoding="utf-8") as f:
        stop_cmds = [h["command"] for g in json.load(f)["hooks"]["SubagentStop"] for h in g["hooks"]]
    for cmd in stop_cmds:
        code, err = run_gate(worker, "I looked at some things", command=cmd, env={"CLAUDE_PLUGIN_ROOT": spaced})
        check("seat check: hooks.json's command runs from a plugin folder with a space in its path",
              code == 2 and "Small Council seat check" in err, err)
    code, err = run_gate("general-purpose", "hello")
    check("seat check: other agent types pass through", code == 0, err)
    ver = os.path.join(tmp, "run", "verify-1.md")
    write(ver, "# Verification — eval\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n| 1 | a | CONFIRMED | x |\n")
    code, err = run_gate(verifier, f"Wrote {ver} — 1 confirmed, 0 refuted, 0 uncertain, 0 miscited")
    check("seat check: a valid verifier file passes", code == 0, err)
    code, err = run_gate(verifier, f"Wrote {good} — 1 confirmed")
    check("seat check: a verifier file must be a verification", code == 2 and "# Verification" in err, err)
    tableless = os.path.join(tmp, "run", "verify-3.md")
    write(tableless, "# Verification — eval\nAll four items hold up.\n")
    code, err = run_gate(verifier, f"Wrote {tableless} — 4 confirmed")
    check("seat check: a verifier file with its title but no verdict table blocks", code == 2 and "verdict table" in err, err)
    for label, reply in [("'Wrote verdicts to <path>'", f"Wrote verdicts to {tableless} — 4 confirmed"),
                         ("a full stop after the path", f"Wrote {tableless}.")]:
        code, err = run_gate(verifier, reply)
        check(f"seat check: a verifier file with no verdict table blocks — {label}", code == 2 and "verdict table" in err, err)
    code, err = run_gate(verifier, "1 OK — no assertion weakened; 2 OK — tests exercise behaviour; 3 INCOMPLETE — a mutant survives")
    check("seat check: a verifier that wrote no file is told the verifier's reply, not the worker's",
          code == 2 and "verify-" in err and "<N> items" not in err, err)
    bigver = os.path.join(tmp, "run", "verify-4.md")
    write(bigver, "# Verification — eval\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n| 1 | a | INCOMPLETE | x |\n"
                  + ("The owner filter is missing here. " * 500) + "\n")
    code, err = run_gate(verifier, f"Wrote {bigver} — 0 ok, 1 incomplete")
    check("seat check: an oversized verifier file is told to shorten its paragraphs and keep every row",
          code == 2 and "keep every row" in err and "item cap" not in err and "the file is 16." in err, err)
    bomver = os.path.join(tmp, "run", "verify-5.md")
    write(bomver, "﻿# Verification — eval\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n| 1 | a | OK | x |\n")
    code, err = run_gate(verifier, f"Wrote {bomver} — 1 ok")
    check("seat check: a verifier file with a byte-order mark passes", code == 0, err)
    r2 = os.path.join(seats, "leach-r2.md")
    write(r2, "# Leach — Data integrity (council-plan, round 2)\nref: Data Reference\nquestion: q\n## Index\n"
              "1 · hold · P1 fowler#4 · a.py:1 · one table: the join exists\n2 · concede · hunt#1 · src/ · scoped tokens\n"
              "### 1. one table\n- Stance: hold\n## Riskiest assumption\nleach#2 — the join is indexed — schema.sql\n")
    code, err = run_gate(worker, f"Wrote {r2} — 2 items (hold 1, concede 1)")
    check("seat check: a war-room round-2 file passes", code == 0, err)
    prose = os.path.join(seats, "prose-r2.md")
    write(prose, "# Prose — x (council-plan, round 2)\nref: none\n## Index\n1 — I hold my position on P1 · mostly\n")
    code, err = run_gate(worker, f"Wrote {prose} — 1 items")
    check("seat check: round-2 stances written as prose are blocked", code == 2 and "aren't in the index format" in err, err)
    met = os.path.join(tmp, "run", "verify-2.md")
    write(met, "# Verification — post-game\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
               "| 1 | export | MET | src/x.py:4 · tested: no |\n| 2 | owner filter | NOT MET | no filter found |\n"
               "| M1 | admins only | NOT MET | asked, no part covers it |\n")
    code, err = run_gate(verifier, f"Wrote {met} — 1 met, 0 partly met, 2 not met, 0 can't tell, 1 missing, 0 not asked")
    check("seat check: a post-game verifier file passes", code == 0, err)
    # The claim index's own reading of a review's verifier table (evidence.py table): in run 1 the stop
    # check passed a table the index couldn't read, and the Chair fixed the blind verifier's file by hand.
    review_run = os.path.join(tmp, "review-run")
    write(os.path.join(review_run, "session-state.md"), "status: in-progress\nmode: council-review\n")
    write(os.path.join(review_run, "synthesis.md"), "# Synthesis\n## Kept\n"
          "1 · P1 · P · a.py:1 · One · state: OBSERVED · from: hunt#1\n"
          "2 · P2 · P · a.py:2 · Two · state: OBSERVED · from: hunt#1\n## Cut\n(none)\n")
    claimed = os.path.join(review_run, "verify-1.md")
    head = "# Verification — eval\n\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
    for label, body, reason in [
            ("another heading", "# Verification — eval\n| # | Claim | Verdict | Notes |\n|---|---|---|---|\n"
                                "| 1 | One | CONFIRMED | a.py:1 |\n| 2 | Two | REFUTED | a.py:2 |\n", "heading isn't"),
            ("a number the synthesis doesn't have", head + "| 1 | One | CONFIRMED | a.py:1 |\n"
                                                          "| 9 | Two | REFUTED | a.py:2 |\n", "unknown claim 9"),
            ("two verdicts in one cell", head + "| 1 | One | CONFIRMED or REFUTED | a.py:1 |\n"
                                               "| 2 | Two | REFUTED | a.py:2 |\n", "ambiguous claim verdict")]:
        write(claimed, body)
        code, err = run_gate(verifier, f"Wrote {claimed} — 1 confirmed, 1 refuted")
        check(f"seat check: a review verifier table the claim index can't read is sent back — {label}",
              code == 2 and reason in err and "Fix the file" in err, err)
    write(claimed, "# Verification — eval\n| # | Item | Verdict | Evidence (path:line) |\n|---|---|---|---|\n"
                   "  | **1** | One | **CONFIRMED** | `grep x a.py | wc -l` is 1\n| #2 | Two | REFUTED — guarded | a.py:2 |\n")
    code, err = run_gate(verifier, f"Wrote {claimed} — 1 confirmed, 1 refuted")
    check("seat check: a review verifier table the index reads (bold, #2, a | in the evidence, no closing pipe) passes",
          code == 0, err)

@part("main")
def bash_gate(tmp):
    # --- PreToolUse pipe stop: the helper's output piped into head, tail or grep is refused. The rule lived
    # only in prose and was broken 133 times across three sessions, again after every warning ------------
    with open(os.path.join(ROOT, "hooks", "hooks.json"), encoding="utf-8") as f:
        pre_groups = json.load(f)["hooks"].get("PreToolUse", [])
    groups = [g for g in pre_groups if any("hooks/bash-gate.sh" in h.get("command", "") for h in g.get("hooks", []))]
    cmd = next((h["command"] for g in groups for h in g["hooks"] if "hooks/bash-gate.sh" in h["command"]),
               "echo 'no bash gate in hooks.json' >&2; exit 1")   # with no gate, no check below can pass
    matcher = groups[0].get("matcher") if groups else None
    taken = [n for n in ("Bash", "BashOutput", "PowerShell", "Agent", "Task", "Read") if matcher and re.search(matcher, n)]
    check("pipe stop: hooks.json runs bash-gate.sh before a Bash call — no other tool — with a timeout of 5 s at most",
          len(groups) == 1 and taken == ["Bash"] and all(h.get("timeout", 99) <= 5 for h in groups[0]["hooks"]),
          f"matcher {matcher!r} takes {taken} · {json.dumps(groups)}")
    here = new_repo(tmp, "pipe-stop")

    def bash_input(command):
        return json.dumps({"session_id": "sA", "transcript_path": "/x/t.jsonl", "cwd": here, "permission_mode": "default",
                           "hook_event_name": "PreToolUse", "tool_name": "Bash",
                           "tool_input": {"command": command, "description": "Check the run"}}, separators=(",", ":"))

    def said(code, out, err):
        return f"exit {code} · stdout {out.strip()[:80]!r} · stderr {err.strip()}"

    for command in ("council run status | tail -20",
                    "council collect 2>&1 | head -5",
                    "council gate --all |& tail",
                    "council doctor | grep -c FAIL",
                    'bash "/home/u/.claude/plugins/small-council/bin/council" run status 2>&1 | tail -30',
                    "bash ~/.claude/plugins/small-council/bin/council run status | tail",
                    "cd app && COUNCIL_RUN=x council run status | head -3",
                    "for s in hunt beck; do council seat $s done; done 2>&1 | tail -2",
                    "{ council run status; council doctor; } | head",
                    "council run status | sort | head",
                    "x=$(council run status | head -1)",
                    'C="bash /opt/sc/bin/council"; $C run status | tail',
                    "council run status\ncouncil doctor | tail"):
        code, out, err, _ = run_agent_gate(cmd, bash_input(command), here)
        check(f"pipe stop refuses {command!r} — exit 2, one line on stderr: run it plain, or redirect it to a file",
              code == 2 and not out and err.count("\n") == 1 and "run council plain" in err and "exit status" in err
              and "redirect it to a file (council … > out.txt) and read that" in err, said(code, out, err))
    for command in ("council run status",
                    "council run status > out.txt",
                    "council collect > out.txt 2>&1; tail -20 out.txt",
                    "council run status | tee out.txt",
                    "grep council notes.md | head",
                    "git log --oneline | grep council | head",
                    'git commit -m "Refuse council run status | tail"',
                    "echo 'council doctor | grep FAIL'",
                    "git commit -m \"$(cat <<'EOF'\nRefuse `council run status | head`\ncouncil doctor | tail\nEOF\n)\"",
                    "council run status # | tail",
                    "command -v council | head -1",
                    "council run status | wc -l",
                    'echo "council run status | head'):           # can't be parsed: let through
        code, out, err, _ = run_agent_gate(cmd, bash_input(command), here)
        check(f"pipe stop lets {command!r} through, silently", code == 0 and not out and not err, said(code, out, err))
    for label, raw in (("garbage", "\x00council | tail{{{"), ("an empty input", ""),
                       ("a command outside tool_input", '{"tool_name":"Bash","command":"council run status | tail"}'),
                       ("the pipe only in the description",
                        json.dumps({"tool_name": "Bash", "tool_input": {"description": "council x | tail", "command": "ls | tail"}}))):
        code, out, err, _ = run_agent_gate(cmd, raw, here)
        check(f"pipe stop: {label} — the call goes ahead, nothing said", code == 0 and not out and not err, said(code, out, err))


@part("main")
def hooks_running(tmp):
    # --- A session whose hooks don't run (the plugin was enabled after it started) can't open a run: a whole
    # night ran with no agent stop and no seat check, and Claude was told to reload once, in a sub-bullet ---
    plain = new_repo(tmp, "marks-no-council")
    code, out = run_hook(plain, session="s-started")
    check("session mark: the SessionStart hook marks its session even where there is no council home, saying nothing",
          code == 0 and out.strip() == "" and os.path.isfile(os.path.join(marks(), "s-started")), out)

    late = new_repo(tmp, "no-hooks")
    write(os.path.join(late, ".council", "council.config.md"), "# Council config\n")
    code, out, err = council(late, "run", "open", "council-review", session="s-late", hooks=False)
    check("run open: a session its SessionStart hook never marked is refused — exit 2, restart the session, "
          "the escape named in the refusal", code == 2 and "hooks aren't running in this session" in err
          and "Restart the session (or run /reload-plugins and start a new one)" in err
          and "COUNCIL_ALLOW_NO_HOOKS=1 council run open council-review" in err, f"exit {code} · {out} · {err}")
    check("run open: ... and the refusal opens nothing", not os.path.exists(os.path.join(late, ".council", "runs")),
          str(os.listdir(os.path.join(late, ".council"))))
    run_hook(late, session="s-late")                                  # the session restarted with the plugin on
    code, out, err = council(late, "run", "open", "council-review", session="s-late", hooks=False)
    check("run open: once the session's SessionStart hook has run, the run opens", code == 0 and os.path.isdir(out), out + err)

    for label, repo, session, env in (("with no session id (scripts, tests), nothing is checked", "no-session", "", None),
                                      ("COUNCIL_ALLOW_NO_HOOKS=1 opens it for a user who insists", "insists", "s-insists",
                                       {"COUNCIL_ALLOW_NO_HOOKS": "1"}),
                                      ("a session id that can't be a file name is never refused on a guess", "odd-id",
                                       "../x", None)):
        r = new_repo(tmp, repo)
        write(os.path.join(r, ".council", "council.config.md"), "# Council config\n")
        code, out, err = council(r, "run", "open", "council-review", session=session, hooks=False, env=env)
        check(f"run open: {label}", code == 0 and os.path.isdir(out), out + err)
    run_hook(plain, session="../x")
    check("session mark: a session id that can't be a file name leaves no file anywhere",
          not os.path.exists(os.path.join(marks(), "..", "x")) and not os.path.exists(os.path.join(marks(), "x")),
          " ".join(sorted(os.listdir(os.path.dirname(marks())))) if os.path.isdir(os.path.dirname(marks())) else "")


@part("main")
def worktree_session(tmp):
    # --- A session in a linked worktree can't drive a run whose code is elsewhere: a handoff into an app-made
    # worktree cost 21.6 minutes and six refused edits, and the plugin's only warning was one table cell ---
    main = new_repo(tmp, "wt-warn")
    mtop = git(main, "rev-parse", "--show-toplevel")
    write(os.path.join(main, ".council", "council.config.md"), "# Council config\n")
    tree = os.path.join(main, ".claude", "worktrees", "app-made")
    git(main, "worktree", "add", "-q", tree, "-b", "app-made")
    wtop = git(tree, "rev-parse", "--show-toplevel")

    def start(project, cwd):
        return run_hook(project, payload=json.dumps({"session_id": "s-wt", "transcript_path": "/x/t.jsonl", "cwd": cwd,
                                                     "hook_event_name": "SessionStart", "source": "startup"}))

    code, out = start(tree, tree)
    check("worktree session with no open run: no worktree warning", code == 0 and "linked worktree" not in out, out)
    _, mrun, _ = council(main, "run", "open", "council-implement", session="s-main")
    mname = os.path.basename(mrun)
    code, out = start(tree, tree)
    first = out.splitlines()[0] if out.strip() else ""
    check("worktree session while a run's code is in the main checkout: warned first — the worktree, the run, "
          "where its code is, and where to start a session instead",
          first.startswith(f"[Small Council] This session runs in a linked worktree ({wtop}). Claude Code may refuse "
                           f"edits outside it, and run {mname}'s code is in {mtop}. To drive that run, start a session "
                           f"in {mtop} with the worktree option off."), out)
    code, out = start(main, main)
    check("a session in the main checkout: no worktree warning", code == 0 and "linked worktree" not in out, out)

    own = new_repo(tmp, "wt-own")
    write(os.path.join(own, ".council", "council.config.md"), "# Council config\n")
    otree = os.path.join(own, ".claude", "worktrees", "feat")
    git(own, "worktree", "add", "-q", otree, "-b", "feat")
    _, orun, _ = council(otree, "run", "open", "council-implement", session="s-own")   # its code root: this worktree
    code, out = start(otree, otree)
    check("worktree session whose open run's code is this worktree: the run is reported, with no worktree warning",
          code == 0 and "linked worktree" not in out and bool(orun) and os.path.basename(orun) in out, out)


@part("main")
def agent_gate_dispatch_record(tmp):
    # The agent gate holds Small Council's own agents to the record, through hooks.json's own commands: a real
    # run sent a verifier 9 s before its plan row existed, and an 11th agent after the run had closed.
    with open(os.path.join(ROOT, "hooks", "hooks.json"), encoding="utf-8") as f:
        wired = json.load(f)["hooks"]
    gate_cmd = next(h["command"] for g in wired["PreToolUse"] for h in g["hooks"] if "hooks/agent-gate.sh" in h["command"])
    stop_cmd = next(h["command"] for g in wired["Stop"] for h in g["hooks"] if "hooks/turn-end.sh" in h["command"])
    worker, verifier = "small-council:council-worker", "small-council:council-verifier"

    def said(code, out, err):
        return f"exit {code} · stdout {out.strip()[:80]!r} · stderr {err.strip()[:300]}"

    def gate(cwd, subagent, prompt, session="sD", tool="Agent", before=None):
        return run_agent_gate(gate_cmd, dispatch_input(session, cwd, subagent, prompt, tool, before), cwd)[:3]

    def starts(run):
        path = os.path.join(run, "agent-starts.tsv")
        return open(path, encoding="utf-8").read().count("\tAgent\t") if os.path.exists(path) else 0

    bare = new_repo(tmp, "dispatch-gate-bare")
    code, out, err = gate(bare, worker, "Seat: hunt — x\nWrite seats/hunt.md, then return one line.")
    check("dispatch: no council home — a council-worker starts, nothing said", code == 0 and not out and not err,
          said(code, out, err))
    dg = new_repo(tmp, "dispatch-gate")
    write(os.path.join(dg, ".council", "council.config.md"), "# Council config\n")
    code, out, err = gate(dg, worker, "Seat: hunt — Security · review run\nWrite /x/seats/hunt.md, then return one line.")
    check("dispatch: a council-worker with no council run open is refused — exit 2, the reason on stderr, nothing on stdout",
          code == 2 and not out and "no council run is open on this working tree or for this session" in err, said(code, out, err))
    code, out, err = gate(dg, "general-purpose", "Seat: hunt — Security · review run\nWrite /x/seats/hunt.md.")
    check("dispatch: an ordinary agent given the same message starts — only Small Council's own agents are held to it",
          code == 0 and not err, said(code, out, err))
    code, out, err = gate(dg, verifier, "Check the changed tests.\nWrite your verdicts to /tmp/xyz/verify-1.md, then reply.")
    check("dispatch: a council-verifier writing outside any run (test-architect's own check) starts with no run open",
          code == 0 and not err, said(code, out, err))
    code, out, err = gate(dg, "general-purpose", "Seat: hunt\nWrite /x/seats/hunt.md", before={"subagent_type": worker})
    check("dispatch: the agent type is read from the call's own tool_input — never a top-level field or other text",
          code == 0 and not err, said(code, out, err))
    _, grun, _ = council(dg, "run", "open", "council-review", session="sD")
    gname = os.path.basename(grun)
    valid_plan(grun, seats=("chair", "hunt"))
    orders = "Seat: {0} — Security · review run\nBrief: {1}/brief.md — read the top and your block\nWrite {1}/seats/{0}.md, then return one line."
    code, out, err = gate(dg, worker, orders.format("beck", grun))
    check("dispatch: a council-worker for a seat the plan doesn't select is refused, before it starts, and is not counted",
          code == 2 and "seat beck has no selected row in the run plan of " + gname in err and starts(grun) == 0,
          said(code, out, err))
    code, out, err = gate(dg, worker, "Look at the change.\nWrite {0}/seats/beck.md, then return one line.".format(grun))
    check("dispatch: with no Seat: line, the seat is read from the file the worker writes", code == 2 and "seat beck" in err,
          said(code, out, err))
    code, out, err = gate(dg, worker, orders.format("hunt", grun))
    check("dispatch: a council-worker for a selected seat of the open run starts, and is counted", code == 0 and not err
          and starts(grun) == 1, said(code, out, err))
    code, out, err = gate(dg, worker, "Seat: hunt\nWrite {0}/seats/hunt.md".format(grun), tool="Workflow")
    check("dispatch: a Workflow names no agent type of its own — never held to it", code == 0 and not err, said(code, out, err))
    council(dg, "seat", "hunt", "running", "agent=h1", session="sD")
    code, out, err, _ = run_agent_gate(stop_cmd, stop_input("sD", dg), dg)
    check("turn end: after the run's first dispatch, with no status shown, the Chair is sent back once to show it",
          code == 2 and not out and "made its first dispatch" in err and "council status --widget --run " + gname in err,
          said(code, out, err))
    code, out, err, _ = run_agent_gate(stop_cmd, stop_input("sD", dg), dg)
    check("turn end: ... and the next turn end says nothing", code == 0 and not out and not err, said(code, out, err))
    council(dg, "run", "close", "--status", "abandoned", session="sD")
    check_orders = "Check claim 1.\nThe brief: {0}/brief.md\nWrite your verdicts to {0}/verify-plan.md, then reply in one line."
    code, out, err = gate(dg, verifier, check_orders.format(grun))
    check("dispatch: a council-verifier for a run that has closed is refused", code == 2 and "which is closed (abandoned)" in err,
          said(code, out, err))
    code, out, err = gate(dg, verifier, check_orders.format(grun.replace("/", "\\")))
    check("dispatch: ... found from a Windows path too (backslashes, escaped in the JSON)", code == 2 and gname in err,
          said(code, out, err))
    for label, raw in (("garbage", "\x00not json at all"), ("a truncated call", '{"session_id":"sD","cwd":"%s",'
                       '"tool_name":"Agent","tool_input":{"subagent_type":"%s","prompt":"Seat: hu' % (dg, worker))):
        code, out, err, _ = run_agent_gate(gate_cmd, raw, dg)
        check(f"dispatch: {label} — the agent starts, nothing said", code == 0 and not out and not err, said(code, out, err))
    # A third check of one build task, refused before it starts (council-implement, step 7).
    tg = new_repo(tmp, "dispatch-gate-third")
    write(os.path.join(tg, ".council", "council.config.md"), "# Council config\n")
    _, trun, _ = council(tg, "run", "open", "council-implement", session="sE")
    valid_plan(trun, seats=("chair", "verify-6", "verify-6b", "verify-6c"), mode="council-implement")
    for slug, n in (("verify-6", 1), ("verify-6b", 2)):
        write(os.path.join(trun, slug + ".md"), "# Verification — x\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
              "| 1 | a | INCOMPLETE | a.py:1 |\n")
        council(tg, "seat", slug, "running", f"agent=v{n}", session="sE")
        council(tg, "seat", slug, "done", "tokens=20000", session="sE")
    recheck = ("Check task 6 again.\nDiff: {0}/diff-6.patch\nThe last verdict: {0}/verify-6b.md\n"
               "Write your verdicts to {0}/verify-6c.md, then reply in one line.").format(trun)
    code, out, err = gate(tg, verifier, recheck, session="sE")
    check("dispatch: a third check of one task, after two verdicts with no diagnosis or decision since, is refused before "
          "it starts — the file it writes names it, not the earlier verdict the message mentions",
          code == 2 and "cannot start verify-6c" in err and "third check of task 6" in err, said(code, out, err))


@part("timing")
def turn_end(tmp):
    # --- Stop hook: the run notices when the Chair stops for the user (promised-4: across 33 real sessions
    # no waiting state was recorded and no alert sent; the rule lived only in the Chair's memory) ----------
    with open(os.path.join(ROOT, "hooks", "hooks.json"), encoding="utf-8") as f:
        stop_groups = json.load(f)["hooks"].get("Stop", [])
    hooks_here = [h for g in stop_groups for h in g.get("hooks", []) if "hooks/turn-end.sh" in h.get("command", "")]
    cmd = hooks_here[0]["command"] if hooks_here else "echo 'no turn-end hook in hooks.json' >&2; exit 1"
    check("turn end: hooks.json runs turn-end.sh when a turn ends, with a 15 s timeout",
          len(hooks_here) == 1 and hooks_here[0].get("timeout") == 15, json.dumps(stop_groups))

    def said(code, out, err):
        return f"exit {code} · stdout {out.strip()[:80]!r} · stderr {err.strip()}"

    bare = new_repo(tmp, "turn-no-council")
    code, out, err, took = run_agent_gate(cmd, stop_input("sA", bare), bare)
    check("turn end: no council home — the turn ends, nothing said, well inside the 15 s limit",
          code == 0 and not out and not err and took < 10, said(code, out, err) + " · {:.1f} s".format(took))
    te = new_repo(tmp, "turn-end")
    write(os.path.join(te, ".council", "council.config.md"), "# Council config\n")
    code, out, err, _ = run_agent_gate(cmd, stop_input("sA", te), te)
    check("turn end: a council with no open run — the turn ends, nothing said", code == 0 and not out and not err,
          said(code, out, err))
    _, out, _ = council(te, "run", "open", "council-review", session="sA")
    run = out.splitlines()[-1]
    name, st = os.path.basename(run), os.path.join(run, "session-state.md")
    valid_plan(run)

    def waiting():
        m = re.search(r"^waiting:[ \t]*(.*)$", open(st, encoding="utf-8").read(), re.MULTILINE)
        return m.group(1).strip() if m else ""

    code, out, err, _ = run_agent_gate(cmd, stop_input("sB", te), te)
    check("turn end: another session's turn never touches this run", code == 0 and not err and not waiting(), said(code, out, err))
    code, out, err, _ = run_agent_gate(cmd, stop_input("sA", te, active=True), te)
    check("turn end: a stop the hook already sent back ends there — nothing said, nothing recorded",
          code == 0 and not err and not waiting(), said(code, out, err))
    council(te, "seat", "w1", "running", "agent=a1", session="sA")
    code, out, err, _ = run_agent_gate(cmd, stop_input("sA", te), te)
    check("turn end: the run's first dispatch, its status not yet shown, sends the Chair back once for the card — and "
          "records no wait, since a seat is working",
          code == 2 and "made its first dispatch" in err and not waiting(), said(code, out, err))
    code, out, err, _ = run_agent_gate(cmd, stop_input("sA", te), te)
    check("turn end: with a seat still working the run waits on its agent, not the user — nothing said or recorded",
          code == 0 and not err and not waiting(), said(code, out, err))
    council(te, "seat", "w1", "queued", session="sA")              # planned, not started: no agent is at work
    code, out, err, _ = run_agent_gate(cmd, stop_input("sA", te), te)
    check("turn end: a seat only queued is no agent at work — the wait is recorded", code == 2 and waiting() != "",
          said(code, out, err))
    council(te, "state", "phase=prepare", session="sA")
    council(te, "seat", "w1", "done", "agent=a1", "tokens=20000", session="sA")
    code, out, err, took = run_agent_gate(cmd, stop_input("sA", te), te)
    check("turn end: the driving session stops with no seat working — the wait is recorded, and the Chair is sent "
          "back once to alert the owner with council status --line (exit 2, the reason on stderr, nothing on stdout)",
          code == 2 and not out and f"council status --line --run {name}" in err and "PushNotification" in err
          and "unless you already sent" in err and waiting() != "", said(code, out, err))
    check("turn end: the wait is an event in the run's stream",
          any(e.split("\t")[3:6] == ["run.waiting_changed", "run", "on"]
              for e in open(os.path.join(run, "events.tsv"), encoding="utf-8").read().splitlines()[1:]))
    check("turn end: sending the Chair back comes well inside the 15 s limit", took < 10, f"{took:.1f} s")
    code, out, err, _ = run_agent_gate(cmd, stop_input("sA", te), te)
    check("turn end: the next turn end of the same wait says nothing — never twice for one wait",
          code == 0 and not out and not err, said(code, out, err))
    council(te, "state", "phase=assign", session="sA")
    check("turn end: the next helper action (a stage change) ends the wait", waiting() == "", waiting())
    council(te, "state", "waiting=Ship the plan as it is, or cut task 3?", session="sA")
    code, out, err, _ = run_agent_gate(cmd, stop_input("sA", te), te)
    check("turn end: the Chair's own question is kept, and not asked about again — the helper asked for the alert "
          "when it was recorded, so the owner gets one alert per wait",
          code == 0 and not err and waiting() == "Ship the plan as it is, or cut task 3?", said(code, out, err))
    council(te, "seat", "w1", "done", "agent=a1", "tokens=25000", session="sA")
    check("turn end: a seat record ends the wait too", waiting() == "", waiting())
    with open(os.path.join(te, ".council", "council.config.md"), "a", encoding="utf-8") as f:
        f.write("- notifications: off\n")
    code, out, err, _ = run_agent_gate(cmd, stop_input("sA", te), te)
    check("turn end: with notifications off, the wait is still recorded but nobody is sent back",
          code == 0 and not out and not err and waiting() != "", said(code, out, err))
    council(te, "cap", "allow", "1", "--user-said", "yes, one more", session="sA")
    check("turn end: the user's go (cap allow) ends the wait", waiting() == "", waiting())


@part("timing")
def agent_gate(tmp):
    # --- PreToolUse agent gate -----------------------------------------------------------------
    with open(os.path.join(ROOT, "hooks", "hooks.json"), encoding="utf-8") as f:
        pre_groups = json.load(f)["hooks"].get("PreToolUse", [])
    gate_groups = [g for g in pre_groups if any("hooks/agent-gate.sh" in h.get("command", "") for h in g.get("hooks", []))]
    gate_cmd = next((h["command"] for g in gate_groups for h in g["hooks"] if "hooks/agent-gate.sh" in h["command"]),
                    "echo 'no agent gate in hooks.json' >&2; exit 1")   # with no gate, no check below can pass
    check("agent gate: hooks.json runs agent-gate.sh before a tool call, with a 15 s timeout",
          len(gate_groups) == 1 and all(h.get("timeout") == 15 for h in gate_groups[0]["hooks"]), json.dumps(pre_groups))
    matcher = gate_groups[0].get("matcher") if gate_groups else None
    taken = [n for n in ("Agent", "Task", "Workflow", "TaskCreate", "TaskStop", "TaskOutput", "Bash", "SendMessage")
             if matcher and re.search(matcher, n)]
    check("agent gate: the matcher takes Agent, Task and Workflow — never TaskCreate, TaskStop or Bash",
          taken == ["Agent", "Task", "Workflow"], f"matcher {matcher!r} takes {taken}")

    bare_home = new_repo(tmp, "no-council")   # a repo with no council home

    def said(code, out, err):
        return f"exit {code} · stdout {out.strip()[:80]!r} · stderr {err.strip()}"

    code, out, err, _ = run_agent_gate(gate_cmd, pre_tool("sA", bare_home), bare_home)
    check("agent gate: no council home — the agent starts, nothing said", code == 0 and not out and not err, said(code, out, err))
    cap3 = new_repo(tmp, "agent-gate")
    write(os.path.join(cap3, ".council", "council.config.md"), "# Council config\n## Run preferences\n- agent cap: 3\n")
    code, out, err, _ = run_agent_gate(gate_cmd, pre_tool("sA", cap3), cap3)
    check("agent gate: a council with no open run — the agent starts", code == 0 and not out and not err, said(code, out, err))
    _, grun, _ = council(cap3, "run", "open", "council-review", session="sA")
    gname = os.path.basename(grun)
    council(cap3, "seat", "w1", "done", "agent=a1", "agents=2", "tokens=20000")
    code, out, err, _ = run_agent_gate(gate_cmd, pre_tool("sA", cap3), cap3)
    check("agent gate: 2 of 3 agent runs used — the agent starts", code == 0 and not out and not err, said(code, out, err))
    council(cap3, "seat", "w2", "done", "agent=a2", "tokens=10000")
    code, out, err, took = run_agent_gate(gate_cmd, pre_tool("sA", cap3), cap3)
    check("agent gate: at the cap (3 of 3) the agent is refused — exit 2, the reason on stderr, nothing on stdout",
          code == 2 and not out and "3 of its 3 agent runs" in err and gname in err, said(code, out, err))
    check("agent gate: the reason says to ask the user, and how their go lifts the stop",
          "ask whether to continue" in err and f"council cap allow <n> --run {gname} --user-said" in err, err)
    check("agent gate: a refusal, its longest path, comes well inside the 15 s limit", code == 2 and took < 10,
          f"exit {code}, {took:.1f} s")
    code, out, err, _ = run_agent_gate(gate_cmd, pre_tool("sA", cap3, tool="Workflow"), cap3)
    check("agent gate: a Workflow is refused too", code == 2, said(code, out, err))
    code, out, err, _ = run_agent_gate(gate_cmd, pre_tool("sB", cap3), cap3)
    check("agent gate: a run another session drives never stops this session's agents", code == 0 and not err, said(code, out, err))
    code, out, err, _ = run_agent_gate(gate_cmd, pre_tool(None, cap3), cap3)
    check("agent gate: an input with no session id — every in-progress run on this tree counts", code == 2, said(code, out, err))
    # The run is found from the input's own cwd, read at the top level only.
    if os.name == "nt":
        far, label = cap3.replace("/", "\\"), "a Windows cwd (C:\\…, its backslashes escaped in the JSON)"
    else:
        far, label = os.path.join(tmp, "back\\slash"), "a cwd with a backslash in it, escaped in the JSON"
        os.symlink(cap3, far)
    code, out, err, _ = run_agent_gate(gate_cmd, pre_tool("sA", far), tmp)
    check(f"agent gate: {label} is found", code == 2 and gname in err, said(code, out, err))
    decoy = {"context": {"session_id": "sB", "cwd": bare_home}, "note": '{"session_id":"sB","cwd":"%s"}' % bare_home}
    code, out, err, _ = run_agent_gate(gate_cmd, pre_tool("sA", cap3, before=decoy,
                                                          prompt='use "cwd": "/nowhere" and \\"session_id\\": \\"sB\\"'), tmp)
    check("agent gate: session_id and cwd come from the top level — never a nested object or text quoted in a value",
          code == 2 and gname in err, said(code, out, err))
    council(cap3, "cap", "allow", "2", "--user-said", "yes, two more")
    code, out, err, _ = run_agent_gate(gate_cmd, pre_tool("sA", cap3), cap3)
    check("agent gate: after council cap allow 2, the agent starts", code == 0 and not err, said(code, out, err))
    council(cap3, "seat", "w3", "done", "agent=a3", "tokens=10000")
    code, out, err, _ = run_agent_gate(gate_cmd, pre_tool("sA", cap3), cap3)
    check("agent gate: ... and so does the second agent run it allowed", code == 0 and not err, said(code, out, err))
    council(cap3, "seat", "w4", "done", "agent=a4", "tokens=10000")
    code, out, err, _ = run_agent_gate(gate_cmd, pre_tool("sA", cap3), cap3)
    check("agent gate: once the two agent runs allowed are recorded, it stops again",
          code == 2 and "5 of its 3 agent runs" in err and "allowed up to 5" in err, said(code, out, err))

    ceil = new_repo(tmp, "agent-gate-ceiling")
    write(os.path.join(ceil, ".council", "council.config.md"), "# Council config\n")
    other_tree = os.path.join(tmp, "agent-gate-other-tree").replace("\\", "/")
    os.makedirs(other_tree)
    _, crun, _ = council(ceil, "run", "open", "council-review", "--code-root", other_tree, session="sC")
    with open(os.path.join(crun, "run-plan.tsv"), "a", encoding="utf-8", newline="") as f:
        f.write("budget\trun\ttoken-ceiling\t50000\towner limit\n")
    council(ceil, "seat", "w1", "done", "agent=c1", "tokens=60000", "--run", os.path.basename(crun))
    code, out, err, _ = run_agent_gate(gate_cmd, pre_tool("sC", ceil), ceil)
    check("agent gate: past the token ceiling but under the cap, the agent is refused (the run's code root is another "
          "tree, but this session drives it)", code == 2 and "60k tokens, over its 50k ceiling" in err, said(code, out, err))
    code, out, err, _ = run_agent_gate(gate_cmd, pre_tool(None, ceil), ceil)
    check("agent gate: with no session id, a run on another working tree is not this tree's", code == 0 and not err,
          said(code, out, err))

    nos = new_repo(tmp, "agent-gate-sessionless")
    write(os.path.join(nos, ".council", "council.config.md"), "# Council config\n- agent cap: 1\n")
    council(nos, "run", "open", "council-review")          # no session id to record
    council(nos, "seat", "w1", "done", "agent=n1", "tokens=5000")
    code, out, err, _ = run_agent_gate(gate_cmd, pre_tool("sX", nos), nos)
    check("agent gate: a run on this tree that recorded no session stops any session's agents", code == 2, said(code, out, err))
    council(nos, "run", "close", "--status", "paused")
    code, out, err, _ = run_agent_gate(gate_cmd, pre_tool("sX", nos), nos)
    check("agent gate: a paused run at its cap stops nothing", code == 0 and not err, said(code, out, err))
    for label, raw in (("garbage", "\x00not json at all"), ("an empty input", ""),
                       ("a truncated object", '{"session_id":"sX","cwd":"')):
        code, out, err, _ = run_agent_gate(gate_cmd, raw, nos)
        check(f"agent gate: {label}, no open run — the agent starts, nothing said", code == 0 and not out and not err,
              said(code, out, err))

@part("timing")
def agent_gate_counts_starts(tmp):
    # The gate counts the agent starts it lets through, so agents started together, or recorded only after
    # they finished, still meet the stop (in a real run a verifier was recorded three minutes after it began).
    with open(os.path.join(ROOT, "hooks", "hooks.json"), encoding="utf-8") as f:
        gate_cmd = next(h["command"] for g in json.load(f)["hooks"]["PreToolUse"] for h in g["hooks"]
                        if "hooks/agent-gate.sh" in h["command"])

    def said(code, err):
        return f"exit {code} · stderr {err.strip()[:200]}"

    def starts(run):
        path = os.path.join(run, "agent-starts.tsv")
        return max(0, len(open(path, encoding="utf-8").read().splitlines()) - 1) if os.path.exists(path) else 0

    fly = new_repo(tmp, "gate-counts")
    write(os.path.join(fly, ".council", "council.config.md"), "# Council config\n- agent cap: 3\n")
    _, frun, _ = council(fly, "run", "open", "council-review", session="sA")
    fname = os.path.basename(frun)
    for _ in range(3):
        council(fly, "cap", "check", "--session", "sA")
    check("agent gate: council cap check with no tool only reads — it counts nothing", starts(frun) == 0, str(starts(frun)))
    codes = [run_agent_gate(gate_cmd, pre_tool("sA", fly), fly)[0] for _ in range(3)]
    code, out, err, _ = run_agent_gate(gate_cmd, pre_tool("sA", fly), fly)
    check("agent gate: three agents started with nothing recorded pass, and the fourth is stopped at the cap of 3",
          codes == [0, 0, 0] and code == 2 and f"run {fname} has used 3 of its 3 agent runs" in err,
          f"{codes} then {said(code, err)}")
    code, out, err = council(fly, "cap", "--run", fname)
    check("cap: counts the agents started through the gate, and says how many are recorded",
          "3 of 3 agent runs used (3 started through the agent gate, 0 recorded)" in out and "stopped" in out, out + err)
    code, out, err, _ = run_agent_gate(gate_cmd, pre_tool("sB", fly), fly)
    check("agent gate: another session's agents are neither stopped nor counted by this run",
          code == 0 and starts(frun) == 3, f"{said(code, err)} · {starts(frun)} starts")
    for i in range(1, 4):
        council(fly, "seat", f"w{i}", "done", f"agent=a{i}", "tokens=20000", "--run", fname)
    code, out, err = council(fly, "cap", "--run", fname)
    code2, _, err2, _ = run_agent_gate(gate_cmd, pre_tool("sA", fly), fly)
    check("agent gate: the same three agents recorded later are not counted twice (3 of 3, not 6)",
          "3 of 3 agent runs used" in out and "started through" not in out and code2 == 2
          and "3 of its 3 agent runs" in err2, out + said(code2, err2))
    council(fly, "cap", "allow", "1", "--run", fname, "--user-said", "one more")
    codes = [run_agent_gate(gate_cmd, pre_tool("sA", fly), fly)[0] for _ in range(2)]
    check("agent gate: after the user's go for one more, one agent starts and the next is stopped", codes == [0, 2], str(codes))

    wf = new_repo(tmp, "gate-counts-workflow")
    write(os.path.join(wf, ".council", "council.config.md"), "# Council config\n- agent cap: 2\n")
    council(wf, "run", "open", "council-review", session="sW")
    codes = [run_agent_gate(gate_cmd, pre_tool("sW", wf, tool=t), wf)[0] for t in ("Workflow", "Agent", "Agent")]
    check("agent gate: a Workflow counts as at least one agent start", codes == [0, 0, 2], str(codes))

    # A Workflow recorded with its agent count: the starts after it are added to that count, not hidden by it.
    wf3 = new_repo(tmp, "gate-counts-workflow-recorded")
    write(os.path.join(wf3, ".council", "council.config.md"), "# Council config\n- agent cap: 5\n")
    _, w3run, _ = council(wf3, "run", "open", "council-review", session="sV")
    first = run_agent_gate(gate_cmd, pre_tool("sV", wf3, tool="Workflow"), wf3)[0]
    write(os.path.join(w3run, "verify-1-a.md"), "# Verification — w\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
          "| 1 | a | CONFIRMED | a.py:1 |\n")                       # a seat is done only with its file
    council(wf3, "seat", "verify-1", "done", "agent=wf_1", "agents=3", "tokens=60000", "--run", os.path.basename(w3run))
    codes = [first] + [run_agent_gate(gate_cmd, pre_tool("sV", wf3), wf3)[0] for _ in range(4)]
    check("agent gate: after a Workflow of 3 recorded on a cap of 5, two more agents start and the third is stopped "
          "(7 would have run when the larger count hid the starts)", codes == [0, 0, 0, 2, 2], str(codes))

    # Agents recorded before the gate counted any start (a run resumed from an older version): they count too.
    pre = new_repo(tmp, "gate-counts-recorded-first")
    write(os.path.join(pre, ".council", "council.config.md"), "# Council config\n- agent cap: 3\n")
    _, prun, _ = council(pre, "run", "open", "council-review", session="sP")
    for i in (1, 2):
        council(pre, "seat", f"w{i}", "done", f"agent=p{i}", "tokens=20000", "--run", os.path.basename(prun))
    codes = [run_agent_gate(gate_cmd, pre_tool("sP", pre), pre)[0] for _ in range(3)]
    code, out, err = council(pre, "cap", "--run", os.path.basename(prun))
    check("agent gate: two agents recorded before any start was counted, on a cap of 3 — one more starts, then the stop",
          codes == [0, 2, 2] and "3 of 3 agent runs used" in out, f"{codes} · {out.strip()}")

    # Agents started in one message reach the hook together: the count and the check share one lock.
    batch = new_repo(tmp, "gate-counts-batch")
    write(os.path.join(batch, ".council", "council.config.md"), "# Council config\n- agent cap: 3\n")
    _, brun, _ = council(batch, "run", "open", "council-review", session="sT")
    env = dict(GIT_ENV, CLAUDE_PLUGIN_ROOT=ROOT)
    procs = [subprocess.Popen([BASH, "-c", gate_cmd], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              cwd=batch, env=env) for _ in range(6)]
    for p in procs:
        p.stdin.write(pre_tool("sT", batch).encode("utf-8"))
        p.stdin.close()
    codes = sorted(p.wait(timeout=120) for p in procs)
    check("agent gate: six agents started together on a cap of 3 — exactly three start, three are stopped",
          codes == [0, 0, 0, 2, 2, 2] and starts(brun) == 3, f"{codes}, {starts(brun)} starts recorded")

    # A run opened before plans and agent limits (no plan-schema): past the cap, it warns, never stops.
    old = new_repo(tmp, "gate-old-run")
    write(os.path.join(old, ".council", "council.config.md"), "# Council config\n- agent cap: 1\n")
    orun = os.path.join(old, ".council", "runs", "2026-09-20-173008-implement")
    write(os.path.join(orun, "session-state.md"), state("in-progress", mode="council-implement", phase="build",
                                                        code_root=git(old, "rev-parse", "--show-toplevel"), session="sO"))
    write(os.path.join(orun, "seats.tsv"), "slug\tstate\tagent\ttokens\tupdated\tnote\nhunt\tdone\ta1\t50000\t10:05\t\n"
                                           "beck\tdone\ta2\t50000\t10:07\t\n")
    code, out, err, _ = run_agent_gate(gate_cmd, pre_tool("sO", old), old)
    check("agent gate: a run opened before plans and agent limits, past the cap — the agent starts, uncounted",
          code == 0 and not err and starts(orun) == 0, f"{said(code, err)} · {starts(orun)} starts")

parser = argparse.ArgumentParser(description="Hook evals: run the plugin's hooks against scaffolded repos.")
parser.add_argument("--list", action="store_true",
                    help="print each group, whether it must run alone, and its blocks; run nothing")
parser.add_argument("--group", metavar="NAME[,NAME...]", help="run only these groups (default: all, in file order)")
parser.add_argument("--block", metavar="NAME[,NAME...]",
                    help="run only these blocks of the chosen groups — for a block that sets up all it needs")
parser.add_argument("--allow-skip", action="store_true",
                    help="exit 0 when bash or git is missing (default: exit 3, so a run that checked nothing never passes)")
opts = parser.parse_args()
GROUPS = list(dict.fromkeys(group for group, _ in PARTS))
blocks = [block for _, block in PARTS]
stray = [name for name, value in list(globals().items())
         if getattr(value, "__module__", None) == "__main__" and hasattr(value, "__code__")
         and value.__code__.co_firstlineno > blocks[0].__code__.co_firstlineno and value not in blocks]
if stray:   # a block without @part would never run, here or in CI
    sys.exit("run_hook.py: %s has no @part(...) group, so it would never run" % ", ".join(stray))
if opts.list:
    for group in GROUPS:
        print("%s\t%s\t%s" % (group, "alone" if group in ALONE else "shared",
                              " ".join(block.__name__ for g, block in PARTS if g == group)))
    sys.exit(0)
chosen = opts.group.split(",") if opts.group else GROUPS
if any(group not in GROUPS for group in chosen):
    parser.error("unknown group in %r (groups: %s)" % (opts.group, ", ".join(GROUPS)))
only = opts.block.split(",") if opts.block else None
if only and any(name not in [block.__name__ for g, block in PARTS if g in chosen] for name in only):
    parser.error("unknown block in %r for the chosen groups" % opts.block)
if not BASH or not GIT:
    print("[SKIP] bash or git not on PATH — hook evals need both; nothing was checked")
    sys.exit(0 if opts.allow_skip else 3)
with tempfile.TemporaryDirectory() as tmp:
    tmp = os.path.realpath(tmp)   # a runner's TEMP may be an 8.3 name (RUNNER~1); git prints the long one
    GIT_ENV["XDG_CACHE_HOME"] = os.path.join(tmp, "cache")   # session marks (bin/council's sessions_dir) stay here
    for group, block in PARTS:
        if group in chosen and (only is None or block.__name__ in only):
            block(tmp)

passed = sum(1 for ok, *_ in results if ok)
for ok, name, detail in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail.strip()[:300]})" if detail and not ok else ""))
if BASH:
    print(f"\nbash: {BASH} ({subprocess.run([BASH, '-c', 'echo $BASH_VERSION'], capture_output=True, text=True).stdout.strip()})")
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
