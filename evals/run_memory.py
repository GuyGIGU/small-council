#!/usr/bin/env python3
"""Focused, no-model checks for scoped and provenance-aware memory."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parent.parent
BASH = os.environ.get("COUNCIL_EVAL_BASH") or shutil.which("bash")
GIT = shutil.which("git")
checks = []


def check(name, good, detail=""):
    checks.append((name, good, detail))


def council(repo, *args):
    env = os.environ.copy()
    if os.environ.get("COUNCIL_EVAL_BASH"):
        env["PATH"] = str(Path(BASH).parent) + os.pathsep + env.get("PATH", "")
    result = subprocess.run([BASH, str(ROOT / "bin" / "council"), *args], cwd=repo,
                            capture_output=True, text=True, encoding="utf-8", errors="replace",
                            env=env, timeout=30)
    return result.returncode, result.stdout, result.stderr


if not BASH or not GIT:
    print("[SKIP] bash or git unavailable")
    raise SystemExit(0)

with tempfile.TemporaryDirectory(prefix="council-memory-") as temporary:
    repo = Path(temporary)
    subprocess.run([GIT, "init", "-q"], cwd=repo, check=True)
    (repo / ".council").mkdir()
    (repo / "src" / "auth").mkdir(parents=True)
    (repo / "src" / "auth" / "session.py").write_text("def revoke(): pass\n", encoding="utf-8")
    (repo / ".council" / "council.config.md").write_text("# Council config\n", encoding="utf-8")
    (repo / ".council" / "conventions.md").write_text(
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
        "**Origin:** review run-14\n**Evidence:** review.md\n**Verdict:** OBSERVED\n",
        encoding="utf-8")

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

    (repo / ".council" / "conventions.md").write_text(
        "# Legacy memory\n## Accepted Patterns\n"
        "- **AP-8 — title-only bullet** kept by the user\n"
        "**Scope:** src/auth/**\n"
        "## Decisions\n### D-9: title-only heading\n"
        "## Proposed\n### F-8: unapproved old note\n",
        encoding="utf-8")
    code, out, err = council(repo, "memory", "select", "src/auth/session.py")
    check("legacy entries without new fields remain readable", code == 0 and
          "AP-8 · title-only bullet · scope: src/auth/**" in out and
          "D-9 · title-only heading · every run" in out and
          "F-8" not in out, out + err)

passed = sum(good for _, good, _ in checks)
for name, good, detail in checks:
    print(f"[{'PASS' if good else 'FAIL'}] {name}" +
          (f"  ({detail.strip()[:400]})" if detail and not good else ""))
print(f"\n{passed}/{len(checks)} checks passed")
raise SystemExit(0 if passed == len(checks) else 1)
