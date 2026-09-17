#!/usr/bin/env python3
"""Hook evals for the Small Council — run both hooks against fixture projects (bash + git, no LLM).

SessionStart (hooks/session-start.sh):
  - silent (exit 0) in a project with no .council/;
  - orients a council project: missing config, the map, memory, pending proposals, the helper;
  - finds open runs by scanning runs/*/session-state.md, several at once, and flags each one:
    unfinished on startup (its running seats died with the old session); paused as paused, even right
    after a compaction; a run in another working tree as "leave it alone";
  - after a compaction, resumes only the run this session was driving — the one whose session: matches,
    else the newest recent in-progress run that recorded none — and only lists the rest;
  - says nothing about complete or abandoned runs; keeps a 0.2 run's fields in place (no code-root);
  - still finds a legacy run through the old active-run pointer (no status line, CRLF, <mode>-output);
  - finds the MAIN checkout's .council/ from a linked worktree; reports a stale map; survives garbage.
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


def run_hook(project, source="startup", payload=None, session="eval"):
    env = dict(GIT_ENV, CLAUDE_PROJECT_DIR=project, CLAUDE_PLUGIN_ROOT=ROOT)
    if payload is None:
        payload = json.dumps({"session_id": session, "hook_event_name": "SessionStart", "source": source})
    p = subprocess.run([BASH, HOOK], input=payload, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, cwd=project, timeout=60)
    return p.returncode, p.stdout


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
    write(os.path.join(run_b, "session-state.md"), state("in-progress", mode="council-implement", code_root="C:/elsewhere/tree"))
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

    legacy = new_repo(tmp, "legacy")
    write(os.path.join(legacy, ".council", "council.config.md"), "# Council config\n", crlf=True)
    write(os.path.join(legacy, "conventions.md"), "# Project Conventions\n", crlf=True)
    old_rel = ".council/review-output/2026-09-07-1200"
    write(os.path.join(legacy, ".council", "active-run"), old_rel + "\n", crlf=True)
    write(os.path.join(legacy, old_rel, "session-state.md"), "# Session state\nphase: 5 — awaiting worker returns\n", crlf=True)
    code, out = run_hook(legacy, "startup")
    check("legacy run without status: flagged unfinished", "UNFINISHED COUNCIL RUN" in out, out)
    check("legacy run: mode inferred from the old folder name", "council-review (legacy run)" in out, out)
    check("legacy CRLF state: no carriage returns leak into output", "\r" not in out, repr(out))
    check("legacy root conventions.md: found", "Settled decisions:" in out and "conventions.md" in out, out)

    wt = os.path.join(tmp, "full-wt")
    git(full, "worktree", "add", "-q", "-b", "feature", wt)
    code, out = run_hook(wt, "startup")
    first = out.splitlines()[0] if out.strip() else ""
    check("linked worktree: finds the main checkout's council", "[Small Council]" in first
          and first.replace("\\", "/").rstrip("/").endswith("full/.council"), first)
    check("linked worktree: the main checkout's run is someone else's", "different working tree" in out, out)

    for n in (2, 3):
        write(os.path.join(full, "app.txt"), f"v{n}\n")
        git(full, "commit", "-q", "-am", f"change {n}")
    code, out = run_hook(full, "startup")
    check("stale map: reports commits behind", "2 commits behind HEAD" in out, out)

    pgr = new_repo(tmp, "pg")
    ptop = git(pgr, "rev-parse", "--show-toplevel")
    write(os.path.join(pgr, ".council", "runs", "2026-09-15-130000-postgame", "session-state.md"),
          state("in-progress", mode="council-postgame", phase="judge", code_root=ptop, session="eval"))
    code, out = run_hook(pgr, "compact", session="eval")
    check("after compaction in a post-game: re-invoke council-postgame and re-read ask.md",
          "Re-invoke the council-postgame skill" in out and "and ask.md, if present" in out, out)

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
    check("seat check: a relative path it can't find from the session's folder is let through", code == 0, err)
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

passed = sum(1 for ok, *_ in results if ok)
for ok, name, detail in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail.strip()[:300]})" if detail and not ok else ""))
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
