#!/usr/bin/env python3
"""Focused, no-model checks for scoped and provenance-aware memory."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
BASH = os.environ.get("COUNCIL_EVAL_BASH") or shutil.which("bash")
GIT = shutil.which("git")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
checks = []


def check(name, good, detail=""):
    checks.append((name, good, detail))


def council(repo, *args):
    env = os.environ.copy()
    for var in ("COUNCIL_RUN", "CLAUDE_CODE_SESSION_ID"):  # never inherit the session the eval runs in
        env.pop(var, None)
    if os.environ.get("COUNCIL_EVAL_BASH"):
        env["PATH"] = str(Path(BASH).parent) + os.pathsep + env.get("PATH", "")
    result = subprocess.run([BASH, str(ROOT / "bin" / "council"), *args], cwd=repo,
                            capture_output=True, text=True, encoding="utf-8", errors="replace",
                            env=env, timeout=60)
    return result.returncode, result.stdout, result.stderr


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def failure(ident, title, *, failure="a seat claimed tokens stay valid", scope="src/auth/**",
            origin="run r1", evidence=".council/reviews/run-12.md:42", verdict="REFUTED", extra=""):
    """One observed-failure entry; pass None to leave a field out."""
    text = "### {}: {}\n".format(ident, title)
    for name, value in (("Failure", failure), ("Scope", scope), ("Origin", origin),
                        ("Evidence", evidence), ("Verdict", verdict)):
        if value is not None:
            text += "**{}:** {}\n".format(name, value)
    return text + extra


if not BASH or not GIT:
    print("[SKIP] bash or git unavailable")
    raise SystemExit(0)

def line_of(out, prefix):
    return next((line for line in out.splitlines() if line.startswith(prefix)), "")


with tempfile.TemporaryDirectory(prefix="council-memory-") as temporary:
    repo = Path(temporary) / "repo"
    outside = Path(temporary) / "outside.md"                # beside the project, never inside it
    repo.mkdir()
    subprocess.run([GIT, "init", "-q"], cwd=repo, check=True)
    write(repo / "src" / "auth" / "session.py", "def revoke(): pass\n")
    write(repo / ".council" / "council.config.md", "# Council config\n")
    # The evidence F-1 cites: line 42 of a review is the verifier's REFUTED row.
    write(repo / ".council" / "reviews" / "run-12.md",
          "".join("line {}\n".format(n) for n in range(1, 42)) +
          "| 3 | stale token claim | REFUTED — middleware invalidates first | src/auth/mw.py:30 |\n")
    memory = repo / ".council" / "conventions.md"
    write(memory,
          "# Memory\n## Accepted Patterns\n### AP-1: revocation order\n"
          "**Pattern:** invalidate before cache lookup · **Origin:** user-approved review 2026-09-26\n"
          "**Scope:** src/auth/**\n"
          "## Decisions\n### D-1: use the current parser\n"
          "**Decision:** preserve the parser · **Origin:** user ruling 2026-09-26\n"
          "## Observed Failures (F)\n### F-1: stale token claim\n"
          "**Failure:** a seat made a false stale-token claim\n"
          "**Scope:** src/auth/**\n**Origin:** review run-12\n"
          "**Evidence:** reviews/run-12.md:42\n**Verdict:** REFUTED\n"
          "**Anchor:** src/auth/session.py:2\n"
          "### F-2: unsupported claim\n**Failure:** an assumed cause\n"
          "**Scope:** src/auth/**\n**Origin:** review run-13\n**Verdict:** INFERRED\n"
          "## Proposed\n### F-3: unapproved claim\n"
          "**Failure:** proposal only\n**Scope:** src/auth/**\n"
          "**Origin:** review run-14\n**Evidence:** review.md\n**Verdict:** OBSERVED\n")

    code, out, err = council(repo, "memory", "select", "src/auth/session.py")
    check("settled meaning and origin reach selection", code == 0 and
          "AP-1 · revocation order · scope: src/auth/** · invalidate before cache lookup" in out and
          "origin: user-approved review 2026-09-26" in out and
          "D-1 · use the current parser · every run · preserve the parser" in out, out + err)
    check("only complete approved failures reach selection", "F-1 · stale token claim · observed failure, not a rule" in out and
          "verdict: REFUTED" in out and "evidence: reviews/run-12.md:42" in out and
          "F-2" not in out and "F-3" not in out, out + err)
    code, out, err = council(repo, "memory", "select", "src/other.py")
    check("failure retrieval is scoped", code == 0 and "F-1" not in out and "AP-1" not in out and
          "D-1" in out, out + err)
    code, out, err = council(repo, "memory")
    check("incomplete failures remain indexed but unserved", code == 0 and
          "F-2 · unsupported claim · NOT SERVED" in out and
          "F-3 · unapproved claim · not served" in out, out + err)
    code, out, err = council(repo, "memory", "check")
    check("observed failure anchors are checked", code == 1 and
          "STALE  F-1" in out and "bad-line" in out, out + err)

    # What an observed failure needs before any brief gets it — each of these is left out, and says why.
    write(memory,
          "# Memory\n## Accepted Patterns\n### AP-1: revocation order\n"
          "**Pattern:** invalidate before cache lookup\n**Scope:** src/auth/**\n"
          "**Evidence:** reviews/gone.md:3\n"                     # a settled entry's evidence is not audited
          "## Observed Failures (F)\n" +
          failure("F-1", "a guess recorded as history", verdict="INFERRED — the cache probably did it") +
          failure("F-2", "an assumption", verdict="assumed") +
          failure("F-3", "a verifier that could not tell", verdict="UNCERTAIN") +
          failure("F-4", "scoped to none", scope="none") +
          failure("F-5", "scoped with a star", scope="src/auth/**, *") +
          failure("F-6", "scoped to a dot", scope=".") +
          failure("F-7", "a rule and no failure", failure=None, extra="**Rule:** never touch the cache\n") +
          failure("F-8", "a rule beside the failure", extra="**Rule:** never touch the cache\n") +
          failure("F-9", "no origin", origin=None) +
          "## Rules nobody named\n" +
          failure("F-10", "outside Observed Failures"))
    code, out, err = council(repo, "memory")
    check("an inferred, assumed or uncertain verdict is never served as history",
          "F-1 · a guess recorded as history · NOT SERVED as an observed failure — its verdict, INFERRED" in out and
          "F-2 · an assumption · NOT SERVED" in out and "assumed, does not establish a failure" in out and
          "F-3 · a verifier that could not tell · NOT SERVED" in out, out + err)
    check("an observed failure must be scoped: none, * and . reach every run and are refused",
          all("NOT SERVED as an observed failure — its scope reaches every run" in line_of(out, "F-{} ·".format(n))
              for n in (4, 5, 6)), out + err)
    check("a rule is not a failure: no Failure field, not served; a rule beside one is never its meaning",
          "F-7 · a rule and no failure · NOT SERVED as an observed failure — it has no Failure" in out and
          "F-9 · no origin · NOT SERVED as an observed failure — it has no Origin" in out and
          "F-10 · outside Observed Failures · NOT SERVED as an observed failure — it sits outside" in out, out + err)
    code, out, err = council(repo, "memory", "select", "src/auth/session.py")
    served = [line for line in out.splitlines() if line.startswith("F-")]
    check("select serves only the supported failure, with its observation and not the rule beside it",
          code == 0 and len(served) == 1 and served[0].startswith("F-8 · a rule beside the failure") and
          "a seat claimed tokens stay valid" in served[0] and "never touch the cache" not in out and
          "AP-1 · revocation order" in out and
          "F-1 is left out: its verdict" in err and "F-4 is left out: its scope reaches every run" in err, out + err)
    code, out, err = council(repo, "memory", "select", "docs/unrelated.md")
    check("a refused every-run failure never reaches an unrelated run", code == 0 and
          not [line for line in out.splitlines() if line.startswith("F-")], out + err)

    # Provenance: the audit opens what **Evidence:** names and never takes the entry's word for it.
    write(repo / ".council" / "runs" / "r1" / "verify-1.md",
          "# Verify\n| # | Item | Verdict | Evidence |\n"
          "| 3 | stale tokens | REFUTED — middleware invalidates first | src/auth/mw.py:30 |\n")
    write(repo / "docs" / "My Notes" / "gate out.txt", "gate output\nAssertionError: 1 != 2\n")
    write(outside, "| 3 | x | REFUTED | y |\n")
    write(memory,
          "# Memory\n## Accepted Patterns\n### AP-1: revocation order\n**Pattern:** invalidate first\n"
          "**Scope:** src/auth/**\n**Evidence:** reviews/gone.md:3\n"
          "## Observed Failures (F)\n" +
          failure("F-1", "the verifier row shows it", evidence=".council/runs/r1/verify-1.md:3") +
          failure("F-2", "the cited line does not show the verdict", evidence="runs/r1/verify-1.md:1") +
          failure("F-3", "one piece gone, one still there", verdict="refuted - see the row",
                  evidence="runs/r0/verify-1.md:3; runs/r1/verify-1.md:2-3") +
          failure("F-4", "a line past the end", verdict="OBSERVED", evidence="runs/r1/verify-1.md:99") +
          failure("F-5", "evidence that is gone", evidence="reviews/nowhere.md:42") +
          failure("F-6", "a whole file cited, the verdict in it", evidence="the review at reviews/run-12.md") +
          failure("F-7", "a path with a blank", verdict="OBSERVED", scope="docs/**",
                  evidence="`docs/My Notes/gate out.txt:2`") +
          failure("F-8", "evidence outside the project", verdict="OBSERVED",
                  evidence="../outside.md, {}".format(outside.as_posix())) +
          failure("F-9", "prose instead of a file", verdict="OBSERVED", evidence="the user saw it happen"))
    code, out, err = council(repo, "memory", "select", "src/auth/session.py", "docs/My Notes/x.md")
    served = sorted(line.split(" · ")[0] for line in out.splitlines() if line.startswith("F-"))
    check("only failures whose evidence still shows them are served",
          code == 0 and served == ["F-1", "F-3", "F-6", "F-7"] and "AP-1 · revocation order" in out, out + err)
    check("select says why each unsupported failure is left out",
          "F-2 is left out: none of the evidence it cites shows REFUTED" in err and
          "F-4 is left out: none of its evidence can be found and read as cited" in err and
          "F-5 is left out" in err and "F-8 is left out" in err and
          "F-9 is left out: its evidence names no file that can be checked" in err, err)
    code, out, err = council(repo, "memory", "check")
    check("check reports every missing piece and each failure it stopped serving, and fails",
          code == 1 and "EVIDENCE  F-3 — evidence runs/r0/verify-1.md:3 can't be found" in out and
          "EVIDENCE  F-4 — evidence runs/r1/verify-1.md:99: the file has 3 line(s), not 99" in out and
          "UNSUPPORTED  F-2" in out and "UNSUPPORTED  F-5" in out and "UNSUPPORTED  F-8" in out and
          "UNSUPPORTED  F-9" in out and "UNSUPPORTED  F-1" not in out and "UNSUPPORTED  F-7" not in out and
          "5 no longer served" in out, out + err)
    check("a settled entry's own evidence field is not audited (its authority is the user's approval)",
          "AP-1" not in out, out)
    code, out, err = council(repo, "doctor")
    check("doctor warns about observed failures that are no longer served",
          "5 observed failure(s) in memory are no longer served" in out, out + err)

    write(memory,
          "# Legacy memory\n## Accepted Patterns\n"
          "- **AP-8 — title-only bullet** kept by the user\n"
          "**Scope:** src/auth/**\n"
          "## Decisions\n### D-9: title-only heading\n"
          "## Proposed\n### F-8: unapproved old note\n",
          )
    code, out, err = council(repo, "memory", "select", "src/auth/session.py")
    check("legacy entries without new fields remain readable", code == 0 and
          "AP-8 · title-only bullet · scope: src/auth/**" in out and
          "D-9 · title-only heading · every run" in out and
          "F-8" not in out, out + err)
    code, out, err = council(repo, "memory", "check")
    check("a memory with no observed failures checks exactly as before", code == 0 and
          "memory check: 0 stale anchor(s) across 2 entries" in out and "observed failure" not in out, out + err)

passed = sum(good for _, good, _ in checks)
for name, good, detail in checks:
    print(f"[{'PASS' if good else 'FAIL'}] {name}" +
          (f"  ({detail.strip()[:400]})" if detail and not good else ""))
print(f"\n{passed}/{len(checks)} checks passed")
raise SystemExit(0 if passed == len(checks) else 1)
