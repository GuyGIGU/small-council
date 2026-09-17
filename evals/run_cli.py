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
  - citation and origin checks (single lines, ranges and comma lists); map status; the drift doctor.
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
    code, out, _ = council(repo, "gate", "ship")
    check("gate <name>: runs a side-effect gate when named, with a warning", code == 0 and "side effects (deploy, network)" in out, out)
    code, out, _ = council(repo, "gate", "--all", "--at", "strict")
    check("gate --all: a failing mandatory gate fails the set", code == 1 and "a mandatory gate failed" in out, out)
    check("gate --all: the verdict line marks a mandatory failure", "FAIL (must \u2014 mandatory)" in out, out)
    code, out, _ = council(repo, "gate", "--all", "--at", "nobody-runs-here")
    check("gate --all: no gate at this stage is NOTHING WAS CHECKED, and never exit 0",
          code == 4 and "NOTHING WAS CHECKED" in out and "nobody-runs-here" in out, out)
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
          "### AP-4: an empty list raises on purpose\n**Pattern:** no empty guard · **Why:** callers check first\n"
          "**Scope:** src/stats.py · **Anchor:** src/stats.py:5, 8–9, summary\n"
          "## Enforced Conventions (EC) — always / never rules\n"
          "### EC-1: every module has a docstring\n**Rule:** always · **Why:** tooling\n"
          "### EC-2: no global caches\n**Rule:** never · **Why:** tests\n**Scope:** src/cache/** · **Anchor:** src/cache/store.py:3\n"
          # README.md has 2 lines, and 3 is a word in tests/test_stats.py: read as a symbol, line 3 would pass
          "### EC-3: the README names the robust statistic\n**Rule:** always · **Why:** users reach for the mean\n"
          "**Scope:** README.md · **Anchor:** README.md:1,3, robust_mean\n"
          "## Proposed — awaiting the user's yes/no\n")
    code, out, _ = council(repo, "memory")
    check("memory: prints a one-line index with scopes and anchors",
          "AP-1 · median returns the upper middle on purpose · scope: src/stats.py, beck · anchor: src/stats.py:7" in out
          and "AP-4 · an empty list raises on purpose · scope: src/stats.py · anchor: src/stats.py:5, 8–9, summary" in out
          and "EC-1 · every module has a docstring · every run" in out and out.count("\n") == 7, out)
    code, out, _ = council(repo, "memory", "select", "src/stats.py")
    check("memory select: a path pulls its scoped entries plus the every-run ones",
          "AP-1" in out and "EC-1" in out and "AP-2" not in out and "EC-2" not in out and "2 scoped and 1 every-run entries of 7" in out, out)
    code, out, _ = council(repo, "memory", "select", "auth/session.py")
    check("memory select: **/ also matches a path at the repo root", "AP-3" in out, out)
    code, out, _ = council(repo, "memory", "select", "beck")
    check("memory select: a seat slug pulls its entries", "AP-1" in out and "AP-2" not in out, out)
    code, out, _ = council(repo, "memory", "select", "src/cache/deep/x.py")
    check("memory select: ** globs reach into subfolders", "EC-2" in out, out)
    code, out, _ = council(repo, "memory", "select")
    check("memory select: defaults to the run's changed files and seats", "AP-1" in out and "AP-2" in out and "EC-2" not in out, out)
    code, out, _ = council(repo, "memory", "check")
    check("memory check: flags the anchors that no longer hold, and only those",
          code == 1 and "STALE  EC-2" in out and "AP-1" not in out and "AP-2" not in out and "3 stale anchor(s) across 7 entries" in out, out)
    check("memory check: an anchor may list lines, as a citation does; with every line there, it isn't stale",
          "AP-4" not in out, out)
    check("memory check: a listed line past the end is bad-line, even where its number is a word in the code",
          "STALE  EC-3 — anchor README.md:1,3: bad-line (the file has 2 lines)" in out, out)
    check("memory check: a name after the listed lines is an anchor of its own",
          "STALE  EC-3 — nothing in the code is named robust_mean any more" in out, out)

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
    check("doctor: flags stale memory anchors", "3 memory anchor(s) point at code" in out, out)
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
    code, out, _ = council(req, "seat", "leach", "done", "tokens=6000")
    check("seat: a resumed worker adds tokens, not agents", "agents: 1 of 1 done" in out and "~26k tokens so far" in out, out)
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
          "| lint | `bash '" + slash(CLI) + "' changed --glob '*.nothing' -- false` | verify | no | ok | `true` | none | - |\n")
    code, out, _ = council(names_repo, "gate", "--all", "--at", "verify")
    check("gate --all: a check that matched no files passes, but is never reported as a clean pass",
          code == 0 and "pass \u2014 but nothing to check (0 files matched)" in out
          and "1 had nothing to check (lint \u2014 0 files matched)" in out, out)

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
            "webapp/frontend/src/components", "core/pipeline/downloads", "ReplaySealIntegrityChecker",
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
    code, rs, _ = council(ap, "run", "open", "council-review")
    rs = rs.strip()
    title_key = "sk" + "_live_" + "AbCdEfGhIjKlMnOpQrStUvWx"     # built at run time: not a real key's text
    write(os.path.join(rs, "ask.md"), f"# Ask — rotate {title_key}\n## In your words\nPlease rotate it.\n")
    code, out, _ = council(ap, "ask", "save")
    check("ask save: a secret in the title never reaches the file name",
          code == 0 and "-rotate" in out and "abcdefghij" not in out.lower() and "live" not in out, out)
    council(ap, "run", "close", "--status", "abandoned")

    # A war room's round 2: collect waits for a running seat; a fresh round-2 worker counts as its seat
    code, wr, _ = council(req, "run", "open", "council-plan")
    wr = wr.strip()
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
    council(req, "seat", "leach-r2", "done", "agent=w9", "tokens=900")
    write(os.path.join(fr, "seats", "leach-r2.md"), "# Leach — Data (council-plan, round 2)\nref: none\n## Index\n1 · hold · P1 x#1 · a.txt:1 · y\n")
    code, out, _ = council(req, "collect")
    check("collect: once a fresh round-2 worker is done, the lost round-1 seat is judged by its file",
          code == 0 and "all 2 seats in order" in out, out)
    council(req, "run", "close", "--status", "abandoned")

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
