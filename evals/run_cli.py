#!/usr/bin/env python3
"""Helper evals for the Small Council — run bin/council against scaffolded git repos.

Needs bash and git; no LLM, no network. Covers:
  - the council home: main checkout, linked worktree, outside git, a bare repository's worktrees;
  - runs: open, update, close, resume; a second in-progress run on one tree refused without --alongside;
    commands that never guess between runs; paused runs; session ids; init creating the home; an old
    open run found behind many newer closed ones, and this tree's run behind many other trees' runs;
    a byte-order mark; a Windows --run path;
  - the change index: files, symbols (code only, shell functions included), callers, tests; files past
    the cap named; renames, non-ASCII names, binaries, nested worktrees, a relative --run;
  - gates judged by exit code, with the command passed intact, and table cells that never shift; one
    gate call per run at a time, a second refused before it writes anything;
  - seat-file collection: ref: proof of reading (paired seats too), caps, broken citations, list-style
    and unreadable index lines, failed and re-dispatched workers;
  - citation and origin checks (single lines, ranges and comma lists); map status; the drift doctor;
  - the agent stop: council cap's standing, cap allow's refusals and record (older runs too), cap check's
    exit codes.

Each block of checks belongs to a group (@part below); `--list` prints the groups, `--group NAME` runs
one, and evals/run_all.py runs them side by side. With no options every group runs, in file order.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "bin", "council")
BASH = os.environ.get("COUNCIL_EVAL_BASH") or shutil.which("bash")   # CI's macOS leg: /bin/bash (3.2)
GIT = shutil.which("git")
GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME="eval", GIT_AUTHOR_EMAIL="eval@example.invalid",
               GIT_COMMITTER_NAME="eval", GIT_COMMITTER_EMAIL="eval@example.invalid")
for var in ("COUNCIL_RUN", "CLAUDE_CODE_SESSION_ID"):   # never inherit the session the eval runs in
    GIT_ENV.pop(var, None)
if os.environ.get("COUNCIL_EVAL_BASH"):                  # a gate's `bash -c` must use that bash too
    GIT_ENV["PATH"] = os.path.dirname(BASH) + os.pathsep + GIT_ENV.get("PATH", "")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
results = []


FULL_DETAIL = set()   # checks whose detail is printed whole: every worker's exit code and stderr of a race


def result_line(ok, name, detail):
    cut = None if name in FULL_DETAIL else 400
    return f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail.strip()[:cut]})" if detail and not ok else "")


def check(name, ok, detail="", full=False):
    if full:
        FULL_DETAIL.add(name)
    results.append((ok, name, detail))
    # Printed as it happens: the suite runs the helper hundreds of times (about 17 minutes on Windows
    # Git Bash), and a run that prints nothing until the end is easy to mistake for a stalled one.
    print(result_line(ok, name, detail), flush=True)


def council(cwd, *args, env=None):
    try:
        p = subprocess.run([BASH, CLI, *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=dict(GIT_ENV, **(env or {})), timeout=120)
    except subprocess.TimeoutExpired:   # one failed check, not a crash that hides every other result
        return 124, "", f"council {' '.join(args)}: still running after 120 s"
    return p.returncode, p.stdout, p.stderr


def council_quoted(cwd, *args):
    """council() for words like *.sh or *.{py,md}: on Windows, Git Bash globs and brace-expands any
    unquoted word of its command line against the cwd, so there every word is passed quoted."""
    if os.name != "nt":
        return council(cwd, *args)
    line = " ".join('"%s"' % a for a in (BASH, CLI) + args)
    p = subprocess.run(line, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=GIT_ENV, timeout=120)
    return p.returncode, p.stdout, p.stderr


def council_together(cwd, *calls):
    """Start several council calls at the same moment; return each one's (exit code, stderr) once all
    have finished. A call still running after 120 s is stopped and reads as exit 124, as in council()."""
    procs = [subprocess.Popen([BASH, CLI, *args], cwd=cwd, env=GIT_ENV, stdout=subprocess.DEVNULL,
                              stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
             for args in calls]
    finished = []
    for p in procs:
        try:
            err = p.communicate(timeout=120)[1]
            finished.append((p.returncode, err))
        except subprocess.TimeoutExpired:
            p.kill()
            finished.append((124, p.communicate()[1] + " (still running after 120 s)"))
    return finished


def gates_together(cwd, run, names):
    """Start `council gate <name> --run <run> -- true` for every name at the same moment; return each
    one's (exit code, stdout, stderr) once all have finished, as council_together does."""
    return all_finished([subprocess.Popen([BASH, CLI, "gate", name, "--run", run, "--", "true"], cwd=cwd, env=GIT_ENV,
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                          errors="replace") for name in names])


def events_together(cwd, run, names):
    """Append one event per name to the run's stream at the same moment — each from its own bash with
    the helper sourced, as the SessionStart hook sources it — and return each one's (exit code, stdout,
    stderr). Gate calls no longer contend for the events lock (a run takes one `council gate` at a
    time), so the lock's races are driven straight through event_append."""
    script = 'source "$1"; event_append "$2" gate.finished "$3" passed "exit=0;seconds=0;empty=0"'
    return all_finished([subprocess.Popen([BASH, "-c", script, "council", CLI.replace("\\", "/"), run, name], cwd=cwd,
                                          env=GIT_ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                          encoding="utf-8", errors="replace") for name in names])


def all_finished(procs):
    finished = []
    for p in procs:
        try:
            out, err = p.communicate(timeout=120)
            finished.append((p.returncode, out, err))
        except subprocess.TimeoutExpired:
            p.kill()
            out, err = p.communicate()
            finished.append((124, out, err + " (still running after 120 s)"))
    return finished


def gates_detail(finished):
    """Every gate worker's exit code, stdout and whole stderr, for a race check's detail."""
    return "\n".join("worker %d: exit %d · stdout %r · stderr %r" % (i, code, out, err)
                     for i, (code, out, err) in enumerate(finished))


def workers_detail(finished, expected=()):
    """Each worker's exit code, then whatever else it said on stderr: first in a check's detail, which
    a race check prints whole (check(..., full=True)) so a rare failure shows every worker."""
    said = []
    for i, (_, err) in enumerate(finished):
        lines = [x for x in err.splitlines() if x.strip() and not any(e in x for e in expected)]
        if lines:
            said.append("worker %d: %s" % (i, " / ".join(lines)))
    return "exit codes %s%s" % ([code for code, _ in finished], "".join("; " + s for s in said))


def git(cwd, *args):
    return subprocess.run([GIT, "-c", "core.autocrlf=false", *args], cwd=cwd, check=True,
                          capture_output=True, text=True, env=GIT_ENV).stdout.strip()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def append(path, text):
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(text)


def read(path):
    if not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


def events(run):
    """Parsed event rows, excluding the header."""
    return [line.split("\t") for line in read(os.path.join(run, "events.tsv")).splitlines()[1:]]


def route_table(output):
    """Parse the advisory route's stable five-column TSV contract."""
    lines = output.splitlines()
    valid = bool(lines) and lines[0] == "kind\tid\tfield\tvalue\treason"
    rows = [line.split("\t") for line in lines[1:]]
    valid = valid and all(len(row) == 5 for row in rows)
    return valid, {(row[0], row[1], row[2]): row[3:] for row in rows if len(row) == 5}


def route_value(rows, kind, ident, field):
    return rows.get((kind, ident, field), [""])[0]


def write_plan(run, selected=("chair",), skipped=(), size="squad", risk="medium", complexity="medium",
               uncertainty="medium", verification="independent", estimated_tokens=100000):
    """Complete a run-plan v1 for tests whose subject is later than routing."""
    selected = list(selected)
    if "chair" not in selected:
        selected.insert(0, "chair")
    if size != "solo" and verification != "self" and not any(slug.startswith("verify-") for slug in selected):
        selected.append("verify-plan")
    state = read(os.path.join(run, "session-state.md"))
    mode = re.search(r"^mode:\s*(.+)$", state, re.MULTILINE).group(1).strip()
    rows = [
        ("kind", "id", "field", "value", "reason"),
        ("schema", "plan", "version", "1", "versioned test contract"),
        ("run", "run", "id", os.path.basename(run), "bind this plan to the test run"),
        ("run", "run", "mode", mode, "mode chosen by this test"),
        ("run", "run", "size", size, "sized for this test"),
        ("assessment", "run", "risk", risk, "test fixture risk"),
        ("assessment", "run", "complexity", complexity, "test fixture complexity"),
        ("assessment", "run", "uncertainty", uncertainty, "test fixture uncertainty"),
        ("budget", "run", "agent-cap", "10", "default project cap"),
        ("budget", "run", "estimated-tokens", str(estimated_tokens), "fixture estimate"),
        ("verification", "run", "level", verification, "fixture verification"),
    ]
    for slug in selected:
        role = "chair" if slug == "chair" else ("verifier" if slug.startswith("verify-") else "worker")
        rows.extend([
            ("seat", slug, "disposition", "selected", "needed by this test"),
            ("seat", slug, "role", role, "fixture role"),
            ("context", slug, "level", "focused", "only the fixture context"),
            ("budget", slug, "tool-calls", "15", "small fixture slice"),
        ])
    for slug in skipped:
        rows.extend([
            ("seat", slug, "disposition", "skipped", "no surface in this fixture"),
            ("seat", slug, "role", "worker", "roster seat"),
        ])
    write(os.path.join(run, "run-plan.tsv"), "\n".join("\t".join(row) for row in rows) + "\n")


def slash(p):
    return p.strip().replace("\\", "/").rstrip("/")


def ref(doc):
    return os.path.join(ROOT, "references", doc)


def first_heading(doc):
    return read(ref(doc)).split("\n", 1)[0].lstrip("# ").strip()


def new_repo(base, name):
    repo = os.path.join(base, name)
    os.makedirs(repo)
    git(repo, "init", "-q")
    git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    return repo


def small_council_repo(tmp, name, gate_rows):
    """A committed repo whose config holds only a Gates table (with Side effects, so gate --all runs them)."""
    repo = new_repo(tmp, name)
    write(os.path.join(repo, "a.txt"), "a\n")
    write(os.path.join(repo, ".council", "council.config.md"),
          "# Council config — x\nlast-verified: 2026-09-15 @ x\n\n## Gates\n"
          "| Gate | Command | Run at | Mandatory | Checked | Probe | Side effects | Needs |\n"
          "|---|---|---|---|---|---|---|---|\n" + gate_rows + "\n## Hard rules\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def row(out, slug):
    m = re.search(rf"^{slug}\s.*$", out, re.MULTILINE)
    return m.group(0) if m else ""


def line_of(out, text):
    return next((line for line in out.splitlines() if text in line), "")


CONFIG = """# Council config — eval
last-verified: 2026-09-15 @ eval

## Roster
| Seat | Slug | Lens | Surface | Reference | Recast note |
|---|---|---|---|---|---|
| Martin Fowler | fowler | Structure | `src/**` | references/refactoring.md | kept |
| Ghost | ghost | Nothing | `x` | references/does-not-exist.md | a broken reference |
| Kent Beck | fowler | Tests | `tests/**` | references/quality-testing.md | a repeated slug |

## Gates
| Gate | Command | Run at | Mandatory | Checked | Needs | Side effects |
|---|---|---|---|---|---|---|
| ok | `true` | grounding, verify | yes | ok | — | none |
| bad | `echo "Error: boom"; exit 3` | verify | no | ok | — | none |
| must | `exit 4` | grounding | yes | ok | — | none |
| piped | `printf "a|b"` | manual | no | ok | — | none |
| anytime | `true` |  | no | ok |  |  |
| broken | `true` | verify | no | ✗ 2026-09-15: needs a simulator | a simulator | none |
| ship | `echo shipped` | verify | no | ok | — | deploy, network |
| stripe | `echo charged` | verify | no | not probed: needs a live key | STRIPE_SECRET_KEY (credentials) | network |
| leaky | `echo leaked` | verify | no | ok | VPN | bastion | deploy, cost |
| bill | `echo billed` | verify | no | ok | — | billable API calls |
| shifted | echo x | grep x | never | no | ok | — | none |

## Memory
- conventions: .council/conventions.md
"""

PARTS = []                   # (group, block), in file order
ALONE = {"timing"}           # groups that must run with nothing else running (see evals/run_all.py)


def part(group):
    """Adds the block below to a group. A group runs in one process, its blocks in file order, and
    what one block leaves for a later one (a repo, a run) stays inside its group, so each group runs
    on its own. With no options every block runs, in file order, in this one process."""
    def add(block):
        PARTS.append((group, block))
        return block
    return add


@part("runs")
def runs_open(tmp):
    """The main scaffolded repo: its council home, its first run, the run's state and routing."""
    global repo, top, plain, run   # later "runs" blocks carry on with these
    repo = new_repo(tmp, "repo")
    write(os.path.join(repo, "src", "stats.py"),
          "def average(values):\n    total = 0\n    for v in values:\n        total += v\n    return total / len(values)\n")
    write(os.path.join(repo, "tests", "test_stats.py"),
          "from src.stats import average\n\ndef test_avg():\n    assert average([1, 2]) == 1.5\n")
    write(os.path.join(repo, "README.md"), "# Stats\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    git(repo, "checkout", "-q", "-b", "feature")
    append(os.path.join(repo, "src", "stats.py"), "\ndef median(values):\n    s = sorted(values)\n    return s[len(s) // 2]\n")
    write(os.path.join(repo, "src", "report.py"), "from src.stats import median\n\ndef summary(xs):\n    return median(xs)\n")
    write(os.path.join(repo, "scripts", "deploy.sh"), "#!/usr/bin/env bash\nship_it() {\n  echo shipping\n}\n")
    append(os.path.join(repo, "tests", "test_stats.py"), "\ndef test_median():\n    assert median([3, 1, 2]) == 2\n")
    append(os.path.join(repo, "README.md"), "Use the median for robust stats.\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "feature")
    append(os.path.join(repo, "src", "report.py"), "# uncommitted line\n")
    write(os.path.join(repo, ".council", "council.config.md"), CONFIG)
    write(os.path.join(repo, ".council", ".gitignore"), "runs/\nactive-run\n")
    write(os.path.join(repo, ".council", "conventions.md"), "# Conventions\n")
    top = slash(git(repo, "rev-parse", "--show-toplevel"))

    # Council home
    code, out, _ = council(repo, "home")
    check("home: the repo's .council/", code == 0 and slash(out).lower().endswith("/repo/.council"), out)
    plain = os.path.join(tmp, "plain")
    os.makedirs(plain)
    code, out, _ = council(plain, "home")
    check("home: outside git it is ./.council", code == 0 and slash(out).lower().endswith("/plain/.council"), out)
    # The permission rule for the home's real path, in the form Claude Code matches: //<absolute path>/**,
    # and a Windows drive as /c/… — a rule written //C:/… (what `council home` prints there) never matches.
    _, home_out, _ = council(repo, "home")
    code, out, _ = council(repo, "home", "rule")
    want = slash(home_out)
    if re.match(r"^[A-Za-z]:/", want):
        want = "/" + want[0].lower() + want[2:]
    check("home rule: prints the Edit rule for the council home's real path",
          code == 0 and out.strip() == "Edit(/" + want + "/**)" and ":" not in out.strip()[5:], out)
    code, out, err = council(repo, "home", "rule", "x")
    check("home rule: refuses a word it doesn't take", code == 2 and "doesn't take" in err, out + err)
    p = subprocess.run([BASH, "-c", 'H="$2"; source "$1"; council_home() { printf "%s\\n" "$H"; }; home_rule', "council",
                        CLI.replace("\\", "/"), "C:/Users/Me/My Project/.council"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=GIT_ENV)
    check("home rule: a Windows home is written with the drive lower-case and no colon, blanks kept",
          p.stdout.strip() == "Edit(//c/Users/Me/My Project/.council/**)", p.stdout + p.stderr)

    # Opening a run
    code, out, err = council(repo, "run", "open", "nonsense")
    check("run open: rejects an unknown mode", code == 2 and "unknown mode" in err, err)
    code, run, err = council(repo, "run", "open", "council-review", env={"CLAUDE_CODE_SESSION_ID": "sess-123"})
    run = run.strip()
    check("run open: prints the new run folder", code == 0 and os.path.isdir(run) and run.endswith("-review"), run + err)
    st = read(os.path.join(run, "session-state.md"))
    check("run open: state starts in-progress at convene", "status: in-progress" in st and "phase: convene" in st, st)
    check("run open: state records the full mode skill name", "mode: council-review" in st, st)
    check("run open: state records the code root", re.search(r"^code-root: .+/repo$", st, re.MULTILINE) is not None, st)
    check("run open: state records Claude Code's session id", "session: sess-123" in st, st)
    check("run open: seats.tsv and seats/ created", os.path.isfile(os.path.join(run, "seats.tsv")) and os.path.isdir(os.path.join(run, "seats")))

    large_memory = new_repo(tmp, "large-memory")
    write(os.path.join(large_memory, ".council", "council.config.md"), "# Council config\n")
    write(os.path.join(large_memory, ".council", "conventions.md"), "x" * 30000)
    code, _, err = council(large_memory, "run", "open", "council-review")
    check("run open: a 30 KB project memory warns and points to consolidation",
          code == 0 and "conventions.md is 30 KB" in err and "propose a consolidation" in err, err)
    write(os.path.join(large_memory, ".council", "conventions.md"), "x" * 20000)
    code, _, err = council(large_memory, "run", "open", "council-review", "--alongside")
    check("run open: a 20 KB project memory does not warn", code == 0 and "over the ~25 KB" not in err, err)
    configured_memory = new_repo(tmp, "configured-memory")
    write(os.path.join(configured_memory, ".council", "council.config.md"),
          "# Council config\n## Memory\n- conventions: docs/project-memory.md\n")
    write(os.path.join(configured_memory, "docs", "project-memory.md"), "x" * 65864)
    code, _, err = council(configured_memory, "run", "open", "council-review")
    check("run open: the configured memory file, not only the default, is measured",
          code == 0 and "project-memory.md is 66 KB" in err, err)
    plan_path = os.path.join(run, "run-plan.tsv")
    check("run open: creates and stamps a versioned run plan",
          os.path.isfile(plan_path) and "plan-schema: 1" in st and "\t{{MODE}}\t" not in read(plan_path), read(plan_path) + st)
    first_events = events(run)
    check("run open: stamps and writes the first structured event",
          "events-schema: 1" in st and len(first_events) == 1 and
          first_events[0][0:2] == ["1", "1"] and first_events[0][3:6] == ["run.opened", "run", "council-review"],
          read(os.path.join(run, "events.tsv")))
    code, out, err = council(repo, "run", "events", "check")
    check("run events check: accepts the opened stream", code == 0 and "1 event(s)" in out, out + err)
    code, out, err = council(repo, "run", "events", "show")
    check("run events show: renders the first event and its detail",
          code == 0 and "run.opened  run → council-review  (phase=convene)" in out, out + err)
    code, out, _ = council(repo, "run", "plan", "check")
    check("run plan check: the starter plan is intentionally incomplete", code == 1 and "replace the placeholder" in out, out)
    code, out, err = council(repo, "state", "phase=brief")
    check("state: refuses to enter Brief while the run plan is invalid",
          code == 2 and "cannot advance to brief" in err and "phase: convene" in read(os.path.join(run, "session-state.md")), out + err)
    code, out, err = council(repo, "state", "phase=build")
    check("state: refuses to enter an implement Build while the run plan is invalid",
          code == 2 and "cannot advance to build" in err and "phase: convene" in read(os.path.join(run, "session-state.md")), out + err)

    # State
    code, out, _ = council(repo, "state", "phase=prepare", "next=build the index")
    st = read(os.path.join(run, "session-state.md"))
    check("state: updates header fields", code == 0 and "phase: prepare" in st and "next: build the index" in st, st)
    check("state: the phase transition gets one event",
          len(events(run)) == 2 and events(run)[1][3:7] == ["run.phase_changed", "run", "prepare", "from=convene"],
          read(os.path.join(run, "events.tsv")))
    code, _, err = council(repo, "state", "status=bogus")
    check("state: rejects an invalid status", code == 2, err)
    code, _, err = council(repo, "state", "no-equals-sign")
    check("state: rejects a bare word", code == 2, err)
    # A stage name is checked: a typo skipped the plan check, and an empty one wrote an event row that
    # failed the stream for good.
    for bad_phase in ("", "Brief", "working"):
        code, _, err = council(repo, "state", "phase=" + bad_phase, "next=never written")
        st = read(os.path.join(run, "session-state.md"))
        check(f"state: refuses the stage name {bad_phase!r} and writes nothing, not even the other keys",
              code == 2 and "is not a stage" in err and "phase: prepare" in st and "never written" not in st, err + st)
    code, out, err = council(repo, "run", "events", "check")
    check("state: refused stage names leave the event stream valid, with no row for them",
          code == 0 and len(events(run)) == 2, out + err)
    steps = new_repo(tmp, "init-steps")
    write(os.path.join(steps, ".council", "council.config.md"), "# Council config\n\n## Run preferences\n- notifications: off\n")
    council(steps, "run", "open", "council-init")
    code, out, err = council(steps, "state", "phase=propose")
    code2, _, err2 = council(steps, "state", "phase=Propose")
    check("state: an init run may name its own steps in lower case, never with capitals",
          code == 0 and "phase propose" in out and code2 == 2 and "is not a stage" in err2, out + err + err2)
    # Waiting on the user: the helper reminds the Chair to alert them, once per question (the step was
    # never taken in 33 real sessions), unless the project turned alerts off.
    code, _, err = council(steps, "state", "waiting=Which export cap?")
    check("state: with notifications off, a waiting question prints no alert reminder",
          code == 0 and "PushNotification" not in err, err)
    council(steps, "state", "waiting=")
    write(os.path.join(steps, ".council", "council.config.md"), "# Council config\n")
    code, _, err = council(steps, "state", "waiting=Which export cap?")
    code2, _, err2 = council(steps, "state", "waiting=Which export cap?", "next=wait")
    council(steps, "state", "waiting=")
    check("state: a run that starts waiting on the user is told once to send the alert with a PushNotification "
          "tool, which may be a deferred one",
          code == 0 and "waits on the user" in err and "PushNotification" in err and "deferred tool" in err
          and code2 == 0 and "PushNotification" not in err2, err + " | " + err2)

    write_plan(run, selected=("fowler", "beck", "gone"), skipped=("ghost",))
    code, out, err = council(repo, "run", "plan", "check")
    check("run plan check: accepts a complete plan and counts selected agents",
          code == 0 and "5 selected, 1 skipped" in out and "4 agent run(s) of cap 10" in out, out + err)
    code, out, err = council(repo, "state", "phase=brief")
    check("state: enters Brief once the run plan is valid", code == 0 and "phase brief" in out, out + err)
    code, out, err = council(repo, "run", "plan", "show")
    check("run plan show: explains routing, context, budgets and verification",
          code == 0 and "selected — fowler" in out and "skipped — ghost" in out and "verification: independent" in out, out + err)
    good_plan = read(plan_path)
    for bad in ("0", "-1", "many"):
        write(plan_path, good_plan + "budget\trun\ttoken-ceiling\t{}\towner limit\n".format(bad))
        code, out, _ = council(repo, "run", "plan", "check")
        check("run plan check: refuses invalid token ceiling " + bad,
              code == 1 and "token-ceiling must be a positive integer" in out, out)
    write(plan_path, good_plan)

    # Advisory routing is deterministic policy output, never a run mutation or agent dispatch.
    route_before = {os.path.relpath(os.path.join(folder, name), run):
                    Path(folder, name).read_bytes()
                    for folder, _, names in os.walk(run) for name in names}
    tiny_args = ("route", "recommend", "--task", "Fix a typo in README", "--risk", "low",
                 "--complexity", "1", "--uncertainty", "low")
    code, tiny, err = council(repo, *tiny_args)
    table_ok, tiny_rows = route_table(tiny)
    tiny_seats = [(key, value) for key, value in tiny_rows.items() if key[0] == "seat" and key[2] == "disposition"]
    check("route recommend: tiny low-risk work gets a compatible solo plan",
          code == 0 and table_ok and route_value(tiny_rows, "schema", "route", "version") == "1" and
          route_value(tiny_rows, "run", "route", "policy") == "adaptive" and
          route_value(tiny_rows, "run", "route", "size") == "solo" and
          route_value(tiny_rows, "assessment", "route", "risk") == "low" and
          route_value(tiny_rows, "assessment", "route", "complexity") == "1" and
          route_value(tiny_rows, "assessment", "route", "complexity-band") == "low" and
          route_value(tiny_rows, "assessment", "route", "uncertainty") == "low" and
          route_value(tiny_rows, "verification", "route", "level") == "self" and
          sum(value[0] == "selected" for _, value in tiny_seats) == 1 and
          all(value[0] in ("selected", "skipped") and value[1] for _, value in tiny_seats), tiny + err)
    code, tiny_again, err = council(repo, *tiny_args)
    check("route recommend: identical inputs give byte-identical advice", code == 0 and tiny_again == tiny, tiny_again + err)
    for wording in ("Author a README", "Build docs", "Fix a rapid typo", "Reduce token usage"):
        code, advice, err = council(repo, "route", "recommend", "--task", wording)
        table_ok, advice_rows = route_table(advice)
        check("route recommend: incidental keyword letters do not inflate " + wording,
              code == 0 and table_ok and route_value(advice_rows, "assessment", "route", "risk") == "low" and
              route_value(advice_rows, "run", "route", "size") == "solo", advice + err)
    code, auth_advice, err = council(repo, "route", "recommend", "--task", "Fix refresh token authorization")
    table_ok, auth_rows = route_table(auth_advice)
    check("route recommend: actual authorization work still activates security routing",
          code == 0 and table_ok and route_value(auth_rows, "assessment", "route", "risk") == "high" and
          route_value(auth_rows, "seat", "security", "disposition") == "selected", auth_advice + err)
    code, refresh_advice, err = council(repo, "route", "recommend", "--task", "Rotate refresh tokens")
    table_ok, refresh_rows = route_table(refresh_advice)
    check("route recommend: refresh tokens infer security and adversarial verification without overrides",
          code == 0 and table_ok and route_value(refresh_rows, "assessment", "route", "risk") == "high" and
          route_value(refresh_rows, "seat", "security", "disposition") == "selected" and
          route_value(refresh_rows, "verification", "route", "level") == "adversarial", refresh_advice + err)

    code, high, err = council(repo, "route", "recommend", "--task", "Change authentication and persistent user records",
                              "--risk", "high", "--complexity", "8", "--uncertainty", "high",
                              "--surface", "security", "--surface", "data")
    table_ok, high_rows = route_table(high)
    high_seats = [(key, value) for key, value in high_rows.items() if key[0] == "seat" and key[2] == "disposition"]
    check("route recommend: high-risk persistent security work escalates and explains seats",
          code == 0 and table_ok and route_value(high_rows, "assessment", "route", "risk") == "high" and
          route_value(high_rows, "run", "route", "size") == "full" and
          route_value(high_rows, "assessment", "route", "complexity") == "8" and
          route_value(high_rows, "assessment", "route", "complexity-band") == "high" and
          route_value(high_rows, "assessment", "route", "uncertainty") == "high" and
          route_value(high_rows, "verification", "route", "level") == "adversarial" and
          route_value(high_rows, "seat", "security", "disposition") == "selected" and
          route_value(high_rows, "seat", "data", "disposition") == "selected" and
          sum(value[0] == "selected" for _, value in high_seats) > 1 and
          all(value[1] for _, value in high_seats), high + err)
    code, data_advice, err = council(repo, "route", "recommend", "--task", "Database migration", "--agent-cap", "4")
    table_ok, data_rows = route_table(data_advice)
    check("route recommend: a capped migration keeps its data specialist",
          code == 0 and table_ok and route_value(data_rows, "assessment", "route", "risk") == "high" and
          route_value(data_rows, "seat", "data", "disposition") == "selected" and
          route_value(data_rows, "budget", "route", "selected-agents") == "4", data_advice + err)
    code, mixed_advice, err = council(repo, "route", "recommend", "--task", "Auth database migration", "--agent-cap", "4")
    table_ok, mixed_rows = route_table(mixed_advice)
    check("route recommend: a cap-omitted relevant lens is called out as constrained",
          code == 0 and table_ok and route_value(mixed_rows, "seat", "security", "disposition") == "selected" and
          route_value(mixed_rows, "seat", "data", "disposition") == "skipped" and
          route_value(mixed_rows, "run", "route", "status") == "constrained", mixed_advice + err)

    code, capped, err = council(repo, "route", "recommend", "--task", "Change authentication and persistent user records",
                                "--risk", "high", "--complexity", "8", "--uncertainty", "high",
                                "--surface", "security", "--surface", "data", "--agent-cap", "1",
                                "--budget-tokens", "1000")
    table_ok, cap_rows = route_table(capped)
    selected = sum(value[0] == "selected" for key, value in cap_rows.items()
                   if key[0] == "seat" and key[1] != "chair" and key[2] == "disposition")
    estimated = route_value(cap_rows, "budget", "route", "estimated-tokens")
    check("route recommend: a small cap is honored without pretending high-risk work fits its token ceiling",
          code == 0 and table_ok and route_value(cap_rows, "budget", "route", "agent-cap") == "1" and
          selected <= 1 and route_value(cap_rows, "budget", "route", "selected-agents") == str(selected) and
          route_value(cap_rows, "budget", "route", "ceiling-tokens") == "1000" and
          route_value(cap_rows, "budget", "run", "token-ceiling") == "1000" and
          estimated.isdigit() and int(estimated) > 1000 and
          route_value(cap_rows, "verification", "route", "level") == "adversarial" and
          route_value(cap_rows, "run", "route", "status") == "needs-rescope" and
          route_value(cap_rows, "verification", "route", "status") == "unavailable",
          capped + err)

    code, classic, err = council(repo, "route", "recommend", "--task", "Fix a typo in README", "--classic")
    table_ok, classic_rows = route_table(classic)
    check("route recommend: classic static routing remains available",
          code == 0 and table_ok and route_value(classic_rows, "run", "route", "policy") == "classic" and
          route_value(classic_rows, "run", "route", "size") == "squad", classic + err)

    for bad_args in (("route", "recommend"),
                     ("route", "recommend", "--task", "x", "--risk", "urgent"),
                     ("route", "recommend", "--task", "x", "--complexity", "0"),
                     ("route", "recommend", "--task", "x", "--complexity", "11"),
                     ("route", "recommend", "--task", "x", "--uncertainty", "unknown"),
                     ("route", "recommend", "--task", "x", "--agent-cap", "0"),
                     ("route", "recommend", "--task", "x", "--agent-cap", "11"),
                     ("route", "recommend", "--task", "x", "--budget-tokens", "0"),
                     ("route", "recommend", "--task", "x", "--run", run)):
        code, _, err = council(repo, *bad_args)
        check("route recommend: rejects invalid " + " ".join(bad_args[2:]), code == 2 and bool(err.strip()), err)
    route_after = {os.path.relpath(os.path.join(folder, name), run):
                   Path(folder, name).read_bytes()
                   for folder, _, names in os.walk(run) for name in names}
    check("route recommend: advice does not alter an existing run or dispatch seats",
          route_after == route_before and read(plan_path) == good_plan, str(set(route_after) ^ set(route_before)))

    append(plan_path, "schema\tplan\tversion\t1\tduplicate for the drill\n")
    code, out, _ = council(repo, "run", "plan", "check")
    check("run plan check: rejects duplicate identities", code == 1 and "duplicate row" in out, out)
    write(plan_path, good_plan.replace("budget\trun\tagent-cap\t10", "budget\trun\tagent-cap\t2"))
    code, out, _ = council(repo, "run", "plan", "check")
    check("run plan check: rejects a roster over its plan cap", code == 1 and "planned agent runs exceed the plan cap" in out, out)
    write(plan_path, good_plan + "budget\tverify-plan\tagent-runs\t8\ta Workflow of eight verifiers\n")
    code, out, _ = council(repo, "run", "plan", "check")
    check("run plan check: a Workflow seat counts every agent it starts — three workers and eight verifiers are 11 of cap 10",
          code == 1 and "11 planned agent runs exceed the plan cap 10" in out, out)
    write(plan_path, good_plan + "budget\tverify-plan\tagent-runs\t7\ta Workflow of seven verifiers\n")
    code, out, _ = council(repo, "run", "plan", "check")
    code_s, shown, _ = council(repo, "run", "plan", "show")
    check("run plan check: agent runs that fit the cap pass, and the plan shows the Workflow's count",
          code == 0 and "10 agent run(s) of cap 10" in out and code_s == 0 and "7 agent runs" in shown, out + shown)
    for bad, want in (("budget\tchair\tagent-runs\t2\tno\n", "the Chair is not an agent run"),
                      ("budget\tverify-plan\tagent-runs\t0\tno\n", "agent-runs must be an integer from 1 to 1000"),
                      ("budget\tghost\tagent-runs\t2\tno\n", "a seat budget belongs only to a selected seat: ghost")):
        write(plan_path, good_plan + bad)
        code, out, _ = council(repo, "run", "plan", "check")
        check("run plan check: agent-runs is refused — " + want, code == 1 and want in out, out)
    write(plan_path, good_plan)
    write(plan_path, "\n".join(line for line in good_plan.splitlines() if "\tchair\t" not in line) + "\n")
    code, out, _ = council(repo, "run", "plan", "check")
    check("run plan check: requires exactly one selected Chair", code == 1 and "select exactly one Chair" in out, out)
    write(plan_path, "\n".join(line for line in good_plan.splitlines() if "\tverify-plan\t" not in line) + "\n")
    code, out, _ = council(repo, "run", "plan", "check")
    check("run plan check: independent verification needs a selected verifier",
          code == 1 and "independent verification needs a selected verifier" in out, out)
    write(plan_path, good_plan.replace("run\trun\tsize\tsquad", "run\trun\tsize\tsolo"))
    code, out, _ = council(repo, "run", "plan", "check")
    check("run plan check: Solo cannot select delegated agents", code == 1 and "Solo must not select" in out, out)
    write(plan_path, "\n".join(line for line in good_plan.replace("run\trun\tsize\tsquad", "run\trun\tsize\tfull").splitlines()
                                if "\tgone\t" not in line) + "\n")
    code, out, _ = council(repo, "run", "plan", "check")
    check("run plan check: Full needs a broader selected team", code == 1 and "Full needs at least four" in out, out)
    write(plan_path, good_plan)
    code, out, err = council(repo, "seat", "outsider", "running", "agent=nope")
    check("seat: refuses to start an identity the valid plan did not select",
          code == 2 and "does not mark it selected" in err, out + err)

    budget_repo = new_repo(tmp, "spend-ceiling")
    write(os.path.join(budget_repo, ".council", "council.config.md"), "# Council config\n")
    _, budget_run, _ = council(budget_repo, "run", "open", "council-review")
    budget_run = budget_run.strip()
    write_plan(budget_run, selected=("worker",), verification="self", estimated_tokens=420000)
    append(os.path.join(budget_run, "run-plan.tsv"), "budget\trun\ttoken-ceiling\t600000\towner limit\n")
    code, out, err = council(budget_repo, "run", "plan", "check")
    check("spend: a positive optional ceiling is a valid plan row", code == 0, out + err)
    code, out, err = council(budget_repo, "run", "plan", "show")
    check("spend: the checked plan shows the owner's ceiling", code == 0 and "owner ceiling: 600000 tokens" in out, out + err)
    council(budget_repo, "seat", "worker", "running", "agent=a1")
    council(budget_repo, "seat", "worker", "done", "agent=a1", "tokens=300000")
    check("spend: usage below estimate raises no budget event",
          not any(e[3] in ("run.estimate_passed", "run.ceiling_passed") for e in events(budget_run)))
    council(budget_repo, "seat", "worker", "running", "agent=a2")
    code, _, err = council(budget_repo, "seat", "worker", "done", "agent=a2", "tokens=327000")
    check("spend: crossing the ceiling tells the Chair to ask before more work",
          code == 0 and "over its ceiling of 600000" in err and "ask before starting more" in err, err)
    council(budget_repo, "seat", "worker", "done", "agent=a2", "tokens=327000")
    budget_events = [e[3] for e in events(budget_run)]
    check("spend: each estimate and ceiling event is recorded once, even after a repeated report",
          budget_events.count("run.estimate_passed") == 1 and budget_events.count("run.ceiling_passed") == 1,
          budget_events)
    code, out, err = council(budget_repo, "run", "events", "check")
    check("spend: the stream with the two budget events remains valid", code == 0, out + err)
    code, out, err = council(budget_repo, "run", "close")
    check("close: exact usage is compared with the whole estimate",
          code == 0 and "estimated ~420k (about 49% over)" in out and
          "estimated ~420k (about 49% over)" in read(os.path.join(budget_run, "session-state.md")), out + err)
    million = new_repo(tmp, "spend-million")
    write(os.path.join(million, ".council", "council.config.md"), "# Council config\n")
    _, million_run, _ = council(million, "run", "open", "council-review")
    million_run = million_run.strip()
    write_plan(million_run, selected=("worker",), verification="self", estimated_tokens=1500000)
    council(million, "seat", "worker", "done", "agent=m1", "tokens=1,600,000")
    code, out, err = council(million, "run", "close")
    check("close: an estimate past a million is written as the total is — ~1.5M, never ~1500k",
          code == 0 and "~1.6M tokens across 1 agent run(s) · estimated ~1.5M (about 7% over)" in out and
          "estimated ~1.5M (about 7% over)" in read(os.path.join(million_run, "session-state.md")), out + err)

    legacy = new_repo(tmp, "legacy-plan")
    write(os.path.join(legacy, ".council", "council.config.md"), "# Council config — legacy plan\n")
    _, legacy_run, _ = council(legacy, "run", "open", "council-review")
    legacy_run = legacy_run.strip()
    os.remove(os.path.join(legacy_run, "run-plan.tsv"))
    write(os.path.join(legacy_run, "session-state.md"), read(os.path.join(legacy_run, "session-state.md")).replace("plan-schema: 1\n", ""))
    os.remove(os.path.join(legacy_run, "events.tsv"))
    write(os.path.join(legacy_run, "session-state.md"), read(os.path.join(legacy_run, "session-state.md")).replace("events-schema: 1\n", ""))
    code, out, err = council(legacy, "run", "events", "check")
    check("legacy run: no event stream is required", code == 0 and "legacy run" in out, out + err)
    write(os.path.join(legacy_run, "events.tsv"), "schema\tseq\tat\ttype\tsubject\tvalue\tdetail\n")
    code, _, err = council(legacy, "run", "events", "check")
    check("run events check: rejects a stream without a schema stamp",
          code == 1 and "without an events-schema stamp" in err, err)
    os.remove(os.path.join(legacy_run, "events.tsv"))
    code, out, err = council(legacy, "seat", "old-worker", "running", "agent=old")
    check("legacy run: a pre-contract run without a plan still works", code == 0 and "old-worker" in out, out + err)
    council(legacy, "run", "close", "--status", "abandoned")

@part("timing")
def event_races(tmp):
    event_repo = new_repo(tmp, "event-contract")
    write(os.path.join(event_repo, ".council", "council.config.md"), "# Council config — events\n")
    _, event_run, _ = council(event_repo, "run", "open", "council-review")
    event_run = event_run.strip()
    finished = events_together(event_repo, event_run, [f"parallel-{i}" for i in range(3)])
    code, out, err = council(event_repo, "run", "events", "check", "--run", event_run)
    check("run events: records appended at the same moment get distinct, continuous sequence numbers",
          all(rc == 0 for rc, _, _ in finished) and code == 0 and len(events(event_run)) == 4 and
          {e[4] for e in events(event_run)[1:]} == {"parallel-0", "parallel-1", "parallel-2"},
          out + err + "\n" + gates_detail(finished), full=True)
    event_lock_path = os.path.join(event_run, "events.tsv.lock")
    os.mkdir(event_lock_path)
    write(os.path.join(event_lock_path, "owner"), "99999999\n")
    code, out, err = council(event_repo, "run", "events", "check", "--run", event_run)
    check("run events: reclaims a lock left by a terminated writer",
          code == 0 and "valid" in out and not os.path.exists(event_lock_path), out + err)
    os.mkdir(event_lock_path)
    old_time = time.time() - 30
    os.utime(event_lock_path, (old_time, old_time))
    code, out, err = council(event_repo, "run", "events", "check", "--run", event_run)
    check("run events: reclaims an old lock with no owner file",
          code == 0 and "valid" in out and not os.path.exists(event_lock_path), out + err)

    write_plan(event_run, selected=("racer",))
    os.mkdir(event_lock_path)
    future_time = time.time() + 300  # Hold this test lock while two seat commands contend.
    os.utime(event_lock_path, (future_time, future_time))
    first = subprocess.Popen([BASH, CLI, "seat", "racer", "running", "agent=a", "--run", event_run],
                             cwd=event_repo, env=GIT_ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, encoding="utf-8", errors="replace")
    seat_file = os.path.join(event_run, "seats.tsv")
    deadline = time.monotonic() + 8
    while "racer\trunning\t" not in read(seat_file) and time.monotonic() < deadline:
        time.sleep(0.05)
    first_wrote = "racer\trunning\t" in read(seat_file)
    second = subprocess.Popen([BASH, CLI, "seat", "racer", "done", "agent=a", "--run", event_run],
                              cwd=event_repo, env=GIT_ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, encoding="utf-8", errors="replace")
    time.sleep(0.5)
    second_waited = "racer\trunning\t" in read(seat_file)
    os.rmdir(event_lock_path)
    first_result = first.communicate(timeout=120)
    second_result = second.communicate(timeout=120)
    racer_events = [row[5] for row in events(event_run) if row[3:5] == ["seat.updated", "racer"]]
    check("run events: concurrent updates to one seat preserve state and event order",
          first_wrote and second_waited and first.returncode == 0 and second.returncode == 0 and
          racer_events == ["running", "done"] and "racer\tdone\t" in read(seat_file),
          str((first.returncode, first_result, second.returncode, second_result, racer_events, read(seat_file))),
          full=True)
    append(os.path.join(event_run, "events.tsv"), "1\t9\tbroken\n")
    code, out, _ = council(event_repo, "run", "events", "check", "--run", event_run)
    check("run events check: rejects a truncated or discontinuous row", code == 1 and "invalid row" in out, out)
    code, out, _ = council(event_repo, "doctor")
    check("doctor: flags a damaged event stream", "invalid event stream" in out, out)
    os.remove(os.path.join(event_run, "events.tsv"))
    code, _, err = council(event_repo, "run", "events", "check", "--run", event_run)
    check("run events check: a stamped run cannot silently lose its stream", code == 1 and "missing" in err, err)
    code, _, err = council(event_repo, "gate", "after-loss", "--run", event_run, "--", "true")
    check("run events: a later action reports a lost stream instead of silently recreating it",
          code == 0 and "not recorded" in err and not os.path.exists(os.path.join(event_run, "events.tsv")), err)


@part("timing")
def event_lock_stress(tmp):
    """Rounds of six records at once on one run. A call waiting for the events lock once died under set -u
    when the holder released between its look at the owner file and its read, and its event was lost."""
    stress = new_repo(tmp, "event-stress")
    write(os.path.join(stress, ".council", "council.config.md"), "# Council config — event stress\n")
    _, stress_run, _ = council(stress, "run", "open", "council-review")
    stress_run = stress_run.strip()
    trouble = []
    for r in range(4):   # about a second a round on Windows Git Bash; the old lock lost a record about one round in six
        names = [f"r{r}-g{i}" for i in range(6)]
        finished = events_together(stress, stress_run, names)
        got = sorted(e[4] for e in events(stress_run) if e[3] == "gate.finished" and e[4].startswith(f"r{r}-"))
        if got != names or any(rc != 0 or err.strip() for rc, _, err in finished):
            trouble.append("round %d recorded %s\n%s" % (r, got, gates_detail(finished)))
    code, out, err = council(stress, "run", "events", "check", "--run", stress_run)
    check("run events: four rounds of six records at once leave all 24 events; every writer exits 0 and is silent on stderr",
          not trouble and code == 0 and len(events(stress_run)) == 25, out + err + "\n".join(trouble), full=True)


@part("timing")
def gate_lock(tmp):
    """One `council gate` per run at a time. A real run started `gate --all` twice: the second copy
    overwrote the first's saved output and was stopped, and its results became the run's events and
    baseline. A second call must refuse before it writes anything."""
    lk = new_repo(tmp, "gate-lock")
    waits = 'echo started; echo x >> ran.log; while [ ! -f go.flag ]; do sleep 0.2; done; echo finished'
    write(os.path.join(lk, ".council", "council.config.md"),
          "# Council config — gate lock\n\n## Gates\n"
          "| Gate | Command | Run at | Mandatory | Checked | Needs | Side effects |\n|---|---|---|---|---|---|---|\n"
          f"| tests | `{waits}` | grounding | yes | ok | — | none |\n"
          "| lint | `echo lint-ok` | grounding | yes | ok | — | none |\n")
    _, lrun, _ = council(lk, "run", "open", "council-review")
    lrun = lrun.strip()
    lock, saved = os.path.join(lrun, "gates.lock"), os.path.join(lrun, "gates", "tests.txt")

    def folder():
        """Every file under the run folder with its bytes — what a refused call must leave as it was."""
        seen = {}
        for base, _, names in os.walk(lrun):
            for name in names:
                with open(os.path.join(base, name), "rb") as f:
                    seen[slash(os.path.relpath(os.path.join(base, name), lrun))] = f.read()
        return seen

    first = subprocess.Popen([BASH, CLI, "gate", "--all", "--at", "grounding", "--run", lrun], cwd=lk, env=GIT_ENV,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    deadline = time.monotonic() + 60
    while not (os.path.isfile(os.path.join(lock, "owner")) and "started" in read(saved)) and time.monotonic() < deadline:
        time.sleep(0.1)
    held = read(os.path.join(lock, "owner")).splitlines()
    before = folder()
    second = [council(lk, "gate", "--run", lrun, *args) for args in (
        ("--all", "--at", "grounding"), ("--all", "--at", "verify"), ("tests",), ("lint",),
        ("adhoc", "--", "echo second-copy"))]
    after = folder()
    check("gate lock: while one gate call runs, its lock names the process and when it started",
          len(held) == 2 and held[0].isdigit() and re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d", held[1]) is not None,
          str(held))
    check("gate lock: a second gate call for the same run — the set again, another stage, the same gate, another gate, "
          "an ad-hoc one — is refused with exit 2 and says which run, since when, and that nothing was started",
          len(held) == 2 and all(code == 2 and out == "" and "checks are already running for this run" in err
                                 and os.path.basename(lrun) in err and "started " + held[1] in err
                                 and "wait for them to finish; nothing was started" in err for code, out, err in second),
          "\n".join("exit %d · stdout %r · stderr %r" % s for s in second), full=True)
    check("gate lock: a refused call writes nothing — no output file touched, no event, no baseline, no new file",
          after == before and sorted(n for n in after if n.startswith("gates/")) == ["gates/tests.txt"]
          and after.get("gates/tests.txt") == b"started\n" and len(events(lrun)) == 1,
          "changed: %s" % sorted(n for n in set(before) | set(after) if before.get(n) != after.get(n)), full=True)
    write(os.path.join(lk, "go.flag"), "")
    try:
        out1, err1 = first.communicate(timeout=120)
    except subprocess.TimeoutExpired:
        first.kill()
        out1, err1 = first.communicate()
        err1 += " (still running after 120 s)"
    done = [e[4:6] for e in events(lrun) if e[3] == "gate.finished"]
    check("gate lock: the first call finishes as if nobody had tried — each gate ran once, its own output is the saved "
          "one and the baseline, one event per gate — and its lock is gone",
          first.returncode == 0 and "gates: 2 ran — all pass" in out1 and err1.strip() == ""
          and read(os.path.join(lk, "ran.log")) == "x\n" and read(saved) == "started\nfinished\n"
          and read(os.path.join(lrun, "gates", "baseline", "tests.txt")) == "started\nfinished\n"
          and done == [["tests", "passed"], ["lint", "passed"]] and not os.path.exists(lock),
          "exit %s · stdout %r · stderr %r · events %s" % (first.returncode, out1, err1, done), full=True)
    code, out, err = council(lk, "gate", "lint", "--run", lrun)
    code2, out2, err2 = council(lk, "gate", "--all", "--at", "grounding", "--run", lrun)
    check("gate lock: gate calls one after another still run, and each leaves no lock behind",
          code == 0 and "gate lint: pass" in out and err.strip() == "" and code2 == 0 and "gates: 2 ran — all pass" in out2
          and err2.strip() == "" and len([e for e in events(lrun) if e[3] == "gate.finished"]) == 5
          and not os.path.exists(lock), out + err + out2 + err2)

    # A lock whose process is gone is cleared by the next call, which says so in one line.
    os.mkdir(lock)
    write(os.path.join(lock, "owner"), "99999999\n2026-01-01 00:00:00\n")
    code, out, err = council(lk, "gate", "lint", "--run", lrun)
    check("gate lock: a lock left by a process that is gone is cleared, in one line, and the gate runs",
          code == 0 and "gate lint: pass" in out and not os.path.exists(lock)
          and [x for x in err.splitlines() if x.strip()] == [
              "council: cleared a gate lock left by a call that is no longer running "
              "(process 99999999, started 2026-01-01 00:00:00)"], out + err)
    os.mkdir(lock)                                   # a call stopped between taking the lock and signing it
    old_time = time.time() - 30
    os.utime(lock, (old_time, old_time))
    code, out, err = council(lk, "gate", "lint", "--run", lrun)
    check("gate lock: an old lock with no owner file is cleared too",
          code == 0 and "gate lint: pass" in out and "cleared a gate lock" in err and not os.path.exists(lock), out + err)

    # The holder stopped: by a signal its shell can catch, it releases the lock itself and records no
    # verdict for the stopped gate; killed outright, the next call clears what it left.
    owner = slash(os.path.join(lock, "owner"))
    before_stop = len(events(lrun))
    code, out, err = council(lk, "gate", "stopped", "--run", lrun, "--",
                             "kill -TERM \"$(head -n 1 '%s')\"; sleep 1; echo went-on" % owner)
    check("gate lock: a gate call stopped by a signal releases its lock and records no result for the stopped gate",
          code == 143 and not os.path.exists(lock) and len(events(lrun)) == before_stop
          and not os.path.exists(os.path.join(lrun, "gates", "stopped.json")), "exit %d · %s%s" % (code, out, err))
    code, out, err = council(lk, "gate", "killed", "--run", lrun, "--", "kill -9 \"$(head -n 1 '%s')\"" % owner)
    left = os.path.isdir(lock)
    code2, out2, err2 = council(lk, "gate", "lint", "--run", lrun)
    check("gate lock: a gate call killed outright leaves its lock, and the next call clears it and runs",
          code != 0 and left and len(events(lrun)) == before_stop + 1 and code2 == 0 and "gate lint: pass" in out2
          and "cleared a gate lock left by a call that is no longer running" in err2 and not os.path.exists(lock),
          "killed: exit %d · %s%s · lock left: %s · next: exit %d · %s%s" % (code, out, err, left, code2, out2, err2))

    # Started at the same moment: whichever wins runs; every other either ran after it or was refused
    # whole. Each gate that ran has exactly one event, and none is left half-recorded.
    names = [f"race-{i}" for i in range(4)]
    before_race = len(events(lrun))
    finished = gates_together(lk, lrun, names)
    ran = [name for name, (rc, _, _) in zip(names, finished) if rc == 0]
    raced = sorted(e[4] for e in events(lrun)[before_race:])
    code, out, err = council(lk, "run", "events", "check", "--run", lrun)
    check("gate lock: four gate calls at the same moment — at least one runs, every other runs or is refused whole, and "
          "only the ones that ran leave an event and files",
          ran and all(rc == 0 and "pass" in o and e.strip() == "" or rc == 2 and o == "" and "nothing was started" in e
                      for rc, o, e in finished)
          and raced == sorted(ran) and code == 0 and not os.path.exists(lock)
          and sorted(n[:-4] for n in os.listdir(os.path.join(lrun, "gates")) if n.startswith("race-") and n.endswith(".txt")) == sorted(ran),
          out + err + "\n" + gates_detail(finished), full=True)


@part("runs")
def runs_change_index(tmp):
    # Change index, with an earlier review on disk
    write(os.path.join(repo, ".council", "reviews", "2026-08-01-stats.md"),
          "---\ntitle: Stats review\nkind: review\nareas: src/**\ndate: 2026-08-01\nstatus: final\nrun: 2026-08-01-100000-review\n---\n"
          "# Review — stats\n1 · P2 · Principle 3 · src/stats.py:1 · average divides by zero on an empty list\n")
    write(os.path.join(repo, ".council", "reviews", "2026-08-02-scripts.md"),
          "---\ntitle: Scripts review\nkind: review\nareas:\n  - scripts/**\n  - tools/**\ndate: 2026-08-02\nstatus: final\n---\n"
          "# Review — scripts\nCompare old/src/stats.py with the new one.\n")
    code, out, err = council(repo, "index")
    idx = read(os.path.join(run, "index.md"))
    check("index: succeeds", code == 0 and "index: 5 files" in out, out + err)
    check("index: lists the changed files", all(f"## {f}  (" in idx for f in
          ["src/stats.py", "src/report.py", "scripts/deploy.sh", "README.md", "tests/test_stats.py"]), idx)
    check("index: never lists the council's own files", ".council" not in idx.split("\n", 3)[-1], idx)
    check("index: finds the new symbol", re.search(r"symbols: .*\bmedian\b", idx) is not None, idx)
    check("index: finds shell functions", "symbols: ship_it" in idx, idx)
    readme = idx.split("## README.md", 1)[-1].split("\n## ", 1)[0]
    check("index: text files get hunks but no symbols", "- hunks:" in readme and "- symbols:" not in readme, readme)
    check("index: finds its callers by name", re.search(r"callers: .*src/report\.py:\d+ \(median\)", idx) is not None, idx)
    check("index: finds the covering test", "tests: tests/test_stats.py" in idx, idx)
    check("index: knows a test file by its path", "tests: (this is a test file)" in idx, idx)
    check("index: notes uncommitted changes", "uncommitted" in idx, idx)
    check("index: records the base in the state", re.search(r"^base: [0-9a-f]{40}$", read(os.path.join(run, "session-state.md")), re.MULTILINE) is not None)
    check("index: lists earlier council work on the changed files", "earlier council work on these files: 3 mention(s)" in out
          and "- src/stats.py — reviews/2026-08-01-stats.md:10 — 1 · P2" in idx
          and "src/report.py — reviews/2026-08-01-stats.md — (its areas cover src/**)" in idx, out + idx)
    check("index: a deliverable's areas: may be a YAML list", "scripts/deploy.sh — reviews/2026-08-02-scripts.md — (its areas cover scripts/**)" in idx, idx)
    check("index: a path inside a longer path is not a mention", "reviews/2026-08-02-scripts.md:" not in idx, idx)
    code, out, _ = council(repo, "prior", "README.md")
    check("prior: says so when nothing earlier mentions a path", code == 0 and "no earlier council work" in out, out)
    code, out, _ = council(repo, "prior", "src/report.py")
    check("prior: a deliverable whose areas cover the path counts", "reviews/2026-08-01-stats.md" in out and "areas cover src/**" in out, out)
    pr = new_repo(tmp, "priors")
    write(os.path.join(pr, ".council", "council.config.md"), "# c\n")
    prtop = slash(git(pr, "rev-parse", "--show-toplevel"))
    prv = os.path.join(pr, ".council", "reviews")
    write(os.path.join(prv, "2026-09-01-brace.md"), "---\nareas: webapp/frontend/src/**/*.{js,jsx}\n---\n# r\n")
    write(os.path.join(prv, "2026-09-02-yaml.md"), "---\nareas:\n  - tests/**   # the suites\n---\n# p\n")
    with open(os.path.join(prv, "2026-09-03-bom.md"), "w", encoding="utf-8-sig", newline="\n") as f:
        f.write("---\nareas: docs/** lib/**; tools/**\n---\n# s\n")
    write(os.path.join(prv, "2026-09-04-cites.md"),
          "# m\n1 · P2 · ./scripts/deploy.sh:4 — q\n2 · P2 · api.py.bak shipped\n3 · P2 · res://scripts/ai/role_def.gd:3 — r\n"
          "4 · P3 · webapp\\backend\\main.py:7 — w\n" f"5 · P3 · {prtop}/core/x.py:5 — abs\n")
    code, out, _ = council(pr, "prior", "webapp/frontend/src/App.jsx", "tests/test_a.py", "lib/x.py", "tools/y.sh")
    check("prior: areas may be brace globs, a YAML list with comments, or blank- and semicolon-separated behind a BOM",
          "(its areas cover webapp/frontend/src/**/*.{js,jsx})" in out and "tests/test_a.py — reviews/2026-09-02-yaml.md — (its areas cover tests/**)" in out
          and "lib/x.py — reviews/2026-09-03-bom.md" in out and "tools/y.sh — reviews/2026-09-03-bom.md" in out and "prior: 4 mention(s)" in out, out)
    code, out, _ = council(pr, "prior", "scripts/deploy.sh", "scripts/ai/role_def.gd", "webapp/backend/main.py", "core/x.py")
    check("prior: a mention may start with ./, res:// or the repo's own path, and use backslashes",
          all(f"{q} — reviews/2026-09-04-cites.md:{n} —" in out for q, n in
              [("scripts/deploy.sh", 2), ("scripts/ai/role_def.gd", 4), ("webapp/backend/main.py", 5), ("core/x.py", 6)]), out)
    code, out, _ = council(pr, "prior", "api.py")
    check("prior: a path inside a longer name (api.py.bak) is not a mention", "no earlier council work" in out, out)
    for i in range(45):
        write(os.path.join(prv, f"2026-07-{i:02d}-many.md"), "---\nareas: src/**\n---\n# many\n")
    code, out, _ = council(pr, "prior", "src/a.py")
    check("prior: past 40 mentions it says how many it left out", out.count("src/a.py — ") == 40 and "prior: 40 of 45 mention(s) shown" in out, out)

@part("collect")
def index_limits(tmp):
    # The change index past its file cap (80 files; lowered here, since 80 take minutes on a busy Windows machine)
    big = new_repo(tmp, "bigchange")
    write(os.path.join(big, "a.txt"), "x\n")
    git(big, "add", "-A")
    git(big, "commit", "-q", "-m", "init")
    git(big, "checkout", "-q", "-b", "big")
    for i in range(1, 5):
        write(os.path.join(big, "core", f"mod_{i:02d}.txt"), f"core {i}\n")
    write(os.path.join(big, "package-lock.json"), "{}\n")
    for i in range(1, 6):
        write(os.path.join(big, "webapp", "backend", f"orders_{i}.py"), f"def place_order_{i}(req):\n    return req\n")
    git(big, "add", "-A")
    git(big, "commit", "-q", "-m", "big")
    write(os.path.join(big, ".council", "council.config.md"), "# Council config — big\n")
    code, brun, _ = council(big, "run", "open", "council-review")
    code, out, err = council(big, "index", env={"COUNCIL_INDEX_CAP": "4"})
    bidx = read(os.path.join(brun.strip(), "index.md"))
    check("index: past the file cap, every other changed file is still named, as a file in scope",
          code == 0 and "## Past the 4-file cap" in bidx
          and all(f"\n## webapp/backend/orders_{i}.py  (added" in bidx for i in range(1, 6)), out + err + bidx[-800:])
    check("index: files past the cap are counted apart from lockfiles, and the output line says so",
          "past the 4-file cap: 5" in bidx and "not indexed: 1 (lockfiles" in bidx and "5 more past the 4-file cap" in out,
          out + bidx[:400])
    # The list of names has a bound of its own: a repo-wide change must not flood the file every seat reads.
    code, out, err = council(big, "index", env={"COUNCIL_INDEX_CAP": "4", "COUNCIL_INDEX_NAMECAP": "2"})
    bidx = read(os.path.join(brun.strip(), "index.md"))
    check("index: past the cap, only the first few files are named one by one; the rest are counted",
          code == 0 and bidx.count("past the 4-file cap: not indexed") == 2
          and "… and 3 more, not named one by one: git diff --name-only" in bidx, out + err + bidx[-600:])

    # The change index: renames, non-ASCII names, untracked binaries, a nested worktree, a relative --run
    uni = new_repo(tmp, "unicode")
    write(os.path.join(uni, "big_module.py"), "".join(f"x_{i} = 1\n" for i in range(1, 301)) + "def load():\n    return 1\n")
    write(os.path.join(uni, "sub", "keep.txt"), "k\n")
    git(uni, "add", "-A")
    git(uni, "commit", "-q", "-m", "base")
    git(uni, "checkout", "-q", "-b", "feat")
    write(os.path.join(uni, "café.py"), "def cafe_price():\n    return 3\n")
    git(uni, "mv", "big_module.py", "core_module.py")
    append(os.path.join(uni, "core_module.py"), "def save():\n    return 2\n")
    git(uni, "add", "-A")
    git(uni, "commit", "-q", "-m", "rename")
    write(os.path.join(uni, "ünï new.py"), "def helper_new():\n    pass\n")
    with open(os.path.join(uni, "new_logo.png"), "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\n")
    git(uni, "worktree", "add", "-q", "-b", "feat-x", os.path.join(uni, ".claude", "worktrees", "feat-x"))
    write(os.path.join(uni, ".council", "council.config.md"), "# Council config — unicode\n")
    code, urun, _ = council(uni, "run", "open", "council-review")
    urun = urun.strip()
    code, out, err = council(uni, "index")
    uidx = read(os.path.join(urun, "index.md"))
    check("index: a non-ASCII file name is indexed as itself, with its lines and symbols",
          "## café.py  (added, +2/-0)" in uidx and "symbols: cafe_price" in uidx
          and "## ünï new.py  (new, untracked, +2/-0)" in uidx, out + err + uidx)
    moved = uidx.split("## core_module.py", 1)[-1].split("\n## ", 1)[0]
    check("index: a renamed file shows only its changed lines, and the path it came from",
          "  (renamed from big_module.py, +2/-0)" in moved and "- hunks: 303-304" in moved, uidx)
    check("index: an untracked binary file is marked binary, with no line count and no warning",
          "## new_logo.png  (new, untracked, binary)" in uidx and "null byte" not in err, err + uidx)
    check("index: a nested worktree's folder is not a changed file", ".claude/worktrees" not in uidx and "index: 4 files" in out, out + uidx)
    code, out, err = council(os.path.join(uni, "sub"), "index", "--run", "../.council/runs/" + os.path.basename(urun))
    check("index --run: a relative run path works from a subfolder", code == 0 and out.startswith("index: 4 files"), out + err)
    staged = new_repo(tmp, "staged")
    write(os.path.join(staged, "a.py"), "a = 1\n")
    git(staged, "add", "-A")
    git(staged, "commit", "-q", "-m", "init")
    git(staged, "checkout", "-q", "-b", "work")
    write(os.path.join(staged, "a.py"), "a = 2\n")
    git(staged, "add", "a.py")
    write(os.path.join(staged, ".council", "council.config.md"), "# Council config — staged\n")
    code, srun, _ = council(staged, "run", "open", "council-review")
    council(staged, "index")
    check("index: a staged-only change is noted as uncommitted", "+ uncommitted changes" in read(os.path.join(srun.strip(), "index.md")),
          read(os.path.join(srun.strip(), "index.md")))

@part("runs")
def runs_gates_and_seats(tmp):
    # Gates
    gates = os.path.join(run, "gates")
    code, out, _ = council(repo, "gates")
    check("gates: lists the configured gates", code == 0 and all(f"\n{g} ·" in "\n" + out for g in ["ok", "bad", "must", "piped", "anytime"]), out)
    check("gates: an empty Run-at cell stays empty (no column shift)", "anytime · true · run at: - · mandatory: no" in out, out)
    check("gates: a pipe inside backticks stays in the command", 'piped · printf "a|b" · run at: manual' in out, out)
    check("gates: shows side effects", "ship · echo shipped · run at: verify · mandatory: no · side effects: deploy, network" in out, out)
    code, out, _ = council(repo, "gate", "ok")
    check("gate: a passing gate exits 0", code == 0 and "pass (exit 0" in out, out)
    code, out, _ = council(repo, "gate", "bad")
    verdict = json.loads(read(os.path.join(gates, "bad.json")) or "{}")
    check("gate: a failing gate returns its own exit code", code == 3 and "FAIL (exit 3" in out, out)
    check("gate: the verdict JSON records the exit code", verdict.get("exit") == 3 and verdict.get("gate") == "bad", str(verdict))
    gate_events = [e for e in events(run) if e[3] == "gate.finished"]
    check("gate: passing and failing commands leave sequenced verdict events",
          len(gate_events) >= 2 and gate_events[-2][4:6] == ["ok", "passed"] and
          gate_events[-1][4:6] == ["bad", "failed"] and "exit=3" in gate_events[-1][6],
          str(gate_events[-2:]))
    check("gate: a failure shows its error line", "Error: boom" in out, out)
    check("gate: saves the full output", "Error: boom" in read(os.path.join(gates, "bad.txt")))
    code, out, _ = council(repo, "gate", "noisy", "--", "for i in $(seq 1 60); do echo step $i; done; echo 'Error: boom at the end'; exit 3")
    check("gate: prints a failure excerpt, not the whole output",
          code == 3 and "Error: boom at the end" in out and "step 30" not in out
          and len(read(os.path.join(gates, "noisy.txt")).splitlines()) == 61, out)
    code, out, _ = council(repo, "gate", "piped")
    check("gate: a quoted pipe in a configured command runs as written", code == 0 and read(os.path.join(gates, "piped.txt")) == "a|b", out)
    code, out, _ = council(repo, "gate", "adhoc", "--", "echo hi")
    check("gate: runs an ad-hoc command after --", code == 0 and "gate adhoc: pass" in out, out)
    code, out, _ = council(repo, "gate", "quoted", "--", 'echo "a  b" && exit 5')
    verdict = json.loads(read(os.path.join(gates, "quoted.json")) or "{}")
    check("gate: one quoted command keeps its quotes and &&", code == 5 and read(os.path.join(gates, "quoted.txt")) == "a  b\n", out)
    check("gate: the verdict records the command as written", verdict.get("command") == 'echo "a  b" && exit 5', str(verdict))
    code, out, _ = council(repo, "gate", "words", "--", "printf", "(%s)", "two words")
    check("gate: separate words stay separate arguments", code == 0 and read(os.path.join(gates, "words.txt")) == "(two words)",
          out + read(os.path.join(gates, "words.txt")))
    code, out, _ = council(repo, "gate", "--all", "--at", "verify")
    check("gate --all: a failing optional gate doesn't fail the set", code == 0 and "gate bad: FAIL" in out and "gate must" not in out, out)
    check("gate --all --at: a gate with no Run-at value isn't run, and is never silent about it",
          "gate anytime: skipped \u2014 its Run at cell is empty" in out
          and not os.path.isfile(os.path.join(gates, "anytime.txt")), out)
    check("gate --all: skips a gate the config marks not runnable", "gate broken: skipped" in out, out)
    check("gate --all: skips a gate init never probed (it needs credentials)",
          "gate stripe: skipped" in out and not os.path.isfile(os.path.join(gates, "stripe.txt")), out)
    check("gate --all: never runs a gate with deploy, cost or hardware side effects",
          "gate ship: skipped — side effects" in out and not os.path.isfile(os.path.join(gates, "ship.txt")), out)
    check("gate --all: a row whose columns shifted never runs",
          "gate leaky: skipped — its row has" in out and not os.path.isfile(os.path.join(gates, "leaky.txt")), out)
    check("gate --all: runs only side effects on the safe list",
          "gate bill: skipped — side effects: billable API calls" in out and not os.path.isfile(os.path.join(gates, "bill.txt")), out)
    check("gate --all: the verdict line names the pass count, the failures and the skips",
          "gates: 2 ran \u2014 1 pass, 1 FAIL (bad, not mandatory) \u00b7 7 skipped" in out, out)
    check("gate --all --at: a row whose columns shifted is still reported, not filtered away",
          "gate leaky: skipped \u2014 its row has" in out, out)
    code2, out2, _ = council(repo, "gate", "--all", "--at=verify")
    check("gate --all --at=verify: the = form picks the same stage as --at verify",
          code2 == code and out2.strip().splitlines()[-1:] == out.strip().splitlines()[-1:], out2)
    code, out, _ = council(repo, "gate", "ship")
    check("gate <name>: runs a side-effect gate when named, with a warning", code == 0 and "side effects (deploy, network)" in out, out)
    code, out, _ = council(repo, "gate", "--all", "--at", "grounding")
    check("gate --all: a failing mandatory gate fails the set", code == 1 and "a mandatory gate failed" in out, out)
    check("gate --all: the verdict line marks a mandatory failure", "FAIL (must \u2014 mandatory)" in out, out)
    code, out, err = council(repo, "gate", "--all", "--at", "nobody-runs-here")
    check("gate --all --at: a stage that doesn't exist is refused, never a quietly empty set",
          code == 2 and "--at takes grounding or verify" in err, out + err)
    code, _, err = council(repo, "gate", "missing-gate")
    check("gate: an unknown gate name is an error", code == 2 and "no gate named" in err, err)

    # Seats and collect
    write(os.path.join(run, "brief.md"),
          "# Brief — eval\n## Seats\n"
          f"### fowler — Structure (Fowler)\n- ref: {ref('refactoring.md')}\n- out: seats/fowler.md\n- cap: 8 · budget: ~15 tool calls\n"
          f"### beck — Tests (Beck)\n- ref: {ref('quality-testing.md')}\n- out: seats/beck.md\n- cap: 2\n"
          "### gone — Missing\n- ref: none\n"
          "## Seats not called\n- ghost — nothing: no surface\n")
    write(os.path.join(run, "seats", "fowler.md"),
          f"# Fowler — Structure (council-review)\nref: {first_heading('refactoring.md')}\n## Index\n"
          "1 · P2 · Principle 3 · src/stats.py:7-9 · median has no empty guard\n")
    write(os.path.join(run, "seats", "beck.md"),
          "# Beck — Tests (council-review)\nref: not the real title\n## Index\n"
          "1 · P1 · Principle 5 · tests/test_stats.py:3 · no median test\n2 · P2 · Principle 5 · src/stats.py:1 · a\n"
          "3 · P3 · Principle 5 · src/stats.py:99 · a line that doesn't exist\n")
    code, out, _ = council(repo, "seat", "fowler", "running", "agent=a1")
    check("seat: records a running worker", code == 0 and "still working: fowler" in out, out)
    council(repo, "seat", "fowler", "done", "tokens=40000")
    council(repo, "seat", "beck", "running", "agent=a2")
    code, out, _ = council(repo, "seat", "beck", "done", "tokens=35500")
    check("seat: progress line counts done seats (not agents) and tokens", "seats: 2 of 2 done" in out and "~76k tokens so far" in out, out)
    code, out, _ = council(repo, "seat", "ghost", "skipped", "note=no surface")
    check("seat: skipped seats don't count", code == 0 and "seats: 2 of 2 done" in out, out)
    code, _, err = council(repo, "seat", "beck", "sleeping")
    check("seat: rejects an unknown state", code == 2, err)
    code, out, _ = council(repo, "seat", "gone", "failed", "note=timed out")
    check("seat: a failed worker shows in the progress line", "failed: gone" in out, out)
    code, out, _ = council(repo, "collect")
    check("collect: fails while seats are wrong", code == 1, out)
    check("collect: a correct seat is ok", re.search(r"^fowler\s+ok\s+1/8\s+\d+\s+ok\s+1/1", out, re.MULTILINE) is not None, out)
    check("collect: catches a ref: line that doesn't match the doc", "MISMATCH" in row(out, "beck"), out)
    check("collect: catches a seat over its item cap", "over-cap" in row(out, "beck"), out)
    check("collect: catches a broken citation", "broken-cites" in row(out, "beck"), out)
    check("collect: catches a missing seat file and its failed worker", re.search(r"^gone\s+missing.*state:failed", out, re.MULTILINE) is not None, out)
    write(os.path.join(run, "seats", "beck.md"),
          f"# Beck — Tests (council-review)\nref: {first_heading('quality-testing.md')}\n## Index\n"
          "1 · P1 · Principle 5 · tests/test_stats.py:3 · no median test\n")
    write(os.path.join(run, "seats", "gone.md"), "# Gone — Missing (council-review)\nref: none\n## Index\n(none) — nothing in scope\n")
    council(repo, "seat", "gone", "done")
    code, out, _ = council(repo, "collect")
    check("collect: passes once every seat is right", code == 0 and "all 3 seats in order" in out, out)
    brief_before = read(os.path.join(run, "brief.md"))
    plan_before = read(os.path.join(run, "run-plan.tsv"))
    write(os.path.join(run, "brief.md"), brief_before.replace("## Seats not called",
          "### verify-1 — Blind verifier\n- ref: none\n- out: verify-1.md\n## Seats not called"))
    append(os.path.join(run, "run-plan.tsv"), "seat\tverify-1\trole\tverifier\tChallenge only\n")
    council(repo, "seat", "verify-1", "queued")
    code, out, _ = council(repo, "collect")
    check("collect: a queued plan verifier in the brief does not count as a missing worker",
          code == 0 and "all 3 seats in order" in out and "verify-1" not in out, out)
    write(os.path.join(run, "brief.md"), brief_before)
    write(os.path.join(run, "run-plan.tsv"), plan_before)
    council(repo, "seat", "verify-1", "skipped")
    council(repo, "seat", "beck", "running", "agent=a3")
    code, out, _ = council(repo, "collect")
    check("collect: a seat that is running again is a hole, file or not", code == 1 and "state:running" in row(out, "beck"), out)
    code, out, _ = council(repo, "seat", "beck", "done", "tokens=10000")
    check("seat: a re-dispatched worker adds its tokens instead of replacing them", "seats: 3 of 3 done" in out and "~86k tokens so far" in out, out)

@part("timing")
def seat_races(tmp):
    # Token counts as the UI shows them; several workers recorded at the same moment
    tk = new_repo(tmp, "tokens")
    write(os.path.join(tk, ".council", "council.config.md"), "# Council config — tokens\n")
    code, trun, _ = council(tk, "run", "open", "council-review")
    trun = trun.strip()
    write_plan(trun, selected=tuple(f"par{i}" for i in range(6)) + ("afterlock",))
    code_k, _, err_k = council(tk, "seat", "hunt", "done", "agent=a1", "tokens=74.3k")
    council(tk, "seat", "beck", "done", "agent=a2", "tokens=1,200")
    council(tk, "seat", "leach", "done", "agent=a3", "tokens=74,304")
    code, out, err = council(tk, "seat", "dodds", "done", "agent=a4", "tokens=lots")
    tseats = read(os.path.join(trun, "seats.tsv"))
    check("seat: a rounded 74.3k is refused (the notification's exact figure is wanted); 1,200 is 1,200 and 74,304 is 74,304",
          code_k == 2 and "rounded" in err_k and "\nhunt\t" not in tseats
          and "\nbeck\tdone\ta2\t1200\t" in tseats and "\nleach\tdone\ta3\t74304\t" in tseats, err_k + tseats)
    council(tk, "seat", "spaced", "done", "agent=a5", "tokens=74 304")
    tseats = read(os.path.join(trun, "seats.tsv"))
    check("seat: a space between digits is a thousands separator, not the end of the number",
          "\nspaced\tdone\ta5\t74304\t" in tseats, tseats)
    check("seat: a tokens= value with no number in it is refused", code == 2 and "tokens" in err and "\ndodds\t" not in tseats, out + err)
    workers = council_together(tk, *[("seat", f"par{i}", "running", f"agent=p{i}", "--run", trun) for i in range(6)])
    tlines = read(os.path.join(trun, "seats.tsv")).splitlines()
    check("seat: six workers recorded at the same moment all succeed and keep six rows, and the header stays first",
          all(code == 0 for code, _ in workers)
          and tlines[:1] == ["slug\tstate\tagent\ttokens\tupdated\tnote\tagents\treported"] and sum(1 for x in tlines if x.startswith("par")) == 6,
          workers_detail(workers) + "\n" + "\n".join(tlines), full=True)
    os.makedirs(os.path.join(trun, "seats.tsv.lock"), exist_ok=True)   # what a killed seat call leaves behind
    started = time.time()
    code, out, err = council(tk, "seat", "afterlock", "running", "agent=a9", "--run", trun)
    took = time.time() - started
    check("seat: a lock a killed call left behind is broken after about ten seconds, not a minute",
          code == 0 and took < 40 and "\nafterlock\t" in read(os.path.join(trun, "seats.tsv")),
          "%.1f s · %s%s" % (took, out, err))

    # The reminder to show the run's status comes once per run: which record is the run's first dispatch
    # is settled under the seat lock.
    fd = new_repo(tmp, "first-dispatch")
    write(os.path.join(fd, ".council", "council.config.md"), "# Council config — first dispatch\n")
    _, fd_run, _ = council(fd, "run", "open", "council-review")
    fd_run = fd_run.strip()
    write_plan(fd_run, selected=tuple(f"w{i}" for i in range(4)))
    workers = council_together(fd, *[("seat", f"w{i}", "running", f"agent=f{i}", "--run", fd_run) for i in range(4)])
    check("seat: of four workers first recorded at the same moment, exactly one call is told to show the run's status",
          all(code == 0 for code, _ in workers) and sum(err.count("first dispatch of this run") for _, err in workers) == 1,
          workers_detail(workers), full=True)

    # Once-only events: whether one is on record is checked under the events lock, so seat records that
    # pass the cap, the estimate and the ceiling together still record each passing once.
    race = new_repo(tmp, "cap-race")
    write(os.path.join(race, ".council", "council.config.md"), "# Council config — once-only events\n")
    _, race_run, _ = council(race, "run", "open", "council-review")
    race_run = race_run.strip()
    write_plan(race_run, selected=("wf", "r0", "r1", "r2", "late"), verification="self", estimated_tokens=505000)
    append(os.path.join(race_run, "run-plan.tsv"), "budget\trun\ttoken-ceiling\t515000\towner limit\n")
    council(race, "seat", "wf", "done", "agent=wf1", "agents=10", "tokens=500000")   # the whole cap, just under both token limits
    workers = council_together(race, *[("seat", f"r{i}", "done", f"agent=x{i}", "tokens=20000", "--run", race_run) for i in range(3)])
    once = ("run.cap_passed", "run.estimate_passed", "run.ceiling_passed")
    kinds = [e[3] for e in events(race_run)]
    check("seat: three workers that pass the cap, the estimate and the ceiling together record each passing once",
          [kinds.count(k) for k in once] == [1, 1, 1],
          "cap, estimate, ceiling events %s; %s" % ([kinds.count(k) for k in once],
                                                    workers_detail(workers, ("over its cap of 10", "over its ceiling of 515000"))),
          full=True)
    council(race, "seat", "late", "done", "agent=x9", "tokens=20000")
    code, out, err = council(race, "run", "events", "check")
    kinds = [e[3] for e in events(race_run)]
    check("seat: a later record past all three limits adds no second passing event, and the stream stays valid",
          [kinds.count(k) for k in once] == [1, 1, 1] and code == 0,
          "cap, estimate, ceiling events %s; %s%s" % ([kinds.count(k) for k in once], out, err))

@part("timing")
def state_races(tmp):
    """State updates at the same moment: session-state.md is rewritten under a lock, so none is lost. Before,
    six at once all said they had succeeded and one key survived."""
    sr = new_repo(tmp, "state-race")
    write(os.path.join(sr, ".council", "council.config.md"), "# Council config — state races\n")
    _, srun, _ = council(sr, "run", "open", "council-review")
    srun = srun.strip()
    workers = []
    for rnd in range(3):
        workers += council_together(sr, *[("state", f"k{rnd}{i}=v", "--run", srun) for i in range(6)])
    st = read(os.path.join(srun, "session-state.md"))
    kept = [f"k{rnd}{i}" for rnd in range(3) for i in range(6) if f"\nk{rnd}{i}: v\n" in st]
    check("state: eighteen updates made six at a time all succeed and all eighteen keys are kept",
          all(code == 0 for code, _ in workers) and len(kept) == 18,
          workers_detail(workers) + "\nkept %d: %s" % (len(kept), " ".join(kept)), full=True)
    lost = []
    for rnd, phase in enumerate(("prepare", "convene", "prepare", "convene")):
        pair = council_together(sr, ("state", f"phase={phase}", "--run", srun), ("state", f"next=step {rnd}", "--run", srun))
        st = read(os.path.join(srun, "session-state.md"))
        if any(code != 0 for code, _ in pair) or f"\nphase: {phase}\n" not in st or f"\nnext: step {rnd}\n" not in st:
            lost.append("round %d: %s · %s" % (rnd, workers_detail(pair), st.split("## ")[0].replace("\n", " | ")))
    last_phase = [e[5] for e in events(srun) if e[3] == "run.phase_changed"][-1:]
    code, out, err = council(sr, "run", "events", "check", "--run", srun)
    check("state: a stage change made together with another update keeps both, and the last stage event matches the file",
          not lost and last_phase == ["convene"] and code == 0, "\n".join(lost) + " · last phase event %s · %s%s" % (last_phase, out, err),
          full=True)

@part("collect")
def agent_stop(tmp):
    # The agent stop: council cap says where a run stands, cap allow records the user's go in their words,
    # cap check is the agent gate's decision (hooks/agent-gate.sh) — exit 2 and the reason while stopped.
    stop = new_repo(tmp, "agent-stop")
    write(os.path.join(stop, ".council", "council.config.md"), "# Council config — the agent stop\n- agent cap: 2\n")
    code, out, err = council(stop, "cap", "check", "--session", "s1")
    check("cap check: a council with no run — exit 0, nothing printed", code == 0 and not out and not err, out + err)
    _, stop_run, _ = council(stop, "run", "open", "council-review", env={"CLAUDE_CODE_SESSION_ID": "s1"})
    stop_run = stop_run.strip()
    council(stop, "seat", "w1", "done", "agent=a1", "tokens=30000")
    code, out, err = council(stop, "cap", "check", "--session", "s1")
    check("cap check: a run under its cap — exit 0, nothing printed", code == 0 and not out and not err, out + err)
    council(stop, "seat", "w2", "done", "agent=a2", "tokens=30000")
    code, out, err = council(stop, "cap")
    check("cap: the agent runs used against the cap, and that new agents are stopped now",
          code == 0 and "2 of 2 agent runs used" in out and "new agents: stopped" in out, out + err)
    code, out, err = council(stop, "cap", "check", "--session", "s1")
    check("cap check: at the cap — exit 2, the reason on stdout, naming council cap allow",
          code == 2 and out.startswith("Small Council:") and "2 of its 2 agent runs" in out and "council cap allow" in out,
          out + err)
    code, out, err = council(stop, "cap", "check", "--session", "someone-else")
    check("cap check: a run another session drives is not this session's to stop — exit 0", code == 0 and not out, out + err)
    for args, want in ((("cap", "allow", "2"), "needs --user-said"),
                       (("cap", "allow", "2", "--user-said", "   "), "needs --user-said"),
                       (("cap", "allow", "two", "--user-said", "yes"), "a whole number from 1 to 1000"),
                       (("cap", "allow", "0", "--user-said", "yes"), "a whole number from 1 to 1000"),
                       (("cap", "allow", "1001", "--user-said", "yes"), "a whole number from 1 to 1000")):
        code, out, err = council(stop, *args)
        check(f"cap allow: refuses {' '.join(repr(a) for a in args[2:])}", code == 2 and want in err, out + err)
    code, out, err = council(stop, "cap", "allow", "3", "--user-said", "yes\tgo on, three more")
    rows = read(os.path.join(stop_run, "cap-allowances.tsv")).splitlines()
    cells = rows[1].split("\t") if len(rows) == 2 else []
    check("cap allow: records one row (the refused ones none) — used, n, until, and the user's words on one line",
          code == 0 and rows[:1] == ["at\tused\tn\tuntil\tsaid"] and cells[1:] == ["2", "3", "5", "yes go on, three more"],
          "\n".join(rows) + out + err)
    check("cap allow: says how many more agent runs may start, and up to what count",
          "3 more agent run(s) may start, up to 5" in out, out)
    allowed = [e for e in events(stop_run) if e[3] == "run.cap_allowed"]
    check("cap allow: records a run.cap_allowed event", len(allowed) == 1 and allowed[0][4:] == ["run", "3", "used=2;until=5"],
          allowed)
    code, out, err = council(stop, "cap", "check", "--session", "s1")
    check("cap check: after the go — exit 0", code == 0 and not out, out + err)
    code, out, err = council(stop, "cap")
    check("cap: shows the go and how many more agent runs it covers",
          "the user's go allows up to 5" in out and "3 more under the user's go" in out, out + err)
    code, out, err = council(stop, "seat", "w3", "done", "agent=a3", "tokens=30000")
    check("seat: past the cap under the user's go, the note says the go covers it, not to ask again",
          "the user's go covers up to 5" in err and "ask before starting more" not in err, err)
    code, out, err = council(stop, "run", "events", "check")
    check("cap allow: the event stream holding run.cap_allowed stays valid", code == 0 and len(allowed) == 1, out + err)
    # The user's go past the cap lets the plan hold the agent runs it allowed: a real build jammed here, its
    # extra verifier refused by the plan check, and the run unable to move on.
    grow = new_repo(tmp, "agent-stop-plan-go")
    write(os.path.join(grow, ".council", "council.config.md"), "# Council config — plan under a go\n- agent cap: 3\n")
    _, grow_run, _ = council(grow, "run", "open", "council-review")
    grow_run = grow_run.strip()
    grow_plan = os.path.join(grow_run, "run-plan.tsv")
    write_plan(grow_run, selected=("w1", "w2"))                                  # w1, w2 and verify-plan: 3 agent runs
    three = read(grow_plan).replace("budget\trun\tagent-cap\t10", "budget\trun\tagent-cap\t3")
    extra = "".join(f"{k}\tverify-2\t{f}\t{v}\tthe extra check\n" for k, f, v in
                    (("seat", "disposition", "selected"), ("seat", "role", "verifier"), ("context", "level", "focused"),
                     ("budget", "tool-calls", "15")))
    write(grow_plan, three)
    write(os.path.join(grow_run, "verify-plan.md"), "# Verification — plan\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
          "| 1 | a | CONFIRMED | a.py:1 |\n")                       # a verifier is done only with its file
    for slug in ("w1", "w2", "verify-plan"):
        council(grow, "seat", slug, "done", f"agent=g-{slug}", "tokens=20000")
    write(grow_plan, three + extra)
    code, out, _ = council(grow, "run", "plan", "check")
    check("run plan check: with no go on record, a fourth agent run past the cap of 3 is refused",
          code == 1 and "4 planned agent runs exceed the plan cap 3 (" in out, out)
    council(grow, "cap", "allow", "2", "--user-said", "yes, two more checks")
    code, out, _ = council(grow, "run", "plan", "check")
    check("run plan check: after the user's go for two more, the extra seat's plan rows pass, and the go is named",
          code == 0 and "4 agent run(s) of cap 3 — past the cap under the user's go, up to 5" in out, out)
    code, out, err = council(grow, "seat", "verify-2", "running", "agent=g-v2")
    code2, out2, err2 = council(grow, "state", "phase=deliver")
    check("seat and state: under the go, the extra seat starts and the run moves on", code == 0 and code2 == 0,
          out + err + out2 + err2)
    write(grow_plan, three.replace("budget\trun\tagent-cap\t3", "budget\trun\tagent-cap\t5") + extra)
    code, out, _ = council(grow, "run", "plan", "check")
    check("run plan check: a plan cap raised to the user's go (5) passes", code == 0, out)
    write(grow_plan, three.replace("budget\trun\tagent-cap\t3", "budget\trun\tagent-cap\t6") + extra)
    code, out, _ = council(grow, "run", "plan", "check")
    check("run plan check: a plan cap past the go is refused, naming the configured cap and the go",
          code == 1 and "agent-cap 6 exceeds the configured cap 3 or the user's go up to 5 agent runs" in out, out)
    write(grow_plan, three + extra + extra.replace("verify-2", "verify-3") + extra.replace("verify-2", "verify-4"))
    code, out, _ = council(grow, "run", "plan", "check")
    check("run plan check: planned agent runs past the go are refused, naming the go",
          code == 1 and "6 planned agent runs exceed the plan cap 3 or the user's go up to 5" in out, out)
    old_stop = os.path.join(stop, ".council", "runs", "2026-09-01-100000-review")   # from before event streams and run plans
    write(os.path.join(old_stop, "session-state.md"), "status: in-progress\nmode: council-review\nphase: work\n")
    write(os.path.join(old_stop, "seats.tsv"), "slug\tstate\tagent\ttokens\tupdated\tnote\nhunt\tdone\ta1\t50000\t10:05\t\n"
                                               "beck\tdone\ta2\t50000\t10:07\t\n")
    code, out, err = council(stop, "cap", "check", "--session", "s1")
    check("cap check: an older run opened before plans and agent limits, past its cap on this tree, never stops an agent",
          code == 0 and not out, out + err)
    code, out, err = council(stop, "cap", "--run", "2026-09-01-100000-review")
    check("cap: an older run past its cap says so, and that the stop does not hold for it",
          "2 of 2 agent runs used" in out and "not stopped" in out and "opened before plans and agent limits" in out, out + err)
    old_seats = os.path.join(old_stop, "seats.tsv")
    code, out, err = council(stop, "seat", "gamma", "done", "agents=1", "--run", "2026-09-01-100000-review")
    check("seat: past the cap, an older run's note warns — new agents are not stopped, tell the user",
          "more than the cap of 2" in err and "not stopped" in err and "refused" not in err, err)
    write(old_seats, "slug\tstate\tagent\ttokens\tupdated\tnote\nhunt\tdone\ta1\t50000\t10:05\t\nbeck\tdone\ta2\t50000\t10:07\t\n")
    os.remove(os.path.join(old_stop, "usage.tsv"))                                  # back to the two older rows
    code, out, err = council(stop, "cap", "allow", "1", "--run", "2026-09-01-100000-review", "--user-said", "fine, one more")
    rows = read(os.path.join(old_stop, "cap-allowances.tsv")).splitlines()
    check("cap allow: works on an older run with no events.tsv or run-plan.tsv, and adds no event file",
          code == 0 and len(rows) == 2 and rows[1].split("\t")[1:] == ["2", "1", "3", "fine, one more"]
          and not os.path.exists(os.path.join(old_stop, "events.tsv")), "\n".join(rows) + out + err)
    code, out, err = council(stop, "cap", "check", "--session", "s1")
    check("cap check: with both runs covered — exit 0", code == 0 and not out, out + err)
    # A usage report repeated with no agent id (to add a note, say) is the same agent run, not a second one:
    # counted twice, it inflated the agent count the stop reads, the cost line and the ledger.
    rep = new_repo(tmp, "agent-stop-repeat")
    write(os.path.join(rep, ".council", "council.config.md"), "# Council config — repeated report\n- agent cap: 2\n")
    _, rep_run, _ = council(rep, "run", "open", "council-review")
    rep_run = rep_run.strip()
    council(rep, "seat", "beck", "done", "tokens=80000")
    code, out, err = council(rep, "seat", "beck", "done", "tokens=80000", "note=fixed the note")
    beck = next((line.split("\t") for line in read(os.path.join(rep_run, "seats.tsv")).splitlines() if line.startswith("beck\t")), [])
    check("seat: the same report repeated with no agent id counts once, says so, and still takes the note",
          code == 0 and "~80k tokens so far" in out and "not counted again" in err
          and beck[3:4] == ["80000"] and beck[5:8] == ["fixed the note", "1", "1"], out + err + str(beck))
    code, out, err = council(rep, "cap")
    check("cap: a repeated report does not bring the run to its cap", "1 of 2 agent runs used" in out, out + err)
    code, out, err = council(rep, "seat", "beck", "done", "tokens=60000")
    check("seat: a different figure with no agent id is another agent run, and adds", "~140k tokens so far" in out
          and "not counted again" not in err, out + err)
    absurd = new_repo(tmp, "agent-stop-absurd")        # a cap bash can't compare: the gate never fails closed
    write(os.path.join(absurd, ".council", "council.config.md"), "# Council config\n")
    _, absurd_run, _ = council(absurd, "run", "open", "council-review")
    append(os.path.join(absurd_run.strip(), "run-plan.tsv"), "budget\trun\tagent-cap\t99999999999999999999999\tunreadable\n")
    council(absurd, "seat", "w1", "done", "agent=a1", "tokens=5000")
    code, out, err = council(absurd, "cap", "check")
    check("cap check: a cap too large to compare never stops an agent — exit 0", code == 0 and not out, out + err)

@part("runs")
def runs_memory(tmp):
    global ms, ms_conv, rs, rs_cfg, msec, msec_conv, msc   # later "runs" blocks carry on with these
    # Memory: scopes and anchors
    conv_text = ("# Conventions\n## Accepted Patterns (AP) — intentional; never flag these\n"
          "### AP-1: median returns the upper middle on purpose\n**Pattern:** even lists return the upper middle · **Why:** the spec\n"
          "**Scope:** src/stats.py, beck · **Anchor:** src/stats.py:7\n"
          "### AP-2: reports never round\n**Pattern:** raw numbers · **Why:** the users asked\n**Scope:** src/report.py · **Anchor:** summary\n"
          "### AP-3: sessions are re-read on every request\n**Pattern:** no session cache · **Why:** revocation\n**Scope:** **/auth/**, ghost\n"
          "### AP-4: an empty list raises on purpose\n**Pattern:** no empty guard · **Why:** callers check first\n"
          "**Scope:** src/stats.py · **Anchor:** src/stats.py:5, 8–9, summary\n"
          "## Enforced Conventions (EC) — always / never rules\n"
          "### EC-1: every module has a docstring\n**Rule:** always · **Why:** tooling\n"
          "### EC-2: no global caches\n**Rule:** never · **Why:** tests\n**Scope:** src/cache/** · **Anchor:** src/cache/store.py:3\n"
          # README.md has 2 lines, and 3 is a word in tests/test_stats.py: read as a symbol, line 3 would pass
          "### EC-3: the README names the robust statistic\n**Rule:** always · **Why:** users reach for the mean\n"
          "**Scope:** README.md · **Anchor:** README.md:1,3, robust_mean\n"
          "## Proposed — awaiting the user's yes/no\n")
    write(os.path.join(repo, ".council", "conventions.md"), conv_text)
    memonly = new_repo(tmp, "memonly")          # no run open: the paths given are the only keys
    write(os.path.join(memonly, ".council", "council.config.md"), CONFIG)
    write(os.path.join(memonly, ".council", "conventions.md"), conv_text)
    code, out, _ = council(repo, "memory")
    check("memory: prints a one-line index with scopes and anchors",
          "AP-1 · median returns the upper middle on purpose · scope: src/stats.py, beck · anchor: src/stats.py:7" in out
          and "AP-4 · an empty list raises on purpose · scope: src/stats.py · anchor: src/stats.py:5, 8–9, summary" in out
          and "EC-1 · every module has a docstring · every run" in out and sum(" · " in l for l in out.splitlines()) == 7, out)
    code, out, _ = council(memonly, "memory", "select", "src/stats.py")
    check("memory select: a path pulls its scoped entries plus the every-run ones",
          "AP-1" in out and "EC-1" in out and "AP-2" not in out and "EC-2" not in out and "2 scoped and 1 every-run entries of 7" in out, out)
    code, out, _ = council(memonly, "memory", "select", "auth/session.py")
    check("memory select: **/ also matches a path at the repo root", "AP-3" in out, out)
    code, out, _ = council(memonly, "memory", "select", "beck")
    check("memory select: a seat slug pulls its entries", "AP-1" in out and "AP-2" not in out, out)
    code, out, _ = council(memonly, "memory", "select", "src/cache/deep/x.py")
    check("memory select: ** globs reach into subfolders", "EC-2" in out, out)
    code, out, _ = council(repo, "memory", "select")
    check("memory select: defaults to the run's changed files and seats", "AP-1" in out and "AP-2" in out and "EC-2" not in out, out)
    mem8 = new_repo(tmp, "memory-evolution")
    write(os.path.join(mem8, ".council", "council.config.md"), "# c\n")
    # F-1's evidence: an observed failure is served only while the file it cites still shows its verdict.
    write(os.path.join(mem8, ".council", "reviews", "run-12.md"),
          "".join(f"line {n}\n" for n in range(1, 42)) + "| 4 | stale tokens | REFUTED — invalidated first | mw.py:3 |\n")
    write(os.path.join(mem8, ".council", "conventions.md"),
          "# Conventions\n## Accepted Patterns\n### AP-1: old title\n"
          "**Pattern:** read the cache after revocation · **Origin:** review-12, user accepted 2026-09-26\n"
          "**Scope:** src/auth/**\n"
          "## Observed Failures (F)\n### F-1: stale token finding\n"
          "**Failure:** a seat reported stale tokens, but middleware invalidates before lookup\n"
          "**Scope:** src/auth/**\n**Origin:** run-12, 2026-09-26\n"
          "**Evidence:** reviews/run-12.md:42\n**Verdict:** REFUTED\n"
          "### F-2: unsupported failure\n**Failure:** guessed cause\n**Scope:** src/auth/**\n"
          "**Origin:** run-13\n**Verdict:** INFERRED\n"
          "## Proposed\n### F-3: not approved\n**Failure:** a proposal only\n"
          "**Scope:** src/auth/**\n**Origin:** run-14\n**Evidence:** log.md\n**Verdict:** OBSERVED\n")
    code, out, err = council(mem8, "memory", "select", "src/auth/session.py")
    check("memory select: serves the rule itself and its origin, not only the title",
          code == 0 and "AP-1 · old title · scope: src/auth/** · read the cache after revocation" in out
          and "origin: review-12, user accepted 2026-09-26" in out, out + err)
    check("memory select: scoped failure history is labelled as evidence, not a rule",
          "F-1 · stale token finding · observed failure, not a rule" in out
          and "verdict: REFUTED" in out and "evidence: reviews/run-12.md:42" in out
          and "F-2" not in out and "F-3" not in out, out + err)
    code, out, err = council(mem8, "memory", "select", "src/other.py")
    check("memory select: failure history outside the touched scope stays out",
          code == 0 and "F-1" not in out and "AP-1" not in out, out + err)
    code, out, err = council(mem8, "memory")
    check("memory index: incomplete failure provenance is visible but never served",
          code == 0 and "F-2 · unsupported failure · NOT SERVED" in out
          and "F-3 · not approved · not served" in out, out + err)
    # A field hard-wrapped over several lines, as Chrollo's conventions.md had them, is served whole:
    # it runs on until a blank line, the next **Field:** or a heading, as a Markdown paragraph does.
    mwrap = new_repo(tmp, "memwrapped")
    write(os.path.join(mwrap, ".council", "council.config.md"), "# c\n")
    write(os.path.join(mwrap, ".council", "reviews", "run-12.md"), "line 1\n| 4 | stale tokens | REFUTED — invalidated first | mw.py:3 |\n")
    write(os.path.join(mwrap, ".council", "conventions.md"),
          "# Conventions\n## Enforced Conventions (EC)\n### EC-20: A telemetry lane never widens the blast radius\n"
          "**Convention:** Measure-only passengers (refusal telemetry, probes, shadow reads) get their own\n"
          "containment at EVERY layer they ride, and ordering\nthat puts the paying artifact first.\n"
          "**Origin:** Council Review 2026-07-26-2156 (engine/near-miss-lane,\nfindings 2/5/6); operator-delegated 2026-07-26\n"
          "**Principle:** a lane is a passenger,\nnever the driver\n"
          "### EC-21: wrapped scope\n**Rule:** never cache a session · **Why:** revocation must\nbite at once\n"
          "**Scope:** src/auth/**,\nsrc/session/**\n\nA paragraph after a blank line is not part of the rule.\n"
          "### EC-24: a sentence under a scope\n**Rule:** keep tokens short-lived\n**Scope:** src/auth/**\n"
          "A sentence under the scope is not one more path.\n"
          "## Accepted Patterns (AP)\n"
          "- **AP-1 — a bullet entry.** **Pattern:** every deadline is in seconds,\n  never a tick count\n  · **Why:** frame rates vary\n"
          "- **AP-2 — the next bullet.** **Pattern:** one line only\n"
          "## Observed Failures (F)\n### F-1: stale token finding\n"
          "**Observation:** a seat reported stale tokens,\nbut middleware invalidates before lookup\n"
          "**Scope:** src/auth/**\n**Origin:** run-12, 2026-09-26\n**Evidence:** reviews/run-12.md:2\n**Verdict:** REFUTED\n")
    code, out, err = council(mwrap, "memory", "select", "src/session/store.py", "src/auth/login.py")
    check("memory select: a hard-wrapped rule and origin are served whole, not cut at the first line's end",
          code == 0 and "EC-20 · A telemetry lane never widens the blast radius · every run · Measure-only passengers "
          "(refusal telemetry, probes, shadow reads) get their own containment at EVERY layer they ride, and ordering "
          "that puts the paying artifact first. · origin: Council Review 2026-07-26-2156 (engine/near-miss-lane, "
          "findings 2/5/6); operator-delegated 2026-07-26\n" in out, out + err)
    check("memory select: a wrapped scope still matches its second line, and a wrapped bullet rule reads whole",
          "EC-21 · wrapped scope · scope: src/auth/**, src/session/** · never cache a session\n" in out
          and "AP-1 · a bullet entry · every run · every deadline is in seconds, never a tick count\n" in out
          and "AP-2 · the next bullet · every run · one line only\n" in out
          and "2 scoped and 3 every-run entries of 5 apply" in out, out + err)
    check("memory select: the next field, a blank line or a '· **Why:**' ends a wrapped field — nothing else leaks in",
          not any(t in out for t in ["passenger,", "never the driver", "bite at once", "A paragraph after", "frame rates"]), out)
    check("memory select: a scope runs on only while its line ends in a comma — a sentence under it is not a path",
          "EC-24 · a sentence under a scope · scope: src/auth/** · keep tokens short-lived\n" in out and "one more path" not in out, out)
    check("memory select: a wrapped observation reads whole too",
          "F-1 · stale token finding · observed failure, not a rule · scope: src/auth/** · a seat reported stale tokens, "
          "but middleware invalidates before lookup · verdict: REFUTED" in out, out + err)
    code, out, err = council(mwrap, "memory")
    check("memory index: a wrapped origin shows whole",
          code == 0 and "origin: Council Review 2026-07-26-2156 (engine/near-miss-lane, findings 2/5/6); operator-delegated 2026-07-26\n" in out
          and "WARNING" not in out + err, out + err)
    code, out, _ = council(repo, "memory", "check")
    check("memory check: flags the anchors that no longer hold, and only those",
          code == 1 and "STALE  EC-2" in out and "AP-1" not in out and "AP-2" not in out and "3 stale anchor(s) across 7 entries" in out, out)
    check("memory check: an anchor may list lines, as a citation does; with every line there, it isn't stale",
          "AP-4" not in out, out)
    check("memory check: a listed line past the end is bad-line, even where its number is a word in the code",
          "STALE  EC-3 — anchor README.md:1,3: bad-line (the file has 2 lines)" in out, out)
    check("memory check: a name after the listed lines is an anchor of its own",
          "STALE  EC-3 — nothing in the code is named robust_mean any more" in out, out)

    # Memory: the entry shapes real projects write
    ms = new_repo(tmp, "memshapes")
    write(os.path.join(ms, ".council", "council.config.md"), "# c\n")
    ms_conv = os.path.join(ms, ".council", "conventions.md")
    write(ms_conv, "# m\n## Accepted Patterns\n### **AP-3**: bold id\n#### AP-4: four hashes\n### ap-7: lowercase\n### AP8: no dash\n"
          "### AP-2 — em dash title\n- **AP-6 — bullet entry.**\n### AP-5. period\n## AP-9: a level-two entry\n### **AP-10: all in bold**\n")
    code, out, _ = council(ms, "memory")
    check("memory: reads ## to #### headings, bold and lower-case ids, ids without a dash, and bold bullets",
          all(f"{e} · every run" in out for e in ["AP-3 · bold id", "AP-4 · four hashes", "AP-7 · lowercase", "AP-8 · no dash",
              "AP-2 · em dash title", "AP-6 · bullet entry", "AP-5 · period", "AP-9 · a level-two entry", "AP-10 · all in bold"])
          and out.count(" · every run") == 9, out)
    bullets = ("# Conventions — settled decisions\n\nProvenance: review 2026-07-28 (9 seats). Adopted 2026-07-28.\n\n"
               "**Accepted patterns — stop flagging these. They are deliberate.**\n\n"
               "- **AP-1 — `widget.ext` stays whole.** It is not a god object. It reads\n  top-to-bottom. *(Structure, unprompted.)*\n"
               "- **AP-2 — A whole-list scan is the right answer to \"who else is here\"** at\n  this scale. Do not propose an index.\n\n"
               "**Enforced conventions — always/never.**\n\n"
               "- **EC-1 — Never keep a handle across ticks without\n  `is_live`.** Prefer not keeping it. A released handle is\n  *not* null.\n"
               "- **EC-2 — Every deadline in a test is in seconds, never a tick\n  count.** Run suites with `--fixed-rate 60`.\n  **Scope:** tests/**\n\n"
               "---\n\n## Adopted 2026-07-30 — review 2026-07-30-2257\n\nProvenance: 11 seats, 98 raw findings.\n\n"
               "**Accepted patterns — stop flagging these.**\n\n"
               "- **AP-3 — Recast seats are the norm here, not an exception.** A seat whose\n  domain is absent is re-aimed.\n\n"
               "**Enforced conventions — always/never.**\n\n"
               "- **EC-3 — A CHECK THAT CANNOT FAIL PROVES NOTHING, AND ONE BUILT ON A CONSTANT\n"
               "  NEVER FAILS.** The run reported **+0.00 four times**, and **what hid it is\n  that it gave the expected answer**.\n\n"
               "- **EC-4 — EVERY `linked_asset` CARRIES AN `id://`.** Most lines were path-only.\n")
    write(ms_conv, bullets)
    code, out, _ = council(ms, "memory")
    check("memory: a file of bold bullet entries under bold labels and dated sections reads whole",
          all(e in out for e in ["AP-1 · `widget.ext` stays whole · every run",
                                 "AP-2 · A whole-list scan is the right answer to \"who else is here\" · every run",
                                 "EC-1 · Never keep a handle across ticks without `is_live` · every run",
                                 "EC-2 · Every deadline in a test is in seconds, never a tick count · scope: tests/**",
                                 "AP-3 · Recast seats are the norm here, not an exception · every run",
                                 "EC-3 · A CHECK THAT CANNOT FAIL PROVES NOTHING, AND ONE BUILT ON A CONSTANT NEVER FAILS · every run",
                                 "EC-4 · EVERY `linked_asset` CARRIES AN `id://` · every run"]) and "WARNING" not in out, out)
    code, out, _ = council(ms, "memory", "select", "tests/test_x.gd")
    check("memory select: ... and serves it", "1 scoped and 6 every-run entries of 7 apply" in out, out)
    write(ms_conv, "# m\n| Id | Rule |\n|---|---|\n| AP-1 | tables are not entries |\n")
    code, out, _ = council(ms, "memory")
    check("memory: a file that names entry ids but gives no entry says so loudly",
          "no entries yet" in out and "WARNING" in out and "names entry ids, but no entry could be read" in out, out)
    code, out, err = council(ms, "memory", "select", "x.py")
    check("memory select: ... and so does select", "no entry could be read" in err and "entries of 0 apply" in out, out + err)
    write(ms_conv, read(ref(os.path.join("templates", "conventions.md"))))
    code, out, _ = council(ms, "memory")
    check("memory: the blank template has no entries yet, and no warning", "no entries yet" in out and "WARNING" not in out, out)

    root_shape = ("# Project Conventions\n\nAccepted patterns and enforced conventions from council reviews. The council reads this file\n"
                  "before every review.\n\n---\n\n## Accepted Patterns\n\nThese are intentional — do not flag as findings.\n\n"
                  "### AP-1: `main_list` key vs `main_items` type split\n**Pattern:** The default key is `main_list`; its stored type is\n"
                  "`main_items`. Do NOT propose migrating.\n**Origin:** Review 2026-06-30\n**Rationale:** A live migration for cosmetic gain.\n\n"
                  "### AP-2: `load_rows` cold/incremental/repair state machine\n**Pattern:** a sequence of named helpers.\n**Origin:** Review 2026-06-30\n\n"
                  "---\n\n## Enforced Conventions\n\n### EC-1: One source for the default scope\n**Convention:** every caller reads one place.\n\n"
                  "### EC-2: Fold twin code paths, never copy\n**Convention:** one path.\n\n---\n\n"
                  "### AP-3: The two reads use DIFFERENT sources — by design\n**Pattern:** they may disagree.\n\n"
                  "### EC-3: `/status` degrades, never 500s\n**Convention:** an empty answer, not an error.\n")
    rs = new_repo(tmp, "rootmem")
    rs_cfg = os.path.join(rs, ".council", "council.config.md")
    write(rs_cfg, "# c\n## Stack\n- conventions: PEP 8 + ruff\n## Memory\n- conventions: .council/conventions.md\n")
    with open(os.path.join(rs, "conventions.md"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(root_shape)
    code, out, err = council(rs, "memory", "select", "core/pipeline/downloads.py")
    check("memory: a CRLF file at the repo root reads whole when the config names a memory file that doesn't exist — and says so",
          code == 0 and "0 scoped and 6 every-run entries of 6 apply" in out and "AP-3 · The two reads use DIFFERENT sources — by design · every run" in out
          and "doesn't exist — reading" in err and "PEP" not in out + err, out + err)
    write(rs_cfg, "# c\n## Memory\n- conventions: /conventions.md\n")
    code, out, err = council(rs, "memory")
    check("memory: a configured /conventions.md is the repo's root one", code == 0 and "EC-3 · `/status` degrades, never 500s" in out and not err.strip(), out + err)

    # Memory: only settled entries are served
    msec = new_repo(tmp, "memsections")
    write(os.path.join(msec, ".council", "council.config.md"), "# c\n")
    msec_conv = ("# m\n## Accepted Patterns (AP)\n### AP-1: live one\n**Scope:** webapp/**\n"
          "### AP-2: retired by a line\n**Pattern:** x · **Retired:** 2026-09-01 — superseded by AP-1\n**Scope:** webapp/**\n"
          "### ~~AP-3~~: struck out\n"
          "## Proposed — awaiting the user's yes/no\n### AP-9: proposed as a heading\n**Scope:** webapp/**\n"
          "- PROPOSED accepted pattern: stop flagging X — deliberate (evidence: a.py:1)\n"
          "## Rejected — never propose again\n### AP-10: the user said NO\n"
          "## Retired\n### EC-15: superseded\n"
          "## Backend notes\n### EC-20: under a section nobody named\n")
    write(os.path.join(msec, ".council", "conventions.md"), msec_conv)
    code, out, err = council(msec, "memory", "select", "webapp/frontend/src/App.jsx")
    check("memory select: serves only settled entries — never proposed, rejected or retired ones",
          code == 0 and "AP-1 · live one" in out and not any(i in out for i in ["AP-2", "AP-3", "AP-9", "AP-10", "EC-15", "EC-20"])
          and "1 scoped and 0 every-run entries of 1 apply" in out and "(5 retired or not yet accepted, left out)" in out, out)
    check("memory select: an entry under a section it can't place is left out, loudly", "EC-20" in err and "WARNING" in err, err)
    code, out, _ = council(msec, "memory")
    check("memory: lists what it doesn't serve, and why",
          "AP-2 · retired by a line · not served (marked retired)" in out and "AP-3 · struck out · not served (marked retired)" in out
          and "AP-9 · proposed as a heading · not served (under ## Proposed" in out and "EC-15 · superseded · not served (under ## Retired)" in out
          and "EC-20 · under a section nobody named · NOT SERVED" in out and "WARNING — 1 entry never reaches a brief" in out, out)

    # Memory: scope spellings, folder boundaries, and speed
    msc = new_repo(tmp, "memscopes")
    write(os.path.join(msc, ".council", "council.config.md"), "# c\n")
    write(os.path.join(msc, "webapp", "frontend", "src", "App.jsx"), "x\n")
    scopes = [("brace", "webapp/frontend/src/*.{js,jsx}"), ("all", "all"), ("dot", "./webapp/frontend/"), ("star", "*"),
              ("leading slash", "/webapp/**"), ("backslashes", "webapp\\frontend\\**"), ("semicolons", "docs/**; webapp/**"),
              ("brackets", "app/(group)/[id]/**"), ("none", "none"), ("elsewhere", "server/**, {api,worker}/**"),
              ("brace folders", "{webapp,mobile}/frontend/**"), ("a folder", "src/api"), ("a typo", "webapp/fronted/**")]
    write(os.path.join(msc, ".council", "conventions.md"), "# m\n## Enforced Conventions\n" +
          "".join(f"### EC-{i}: {t}\n**Scope:** {sc}\n" for i, (t, sc) in enumerate(scopes, 1)))
    code, out, _ = council(msc, "memory", "select", "webapp/frontend/src/App.jsx", "app/(group)/[id]/page.tsx", "src/api_v2/client.py")
    picked = sorted(int(m) for m in re.findall(r"^EC-(\d+) ", out, re.MULTILINE))
    check("memory select: brace globs, all, ./, a leading /, backslashes, semicolons and literal brackets all match",
          picked == [1, 2, 3, 4, 5, 6, 7, 8, 9, 11] and "7 scoped and 3 every-run entries of 13 apply" in out
          and "EC-2 · all · every run" in out and "EC-9 · none · every run" in out, out)
    check("memory select: a folder scope never reaches a sibling that shares its prefix (src/api, src/api_v2)", "EC-12" not in out, out)
    code, out, _ = council(msc, "memory", "select", "src/api/client.py")
    check("memory select: ... and does reach inside the folder", "EC-12 · a folder" in out, out)
    code, out, _ = council(msc, "memory")
    check("memory: flags a scope item that matches no file, seat or mode",
          '"webapp/fronted/**" (EC-13) matches no file, seat or mode' in out and not any(f"({e})" in out for e in ["EC-1", "EC-3", "EC-5", "EC-6"]), out)

@part("timing")
def memory_speed(tmp):
    # Scopes and keys as projects really write them: a folder with a blank in its name, a Godot
    # res:// path, the absolute path Git Bash prints, and "." for the whole tree.
    msp = new_repo(tmp, "memspaced")
    write(os.path.join(msp, ".council", "council.config.md"), "# c\n")
    write(os.path.join(msp, "docs", "My Notes", "a.md"), "x\n")
    write(os.path.join(msp, "scripts", "fighter.gd"), "x\n")
    write(os.path.join(msp, "scripts", "ai", "role_def.gd"), "x\n")
    write(os.path.join(msp, "webapp", "backend", "main.py"), "x\n")
    git(msp, "add", "-A")
    git(msp, "commit", "-q", "-m", "i")
    write(os.path.join(msp, ".council", "conventions.md"), "# m\n## Enforced Conventions\n"
          "### EC-1: a folder with a blank in its name\n**Scope:** docs/My Notes/**\n"
          "### EC-2: a res:// path\n**Scope:** res://scripts/fighter.gd\n"
          "### EC-3: a res:// glob\n**Scope:** `res://scripts/ai/**`\n"
          "### EC-4: two globs, blank-separated\n**Scope:** webapp/backend/** docs/**\n")
    code, out, _ = council(msp, "memory", "select", os.path.join("docs", "My Notes", "a.md"))
    check("memory select: a scope path with a blank in it still matches", "EC-1 ·" in out, out)
    code, out, _ = council(msp, "memory", "select", "scripts/fighter.gd", "scripts/ai/role_def.gd")
    check("memory select: a Godot res:// scope matches the file it names", "EC-2 ·" in out and "EC-3 ·" in out, out)
    code, out, _ = council(msp, "memory")
    check("memory: and none of those is called a spelling mistake", "matches no" not in out, out)
    write(os.path.join(msp, ".council", "reviews", "2026-09-01-r.md"), "---\nareas: res://scripts/ai/**\n---\n# r\n")
    code, out, _ = council(msp, "prior", "scripts/ai/role_def.gd")
    check("prior: a res:// area matches the file it names", "2026-09-01-r.md" in out, out)
    code, out, _ = council(msp, "memory", "select", ".")
    check("memory select: '.' is the whole tree — every scoped entry applies", "4 scoped" in out, out)
    if re.match(r"^[A-Za-z]:", slash(msp)):                  # Windows: the absolute form Git Bash prints
        unix = "/" + slash(msp)[0].lower() + slash(msp)[2:]
        code, out, _ = council(msp, "memory", "select", unix + "/webapp/backend/main.py")
        check("memory select: a /c/… absolute key is the same file as C:/…", "EC-4 ·" in out, out)
    mpf = new_repo(tmp, "memperf")
    write(os.path.join(mpf, ".council", "council.config.md"), "# c\n")
    pscopes = ["core/structure/**, mckinney", "webapp/backend/**/*.py, leach", "**/tests/**, beck"]
    write(os.path.join(mpf, ".council", "conventions.md"), "# m\n## Enforced Conventions\n" +
          "".join(f"### EC-{i}: rule {i}\n**Rule:** always · **Why:** x\n**Scope:** {pscopes[i % 3]}\n" for i in range(1, 71)))
    pkeys = [f"webapp/frontend/src/components/Panel{i}.jsx" for i in range(117)] + ["fowler", "hunt", "council-review"]
    t0 = time.time()
    try:
        code, out, _ = council(mpf, "memory", "select", *pkeys)
    except subprocess.TimeoutExpired:
        code, out = -1, "timed out after 120 s"
    took = time.time() - t0
    check("memory select: 70 scoped entries against 120 paths and slugs take seconds, not minutes",
          code == 0 and "0 scoped and 0 every-run entries of 70 apply" in out and took < 10, f"{took:.1f} s: {out}")

    # Memory: anchors as models write them, and a project without git
    man = new_repo(tmp, "anchors")
    write(os.path.join(man, ".council", "council.config.md"), "# c\n")
    write(os.path.join(man, "core", "x.py"), "class Universe:\n    def registry(self):\n        pass\n\ndef fetch_data(t, s):\n    return None\n")
    git(man, "add", "-A")
    git(man, "commit", "-q", "-m", "i")
    write(os.path.join(man, "core", "new.py"), "def new_helper():\n    pass\n")      # never committed
    live = ["Universe.registry", "fetch_data()", "core/x.py::fetch_data", "fetch_data in x.py", "x.py; fetch_data",
            "x.py:5 (fetch_data)", "x.py.", "[x.py](core/x.py)", "core/x.py#L5", "none", "n/a", "new_helper",
            "res://core/x.py", "Universe::registry", "core\\x.py"]
    write(os.path.join(man, ".council", "conventions.md"), "# m\n## Accepted Patterns\n" +
          "".join(f"### AP-{i}: live {i}\n**Anchor:** {a}\n" for i, a in enumerate(live, 1)) +
          "## Enforced Conventions\n### EC-1: gone\n**Anchor:** gone_helper()\n"
          "### EC-2: gone from its file\n**Anchor:** core/x.py::gone_helper\n### EC-3: past the end\n**Anchor:** x.py:99\n")
    code, out, _ = council(man, "memory", "check")
    check("memory check: anchors written as a.b, f(), path::name, name in path, short paths, links, #L5 or none hold while the code does",
          code == 1 and "AP-" not in out and "3 stale anchor(s) across 18 entries" in out, out)
    check("memory check: ... and the ones that moved are still caught",
          "STALE  EC-1 — nothing in the code is named gone_helper any more" in out
          and "STALE  EC-2 — nothing in core/x.py is named gone_helper any more" in out
          and "STALE  EC-3 — anchor x.py:99: bad-line (the file has 6 lines)" in out, out)
    nogit = os.path.join(tmp, "nogit")
    shutil.copytree(os.path.join(man, "core"), os.path.join(nogit, "core"))
    write(os.path.join(nogit, ".council", "council.config.md"), "# c\n")
    write(os.path.join(nogit, ".council", "conventions.md"),
          "# m\n## EC\n### EC-1: live\n**Anchor:** fetch_data\n### EC-2: gone\n**Anchor:** gone_helper\n")
    code, out, _ = council(nogit, "memory", "check")
    check("memory check: outside git, a name that is in the code is not stale", code == 1 and "EC-1" not in out
          and "STALE  EC-2" in out and "1 stale anchor(s) across 2 entries" in out, out)

    # Anchor forms real projects write. A dotted name that ends in something that looks like a file
    # extension (process.env), a method inside a file (path::Class.method), a pytest id, and a path
    # and a symbol joined by an arrow, a colon or a blank: each is checked, none is called gone.
    man2 = new_repo(tmp, "anchors2")
    write(os.path.join(man2, ".council", "council.config.md"), "# c\n")
    write(os.path.join(man2, "core", "x.py"), "class Universe:\n    def registry(self):\n        pass\n\ndef fetch_data(t, s):\n    return None\n")
    write(os.path.join(man2, "web", "src", "client.js"), "const url = import.meta.env.VITE_API;\nconst key = process.env.API_KEY;\n")
    write(os.path.join(man2, "api", "routes.py"), "from flask import request\ndef create():\n    body = request.json\n    return body\n")
    write(os.path.join(man2, "tests", "test_x.py"), "class TestFoo:\n    def test_bar(self):\n        pass\n")
    write(os.path.join(man2, "scripts", "fighter.gd"), "func _teardown_move():\n\tpass\n")
    git(man2, "add", "-A")
    git(man2, "commit", "-q", "-m", "i")
    live2 = ["core/x.py::Universe.registry", "tests/test_x.py::TestFoo::test_bar", "`Universe.registry()` in `core/x.py`",
             "`core/x.py` — `fetch_data`", "core/x.py → fetch_data", "core/x.py `fetch_data`",
             "scripts/fighter.gd:_teardown_move", "import.meta.env", "process.env", "request.json"]
    write(os.path.join(man2, ".council", "conventions.md"), "# m\n## Accepted Patterns\n" +
          "".join(f"### AP-{i}: live {i}\n**Anchor:** {a}\n" for i, a in enumerate(live2, 1)) +
          "## Enforced Conventions\n### EC-1: a method that is gone\n**Anchor:** core/x.py::Universe.vanished\n"
          "### EC-2: a dotted name that is gone\n**Anchor:** request.vanished\n")
    code, out, _ = council(man2, "memory", "check")
    check("memory check: path::Class.method, pytest ids, process.env and path → symbol hold while the code does",
          code == 1 and "AP-" not in out and "2 stale anchor(s) across 12 entries" in out, out)
    check("memory check: ... and the ones that really went are still named once each",
          "STALE  EC-1 — nothing in core/x.py is named Universe.vanished any more" in out
          and "STALE  EC-2 — nothing in the code is named request.vanished any more" in out, out)
    # Speed: one search for every name, not one per anchor — a real project's memory, with anchors on
    # every entry used to take minutes, past the 2-minute limit a tool call has.
    apf = new_repo(tmp, "anchorperf")
    write(os.path.join(apf, ".council", "council.config.md"), "# c\n")
    for d in range(1, 11):
        for f in range(1, 21):
            write(os.path.join(apf, "webapp", f"mod{d}", f"f{f}.py"),
                  f"class Thing{d}_{f}:\n    def run_{f}(self):\n        return {f}\n")
    git(apf, "add", "-A")
    git(apf, "commit", "-q", "-m", "i")
    write(os.path.join(apf, ".council", "conventions.md"), "# m\n## Enforced Conventions\n" + "".join(
        f"### EC-{i}: rule {i}\n**Anchor:** webapp/mod{(i % 10) + 1}/f1.py:2, Thing{(i % 10) + 1}_1.run_1, "
        f"services/f{(i % 10) + 1}.py::run_1\n" for i in range(1, 70)))
    t0 = time.time()
    try:
        code, out, _ = council(apf, "memory", "check")
    except subprocess.TimeoutExpired:
        code, out = -1, "timed out after 120 s"
    took = time.time() - t0
    check("memory check: a memory with an anchor on every entry is checked in seconds, not minutes",
          code == 1 and "69 stale anchor(s) across 69 entries" in out and took < 60, f"{took:.1f} s: {out}")

@part("runs")
def runs_citation_check(tmp):
    # Memory: with a run open, the paths given add to the run's own keys
    msel = new_repo(tmp, "memsel")
    write(os.path.join(msel, ".council", "council.config.md"), CONFIG)
    write(os.path.join(msel, "webapp", "backend", "main.py"), "x = 1\n")
    write(os.path.join(msel, ".council", "conventions.md"),
          "# m\n## Accepted Patterns\n### AP-1: bare except in the router\n**Scope:** webapp/backend/**\n"
          "### AP-2: the frontend polls\n**Scope:** webapp/frontend/**\n"
          "## Enforced Conventions\n### EC-1: plans that touch migrations include a rollback task\n**Scope:** council-plan\n"
          "### EC-2: credentials come from the keyring on purpose\n**Scope:** hunt\n")
    code, selrun, _ = council(msel, "run", "open", "council-plan")
    selrun = selrun.strip()
    write_plan(selrun, selected=("hunt",))
    council(msel, "seat", "hunt", "queued")
    code, out, _ = council(msel, "memory", "select", "webapp/backend")
    check("memory select: with a run open, the paths given add to the run's seats and mode",
          all(i in out for i in ["AP-1", "EC-1", "EC-2"]) and "AP-2" not in out and "3 scoped and 0 every-run entries of 4 apply" in out, out)
    code, selrun2, _ = council(msel, "run", "open", "council-research", "--alongside")
    code, out, err = council(msel, "memory", "select", "webapp/backend/")
    check("memory select: with several runs open, only the paths given count — and it says so",
          code == 0 and "AP-1" in out and "EC-1" not in out and "several runs are open" in err, out + err)
    council(msel, "run", "close", "--run", selrun2.strip(), "--status", "abandoned")
    council(msel, "run", "close", "--run", selrun, "--status", "abandoned")

    # Citation and origin check
    write(os.path.join(run, "synthesis.md"),
          "# Synthesis — eval\n## Kept\n1 · P2 · Principle 3 · src/stats.py:7-9 · median · from: fowler#1\n"
          "2 · P1 · Principle 5 · src/stats.py:1-2 · old lines · from: beck#1\n"
          "3 · P2 · Principle 1 · src/report.py:5 · the uncommitted line · from: x\n"
          "4 · P3 · Principle 2 · `src/stats.py:7–9` · a backticked cite with an en dash · from: z\n"
          "5 · P2 · Principle 3 · src/stats.py:1,7-9 · a list: a base line and branch lines · from: y\n"
          "6 · P3 · Principle 3 · src/stats.py:9, 7-8 · a list out of order, with a blank · from: y\n"
          "## Cut\nC1 · P3 · Principle 1 · src/report.py:99 · past the end · from: gone · why: repeats from: beck\n"
          "C2 · P3 · Principle 1 · src/stats.py:1,10,7-9 · a list with its middle piece past the end · from: y · why: x\n")
    code, out, _ = council(repo, "check")
    check("check: fails on a broken citation", code == 1 and "2 broken citation" in out, out)
    check("check: new lines on the branch are 'introduced'", re.search(r"synthesis#1\s+src/stats\.py:7-9\s+ok · introduced", out) is not None, out)
    check("check: lines from the base are 'pre-existing'", re.search(r"synthesis#2\s+src/stats\.py:1-2\s+ok · pre-existing", out) is not None, out)
    check("check: uncommitted lines are 'introduced'", re.search(r"synthesis#3\s+src/report\.py:5\s+ok · introduced", out) is not None, out)
    check("check: backticks and en-dash ranges resolve", re.search(r"synthesis#4\s+src/stats\.py:7–9\s+ok · introduced", out) is not None, out)
    check("check: a comma list of lines and ranges passes, and every piece is blamed (base + branch = 'touched')",
          re.search(r"synthesis#5\s+src/stats\.py:1,7-9\s+ok · touched", out) is not None, out)
    check("check: a list's pieces may come in any order, with blanks after the commas",
          re.search(r"synthesis#6\s+src/stats\.py:9, 7-8\s+ok · introduced", out) is not None, out)
    check("check: a list with one piece past the end is bad-line",
          re.search(r"synthesis#C2\s+src/stats\.py:1,10,7-9\s+bad-line \(the file has 9 lines\)", out) is not None, out)
    check("check: reads cut items too", re.search(r"synthesis#C1\s+src/report\.py:99\s+bad-line", out) is not None, out)
    check("check: writes check.md", os.path.isfile(os.path.join(run, "check.md")))

@part("citations")
def citation_shapes(tmp):
    # Citation shapes models really write: every place a field names is read and checked, a shape
    # the reader can't parse says so, and nothing it couldn't check is ever counted as fine.
    cites = new_repo(tmp, "cites")
    write(os.path.join(cites, ".council", "council.config.md"), "# Council config\n")
    write(os.path.join(cites, ".council", ".gitignore"), "runs/\n")
    write(os.path.join(cites, "web", "main.py"), "".join(f"code {i}\n" for i in range(1, 701)))
    write(os.path.join(cites, "web", "db.py"), "".join(f"db {i}\n" for i in range(1, 31)))
    write(os.path.join(cites, "sub dir", "my file.py"), "a\nb\nc\n")
    write(os.path.join(cites, "Makefile"), "all:\n\ttrue\n")
    git(cites, "add", "-A")
    git(cites, "commit", "-q", "-m", "base")
    code, crun, _ = council(cites, "run", "open", "council-review")
    crun = crun.strip()
    shapes = [
        ("web/main.py:455/474", "ok"), ("web/main.py:254-268+", "ok"), ("web/main.py:148-150+170", "ok"),
        ("web/main.py:12:5", "ok"), ("web/main.py:L58", "ok"), ("web/main.py#L12", "ok"), ("web/main.py:328,", "ok"),
        ("web/main.py:335-341 (start_run before try)", "ok"), ("web/main.py:75, web/db.py:9-10", "ok"),
        ("web/main.py:533, :7", "ok"), ("web/main.py:40 and web/db.py:12", "ok"),
        ("[web/main.py:40](web/main.py#L40)", "ok"), ("**web/main.py:5**", "ok"), ("'web/main.py:5'", "ok"),
        ("web/main.py:5 → web/db.py:2", "ok"), ("web/main.py:5—7", "ok"), ("web/main.py:5..7", "ok"),
        ("web/main.py:5;25", "ok"), ("web/main.py:5.", "ok"), ("web/main.py: 2", "ok"), ("Makefile:2", "ok"),
        ("sub dir/my file.py:3", "ok"), ("web/main.py:5 (see web/db.py)", "ok"),
        ("`git grep -n TIMEOUT web/` → web/main.py:12: TIMEOUT = 30", "ok"),
        ("web/main.py:0", "bad-line (there is no line 0)"),
        ("web/main.py:20-10", "bad-line (20-10 runs backwards)"),
        ("web/main.py:40, web/db.py:99", "bad-line (web/db.py:99 — the file has 30 lines)"),
        ("web/main.py:12, web/ghost.py:3", "missing-file (web/ghost.py)"),
        ("web/main.py:5x", "unreadable (web/main.py:5x — write it as path:line)"),
        ("web/scaner.py", "missing-file"), ("web/ghost/", "missing-file"), ("web/missing.py:handle", "missing-file"),
        ("web/main.py::run_scan", "no-line (the path exists)"), ("web/", "no-line (the path exists)"),
        ("`curl -s localhost:8000/health` → 200", "n/a (command)"),
        ("https://example.com/docs/page.html#L5", "n/a (link)"),
        ("web/main.py:10 and 9999", "bad-line (the file has 700 lines)"),
        ("web/main.py:10, line 9999", "bad-line (the file has 700 lines)"),
        ("web/db.py:5 & 9999", "bad-line (the file has 30 lines)"),
        ("web/main.py:10 and 20", "ok"), ("web/main.py:10 or 12", "ok"), ("web/main.py: line 10", "ok"),
        ("web/main.py lines 10-12", "ok"), ("web/main.py:  12", "ok"),
        ("web/main.py:5 and 9 other callers", "ok"), ("web/main.py:40 (extract to web/lib/retry.py)", "ok"),
        ("ghost.py lines 10-12", "missing-file"),
        ("the auth layer", "no-citation (a review item needs a path:line)"),
        ("-", "no-citation (a review item needs a path:line)"),
        ("n/a", "no-citation (a review item needs a path:line)"),
    ]
    # The summary's own arithmetic, from the table above: broken, path-but-no-line, and not checked.
    n_broken = sum(1 for _, w in shapes if not w.startswith(("ok", "n/a", "no-line", "deleted"))) + 1
    n_noline = sum(1 for _, w in shapes if w.startswith("no-line"))
    n_unchecked = sum(1 for _, w in shapes if w.startswith("n/a"))
    write(os.path.join(crun, "synthesis.md"), "# Synthesis\n## Kept\n" + "".join(
        f"{i} · P2 · Principle 1 · {c} · shape {i} · from: x#{i}\n" for i, (c, _) in enumerate(shapes, 1))
        + f"{len(shapes) + 1} · P2 · OWASP A01 | Access control · web/db.py:99 · a pipe inside the principle\n")
    code, out, _ = council(cites, "check")
    lines = {l.split("  ", 1)[0]: l for l in out.splitlines()}
    wrong = [(i, c, lines.get(f"synthesis#{i}", "?")) for i, (c, want) in enumerate(shapes, 1)
             if not lines.get(f"synthesis#{i}", "").endswith("  " + want)]
    check("check: every citation shape models write gets the right verdict, never a false missing-file or bad-line",
          not wrong, "\n".join(f"{i} {c!r} -> {l}" for i, c, l in wrong))
    check("check: a pipe inside the principle doesn't shift the fields — the citation is still read",
          lines.get(f"synthesis#{len(shapes) + 1}", "").endswith("web/db.py:99  bad-line (the file has 30 lines)"), out)
    check("check: the summary counts broken, line-less and unchecked citations apart, and fails",
          code == 1 and f"check: {len(shapes) + 1} items, {n_broken} broken citation(s) · {n_noline} name a path but no line"
          f" · {n_unchecked} not checked (a command, a link, an area or no path)" in out, out)
    write(os.path.join(crun, "brief.md"), "# Brief\n## Seats\n### shapes — A\n- ref: none\n### map — B\n- ref: none\n"
          "### res — C\n- ref: none\n")
    write(os.path.join(crun, "seats", "shapes.md"), "# Shapes — x (council-review)\nref: none\n## Index\n"
          + "".join(f"{i} · P2 · Principle 1 · {shapes[i + 6][0]} · t\n" for i in range(1, 6)))
    write(os.path.join(crun, "seats", "map.md"), "# Map — x (council-init)\nref: none\n## Index\n"
          "1 · map · Where things live · web/scaner.py · a typo\n2 · map · Flows · web/main.py::run · a symbol\n"
          "3 · map · Flows · web/main.py: 2 · a blank after the colon\n")
    write(os.path.join(crun, "seats", "res.md"), "# Res — x (council-research)\nref: none\n## Index\n"
          "1 · strong · code · `git grep -n X web/` → web/main.py:12: X = 30 · t\n"
          "2 · moderate · runtime · `curl -s localhost:8000/health` → 200 · t\n")
    code, out, _ = council(cites, "collect")
    check("collect: citations with notes, lists, links and several places resolve",
          re.search(r"^shapes\s+ok\s+5/8\s+\d+\s+n/a\s+5/5\s+-$", out, re.MULTILINE) is not None, out)
    check("collect: a bare path is checked too; one with no line and one it couldn't check are counted, not hidden",
          re.search(r"^map\s+ok\s+3/8\s+\d+\s+n/a\s+2/3\s+- · broken-cites no-line\(1\)$", out, re.MULTILINE) is not None
          and re.search(r"^res\s+ok\s+2/8\s+\d+\s+n/a\s+1/1\s+- · unchecked\(1\)$", out, re.MULTILINE) is not None, out)
    check("collect: when only citations are wrong it says fix them in place, not re-dispatch",
          code == 1 and "collect: only citations are wrong" in out and "re-dispatch" not in out, out)

    # A plan, research or post-game cites "<path or area>": a name that is on disk nowhere is an area,
    # or a file the work would still write — never a broken citation. A review item must name a place.
    areas = new_repo(tmp, "areas")
    write(os.path.join(areas, ".council", "council.config.md"), "# Council config\n")
    write(os.path.join(areas, ".council", ".gitignore"), "runs/\n")
    write(os.path.join(areas, "src", "auth", "session.py"), "".join(f"l{i}\n" for i in range(1, 11)))
    git(areas, "add", "-A")
    git(areas, "commit", "-q", "-m", "base")
    code, arun, _ = council(areas, "run", "open", "council-plan")
    arun = arun.strip()
    write(os.path.join(arun, "brief.md"), "# Brief\n## Seats\n### fowler — Structure\n- ref: none\n")
    write(os.path.join(arun, "seats", "fowler.md"), "# Fowler — Structure (council-plan)\nref: none\n## Index\n"
          "1 · must · P2 · src/auth/tokens.py · a module still to write · t\n"
          "2 · should · P4 · src/auth/session.py:3 · one seam · t\n"
          "3 · could · P1 · n/a · name the flag once · t\n"
          "4 · could · P1 · CI/CD · the pipeline · t\n"
          "5 · could · P1 · tests/test_*.py · a glob · t\n"
          "6 · could · P1 · asyncio.gather · a library call · t\n")
    code, out, _ = council(areas, "collect")
    check("collect: a plan's areas, globs and files still to write are not broken citations",
          code == 0 and "all 1 seats in order" in out and "unchecked(5)" in out, out)
    code, out, _ = council(areas, "check", os.path.join(arun, "seats", "fowler.md"))
    check("check: ... and check says what they are instead of missing-file",
          code == 0 and "nothing on disk by that name" in out and "5 not checked" in out and "missing-file" not in out, out)
    council(areas, "run", "close", "--status", "abandoned")
    nocite = new_repo(tmp, "nocite")
    write(os.path.join(nocite, ".council", "council.config.md"), "# Council config\n")
    write(os.path.join(nocite, ".council", ".gitignore"), "runs/\n")
    write(os.path.join(nocite, "a.py"), "".join(f"l{i}\n" for i in range(1, 10)))
    git(nocite, "add", "-A")
    git(nocite, "commit", "-q", "-m", "base")
    code, nrun, _ = council(nocite, "run", "open", "council-review")
    nrun = nrun.strip()
    write(os.path.join(nrun, "brief.md"), "# Brief\n## Seats\n### hunt — Security\n- ref: none\n")
    write(os.path.join(nrun, "seats", "hunt.md"), "# Hunt — Security (council-review)\nref: none\n## Index\n"
          "1 · P1 · Principle 3 · Login has no rate limit\n2 · P2 · Principle 1 · n/a · Tokens never expire\n")
    code, out, _ = council(nocite, "collect")
    check("collect: a review item with no path:line is a hole in its seat, four fields or not",
          code == 1 and "broken-cites" in row(out, "hunt"), out)
    code, out, _ = council(nocite, "check", os.path.join(nrun, "seats", "hunt.md"))
    check("check: ... and check names it: a review item needs a path:line",
          code == 1 and out.count("no-citation (a review item needs a path:line)") == 2, out)

    # A file the change only renamed: the diff calls every line new, blame knows better
    ren = new_repo(tmp, "renamed")
    write(os.path.join(ren, ".council", "council.config.md"), "# Council config\n")
    write(os.path.join(ren, ".council", ".gitignore"), "runs/\n")
    write(os.path.join(ren, "app", "moved.py"), "".join(f"old line {i}\n" for i in range(1, 41)))
    git(ren, "add", "-A")
    git(ren, "commit", "-q", "-m", "base")
    git(ren, "checkout", "-q", "-b", "feature")
    git(ren, "mv", "app/moved.py", "app/renamed.py")
    git(ren, "commit", "-q", "-m", "move")
    code, rrun, _ = council(ren, "run", "open", "council-review")
    rrun = rrun.strip()
    council(ren, "index")
    write(os.path.join(rrun, "synthesis.md"), "# Synthesis\n## Kept\n"
          "1 · P2 · Naming · app/renamed.py:10 · an old bug in a file the change only moved · from: hunt#1\n")
    code, out, _ = council(ren, "check")
    check("check: in a file the change only renamed, an untouched line stays 'pre-existing'",
          code == 0 and "app/renamed.py:10  ok · pre-existing" in out, out)
    if re.match(r"^[A-Za-z]:", slash(ren)):          # Windows: /c/… and a lower-case drive name one file
        unix = "/" + slash(ren)[0].lower() + slash(ren)[2:]
        write(os.path.join(rrun, "synthesis.md"), "# Synthesis\n## Kept\n"
              f"1 · P2 · Naming · {unix}/app/renamed.py:10 · the path as Git Bash prints it · from: hunt#1\n"
              f"2 · P2 · Naming · {slash(ren).lower()}/app/renamed.py:10 · a lower-case drive · from: hunt#2\n")
        code, out, _ = council(ren, "check")
        check("check: a citation written /c/… or with a lower-case drive keeps its origin",
              code == 0 and out.count("ok · pre-existing") == 2 and "origin unknown" not in out, out)

    # Code the change deleted or moved: a finding about it belongs to the change, never to the past
    moved = new_repo(tmp, "moved")
    write(os.path.join(moved, ".council", "council.config.md"), "# Council config\n")
    write(os.path.join(moved, ".council", ".gitignore"), "runs/\n")
    write(os.path.join(moved, "app", "api.py"), "def delete_account(user, target):\n    \"\"\"Delete an account.\"\"\"\n"
          "    if not user.is_admin:\n        raise PermissionError(\"admins only\")\n    target.delete()\n")
    write(os.path.join(moved, "app", "guard.py"), "def check(token):\n    return token == EXPECTED\n")
    write(os.path.join(moved, "app", "bank.py"), "lock.acquire()\ncheck_balance()\nledger.debit()\nlock.release()\n")
    write(os.path.join(moved, "app", "old.py"), "a = 1\nb = 2\nc = 3\n")
    git(moved, "add", "-A")
    git(moved, "commit", "-q", "-m", "base")
    git(moved, "checkout", "-q", "-b", "feature")
    write(os.path.join(moved, "app", "api.py"), "def delete_account(user, target):\n    \"\"\"Delete an account.\"\"\"\n"
          "    target.delete()\n")
    write(os.path.join(moved, "app", "bank.py"), "lock.acquire()\nledger.debit()\ncheck_balance()\nlock.release()\n")
    git(moved, "rm", "-q", "app/guard.py")
    git(moved, "commit", "-q", "-am", "simplify")
    code, mrun, _ = council(moved, "run", "open", "council-review")
    council(moved, "index")
    write(os.path.join(mrun.strip(), "synthesis.md"), "# Synthesis\n## Kept\n"
          "1 · P1 · Least privilege · app/api.py:1-3 · the change removed the admin check · from: hunt#1\n"
          "2 · P2 · Least privilege · app/api.py:3 · guard removed right before delete · from: hunt#2\n"
          "3 · P1 · Authentication · app/guard.py:2 · the change deleted the token check · from: hunt#3\n"
          "4 · P1 · Ordering · app/bank.py:2 · the debit now runs before the balance check · from: hunt#4\n"
          "5 · P3 · Naming · app/old.py:2 · an untouched file · from: hunt#5\n"
          "6 · P3 · Naming · app/api.py:1 · a line away from the removed ones · from: hunt#6\n"
          "7 · P3 · Naming · app/guard.py:9 · past the end of the deleted file · from: hunt#7\n")
    code, out, _ = council(moved, "check")
    check("check: lines next to code the change removed are 'touched', not 'pre-existing'",
          "synthesis#1  app/api.py:1-3  ok · touched" in out and "synthesis#2  app/api.py:3  ok · touched" in out, out)
    check("check: a line the change moved is 'touched'", "synthesis#4  app/bank.py:2  ok · touched" in out, out)
    check("check: a file the change deleted is its own verdict, checked against the base — never missing-file",
          re.search(r"synthesis#3  app/guard\.py:2  deleted \(.*\) · touched", out) is not None
          and "synthesis#7  app/guard.py:9  bad-line (the deleted file had 2 lines)" in out, out)
    check("check: lines away from the change stay 'pre-existing'",
          "synthesis#5  app/old.py:2  ok · pre-existing" in out and "synthesis#6  app/api.py:1  ok · pre-existing" in out
          and "7 items, 1 broken citation(s)" in out, out)
    # The run's own files, cited the way the helper names them: found in the run, never "missing-file"
    write(os.path.join(mrun.strip(), "gates", "tests.txt"), "1 passed\n2 failed: test_admin_only\n")
    write(os.path.join(mrun.strip(), "context", "note.md"), "# Note\nthe guard moved\n")
    write(os.path.join(mrun.strip(), "verify-1.md"), "# Verification\n\n| # | Item | Verdict | Evidence |\n")
    write(os.path.join(mrun.strip(), "synthesis.md"), "# Synthesis\n## Kept\n"
          "1 · P1 · Tests · gates/tests.txt:2 · the admin test fails · from: gate:tests\n"
          "2 · P2 · Context · context/note.md:2 · the brief's note · from: hunt#1\n"
          "3 · P2 · Verifier · verify-1.md:3 · the verifier's table · from: hunt#2\n"
          "4 · P2 · Past the end · context/note.md:9 · a line the note hasn't · from: hunt#3\n"
          "5 · P2 · Nowhere · gates/lint.txt:1 · a file nobody wrote · from: hunt#4\n")
    code, out, _ = council(moved, "check")
    check("check: citations of the run's own files (gates/…, context/…, verify-1.md) are found in the run",
          "synthesis#1  gates/tests.txt:2  ok · run file" in out and "synthesis#2  context/note.md:2  ok · run file" in out
          and "synthesis#3  verify-1.md:3  ok · run file" in out, out)
    check("check: ... and a run file's lines are still checked, and a run file that isn't there is still missing",
          "synthesis#4  context/note.md:9  bad-line" in out and "synthesis#5  gates/lint.txt:1  missing-file" in out
          and "5 items, 2 broken citation(s)" in out, out)
    if os.path.isfile(os.path.join(moved, "APP", "OLD.PY")):         # a file system that ignores case
        write(os.path.join(mrun.strip(), "synthesis.md"), "# Synthesis\n## Kept\n"
              "1 · P3 · Naming · APP/OLD.PY:2 · the path in the wrong case · from: hunt#1\n")
        code, out, _ = council(moved, "check")
        check("check: a path cited in the wrong case keeps its real origin", "APP/OLD.PY:2  ok · pre-existing" in out, out)

    # Old lines never read as new for technical reasons: a SHA-256 repository, a line-ending rewrite
    sha = os.path.join(tmp, "sha256")
    os.makedirs(sha)
    try:                                    # git < 2.29 has no SHA-256 repositories: skip that one check
        git(sha, "init", "-q", "--object-format=sha256")
        sha256 = True
    except subprocess.CalledProcessError:
        sha256 = False
        print("[SKIP] check: origins hold in a SHA-256 repository (this git has no --object-format)")
    if sha256:
        git(sha, "symbolic-ref", "HEAD", "refs/heads/main")
        write(os.path.join(sha, ".council", "council.config.md"), "# Council config\n")
        write(os.path.join(sha, ".council", ".gitignore"), "runs/\n")
        write(os.path.join(sha, "a.py"), "l1\nl2\nl3\nl4\nl5\n")
        git(sha, "add", "-A")
        git(sha, "commit", "-q", "-m", "base")
        git(sha, "checkout", "-q", "-b", "feature")
        append(os.path.join(sha, "a.py"), "l6\nl7\n")
        git(sha, "commit", "-q", "-am", "more")
        code, srun, _ = council(sha, "run", "open", "council-review")
        council(sha, "index")
        write(os.path.join(srun.strip(), "synthesis.md"), "# Synthesis\n## Kept\n"
              "1 · P3 · P · a.py:2 · old · from: x#1\n2 · P3 · P · a.py:7 · new · from: x#2\n")
        code, out, _ = council(sha, "check")
        check("check: origins hold in a SHA-256 repository",
              "synthesis#1  a.py:2  ok · pre-existing" in out and "synthesis#2  a.py:7  ok · introduced" in out, out)
    eol = new_repo(tmp, "eol")
    write(os.path.join(eol, ".council", "council.config.md"), "# Council config\n")
    write(os.path.join(eol, ".council", ".gitignore"), "runs/\n")
    with open(os.path.join(eol, "a.py"), "wb") as f:
        f.write(b"l1\r\nl2\r\nl3\r\nl4\r\n")
    git(eol, "add", "-A")
    git(eol, "commit", "-q", "-m", "base")
    git(eol, "checkout", "-q", "-b", "feature")
    code, erun, _ = council(eol, "run", "open", "council-review")
    council(eol, "index")
    with open(os.path.join(eol, "a.py"), "wb") as f:
        f.write(b"l1\nl2\nl3 changed\nl4\n")
    write(os.path.join(erun.strip(), "synthesis.md"), "# Synthesis\n## Kept\n"
          "1 · P3 · P · a.py:1-2 · old · from: x#1\n2 · P3 · P · a.py:3 · changed · from: x#2\n")
    code, out, _ = council(eol, "check")
    check("check: lines whose endings alone changed are never called 'introduced'",
          "synthesis#1  a.py:1-2  ok · origin unknown (only line endings changed)" in out
          and "synthesis#2  a.py:3  ok · introduced" in out, out)

    # A synthesis the check can't read is never a pass
    council(cites, "run", "close", "--status", "abandoned")
    code, urun, _ = council(cites, "run", "open", "council-review")
    usyn = os.path.join(urun.strip(), "synthesis.md")
    write(usyn, "# Synthesis — the first four citations are wrong\n## Kept\n"
          "| # | Sev | Principle | Cite | Title | From |\n|---|---|---|---|---|---|\n"
          "| 1 | P1 | Validation | web/ghost.py:40 | Missing check | hunt#1 |\n"
          "### 2 · P2 · Tests · web/db.py:999 · No test · from: beck#2\n"
          "3. P2 · Tests · web/db.py:500 · No test either · from: beck#3\n"
          "4 · P2 · just a title, no citation\n"
          "**5** · P2 · Tests · web/nope.py:1 · a bold number · from: beck#5\n"
          "6a · P2 · Tests · web/db.py:1 · a lettered number · from: beck#6\n## Cut\n")
    code, out, _ = council(cites, "check")
    check("check: item lines it can't read fail the check, and are counted apart from broken citations",
          code == 1 and "synthesis: 4 item line(s) check can't read" in out
          and "check: 2 items, 1 broken citation(s) · 4 item line(s) check can't read" in out, out)
    check("check: a bold or lettered item number is read",
          "synthesis#5  web/nope.py:1  missing-file" in out and "synthesis#6a  web/db.py:1  ok" in out, out)
    write(usyn, "# Synthesis\n## Kept\n## Cut\n")
    code, out, _ = council(cites, "check")
    check("check: a synthesis with no items and no (none) line is not a pass", code == 1 and "nothing was checked" in out, out)

    # Items grouped under a heading the worker chose — by area, by file, with an emoji — are still
    # items: they count towards the cap, and check reads them instead of saying nothing was checked.
    grp = new_repo(tmp, "grouped")
    write(os.path.join(grp, ".council", "council.config.md"), "# Council config\n")
    write(os.path.join(grp, ".council", ".gitignore"), "runs/\n")
    write(os.path.join(grp, "a.py"), "".join(f"l{i}\n" for i in range(1, 10)))
    git(grp, "add", "-A")
    git(grp, "commit", "-q", "-m", "base")
    code, grun, _ = council(grp, "run", "open", "council-review")
    grun = grun.strip()
    write(os.path.join(grun, "brief.md"), "# Brief\n## Seats\n### lens — Lane\n- ref: none\n- cap: 3\n")
    write(os.path.join(grun, "seats", "lens.md"), "# Lens — Lane (council-review)\nref: none\n## Index\n"
          "### Auth\n1 · P1 · P · a.py:1 · x\n2 · P1 · P · a.py:2 · y\n"
          "### `a.py` storage\n3 · P2 · P · a.py:3 · z\n"
          "### Nice to have\n4 · P3 · P · a.py:4 · w\n5 · P3 · P · a.py:5 · v\n\n### 1. x\nThe body · with a dot.\n")
    code, out, _ = council(grp, "collect")
    check("collect: items grouped under headings of the worker's own choosing are counted, not called an empty Index",
          code == 1 and "empty-index" not in out and re.search(r"^lens\s+ok\s+5/3\s+\d+\s+n/a\s+5/5\s+- · over-cap$",
                                                              row(out, "lens")) is not None, out)
    write(os.path.join(grun, "synthesis.md"), "# Synthesis\n## KEPT\n### Security\n"
          "1 · P1 · P · a.py:1 · a real one · from: lens#1\n"
          "   - 3 callers reach it · origin: introduced\n"
          "2 · P2 · P · a.py:2 · another · from: lens#2\n")
    code, out, _ = council(grp, "check")
    check("check: '## KEPT', a group heading and an indented note under an item are all read",
          code == 0 and "nothing was checked" not in out and "can't read" not in out
          and "check: 2 items, 0 broken citation(s)" in out, out)
    write(os.path.join(grun, "synthesis.md"), "# Synthesis\n## Kept\n"
          "1 · P1 · P · a.py:1 · a real one · from: lens#1\n2) P2 — no separators at all\n")
    code, out, _ = council(grp, "check")
    check("check: a line it can't read is counted as that, never as a broken citation",
          code == 1 and "check: 1 items, 0 broken citation(s) · 1 item line(s) check can't read" in out, out)
    code, out, err = council(grp, "check", os.path.join(grun, "nope.md"))
    check("check: a named file that doesn't exist says so once (a refusal, exit 2), and never 'nothing to check'",
          code == 2 and (out + err).count("no such file") == 1 and "nothing to check" not in out + err, out + err)
    write(usyn, "# Synthesis\n## Kept\n(none) — the change only renames a file\n## Cut\n")
    code, out, _ = council(cites, "check")
    check("check: '(none)' under Kept is an honest empty result", code == 0 and "check: 0 items, 0 broken" in out, out)
    code, out, err = council(cites, "check", os.path.join(urun.strip(), "seats", "nobody.md"))
    check("check: a file named on the command line that doesn't exist is refused (exit 2), never a pass",
          code == 2 and "no such file" in err, out + err)
    council(cites, "run", "close", "--status", "abandoned")

@part("runs")
def runs_second_run(tmp):
    global run2   # later "runs" blocks carry on with these
    # A second run: refused, then alongside; never guessing
    code, _, err = council(repo, "run", "open", "council-research")
    check("run open: refuses a second in-progress run on this tree", code == 2 and "already in progress" in err and "--alongside" in err, err)
    code, run2, err = council(repo, "run", "open", "council-research", "--alongside")
    run2 = run2.strip()
    check("run open --alongside: opens it and says to pass --run", code == 0 and os.path.isdir(run2) and "--run" in err, run2 + err)
    code, out, _ = council(repo, "run", "status")
    check("run status: lists several open runs", out.count("· here") == 2 and "council-research" in out and "council-review" in out, out)
    code, out, err = council(repo, "state")
    check("state: never guesses between several open runs", code == 2 and "several runs are open" in err, out + err)
    code, out, err = council(repo, "state", "--run", run2)
    check("state --run: acts on the named run", code == 0 and "mode: council-research" in out, out + err)
    code, out, err = council(repo, "state", "--run", os.path.basename(run2))
    check("state --run: a bare folder name works too", code == 0 and "mode: council-research" in out, out + err)
    code, out, _ = council(repo, "memory", "select", "--run", run2)
    check("memory select: before any seat is recorded, the roster stands in", "AP-3" in out and "AP-1" not in out, out)

    # Seat-file formats (in the second run)
    seats2 = os.path.join(run2, "seats")
    write(os.path.join(run2, "brief.md"),
          "# Brief — formats\n## Seats\n"
          f"### pair — Frontend and UX (Dodds, Norman)\n- ref: `{ref('quality-frontend.md')}`\n- ref: {ref('quality-ux.md')}\n- cap: 4\n"
          "### listy — A list-style index\n- ref: none\n"
          "### multi — Several lines in one citation\n- ref: none\n"
          "### hollow — Header only\n- ref: none\n"
          "### messy — Unreadable index lines\n- ref: none\n")
    write(os.path.join(seats2, "pair.md"),
          f"# Pair — Frontend and UX (council-research)\nref: {first_heading('quality-frontend.md')}\nref: {first_heading('quality-ux.md')}\n"
          "## Index\n1 · strong · Principle 1 · `src/stats.py:1–2` · a backticked path and an en-dash range\n")
    write(os.path.join(seats2, "listy.md"),
          "# Listy — list-style (council-research)\nref: none\n## Index\nMost important first:\n"
          "- 1 · moderate · inquiry · src/report.py:1 · written as a list item\n\n### 1. written as a list item\nThe body.\n")
    write(os.path.join(seats2, "multi.md"),
          "# Multi — several lines (council-research)\nref: none\n## Index\n"
          "1 · moderate · inquiry · src/stats.py:2,7-9 · one claim cites a line and a range\n")
    write(os.path.join(seats2, "hollow.md"), "# Hollow — header only (council-research)\nref: none\nquestion: q\n## Index\n")
    write(os.path.join(seats2, "messy.md"), "# Messy — x (council-research)\nref: none\n## Index\n1) P2 — no separators at all\n")

    # A section is read by what it calls itself, and an entry by its own marks: a heading's aside, a
    # title that happens to say "retired", or a **Deprecated:** line about the code never drop a
    # settled entry. The user settled these; silently withholding them is the failure this guards.
    write(os.path.join(msec, ".council", "conventions.md"),
          "# m\n## Accepted Patterns — intentional; never re-propose these\n"
          "### AP-1: live one\n"
          "### AP-2: Superseded verdict rows stay in the archive\n**Pattern:** kept for audit\n"
          "### AP-3: The (retired) v1 route still answers 410\n**Pattern:** on purpose\n"
          "## Enforced Conventions (replaces the deprecated STYLE.md)\n"
          "### EC-1: Retired flags stay registered in the manifest\n**Rule:** never delete a flag row\n"
          "### EC-2: Never call the old loader\n**Rule:** use load()\n"
          "**Deprecated:** `load_v1()` — kept only for the migration script\n"
          "### EC-3: accepted after a proposal\n**Status:** accepted (proposed 2026-07-01, approved 2026-07-02)\n"
          "### EC-4: a superseded field that says no\n**Pattern:** x · **Superseded:** no\n"
          "### Notes on the draft-flag protocol\nSome notes about EC-1.\n"
          "### EC-5: after a note sub-heading\n**Rule:** y\n"
          "## Decisions — each supersedes an older ADR\n### D-1: the user ruled\n")
    code, out, _ = council(msec, "memory", "select", "x.py")
    check("memory select: a settled section with 'propose' or 'deprecated' further along its heading still serves",
          code == 0 and all(f"{i} ·" in out for i in ["AP-1", "AP-2", "AP-3", "EC-1", "EC-2", "EC-3", "EC-4", "EC-5", "D-1"])
          and "9 every-run entries of 9 apply" in out and "retired or not yet accepted" not in out, out)
    write(os.path.join(msec, ".council", "conventions.md"),
          "# Accepted Patterns\n## AP-1: live\n# Rejected\n## AP-2: the user said no\n# Retired\n### EC-3: withdrawn rule\n")
    code, out, _ = council(msec, "memory", "select", "x.py")
    check("memory select: with #-level sections, a '# Rejected' or '# Retired' one is not served either",
          "AP-1 ·" in out and "AP-2" not in out and "EC-3" not in out
          and "1 every-run entries of 1 apply" in out, out)
    write(os.path.join(msec, ".council", "conventions.md"),
          "# m\n## Enforced Conventions\n### EC-32: An EC-17 cascade carries an assertion\n"
          "**Convention:** it extends two rules:\n- **EC-17 cascade** — the real flag path\n"
          "- **EC-9 verdicts** — stay pinned\n**Scope:** webapp/backend/**\n"
          "### EC-40: the old endpoint\n**Rule:** clients call /risk\n"
          "- **EC-41 replaces this** for batch callers\n**Retired:** 2026-09-10 — superseded by EC-41\n"
          "- **EC-13 — a rule of its own, written inside another entry.** never Z\n")
    code, out, _ = council(msec, "memory")
    check("memory: a bold-id bullet inside a heading entry is that entry's body, not an entry of its own",
          "EC-32 · An EC-17 cascade carries an assertion · scope: webapp/backend/**" in out
          and "EC-40 · the old endpoint · not served (marked retired)" in out
          and not any(f"{i} ·" in out for i in ["EC-17", "EC-9", "EC-41", "EC-13"]), out)
    check("memory: ... and a bullet written as an entry of its own inside one is named, not dropped in silence",
          "not read" in out and "EC-13" in out, out)
    write(os.path.join(msec, ".council", "conventions.md"),
          "# m\n## Enforced Conventions\n1. **EC-1 — a numbered entry.** never X\n"
          "2. **EC-2 — another.** never Y\n   **Scope:** src/**\n- EC-3: a plain bullet — never Z\n")
    code, out, err = council(msec, "memory", "select", "src/a.py")
    check("memory select: numbered bold entries are read like bullet ones",
          "EC-1 ·" in out and "EC-2 ·" in out and "1 scoped and 1 every-run entries of 2 apply" in out, out)
    check("memory select: ... and a plain bullet that names an id is warned about, never dropped in silence",
          "EC-3" in err and "not read" in err, err)
    write(os.path.join(msec, ".council", "conventions.md"), msec_conv)   # as the later doctor check expects
    code, out, _ = council(repo, "collect", "--run", run2)
    check("collect: a paired seat proves both reference docs", re.search(r"^pair\s+ok\s+1/4\s+\d+\s+ok\s+1/1", out, re.MULTILINE) is not None, out)
    check("collect: a list-style index line counts; prose under the Index is ignored",
          re.search(r"^listy\s+ok\s+1/8\s+\d+\s+n/a\s+1/1", out, re.MULTILINE) is not None, out)
    check("collect: a comma list of lines and ranges is a good citation",
          re.search(r"^multi\s+ok\s+1/8\s+\d+\s+n/a\s+1/1", out, re.MULTILINE) is not None, out)
    check("collect: a header-only seat file is caught", "empty-index" in row(out, "hollow"), out)
    check("collect: an index line it can't read is caught", "unparsed-index(1)" in row(out, "messy"), out)
    write(os.path.join(seats2, "pair.md"),
          f"# Pair — Frontend and UX (council-research)\nref: {first_heading('quality-frontend.md')}\n"
          "## Index\n1 · strong · Principle 1 · src/stats.py:1 · x\n")
    code, out, _ = council(repo, "collect", "--run", run2)
    check("collect: a paired seat missing one ref: line is a mismatch", "MISMATCH" in row(out, "pair"), out)

@part("collect")
def collect_one_bad_seat(tmp):
    # One bad seat on its own fails collect: each problem alone, exit code included
    lone = new_repo(tmp, "lone")
    write(os.path.join(lone, ".council", "council.config.md"), "# Council config\n")
    write(os.path.join(lone, ".council", ".gitignore"), "runs/\n")
    write(os.path.join(lone, "a.txt"), "".join(f"{i}\n" for i in range(1, 10)))
    git(lone, "add", "-A")
    git(lone, "commit", "-q", "-m", "a")

    def lone_collect(block, seat, mode="council-review", extra=None):
        _, r, _ = council(lone, "run", "open", mode, "--alongside")
        r = r.strip()
        write(os.path.join(r, "brief.md"), "# Brief\n## Seats\n### s1 — Lane (S)\n" + block + "\n")
        write(os.path.join(r, "seats", "s1.md"), seat)
        council(lone, "seat", "s1", "done", "--run", r)
        if extra:
            extra(r)
        code_, out_, _ = council(lone, "collect", "--run", r)
        council(lone, "run", "close", "--run", r, "--status", "abandoned")
        return code_, out_

    one = "1 · P1 · Principle 1 · a.txt:1 · x\n"
    lone_cases = [
        ("a ref: line that doesn't match its doc", f"- ref: {ref('security.md')}",
         "# S — Security (council-review)\nref: I skimmed it\n## Index\n" + one, "MISMATCH"),
        ("a reference doc that doesn't exist", "- ref: /no/such/doc.md", "# S\nref: x\n## Index\n" + one, "no-doc"),
        ("an empty Index", "- ref: none", "# S\nref: none\n## Index\n", "empty-index"),
        ("an index line it can't read", "- ref: none",
         "# S\nref: none\n## Index\n" + one + "2) P1 — auth bypass in login.py line 99\n", "unparsed-index(1)"),
        ("more items than its cap", "- ref: none\n- cap: 1",
         "# S\nref: none\n## Index\n" + one + "2 · P2 · Principle 1 · a.txt:2 · y\n", "over-cap"),
        ("broken citations", "- ref: none",
         "# S\nref: none\n## Index\n1 · P1 · P · a.txt:40 · x\n2 · P1 · P · nope.py:3 · y\n", "broken-cites"),
        ("an item with no citation field", "- ref: none", "# S\nref: none\n## Index\n1 · P2 · just a title\n",
         "unparsed-index(1)"),
        ("a first line that isn't a '# ' heading (the seat-check hook's line 1)", "- ref: none",
         "S — Lane (council-review)\nref: none\n## Index\n" + one, "no-heading"),
    ]
    for what, block, seat, flag in lone_cases:
        code, out = lone_collect(block, seat)
        check(f"collect: a lone seat with {what} fails collect on its own",
              code == 1 and flag in row(out, "s1") and "seats in order" not in out, out)
    code, out = lone_collect("- ref: none\n- cap: 3", "# S\nref: none\n## Index\n### P1\n" + one
                             + "2 · P1 · P · a.txt:2 · y\n### P2 — lower\n3 · P2 · P · a.txt:3 · z\n"
                             "4 · P2 · P · a.txt:4 · w\n5 · P2 · P · a.txt:5 · v\n\n### 1. x\nThe body · more.\n")
    check("collect: items grouped under ### P1 / ### P2 inside the Index are read, and over the cap is reported",
          code == 1 and re.search(r"^s1\s+ok\s+5/3\s+\d+\s+n/a\s+5/5\s+- · over-cap$", row(out, "s1")) is not None, out)
    card = os.path.join(lone, ".council", "cards", "hunt.md")
    write(card, "# Hunt — Security card for eval\nsource: x\n")
    for key in ("- **ref:** ", "ref: ", "- Ref: ", "- refs: ", "- reference: ", "- ref : ", "  - ref: "):
        code, out = lone_collect(key + card, "# S\nref: I did not open the card\n## Index\n" + one)
        check(f"collect: a brief's ref line written '{key.strip()}' is still checked",
              code == 1 and "MISMATCH" in row(out, "s1"), out)
    design = os.path.join(lone, "DESIGN.md")
    write(design, "---\nname: design system\n---\n# Design System — Eval\nbody\n")
    code, out = lone_collect(f"- ref: {design}", "# S\nref: Design System — Eval\n## Index\n" + one)
    check("collect: a doc that opens with front matter is proved by its first heading",
          code == 0 and re.search(r"^s1\s+ok\s+1/8\s+\d+\s+ok\s", row(out, "s1")) is not None, out)
    code, out = lone_collect(f"- ref: {design}", "# S\nquestion: q\n## Index\n" + one)
    check("collect: a seat with no ref: line never passes the proof of reading",
          code == 1 and "MISMATCH" in row(out, "s1"), out)

    # A Workflow's agents are typed workflow-subagent, so the seat-check hook never sees their files:
    # collect holds every .md in seats/ to the same shape, named in the brief or not.
    def workflow_files(r, bad=True):
        write(os.path.join(r, "seats", "wf-b.md"), "# S — Lane, part B (council-review)\nref: none\n## Index\n" + one)
        if bad:
            write(os.path.join(r, "seats", "wf-a.md"), "Verdicts for part A\n\nAll fine.\n" + "x" * 20000 + "\n")

    code, out = lone_collect("- ref: none", "# S\nref: none\n## Index\n" + one, extra=workflow_files)
    check("collect: a file in seats/ that no seat block names is checked like a seat file, and a bad one fails collect",
          code == 1 and all(f in row(out, r"wf-a\.md") for f in ("not-in-brief", "no-heading", "no-index", "over-16KB", "no-ref"))
          and "not-in-brief" in row(out, r"wf-b\.md") and "no-heading" not in row(out, r"wf-b\.md")
          and "seat-check hook never checks" in out and "seats in order" not in out, out)
    code, out = lone_collect("- ref: none", "# S\nref: none\n## Index\n" + one, extra=lambda r: workflow_files(r, bad=False))
    check("collect: a well-formed file in seats/ outside the brief passes, and the summary counts it apart from the seats",
          code == 0 and "all 1 seats in order · 1 other file(s) in seats/ in order too" in out, out)

    heb = os.path.join(lone, "HEBREW.md")
    write(heb, "# \u05de\u05d3\u05e8\u05d9\u05da \u05d0\u05d1\u05d8\u05d7\u05d4\nbody\n")
    code, out = lone_collect(f"- ref: {heb}", "# S\nref: \u05de\u05d3\u05e8\u05d9\u05da \u05d0\u05d1\u05d8\u05d7\u05d4\n## Index\n" + one)
    check("collect: a reference doc whose title has no Latin letters can still be proved",
          code == 0 and re.search(r"^s1\s+ok\s+1/8\s+\d+\s+ok\s", row(out, "s1")) is not None, out)
    code, out = lone_collect(f"- ref: {heb}", "# S\nref: I did not open it\n## Index\n" + one)
    check("collect: ... and a worker that did not copy that title is still a MISMATCH",
          code == 1 and "MISMATCH" in row(out, "s1"), out)

    def sat_out(r, ghost=False):
        write(os.path.join(r, "debate.md"), "# War room\n## Seats\n### s1-r2 — Lane (S), round 2\n- ref: none\n"
              "### s2-r2 — Other (T), round 2\n- ref: none\n")
        write(os.path.join(r, "seats", "s1-r2.md"), "# S — x (council-plan, round 2)\nref: none\n## Index\n"
              "1 · hold · P1 · a.txt:1 · y\n")
        council(lone, "seat", "s2-r2", "skipped", "note=sits out: no room", "--run", r)
        if ghost:
            with open(os.path.join(r, "brief.md"), "a", encoding="utf-8") as f:
                f.write("### ghost — Never ran\n- ref: none\n")
            council(lone, "seat", "ghost", "skipped", "--run", r)

    code, out = lone_collect("- ref: none", "# S\nref: none\n## Index\n" + one, "council-plan", sat_out)
    check("collect: a round-2 seat that sat out (recorded skipped) is shown, not demanded",
          code == 0 and "skipped" in row(out, "s2-r2") and "sits out: no room" in row(out, "s2-r2")
          and "1 sat out" in out, out)
    code, out = lone_collect("- ref: none", "# S\nref: none\n## Index\n" + one, "council-plan",
                             lambda r: sat_out(r, ghost=True))
    check("collect: a first-round seat marked skipped with no file is still a hole",
          code == 1 and re.search(r"^ghost\s+missing", out, re.MULTILINE) is not None, out)

@part("runs")
def runs_found_by_session(tmp):
    # A run whose code root is a worktree is found from the main checkout by the session that drives it
    # (in run 2 every command needed --run) — never another session's run, and never one of several.
    main = new_repo(tmp, "by-session")
    write(os.path.join(main, "a.txt"), "a\n")
    write(os.path.join(main, ".council", "council.config.md"), "# Council config\n")
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "init")
    wt, wt2 = os.path.join(main, ".claude", "worktrees", "feat"), os.path.join(main, ".claude", "worktrees", "feat2")
    git(main, "worktree", "add", "-q", "-b", "feat", wt)
    git(main, "worktree", "add", "-q", "-b", "feat2", wt2)
    me, other = {"CLAUDE_CODE_SESSION_ID": "sess-me"}, {"CLAUDE_CODE_SESSION_ID": "sess-other"}
    _, out, _ = council(main, "run", "open", "council-review", "--code-root", wt, env=me)
    run = out.strip().splitlines()[-1] if out.strip() else ""
    code, out, err = council(main, "state", "next=found by session", env=me)
    check("state: from the main checkout, the run this session drives is found though its code root is a worktree",
          code == 0 and run != "" and "next: found by session" in read(os.path.join(run, "session-state.md")), out + err)
    code, out, err = council(main, "state", "next=not mine", env=other)
    check("state: another session's run on another tree is never picked — the refusal still names --run",
          code == 2 and "--run" in err and "not mine" not in read(os.path.join(run, "session-state.md")), out + err)
    council(wt2, "run", "open", "council-review", env=me)
    code, out, err = council(main, "state", "next=which one", env=me)
    check("state: a session driving two runs on other trees is told to pass --run, and nothing is written",
          code == 2 and "--run" in err and "which one" not in read(os.path.join(run, "session-state.md")), out + err)

@part("runs")
def runs_reminders_last(tmp):
    # A reminder the Chair must act on is the last line a command prints: in run 2 the Chair cut helper
    # output with `2>&1 | tail -1` 26 times, and a reminder printed before the status line was lost.
    def merged(cwd, *args, env=None):
        p = subprocess.run([BASH, CLI, *args], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                           encoding="utf-8", errors="replace", env=dict(GIT_ENV, **(env or {})), timeout=120)
        lines = [line for line in p.stdout.splitlines() if line.strip()]
        return p.returncode, (lines[-1] if lines else ""), p.stdout
    rem = new_repo(tmp, "reminders-last")
    write(os.path.join(rem, ".council", "council.config.md"), "# Council config\n- agent cap: 1\n")
    council(rem, "run", "open", "council-review", env={"CLAUDE_CODE_SESSION_ID": "s-rem"})
    code, last, whole = merged(rem, "state", "waiting=Which option?")
    check("state waiting=: the alert reminder is the last line printed, so `2>&1 | tail -1` keeps it",
          code == 0 and "PushNotification" in last, whole)
    merged(rem, "seat", "w1", "done", "agent=a1", "tokens=20000")
    code, last, whole = merged(rem, "seat", "w2", "done", "agent=a2", "tokens=20000")
    check("seat: past the agent cap, the cap note is the last line printed, after the progress line",
          code == 0 and "over its cap" in last, whole)

@part("runs")
def runs_records_all_or_nothing(tmp):
    # A damaged event stream refuses a write before anything changes, and the repair keeps a copy and drops
    # only the torn tail (helper-runs-6: the state was written, its event refused, and close skipped the ledger).
    aon = new_repo(tmp, "all-or-nothing")
    write(os.path.join(aon, ".council", "council.config.md"), "# Council config\n")
    _, out, _ = council(aon, "run", "open", "council-review")
    run = out.strip().splitlines()[-1]
    st, ev = os.path.join(run, "session-state.md"), os.path.join(run, "events.tsv")
    with open(ev, "a", encoding="utf-8", newline="") as f:
        f.write("1\t2\t2026-10-01T00:00:00Z\trun.ph")              # a writer killed in the middle of a row
    before = read(st)
    code, out, err = council(aon, "state", "phase=prepare", "next=never")
    check("state: a torn event stream refuses the call before anything is written, and names the repair",
          code == 2 and "council run events repair" in err and read(st) == before, err)
    seats_before = read(os.path.join(run, "seats.tsv"))       # run open writes its header
    code, out, err = council(aon, "seat", "w1", "done", "tokens=20000")
    check("seat: the same refusal, with nothing written to seats.tsv or usage.tsv",
          code == 2 and "council run events repair" in err and read(os.path.join(run, "seats.tsv")) == seats_before
          and not os.path.exists(os.path.join(run, "usage.tsv")), err)
    code, out, err = council(aon, "correct", "w1", "tokens=30000", "agents=1", "evidence=the notification said 30000")
    check("correct: the same refusal, and no correction is written",
          code == 2 and "council run events repair" in err and not os.path.exists(os.path.join(run, "corrections.jsonl")), err)
    write(os.path.join(run, "ask.md"), "# Ask — x\nsource: said at the time\n## In your words\nfix it\n")
    code, out, err = council(aon, "ask", "save")
    check("ask save: a state write that records no event still works on a torn stream (it never said nothing was written)",
          code == 0 and "ask-saved:" in read(st), out + err)
    before = read(st)
    code, out, err = council(aon, "run", "close")
    check("run close: refused on a torn stream, and the run stays in progress",
          code == 2 and "council run events repair" in err and read(st) == before, err)
    raw = open(ev, "rb").read()
    code, out, err = council(aon, "run", "events", "repair")
    copies = [n for n in os.listdir(run) if n.startswith("events.tsv.bak")]
    code2, out2, _ = council(aon, "run", "events", "check")
    check("run events repair: keeps a byte copy, drops only the torn tail, records itself, and the stream checks valid",
          code == 0 and len(copies) == 1 and open(os.path.join(run, copies[0]), "rb").read() == raw
          and code2 == 0 and "run.events_repaired" in read(ev) and "run.opened" in read(ev), out + err + out2)
    code, out, err = council(aon, "state", "phase=prepare")
    check("state: after the repair, writes go through", code == 0 and "phase: prepare" in read(st), out + err)
    code, out, err = council(aon, "state", "phase=assign", env={"EVENTS_LOST": "1", "CLOSING": "1"})
    check("state: the close's internal flags can't be inherited from the environment",
          code == 0 and "run.phase_changed\trun\tassign" in read(ev), out + err)
    council(aon, "seat", "w1", "done", "tokens=20000")
    os.remove(ev)
    code, out, err = council(aon, "run", "events", "repair")
    check("run events repair: a missing stream is said not repairable, never rebuilt from guesses",
          code == 2 and "missing" in err and not os.path.exists(ev), err)
    code, out, err = council(aon, "run", "close")
    ledger = read(os.path.join(aon, ".council", "ledger.tsv")) if os.path.exists(os.path.join(aon, ".council", "ledger.tsv")) else ""
    check("run close: with the stream lost, the run still closes, writes its ledger, and says its events were not recorded",
          code == 0 and "status: complete" in read(st) and "not recorded" in err and not os.path.exists(ev)
          and os.path.basename(run) in ledger, out + err)
    # A close whose status event fails at the moment of writing still writes the ledger and the close line.
    late = new_repo(tmp, "late-event")
    write(os.path.join(late, ".council", "council.config.md"), "# Council config\n")
    _, out, _ = council(late, "run", "open", "council-review")
    lrun = out.strip().splitlines()[-1]
    council(late, "seat", "w1", "done", "tokens=20000")
    lst = os.path.join(lrun, "session-state.md")
    write(lst, read(lst).replace("events-schema: 1", "events-schema: 9"))     # every event write now fails
    code, out, err = council(late, "run", "close")
    lledger = read(os.path.join(late, ".council", "ledger.tsv")) if os.path.exists(os.path.join(late, ".council", "ledger.tsv")) else ""
    check("run close: a status event that fails as it is written leaves the run closed, its ledger written and a warning",
          code == 0 and "status: complete" in read(lst) and "closed " in out and os.path.basename(lrun) in lledger
          and "could not be recorded" in err, out + err)

@part("runs")
def runs_closed_run_stays_closed(tmp):
    # A closed run keeps the record its ledger counted (helper-runs-8: a complete run could be re-closed as
    # abandoned and its seats changed) — but the writes its own close and the audit ask for still work, and
    # a late agent report goes through council correct, which refreshes the ledger.
    cl = new_repo(tmp, "closed-stays")
    write(os.path.join(cl, ".council", "council.config.md"), "# Council config\n")
    _, out, _ = council(cl, "run", "open", "council-review")
    run = out.strip().splitlines()[-1]
    name, st = os.path.basename(run), os.path.join(run, "session-state.md")
    write_plan(run, selected=("chair", "w1", "w2", "w3"))
    council(cl, "seat", "w1", "done", "agent=a1", "tokens=20000")
    council(cl, "seat", "w2", "running", "agent=a2")
    council(cl, "seat", "w3", "queued")
    council(cl, "state", "phase=deliver")
    council(cl, "run", "close")
    closed_at, seats_before = re.search(r"^closed: (.+)$", read(st), re.MULTILINE).group(1), read(os.path.join(run, "seats.tsv"))
    code, out, err = council(cl, "run", "close", "--status", "abandoned", "--run", name)
    check("run close: a complete run can't be closed again as abandoned", code == 2 and "status: complete" in read(st), err)
    code, out, err = council(cl, "run", "close", "--run", name)
    check("run close: closing a complete run again as complete says when it closed and changes nothing",
          code == 0 and "already closed" in out and closed_at in out and f"closed: {closed_at}" in read(st), out + err)
    code, out, err = council(cl, "seat", "w1", "failed", "--run", name)
    check("seat: a closed run takes no seat change, and the refusal names council correct",
          code == 2 and "council correct" in err and read(os.path.join(run, "seats.tsv")) == seats_before, err)
    code, out, err = council(cl, "seat", "w2", "done", "agent=a2", "tokens=25000", "--run", name)
    check("seat: a late agent report on a closed run is refused, naming council correct", code == 2 and "council correct" in err, err)
    seats_now = read(os.path.join(run, "seats.tsv"))
    refused = [args for args in (("seat", "w2", "skipped"), ("seat", "verify-plan", "done", "agents=0"), ("seat", "ghost", "done", "agents=0"))
               if council(cl, *args, "--run", name)[0] != 2]
    check("seat: after close, skipped for a seat with an agent on record, and agents=0 for any seat but the plan's Chair, are refused",
          not refused and read(os.path.join(run, "seats.tsv")) == seats_now, str(refused))
    code, out, err = council(cl, "seat", "w3", "skipped", "--run", name)
    check("seat: a seat only queued at close, no agent started, can still be marked skipped", code == 0, out + err)
    code, out, err = council(cl, "seat", "w2", "failed", "note=interrupted", "--run", name)
    check("seat: a seat the close left running can still be marked failed, as the close's own warning asks",
          code == 0 and "w2\tfailed" in read(os.path.join(run, "seats.tsv")), out + err)
    code, out, err = council(cl, "seat", "chair", "done", "agents=0", "--run", name)
    ledger = [line.split("\t") for line in read(os.path.join(cl, ".council", "ledger.tsv")).splitlines()]
    check("seat chair done agents=0: the Chair's own record the audit asks for still goes in after close, and reaches the ledger",
          code == 0 and any(row[1] == name and row[3] == "chair" for row in ledger), out + err + str(ledger))
    refused = [args for args in (("gate", "late", "--run", name, "--", "true"), ("cap", "allow", "1", "--run", name, "--user-said", "go"),
                                 ("state", "next=more", "--run", name))
               if council(cl, *args)[0] != 2]
    check("gate, cap allow and state changes are refused on a closed run", not refused, str(refused))
    code, out, err = council(cl, "state", "deliverable=.council/reviews/x.md", "--run", name)
    check("state deliverable=: still allowed after close, as the close's own hint asks", code == 0, out + err)
    code, out, err = council(cl, "correct", "w1", "tokens=30000", "agents=1", "evidence=the notification said 30000", "--run", name)
    ledger = [line.split("\t") for line in read(os.path.join(cl, ".council", "ledger.tsv")).splitlines()]
    check("correct: a late figure on a complete run refreshes its ledger row",
          code == 0 and any(row[1] == name and row[3] == "w1" and "30000" in row for row in ledger), out + err + str(ledger))
    early = new_repo(tmp, "closed-early")
    write(os.path.join(early, ".council", "council.config.md"), "# Council config\n")
    _, out, _ = council(early, "run", "open", "council-review")
    erun = out.strip().splitlines()[-1]
    ename = os.path.basename(erun)
    write_plan(erun, selected=("chair", "w1"))
    council(early, "seat", "w1", "done", "agent=a1", "tokens=20000")
    council(early, "run", "close")
    code, out, err = council(early, "run", "close", "--status", "abandoned", "--run", ename)
    eledger = read(os.path.join(early, ".council", "ledger.tsv"))
    check("run close: a run closed complete before Deliver can be closed again as abandoned, as its close says, and leaves the ledger",
          code == 0 and "status: abandoned" in read(os.path.join(erun, "session-state.md")) and ename not in eledger
          and [e[5] for e in events(erun) if e[3] == "run.closed"][-1:] == ["abandoned"], out + err + eledger)
    hand = new_repo(tmp, "closed-by-hand")
    write(os.path.join(hand, ".council", "council.config.md"), "# Council config\n")
    _, out, _ = council(hand, "run", "open", "council-review")
    hrun = out.strip().splitlines()[-1]
    hname = os.path.basename(hrun)
    write_plan(hrun, selected=("chair", "w1"))
    council(hand, "seat", "w1", "done", "agent=a1", "tokens=20000")
    code, out, err = council(hand, "state", "closed=2020-01-01 00:00")
    check("state closed=: the close's own stamp is refused from anywhere but the close",
          code == 2 and "closed:" not in read(os.path.join(hrun, "session-state.md")), out + err)
    council(hand, "state", "status=complete")
    code, out, err = council(hand, "run", "close", "--run", hname)
    check("run close: a run set complete by hand, never closed, still gets its real close — its time, ledger rows and close event",
          code == 0 and re.search(r"^closed: \S", read(os.path.join(hrun, "session-state.md")), re.MULTILINE) is not None
          and hname in read(os.path.join(hand, ".council", "ledger.tsv")) and any(e[3] == "run.closed" for e in events(hrun)), out + err)

@part("runs")
def runs_seat_files(tmp):
    # A seat is done only with its file (sessions-seats-1: a verifier out of turns was recorded done with
    # nothing written), and every verify file in the run folder is checked, a Workflow's too (sessions-seats-4).
    sf = new_repo(tmp, "seat-files")
    write(os.path.join(sf, ".council", "council.config.md"), "# Council config\n")
    _, out, _ = council(sf, "run", "open", "council-implement")
    run = out.strip().splitlines()[-1]
    write_plan(run, selected=("chair", "w1", "verify-1"))
    write(os.path.join(run, "brief.md"), "# Brief\n## Seats\n### w1 — tests (Beck)\n- ref: none\n- out: seats/w1.md\n- cap: 8\n")
    code, out, err = council(sf, "seat", "w1", "done", "agent=a1", "tokens=20000")
    check("seat done: a briefed seat with no file is refused, naming the resume and failed",
          code == 2 and "SendMessage" in err and "failed" in err and "w1\tdone" not in read(os.path.join(run, "seats.tsv")), err)
    code, out, err = council(sf, "seat", "verify-1", "done", "agent=v1", "tokens=20000")
    check("seat done: a verifier with no verify file is refused the same way", code == 2 and "SendMessage" in err, err)
    write(os.path.join(run, "seats", "w1.md"), "# Tests — tests (implement)\nref: none\n## Index\n(none) — nothing\n")
    code, out, err = council(sf, "seat", "w1", "done", "agent=a1", "tokens=20000")
    check("seat done: with its file written, the seat is done", code == 0, out + err)
    code, out, err = council(sf, "seat", "w1", "failed", "note=interrupted")
    check("seat failed: needs no file", code == 0, out + err)
    write(os.path.join(run, "verify-9-a.md"), "Some notes a Workflow agent wrote, with no heading and no table.\n")
    code, out, err = council(sf, "collect")
    check("collect: a verify file with no heading and no verdict table is named, in a build too",
          code == 1 and "verify-9-a.md" in out and "Verification" in out, out + err)
    write(os.path.join(run, "verify-10.md"), "# Verification — x\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n| 1 | a | OK | a.py:1 |\n")
    code, out, err = council(sf, "seat", "verify-1", "done", "agent=v1", "tokens=20000")
    check("seat done: verify-10.md is not verify-1's file", code == 2 and "SendMessage" in err, err)
    ok = new_repo(tmp, "seat-files-only-verify")
    write(os.path.join(ok, ".council", "council.config.md"), "# Council config\n")
    _, out, _ = council(ok, "run", "open", "council-review")
    orun = out.strip().splitlines()[-1]
    write_plan(orun, selected=("chair", "w1"))
    write(os.path.join(orun, "brief.md"), "# Brief\n## Seats\n### w1 — tests (Beck)\n- ref: none\n- out: seats/w1.md\n- cap: 8\n")
    write(os.path.join(orun, "seats", "w1.md"), "# Tests — tests (review)\nref: none\n## Index\n(none) — nothing\n")
    council(ok, "seat", "w1", "done", "agent=a1", "tokens=20000")
    write(os.path.join(orun, "verify-2-a.md"), "Notes with no heading and no table.\n")
    write(os.path.join(orun, "verify-self.md"), "# Self-check — x\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n| 1 | a | CONFIRMED | a.py:1 |\n")
    code, out, err = council(ok, "collect")
    check("collect: when only a verify file is out of shape, it says to fix it — not that seats are still working",
          code == 1 and "fix the rows above" in out and "still working" not in out and "verify-self.md" not in out, out + err)
    council(ok, "state", "phase=deliver")
    code, out, err = council(ok, "run", "close")
    check("run close: names the out-of-shape verify file and how to mend it, never a Solo run's verify-self.md",
          code == 0 and "verify-2-a.md is out of shape" in err and "verify-self.md" not in err and "council collect" not in line_of(err, "verify-2-a.md"),
          err)

@part("runs")
def runs_tool_calls(tmp):
    # Tool-call budgets are measured, not only planned (sessions-seats-6: in run 2 a seat used 57 tool calls
    # against 40 and nothing noticed). A resumed agent's later figure is its running total, counted once.
    tc = new_repo(tmp, "tool-calls")
    write(os.path.join(tc, ".council", "council.config.md"), "# Council config\n")
    _, out, _ = council(tc, "run", "open", "council-review")
    run = out.strip().splitlines()[-1]
    write_plan(run, selected=("chair", "w1"))                     # tool-calls 15 for each selected seat
    write(os.path.join(run, "brief.md"), "# Brief\n## Seats\n### w1 — w (W)\n- ref: none\n- out: seats/w1.md\n- cap: 8\n")
    write(os.path.join(run, "seats", "w1.md"), "# W — w (review)\nref: none\n## Index\n(none) — nothing\n")
    code, out, err = council(tc, "seat", "w1", "done", "agent=a1", "tokens=20000", "tools=57")
    check("seat done tools=: a seat over its plan's tool-call budget is said, with both numbers",
          code == 0 and "57 tool calls" in out + err and "15" in out + err, out + err)
    code, out, err = council(tc, "seat", "w1", "done", "agent=a1", "tokens=30000", "tools=70")
    check("seat done tools=: a resumed agent's later figure is its running total, counted once (70, not 127)",
          code == 0 and "70 tool calls" in out + err and "127" not in out + err, out + err)
    bad = [args for args in (("seat", "w1", "done", "tokens=20000", "tools=lots"), ("seat", "w1", "running", "agent=a2", "tools=5"))
           if council(tc, *args)[0] != 2]
    check("seat tools=: a count that isn't digits, or tools= on a start, is refused", not bad, str(bad))
    code, out, err = council(tc, "collect")
    check("collect: shows a seat's tool calls against its budget", "tools 70/15" in out, out + err)

@part("runs")
def runs_worktrees_close_and_find(tmp):
    global fresh   # later "runs" blocks carry on with these
    # A linked worktree
    wt = os.path.join(tmp, "wt")
    git(repo, "worktree", "add", "-q", "-b", "other", wt)
    code, out, _ = council(wt, "home")
    check("home: a linked worktree uses the main checkout's council", slash(out).lower().endswith("/repo/.council"), out)
    code, out, _ = council(wt, "run", "status")
    check("run status: runs from the main checkout show as elsewhere in a worktree", "elsewhere:" in out, out)

    # A bare repository with worktrees: the council lives in the worktree that holds the config
    bsrc = new_repo(tmp, "bare-src")
    write(os.path.join(bsrc, "a.txt"), "x\n")
    git(bsrc, "add", "-A")
    git(bsrc, "commit", "-q", "-m", "init")
    bare = os.path.join(tmp, "proj.git")
    git(tmp, "clone", "-q", "--bare", bsrc, bare)
    main_wt = os.path.join(tmp, "main-wt")
    git(bare, "worktree", "add", "-q", main_wt, "main")
    write(os.path.join(main_wt, ".council", "council.config.md"), "# Council config — bare\n")
    git(bare, "worktree", "add", "-q", "-b", "f1", os.path.join(tmp, "aa-feature"), "main")
    code, out, _ = council(os.path.join(tmp, "aa-feature"), "home")
    code2, out2, _ = council(main_wt, "home")
    check("home: in a bare repository's worktrees, the one holding the config, whatever their names",
          slash(out).lower().endswith("/main-wt/.council") and slash(out2).lower().endswith("/main-wt/.council"), out + out2)

    # Map and doctor
    code, out, _ = council(repo, "map", "status")
    check("map status: no map yet", code == 0 and "no map yet" in out, out)
    prev = git(repo, "rev-parse", "HEAD~1")
    write(os.path.join(repo, ".council", "map.md"), f"# Codebase map\nmap-commit: {prev}\nupdated: 2026-09-15\n")
    code, out, _ = council(repo, "map", "status")
    check("map status: counts commits behind and changed areas", "1 commits behind" in out and "src/" in out, out)
    code, out, _ = council(os.path.join(repo, "src"), "map", "status")
    check("map status: from a subfolder, still lists every changed area",
          all(a in out for a in ("src/", "scripts/", "tests/", "README.md")), out)
    write(os.path.join(repo, ".council", "cards", "fowler.md"),
          "# Fowler — Structure card for eval\nsource: references/nope.md · written: 2026-09-15 @ abc1234\n## Principles, applied here\n1. x — here: y\n")
    code, out, _ = council(repo, "doctor")
    check("doctor: a missing reference doc is an error", code == 1 and "does-not-exist.md" in out and "Fix:" in out, out)
    check("doctor: flags a gate row whose columns shifted", "columns have shifted" in out, out)
    check("doctor: flags a repeated slug", "repeats a slug: fowler" in out, out)
    check("doctor: flags a seat without a card", "seat 'Ghost' has no card" in out, out)
    check("doctor: flags a card whose source doc is gone", "names a source doc that doesn't exist: references/nope.md" in out, out)
    check("doctor: flags stale memory anchors", "3 memory anchor(s) point at code" in out, out)
    check("doctor: notices a config without a stack fingerprint", "has no stack-fingerprint" in out, out)
    check("doctor: every finding carries a fix", out.count("Fix:") == out.count("ERROR") + out.count("WARN "), out)
    gone_map = new_repo(tmp, "maphistory")
    write(os.path.join(gone_map, "a.txt"), "x\n")
    git(gone_map, "add", "-A")
    git(gone_map, "commit", "-q", "-m", "init")
    write(os.path.join(gone_map, ".council", "council.config.md"), "# Council config — map\n")
    write(os.path.join(gone_map, ".council", "map.md"), "# Map\nmap-commit: 0123456789abcdef0123456789abcdef01234567\n")
    code, out, _ = council(gone_map, "doctor")
    check("doctor: a map-commit that isn't in this repo's history is flagged", "isn't in this repo's history" in out, out)
    code, out, _ = council(msec, "doctor")
    check("doctor: counts a proposal written as a heading, and flags entries under a section it can't place",
          "2 memory proposal(s) await" in out and "1 memory entr" in out and "never reach a brief" in out, out)
    write(ms_conv, "# m\n| Id | Rule |\n|---|---|\n| AP-1 | tables are not entries |\n")
    code, out, _ = council(ms, "doctor")
    check("doctor: flags a memory file whose entries can't be read", "no entry could be read" in out, out)
    write(rs_cfg, "# c\n## Memory\n- conventions: .council/conventions.md\n")
    code, out, _ = council(rs, "doctor")
    check("doctor: a configured memory path that doesn't exist points at the real file, never at creating an empty one",
          "doesn't exist — reading" in out and "council-init creates" not in out and "no memory file" not in out, out)
    write(os.path.join(rs, ".council", "conventions.md"), read(ref(os.path.join("templates", "conventions.md"))))
    code, out, _ = council(rs, "doctor")
    check("doctor: a second memory file with entries the council never reads is flagged", "holds 6 entries the council never reads" in out, out)
    code, out, _ = council(msc, "doctor")
    check("doctor: flags memory scope items that match nothing, and says the entry still reaches a brief through its others",
          "memory scope item(s) match no file, seat or mode" in out and "through its other scope items" in out
          and "drop the ones whose folder is gone" in out, out)
    nomem = new_repo(tmp, "nomem")
    write(os.path.join(nomem, ".council", "council.config.md"), "# c\n## Memory\n- conventions: docs/memory.md\n")
    code, out, _ = council(nomem, "doctor")
    check("doctor: a configured memory path with no file anywhere names that path", "the config names" in out and "docs/memory.md" in out, out)
    code, _, err = council(nomem, "memory")
    check("memory: ... and memory says the same", code == 2 and "docs/memory.md" in err and "doesn't exist" in err, err)

    # A blank .council/conventions.md beside a memory file full of entries: every command says so, so
    # a project's settled decisions can never sit unread in silence.
    two = new_repo(tmp, "twomem")
    write(os.path.join(two, ".council", "council.config.md"), "# c\n")
    write(os.path.join(two, ".council", "conventions.md"), read(ref(os.path.join("templates", "conventions.md"))))
    write(os.path.join(two, "conventions.md"), "# m\n## Accepted Patterns\n### AP-1: the real one\n### AP-2: and another\n")
    code, out, err = council(two, "memory")
    check("memory: a second memory file with entries the council never reads is called out",
          "a second memory file" in err and "2 entries" in err, out + err)
    code, out, err = council(two, "memory", "select", "x.py")
    check("memory select: ... and select says it too, where a brief would see it",
          "a second memory file" in err, out + err)
    code, out, _ = council(two, "doctor")
    check("doctor: ... and so does doctor", "a second memory file" in out, out)
    # The same file, named in the config the other way round, is not a second file
    write(os.path.join(two, ".council", "conventions.md"), "# m\n## Accepted Patterns\n### AP-1: the only one\n")
    os.remove(os.path.join(two, "conventions.md"))
    conf_path = slash(os.path.join(two, ".council", "conventions.md"))
    if re.match(r"^[A-Za-z]:", conf_path):
        conf_path = "/" + conf_path[0].lower() + conf_path[2:]
    write(os.path.join(two, ".council", "council.config.md"), f"# c\n## Memory\n- conventions: {conf_path}\n")
    code, out, _ = council(two, "doctor")
    check("doctor: the same file named as /c/… is not 'a second memory file'",
          "a second memory file" not in out and "AP-1" not in out, out)
    spaced = os.path.join(tmp, "My Notes Project")
    os.makedirs(spaced)
    git(spaced, "init", "-q")
    git(spaced, "symbolic-ref", "HEAD", "refs/heads/main")
    write(os.path.join(spaced, "conventions.md"), "# m\n## Accepted Patterns\n### AP-1: one\n")
    write(os.path.join(spaced, ".council", "council.config.md"),
          f"# c\n## Memory\n- conventions: \"{slash(spaced)}/conventions.md\"\n")
    code, out, err = council(spaced, "memory")
    check("memory: a configured absolute path with a blank in it is read whole, not cut at the blank",
          code == 0 and "AP-1 · one" in out and "doesn't exist" not in err, out + err)

    # Close, and the legacy pointer
    write(os.path.join(run, "verify-1.md"), "# Verification — eval\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
          "| 1 | median | CONFIRMED | traced; the guard does not make it REFUTED |\n| 2 | old lines | REFUTED | guarded upstream |\n")
    write(os.path.join(repo, ".council", "active-run"), run2 + "\n")
    code, out, _ = council(repo, "run", "close", "--run", run2, "--status", "abandoned")
    check("run close: abandons a run", code == 0 and "abandoned" in out, out)
    check("run close: empties the old active-run pointer when it names the run", read(os.path.join(repo, ".council", "active-run")).strip() == "")
    code, out, _ = council(repo, "run", "close")
    st = read(os.path.join(run, "session-state.md"))
    check("run close: marks complete and stamps the actual cost — a re-dispatch is an agent run, a skipped seat is none, "
          "and a seat with no agent on record makes the figure a lower bound, never a zero",
          "status: complete" in st and "actual: at least ~86k tokens across at least 3 agent run(s) — 1 seat(s) with no agent on record" in st, st)
    final_events = events(run)
    code_ev, out_ev, err_ev = council(repo, "run", "events", "check", "--run", run)
    check("run events: seat updates and completion survive with a continuous sequence",
          code_ev == 0 and any(e[3] == "seat.updated" for e in final_events) and
          any(e[3] == "collect.finished" for e in final_events) and
          any(e[3] == "verification.finished" for e in final_events) and
          final_events[-1][3:6] == ["run.closed", "run", "complete"] and
          [int(e[1]) for e in final_events] == list(range(1, len(final_events) + 1)),
          out_ev + err_ev + str(final_events[-3:]))
    check("run close: prints the actual cost", "at least ~86k tokens across at least 3 agent run(s)" in out, out)
    ledger = read(os.path.join(repo, ".council", "ledger.tsv"))
    check("run close: records each seat in the ledger", "ledger: 3 seat row(s) recorded" in out
          and "\tcouncil-review\tfowler\t1\t1\t0\t0\t40000" in ledger and "\tbeck\t1\t1\t0\t1\t45500" in ledger
          and "\tgone\t0\t0\t1\t0\t-\t2" in ledger, out + ledger)
    code, out, _ = council(repo, "ledger")
    check("ledger: each seat's record — shipped means kept and not refuted",
          re.search(r"^fowler\s+1\s+1\s+1\s+0\s+0\s+40\s+100%", out, re.MULTILINE) is not None
          and re.search(r"^beck\s+1\s+1\s+1\s+0\s+1\s+46\s+0%", out, re.MULTILINE) is not None, out)
    with open(os.path.join(repo, ".council", "ledger.tsv"), "a", encoding="utf-8", newline="\n") as f:
        f.write("2026-09-16\t2026-09-16-000000-review\tcouncil-review\thunt-a\t2\t1\t0\t0\t10000\t2\n"
                "2026-09-16\t2026-09-16-000000-review\tcouncil-review\thunt-b\t2\t1\t0\t0\t20000\t2\n")
    code, out, _ = council(repo, "ledger")
    check("ledger: a split worker's rows count as one seat in one run", re.search(r"^hunt\s+1\s+4\s+2\s+0\s+0\s+30\s+50%", out, re.MULTILINE) is not None, out)

    # The ledger reads provenance and verdicts as they are really written
    led = new_repo(tmp, "led")
    write(os.path.join(led, ".council", "council.config.md"), "# Council config\n")
    write(os.path.join(led, ".council", ".gitignore"), "runs/\n")
    write(os.path.join(led, "a.py"), "".join(f"{i}\n" for i in range(1, 31)))
    git(led, "add", "-A")
    git(led, "commit", "-q", "-m", "a")
    _, lrun, _ = council(led, "run", "open", "council-review")
    lrun = lrun.strip()
    write(os.path.join(lrun, "brief.md"), "# Brief\n## Seats\n### hunt — Security\n- ref: none\n### beck — Tests\n- ref: none\n")
    write(os.path.join(lrun, "seats", "hunt.md"), "# Hunt — Security (council-review)\nref: none\n## Index\n"
          + "".join(f"{i} · P2 · P1 · a.py:{i} · h{i}\n" for i in range(1, 5))
          + "\n### 1. h1\nbody\n## Outside my lane\n5 · P2 · Tests · a.py:5 · no test for a.py\n")
    write(os.path.join(lrun, "seats", "beck.md"), "# Beck — Tests (council-review)\nref: none\n## Index\n"
          + "".join(f"{i} · P2 · T1 · a.py:{i + 5} · b{i}\n" for i in range(1, 4)))
    council(led, "seat", "hunt", "done", "agent=a1", "tokens=30000")
    council(led, "seat", "beck", "done", "agent=a2", "tokens=20000")
    write(os.path.join(lrun, "synthesis.md"), "# Synthesis\n## Kept\n"
          "1 · P2 · P1 · a.py:1 · h1 and h2 are one bug · from: hunt#1, #2\n"
          "2 · P2 · T1 · a.py:6 · b1 and b2 merged · from: beck#1,2\n"
          "3 · P2 · P1 · a.py:3 · h3, also raised by beck · from: hunt#3 and beck#3\n"
          "4 · P2 · P1 · a.py:4 · Data from: the webhook is trusted · from: hunt#4\n")
    write(os.path.join(lrun, "verify-1.md"), "# Verification — ledger\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
          "| 1. | h1 | REFUTED (latent) | guarded upstream |\n| #2 | b1 | REFUTED — test exists | covered |\n"
          "| 3 | h3 | ❌ REFUTED | guarded |\n| 4 | data | Refuted | signature checked |\n")
    council(led, "seat", "verify-1", "done", "agent=v1", "tokens=9000")      # a verifier is done only with its file
    council(led, "run", "close")
    code, out, _ = council(led, "ledger")
    check("ledger: 'from: a#1, #2', 'b#1,2', 'a#3 and b#3', a title holding 'from:', and verdicts as written all count",
          re.search(r"^hunt\s+1\s+4\s+4\s+0\s+4\s+30\s+0%", out, re.MULTILINE) is not None
          and re.search(r"^beck\s+1\s+3\s+3\s+0\s+3\s+20\s+0%", out, re.MULTILINE) is not None, out)

    # Provenance as models write it: "hunt #1" with a blank, "beck 1, 3", a slash between two seats,
    # a bracketed note that names another seat, and a "from:" introduced by a dash or a bracket. Each
    # item of a seat counts once, however often it is named — this is the number the owner reads as
    # "shipped", so counting a seat twice, or losing it, is the failure here.
    led2 = new_repo(tmp, "ledger2")
    write(os.path.join(led2, ".council", "council.config.md"), "# Council config\n")
    write(os.path.join(led2, ".council", ".gitignore"), "runs/\n")
    write(os.path.join(led2, "a.py"), "".join(f"{i}\n" for i in range(1, 31)))
    git(led2, "add", "-A")
    git(led2, "commit", "-q", "-m", "a")
    _, l2run, _ = council(led2, "run", "open", "council-review")
    l2run = l2run.strip()
    write(os.path.join(l2run, "brief.md"), "# Brief\n## Seats\n### hunt — Security\n- ref: none\n### beck — Tests\n- ref: none\n")
    write(os.path.join(l2run, "seats", "hunt.md"), "# Hunt — Security (council-review)\nref: none\n## Index\n"
          + "".join(f"{i} · P2 · P1 · a.py:{i} · h{i}\n" for i in range(1, 5)))
    write(os.path.join(l2run, "seats", "beck.md"), "# Beck — Tests (council-review)\nref: none\n## Index\n"
          + "".join(f"{i} · P2 · T1 · a.py:{i + 5} · b{i}\n" for i in range(1, 5)))
    council(led2, "seat", "hunt", "done", "agent=a1", "tokens=30000")
    council(led2, "seat", "beck", "done", "agent=a2", "tokens=20000")
    write(os.path.join(l2run, "synthesis.md"), "# Synthesis\n## Kept\n"
          "1 · P2 · P1 · a.py:1 · a blank before the number · from: hunt #1\n"
          "2 · P2 · P1 · a.py:2 · a bracketed note names a seat · from: beck#2 (merged with hunt#2)\n"
          "3 · P2 · P1 · a.py:3 · bare numbers after the seat · from: beck 1, 3\n"
          "4 · P2 · P1 · a.py:4 · a slash between seats · from: hunt#4/beck#4\n"
          "5 · P2 · P1 · a.py:5 · an em dash before from — from: hunt#3\n"
          "6 · P2 · P1 · a.py:6 · a bracketed from · (from: hunt#1)\n")
    council(led2, "run", "close")
    code, out, _ = council(led2, "ledger")
    check("ledger: 'hunt #1', 'beck 1, 3', 'a#4/b#4', '(merged with hunt#2)' and '— from:' all count, each item once",
          re.search(r"^hunt\s+1\s+4\s+4\s+0\s+0\s+30\s+100%", out, re.MULTILINE) is not None
          and re.search(r"^beck\s+1\s+4\s+4\s+0\s+0\s+20\s+100%", out, re.MULTILINE) is not None, out)
    code, out, _ = council(repo, "run", "status")
    check("run status: nothing open after closing", "no open council runs" in out, out)
    code, out, _ = council(repo, "run", "status", "--all")
    check("run status --all: shows closed runs with their cost", "complete" in out and "~86k tokens" in out, out)
    closed_state = read(os.path.join(run, "session-state.md"))
    code, _, err = council(repo, "run", "close", "--run", run, "--status", "finished")
    check("run close: rejects an unknown status, and leaves the run as it was",
          code == 2 and "--status must be" in err and read(os.path.join(run, "session-state.md")) == closed_state, err)

    # --flag=value works for every flag, the same as --flag value
    flags = new_repo(tmp, "flags")
    write(os.path.join(flags, "a.py"), "a = 1\n")
    write(os.path.join(flags, ".council", "council.config.md"), "# Council config — flags\n")
    git(flags, "add", "-A")
    git(flags, "commit", "-q", "-m", "init")
    write(os.path.join(flags, "m.py"), "def f():\n    return 1\n")
    git(flags, "add", "-A")
    git(flags, "commit", "-q", "-m", "work")
    code, frun, _ = council(flags, "run", "open", "council-review")
    code, out, err = council(flags, "run", "close", "--status=paused")
    check("run close --status=paused: pauses the run, as --status paused does",
          code == 0 and "status: paused" in read(os.path.join(frun.strip(), "session-state.md")), out + err)
    code, frun, _ = council(flags, "run", "open", "council-postgame")
    code, out, err = council(flags, "index", "--base=HEAD~1")
    check("index --base=<ref>: diffs against that ref, as --base <ref> does", code == 0 and "index: 1 files" in out, out + err)
    council(flags, "run", "close", "--run=" + frun.strip(), "--status=abandoned")
    check("run close --run=<folder> --status=abandoned: both = forms are read",
          "status: abandoned" in read(os.path.join(frun.strip(), "session-state.md")))

    # An old open run behind many newer closed ones
    runs_dir = os.path.join(repo, ".council", "runs")
    write(os.path.join(runs_dir, "2020-01-01-000000-review", "session-state.md"),
          f"status: in-progress\nmode: council-review\nphase: work\nupdated: 2020-01-01 00:00\ncode-root: {top}\n")
    for i in range(25):
        write(os.path.join(runs_dir, f"2026-01-01-0000{i:02d}-plan", "session-state.md"), "status: complete\nmode: council-plan\n")
    code, out, _ = council(repo, "run", "status")
    check("run status: finds an old open run behind many newer closed ones", "2020-01-01-000000-review" in out, out)
    code, out, _ = council(repo, "run", "close", "--run", "2020-01-01-000000-review", "--status", "abandoned")
    check("run close: takes a bare folder name", code == 0 and "abandoned" in out, out)

    # Many open runs in other working trees never hide this tree's run
    crowd = new_repo(tmp, "crowd")
    write(os.path.join(crowd, ".council", "council.config.md"), "# Council config — crowd\n")
    ctop = slash(git(crowd, "rev-parse", "--show-toplevel"))
    cruns = os.path.join(crowd, ".council", "runs")
    write(os.path.join(cruns, "2026-01-01-000000-review", "session-state.md"),
          f"status: in-progress\nmode: council-review\nphase: work\nupdated: 2026-01-01 00:00\ncode-root: {ctop}\n")
    for i in range(55):
        write(os.path.join(cruns, f"2026-09-17-1{i:05d}-plan", "session-state.md"),
              f"status: in-progress\nmode: council-plan\nphase: work\nupdated: 2026-09-17 10:00\ncode-root: C:/p/.claude/worktrees/w{i}\n")
    code, out, err = council(crowd, "state")
    check("state: finds this tree's run behind 55 newer open runs from other working trees", code == 0 and "mode: council-review" in out, out + err)
    code, out, err = council(crowd, "run", "open", "council-review")
    check("run open: behind 55 other trees' runs, still refuses a second run on this tree", code == 2 and "already in progress" in err, out + err)
    code, out, _ = council(crowd, "run", "status")
    check("run status: lists this tree's run first, however many other trees' runs are open",
          out.startswith("2026-01-01-000000-review · council-review") and "more" in out.strip().splitlines()[-1], out)

    # A byte-order mark at the top of session-state.md (PowerShell's utf8)
    bom = new_repo(tmp, "bom")
    write(os.path.join(bom, ".council", "council.config.md"), "# Council config — bom\n")
    code, bomrun, _ = council(bom, "run", "open", "council-review")
    bomrun = bomrun.strip()
    write_plan(bomrun)
    bom_state = os.path.join(bomrun.strip(), "session-state.md")
    body = read(bom_state)
    with open(bom_state, "w", encoding="utf-8-sig", newline="\n") as f:
        f.write(body)
    code, out, _ = council(bom, "run", "status")
    check("run status: a byte-order mark at the top of session-state.md doesn't hide the run", os.path.basename(bomrun.strip()) in out, out)
    code, out, err = council(bom, "run", "open", "council-plan")
    check("run open: a byte-order mark doesn't let a second run open on this tree", code == 2 and "already in progress" in err, out + err)
    code, out, err = council(bom, "state", "phase=judge", "status=paused")
    body = read(bom_state)
    check("state: updates a state file that starts with a byte-order mark, in place",
          code == 0 and "phase judge · paused" in out and os.path.basename(bomrun.strip()) in out
          and not body.startswith("﻿") and body.count("status:") == 1 and "status: paused" in body,
          out + err + body)

    # --run as a Windows path (backslashes, a trailing one) names the same run as its folder name
    wp = new_repo(tmp, "winpath")
    write(os.path.join(wp, ".council", "council.config.md"), "# Council config — winpath\n")
    code, wrun, _ = council(wp, "run", "open", "council-init")
    wname = os.path.basename(wrun.strip())
    council(wp, "seat", "engine", "done", "agent=a1", "tokens=74304")
    code, out, err = council(wp, "run", "close", "--run", wrun.strip().replace("/", "\\") + "\\")
    council(wp, "run", "close", "--run", wname)
    wrows = [x for x in read(os.path.join(wp, ".council", "ledger.tsv")).splitlines()[1:] if x]
    check("run close --run with backslashes: one ledger row, dated and named by the run's folder",
          code == 0 and out.startswith(f"closed {wname} ") and len(wrows) == 1 and wrows[0].startswith(f"{wname[:10]}\t{wname}\t"),
          out + err + "\n".join(wrows))

    # A repo with no council yet; paused runs
    fresh = new_repo(tmp, "fresh")
    write(os.path.join(fresh, "app.txt"), "v1\n")
    git(fresh, "add", "-A")
    git(fresh, "commit", "-q", "-m", "init")
    code, _, err = council(fresh, "run", "open", "council-review")
    check("run open: a mode other than init needs a council home", code == 2 and "council-init first" in err, err)
    code, init_run, err = council(fresh, "run", "open", "council-init")
    init_run = init_run.strip()
    check("run open council-init: creates the council home and its .gitignore (runs/ and asks/)",
          code == 0 and os.path.isdir(init_run)
          and {"runs/", "asks/"} <= set(read(os.path.join(fresh, ".council", ".gitignore")).split()), init_run + err)
    code, out, _ = council(fresh, "gate", "--all")
    check("gate --all: a project with no configured check says NOTHING WAS CHECKED and exits 4",
          code == 4 and "NOTHING WAS CHECKED" in out and "no automated check" in out, out)
    council(fresh, "state", "status=paused")
    code, plan_run, err = council(fresh, "run", "open", "council-plan", "--session=explicit")
    plan_run = plan_run.strip()
    check("run open: a paused run doesn't block a new one", code == 0 and "paused run is also open" in err, plan_run + err)
    check("run open --session: records the given id", "session: explicit" in read(os.path.join(plan_run, "session-state.md")))
    code, out, _ = council(fresh, "state")
    check("state: acts on the in-progress run, never the paused one", code == 0 and "mode: council-plan" in out, out)
    council(fresh, "run", "close")
    code, _, err = council(fresh, "state")
    check("state: with only a paused run left, asks for --run", code == 2 and "paused" in err and "--run" in err, err)

@part("runs")
def runs_init_plan(tmp):
    """A setup run opens with a plan that fits setup; doctor judges only open runs' plans."""
    ip = new_repo(tmp, "initplan")
    write(os.path.join(ip, "a.py"), "x = 1\n")
    git(ip, "add", "-A")
    git(ip, "commit", "-q", "-m", "init")
    _, irun, _ = council(ip, "run", "open", "council-init")
    irun = irun.strip()
    code, out, err = council(ip, "run", "plan", "check")
    check("run open council-init: its plan is valid as it opens — solo, the Chair only, self-verified",
          code == 0 and "plan: valid · solo · 1 selected, 0 skipped · 0 agent run(s)" in out, out + err)
    plan = read(os.path.join(irun, "run-plan.tsv"))
    rows = {tuple(x.split("\t")[:3]): x.split("\t") for x in plan.splitlines() if x and not x.startswith("#")}
    chosen = [("run", "run", "size"), ("assessment", "run", "risk"), ("assessment", "run", "complexity"),
              ("assessment", "run", "uncertainty"), ("budget", "run", "estimated-tokens"), ("verification", "run", "level")]
    check("run open council-init: every value the helper chose says in its reason that it is setup's default",
          all(len(rows.get(k, [])) == 5 and rows[k][4].startswith("setup default:") for k in chosen)
          and rows.get(("run", "run", "id"), ["", "", "", ""])[3] == os.path.basename(irun), plan)
    st = read(os.path.join(irun, "session-state.md"))
    check("run open council-init: its next step is setup's, not Convene's",
          "next: follow council-init" in st and "size the run and ask" not in st, st)
    # A large repo's mapping squad, as council-init Phase D says: the worker rows at the plan's foot
    mapping = [x[2:].replace("<area>", "src").replace("<the area's paths>", "src/**")
               for x in plan.splitlines() if x.startswith("# ") and "\tmap-<area>\t" in x]
    squad = re.sub(r"^run\trun\tsize\tsolo\t.*$", "run\trun\tsize\tsquad\ta large repo: one mapping worker per area",
                   plan, flags=re.MULTILINE).replace("\testimated-tokens\t0\t", "\testimated-tokens\t80000\t")
    write(os.path.join(irun, "run-plan.tsv"), squad + "\n".join(mapping) + "\n")
    code, out, err = council(ip, "run", "plan", "check")
    check("council-init plan: the mapping rows at its foot make a valid squad",
          code == 0 and "squad · 2 selected" in out, out + err + "\n".join(mapping))
    code, out, err = council(ip, "seat", "map-src", "running", "agent=a1")
    code2, out2, err2 = council(ip, "state", "phase=work")
    check("council-init: a mapping worker is recorded and the run moves on, with no plan error",
          code == 0 and code2 == 0 and "ERROR" not in out + err + out2 + err2, out + err + out2 + err2)
    council(ip, "seat", "map-src", "done", "agent=a1", "tokens=30000")
    council(ip, "run", "close")

    # Doctor judges only open runs' plans: a closed run's plan is the record of what was decided then
    write(os.path.join(ip, ".council", "council.config.md"), "# Council config — initplan\n\n## Run preferences\n- agent cap: 10\n")
    _, done, _ = council(ip, "run", "open", "council-review")
    done = done.strip()
    write_plan(done, selected=("hunt", "beck"))
    council(ip, "state", "phase=learn")
    council(ip, "run", "close")
    _, left, _ = council(ip, "run", "open", "council-review")
    left = left.strip()
    council(ip, "run", "close", "--status", "abandoned")
    write(os.path.join(ip, ".council", "council.config.md"), "# Council config — initplan\n\n## Run preferences\n- agent cap: 2\n")
    _, live, _ = council(ip, "run", "open", "council-review")
    live = live.strip()
    write_plan(live, selected=("hunt", "beck"))
    write(os.path.join(live, "session-state.md"), read(os.path.join(live, "session-state.md")).replace("phase: convene", "phase: work"))
    code, out, _ = council(ip, "doctor")
    named = [os.path.basename(r) for r in (irun, done, left) if os.path.basename(r) in out]
    check("doctor: never judges a closed run's plan — setup's, an unfinished abandoned one, or one made under a higher agent cap",
          not named, out)
    check("doctor: an open run's plan past Assign is still checked against today's agent cap",
          f"run {os.path.basename(live)} has an invalid run plan" in out, out)

@part("gates")
def resume(tmp):
    # Carrying on with a run: council run resume
    rs = new_repo(tmp, "resume")
    write(os.path.join(rs, ".council", "council.config.md"), "# Council config — resume\n")
    code, rrun, _ = council(rs, "run", "open", "council-review", env={"CLAUDE_CODE_SESSION_ID": "sess-old"})
    rrun = rrun.strip()
    write_plan(rrun, selected=("hunt", "beck"))
    rname, rstate = os.path.basename(rrun), os.path.join(rrun, "session-state.md")
    council(rs, "seat", "hunt", "running", "agent=a1")
    council(rs, "run", "close", "--status", "paused")
    code, _, err = council(rs, "state")
    check("state: with only a paused run left, the error names council run resume",
          code == 2 and f"council run resume --run {rname}" in err, err)
    council(rs, "state", "--run", rname, "phase=collect", env={"CLAUDE_CODE_SESSION_ID": "sess-new"})
    council(rs, "seat", "--run", rname, "beck", "done", env={"CLAUDE_CODE_SESSION_ID": "sess-new"})
    check("state and seat never take a run over from the session that drives it", "session: sess-old" in read(rstate), read(rstate))
    code, out, err = council(rs, "run", "resume", env={"CLAUDE_CODE_SESSION_ID": "sess-new"})
    st = read(rstate)
    check("run resume: the one open run (paused) is in progress again, driven by this session, its closed: stamp gone",
          code == 0 and rname in out and "status: in-progress" in st and "session: sess-new" in st and "closed:" not in st, out + err + st)
    check("run resume: names the session that drove it and the seats still marked running",
          "sess-old" in out + err and "still working: hunt" in out, out + err)
    code, out, err = council(rs, "state", "phase=judge")
    check("run resume: plain commands act on the run again", code == 0 and "phase judge · in-progress" in out, out + err)
    council(rs, "run", "close")
    code, _, err = council(rs, "run", "resume", "--run", rname)
    check("run resume: a completed run is refused, with the way forward", code == 2 and "complete" in err and "council run open" in err, err)
    code, _, err = council(rs, "run", "resume")
    check("run resume: with no open run here, says so", code == 2 and "no open run" in err, err)
    code, p1, _ = council(rs, "run", "open", "council-plan")
    council(rs, "run", "close", "--status", "paused")
    code, p2, _ = council(rs, "run", "open", "council-research")
    council(rs, "run", "close", "--status", "paused")
    code, _, err = council(rs, "run", "resume")
    check("run resume: with several open runs, asks which (--run), never guesses", code == 2 and "several" in err and "--run" in err, err)
    code, out, err = council(rs, "run", "resume", "--run", os.path.basename(p1.strip()))
    check("run resume --run: resumes the named run only",
          code == 0 and "status: in-progress" in read(os.path.join(p1.strip(), "session-state.md"))
          and "status: paused" in read(os.path.join(p2.strip(), "session-state.md")), out + err)
    # From a linked worktree, the run's usual relative path (.council/runs/<name>, written from the main
    # checkout) names the same run: the worktree's council home is the main checkout's.
    write(os.path.join(rs, "a.txt"), "x\n")
    git(rs, "add", "a.txt")
    git(rs, "commit", "-q", "-m", "init")
    rwt = os.path.join(tmp, "resume-wt")
    git(rs, "worktree", "add", "-q", "-b", "resume-wt", rwt)
    council(rs, "run", "close", "--run", os.path.basename(p1.strip()), "--status", "paused")
    p2name = os.path.basename(p2.strip())
    code, out, err = council(rwt, "run", "resume", "--run", ".council/runs/" + p2name)
    check("run resume --run .council/runs/<name>: works from a linked worktree too",
          code == 0 and f"resumed {p2name}" in out and "status: in-progress" in read(os.path.join(p2.strip(), "session-state.md")),
          out + err)
    code, out, err = council(rwt, "state", "--run", ".council\\runs\\" + os.path.basename(p1.strip()) + "\\")
    check("--run .council\\runs\\<name>\\ (backslashes) from a linked worktree names the same run",
          code == 0 and "mode: council-plan" in out, out + err)
    code, _, err = council(rwt, "state", "--run", ".council/runs/2020-01-01-000000-review")
    check("--run: a relative path that names no run is still refused", code == 2 and "not a run folder" in err, err)

@part("runs")
def runs_fingerprint_and_ledger(tmp):
    # The stack fingerprint
    code, out, _ = council(fresh, "fingerprint")
    fp = out.strip()
    check("fingerprint: prints a hash and what it's made of",
          re.match(r"^stack-fingerprint: [0-9a-f]{12} — manifests: none · languages: none$", fp) is not None, fp)
    write(os.path.join(fresh, ".council", "council.config.md"),
          "# Council config — fresh\nlast-verified: 2026-09-15 @ x\n" + fp + "\n\n## Gates\n"
          "| Gate | Command | Run at | Mandatory | Checked |\n|---|---|---|---|---|\n| t | `true` | verify | yes | ok |\n")
    code, out, _ = council(fresh, "fingerprint", "check")
    check("fingerprint check: an unchanged stack passes", code == 0 and "unchanged" in out, out)
    write(os.path.join(fresh, "go.mod"), "module x\n")
    for name in ("a", "b", "c"):
        write(os.path.join(fresh, "cmd", f"{name}.go"), "package main\n")
    git(fresh, "add", "-A")
    git(fresh, "commit", "-q", "-m", "go")
    code, out, _ = council(fresh, "fingerprint", "check")
    check("fingerprint check: a new language or build file is a changed stack", code == 1 and "added: go.mod, go" in out, out)
    code, out, _ = council(fresh, "doctor")
    check("doctor: notices a changed stack", "the stack changed since council-init" in out, out)
    check("doctor: flags an older Gates table without side effects", "no Side effects column" in out, out)
    write(os.path.join(fresh, "Makefile"), "all:\n")
    git(fresh, "add", "-A")
    git(fresh, "commit", "-q", "-m", "make")
    _, fp_top, _ = council(fresh, "fingerprint")
    _, fp_sub, _ = council(os.path.join(fresh, "cmd"), "fingerprint")
    other_locale = next((loc for loc in ("en_US.UTF-8", "en_GB.UTF-8", "C.UTF-8")
                         if subprocess.run([BASH, "-c", "printf 'B\\na\\n' | sort"], capture_output=True, text=True,
                                           env=dict(GIT_ENV, LC_ALL=loc)).stdout == "a\nB\n"), "")
    _, fp_loc, _ = council(fresh, "fingerprint", env={"LC_ALL": other_locale or "C"})
    check("fingerprint: the same from a subfolder and under another locale"
          + ("" if other_locale else " (no second locale here: only the subfolder is proved)"),
          fp_top == fp_sub == fp_loc and "Makefile, go.mod" in fp_top, fp_top + fp_sub + fp_loc)

    # The ledger belongs to the run's council home, wherever the close runs from
    code, r4, _ = council(fresh, "run", "open", "council-review")
    r4 = r4.strip()
    council(fresh, "seat", "hunt", "done", "tokens=1000", "--run", r4)
    code, out, err = council(plain, "run", "close", "--run", r4)
    check("run close from another folder: the ledger goes to the run's own council home",
          "\thunt\t" in read(os.path.join(fresh, ".council", "ledger.tsv"))
          and not os.path.exists(os.path.join(plain, ".council", "ledger.tsv")) and "ledger: 1 seat row" in out, out + err)

@part("requests")
def requests_and_proofs(tmp):
    global req, asks, filed   # later "requests" blocks carry on with these
    # 0.6 — the user's request word for word, a war room's round 2, the post-game
    req = new_repo(tmp, "req")
    write(os.path.join(req, "a.txt"), "one\ntwo\n")
    git(req, "add", "-A")
    git(req, "commit", "-q", "-m", "a")
    write(os.path.join(req, ".council", "council.config.md"), "# Council config\n## Memory\n- conventions: .council/conventions.md\n")
    write(os.path.join(req, ".council", "conventions.md"), "# Conventions\n## Enforced Conventions (EC)\n"
          "### EC-1: plans that touch migrations get a rollback task\n**Rule:** always · **Why:** x\n**Scope:** council-plan\n")
    code, prun, err = council(req, "run", "open", "council-plan")
    prun = prun.strip()
    check("run open: stdout is the folder alone; the request reminder goes to stderr",
          code == 0 and os.path.isdir(prun) and "ask.md before anything else" in err, prun + err)
    code, _, err = council(req, "ask", "save")
    check("ask save: refuses without an ask.md", code == 2 and "no ask.md" in err, err)
    write(os.path.join(prun, "ask.md"), "# Ask — Empty\nsource: said at the time\n## In your words\n\n## Later, in your words\n")
    code, _, err = council(req, "ask", "save")
    check("ask save: refuses an ask.md with no words", code == 2 and "no words" in err, err)
    words = ("We need CSV export,  filterable by `date` and $OWNER — \"admins\" only.  \n"
             "Key: sk-abcdefghijklmnopqrstuvwx · token=ghp_abcdefghijklmnopqrstuvwxyz1234 · café\n")
    ask_text = ("# Ask — CSV export for Reports!\nsource: said at the time\n## In your words\n" + words
                + "## Later, in your words\n").replace("\n", "\r\n")
    with open(os.path.join(prun, "ask.md"), "w", encoding="utf-8", newline="") as f:
        f.write(ask_text)
    code, out, err = council(req, "ask", "save")
    asks = os.path.join(req, ".council", "asks")
    filed = sorted(os.listdir(asks)) if os.path.isdir(asks) else ["?"]
    with open(os.path.join(asks, filed[0]), encoding="utf-8", newline="") as f:
        body = f.read() if filed[0] != "?" else ""
    check("ask save: files a new request as asks/<date>-<slug>.md",
          code == 0 and len(filed) == 1 and filed[0].endswith("-csv-export-for-reports.md") and "(new)" in out, out + err)
    check("ask save: run and mode follow line 1; the rest stays as written (CRLF, backticks, $, quotes, UTF-8)",
          body.startswith("# Ask — CSV export for Reports!\r\nrun: ") and "\nmode: council-plan\n" in body
          and "filterable by `date` and $OWNER — \"admins\" only.  \r\n" in body and "café" in body, repr(body[:400]))
    check("ask save: redacts secret-looking strings and says so",
          "sk-abc" not in body and "ghp_" not in body and body.count("[redacted]") == 2 and "redacted 2" in out, out + repr(body))
    check("ask save: records ask= in the state", f"ask: .council/asks/{filed[0]}" in read(os.path.join(prun, "session-state.md")))
    code, out, _ = council(req, "memory", "select")
    check("memory select: a lesson scoped to a mode applies in that mode's runs", "EC-1" in out, out)
    council(req, "run", "close")
    code, prun2, _ = council(req, "run", "open", "council-plan")
    with open(os.path.join(prun2.strip(), "ask.md"), "w", encoding="utf-8", newline="") as f:
        f.write(ask_text)
    code, out, _ = council(req, "ask", "save")
    check("ask save: the same name on the same day gets -2", "-csv-export-for-reports-2.md (new)" in out, out)
    gi = read(os.path.join(req, ".council", ".gitignore"))
    check("ask save: the requests stay out of git — asks/ is added to .council/.gitignore, once",
          [l.strip() for l in gi.splitlines()].count("asks/") == 1 and "runs/" in gi.split(), gi)
    council(req, "run", "close")
    code, irun, _ = council(req, "run", "open", "council-implement")
    irun = irun.strip()
    write_plan(irun, selected=("leach",))
    council(req, "state", f"ask=.council/asks/{filed[0]}")
    code, out, _ = council(req, "memory", "select")
    check("memory select: ... and not in another mode's runs", code == 0 and "EC-1" not in out and "memory: 0 scoped" in out, out)
    write(os.path.join(irun, "ask.md"), "# Ask — build it\nsource: said at the time\n## In your words\n(no new words)\n## Later, in your words\n")
    before = read(os.path.join(asks, filed[0]))
    code, out, _ = council(req, "ask", "save")
    check("ask save: a continuing request with no new words appends nothing",
          "(no new words)" in out and read(os.path.join(asks, filed[0])) == before, out)
    write(os.path.join(irun, "ask.md"), "# Ask — build it\n## In your words\nAlso add a PDF option.\n"
          "## Later, in your words\n- 2026-09-15: \"drop the owner filter\"\n")
    code, out, _ = council(req, "ask", "save")
    after = read(os.path.join(asks, filed[0]))
    check("ask save: a continuing request appends its new words under a dated heading",
          "(continued)" in out and after.startswith(before) and "— council-implement, run " in after
          and "Also add a PDF option." in after and "drop the owner filter" in after, out + after)
    with open(os.path.join(irun, "ask.md"), "w", encoding="utf-8", newline="") as f:
        f.write("# Ask — more\r\n## In your words\r\nAlso export XLSX.\r\n## Later, in your words\r\n")
    council(req, "ask", "save")
    with open(os.path.join(asks, filed[0]), "rb") as f:
        raw = f.read()
    check("ask save: a continuing request keeps its words' CRLF endings", b"Also export XLSX.\r\n" in raw, repr(raw[-120:]))
    council(req, "state", "ask=.council/asks/missing.md")
    code, _, err = council(req, "ask", "save")
    check("ask save: a continued request that has gone missing is an error", code == 2 and "missing" in err, err)
    council(req, "state", f"ask=.council/asks/{filed[0]}")

    write(os.path.join(irun, "brief.md"), "# Brief\n## Seats\n### leach — Data (Leach)\n- ref: none\n- out: seats/leach.md\n")
    write(os.path.join(irun, "seats", "leach.md"), "# Leach — Data (council-plan)\nref: none\n## Index\n1 · must · Principle 1 · a.txt:1 · x\n")
    write(os.path.join(irun, "debate.md"), "# War room — x · round 2\n## Points\n### P1. one table or two?\n"
          "## Seats\n### leach-r2 — Data (Leach), round 2\n- ref: none\n- out: seats/leach-r2.md\n- cap: 6\n")
    council(req, "seat", "leach", "running", "agent=w1")
    council(req, "seat", "leach", "done", "tokens=20000")
    code, out, _ = council(req, "collect")
    check("collect: reads a war room's round-2 seat from debate.md", code == 1 and re.search(r"^leach-r2\s+missing", out, re.MULTILINE) is not None, out)
    write(os.path.join(irun, "seats", "leach-r2.md"), "# Leach — Data (council-plan, round 2)\nref: none\nquestion: q\n"
          "## Index\n1 · hold · P1 fowler#4 · a.txt:2 · one table\n")
    council(req, "seat", "leach", "running", "agent=w1", "note=round 2")
    code, out, _ = council(req, "collect")
    check("collect: a round-2 row follows its round-1 seat's worker", "state:running" in row(out, "leach-r2"), out)
    council(req, "seat", "leach", "failed", "note=interrupted")
    code, out, _ = council(req, "collect")
    check("collect: a worker lost in round 2 flags the round-2 row, not the round-1 file that is done",
          code == 1 and "state:failed" in row(out, "leach-r2") and "state:" not in row(out, "leach"), out)
    check("collect: ... and says to start a fresh round-2 worker, not to re-run round 1",
          "leach-r2 lost round 2" in out and "council seat <slug>-r2 running" in out, out)
    council(req, "seat", "leach", "running", "note=round 2")
    code, out, _ = council(req, "seat", "leach", "done", "tokens=6000")
    check("seat: a resumed worker adds tokens, not agents", "seats: 1 of 1 done" in out and "~26k tokens so far" in out, out)
    code, out, _ = council(req, "collect")
    check("collect: both rounds in order", code == 0 and "all 2 seats in order" in out, out)

    write(os.path.join(irun, "ask.md"), "# Ask — more\n## In your words\nAlso email the export every Monday morning.\n")
    write(os.path.join(irun, "synthesis.md"), "# Synthesis\n## Kept\n"
          '1 · must · ask · reports · export · quote: "CSV export,  filterable by `date`"\n'
          '2 · must · ask · reports · email · quote: “Also email the export every Monday morning.”\n'
          '3 · must · ask · reports · team · quote: "filterable by team"\n'
          '4 · must · ask · reports · none\n'
          '5 · must · ask · reports · short · Quote: "port"\n')
    code, out, _ = council(req, "check")
    check("check: a quote found only in the filed request passes (whitespace collapsed)", "synthesis#1  quote  ok" in out, out)
    check("check: a quote found only in this run's ask.md passes — curly quotes too", "synthesis#2  quote  ok" in out, out)
    check("check: a paraphrased quote fails", code == 1 and "synthesis#3  quote  NOT-IN-THE-REQUEST" in out, out)
    check("check: a request part with no quote, or a one-word one, is broken",
          "synthesis#4  quote  NO-QUOTE" in out and "synthesis#5  quote  TOO-SHORT" in out
          and "2 of 5 quotes found in the request" in out, out)
    qrepo = new_repo(tmp, "quotes")
    write(os.path.join(qrepo, "x.txt"), "x\n")
    git(qrepo, "add", "-A")
    git(qrepo, "commit", "-q", "-m", "x")
    code, qrun, _ = council(qrepo, "run", "open", "council-postgame")
    qrun = qrun.strip()
    fake_key = "sk" + "_live_" + "NOTREAL" * 4          # assembled here, so no key-shaped string sits in the file
    write(os.path.join(qrun, "ask.md"), "# Ask — panel\nsource: said at the time\n## In your words\n"
          "The quote panel shouldn’t freeze when the feed drops.\n"
          "Show the last price in **bold** and keep the 5 minute chart.\nit must never place orders.\n"
          f"Wire checkout with the key {fake_key} and email a receipt.\n"
          "Keep `npm test` green and the 5 minute chart​ visible.\n")
    write(os.path.join(qrun, "synthesis.md"), "# Synthesis\n## Kept\n"
          '1 · must · ask · panel · no freeze · quote: "The quote panel shouldn\'t freeze when the feed drops."\n'
          '2 · must · ask · panel · bold · quote: "Show the last price in **bold** and keep the 5 minute chart."\n'
          '3 · must · ask · panel · bold · quote: "Show the last price in bold and keep"\n'
          '4 · must · ask · orders · never · quote: "It must never place orders."\n'
          '5 · must · ask · panel · Quote: stays live · quote: "shouldn’t freeze when the feed"\n'
          '6 · must · Ask · orders · may trade · quote: "the app may place orders on its own"\n'
          '7 · should · asks · orders · a mistyped part · quote: "never place orders"\n'
          f'8 · must · ask · payments · the key · quote: "Wire checkout with the key {fake_key}"\n'
          '9 · must · ask · payments · redacted · quote: "Wire checkout with the key [redacted] and email"\n'
          '10 · must · ask · orders · an em dash before quote — quote: "must never place orders"\n'
          '11 · must · ask · orders · a bracketed quote (quote: "must never place orders")\n'
          '12 · must · ask · orders · no blank after the mark ·quote: "must never place orders"\n'
          '13 · must · ask · panel · a zero-width space in the request · quote: "the 5 minute chart visible"\n'
          '14 · must · ask · panel · backticks dropped · quote: "Keep npm test green"\n')
    code, out, _ = council(qrepo, "check")
    check("check: a quote that differs only by a curly apostrophe or a non-breaking space passes",
          "synthesis#1  quote  ok" in out and "synthesis#2  quote  ok" in out, out)
    check("check: a quote that differs only in capitals or ** marks says exactly that",
          "synthesis#3  quote  NOT-EXACT" in out and "synthesis#4  quote  NOT-EXACT" in out, out)
    check("check: 'Quote:' in a title never hides the part's quote", "synthesis#5  quote  ok" in out, out)
    check("check: in a post-game, a part whose third field isn't exactly 'ask' is still checked",
          "synthesis#6  quote  NOT-IN-THE-REQUEST" in out and "synthesis#7  quote  ok" in out, out)
    check("check: a quote holding a secret-looking string fails; the redacted words pass",
          code == 1 and "synthesis#8  quote  SECRET" in out and "synthesis#9  quote  ok" in out, out)
    check("check: a quote introduced by an em dash, a bracket or no blank at all is still found",
          all(f"synthesis#{i}  quote  ok" in out for i in (10, 11, 12)), out)
    check("check: an invisible character in the request is not a paraphrase; dropped backticks are named",
          "synthesis#13  quote  ok" in out and "synthesis#14  quote  NOT-EXACT" in out
          and "9 of 14 quotes found in the request" in out, out)
    council(qrepo, "run", "close", "--status", "abandoned")
    code, out, err = council(req, "run", "close")
    check("run close: no warning when the request was filed", code == 0 and "no request was filed" not in err, err)
    council(req, "run", "open", "council-review")
    code, out, err = council(req, "run", "close")
    check("run close: warns when a completed review filed no request", code == 0 and "no request was filed" in err, err)

    # A build's own proof: the before-check really failed, the after-check really passed, and the
    # test that proves it is saved in the project rather than thrown away with the run folder.
    write(os.path.join(req, "tests", "test_x.py"), "def test_gap():\n    assert True\n")
    git(req, "add", "-A")
    git(req, "commit", "-q", "-m", "a test")
    code, brun, _ = council(req, "run", "open", "council-implement")
    brun = brun.strip()

    def verdict_json(name, cmd, code_):
        write(os.path.join(brun, "gates", name + ".json"),
              '{"gate": "%s", "command": "%s", "exit": %d, "seconds": 1, "when": "2026-09-16 10:00:00"}\n'
              % (name, cmd, code_))

    verdict_json("before-1", "pytest tests/test_x.py::test_gap", 1)
    verdict_json("after-1", "pytest tests/test_x.py::test_gap", 0)
    verdict_json("before-2", 'npm test -- -t \\"expired token\\"', 1)
    verdict_json("after-2", 'npm test -- -t \\"expired token\\"', 0)
    verdict_json("before-3", "echo fine", 0)
    verdict_json("after-3", "echo fine", 0)
    verdict_json("before-4", "pytest tests/test_gone.py", 1)
    verdict_json("after-4", "pytest tests/test_gone.py", 2)
    verdict_json("before-5", "pytest tests/test_gone.py", 1)
    write(os.path.join(req, "src", "app.py"), "print('hi')\n")
    git(req, "add", "-A")
    git(req, "commit", "-q", "-m", "an app file")
    verdict_json("before-6", "python src/app.py --check", 1)
    verdict_json("after-6", "python src/app.py --check", 0)
    write(os.path.join(req, "tests", "test_fresh.py"), "def test_fresh():\n    assert True\n")   # written, not staged
    verdict_json("before-7", "pytest tests/test_fresh.py", 1)
    verdict_json("after-7", "pytest tests/test_fresh.py", 0)
    verdict_json("before-8", "pytest tests/test_x.py", 1)
    verdict_json("after-8", "true", 0)
    verdict_json("after-9", "pytest tests/test_x.py", 0)
    write(os.path.join(req, "tests", "pytest.ini"), "[pytest]\n")
    git(req, "add", "-A")
    git(req, "commit", "-q", "-m", "a config file")
    verdict_json("before-10", "grep -q marker tests/pytest.ini", 1)
    verdict_json("after-10", "grep -q marker tests/pytest.ini", 0)
    verdict_json("before-11", "pytest -c tests/pytest.ini tests/test_x.py", 1)
    verdict_json("after-11", "pytest -c tests/pytest.ini tests/test_x.py", 0)
    code, out, _ = council(req, "check")
    check("check: a fix whose before-check failed and after-check passed is proved, and names the saved test",
          "task 1  proof  ok \u00b7 test saved: tests/test_x.py" in out, out)
    check("check: a proof whose command names no tracked file under-claims rather than lying",
          "task 2  proof  ok \u00b7 couldn't confirm a saved test" in out, out)
    check("check: a before-check that never failed is broken proof",
          code == 1 and "task 3  proof  BEFORE-PASSED" in out, out)
    check("check: an after-check that still fails, and a missing after-check, are both broken",
          "task 4  proof  AFTER-FAILED" in out and "task 5  proof  NO-AFTER" in out, out)
    check("check: a tracked file that isn't a test never counts as a saved test",
          "task 6  proof  ok \u00b7 couldn't confirm a saved test" in out, out)
    check("check: the test a build just wrote counts before it is committed",
          "task 7  proof  ok \u00b7 test saved: tests/test_fresh.py" in out, out)
    check("check: an after-check that isn't the before-check is broken proof",
          "task 8  proof  DIFFERENT-COMMAND" in out, out)
    check("check: an after-check with nothing before it is broken proof",
          "task 9  proof  NO-BEFORE" in out, out)
    check("check: a config file that merely lives under tests/ is not a saved test",
          "task 10  proof  ok \u00b7 couldn't confirm a saved test" in out, out)
    check("check: the real test wins over a config file named in the same command",
          "task 11  proof  ok \u00b7 test saved: tests/test_x.py" in out, out)
    check("check: leads with the damage, and counts only proofs that held",
          "check: 6 of 11 fix(es) proved \u00b7 5 broken \u00b7 3 left a test behind in the project" in out, out)
    check("check: the summary names proof as its own kind of breakage",
          "broken (citations and proof)" in out or "broken (citations, quotes and proof)" in out, out)
    check("check: the proof rows land in check.md too", "| task 1 | proof | ok |" in read(os.path.join(brun, "check.md")))

    # Where a proof names its test: a Godot flag, a subfolder, a config file, a path outside the project
    proof = new_repo(tmp, "proof")
    for p in ["test/unit/test_player.gd", "webapp/frontend/src/utils/fmt.test.js",
              "webapp/backend/tests/test_expiry.py", "tests/test_settings.toml"]:
        write(os.path.join(proof, p), "x\n")
    write(os.path.join(proof, ".council", "council.config.md"), "# Council config — proof\n")
    git(proof, "add", "-A")
    git(proof, "commit", "-q", "-m", "tests")
    outside = os.path.join(tmp, "outside", "test_repro.py")
    write(outside, "x\n")
    code, prf, _ = council(proof, "run", "open", "council-implement")
    prf = prf.strip()
    for n, cmd in enumerate(["godot --headless -s addons/gut/gut_cmdln.gd -gtest=res://test/unit/test_player.gd -gexit",
                             "npm --prefix webapp/frontend test -- src/utils/fmt.test.js",
                             "cd webapp/backend && python -m pytest tests/test_expiry.py::test_y",
                             "pytest -c tests/test_settings.toml -k expiry",
                             "pytest " + slash(outside),
                             "(cd webapp/backend && pytest tests/test_expiry.py)",
                             "cd " + slash(tmp) + " && pytest webapp/backend/tests/test_expiry.py",
                             "cd webapp/frontend && pytest ../backend/tests/test_expiry.py"], start=1):
        for name, ex in ((f"before-{n}", 1), (f"after-{n}", 0)):
            write(os.path.join(prf, "gates", name + ".json"),
                  '{"gate": "%s", "command": "%s", "exit": %d, "seconds": 1, "when": "2026-09-16 10:00:00"}\n' % (name, cmd, ex))
    write(os.path.join(prf, "seats", "diagnose-2.md"), "# Diagnosis — task 2\nref: none\n## Index\n"
          "1 · likely · root cause · webapp/backend/tests/test_expiry.py:9-12 · the lines before the fix\n")
    code, out, _ = council(proof, "check")
    check("check: a Godot test named as -gtest=res://… counts as the saved test",
          "task 1  proof  ok · test saved: test/unit/test_player.gd" in out, out)
    check("check: a test path under npm --prefix <dir>, or after cd <dir> &&, is found in that folder",
          "task 2  proof  ok · test saved: webapp/frontend/src/utils/fmt.test.js" in out
          and "task 3  proof  ok · test saved: webapp/backend/tests/test_expiry.py" in out, out)
    check("check: a config file is never a saved test, even when its name says test",
          "task 4  proof  ok · couldn't confirm a saved test" in out, out)
    check("check: a test file outside the project is never a test the project keeps",
          "task 5  proof  ok · couldn't confirm a saved test" in out, out)
    check("check: a test run in a subshell — (cd <dir> && …) — is found in that folder",
          "task 6  proof  ok · test saved: webapp/backend/tests/test_expiry.py" in out, out)
    check("check: after a cd out of the project, the project's own file of that name is not the saved test",
          "task 7  proof  ok · couldn't confirm a saved test" in out, out)
    check("check: a test path that walks back up out of a cd folder is named as the file it is",
          "task 8  proof  ok · test saved: webapp/backend/tests/test_expiry.py" in out, out)
    check("check: in a build, a diagnosis file's old line numbers aren't checked as citations",
          code == 0 and "diagnose-2" not in out, out)
    write(os.path.join(req, ".council", "logs", "2026-09-16-build.md"),
          "# Council Implementation Log \u2014 build\nInput: `x` \u00b7 Run: %s \u00b7 Start: abc123\n\n## Task 1: x\n"
          % os.path.basename(brun))
    code, out, err = council(req, "run", "close")
    check("run close: warns when a build log never says what it traded away",
          code == 0 and "Shortcuts and concessions" in err, err)
    code, noproof, _ = council(req, "run", "open", "council-implement", "--alongside")
    noproof = noproof.strip()
    code, out, _ = council(req, "check", "--run", os.path.basename(noproof))
    check("check: a build that recorded no before-and-after evidence is not a pass",
          code == 1 and "NO PROOF" in out, out)
    write(os.path.join(req, ".council", "logs", "2026-09-16-other.md"),
          "# Council Implementation Log \u2014 other\nInput: `x` \u00b7 Run: %s-2 \u00b7 Start: abc123\n\n"
          "## Shortcuts and concessions\nnone\n" % os.path.basename(noproof))
    code, out, err = council(req, "run", "close", "--run", os.path.basename(noproof))
    check("run close: a log naming a different run whose id starts the same doesn't count",
          code == 0 and "no build log names this run" in err, err)

    code, brun2, _ = council(req, "run", "open", "council-implement")
    brun2 = brun2.strip()
    write(os.path.join(req, ".council", "logs", "2026-09-16-build-2.md"),
          "# Council Implementation Log \u2014 build 2\nInput: `x` \u00b7 Run: %s \u00b7 Start: abc123\n\n"
          "## Task 1: x\n\n## Shortcuts and concessions\nnone\n" % os.path.basename(brun2))
    code, out, err = council(req, "run", "close")
    check("run close: no warning when the log says what it traded away (or 'none')",
          code == 0 and "Shortcuts and concessions" not in err, err)
    cl = new_repo(tmp, "closelog")
    write(os.path.join(cl, ".council", "council.config.md"), "# Council config — close\n")
    code, clrun, _ = council(cl, "run", "open", "council-implement")
    clrun = clrun.strip()
    write_plan(clrun, selected=("builder", "verify-1"))
    cln = os.path.basename(clrun)
    council(cl, "state", "ask-saved=x")
    write(os.path.join(cl, ".council", "logs", "2026-09-17-zz-build.md"),
          f"# Build log\nInput: `x` · Run: {cln} · Start: abc123\n\n## Shortcuts and concessions\nnone\n")
    write(os.path.join(cl, ".council", "logs", "2026-09-17-aa-notes.md"), f"# Notes\nThe build (run {cln}) follows plan 3.\n")
    council(cl, "seat", "builder", "done", "agent=b1", "tokens=90000")
    council(cl, "seat", "verify-1", "running", "agent=v1")
    code, out, err = council(cl, "run", "close")
    check("run close: reads the build log whose Run: line names the run, not another file that mentions it",
          code == 0 and "Shortcuts and concessions" not in err, err)
    check("run close: names the seats still marked running", "verify-1" in line_of(err, "still"), err)
    code, clrun2, _ = council(cl, "run", "open", "council-implement")
    clrun2 = clrun2.strip()
    council(cl, "state", "ask-saved=x")
    write(os.path.join(cl, ".council", "logs", "2026-09-17-zz-build-2.md"),
          f"# Build log\nInput: `x` · Run: {slash(clrun2)} · Start: abc123\n\n"
          "## Shortcuts and concessions\nnone\n")
    write(os.path.join(cl, ".council", "logs", "2026-09-17-aa-notes-2.md"),
          f"# Notes\nThe build (run {os.path.basename(clrun2)}) follows plan 3.\n")
    code, out, err = council(cl, "run", "close")
    check("run close: a Run: line that gives the run's folder path names the build log too",
          code == 0 and "Shortcuts and concessions" not in err, err)

    write(os.path.join(req, ".council", "postgames", "2026-09-15-csv.md"),
          "---\ntitle: Post-game — CSV\nkind: postgame\nareas: reports/**\n---\n# Post-game: CSV\n"
          "**Your request:** `.council/asks/x.md` — \"We need CSV export\"\n| 1 | a.txt:1 | Met |\n")
    code, out, _ = council(req, "prior", "a.txt")
    check("prior: finds a post-game", "postgames/2026-09-15-csv.md" in out, out)
    code, out, _ = council(req, "prior", ".council/asks/x.md")
    check("prior: a request's path finds the deliverables that point at it", "postgames/2026-09-15-csv.md" in out, out)
    chg = new_repo(tmp, "changed")
    write(os.path.join(chg, "src", "old.py"), "x = 1\n")
    write(os.path.join(chg, "src", "keep.txt"), "not python\n")
    git(chg, "add", "-A")
    git(chg, "commit", "-q", "-m", "base")
    code, out, _ = council(chg, "changed", "--glob", "*.py", "--", "wc", "-l")
    check("changed: nothing changed is a pass, not a skip",
          code == 0 and "no files matched" in out and "not a skip" in out, out)
    write(os.path.join(chg, ".council", "council.config.md"), "# Council config\n")
    write(os.path.join(chg, ".council", ".gitignore"), "runs/\n# local\ncache/")    # no asks/, no final newline
    git(chg, "add", "-A")
    git(chg, "commit", "-q", "-m", "an older home")
    council(chg, "run", "open", "council-review")
    code, out, _ = council(chg, "changed")
    check("changed: the ignore lines run open adds to an older home's tracked .gitignore are not the user's change",
          code == 0 and "no files matched" in out and ".council" not in out, out)
    write(os.path.join(chg, "src", "old.py"), "x = 11\n")          # unstaged edit
    write(os.path.join(chg, "src", "new file.py"), "y = 2\n")      # untracked, and a space in the name
    code, out, _ = council(chg, "changed", "--glob", "*.py")
    listed = out.split()
    check("changed: lists the edited and the brand-new file, and nothing else",
          code == 0 and "src/old.py" in out and "src/new file.py" in out and "keep.txt" not in out, out)
    code, out, _ = council(chg, "changed", "--glob", "*.py", "--each", "--", "wc", "-l")
    check("changed --each: runs the tool once per file, spaces in names intact",
          code == 0 and out.count("\n") >= 1 and "new file.py" in out, out)
    code, out, _ = council(chg, "changed", "--glob", "*.py", "--", "false")
    check("changed: a failing tool fails the gate", code != 0, out)
    code, out, err = council_quoted(chg, "changed", "--glob", "*.{py,md}")
    check("changed: a {a,b} pattern covers each of its alternatives",
          code == 0 and "src/old.py" in out and "src/new file.py" in out, out + err)
    code, out, err = council_quoted(chg, "changed", "--glob", "docs/*.py", "--", "true")
    check("changed: a pattern that matches no file anywhere in the project is an error, never a pass forever",
          code == 2 and "no file in this project" in err and "anchored at the repo root" in err, out + err)
    write(os.path.join(chg, "good.sh"), "echo fine\n")
    write(os.path.join(chg, "zz-broken.sh"), "if then fi (\n")
    code, out, err = council_quoted(chg, "changed", "--glob", "*.sh", "--each", "--", "bash", "-n")
    check("changed --each: a file that fails the check fails the gate, even when it is the last one",
          code != 0 and "zz-broken.sh" in err, out + err)
    write(os.path.join(chg, "-c.sh"), "echo ok\n")
    code, out, err = council_quoted(chg, "changed", "--glob", "-*.sh", "--", "bash", "-n")
    check("changed: a file whose name starts with - reaches the tool as a file, not as an option",
          code == 0 and "file(s) to check" in err and "invalid option" not in err, out + err)
    git(chg, "add", "-A")
    git(chg, "commit", "-q", "-m", "work")
    git(chg, "checkout", "-q", "-b", "feature")
    write(os.path.join(chg, "src", "branch.py"), "b = 1\n")
    git(chg, "add", "-A")
    git(chg, "commit", "-q", "-m", "on the branch")
    code, out, _ = council(chg, "changed", "--glob", "*.py")
    check("changed: work committed on this branch counts; the rest of the project doesn't",
          code == 0 and out.strip() == "src/branch.py", out)
    code, out, err = council(chg, "changed", "--base", "no-such-ref", "--glob", "*.py")
    check("changed: a --base that isn't a ref is an error, never a quietly smaller file list",
          code == 2 and "not a ref in this repository" in err, err)
    code, out, err = council(chg, "changed", "--glob", "*.py", "--", "wc", "-l")
    check("changed: says how many files the check actually looked at", "file(s) to check" in (out + err), out + err)
    os.remove(os.path.join(chg, "src", "branch.py"))
    code, out, _ = council(chg, "changed", "--glob", "*.py")
    check("changed: a file deleted in the range is never handed to the tool",
          code == 0 and "no files matched" in out, out)
    many = new_repo(tmp, "many")
    write(os.path.join(many, "README.md"), "# many\n")
    git(many, "add", "-A")
    git(many, "commit", "-q", "-m", "init")
    for i in range(300):
        write(os.path.join(many, "src", "a_rather_long_folder_name_for_batches", f"module_number_{i:03d}.py"), "x = 1\n")
    code, out, err = council(many, "changed", "--glob", "*.py", "--", "bash", "-c", 's="$*"; echo "batch $# ${#s}"', "x")
    batches = [(int(a), int(b)) for a, b in re.findall(r"^batch (\d+) (\d+)$", out, re.MULTILINE)]
    check("changed: a long file list goes to the tool in batches a Windows .cmd tool can take (8,191 characters)",
          code == 0 and len(batches) >= 2 and sum(a for a, _ in batches) == 300 and all(b < 7500 for _, b in batches), out + err)
    if os.name == "nt":
        with open(os.path.join(many, "t.cmd"), "w", encoding="utf-8", newline="") as f:
            f.write("@echo off\r\nfor %%a in (%*) do rem\r\nexit /b 0\r\n")
        code, out, err = council(many, "changed", "--glob", "*.py", "--", "./t.cmd")
        check("changed: on Windows a .cmd tool takes 300 changed files", code == 0 and "too long" not in out + err, out + err)

    names_repo = new_repo(tmp, "names")
    write(os.path.join(names_repo, "a.txt"), "a\n")
    git(names_repo, "add", "-A")
    git(names_repo, "commit", "-q", "-m", "init")
    write(os.path.join(names_repo, ".council", "council.config.md"),
          "# Council config \u2014 names\nlast-verified: 2026-09-15 @ x\n\n## Gates\n"
          "| Gate | Command | Run at | Mandatory | Checked | Probe | Side effects | Needs |\n"
          "|---|---|---|---|---|---|---|---|\n"
          "| unit tests | `exit 1` | verify | yes | ok | `true` | none | - |\n"
          "| type check | `exit 1` | verify | no | ok | `true` | none | - |\n"
          "| lint | `true` | verify | no | ok | `true` | none | - |\n"
          "| e2e | `true` | verify | yes | \u2717 2026-09-01: no browser here | - | none | - |\n")
    council(names_repo, "run", "open", "council-review")
    code, out, _ = council(names_repo, "gate", "--all", "--at", "verify")
    check("gate --all: a gate name with a space stays one name in the FAIL list",
          "FAIL (unit tests, type check \u2014 mandatory)" in out, out)
    check("gate --all: a required gate that could not run is named, so the line can't read clean",
          "1 skipped (1 of them required: e2e" in out, out)

    write(os.path.join(names_repo, ".council", "council.config.md"),
          "# Council config \u2014 names\nlast-verified: 2026-09-15 @ x\n\n## Gates\n"
          "| Gate | Command | Run at | Mandatory | Checked | Probe | Side effects | Needs |\n"
          "|---|---|---|---|---|---|---|---|\n"
          "| lint | `true` | verify | no | ok | `true` | none | - |\n"
          "| the whole test suite | `exit 9` |  | yes | ok | `true` | none | - |\n")
    code, out, _ = council(names_repo, "gate", "--all", "--at", "verify")
    check("gate --all --at: a required gate with no stage at all is named, not silently dropped",
          "gate the whole test suite: skipped \u2014 its Run at cell is empty" in out
          and "1 of them required: the whole test suite" in out, out)
    write(os.path.join(names_repo, ".council", "council.config.md"),
          "# Council config \u2014 names\nlast-verified: 2026-09-15 @ x\n\n## Gates\n"
          "| Gate | Command | Run at | Mandatory | Checked | Probe | Side effects | Needs |\n"
          "|---|---|---|---|---|---|---|---|\n"
          "| lint | `bash '" + slash(CLI) + "' changed --glob 'a.txt' -- false` | verify | no | ok | `true` | none | - |\n")
    code, out, _ = council(names_repo, "gate", "--all", "--at", "verify")
    check("gate --all: a check that matched no files passes, but is never reported as a clean pass",
          code == 0 and "pass \u2014 but nothing to check (0 files matched)" in out
          and "1 had nothing to check (lint \u2014 0 files matched)" in out, out)

@part("requests")
def close_unfinished(tmp):
    # A run closed as complete that never finished is said plainly — warned, never refused
    repo = small_council_repo(tmp, "closeearly", "| tests | `echo '1 failed'; exit 1` | grounding, verify | yes | ok | `true` | none | - |\n"
                                                 "| lint | `exit 1` | grounding, verify | no | ok | `true` | none | - |\n")
    code, run, _ = council(repo, "run", "open", "council-review")
    run = run.strip()
    council(repo, "state", "phase=prepare")
    council(repo, "gate", "--all")
    council(repo, "gate", "before-1", "--", "exit 1")        # an ad-hoc red check is never a required one
    code, out, err = council(repo, "run", "close")
    closed = [e for e in events(run) if e[3] == "run.closed"]
    check("run close: a run closed complete at an early stage says it never reached Deliver",
          code == 0 and "closed as complete at stage prepare, so it never reached Deliver" in err
          and "--status abandoned" in err, err)
    check("run close: names the required check whose last run failed, and only that one",
          "a required check failing on its last run: tests —" in err and "lint" not in err and "before-1" not in err, err)
    check("run close: says no deliverable was recorded, and a review has no verifier verdicts",
          "no deliverable recorded" in err and "no verifier verdicts" in err, err)
    check("run close: the close event records the warnings",
          closed and "warnings=phase,check,deliverable,verdicts" in closed[-1][6], str(closed))
    check("run close: the run is still closed as complete (a warning, not a refusal)",
          "status: complete" in read(os.path.join(run, "session-state.md")), read(os.path.join(run, "session-state.md")))

    done = small_council_repo(tmp, "closedone", "| tests | `if [ -f .fixed ]; then echo '3 passed'; exit 0; fi; exit 1` | grounding, verify | yes | ok | `true` | none | - |\n")
    code, run, _ = council(done, "run", "open", "council-review")
    run = run.strip()
    council(done, "gate", "--all")
    write(os.path.join(done, ".fixed"), "")
    council(done, "gate", "tests")                              # red at first, green on its last run
    write_plan(run)
    write(os.path.join(run, "verify-1.md"), "# Verification — finished\n| # | Verdict |\n|---|---|\n| 1 | CONFIRMED |\n")
    code, out, err = council(done, "state", "phase=learn", "deliverable=.council/reviews/2026-10-01-x.md")
    code, out, err = council(done, "run", "close")
    closed = [e for e in events(run) if e[3] == "run.closed"]
    check("run close: a finished run with its checks green, a deliverable and verdicts closes without a warning",
          code == 0 and "closed as complete" not in err and closed and "warnings=" not in closed[-1][6], err + str(closed))
    early = small_council_repo(tmp, "closestop", "| tests | `exit 1` | grounding | yes | ok | `true` | none | - |\n")
    council(early, "run", "open", "council-review")
    council(early, "gate", "--all")
    code, out, err = council(early, "run", "close", "--status", "abandoned")
    check("run close --status abandoned: an unfinished run given up on raises none of these warnings",
          code == 0 and "closed as complete" not in err, err)


@part("gates")
def gates_table(tmp):
    # The Gates table's small vocabularies \u2014 Run at, Mandatory, Checked \u2014 and what gate --all may run unasked
    vocab = new_repo(tmp, "vocab")
    write(os.path.join(vocab, "a.txt"), "a\n")
    git(vocab, "add", "-A")
    git(vocab, "commit", "-q", "-m", "init")

    def gates_cfg(where, rows, head="| Gate | Command | Run at | Mandatory | Checked | Probe | Side effects | Needs |\n"
                                    "|---|---|---|---|---|---|---|---|\n"):
        write(os.path.join(where, ".council", "council.config.md"),
              "# Council config \u2014 x\nlast-verified: 2026-09-15 @ x\n\n## Gates\n" + head + rows + "\n## Hard rules\n")

    gates_cfg(vocab, "| tests | `echo RAN-TESTS; exit 1` | Grounding, Verify | yes | ok | `true` | none | - |\n"
                     "| suite | `exit 1` | grounding, verification | no | ok | `true` | none | - |\n"
                     "| lint | `true` | verify | no | ok | `true` | none | - |\n")
    code, vrun, _ = council(vocab, "run", "open", "council-implement")
    vgates = os.path.join(vrun.strip(), "gates")
    code, out, _ = council(vocab, "gate", "--all", "--at", "verify")
    check("gate --all --at: a Run at cell is read whatever its case, and 'verification' means verify",
          code == 1 and "gate tests: FAIL" in out and "gate suite: FAIL" in out and "gates: 3 ran" in out, out)
    gates_cfg(vocab, "| both | `true` | Both | no | ok | `true` | none | - |\n"
                     "| strict | `exit 7` | strict | yes | ok | `true` | none | - |\n"
                     "| typo | `exit 7` | grounding, verfy | no | ok | `true` | none | - |\n"
                     "| byhand | `exit 7` | manual | yes | ok | `true` | none | - |\n")
    code, out, _ = council(vocab, "gate", "--all", "--at", "Verification")
    check("gate --all --at: the stage is read whatever its case, and 'both' runs at every stage",
          code == 0 and "gate both: pass" in out, out)
    check("gate --all --at: a Run at word it doesn't know is named, never silently dropped",
          "gate strict: skipped" in out and "'strict'" in out and "gate typo: skipped" in out and "'grounding, verfy'" in out
          and not os.path.isfile(os.path.join(vgates, "strict.txt")) and not os.path.isfile(os.path.join(vgates, "typo.txt")), out)
    check("gate --all --at: a required gate that runs only by name is named as required",
          "gate byhand: skipped" in out and "2 of them required: strict, byhand" in out, out)
    mand_bad = []
    for word in ["required", "\u2713", "**Yes**", "always", "YES \u2014 blocks the run"]:
        gates_cfg(vocab, f"| t | `exit 1` | verify | {word} | ok | `true` | none | - |\n")
        code, out, _ = council(vocab, "gate", "--all", "--at", "verify")
        if code != 1 or "a mandatory gate failed" not in out:
            mand_bad.append(word)
    check("gate --all: required, a tick, **Yes** and always all mean mandatory", not mand_bad, ", ".join(mand_bad))
    gates_cfg(vocab, "| t | `exit 1` | verify | not mandatory | \u2705 2026-09-15 | `true` | none | - |\n")
    code, out, _ = council(vocab, "gate", "--all", "--at", "verify")
    check("gate --all: 'not mandatory' is not mandatory, and a green tick in Checked means runnable",
          code == 0 and "FAIL (t, not mandatory)" in out, out)
    gates_cfg(vocab, "| dot | `true` | grounding \u00b7 verify | yes | ok | `true` | none | - |\n"
                     "| slow | `true` | verify (slow, run in background) | yes | ok | `true` | none | - |\n"
                     "| byhand | `true` | manual (needs the device) | yes | ok | `true` | none | - |\n")
    code, out, _ = council(vocab, "gate", "--all", "--at", "verify")
    check("gate --all --at: a note in brackets is a note, and \u00b7 between two stages is a separator",
          code == 0 and "gate dot: pass" in out and "gate slow: pass" in out and "names no stage" not in out
          and "council gate byhand" in out, out)
    code, out, _ = council(vocab, "gate", "--all", "--at", "grounding")
    check("gate --all --at: a gate whose cell names only the other stage is not counted as a required skip",
          code == 0 and "gate dot: pass" in out and "slow" not in out and "1 skipped" in out, out)
    code, out, _ = council(vocab, "doctor")
    check("doctor: a Run at cell that names its stage raises nothing, note or separator included",
          "gate 'dot'" not in out and "gate 'slow'" not in out and "gate 'byhand'" not in out, out)
    gates_cfg(vocab, "| nonblock | `exit 1` | verify | non-blocking | ok | `true` | none | - |\n"
                     "| zero | `exit 1` | verify | 0 | ok | `true` | none | - |\n")
    code, out, _ = council(vocab, "gate", "--all", "--at", "verify")
    check("gate --all: non-blocking and 0 mean not mandatory, so a failing advisory gate never hard-stops a build",
          code == 0 and "not mandatory" in out and "a mandatory gate failed" not in out, out)
    for header in ("Side-effects", "Side effects (none = safe)"):
        gates_cfg(vocab, "| tests | `true` | verify | yes | ok | none |\n",
                  head="| Gate | Command | Run at | Mandatory | Checked | %s |\n|---|---|---|---|---|---|\n" % header)
        code, out, _ = council(vocab, "gate", "--all", "--at", "verify")
        code2, dout, _ = council(vocab, "doctor")
        check(f"gate --all and doctor read a '{header}' header the same way",
              code == 0 and "gate tests: pass" in out and "no Side effects column" not in out + dout, out + dout)
    gates_cfg(vocab, "| odd | `exit 1` | verify | sometimes | maybe | `true` | none | - |\n"
                     "| e2e | `exit 1` | verify | yes | \u274c needs the game editor | `true` | none | - |\n")
    code, out, _ = council(vocab, "gate", "--all", "--at", "verify")
    check("gate --all: a Mandatory word it doesn't know is said, and counts as mandatory",
          code == 1 and "Mandatory cell says 'sometimes'" in out and "gate odd: FAIL" in out, out)
    check("gate --all: a Checked word it doesn't know is said; a cross mark means not runnable here",
          "Checked cell says 'maybe'" in out and "gate e2e: skipped" in out and not os.path.isfile(os.path.join(vgates, "e2e.txt")), out)
    gates_cfg(vocab, "| strict | `true` | strict | sometimes | maybe | `true` | none | - |\n"
                     "| ps | `powershell -File tools\\run_tests.ps1` | verify | yes | ok | `true` | none | - |\n"
                     "| quoted | `echo \"tools\\run.ps1\" 'a\\b'` | verify | no | ok | `true` | none | - |\n")
    code, out, _ = council(vocab, "doctor")
    check("doctor: names a Run at, Mandatory or Checked value it can't read",
          "gate 'strict' has a Run at value" in out and "gate 'strict' has a Mandatory value" in out
          and "gate 'strict' has a Checked value" in out, out)
    check("doctor: flags a gate command whose backslash bash would drop, and only that one",
          "gate 'ps'" in out and "backslash" in out and "gate 'quoted'" not in out, out)
    code, out, _ = council(vocab, "gates")
    check("gates: points out a backslash bash would drop", "backslash" in row(out, "ps") and "backslash" not in row(out, "quoted"), out)
    gates_cfg(vocab, "| msb | `msbuild App.sln /p:Configuration=Release /nologo` | manual | no | ok | `true` | none | - |\n"
                     "| paths | `ls /c/Users /usr/bin http://x/y C:/x` | manual | no | ok | `true` | none | - |\n"
                     "| dashed | `dotnet build -p:Configuration=Release` | manual | no | ok | `true` | none | - |\n")
    code, out, _ = council(vocab, "doctor")
    check("doctor: flags a Windows switch Git Bash would turn into a path, and says to write -p:",
          "gate 'msb' has a Windows switch" in out and "-p:" in out
          and "gate 'paths' has a Windows switch" not in out and "gate 'dashed' has a Windows switch" not in out, out)
    code, out, _ = council(vocab, "gates")
    check("gates: points out the Windows switch on that gate only",
          "Windows switch" in row(out, "msb") and "Windows switch" not in row(out, "paths") + row(out, "dashed"), out)
    gates_cfg(vocab, "| strict | `true` | strict | sometimes | maybe | `true` | none | - |\n"
                     "| ps | `powershell -File tools\\run_tests.ps1` | verify | yes | ok | `true` | none | - |\n"
                     "| quoted | `echo \"tools\\run.ps1\" 'a\\b'` | verify | no | ok | `true` | none | - |\n")
    code, out, _ = council(vocab, "gate", "bs", "--", "echo tools\\x")
    check("gate: an ad-hoc command's stray backslash gets a note", "backslash" in out and read(os.path.join(vgates, "bs.txt")) == "toolsx\n", out)
    write(os.path.join(vocab, "probe_abs.py"), "print('abs ok')\n")
    py = sys.executable.replace("\\", "/")          # a native tool, given a bash absolute path
    code, out, _ = council(vocab, "gate", "abspath", "--", f'"{py}" "$PWD/probe_abs.py"')
    check("gate: a gate's own environment is left alone, so an absolute path still reaches its tool",
          code == 0 and "abs ok" in read(os.path.join(vgates, "abspath.txt")), out + read(os.path.join(vgates, "abspath.txt")))
    if os.name == "nt":
        for form in ("cmd /c exit 3", "cmd //c exit 3", 'cmd.exe /C "exit 3"'):
            code, out, _ = council(vocab, "gate", "cmd-exit", "--", form)
            check(f"gate: on Windows, {form} runs its command and the gate gets its exit code",
                  code == 3 and "FAIL (exit 3" in out, out)
        code, out, _ = council(vocab, "gate", "cmd-bare", "--", "cmd")
        check("gate: on Windows, a cmd that only opened its prompt is never a pass",
              code != 0 and "ran nothing" in out, out)
    gates_cfg(vocab, "| tests | `true` | verify | yes | ok | `true` | none | - |\n")
    code, out, _ = council(vocab, "gate", "--all", "--at", "grounding")
    check("gate --all --at: with every gate at another stage, NOTHING WAS CHECKED names the stage",
          code == 4 and "NOTHING WAS CHECKED \u2014 no gate in" in out and "runs at 'grounding'" in out, out)
    gates_cfg(vocab, "| lint | `true` | verify | no | ok | `true` | none | - |\n"
                     "| e2e suite | `echo e2e > ran-e2e.txt` | verify | yes | ok | `true` | writes the test database, network | - |\n"
                     "| smoke | `echo smoke > ran-smoke.txt` | verify | no | ok | `true` | network | a production API token |\n")
    code, out, _ = council(vocab, "gate", "--all", "--at", "verify")
    check("gate --all: a required gate skipped for its side effects is named as required",
          "gates: 1 ran \u2014 all pass \u00b7 2 skipped (1 of them required: e2e suite" in out
          and not os.path.isfile(os.path.join(vocab, "ran-e2e.txt")), out)
    check("gate --all: never runs a gate whose Needs name a token, even with safe side effects",
          "gate smoke: skipped" in out and not os.path.isfile(os.path.join(vocab, "ran-smoke.txt")), out)
    check("gate --all: the run-it-by-name hint quotes a name with a space", 'council gate "e2e suite"' in out, out)
    code, out, _ = council(vocab, "gate", "e2e", "suite")
    check("gate: a name given as separate words still finds its gate", code == 0 and "gate e2e suite: pass" in out, out)
    gates_cfg(vocab, "| tests | `true` | verify | yes | ok |\n"
                     "| ship | `echo WOULD-RUN: npx vercel --prod > ran-ship.txt` | verify | no | ok |\n"
                     "| push | `echo WOULD-RUN: git push origin main > ran-push.txt` | verify | no | ok |\n",
              head="| Gate | Command | Run at | Mandatory | Checked |\n|---|---|---|---|---|\n")
    code, out, _ = council(vocab, "gate", "--all", "--at", "verify")
    check("gate --all: an older table (no Side effects column) runs nothing unasked, whatever its commands say",
          not os.path.isfile(os.path.join(vocab, "ran-ship.txt")) and not os.path.isfile(os.path.join(vocab, "ran-push.txt"))
          and "gate push: skipped \u2014 the Gates table has no Side effects column" in out, out)
    check("gate --all: when an older table stops every gate, NOTHING WAS CHECKED says why",
          code == 4 and "NOTHING WAS CHECKED \u2014 the Gates table" in out and "no Side effects column" in out, out)

    # A red baseline: its output is kept, and a later failure names only what's new
    redbase = new_repo(tmp, "redbase")
    write(os.path.join(redbase, "a.txt"), "a\n")
    git(redbase, "add", "-A")
    git(redbase, "commit", "-q", "-m", "init")
    gates_cfg(redbase, "| tests | `if [ -f .fixed ]; then echo FAILED test_new; else echo FAILED test_old_a; echo FAILED test_old_b; fi; exit 1`"
                       " | grounding, verify | yes | ok | `true` | none | - |\n")
    code, rrun, _ = council(redbase, "run", "open", "council-implement")
    rgates = os.path.join(rrun.strip(), "gates")
    council(redbase, "gate", "--all")
    write(os.path.join(redbase, ".fixed"), "")
    code, out, _ = council(redbase, "gate", "tests")
    check("gate: a red baseline's output is kept apart from later runs of the same gate",
          "test_old_a" in read(os.path.join(rgates, "baseline", "tests.txt")) and "test_old_a" not in read(os.path.join(rgates, "tests.txt")), out)
    check("gate: a failing gate names the test that failed here and not at the baseline",
          code == 1 and "not at the baseline" in out and "test_new" in out.split("not at the baseline")[-1]
          and "test_old" not in out, out)
    council(redbase, "gate", "--all", "--at", "verify")
    check("gate --all --at verify: never replaces the baseline", "test_old_a" in read(os.path.join(rgates, "baseline", "tests.txt")))
    code, out, _ = council(redbase, "gate", "--all")      # a plain second run, after the change: it writes baselines too
    check("gate --all a second time: the first snapshot stays the baseline, so the change's failure is still named new",
          "test_old_a" in read(os.path.join(rgates, "baseline", "tests.txt"))
          and "test_new" not in read(os.path.join(rgates, "baseline", "tests.txt"))
          and code == 1 and "not at the baseline" in out and "test_new" in out.split("not at the baseline")[-1], out)
    # The comparison is by failing test, not by line: a runner's timed summary is never a "new" failure,
    # and a swap (one test fixed, another broken) is never "nothing new".
    gates_cfg(redbase, "| timed | `if [ -f .fixed ]; then t=0.81; else t=0.26; fi;"
                       " echo FAILED tests/test_a.py::test_one; echo FAILED tests/test_b.py::test_two;"
                       " echo \"== 2 failed, 3 passed in ${t}s ==\"; exit 1`"
                       " | grounding, verify | yes | ok | `true` | none | - |\n")
    os.remove(os.path.join(redbase, ".fixed"))
    council(redbase, "gate", "--all", "--at", "grounding")
    write(os.path.join(redbase, ".fixed"), "")
    code, out, _ = council(redbase, "gate", "timed")
    check("gate: an unchanged red suite is not reported as newly failing, whatever its run time",
          code == 1 and "the same test(s) are failing as at the baseline" in out and "2 failed, 3 passed"
          not in out.split("baseline")[-1], out)
    gates_cfg(redbase, "| swap | `if [ -f .swapped ]; then echo \"✖ formats dates (1.09ms)\";"
                       " else echo \"✖ parses input (0.71ms)\"; fi;"
                       " echo \"AssertionError [ERR_ASSERTION]: Expected values to be strictly equal:\"; exit 1`"
                       " | grounding, verify | yes | ok | `true` | none | - |\n")
    council(redbase, "gate", "--all", "--at", "grounding")
    write(os.path.join(redbase, ".swapped"), "")
    code, out, _ = council(redbase, "gate", "swap")
    check("gate: a red suite that swaps one failing test for another names the new one",
          code == 1 and "not at the baseline" in out and "formats dates" in out.split("not at the baseline")[-1], out)

    # A Gates section still written as a list (the layout before the table)
    legacy = new_repo(tmp, "legacy")
    write(os.path.join(legacy, "a.py"), "a = 1\n")
    write(os.path.join(legacy, ".council", "council.config.md"),
          "# Council config \u2014 legacy\n\n## Gates\n\n- **grounding** (phase 1):\n  - `pytest -m \"not network\"`   # unit tests\n"
          "- **verification** (phase 10):\n  - `npm --prefix web run build`\n- **mandatory:** `pytest`\n\n## Hard rules\n- none\n")
    git(legacy, "add", "-A")
    git(legacy, "commit", "-q", "-m", "init")
    council(legacy, "run", "open", "council-review")
    code, out, _ = council(legacy, "gate", "--all")
    check("gate --all: a Gates section written as a list is named as an older layout, not as no checks",
          code == 4 and "NOTHING WAS CHECKED" in out and "older layout" in out and "no automated check" not in out, out)
    code, out, _ = council(legacy, "doctor")
    check("doctor: a Gates section written as a list is an older layout for a refresh to migrate, not missing checks",
          "older layout (a list" in out and "council-init refresh" in out and "add the project's real" not in out, out)
    code, out, _ = council(legacy, "gates")
    check("gates: says the Gates section is an older layout", "older layout" in out, out)
    for label, gates in [("a plain name and a colon before the command", "- tests: `pytest -q`\n"),
                         ("its command on the line under the list item (tactics-v2's layout)",
                          "- **grounding** (Core phase 1):\n  `powershell -ExecutionPolicy Bypass -File tools\\run_tests.ps1`\n"
                          "  22 suites. Exits 2 on failure.\n")]:
        write(os.path.join(legacy, ".council", "council.config.md"),
              "# Council config — legacy\n\n## Gates\n\n" + gates + "\n## Hard rules\n- none\n")
        code, out, _ = council(legacy, "doctor")
        check(f"doctor: an older Gates list with {label} is named as an older layout",
              "older layout (a list" in out and "council-init refresh" in out, out)
    write(os.path.join(legacy, ".council", "council.config.md"),
          "# Council config — declined\nlast-verified: 2026-09-15 @ x\n\n## Gates\n\n"
          "- guardrails: declined 2026-09-01 (fit them later with a `council-init` refresh)\n\n## Hard rules\n- none\n")
    code, out, _ = council(legacy, "doctor")
    gate_line = [l for l in out.splitlines() if "no gates in council.config.md" in l]
    check("doctor: a Gates section that only mentions a command in prose is not an older layout to migrate",
          bool(gate_line) and gate_line[0].startswith("WARN") and "guardrails declined" in gate_line[0]
          and "older layout (a list" not in out, out)

    nogates = new_repo(tmp, "nogates")
    write(os.path.join(nogates, "x.txt"), "x\n")
    git(nogates, "add", "-A")
    git(nogates, "commit", "-q", "-m", "init")
    write(os.path.join(nogates, ".council", "council.config.md"),
          "# Council config \u2014 nogates\nlast-verified: 2026-09-15 @ x\n\n## Roster\n")
    code, out, _ = council(nogates, "doctor")
    gate_line = [l for l in out.splitlines() if "no gates in council.config.md" in l]
    check("doctor: a config with no gates is an error, not a warning",
          code == 1 and gate_line and gate_line[0].startswith("ERROR") and "NOTHING WAS CHECKED" in gate_line[0], out)

    append(os.path.join(nogates, ".council", "council.config.md"), "guardrails: declined 2026-09-16\n")
    code, out, _ = council(nogates, "doctor")
    gate_line = [l for l in out.splitlines() if "no gates in council.config.md" in l]
    check("doctor: a project that was offered the checks and declined gets a warning, not an error",
          gate_line and gate_line[0].startswith("WARN") and "guardrails declined" in gate_line[0], out)

    nohome = new_repo(tmp, "nohome")
    code, pg, err = council(nohome, "run", "open", "council-postgame")
    pg = pg.strip()
    check("run open council-postgame: works with no council yet, and creates one",
          code == 0 and os.path.isdir(pg)
          and {"runs/", "asks/"} <= set(read(os.path.join(nohome, ".council", ".gitignore")).split()), pg + err)


@part("gates")
def gates_nothing_behind_a_pass(tmp):
    # A pass with nothing behind it is said: no test ran, an empty Command cell, an exit code the command
    # hides, a record another gate overwrites, a committed change a ratchet never looked at
    godot = 'out=$("${GODOT:-/nowhere/Godot.exe}" --headless 2>&1); printf "%s\\n" "$out"; case "$out" in *"ERROR:"*) exit 1 ;; esac'
    repo = small_council_repo(tmp, "nothingran",
        "| zero | `printf 'collected 0 items\\n\\nno tests ran in 0.01s\\n'` | verify | yes | ok | `true` | none | - |\n"
        "| unit tests | `true` | verify | no | ok | `true` | none | - |\n"
        "| types | `true` | verify | no | ok | `true` | none | - |\n"
        "| real | `printf 'collected 3 items\\n3 passed in 0.1s\\n'` | verify | yes | ok | `true` | none | - |\n"
        "| cleared |  | verify | yes | ok | `true` | none | - |\n"
        "| piped | `false \\| tee log.txt` | verify | no | ok | `true` | none | - |\n"
        "| fallback | `true \\|\\| echo fallback` | verify | no | ok | `true` | none | - |\n"
        "| alt | `case x in a\\|x) exit 0 ;; esac` | verify | no | ok | `true` | none | - |\n"
        "| boot | `" + godot + "` | verify | yes | ok | `true` | none | - |\n"
        "| unit_tests | `true` | verify | no | ok | `true` | none | - |\n"
        "| cargo | `printf 'running 5 tests\\ntest result: ok. 5 passed; 0 failed\\n   Doc-tests foo\\nrunning 0 tests\\n'` | verify | no | ok | `true` | none | - |\n"
        "| lint | `true -- src tests` | verify | no | ok | `true` | none | - |\n"
        "| pipefail | `set -o pipefail; true \\| tee log.txt` | verify | no | ok | `true` | none | - |\n")
    code, run, _ = council(repo, "run", "open", "council-review")
    gates = os.path.join(run.strip(), "gates")
    code, out, _ = council(repo, "gate", "--all", "--at", "verify")
    check("gate --all: a runner that exits 0 after collecting no test is a pass with nothing run, never a plain pass",
          'gate zero: pass — but nothing ran: its output says "collected 0 items"' in out
          and "gate real: pass (exit 0" in out, out)
    check("gate --all: a test gate that printed nothing is flagged; a quiet type check is not",
          "gate unit tests: pass — but nothing ran that it shows: it printed nothing" in out
          and "gate types: pass (exit 0" in out, out)
    check("gate --all: the verdict line counts the gates that passed with nothing run",
          "2 passed with nothing run (zero, unit tests" in out, out)
    check("gate --all: cargo's 'running 0 tests' for its doc-tests, after tests that ran, is a plain pass",
          "gate cargo: pass (exit 0" in out, out)
    check("gate --all: a quiet linter is not a test gate because an argument says tests",
          "gate lint: pass (exit 0" in out, out)
    check("gate --all: a pipe after set -o pipefail gets no pipe note", "gate pipefail — its command pipes" not in out, out)
    check("gate: a pass that ran no test is recorded as empty, so it can never close a repair trail",
          any(e[3] == "gate.finished" and e[4] == "zero" and "empty=1" in e[6] for e in events(run.strip())),
          str(events(run.strip())))
    check("gate --all: a required gate whose Command cell is empty is named and counted, never dropped",
          "gate cleared: skipped — its Command cell is empty" in out and "required: cleared" in out, out)
    code2, lst, _ = council(repo, "gates")
    check("gates: lists a gate whose Command cell is empty", "cleared · (no command" in lst, lst)
    code2, out2, err2 = council(repo, "gate", "cleared")
    check("gate <name>: a gate with an empty Command cell is refused with the way to run it",
          code2 == 2 and "empty Command cell" in err2 and "council gate cleared -- '<command>'" in err2, out2 + err2)
    check("gate --all: a piped command gets the pipe note, as it does by name",
          "note: gate piped — its command pipes its output" in out, out)
    check("gate --all: || and a case pattern's bar are not called a pipe; a fallback that always succeeds is named",
          "gate fallback — its command ends with a step that always succeeds" in out
          and "gate fallback — its command pipes" not in out and "gate alt —" not in out, out)
    check("gate --all: a runner kept in $( ) and judged by its text is named (it passes with the engine missing)",
          "gate boot: pass" in out and "note: gate boot — its command keeps a runner's output in $( )" in out
          and "|| exit $?" in out, out)
    check("gate --all: a gate whose record would overwrite another's is skipped and named, not run over it",
          "gate unit_tests: skipped — it would overwrite the record of gate unit tests" in out
          and json.loads(read(os.path.join(gates, "unit_tests.json")) or "{}").get("gate") == "unit tests", out)
    code, out, _ = council(repo, "gate", "fallback")
    check("gate <name>: || is never called a pipe", "contains a pipe" not in out and "pipes its output" not in out
          and "always succeeds" in out, out)

    # The baseline: green before means every failure is new; a log line's time is not a test
    base = small_council_repo(tmp, "wasgreen",
        "| green | `if [ -f .broken ]; then echo 'FAILED tests/test_c.py::test_new - boom'; exit 1; fi; echo '5 passed'` | grounding, verify | no | ok | `true` | none | - |\n"
        "| logs | `if [ -f .broken ]; then t=10:07:44; else t=10:00:01; fi; echo \"ERROR 2026-09-30 $t could not reach cache\"; echo 'FAILED tests/test_a.py::test_old'; exit 1` | grounding, verify | no | ok | `true` | none | - |\n")
    council(base, "run", "open", "council-implement")
    council(base, "gate", "--all", "--at", "grounding")
    write(os.path.join(base, ".broken"), "")
    code, out, _ = council(base, "gate", "--all", "--at", "verify")
    check("gate: a gate green at the baseline says every failure is new, not that nothing can be compared",
          "this gate passed at the baseline" in out and "the baseline's output names no failing test" not in out, out)
    check("gate: a timestamped log line is not read as a newly failing test",
          "the same test(s) are failing as at the baseline (gates/baseline/logs.txt)" in out
          and "10:07:44 could not reach cache" not in out.split("gate logs:")[-1].split("baseline")[-1], out)

    # A ratchet gate on the default branch, the change committed: the run's recorded base reaches it
    ratchet = small_council_repo(tmp, "runbase", "| compile | `bash '" + slash(CLI) + "' changed --glob '*.py' -- '"
                                 + slash(sys.executable) + "' -m py_compile` | verify | yes | ok | `true` | none | - |\n")
    write(os.path.join(ratchet, "good.py"), "x = 1\n")
    git(ratchet, "add", "-A")
    git(ratchet, "commit", "-q", "-m", "good")
    write(os.path.join(ratchet, "bad.py"), "def broken(:\n    return 1\n")
    git(ratchet, "add", "-A")
    git(ratchet, "commit", "-q", "-m", "the change under review")
    code, rrun, _ = council(ratchet, "run", "open", "council-review")
    council(ratchet, "index", "--base", "HEAD~1")
    code, out, _ = council(ratchet, "gate", "--all", "--at", "verify")
    saved = read(os.path.join(rrun.strip(), "gates", "compile.txt"))
    check("gate: council changed inside a gate uses the run's recorded base, so a committed change on main is checked",
          code == 1 and "gate compile: FAIL" in out and "SyntaxError" in saved
          and "(the run's recorded base)" in saved, out + saved)
    code, out, err = council_quoted(ratchet, "changed", "--glob", "*.py")
    check("changed: outside a gate, on the default branch, it says it sees only uncommitted files and how to widen it",
          code == 0 and "no files matched" in out and "uncommitted and new files only" in err and "--base" in err, out + err)


@part("gates")
def gates_build_records_attempts(tmp):
    # In a build a gate's own result is the repair record: three failures stop it with no `repair record`
    # typed (promised-5: the command was typed 0 times in 97 real gate runs), and a pass closes the trail.
    rows = ("| unit | `if [ -f .fixed ]; then echo '3 passed'; exit 0; fi; echo 'FAILED tests/test_x.py::test_a'; exit 1`"
            " | verify | yes | ok | `true` | none | - |\n")
    stop = small_council_repo(tmp, "auto-stop", rows)
    _, run, _ = council(stop, "run", "open", "council-implement")
    run = run.strip()
    write_plan(run)
    council(stop, "state", "phase=build")
    codes = [council(stop, "gate", "unit")[0] for _ in range(3)]
    code, out, err = council(stop, "gate", "unit")
    check("gate: in a build, three failures of one gate stop it with no repair record typed",
          codes == [1, 1, 1] and code == 2 and "gate unit is stopped" in err, f"{codes} · {out}{err}")
    code, out, err = council(stop, "gate", "--all", "--at", "verify")
    check("gate --all: a stopped gate is skipped, named and counted, not run again",
          "gate unit: skipped" in out and "stopped" in out and out.count("FAIL (exit") == 0, out + err)
    code, out, err = council(stop, "repair", "record", "T1", "unit")
    check("repair record: an attempt the gate already recorded says so and exits 0", code == 0 and "already recorded" in out, out + err)
    fix = small_council_repo(tmp, "auto-resolve", rows)
    _, frun, _ = council(fix, "run", "open", "council-implement")
    frun = frun.strip()
    write_plan(frun)
    council(fix, "state", "phase=build")
    code, out, err = council(fix, "gate", "unit")
    check("gate: a failure in a build is recorded as an attempt, and says so last",
          code == 1 and "repair: task T1 attempt 1" in out, out + err)
    write(os.path.join(fix, ".fixed"), "")
    code, out, err = council(fix, "gate", "unit")
    code2, shown, _ = council(fix, "repair", "show", "T1")
    check("gate: the pass that follows closes the trail as resolved", code == 0 and "resolved" in shown.lower(), out + shown)
    os.remove(os.path.join(fix, ".fixed"))
    council(fix, "gate", "unit")                                  # a new failure: T1's trail is resolved, so a new one
    write(os.path.join(fix, ".fixed"), "")
    code, out, err = council(fix, "gate", "--all", "--at", "verify")
    check("gate --all: a pass closes the gate's open trail", code == 0 and "resolved" in out.lower(), out + err)
    check("state phase=build: the build starts on task 1, so its first failures have a task",
          "next: task 1" in read(os.path.join(frun, "session-state.md")), read(os.path.join(frun, "session-state.md")))
    os.remove(os.path.join(fix, ".fixed"))
    council(fix, "state", "next=write the receipt")
    code, out, err = council(fix, "gate", "unit")
    check("gate: with no task id in next:, a failure is said not counted — and how to name the task — with the gate's own exit",
          code == 1 and "not counted — no task id" in out and 'next="task <n>' in out, out + err)
    council(fix, "state", "next=task 3: the next one")
    with open(os.path.join(frun, "repairs.jsonl"), "a", encoding="utf-8", newline="") as f:
        f.write("{not json\n")
    code, out, err = council(fix, "gate", "unit")
    check("gate: a damaged repair trail is said once, even with a task id to count under",
          (out + err).count("council repair check") == 1, out + err)
    check("gate: a damaged repair trail is said, naming council repair check, and the gate still runs with its own exit code",
          code == 1 and "council repair check" in out + err, out + err)

    base = small_council_repo(tmp, "auto-baseline", rows)
    _, brun, _ = council(base, "run", "open", "council-implement")
    write_plan(brun.strip())
    council(base, "gate", "--all")                                # the baseline, before any change: unit already fails
    council(base, "state", "phase=build")
    code, out, err = council(base, "gate", "unit")
    check("gate: in a build, a failure naming only the baseline's failing tests is said, and not counted",
          code == 1 and "not counted — the same tests fail as at the baseline" in out, out + err)

@part("gates")
def gates_repair_stop(tmp):
    # In a build a failed gate names the exact repair record line; three recorded failures stop the gate
    # until the user's go is on record in their words
    repo = small_council_repo(tmp, "repairstop",
        "| unit | `if [ -f .fixed ]; then echo '3 passed'; exit 0; fi; echo 'FAILED tests/test_x.py::test_a - AssertionError'; exit 1`"
        " | grounding, verify | yes | ok | `true` | none | - |\n")
    code, run, _ = council(repo, "run", "open", "council-implement")
    run = run.strip()
    write_plan(run)
    council(repo, "state", "phase=build")
    code, out, _ = council(repo, "gate", "unit")
    check("gate <name>: a failure in a build records the attempt itself (task 1 when no next: names one)",
          code == 1 and "repair: task T1 attempt 1" in out, out)
    code, out, _ = council(repo, "gate", "before-1", "--", "exit 1")
    check("gate <name>: the intentionally red before-check is never called a repair attempt", "repair:" not in out, out)
    council(repo, "state", "next=task 2: export the rows")
    for _ in range(3):
        council(repo, "gate", "unit")
        council(repo, "repair", "record", "T2", "unit")
    code, out, err = council(repo, "gate", "unit")
    check("gate <name>: a gate whose repair trail stopped is refused, with the way forward",
          code == 2 and "gate unit is stopped" in err and "council repair show T2" in err
          and 'council repair allow unit --user-said "<their words>"' in err, out + err)
    before = len([e for e in events(run) if e[3] == "gate.finished"])
    council(repo, "gate", "unit")
    check("gate <name>: a refused gate runs nothing and records nothing",
          len([e for e in events(run) if e[3] == "gate.finished"]) == before, str(events(run)[-2:]))
    code, out, err = council(repo, "repair", "allow", "unit")
    check("repair allow: refused without the user's own words", code == 2 and "--user-said" in err, err)
    code, out, err = council(repo, "repair", "allow", "unit", "--user-said", "go on, try the other approach")
    allowed = read(os.path.join(run, "repair-allowances.tsv"))
    check("repair allow: records the user's go in their words, with an event",
          code == 0 and "go on, try the other approach" in allowed and "\tunit\tT2\t" in allowed
          and any(e[3] == "repair.allowed" and e[4] == "unit" for e in events(run)), out + err + allowed)
    code, out, err = council(repo, "gate", "unit")
    check("gate <name>: after the go the gate runs again, and a new failure goes under a new task id",
          code == 1 and "repair: task T2-2 attempt 1" in out, out + err)
    code, out, err = council(repo, "repair", "record", "T2-2", "unit")
    check("repair record: typing the record the gate already made changes nothing", code == 0 and "already recorded" in out, out + err)
    write(os.path.join(repo, ".fixed"), "")
    code, out, err = council(repo, "repair", "allow", "nosuch", "--user-said", "yes")
    check("repair allow: a gate with no stopped trail is refused", code == 2 and "nothing to allow" in err, err)

    # A second gate failing in the same task is named its own trail, one repair record takes
    two = small_council_repo(tmp, "repairtwo",
        "| unit | `echo 'FAILED tests/test_x.py::test_a'; exit 1` | verify | yes | ok | `true` | none | - |\n"
        "| logs | `echo 'ERROR could not reach cache'; exit 1` | verify | yes | ok | `true` | none | - |\n")
    code, trun, _ = council(two, "run", "open", "council-implement")
    write_plan(trun.strip())
    council(two, "state", "phase=build")
    council(two, "state", "next=task 1: read the rows")
    council(two, "gate", "unit")
    council(two, "repair", "record", "T1", "unit")
    code, out, _ = council(two, "gate", "logs")
    code2, out2, err2 = council(two, "repair", "record", "T1-logs", "logs")
    check("gate <name>: a second gate failing in the same task is recorded under its own task id (typing it changes nothing)",
          code == 1 and "repair: task T1-logs attempt 1" in out and code2 == 0 and "already recorded" in out2, out + out2 + err2)


@part("runs")
def runs_gitignore(tmp):
    # Every run open keeps run scratch and the user's words out of git — in a home with no .gitignore, in a
    # 0.6.0 home whose .gitignore predates asks/, in its own line endings — unless the user shares requests
    def status_lines(repo):
        return [l.strip() for l in git(repo, "status", "--short", "-uall").splitlines() if l.strip()]
    legacy = new_repo(tmp, "legacy-home")
    write(os.path.join(legacy, ".council", "council.config.md"), "# Council config (0.1 layout)\n")
    git(legacy, "add", "-A")
    git(legacy, "commit", "-q", "-m", "legacy council")
    lg_run = council(legacy, "run", "open", "council-implement")[1].strip()
    write(os.path.join(lg_run, "ask.md"), "# Ask — deploy\n## In your words\nuse my key and ship it\n")
    gi_lines = read(os.path.join(legacy, ".council", ".gitignore")).split()
    check("run open: a home with no .gitignore gets one that ignores runs/, asks/ and active-run before any words are written",
          {"runs/", "asks/", "active-run"} <= set(gi_lines)
          and not [l for l in status_lines(legacy) if "runs/" in l], " · ".join(status_lines(legacy)))
    council(legacy, "run", "close", "--status", "abandoned")
    old = new_repo(tmp, "home-0-6")
    write(os.path.join(old, ".council", "council.config.md"), "# Council config\n")
    write(os.path.join(old, ".council", "asks", "2026-09-10-old.md"), "# Ask — old\n")
    with open(os.path.join(old, ".council", ".gitignore"), "w", encoding="utf-8", newline="") as f:
        f.write("runs/\r\nactive-run")                           # CRLF, and no newline at the end
    git(old, "add", "-A")
    git(old, "commit", "-q", "-m", "0.6.0 home")
    code, out, _ = council(old, "doctor")
    check("doctor: warns when asks/ isn't ignored — the user's words would be committed",
          any(l.startswith("WARN") and "asks/" in l for l in out.splitlines()), out)
    _, old_run, old_err = council(old, "run", "open", "council-review")
    old_run = old_run.strip()
    with open(os.path.join(old, ".council", ".gitignore"), "rb") as f:
        raw = f.read()
    check("run open: a 0.6.0 home's .gitignore gains asks/ once, in its own CRLF endings, on a line of its own",
          raw == b"runs/\r\nactive-run\r\nasks/\r\n", repr(raw))
    check("run open: says so when it starts ignoring asks/ where requests are in git — and how to keep sharing them",
          "asks/" in old_err and "!asks/" in old_err, old_err)
    write(os.path.join(old_run, "ask.md"), "# Ask — New thing\n## In your words\nwords\n")
    council(old, "ask", "save")
    council(old, "run", "open", "council-plan", "--alongside")
    with open(os.path.join(old, ".council", ".gitignore"), "rb") as f:
        raw2 = f.read()
    check("run open: the new request stays out of git, and a second open adds nothing",
          raw2 == raw and status_lines(old) == ["M .council/.gitignore"], " · ".join(status_lines(old)) + repr(raw2))
    code, out, _ = council(old, "doctor")
    check("doctor: quiet about asks/ once it is ignored", not [l for l in out.splitlines() if "asks/" in l], out)
    shared = new_repo(tmp, "shared-asks")
    write(os.path.join(shared, ".council", "council.config.md"), "# Council config\n")
    write(os.path.join(shared, ".council", ".gitignore"), "runs/\nactive-run\n!asks/\n")
    council(shared, "run", "open", "council-review")
    code, out, _ = council(shared, "doctor")
    check("run open and doctor: a '!asks/' line — the user shares requests — is left alone",
          read(os.path.join(shared, ".council", ".gitignore")) == "runs/\nactive-run\n!asks/\n"
          and not [l for l in out.splitlines() if "asks/" in l], read(os.path.join(shared, ".council", ".gitignore")) + out)
    rooted = new_repo(tmp, "root-ignores")
    write(os.path.join(rooted, ".gitignore"), ".council/runs/\n.council/asks/\n.council/active-run\n")
    write(os.path.join(rooted, ".council", "council.config.md"), "# Council config\n")
    council(rooted, "run", "open", "council-review")
    check("run open: writes nothing when the project's own .gitignore already covers the council's scratch",
          not os.path.exists(os.path.join(rooted, ".council", ".gitignore")))
    code, out, _ = council(rooted, "doctor")
    check("doctor: quiet about runs/ and asks/ when the project's own .gitignore covers them",
          not [l for l in out.splitlines() if "runs/" in l or "asks/" in l], out)
    loose = os.path.join(tmp, "no-git-home")                          # research and post-game runs work outside git
    write(os.path.join(loose, ".council", "council.config.md"), "# Council config\n")
    for _ in range(3):
        council(loose, "run", "open", "council-research")
        council(loose, "run", "close", "--status", "abandoned")
    loose_gi = read(os.path.join(loose, ".council", ".gitignore")).split()
    code, out, _ = council(loose, "doctor")
    check("run open outside git: writes each ignore line once, and doctor finds them",
          sorted(loose_gi) == ["active-run", "asks/", "runs/"]
          and not [l for l in out.splitlines() if "runs/" in l or "asks/" in l], " ".join(loose_gi) + " · " + out)

@part("requests")
def requests_postgame_and_redaction(tmp):
    # A post-game's index hides earlier council work from its verifier
    append(os.path.join(req, "a.txt"), "three\n")
    code, rv, _ = council(req, "run", "open", "council-review")
    code, out, _ = council(req, "index", "--base", "HEAD")
    check("index: a review's index lists earlier council work", "## Earlier council work" in read(os.path.join(rv.strip(), "index.md")), out)
    council(req, "run", "close", "--status", "abandoned")
    code, pgr, _ = council(req, "run", "open", "council-postgame")
    pgr = pgr.strip()
    code, out, _ = council(req, "index", "--base", "HEAD")
    check("index: a post-game's index leaves earlier council work out — its verifier reads the file",
          "Earlier council work" not in read(os.path.join(pgr, "index.md")) and "left out" in out, out)
    write(os.path.join(pgr, "synthesis.md"), "# Synthesis\n## Kept\n## Drift on paper\n- nothing\n")
    code, out, _ = council(req, "check")
    check("check: a post-game with no quoted parts fails", code == 1 and "no quotes found" in out, out)

    # Redaction: the common secret shapes go; ordinary words stay
    secrets = ['password: "hunter2hunter2"', 'API_KEY="abcd1234efgh5678ijkl"', '{"api_key": "abcd1234efgh5678ijkl"}',
               "STRIPE=sk_live_not-a-real-key-000000", "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
               "postgres://admin:S3cretPassw0rd@db.example.com/app",
               "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop",
               "github_pat_11ABCDEFG0123456789_abcdefghijklmnopqrstuvwxyz"]
    keep = ["Add a task-list-component-for-dashboard page.", "Use the flask-sqlalchemy-extension-helper.",
            "Auth token: short-lived-JWT, 15 minutes.", "## Summary", "Also: add a retry to the deploy script.",
            "token_expiry: 2026-09-16T10:00", "Auth token: 15-minute-lifetime", "secret_santa_budget=120euros"]
    write(os.path.join(pgr, "ask.md"), "# Ask — Secrets\n## In your words\n" + "\n".join(secrets) + "\n"
          + " ".join(keep[:3]) + "\n" + "\n".join(keep[5:]) + "\n" + keep[3] + "\n-----BEGIN OPENSSH PRIVATE KEY-----\n"
          "b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZW\n" + keep[4] + "\n## Later, in your words\n")
    code, out, _ = council(req, "ask", "save")
    filed_s = [f for f in os.listdir(asks) if "secrets" in f]
    sbody = read(os.path.join(asks, filed_s[0])) if filed_s else ""
    leaked = [s for s in ["hunter2", "abcd1234", "sk_live_", "wJalrXUtnFEMI", "S3cretPassw0rd", "eyJhbGci", "github_pat_", "b3BlbnNz"]
              if s in sbody]
    check("ask save: redacts quoted passwords, JSON keys, live keys, AWS secrets, URL passwords, bearer tokens, key blocks",
          not leaked and "[redacted private key]" in sbody and "redacted 9" in out, str(leaked) + out)
    check("ask save: leaves ordinary words alone — task-list-…, flask-…, a token's description, text after a snipped key",
          all(k in sbody for k in keep), sbody)
    code, out, _ = council(req, "ask", "save")
    check("ask save: saving again in the same run re-files the same request — no copy",
          "(new)" in out and len([f for f in os.listdir(asks) if "secrets" in f]) == 1, out)
    council(req, "run", "close", "--status", "abandoned")

@part("filing")
def redaction_widened(tmp):
    # Redaction, widened: each token shape on its own (so only its own rule can catch it), secrets named by
    # their context, key blocks in any indentation, and the ordinary text around them left alone. Every
    # fake secret is assembled here at run time, so no file in the repo holds a real-looking key.
    rdr = new_repo(tmp, "redact")
    write(os.path.join(rdr, ".council", "council.config.md"), "# Council config\n")
    J = "".join
    shapes = [
        ("AWS key id", J(["AK", "IA", "EXAMPLE0NOTREAL0"]), "The deploy uses {} for S3."),
        ("AWS temporary key id", J(["AS", "IA", "EXAMPLE0NOTREAL0"]), "Today it is {} instead."),
        ("Google API key", J(["AI", "za", "EXAMPLE_not-a-real-key-000000000000"]), "Maps key {}"),
        ("GitHub token", J(["gh", "p_", "EXAMPLEnotarealtoken000000"]), "Use {} for the CI."),
        ("GitLab token", J(["gl", "pat-", "EXAMPLEnotarealtoken00"]), "push with {} please"),
        ("Slack bot token", J(["xo", "xb-", "000000000000-EXAMPLEnotreal"]), "bot: {}"),
        ("Slack app token", J(["xa", "pp-", "1-A000-EXAMPLEnotreal"]), "socket mode {}"),
        ("Slack webhook", J(["T00000000/B00000000/", "EXAMPLEnotarealhook000000"]), "post alerts to https://hooks." + "slack.com/services/{}"),
        ("OpenAI-style key", J(["sk", "-", "EXAMPLEnotarealkey000000"]), "the model key {}"),
        ("Stripe webhook secret", J(["wh", "sec_", "EXAMPLEnotarealsecret000"]), "signing with {}"),
        ("Google OAuth secret", J(["GOC", "SPX-", "EXAMPLE_not-a-real-000000"]), "client {}"),
        ("SendGrid key", J(["S", "G.", "EXAMPLEnotreal000000", ".", "EXAMPLEnotarealkey00000"]), "mail with {}"),
        ("npm token", J(["np", "m_", "EXAMPLEnotarealtoken0000000000000"]), "publish using {}"),
        ("PyPI token", J(["py", "pi-", "AgEIEXAMPLE-not-a-real-token-000000000000000"]), "upload with {}"),
        ("Hugging Face token", J(["h", "f_", "EXAMPLEnotarealtoken0000000000000"]), "model pull {}"),
        ("Telegram bot token", J(["0000000000", ":AA", "EXAMPLE_not-a-real-token-00000000"]), "alerts bot {}"),
        ("JWT", J(["ey", "JhbGciOiJIUzI1NiJ9.", "ey", "JzdWIiOiJleGFtcGxlIn0.", "EXAMPLEnotarealsignature"]), "the cookie holds {}"),
    ]
    context = [
        ("Bearer without a header", J(["EXAMPLEnot", "AREALopaque", "1234"]), "send it with Bearer {} in the header"),
        ("Authorization: Token", J(["b7d9", "0a1c"] * 5), "Authorization: Token {}"),
        ("Basic without a header", J(["dXNlcjpw", "YXNzd29yZA", "=="]), "then Basic {} for the proxy"),
        ("URL with a password and no user", J(["Rd", "pwExample", "4"]), "redis://:{}@localhost:6379/0"),
        ("'my password is'", J(["Tr4d", "3r!", "xyz"]), "my login is U1234567 and my password is {}"),
        ("'the secret key is'", J(["kwtD", "9x+Q", "EXAMPLE", "/k3y"] * 2), "and the secret key is {} for the bucket"),
        ("DB_PASS=", J(["Db", "Pa55", "word"]), "DB_PASS={}"),
        ("ENCRYPTION_KEY=", J(["gaS+", "EXAMPLE", "k3y/"] * 3), "ENCRYPTION_KEY={}"),
        ("AccountKey=", J(["znnJ", "Q2x0", "EXAMPLE"] * 6) + "==", "Protocol=https;AccountName=x;AccountKey={};Suffix=core"),
        ("PRIVATE_KEY=0x…", "0x" + "4f3a" * 16, "PRIVATE_KEY={}"),
        ("a quoted password with spaces", "correct horse battery 42", 'password: "{}"'),
        ("a password with no digit", J(["Winter", "IsComingSoon!"]), "password: {}"),
        ("the secret after a key id in a CSV row", J(["wJal", "rXUt", "nFEM", "I/K7", "MDEN", "G/bP", "xRfi", "CYEX", "AMPL", "EKEY"]),
         J(["AK", "IA", "EXAMPLE1NOTREAL1"]) + ",{}"),
    ]
    pk = "PRIVATE" + " KEY"
    b64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    body = [J(b64[(i * 37 + seed * 11) % 64] for i in range(64)) for seed in (1, 2, 3)]   # key-body-shaped lines
    blocks = ("- deploy key:\n  -----BEGIN OPENSSH " + pk + "-----\n  " + body[0] + "\n  -----END OPENSSH " + pk + "-----\n"
              "-----BEGIN PGP " + pk + " BLOCK-----\n\n" + body[1] + "\n=AbCd\n-----END PGP " + pk + " BLOCK-----\n"
              "```\n-----BEGIN RSA " + pk + "-----\n" + body[2] + "\nQmVlZkNha2Ux==\n-----END RSA " + pk + "-----\n```\n")
    keep = ["1. Switch the admin API to bearer authentication/authorization-headers.",
            '2. The line `token = request.headers.get("Authorization")` crashes.', "3. Set max_token=40960000.",
            "Start of a key I snipped:", "-----BEGIN RSA " + pk + "-----", "(rest removed)", "The build id, on its own line:", "SGVsbG9Xb3JsZEZyb21UaGVDb3VuY2lsMjAyNjA5MTc",
            "Then fix these folders:",
            "src/web/components/forms", "lib/pipeline/uploads", "InvoiceRetryScheduler",
            "session token: expires-after-15-minutes-of-idle", "access_key: AWS_ACCESS_KEY_ID",
            "Pin sk-learn-compat-shim-for-python312 in requirements.",
            "Fixed in commit 3f2a9c1e7b4d4e8a9c2f1a2b3c4d5e6f70819a2b.", "The order id is 123e4567-e89b-12d3-a456-426614174000.",
            "secret: /run/secrets/db_password", "api_key: settings.API_KEY", "token: ${GITHUB_TOKEN}",
            "Bearer tokens expire after an hour.", "Authorization: Basic authentication is fine here.",
            "secret_file: config/secrets/production-database.yaml", "token_count: 128000", "Password: required",
            "The token is valid for an hour.", "the API key is rotated-every-quarter"]
    rd_run = council(rdr, "run", "open", "council-review")[1].strip()
    write(os.path.join(rd_run, "ask.md"), "# Ask — Wire the services\n## In your words\n"
          + "\n".join(line.format(s) for _, s, line in shapes + context) + "\n" + blocks + "\n".join(keep) + "\nThanks!\n")
    code, out, _ = council(rdr, "ask", "save")
    rd_files = os.listdir(os.path.join(rdr, ".council", "asks")) if os.path.isdir(os.path.join(rdr, ".council", "asks")) else []
    rd_body = read(os.path.join(rdr, ".council", "asks", rd_files[0])) if rd_files else ""
    rd_words = rd_body.split("## In your words\n", 1)[-1]
    check("ask save: redacts each common token shape, written on its own",
          code == 0 and rd_body and not [l for l, s, _ in shapes if s in rd_body],
          "left: " + ", ".join(l for l, s, _ in shapes if s in rd_body) + " · " + out)
    check("ask save: redacts secrets named by what's around them — Authorization, Bearer, 'password is', DB_PASS=, AccountKey=, …",
          rd_body and not [l for l, s, _ in context if s in rd_body], "left: " + ", ".join(l for l, s, _ in context if s in rd_body))
    check("ask save: removes indented, PGP and short-tailed private-key blocks whole",
          rd_body and not [b for b in body + ["=AbCd", "QmVlZkNha2Ux=="] if b in rd_body] and "  [redacted private key]\n" in rd_body
          and rd_body.count("[redacted private key]") == 4 and "-----BEGIN" not in rd_body and "-----END" not in rd_body, rd_words)
    check("ask save: leaves the words around secrets alone — after a snipped key, auth wording, code, hashes, ids, paths, constants",
          rd_body and "\n".join(keep).replace("-----BEGIN RSA " + pk + "-----", "[redacted private key]") + "\nThanks!\n" in rd_words,
          rd_words[-1500:])
    check("ask save: the redaction count says to check for others",
          "redacted 35 secret-looking string(s)" in out and "check" in out.split("redacted 35", 1)[-1].split("\n", 1)[0], out)
    council(rdr, "run", "close", "--status", "abandoned")

    # Redaction's "ordinary text" rules never shield a real key, and never blank test output or code
    rdm = new_repo(tmp, "redact-more")
    write(os.path.join(rdm, ".council", "council.config.md"), "# Council config\n")
    orkey = J(["sk", "-or-v1-"]) + "0123abcd" * 8
    look_alike = [
        ("OpenRouter key in prose", orkey, "The model calls use {} now."),
        ("OpenRouter key after 'key:'", J(["sk", "-or-v1-"]) + "9f8e7d6c" * 8, "key: {}"),
        ("OpenRouter key in backticks", J(["sk", "-or-v1-"]) + "a1b2c3d4" * 8, "set `{}` in the env"),
        ("Langfuse key", J(["sk", "-lf-", "1a2b3c4d-5e6f-", "4a1b-9c2d-3e4f5a6b7c8d"]), "tracing: {}"),
        ("bot token (a dotted random value)", J(["MTA4NjY1ODk3", "NjU0MzIxMDk4Nz", ".GhIjKl.", "aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789ab"]),
         "DISCORD_TOKEN={}"),
        ("a numeric key", J(["84729103", "84756102"]), "api_key: {}"),
        ("base64 that starts with /", J(["/9Kq2mZ+X7rT0bLp", "W3eVn5sYc8HdJ1uA4gFiRoE6"]), "client_secret={}"),
        ("base64 that starts with / and holds another /", J(["/9Kq2mZX7rT0bLp/", "W3eVn5sYc8HdJ1uA4gFiRoE6"]), "client_secret={}"),
        ("a Django key with a bracket", J(["django-insecure-", "7f$k2(q9x!m@w3z^e8r#t1y+u5i-o0p=a4s6d"]), "SECRET_KEY={}"),
        ("a quoted Django key with a bracket", J(["q9x!m@w3z^e8r#t1y+", "u5i-o0p=a4s6d7f$k2)z"]), 'DJANGO_SECRET_KEY="{}"'),
        ("a Django key that starts like a call", J(["q9xm(w3z^e8r#t1y+", "u5i-o0p=a4s6d7f$k2z"]), "SECRET_KEY={}"),
    ]
    plain = ["--- PASS: TestHandleLoginRejectsExpiredTokens (0.00s)", "PASS: tests/test_auth.py::test_login",
             "All tests pass: 1234/1234", "Bypass: RateLimiterMiddleware for admin calls", "bypass: 12345678",
             "We use Compass: CompassNavigationService2 for maps.", "compass: NorthEast123",
             "In build.py, `pwd = os.getcwd()` returns the wrong folder in CI.", "PWD=/home/runner/work/app",
             "my pwd: /c/Users/me/project", "password = getpass.getpass()", "password = input('pw: ')",
             "password: env(DB_PASSWORD)", 'The line `password = request.form.get("password")` crashes on empty forms.',
             "passwd: /etc/passwd must not be readable", "access_key: AccessKeyProviderFactory should be renamed",
             "token: TokenRefreshScheduler", "The secret is: EverythingGoesThroughTheQueue",
             "Use a bearer AuthenticationMiddleware for the admin routes.", "Basic Authentication/Authorization headers are fine.",
             "token = self.config.auth.token_v2", "api_key = os.environ.get('API_KEY')",
             "The password is hashed-with-bcrypt-before-storage, keep that.",
             "The passphrase is the-same-one-we-use-for-staging"]
    pk_blocks = ("-----BEGIN RSA " + pk + "-----\n" + body[0] + "\n" + body[1][:22] + "\n-----END RSA " + pk + "-----\n"
                 "Here is the start of the deploy key:\n-----BEGIN OPENSSH " + pk + "-----\n"
                 "Comment: I cut the rest; the deploy script is below\nVersion: 2 of deploy.sh must stay\n"
                 'keys: "-----BEGIN ' + pk + '-----\n' + body[2] + '\n-----END ' + pk + '-----", "-----BEGIN ' + pk + '-----\n'
                 + body[0][::-1] + "\n-----END " + pk + '-----"\n'
                 "-----BEGIN EC " + pk + "-----\nExportQueueHealthChecker\nlib/jobs/exports\nThanks!\n")
    rm_run = council(rdm, "run", "open", "council-review")[1].strip()
    write(os.path.join(rm_run, "ask.md"), "# Ask — Keys and output\n## In your words\n"
          + "\n".join(line.format(s) for _, s, line in look_alike) + "\n" + "\n".join(plain) + "\n" + pk_blocks)
    code, out, _ = council(rdm, "ask", "save")
    rm_files = os.listdir(os.path.join(rdm, ".council", "asks")) if os.path.isdir(os.path.join(rdm, ".council", "asks")) else []
    rm_body = read(os.path.join(rdm, ".council", "asks", rm_files[0])) if rm_files else ""
    check("ask save: redacts keys that read like word lists, dotted names, numbers, paths or calls — and counts them",
          code == 0 and rm_body and not [l for l, s, _ in look_alike if s in rm_body] and "redacted 16 " in out,
          "left: " + ", ".join(l for l, s, _ in look_alike if s in rm_body) + " · " + out)
    check("ask save: leaves test output, pwd, bypass, code calls, CamelCase names and /-joined words alone",
          rm_body and not [p for p in plain if p + "\n" not in rm_body],
          "changed: " + " | ".join(p for p in plain if p + "\n" not in rm_body))
    check("ask save: a key's short last line and its END line go; the notes after a snipped key stay; two keys on one line both go",
          rm_body and body[1][:22] not in rm_body and body[2] not in rm_body and body[0][::-1] not in rm_body
          and "-----END" not in rm_body and rm_body.count("[redacted private key]") == 5
          and "Comment: I cut the rest; the deploy script is below\nVersion: 2 of deploy.sh must stay\n" in rm_body
          and "[redacted private key]\nExportQueueHealthChecker\nlib/jobs/exports\nThanks!\n" in rm_body,
          rm_body.split("tracing:", 1)[-1][-900:])
    council(rdm, "run", "close", "--status", "abandoned")

@part("requests")
def requests_bookkeeping(tmp):
    # The request's bookkeeping: continues:, refusals, one section per run, the close warning
    code, crun, _ = council(req, "run", "open", "council-implement")
    crun = crun.strip()
    write(os.path.join(crun, "ask.md"), "# Ask — go\n## In your words\n(no new words)\n")
    code, _, err = council(req, "ask", "save")
    check("ask save: (no new words) that names no request is refused", code == 2 and "names no request" in err, err)
    write(os.path.join(crun, "ask.md"), f"# Ask — go\ncontinues: `.council/asks/{filed[0]}`\n## In your words\nAlso a CSV header row.\n")
    code, out, _ = council(req, "ask", "save")
    code2, out2, _ = council(req, "ask", "save")
    sections = read(os.path.join(asks, filed[0])).count(", run " + os.path.basename(crun))
    check("ask save: follows ask.md's continues: line, and a second save replaces this run's section",
          "(continued)" in out and "(continued)" in out2 and sections == 1
          and f"ask: .council/asks/{filed[0]}" in read(os.path.join(crun, "session-state.md")), out + out2)
    council(req, "state", "ask=README.md")
    code, _, err = council(req, "ask", "save")
    check("ask save: never writes to a file outside .council/asks/", code == 2 and "copy the words into ask.md" in err, err)
    council(req, "run", "close", "--status", "abandoned")
    council(req, "run", "open", "council-implement")
    council(req, "state", f"ask=.council/asks/{filed[0]}")
    code, out, err = council(req, "run", "close")
    check("run close: warns when a continuing run never filed its words", "no request was filed" in err, err)

@part("filing")
def filed_request_paths(tmp):
    # The filed request stays inside asks/, in every legitimate spelling; a re-save replaces only its own run's words
    ap = new_repo(tmp, "askpaths")
    readme = "# Project\nImportant tracked readme.\n"
    write(os.path.join(ap, "README.md"), readme)
    write(os.path.join(ap, ".council", "council.config.md"), "# Council config\n")
    git(ap, "add", "-A")
    git(ap, "commit", "-q", "-m", "i")
    code, fp_run, _ = council(ap, "run", "open", "council-plan")
    fp_run = fp_run.strip()
    write(os.path.join(fp_run, "ask.md"), "# Ask — CSV export\n## In your words\nWe need CSV export.\n")
    council(ap, "ask", "save")
    council(ap, "run", "close")
    ap_asks = os.path.join(ap, ".council", "asks")
    ap_file = sorted(os.listdir(ap_asks))[0] if os.path.isdir(ap_asks) else "?"
    ap_rel = ".council/asks/" + ap_file
    code, tr, _ = council(ap, "run", "open", "council-review")
    tr = tr.strip()
    write(os.path.join(tr, "ask.md"), "# Ask — More\ncontinues: .council/asks/../../README.md\n## In your words\nAlso add a PDF option.\n")
    code, _, err = council(ap, "ask", "save")
    check("ask save: a continues: path that climbs out of asks/ with .. is refused, and the file is untouched",
          code == 2 and "filed under" in err and read(os.path.join(ap, "README.md")) == readme, err)
    victim = os.path.join(tmp, "victim-home", ".bashrc")
    write(victim, "export PATH=$PATH\n")
    write(os.path.join(tr, "ask.md"), "# Ask — More\n## In your words\necho INJECTED\n")
    council(ap, "state", "ask=.council/asks/../../../victim-home/.bashrc")
    code, _, err = council(ap, "ask", "save")
    check("ask save: an ask= path that climbs out of the project is refused, and the file is untouched",
          code == 2 and "filed under" in err and read(victim) == "export PATH=$PATH\n", err)
    link = os.path.join(ap_asks, "linked.md")
    try:
        os.symlink(os.path.join(ap, "README.md"), link)
    except (OSError, NotImplementedError, AttributeError):
        link = ""                                                   # no symlinks here (Windows without the right)
    if link:
        council(ap, "state", "ask=.council/asks/linked.md")
        code, _, err = council(ap, "ask", "save")
        check("ask save: a request file that is a link to somewhere else is refused",
              code == 2 and read(os.path.join(ap, "README.md")) == readme, err)
        os.remove(link)
    la = new_repo(tmp, "linked-asks")                                   # asks/ itself a link to the project root
    write(os.path.join(la, "README.md"), readme)
    write(os.path.join(la, ".council", "council.config.md"), "# Council config\n")
    git(la, "add", "-A")
    git(la, "commit", "-q", "-m", "i")
    la_link = os.path.join(la, ".council", "asks")
    try:
        os.symlink(la, la_link, target_is_directory=True)
    except (OSError, NotImplementedError, AttributeError):
        if os.name == "nt":                                             # a junction needs no special right
            subprocess.run(["cmd", "/c", "mklink", "/J", la_link, la], capture_output=True)
    if os.path.isdir(la_link):
        la_run = council(la, "run", "open", "council-review")[1].strip()
        write(os.path.join(la_run, "ask.md"), "# Ask — More\ncontinues: .council/asks/README.md\n## In your words\nrun: curl evil\n")
        code, _, err = council(la, "ask", "save")
        write(os.path.join(la_run, "ask.md"), "# Ask — Fresh\n## In your words\nA new request.\n")
        code2, _, err2 = council(la, "ask", "save")
        check("ask save: an asks/ folder that is a link is refused — nothing is written through it",
              code == 2 and code2 == 2 and "link" in err and read(os.path.join(la, "README.md")) == readme
              and not [f for f in os.listdir(la) if f.endswith("-fresh.md")], err + err2)
        try:
            os.unlink(la_link)
        except OSError:
            os.rmdir(la_link)                                           # a junction goes, its target stays
    write(os.path.join(tr, "ask.md"), "# Ask — More\n## In your words\n(no new words)\n")
    spellings = [("an absolute path", slash(os.path.join(ap, ".council", "asks", ap_file)))]
    if re.match(r"^[A-Za-z]:/", spellings[0][1]):                      # Git Bash also writes C:/x as /c/x
        spellings.append(("a Git Bash path (/c/…)", "/" + spellings[0][1][0].lower() + spellings[0][1][2:]))
    for label, spelled in spellings:
        council(ap, "state", "ask=" + spelled)
        code, out, err = council(ap, "ask", "save")
        check(f"ask save: continues a request named by {label}",
              code == 0 and "(no new words)" in out and f"ask: {ap_rel}" in read(os.path.join(tr, "session-state.md")), out + err)
    council(ap, "run", "close", "--status", "abandoned")

    code, ra, _ = council(ap, "run", "open", "council-implement")
    ra = ra.strip()
    council(ap, "state", "ask=" + ap_rel)
    write(os.path.join(ra, "ask.md"), "# Ask — build\n## In your words\nAlso add a PDF option.\n")
    council(ap, "ask", "save")
    code, rb, _ = council(ap, "run", "open", "council-review", "--alongside")
    rb = rb.strip()
    council(ap, "state", "--run", rb, "ask=" + ap_rel)
    write(os.path.join(rb, "ask.md"), "# Ask — r\n## In your words\nKeep the XLSX path too.\n")
    council(ap, "ask", "save", "--run", rb)
    write(os.path.join(ra, "ask.md"), "# Ask — build\n## In your words\nAlso add a PDF option, with page numbers.\n")
    code, out, _ = council(ap, "ask", "save", "--run", ra)
    body = read(os.path.join(ap_asks, ap_file))
    check("ask save: an older run saving again replaces only its own section — a later run's words stay",
          code == 0 and "(continued)" in out and "Keep the XLSX path too." in body
          and "with page numbers." in body and "Also add a PDF option.\n" not in body
          and body.count(", run " + os.path.basename(ra)) == 1 and body.count(", run " + os.path.basename(rb)) == 1, out + body)
    append(os.path.join(ap_asks, ap_file), "\n## 2026-09-17 — council-review, run " + os.path.basename(ra) + "-2\nA run whose name starts the same.\n")
    council(ap, "ask", "save", "--run", ra)
    body = read(os.path.join(ap_asks, ap_file))
    check("ask save: a re-save leaves a run whose folder name merely starts the same alone",
          "A run whose name starts the same." in body and body.count(", run " + os.path.basename(ra) + "\n") == 1, body)
    code, out, _ = council(ap, "ask", "save", "--run", fp_run)
    body = read(os.path.join(ap_asks, ap_file))
    check("ask save: the run that filed a request can re-file it without losing later runs' words",
          code == 0 and body.count("We need CSV export.") == 1 and "Keep the XLSX path too." in body
          and "with page numbers." in body and "A run whose name starts the same." in body
          and body.startswith("# Ask — CSV export\nrun: " + os.path.basename(fp_run) + "\n"), out + body)
    council(ap, "run", "close", "--run", rb, "--status", "abandoned")
    council(ap, "run", "close", "--run", ra, "--status", "abandoned")
    hs = new_repo(tmp, "ask-headings")                  # a dated heading inside the user's words is not a run's section
    write(os.path.join(hs, ".council", "council.config.md"), "# Council config\n")
    hp = council(hs, "run", "open", "council-plan")[1].strip()
    write(os.path.join(hp, "ask.md"), "# Ask — Release notes\n## In your words\nWrite release notes.\n")
    council(hs, "ask", "save")
    council(hs, "run", "close")
    hs_asks = os.path.join(hs, ".council", "asks")
    hs_rel = ".council/asks/" + (sorted(os.listdir(hs_asks))[0] if os.path.isdir(hs_asks) else "?")
    ha = council(hs, "run", "open", "council-implement")[1].strip()
    council(hs, "state", "ask=" + hs_rel)
    write(os.path.join(ha, "ask.md"), "# Ask — b\n## In your words\nUse this layout:\n## 2026-09-01 — hotfix, run migrations\n"
                                      "A line under it.\n")
    council(hs, "ask", "save")
    hb = council(hs, "run", "open", "council-review", "--alongside")[1].strip()
    council(hs, "state", "--run", hb, "ask=" + hs_rel)
    write(os.path.join(hb, "ask.md"), "# Ask — r\n## In your words\nKeep the XLSX path too.\n")
    council(hs, "ask", "save", "--run", hb)
    council(hs, "ask", "save", "--run", ha)
    hbody = read(os.path.join(hs, hs_rel))
    check("ask save: a dated heading in the user's own words is not another run's section — a re-save writes them once",
          hbody.count("A line under it.") == 1 and hbody.count("Keep the XLSX path too.") == 1, hbody)
    write(os.path.join(ha, "ask.md"), "# Ask — b\n## In your words\n(no new words)\n")
    code, out, _ = council(hs, "ask", "save", "--run", ha)
    check("ask save: '(no new words)' keeps the words this run saved before",
          code == 0 and "(no new words)" in out and read(os.path.join(hs, hs_rel)) == hbody, out + read(os.path.join(hs, hs_rel)))
    council(hs, "run", "close", "--run", hb, "--status", "abandoned")
    council(hs, "run", "close", "--run", ha, "--status", "abandoned")
    code, rs, _ = council(ap, "run", "open", "council-review")
    rs = rs.strip()
    title_key = "sk" + "_live_" + "AbCdEfGhIjKlMnOpQrStUvWx"     # built at run time: not a real key's text
    write(os.path.join(rs, "ask.md"), f"# Ask — rotate {title_key}\n## In your words\nPlease rotate it.\n")
    code, out, _ = council(ap, "ask", "save")
    check("ask save: a secret in the title never reaches the file name",
          code == 0 and "-rotate" in out and "abcdefghij" not in out.lower() and "live" not in out, out)
    council(ap, "run", "close", "--status", "abandoned")

@part("requests")
def requests_war_room(tmp):
    # A war room's round 2: collect waits for a running seat; a fresh round-2 worker counts as its seat
    code, wr, _ = council(req, "run", "open", "council-plan")
    wr = wr.strip()
    write_plan(wr, selected=("leach",))
    write(os.path.join(wr, "brief.md"), "# Brief\n## Seats\n### leach — Data (Leach)\n- ref: none\n- out: seats/leach.md\n")
    write(os.path.join(wr, "seats", "leach.md"), "# Leach — Data (council-plan)\nref: none\n## Index\n1 · must · Principle 1 · a.txt:1 · x\n")
    write(os.path.join(wr, "debate.md"), "# War room\n## Seats\n### leach-r2 — Data (Leach), round 2\n- ref: none\n- out: seats/leach-r2.md\n")
    council(req, "seat", "leach", "done", "agent=w1", "tokens=20000")
    council(req, "seat", "leach", "running", "agent=w1", "note=round 2")
    code, out, _ = council(req, "collect")
    check("collect: while round 2 runs it says wait, not fix", code == 1 and "still working" in out and "fix the rows" not in out, out)
    council(req, "seat", "leach", "done", "tokens=5000")
    council(req, "seat", "leach-r2", "done", "agent=w9", "tokens=4000")
    write(os.path.join(wr, "seats", "leach-r2.md"), "# Leach — Data (council-plan, round 2)\nref: none\n## Index\n1 · hold · P1 x#1 · a.txt:1 · y\n")
    write(os.path.join(wr, "synthesis.md"), "# Synthesis\n## Kept\n1 · must · Principle 1 · a.txt:1 · x · from: leach#1\n")
    council(req, "run", "close")
    code, out, _ = council(req, "ledger")
    check("ledger: a fresh round-2 worker counts as its seat and raises nothing new",
          "leach-r2" not in out and re.search(r"\tleach-r2\t0\t", read(os.path.join(req, ".council", "ledger.tsv"))) is not None, out)

    # Pasted headings stay in the words; the quote check's reach; collect with a fresh round-2 worker
    code, hr, _ = council(req, "run", "open", "council-research")
    write(os.path.join(hr.strip(), "ask.md"), "# Ask — From the PR\n## In your words\n## Summary\nAdd CSV export to the reports page.\n"
          "## Acceptance\n- admins only\n")
    code, out, err = council(req, "ask", "save")
    pr_file = next((f for f in os.listdir(asks) if "from-the-pr" in f), "")
    check("ask save: words that open with a pasted '## Summary' are filed whole",
          code == 0 and bool(pr_file) and "## Acceptance" in read(os.path.join(asks, pr_file)), out + err)
    council(req, "run", "close")
    code, hr2, _ = council(req, "run", "open", "council-implement")
    hr2 = hr2.strip()
    write(os.path.join(hr2, "ask.md"), f"# Ask — more\ncontinues: .council/asks/{pr_file}\n## In your words\n"
          "Also, from the issue:\n## Details\n- PDF option too\n")
    code, out, _ = council(req, "ask", "save")
    filed_pr = read(os.path.join(asks, pr_file))
    check("ask save: a continued request keeps a pasted heading and the lines under it",
          "(continued)" in out and "## Details" in filed_pr and "- PDF option too" in filed_pr, out + filed_pr)
    write(os.path.join(hr2, "synthesis.md"), "# Synthesis\n## Kept\n"
          "1 · P2 · Principle 1 · a.txt:1 · drops the user's quote: it shows the raw id\n"
          '2 · must · ask · reports · export · quote: "SV export to"\n')
    code, out, _ = council(req, "check")
    check("check: only a request part is quote-checked, and a quote inside a longer word fails",
          "synthesis#1  quote" not in out and "synthesis#2  quote  NOT-IN-THE-REQUEST" in out, out)
    council(req, "run", "close")
    code, sq, _ = council(req, "run", "open", "council-postgame")
    sq = sq.strip()
    write(os.path.join(sq, "ask.md"), f"# Ask — check\ncontinues: .council/asks/{pr_file}\n## In your words\n(no new words)\n")
    write(os.path.join(sq, "synthesis.md"), '# Synthesis\n## Kept\n1 · must · ask · reports · export · quote: "Add CSV export to the reports page."\n')
    code, out, _ = council(req, "check")
    check("check: follows ask.md's continues: line before the request is filed", code == 0 and "synthesis#1  quote  ok" in out, out)
    council(req, "run", "close", "--status", "abandoned")
    code, sq2, _ = council(req, "run", "open", "council-postgame")
    sq2 = sq2.strip()
    write(os.path.join(sq2, "ask.md"), "# Ask — dark\n## In your words\nDark mode.\n## Later, in your words\n")
    write(os.path.join(sq2, "synthesis.md"), '# Synthesis\n## Kept\n1 · must · ask · ui · dark · quote: "Dark mode."\n')
    code, out, _ = council(req, "check")
    check("check: a one-line request quoted whole passes", code == 0 and "synthesis#1  quote  ok" in out, out)
    council(req, "run", "close", "--status", "abandoned")
    code, fr, _ = council(req, "run", "open", "council-plan")
    fr = fr.strip()
    write(os.path.join(fr, "brief.md"), "# Brief\n## Seats\n### leach — Data (Leach)\n- ref: none\n- out: seats/leach.md\n")
    write(os.path.join(fr, "seats", "leach.md"), "# Leach — Data (council-plan)\nref: none\n## Index\n1 · must · Principle 1 · a.txt:1 · x\n")
    write(os.path.join(fr, "debate.md"), "# War room\n## Seats\n### leach-r2 — Data (Leach), round 2\n- ref: none\n- out: seats/leach-r2.md\n")
    council(req, "seat", "leach", "done", "agent=w1", "tokens=1000")
    council(req, "seat", "leach-r2", "failed", "agent=w9", "note=died")
    code, out, _ = council(req, "collect")
    check("collect: a fresh round-2 worker is judged by its own row", code == 1 and "state:failed" in row(out, "leach-r2"), out)
    council(req, "seat", "leach", "failed", "note=interrupted")
    council(req, "seat", "leach-r2", "done", "agent=w9", "tokens=9000")
    write(os.path.join(fr, "seats", "leach-r2.md"), "# Leach — Data (council-plan, round 2)\nref: none\n## Index\n1 · hold · P1 x#1 · a.txt:1 · y\n")
    code, out, _ = council(req, "collect")
    check("collect: once a fresh round-2 worker is done, the lost round-1 seat is judged by its file",
          code == 0 and "all 2 seats in order" in out, out)
    council(req, "run", "close", "--status", "abandoned")

@part("filing")
def close_claim_index(tmp):
    # Closing a synthesis run warns about an absent or outdated claim index without rebuilding it.
    stale_repo = new_repo(tmp, "stale-claims")
    write(os.path.join(stale_repo, ".council", "council.config.md"), "# Council config\n")
    _, stale_run, _ = council(stale_repo, "run", "open", "council-review")
    stale_run = stale_run.strip()
    write(os.path.join(stale_run, "synthesis.md"), "# Synthesis\n## Kept\n(none)\n## Cut\n(none)\n")
    warning = "the claim index is missing or out of date"
    code, _, err = council(stale_repo, "run", "close", "--run", stale_run)
    check("close: missing claims warn with an explicit run rebuild command",
          code == 0 and warning in err and "evidence build --run " + os.path.basename(stale_run) in err
          and not os.path.exists(os.path.join(stale_run, "claims.jsonl")), err)
    council(stale_repo, "evidence", "build", "--run", stale_run)
    code, _, err = council(stale_repo, "run", "close", "--run", stale_run)
    check("close: a current claim index does not warn", code == 0 and warning not in err, err)
    index_before = read(os.path.join(stale_run, "claims.jsonl"))
    for source in ("synthesis.md", "verify-1-a.md"):
        path = os.path.join(stale_run, source)
        write(path, read(path) or "# Verification\n")
        newer = os.stat(os.path.join(stale_run, "claims.jsonl")).st_mtime + 5
        os.utime(path, (newer, newer))
        code, _, err = council(stale_repo, "run", "close", "--run", stale_run)
        check("close: newer " + source + " warns without changing the index",
              code == 0 and warning in err and read(os.path.join(stale_run, "claims.jsonl")) == index_before, err)
        os.utime(path, (newer - 10, newer - 10))

    # Closing also detects deleted sources, which cannot be caught by comparing
    # the mtimes of files that remain beside the index.
    deleted_repo = new_repo(tmp, "deleted-claim-source")
    write(os.path.join(deleted_repo, ".council", "council.config.md"), "# Council config\n")
    _, deleted_run, _ = council(deleted_repo, "run", "open", "council-review")
    deleted_run = deleted_run.strip()
    write(os.path.join(deleted_run, "synthesis.md"), "# Synthesis\n## Kept\n"
          "1 · P2 · principle · source.py:1 · indexed claim\n## Cut\n(none)\n")
    write(os.path.join(deleted_run, "verify-1.md"), "# Verification\n| # | Item | Verdict | Evidence |\n"
          "|---|---|---|---|\n| 1 | claim | CONFIRMED | checked source.py:1 |\n")
    council(deleted_repo, "evidence", "build", "--run", deleted_run)
    code, _, err = council(deleted_repo, "run", "close", "--run", deleted_run)
    check("close: current verifier-backed claim index does not warn",
          code == 0 and warning not in err, err)
    os.unlink(os.path.join(deleted_run, "verify-1.md"))
    code, _, err = council(deleted_repo, "run", "close", "--run", deleted_run)
    check("close: a deleted verifier source warns even when remaining sources are older",
          code == 0 and warning in err, err)
    write(os.path.join(deleted_run, "verify-1.md"), "# Verification\n| # | Item | Verdict | Evidence |\n"
          "|---|---|---|---|\n| 1 | claim | CONFIRMED | checked source.py:1 |\n")
    council(deleted_repo, "evidence", "build", "--run", deleted_run)
    os.unlink(os.path.join(deleted_run, "synthesis.md"))
    code, _, err = council(deleted_repo, "run", "close", "--run", deleted_run)
    check("close: a deleted synthesis source warns", code == 0 and warning in err, err)

@part("runs")
def runs_usage(tmp):
    # Usage
    code, out, _ = council(repo, "help")
    check("help: prints the command list", code == 0 and "council run open" in out and "council doctor" in out, out)
    code, _, err = council(repo, "frobnicate")
    check("an unknown command is an error", code == 2 and "unknown command" in err, err)
    took = []
    for args in [("home", "x"), ("run", "open", "council-review", "x"), ("run", "close", "x"), ("run", "status", "x"),
                 ("seat", "a", "done", "x"), ("index", "x"), ("gate", "--all", "x"), ("gate", "ok", "--at", "verify"),
                 ("gates", "x"), ("changed", "x"), ("collect", "x"), ("check", "no-such-file.md"), ("map", "status", "x"),
                 ("fingerprint", "x"), ("memory", "check", "x"), ("ask", "save", "a", "b"), ("ledger", "5", "x"),
                 ("doctor", "x"), ("version", "x"), ("help", "x"), ("doctor", "--frobnicate"), ("run", "close", "--base", "main"),
                 ("run", "status", "--at=verify"), ("index", "--", "x"), ("doctor", "--all=yes"), ("run", "close", "--status="),
                 ("run", "resume", "x"), ("run", "resume", "--status", "paused"), ("status", "x"), ("status", "--all"),
                 ("correct", "a", "x"), ("cap", "x"), ("cap", "--session", "s1"), ("cap", "allow", "1", "2", "--user-said", "go"),
                 ("cap", "check", "x"), ("cap", "check", "--run", "x"), ("cap", "check", "--user-said", "go")]:
        code, out, err = council(repo, *args)
        if code != 2 or not err.strip():
            took.append(" ".join(args) + f" (exit {code})")
    check("every command refuses a word or flag it doesn't take: exit 2, with a message", not took, "; ".join(took))

parser = argparse.ArgumentParser(description="Helper evals: run bin/council against scaffolded git repos.")
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
    sys.exit("run_cli.py: %s has no @part(...) group, so it would never run" % ", ".join(stray))
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
    print("[SKIP] bash or git not on PATH — helper evals need both; nothing was checked")
    sys.exit(0 if opts.allow_skip else 3)
with tempfile.TemporaryDirectory() as tmp:
    tmp = os.path.realpath(tmp)   # a runner's TEMP may be an 8.3 name (RUNNER~1); git prints the long one
    for group, block in PARTS:
        if group in chosen and (only is None or block.__name__ in only):
            block(tmp)

passed = sum(1 for ok, *_ in results if ok)
if passed != len(results):                     # the failures again, so none scrolls out of sight
    print("\nFailed:")
    for ok, name, detail in results:
        if not ok:
            print(result_line(ok, name, detail))
if BASH:
    print(f"\nbash: {BASH} ({subprocess.run([BASH, '-c', 'echo $BASH_VERSION'], capture_output=True, text=True).stdout.strip()})")
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
