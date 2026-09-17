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


def check(name, ok, detail=""):
    results.append((ok, name, detail))


def council(cwd, *args, env=None):
    p = subprocess.run([BASH, CLI, *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=dict(GIT_ENV, **(env or {})), timeout=120)
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
        ("https://example.com/docs/page.html#L5", "n/a (link)"), ("the auth layer", "n/a (no path)"), ("-", "n/a"),
    ]
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
          code == 1 and f"check: {len(shapes) + 1} items, 9 broken citation(s) · 2 name a path but no line"
          " · 4 not checked (a command, a link or no path)" in out, out)
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
    if os.path.isfile(os.path.join(moved, "APP", "OLD.PY")):         # a file system that ignores case
        write(os.path.join(mrun.strip(), "synthesis.md"), "# Synthesis\n## Kept\n"
              "1 · P3 · Naming · APP/OLD.PY:2 · the path in the wrong case · from: hunt#1\n")
        code, out, _ = council(moved, "check")
        check("check: a path cited in the wrong case keeps its real origin", "APP/OLD.PY:2  ok · pre-existing" in out, out)

    # Old lines never read as new for technical reasons: a SHA-256 repository, a line-ending rewrite
    sha = os.path.join(tmp, "sha256")
    os.makedirs(sha)
    git(sha, "init", "-q", "--object-format=sha256")
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
    check("check: item lines it can't read fail the check, and are counted",
          code == 1 and "synthesis: 4 item line(s) check can't read" in out and "check: 2 items, 5 broken" in out, out)
    check("check: a bold or lettered item number is read",
          "synthesis#5  web/nope.py:1  missing-file" in out and "synthesis#6a  web/db.py:1  ok" in out, out)
    write(usyn, "# Synthesis\n## Kept\n## Cut\n")
    code, out, _ = council(cites, "check")
    check("check: a synthesis with no items and no (none) line is not a pass", code == 1 and "nothing was checked" in out, out)
    write(usyn, "# Synthesis\n## Kept\n(none) — the change only renames a file\n## Cut\n")
    code, out, _ = council(cites, "check")
    check("check: '(none)' under Kept is an honest empty result", code == 0 and "check: 0 items, 0 broken" in out, out)
    code, out, err = council(cites, "check", os.path.join(urun.strip(), "seats", "nobody.md"))
    check("check: a file named on the command line that doesn't exist is refused (exit 2), never a pass",
          code == 2 and "no such file" in err, out + err)
    council(cites, "run", "close", "--status", "abandoned")

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
    for key in ("- **ref:** ", "ref: ", "- Ref: "):
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
    council(led, "seat", "verify-1", "done", "agent=v1", "tokens=9000")
    write(os.path.join(lrun, "synthesis.md"), "# Synthesis\n## Kept\n"
          "1 · P2 · P1 · a.py:1 · h1 and h2 are one bug · from: hunt#1, #2\n"
          "2 · P2 · T1 · a.py:6 · b1 and b2 merged · from: beck#1,2\n"
          "3 · P2 · P1 · a.py:3 · h3, also raised by beck · from: hunt#3 and beck#3\n"
          "4 · P2 · P1 · a.py:4 · Data from: the webhook is trusted · from: hunt#4\n")
    write(os.path.join(lrun, "verify-1.md"), "# Verification — ledger\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
          "| 1. | h1 | REFUTED (latent) | guarded upstream |\n| #2 | b1 | REFUTED — test exists | covered |\n"
          "| 3 | h3 | ❌ REFUTED | guarded |\n| 4 | data | Refuted | signature checked |\n")
    council(led, "run", "close")
    code, out, _ = council(led, "ledger")
    check("ledger: 'from: a#1, #2', 'b#1,2', 'a#3 and b#3', a title holding 'from:', and verdicts as written all count",
          re.search(r"^hunt\s+1\s+4\s+4\s+0\s+4\s+30\s+0%", out, re.MULTILINE) is not None
          and re.search(r"^beck\s+1\s+3\s+3\s+0\s+3\s+20\s+0%", out, re.MULTILINE) is not None, out)
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
          f"Wire checkout with the key {fake_key} and email a receipt.\n")
    write(os.path.join(qrun, "synthesis.md"), "# Synthesis\n## Kept\n"
          '1 · must · ask · panel · no freeze · quote: "The quote panel shouldn\'t freeze when the feed drops."\n'
          '2 · must · ask · panel · bold · quote: "Show the last price in **bold** and keep the 5 minute chart."\n'
          '3 · must · ask · panel · bold · quote: "Show the last price in bold and keep"\n'
          '4 · must · ask · orders · never · quote: "It must never place orders."\n'
          '5 · must · ask · panel · Quote: stays live · quote: "shouldn’t freeze when the feed"\n'
          '6 · must · Ask · orders · may trade · quote: "the app may place orders on its own"\n'
          '7 · should · asks · orders · a mistyped part · quote: "never place orders"\n'
          f'8 · must · ask · payments · the key · quote: "Wire checkout with the key {fake_key}"\n'
          '9 · must · ask · payments · redacted · quote: "Wire checkout with the key [redacted] and email"\n')
    code, out, _ = council(qrepo, "check")
    check("check: a quote that differs only by a curly apostrophe or a non-breaking space passes",
          "synthesis#1  quote  ok" in out and "synthesis#2  quote  ok" in out, out)
    check("check: a quote that differs only in capitals or ** marks says exactly that",
          "synthesis#3  quote  NOT-EXACT" in out and "synthesis#4  quote  NOT-EXACT" in out, out)
    check("check: 'Quote:' in a title never hides the part's quote", "synthesis#5  quote  ok" in out, out)
    check("check: in a post-game, a part whose third field isn't exactly 'ask' is still checked",
          "synthesis#6  quote  NOT-IN-THE-REQUEST" in out and "synthesis#7  quote  ok" in out, out)
    check("check: a quote holding a secret-looking string fails; the redacted words pass",
          code == 1 and "synthesis#8  quote  SECRET" in out and "synthesis#9  quote  ok" in out
          and "5 of 9 quotes found in the request" in out, out)
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
                             "pytest " + slash(outside)], start=1):
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
    code, out, err = council_quoted(chg, "changed", "--glob", "*.{py,md}")
    check("changed: a {a,b} pattern covers each of its alternatives",
          code == 0 and "src/old.py" in out and "src/new file.py" in out, out + err)
    code, out, err = council_quoted(chg, "changed", "--glob", "docs/*.py", "--", "true")
    check("changed: a pattern that matches no file anywhere in the project is an error, never a pass forever",
          code == 2 and "no file in this project" in err, out + err)
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
    code, out, _ = council(vocab, "gate", "bs", "--", "echo tools\\x")
    check("gate: an ad-hoc command's stray backslash gets a note", "backslash" in out and read(os.path.join(vgates, "bs.txt")) == "toolsx\n", out)
    code, out, _ = council(vocab, "gate", "env", "--", 'echo "[${MSYS_NO_PATHCONV:-}]"')
    check("gate: Git Bash is told to leave a gate command's Windows switches (cmd /c, /p:\u2026) alone",
          read(os.path.join(vgates, "env.txt")) == "[1]\n", out)
    if os.name == "nt":
        code, out, _ = council(vocab, "gate", "cmd-exit", "--", "cmd /c exit 3")
        check("gate: on Windows, cmd /c runs its command and the gate gets its exit code", code == 3 and "FAIL (exit 3" in out, out)
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
    check("gate: a failing gate names the failure lines its baseline didn't have",
          code == 1 and "the baseline didn't have" in out and "FAILED test_new" in out.split("the baseline didn't have")[-1]
          and "test_old" not in out, out)
    council(redbase, "gate", "--all", "--at", "verify")
    check("gate --all --at verify: never replaces the baseline", "test_old_a" in read(os.path.join(rgates, "baseline", "tests.txt")))

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
             "token = self.config.auth.token_v2", "api_key = os.environ.get('API_KEY')"]
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
    took = []
    for args in [("home", "x"), ("run", "open", "council-review", "x"), ("run", "close", "x"), ("run", "status", "x"),
                 ("seat", "a", "done", "x"), ("index", "x"), ("gate", "--all", "x"), ("gate", "ok", "--at", "verify"),
                 ("gates", "x"), ("changed", "x"), ("collect", "x"), ("check", "no-such-file.md"), ("map", "status", "x"),
                 ("fingerprint", "x"), ("memory", "check", "x"), ("ask", "save", "a", "b"), ("ledger", "5", "x"),
                 ("doctor", "x"), ("version", "x"), ("help", "x"), ("doctor", "--frobnicate"), ("run", "close", "--base", "main"),
                 ("run", "status", "--at=verify"), ("index", "--", "x"), ("doctor", "--all=yes"), ("run", "close", "--status=")]:
        code, out, err = council(repo, *args)
        if code != 2 or not err.strip():
            took.append(" ".join(args) + f" (exit {code})")
    check("every command refuses a word or flag it doesn't take: exit 2, with a message", not took, "; ".join(took))

passed = sum(1 for ok, *_ in results if ok)
for ok, name, detail in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail.strip()[:400]})" if detail and not ok else ""))
if BASH:
    print(f"\nbash: {BASH} ({subprocess.run([BASH, '-c', 'echo $BASH_VERSION'], capture_output=True, text=True).stdout.strip()})")
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
