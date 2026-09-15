#!/usr/bin/env python3
"""Helper evals for the Small Council — run bin/council against scaffolded git repos.

Needs bash and git; no LLM, no network. Covers:
  - the council home: main checkout, linked worktree, outside git;
  - runs: open, update, close; a second in-progress run on one tree refused without --alongside;
    commands that never guess between runs; paused runs; session ids; init creating the home; an old
    open run found behind many newer closed ones;
  - the change index: files, symbols (code only, shell functions included), callers, tests;
  - gates judged by exit code, with the command passed intact, and table cells that never shift;
  - seat-file collection: ref: proof of reading (paired seats too), caps, broken citations, list-style
    and unreadable index lines, failed and re-dispatched workers;
  - citation and origin checks; map status; the drift doctor.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "bin", "council")
BASH = shutil.which("bash")
GIT = shutil.which("git")
GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME="eval", GIT_AUTHOR_EMAIL="eval@example.invalid",
               GIT_COMMITTER_NAME="eval", GIT_COMMITTER_EMAIL="eval@example.invalid")
for var in ("COUNCIL_RUN", "CLAUDE_CODE_SESSION_ID"):   # never inherit the session the eval runs in
    GIT_ENV.pop(var, None)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
results = []


def check(name, ok, detail=""):
    results.append((ok, name, detail))


def council(cwd, *args, env=None):
    p = subprocess.run([BASH, CLI, *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=dict(GIT_ENV, **(env or {})), timeout=120)
    return p.returncode, p.stdout, p.stderr


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


def row(out, slug):
    m = re.search(rf"^{slug}\s.*$", out, re.MULTILINE)
    return m.group(0) if m else ""


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
| must | `exit 4` | strict | yes | ok | — | none |
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

if not BASH or not GIT:
    print("[SKIP] bash or git not on PATH — helper evals need both")
    sys.exit(0)

with tempfile.TemporaryDirectory() as tmp:
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

    # State
    code, out, _ = council(repo, "state", "phase=prepare", "next=build the index")
    st = read(os.path.join(run, "session-state.md"))
    check("state: updates header fields", code == 0 and "phase: prepare" in st and "next: build the index" in st, st)
    code, _, err = council(repo, "state", "status=bogus")
    check("state: rejects an invalid status", code == 2, err)
    code, _, err = council(repo, "state", "no-equals-sign")
    check("state: rejects a bare word", code == 2, err)

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
    check("gate: prints a failure excerpt, not the whole output", "Error: boom" in out, out)
    check("gate: saves the full output", "Error: boom" in read(os.path.join(gates, "bad.txt")))
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
    check("gate --all --at: a gate with no Run-at value isn't run", "gate anytime" not in out, out)
    check("gate --all: skips a gate the config marks not runnable", "gate broken: skipped" in out, out)
    check("gate --all: skips a gate init never probed (it needs credentials)",
          "gate stripe: skipped" in out and not os.path.isfile(os.path.join(gates, "stripe.txt")), out)
    check("gate --all: never runs a gate with deploy, cost or hardware side effects",
          "gate ship: skipped — side effects" in out and not os.path.isfile(os.path.join(gates, "ship.txt")), out)
    check("gate --all: a row whose columns shifted never runs",
          "gate leaky: skipped — its row has" in out and not os.path.isfile(os.path.join(gates, "leaky.txt")), out)
    check("gate --all: runs only side effects on the safe list",
          "gate bill: skipped — side effects: billable API calls" in out and not os.path.isfile(os.path.join(gates, "bill.txt")), out)
    check("gate --all: says how many ran and how many were skipped", "gates: 2 ran, 5 skipped" in out, out)
    code, out, _ = council(repo, "gate", "ship")
    check("gate <name>: runs a side-effect gate when named, with a warning", code == 0 and "side effects (deploy, network)" in out, out)
    code, out, _ = council(repo, "gate", "--all", "--at", "strict")
    check("gate --all: a failing mandatory gate fails the set", code == 1 and "a mandatory gate failed" in out, out)
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
    check("seat: progress line counts done agents and tokens", "agents: 2 of 2 done" in out and "~76k tokens so far" in out, out)
    code, out, _ = council(repo, "seat", "ghost", "skipped", "note=no surface")
    check("seat: skipped seats don't count as agents", code == 0 and "agents: 2 of 2 done" in out, out)
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
    council(repo, "seat", "beck", "running", "agent=a3")
    code, out, _ = council(repo, "collect")
    check("collect: a seat that is running again is a hole, file or not", code == 1 and "state:running" in row(out, "beck"), out)
    code, out, _ = council(repo, "seat", "beck", "done", "tokens=10000")
    check("seat: a re-dispatched worker adds its tokens instead of replacing them", "agents: 3 of 3 done" in out and "~86k tokens so far" in out, out)

    # Memory: scopes and anchors
    write(os.path.join(repo, ".council", "conventions.md"),
          "# Conventions\n## Accepted Patterns (AP) — intentional; never flag these\n"
          "### AP-1: median returns the upper middle on purpose\n**Pattern:** even lists return the upper middle · **Why:** the spec\n"
          "**Scope:** src/stats.py, beck · **Anchor:** src/stats.py:7\n"
          "### AP-2: reports never round\n**Pattern:** raw numbers · **Why:** the users asked\n**Scope:** src/report.py · **Anchor:** summary\n"
          "### AP-3: sessions are re-read on every request\n**Pattern:** no session cache · **Why:** revocation\n**Scope:** **/auth/**, ghost\n"
          "## Enforced Conventions (EC) — always / never rules\n"
          "### EC-1: every module has a docstring\n**Rule:** always · **Why:** tooling\n"
          "### EC-2: no global caches\n**Rule:** never · **Why:** tests\n**Scope:** src/cache/** · **Anchor:** src/cache/store.py:3\n"
          "## Proposed — awaiting the user's yes/no\n")
    code, out, _ = council(repo, "memory")
    check("memory: prints a one-line index with scopes and anchors",
          "AP-1 · median returns the upper middle on purpose · scope: src/stats.py, beck · anchor: src/stats.py:7" in out
          and "EC-1 · every module has a docstring · every run" in out and out.count("\n") == 5, out)
    code, out, _ = council(repo, "memory", "select", "src/stats.py")
    check("memory select: a path pulls its scoped entries plus the every-run ones",
          "AP-1" in out and "EC-1" in out and "AP-2" not in out and "EC-2" not in out and "1 scoped and 1 every-run entries of 5" in out, out)
    code, out, _ = council(repo, "memory", "select", "auth/session.py")
    check("memory select: **/ also matches a path at the repo root", "AP-3" in out, out)
    code, out, _ = council(repo, "memory", "select", "beck")
    check("memory select: a seat slug pulls its entries", "AP-1" in out and "AP-2" not in out, out)
    code, out, _ = council(repo, "memory", "select", "src/cache/deep/x.py")
    check("memory select: ** globs reach into subfolders", "EC-2" in out, out)
    code, out, _ = council(repo, "memory", "select")
    check("memory select: defaults to the run's changed files and seats", "AP-1" in out and "AP-2" in out and "EC-2" not in out, out)
    code, out, _ = council(repo, "memory", "check")
    check("memory check: flags the anchor that no longer exists, and only that one",
          code == 1 and "STALE  EC-2" in out and "AP-1" not in out and "AP-2" not in out and "1 stale anchor(s) across 5 entries" in out, out)

    # Citation and origin check
    write(os.path.join(run, "synthesis.md"),
          "# Synthesis — eval\n## Kept\n1 · P2 · Principle 3 · src/stats.py:7-9 · median · from: fowler#1\n"
          "2 · P1 · Principle 5 · src/stats.py:1-2 · old lines · from: beck#1\n"
          "3 · P2 · Principle 1 · src/report.py:5 · the uncommitted line · from: x\n"
          "4 · P3 · Principle 2 · `src/stats.py:7–9` · a backticked cite with an en dash · from: z\n"
          "## Cut\nC1 · P3 · Principle 1 · src/report.py:99 · past the end · from: gone · why: repeats from: beck\n")
    code, out, _ = council(repo, "check")
    check("check: fails on a broken citation", code == 1 and "1 broken citation" in out, out)
    check("check: new lines on the branch are 'introduced'", re.search(r"synthesis#1\s+src/stats\.py:7-9\s+ok · introduced", out) is not None, out)
    check("check: lines from the base are 'pre-existing'", re.search(r"synthesis#2\s+src/stats\.py:1-2\s+ok · pre-existing", out) is not None, out)
    check("check: uncommitted lines are 'introduced'", re.search(r"synthesis#3\s+src/report\.py:5\s+ok · introduced", out) is not None, out)
    check("check: backticks and en-dash ranges resolve", re.search(r"synthesis#4\s+src/stats\.py:7–9\s+ok · introduced", out) is not None, out)
    check("check: reads cut items too", "synthesis#C1" in out and "bad-line" in out, out)
    check("check: writes check.md", os.path.isfile(os.path.join(run, "check.md")))

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
          "### hollow — Header only\n- ref: none\n"
          "### messy — Unreadable index lines\n- ref: none\n")
    write(os.path.join(seats2, "pair.md"),
          f"# Pair — Frontend and UX (council-research)\nref: {first_heading('quality-frontend.md')}\nref: {first_heading('quality-ux.md')}\n"
          "## Index\n1 · strong · Principle 1 · `src/stats.py:1–2` · a backticked path and an en-dash range\n")
    write(os.path.join(seats2, "listy.md"),
          "# Listy — list-style (council-research)\nref: none\n## Index\nMost important first:\n"
          "- 1 · moderate · inquiry · src/report.py:1 · written as a list item\n\n### 1. written as a list item\nThe body.\n")
    write(os.path.join(seats2, "hollow.md"), "# Hollow — header only (council-research)\nref: none\nquestion: q\n## Index\n")
    write(os.path.join(seats2, "messy.md"), "# Messy — x (council-research)\nref: none\n## Index\n1) P2 — no separators at all\n")
    code, out, _ = council(repo, "collect", "--run", run2)
    check("collect: a paired seat proves both reference docs", re.search(r"^pair\s+ok\s+1/4\s+\d+\s+ok\s+1/1", out, re.MULTILINE) is not None, out)
    check("collect: a list-style index line counts; prose under the Index is ignored",
          re.search(r"^listy\s+ok\s+1/8\s+\d+\s+n/a\s+1/1", out, re.MULTILINE) is not None, out)
    check("collect: a header-only seat file is caught", "empty-index" in row(out, "hollow"), out)
    check("collect: an index line it can't read is caught", "unparsed-index(1)" in row(out, "messy"), out)
    write(os.path.join(seats2, "pair.md"),
          f"# Pair — Frontend and UX (council-research)\nref: {first_heading('quality-frontend.md')}\n"
          "## Index\n1 · strong · Principle 1 · src/stats.py:1 · x\n")
    code, out, _ = council(repo, "collect", "--run", run2)
    check("collect: a paired seat missing one ref: line is a mismatch", "MISMATCH" in row(out, "pair"), out)

    # A linked worktree
    wt = os.path.join(tmp, "wt")
    git(repo, "worktree", "add", "-q", "-b", "other", wt)
    code, out, _ = council(wt, "home")
    check("home: a linked worktree uses the main checkout's council", slash(out).lower().endswith("/repo/.council"), out)
    code, out, _ = council(wt, "run", "status")
    check("run status: runs from the main checkout show as elsewhere in a worktree", "elsewhere:" in out, out)

    # Map and doctor
    code, out, _ = council(repo, "map", "status")
    check("map status: no map yet", code == 0 and "no map yet" in out, out)
    prev = git(repo, "rev-parse", "HEAD~1")
    write(os.path.join(repo, ".council", "map.md"), f"# Codebase map\nmap-commit: {prev}\nupdated: 2026-09-15\n")
    code, out, _ = council(repo, "map", "status")
    check("map status: counts commits behind and changed areas", "1 commits behind" in out and "src/" in out, out)
    write(os.path.join(repo, ".council", "cards", "fowler.md"),
          "# Fowler — Structure card for eval\nsource: references/nope.md · written: 2026-09-15 @ abc1234\n## Principles, applied here\n1. x — here: y\n")
    code, out, _ = council(repo, "doctor")
    check("doctor: a missing reference doc is an error", code == 1 and "does-not-exist.md" in out and "Fix:" in out, out)
    check("doctor: flags a gate row whose columns shifted", "columns have shifted" in out, out)
    check("doctor: flags a repeated slug", "repeats a slug: fowler" in out, out)
    check("doctor: flags a seat without a card", "seat 'Ghost' has no card" in out, out)
    check("doctor: flags a card whose source doc is gone", "names a source doc that doesn't exist: references/nope.md" in out, out)
    check("doctor: flags a stale memory anchor", "1 memory anchor(s) point at code" in out, out)
    check("doctor: notices a config without a stack fingerprint", "has no stack-fingerprint" in out, out)
    check("doctor: every finding carries a fix", out.count("Fix:") == out.count("ERROR") + out.count("WARN "), out)

    # Close, and the legacy pointer
    write(os.path.join(run, "verify-1.md"), "# Verification — eval\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
          "| 1 | median | CONFIRMED | traced; the guard does not make it REFUTED |\n| 2 | old lines | REFUTED | guarded upstream |\n")
    write(os.path.join(repo, ".council", "active-run"), run2 + "\n")
    code, out, _ = council(repo, "run", "close", "--run", run2, "--status", "abandoned")
    check("run close: abandons a run", code == 0 and "abandoned" in out, out)
    check("run close: empties the old active-run pointer when it names the run", read(os.path.join(repo, ".council", "active-run")).strip() == "")
    code, out, _ = council(repo, "run", "close")
    st = read(os.path.join(run, "session-state.md"))
    check("run close: marks complete and stamps the actual cost (re-dispatches count, skipped seats don't)",
          "status: complete" in st and "actual: ~86k tokens across 4 agents" in st, st)
    check("run close: prints the actual cost", "~86k tokens across 4 agents" in out, out)
    ledger = read(os.path.join(repo, ".council", "ledger.tsv"))
    check("run close: records each seat in the ledger", "ledger: 3 seat row(s) recorded" in out
          and "\tcouncil-review\tfowler\t1\t1\t0\t0\t40000" in ledger and "\tbeck\t1\t1\t0\t1\t45500" in ledger
          and "\tgone\t0\t0\t1\t0\t0" in ledger, out + ledger)
    code, out, _ = council(repo, "ledger")
    check("ledger: each seat's record — shipped means kept and not refuted",
          re.search(r"^fowler\s+1\s+1\s+1\s+0\s+0\s+40\s+100%", out, re.MULTILINE) is not None
          and re.search(r"^beck\s+1\s+1\s+1\s+0\s+1\s+46\s+0%", out, re.MULTILINE) is not None, out)
    with open(os.path.join(repo, ".council", "ledger.tsv"), "a", encoding="utf-8", newline="\n") as f:
        f.write("2026-09-16\t2026-09-16-000000-review\tcouncil-review\thunt-a\t2\t1\t0\t0\t10000\n"
                "2026-09-16\t2026-09-16-000000-review\tcouncil-review\thunt-b\t2\t1\t0\t0\t20000\n")
    code, out, _ = council(repo, "ledger")
    check("ledger: a split worker's rows count as one seat in one run", re.search(r"^hunt\s+1\s+4\s+2\s+0\s+0\s+30\s+50%", out, re.MULTILINE) is not None, out)
    code, out, _ = council(repo, "run", "status")
    check("run status: nothing open after closing", "no open council runs" in out, out)
    code, out, _ = council(repo, "run", "status", "--all")
    check("run status --all: shows closed runs with their cost", "complete" in out and "~86k tokens" in out, out)
    code, _, err = council(repo, "run", "close", "--status", "finished")
    check("run close: rejects an unknown status", code == 2, err)

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

    # A repo with no council yet; paused runs
    fresh = new_repo(tmp, "fresh")
    write(os.path.join(fresh, "app.txt"), "v1\n")
    git(fresh, "add", "-A")
    git(fresh, "commit", "-q", "-m", "init")
    code, _, err = council(fresh, "run", "open", "council-review")
    check("run open: a mode other than init needs a council home", code == 2 and "council-init first" in err, err)
    code, init_run, err = council(fresh, "run", "open", "council-init")
    init_run = init_run.strip()
    check("run open council-init: creates the council home and its .gitignore",
          code == 0 and os.path.isdir(init_run) and "runs/" in read(os.path.join(fresh, ".council", ".gitignore")), init_run + err)
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
    _, fp_loc, _ = council(fresh, "fingerprint", env={"LC_ALL": "en_US.UTF-8"})
    check("fingerprint: the same from a subfolder and under another locale",
          fp_top == fp_sub == fp_loc and "Makefile, go.mod" in fp_top, fp_top + fp_sub + fp_loc)

    # The ledger belongs to the run's council home, wherever the close runs from
    code, r4, _ = council(fresh, "run", "open", "council-review")
    r4 = r4.strip()
    council(fresh, "seat", "hunt", "done", "tokens=1000", "--run", r4)
    code, out, err = council(plain, "run", "close", "--run", r4)
    check("run close from another folder: the ledger goes to the run's own council home",
          "\thunt\t" in read(os.path.join(fresh, ".council", "ledger.tsv"))
          and not os.path.exists(os.path.join(plain, ".council", "ledger.tsv")) and "ledger: 1 seat row" in out, out + err)

    # Usage
    code, out, _ = council(repo, "help")
    check("help: prints the command list", code == 0 and "council run open" in out and "council doctor" in out, out)
    code, _, err = council(repo, "frobnicate")
    check("an unknown command is an error", code == 2 and "unknown command" in err, err)

passed = sum(1 for ok, *_ in results if ok)
for ok, name, detail in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail.strip()[:400]})" if detail and not ok else ""))
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
