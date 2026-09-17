#!/usr/bin/env python3
"""Hook evals for the Small Council — run both hooks against fixture projects (bash + git, no LLM).

SessionStart (hooks/session-start.sh):
  - silent (exit 0) in a project with no .council/;
  - orients a council project: missing config, the map, memory, pending proposals, the helper;
  - finds open runs by scanning runs/*/session-state.md, several at once, and flags each one:
    unfinished on startup (its running seats died with the old session); paused as paused, even right
    after a compaction; a run in another working tree as "leave it alone";
  - after a compaction, resumes only the run this session was driving — the one whose session: matches
    (also after `council run resume` in a new session), else the newest recent in-progress run that
    recorded none — never a paused one or another tree's, and only lists the rest;
  - never offers to re-dispatch or close a run another session updated in the last 2 hours;
  - stays fast and short with many open runs: other trees' runs summed up, gone trees named, at most 5
    of this tree's runs described;
  - says nothing about complete or abandoned runs; keeps a 0.2 run's fields in place (no code-root);
  - still finds a legacy run through the old active-run pointer (no status line, CRLF, <mode>-output),
    offers a finished one to close as complete, and never claims an old one after a compaction;
  - finds the MAIN checkout's .council/ from a linked worktree; reports a stale or rewritten map;
    survives garbage.
SubagentStop (hooks/seat-gate.sh):
  - lets a valid worker or verifier file through, including list-style index lines and prose;
  - blocks once (exit 2, reason on stderr) on a missing, malformed, oversized or empty file, an index
    line it can't read, or a reply with no "Wrote" line;
  - never blocks when stop_hook_active is set, on a line that starts with BLOCKED, or for other agents.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "hooks", "session-start.sh")
GATE = os.path.join(ROOT, "hooks", "seat-gate.sh")
BASH = shutil.which("bash")
GIT = shutil.which("git")
GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME="eval", GIT_AUTHOR_EMAIL="eval@example.invalid",
               GIT_COMMITTER_NAME="eval", GIT_COMMITTER_EMAIL="eval@example.invalid")
GIT_ENV.pop("CLAUDE_CODE_SESSION_ID", None)
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


def council(cwd, *args, session=""):
    env = dict(GIT_ENV, CLAUDE_CODE_SESSION_ID=session) if session else GIT_ENV
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


def run_gate(agent, message, active=False, cwd=None):
    payload = json.dumps({"hook_event_name": "SubagentStop", "agent_type": agent, "agent_id": "a1",
                          "last_assistant_message": message, "stop_hook_active": active, "cwd": cwd or ""})
    p = subprocess.run([BASH, GATE], input=payload, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=60)
    return p.returncode, p.stderr


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


if not BASH or not GIT:
    print("[SKIP] bash or git not on PATH — hook evals need both")
    sys.exit(0)

with tempfile.TemporaryDirectory() as tmp:
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
    check("full council: fresh map is not 'behind'", "behind" not in out, out)
    check("full council: counts 2 pending proposals (ignores the comment)", "2 memory proposal(s)" in out, out)
    check("full council: lists council-postgame among the modes", "council-postgame" in out, out)
    check("full council: no open-run warning", "UNFINISHED" not in out and "COMPACTED" not in out, out)

    runs = os.path.join(full, ".council", "runs")
    run_a = os.path.join(runs, "2026-09-15-100000-review")
    write(os.path.join(run_a, "session-state.md"), state("in-progress", code_root=top))
    write(os.path.join(run_a, "seats.tsv"), "slug\tstate\tagent\ttokens\tupdated\tnote\nhunt\trunning\ta1\t\t10:00\tround 2\nbeck\tdone\ta2\t50000\t10:05\t\n")
    code, out = run_hook(full, "startup")
    check("open run found by scanning (no pointer needed)", "UNFINISHED COUNCIL RUN" in out, out)
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
          and "gone" not in line and "--status abandoned" not in line, out)
    for f in ("session-state.md", "seats.tsv"):
        age(os.path.join(lrun, f), 3 * 3600)
    code, out = run_hook(live, "startup", session="another-session")
    line = line_with(out, "2026-09-15-130000-review")
    check("a run another session left hours ago: unfinished, its running seats gone, resume or close offered",
          "UNFINISHED COUNCIL RUN" in line and "were running when that session ended" in line
          and "council run resume --run 2026-09-15-130000-review" in line and "--status abandoned" in line, out)

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
    write(os.path.join(legacy, old_rel, "FINAL-REVIEW.md"), "# Final review\n")
    code, out = run_hook(legacy, "startup")
    line = line_with(out, "2026-09-07-1200")
    check("legacy run holding its final deliverable: offered to close as complete, not abandoned",
          "--status complete" in line and "--status abandoned" not in line and "FINAL-REVIEW.md" in line, out)

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
    code, err = run_gate(worker, f"Wrote {os.path.join(seats, 'nope.md')} — 0 items")
    check("seat check: a missing file blocks (exit 2)", code == 2 and "doesn't exist" in err, err)
    bad = os.path.join(seats, "bad.md")
    write(bad, "# Bad\nnot a ref line\n")
    code, err = run_gate(worker, f"Wrote {bad} — 1 items")
    check("seat check: a malformed file blocks and names the fixes", code == 2 and "line 2" in err and "## Index" in err, err)
    big = os.path.join(seats, "big.md")
    write(big, "# Big — x (council-review)\nref: none\n## Index\n" + ("x" * 17000) + "\n")
    code, err = run_gate(worker, f"Wrote {big} — 1 items")
    check("seat check: an oversized file blocks", code == 2 and "16 KB" in err, err)
    listy = os.path.join(seats, "listy.md")
    write(listy, "# Listy — Security (council-review)\nref: none\n## Index\nMost important first:\n"
                 "- 1 · P2 · Principle 3 · a.py:1 · x\n\n### 1. x\nThe body.\n")
    code, err = run_gate(worker, f"Wrote {listy} — 1 items (P2 1)")
    check("seat check: list-style index lines and prose under the Index pass", code == 0, err)
    messy = os.path.join(seats, "messy.md")
    write(messy, "# Messy — x (council-review)\nref: none\n## Index\n1) P2 — no separators at all\n")
    code, err = run_gate(worker, f"Wrote {messy} — 1 items")
    check("seat check: an index line it can't read blocks", code == 2 and "aren't in the index format" in err, err)
    hollow = os.path.join(seats, "hollow.md")
    write(hollow, "# Hollow — x (council-review)\nref: none\n## Index\n")
    code, err = run_gate(worker, f"Wrote {hollow} — 0 items")
    check("seat check: an empty Index blocks", code == 2 and "the Index is empty" in err, err)
    quiet = os.path.join(seats, "quiet.md")
    write(quiet, "# Quiet — x (council-review)\nref: none\n## Index\n(none) — nothing in my slice\n")
    code, err = run_gate(worker, f"Wrote {quiet} — 0 items")
    check("seat check: an empty lane with a (none) line passes", code == 0, err)
    code, err = run_gate(worker, "I looked at some things")
    check("seat check: no 'Wrote' line blocks", code == 2 and "Wrote <output path>" in err, err)
    code, err = run_gate(worker, "I looked at some things", active=True)
    check("seat check: never blocks twice (stop_hook_active)", code == 0, err)
    code, err = run_gate(worker, "BLOCKED: cannot read the brief")
    check("seat check: BLOCKED passes through", code == 0, err)
    code, err = run_gate(worker, "Read the dispatch.\nBLOCKED: the brief is missing")
    check("seat check: a BLOCKED line after other text passes", code == 0, err)
    code, err = run_gate(worker, "I was not BLOCKED, I just stopped early")
    check("seat check: 'BLOCKED' mid-sentence is not a BLOCKED reply", code == 2, err)
    code, err = run_gate("general-purpose", "hello")
    check("seat check: other agent types pass through", code == 0, err)
    ver = os.path.join(tmp, "run", "verify-1.md")
    write(ver, "# Verification — eval\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n| 1 | a | CONFIRMED | x |\n")
    code, err = run_gate(verifier, f"Wrote {ver} — 1 confirmed, 0 refuted, 0 uncertain, 0 miscited")
    check("seat check: a valid verifier file passes", code == 0, err)
    code, err = run_gate(verifier, f"Wrote {good} — 1 confirmed")
    check("seat check: a verifier file must be a verification", code == 2 and "# Verification" in err, err)
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

passed = sum(1 for ok, *_ in results if ok)
for ok, name, detail in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail.strip()[:300]})" if detail and not ok else ""))
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
