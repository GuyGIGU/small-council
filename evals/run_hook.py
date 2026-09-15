#!/usr/bin/env python3
"""Hook evals for the Small Council — run hooks/session-start.sh against fixture projects.

Needs bash and git on PATH, no LLM, no network. Asserts that the SessionStart hook:
  - stays completely silent (and exits 0) in a project with no .council/;
  - orients a council project: missing config, the map, memory, pending proposals;
  - flags an unfinished run on startup, and says "resume, don't restart" right after a compaction;
  - says nothing about a run whose status is complete or abandoned, or an empty active-run;
  - treats a legacy run (no status line, CRLF line endings, old <mode>-output path) as unfinished;
  - finds the MAIN checkout's .council/ from a linked git worktree;
  - reports how far the map is behind HEAD;
  - survives garbage on stdin.
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "hooks", "session-start.sh")
BASH = shutil.which("bash")
GIT = shutil.which("git")
GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME="eval", GIT_AUTHOR_EMAIL="eval@example.invalid",
               GIT_COMMITTER_NAME="eval", GIT_COMMITTER_EMAIL="eval@example.invalid")

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
results = []


def check(name, ok, detail=""):
    results.append((ok, name, detail))


def run_hook(project, source="startup", payload=None):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=project)
    if payload is None:
        payload = '{"session_id":"eval","hook_event_name":"SessionStart","source":"%s"}' % source
    proc = subprocess.run([BASH, HOOK], input=payload, capture_output=True, text=True,
                          env=env, cwd=project, timeout=60)
    return proc.returncode, proc.stdout


def git(cwd, *args):
    return subprocess.run([GIT, *args], cwd=cwd, check=True, capture_output=True, text=True,
                          env=GIT_ENV).stdout.strip()


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


def state(status_line, mode="council-review", phase="dispatch"):
    head = f"{status_line}\n" if status_line else ""
    return f"{head}mode: {mode}\nphase: {phase}\nupdated: 2026-09-15 10:00\nnext: collect seats\n"


if not BASH or not GIT:
    print("[SKIP] bash or git not on PATH — hook evals need both")
    sys.exit(0)

with tempfile.TemporaryDirectory() as tmp:
    # 1. No council → silent, exit 0.
    plain = new_repo(tmp, "plain")
    code, out = run_hook(plain)
    check("no .council/: exits 0", code == 0, str(code))
    check("no .council/: prints nothing", out.strip() == "", out)

    # 2. Council dir but no config.
    bare = new_repo(tmp, "bare")
    os.makedirs(os.path.join(bare, ".council"))
    code, out = run_hook(bare)
    check("council without config: says run council-init", "council-init" in out and "No council.config.md" in out, out)

    # 3. Full council: config + fresh map + memory with two proposals, no active run.
    full = new_repo(tmp, "full")
    head = git(full, "rev-parse", "HEAD")
    write(os.path.join(full, ".council", "council.config.md"), "# Council config\n")
    write(os.path.join(full, ".council", "map.md"), f"# Codebase map\nmap-commit: {head}\nupdated: 2026-09-15\n")
    write(os.path.join(full, ".council", "conventions.md"),
          "# Conventions\n## Proposed\n<!-- Format: - PROPOSED AP: ... -->\n"
          "- PROPOSED AP: a — x (from r1, d)\n- PROPOSED EC: b — y (from r1, d)\n")
    code, out = run_hook(full)
    check("full council: exits 0", code == 0, str(code))
    check("full council: orientation line", "[Small Council]" in out and "map.md" in out, out)
    check("full council: fresh map is not 'behind'", "behind" not in out, out)
    check("full council: counts 2 pending proposals (ignores the comment)", "2 memory proposal(s)" in out, out)
    check("full council: no unfinished-run warning", "UNFINISHED" not in out and "COMPACTED" not in out, out)

    # 4–6. Active run: in progress (startup), in progress (compact), complete, abandoned, empty pointer.
    run_rel = ".council/runs/2026-09-15-1000-review"
    write(os.path.join(full, ".council", "active-run"), run_rel + "\n")
    write(os.path.join(full, run_rel, "session-state.md"), state("status: in-progress"))
    code, out = run_hook(full, "startup")
    check("in-progress run on startup: flagged unfinished", "UNFINISHED COUNCIL RUN" in out, out)
    check("in-progress run on startup: shows mode and phase", "council-review" in out and "phase: dispatch" in out, out)
    code, out = run_hook(full, "compact")
    check("in-progress run after compaction: says resume", "COMPACTED DURING A COUNCIL RUN" in out
          and "Re-invoke the context-core skill" in out and "Do not restart" in out, out)
    for closed in ("status: complete", "status: abandoned"):
        write(os.path.join(full, run_rel, "session-state.md"), state(closed))
        code, out = run_hook(full, "startup")
        check(f"{closed.split(': ')[1]} run: no warning", "UNFINISHED" not in out, out)
    write(os.path.join(full, run_rel, "session-state.md"), state("status: in-progress"))
    write(os.path.join(full, ".council", "active-run"), "")
    code, out = run_hook(full, "startup")
    check("empty active-run: no warning", "UNFINISHED" not in out, out)

    # 7–8. Legacy layout: root conventions.md, old <mode>-output run with no status line, CRLF.
    legacy = new_repo(tmp, "legacy")
    write(os.path.join(legacy, ".council", "council.config.md"), "# Council config\n", crlf=True)
    write(os.path.join(legacy, "conventions.md"), "# Project Conventions\n", crlf=True)
    old_rel = ".council/review-output/2026-09-07-1200"
    write(os.path.join(legacy, ".council", "active-run"), old_rel + "\n", crlf=True)
    write(os.path.join(legacy, old_rel, "session-state.md"),
          "# Session state\nphase: 5 — awaiting worker returns\n", crlf=True)
    code, out = run_hook(legacy, "startup")
    check("legacy run without status: flagged unfinished", "UNFINISHED COUNCIL RUN" in out, out)
    check("legacy run: mode inferred from the old folder name", "council-review (legacy run)" in out, out)
    check("legacy CRLF state: no carriage returns leak into output", "\r" not in out, repr(out))
    check("legacy root conventions.md: found", "Settled decisions:" in out and "conventions.md" in out, out)

    # 9. Linked worktree: the hook must find the MAIN checkout's .council/.
    wt = os.path.join(tmp, "full-wt")
    git(full, "worktree", "add", "-q", "-b", "feature", wt)
    code, out = run_hook(wt, "startup")
    first = out.splitlines()[0] if out.strip() else ""
    check("linked worktree: finds the main checkout's council", "[Small Council]" in first
          and first.replace("\\", "/").rstrip("/").endswith("full/.council"), first)

    # 10. Stale map: two commits after map-commit.
    for n in (2, 3):
        write(os.path.join(full, "app.txt"), f"v{n}\n")
        git(full, "commit", "-q", "-am", f"change {n}")
    code, out = run_hook(full, "startup")
    check("stale map: reports commits behind", "2 commits behind HEAD" in out, out)

    # 11. Garbage stdin never breaks the session.
    code, out = run_hook(full, payload="\x00not json at all")
    check("garbage stdin: exits 0", code == 0, str(code))

# Report (same format as run_structural.py)
passed = sum(1 for ok, *_ in results if ok)
for ok, name, detail in results:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f"  ({detail.strip()[:300]})" if detail and not ok else ""))
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
