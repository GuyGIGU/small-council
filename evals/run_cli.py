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
import time

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
    council(msel, "seat", "hunt", "queued")
    code, out, _ = council(msel, "memory", "select", "webapp/backend")
    check("memory select: with a run open, the paths given add to the run's seats and mode",
          all(i in out for i in ["AP-1", "EC-1", "EC-2"]) and "AP-2" not in out and "3 scoped and 0 every-run entries of 4 apply" in out, out)
    code, selrun2, _ = council(msel, "run", "open", "council-research", "--alongside")
    code, out, err = council(msel, "memory", "select", "webapp/backend/")
    check("memory select: with several runs open, only the paths given count — and it says so",
          code == 0 and "AP-1" in out and "EC-1" not in out and "several runs are open" in err, out + err)
    council(msel, "run", "close", "--run", selrun2.strip(), "--status", "abandoned")
    council(msel, "run", "close", "--run", selrun.strip(), "--status", "abandoned")

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
    code, out, _ = council(grp, "check", os.path.join(grun, "nope.md"))
    check("check: a named file that doesn't exist says so once, and never 'nothing to check'",
          code == 1 and "no such file" in out and "nothing to check" not in out, out)
    write(usyn, "# Synthesis\n## Kept\n(none) — the change only renames a file\n## Cut\n")
    code, out, _ = council(cites, "check")
    check("check: '(none)' under Kept is an honest empty result", code == 0 and "check: 0 items, 0 broken" in out, out)
    code, out, _ = council(cites, "check", os.path.join(urun.strip(), "seats", "nobody.md"))
    check("check: a file named on the command line that doesn't exist is not a pass", code == 1 and "no such file" in out, out)
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
    check("doctor: flags memory scope items that match nothing", "memory scope item(s) match no file, seat or mode" in out, out)
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
