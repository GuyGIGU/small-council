#!/usr/bin/env python3
"""No-network behavioral checks for the Phase 6 evidence ledger."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "scripts" / "evidence.py"
CLI = ROOT / "bin" / "council"
BASH = (os.environ.get("COUNCIL_EVAL_BASH") or shutil.which("bash") or
        (r"C:\Program Files\Git\bin\bash.exe" if Path(r"C:\Program Files\Git\bin\bash.exe").is_file() else None))
results = []


def check(name, okay):
    results.append((name, bool(okay)))


def write(run, name, content):
    path = run / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def invoke(run, action, via_cli=False):
    if via_cli:
        return subprocess.run((BASH, str(CLI), "evidence", action, "--run", str(run)), cwd=run,
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
    return subprocess.run((sys.executable, str(ENGINE), action, "--run", str(run)), cwd=run,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def claims(run):
    return [json.loads(line) for line in (run / "claims.jsonl").read_text(encoding="utf-8").splitlines()]


with tempfile.TemporaryDirectory() as folder:
    run = Path(folder) / "runs" / "fixture"
    run.mkdir(parents=True)
    write(run, "session-state.md", "mode: council-review\nstatus: in-progress\n")
    write(run, "seats/hunt.md", "# Hunt\n## Index\n3 · P1 · Principle 1 · src/auth.py:4 · Expiry skipped\n")
    write(run, "synthesis.md", "# Synthesis\n## Kept\n"
          "1 · P1 · Principle 1 · src/auth.py:4 · Expiry skipped · state: OBSERVED · from: hunt#3\n"
          "## Cut\nC1 · P2 · Principle 2 · src/auth.py:8 · Intentional guard · why: already handled · state: INFERRED · from: hunt#3\n")
    build = invoke(run, "build")
    check("provisional ledger builds without claiming verification", build.returncode == 0 and
          len(claims(run)) == 2 and claims(run)[0]["verdict"] == "UNVERIFIED" and
          claims(run)[1]["cut_reason"] == "already handled")
    check("unverified kept claim blocks evidence check", invoke(run, "check").returncode == 1)

    write(run, "verify-1.md", "# Verification\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
          "| 1 | Expiry skipped | CONFIRMED | current path via src/auth.py:4 |\n")
    if BASH:
        built = invoke(run, "build", via_cli=True)
        checked = invoke(run, "check", via_cli=True)
        shown = invoke(run, "show", via_cli=True)
        check("CLI builds, checks and shows a verified run", built.returncode == 0 and
              checked.returncode == 0 and shown.returncode == 0 and "CONFIRMED" in shown.stdout)
    else:
        check("CLI unavailable without bash", True)
        invoke(run, "build")
    first = claims(run)[0]
    check("ledger retains claim, citation, source and verifier evidence", first["claim"] == "Expiry skipped" and
          first["citation"] == "src/auth.py:4" and first["provenance"] == ["hunt#3"] and
          first["source"] == "synthesis.md:3" and first["verification"][0]["ref"] == "verify-1.md:4" and
          first["verification"][0]["evidence"] == "current path via src/auth.py:4")
    write(run, "seats/hunt.md", "# Hunt\n## Index\n(none) — no findings\n### Example\n"
          "3 · P1 · Principle 1 · src/auth.py:4 · Expiry skipped\n")
    check("a source id in prose cannot fake a worker Index item", invoke(run, "check").returncode == 1)
    write(run, "seats/hunt.md", "# Hunt\n## Index\n3 · P1 · Principle 1 · src/auth.py:4 · Expiry skipped\n")
    stable = (run / "claims.jsonl").read_bytes()
    invoke(run, "build")
    check("repeated build is byte-identical", (run / "claims.jsonl").read_bytes() == stable)

    header = "# Verification\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
    part_a = "| 1 | Expiry skipped | CONFIRMED | current path via src/auth.py:4 |\n"
    part_b = "| C1 | Intentional guard | REFUTED | guard at src/auth.py:8 |\n"
    (run / "verify-1.md").unlink()
    write(run, "verify-1-a.md", header + part_a)
    write(run, "verify-1-b.md", header + part_b)
    check("Workflow parts link every claim", invoke(run, "build").returncode == 0 and
          all(len(c["verification"]) == 1 for c in claims(run)))
    write(run, "verify-1.md", header + part_a + part_b)
    check("joined copy of Workflow parts counts each identical row once", invoke(run, "build").returncode == 0 and
          all(len(c["verification"]) == 1 for c in claims(run)) and invoke(run, "check").returncode == 0)
    write(run, "verify-2.md", header + "| 1 | Expiry skipped | REFUTED | opposite trace |\n")
    check("Workflow copy deduplication preserves conflicting verdict refusal", invoke(run, "build").returncode == 2)
    write(run, "verify-2.md", header + "| 1 | Expiry skipped | CONFIRMED | different evidence |\n")
    check("same verdict with different evidence still requires resolution", invoke(run, "build").returncode == 2)
    for name in ("verify-1-a.md", "verify-1-b.md", "verify-2.md"):
        (run / name).unlink()

    write(run, "verify-1.md", "# Verification\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
          "| 1 | Expiry skipped | REFUTED | upstream guard at src/auth.py:2 |\n")
    check("changed verifier makes ledger stale", invoke(run, "check").returncode == 1)
    check("show refuses a stale ledger", invoke(run, "show").returncode == 2)
    invoke(run, "build")
    check("refuted verdict remains visible", claims(run)[0]["verdict"] == "REFUTED" and
          invoke(run, "check").returncode == 0)

    write(run, "verify-2.md", "# Verification\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
          "| 1 | Expiry skipped | CONFIRMED | opposite trace |\n")
    check("conflicting verifier rows cannot silently confirm", invoke(run, "build").returncode == 2)
    (run / "verify-2.md").unlink()
    write(run, "verify-1.md", "# Verification\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
          "| 9 | Orphaned finding | CONFIRMED | stray proof |\n| 1 | Expiry skipped | REFUTED | guarded |\n")
    check("unknown verifier claim id is not silently dropped", invoke(run, "build").returncode == 2)
    write(run, "verify-1.md", "# Verification\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
          "| 1 | Expiry skipped | not CONFIRMED | guarded |\n")
    check("negative wording cannot become CONFIRMED", invoke(run, "build").returncode == 2)
    write(run, "verify-1.md", "# Verification\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
          "| 1 | Expiry skipped | REFUTED | guarded |\n")

    write(run, "synthesis.md", "# Synthesis\n## Kept\n"
          "1 · P1 · Principle 1 · src/auth.py:4 · Expiry skipped · state: REPRODUCED · proof: gates/before-1.json · from: hunt#3\n"
          "## Cut\n(none) — no other claim\n")
    invoke(run, "build")
    check("reproduced needs an existing proof artifact", invoke(run, "check").returncode == 1)
    write(run, "gates/before-1.json", '{"exit":1}\n')
    check("saved proof permits REPRODUCED", invoke(run, "check").returncode == 0)
    write(run, "synthesis.md", "# Synthesis\n## Kept\n"
          "1 · P1 · Principle 1 · src/auth.py:4 · Expiry skipped · state: REPRODUCED · proof: session-state.md · from: hunt#3\n")
    invoke(run, "build")
    check("an arbitrary run file cannot masquerade as reproduction", invoke(run, "check").returncode == 1)
    write(run, "synthesis.md", "# Synthesis\n## Kept\n"
          "1 · P1 · Principle 1 · src/auth.py:4 · Expiry skipped · state: REPRODUCED · proof: ../outside · from: hunt#3\n")
    invoke(run, "build")
    check("proof traversal is rejected", invoke(run, "check").returncode == 1)

    write(run, "synthesis.md", "# Synthesis\n## Kept\n"
          "1 · P1 · Principle 1 · src/auth.py:4 · Expiry skipped · from: hunt#3\n")
    invoke(run, "build")
    check("undeclared state is UNVERIFIED and fails check", claims(run)[0]["evidence_state"] == "UNVERIFIED" and
          invoke(run, "check").returncode == 1)

    write(run, "synthesis.md", "# Synthesis\n## Kept\n"
          "1 · P1 · gate · src/auth.py:4 · Lint failed · state: OBSERVED · from: gate:lint\n")
    invoke(run, "build")
    check("gate provenance needs its saved verdict", invoke(run, "check").returncode == 1)
    write(run, "gates/lint.json", '{"exit":1}\n')
    check("saved gate verdict establishes provenance link", invoke(run, "check").returncode == 0)

    write(run, "synthesis.md", "# Synthesis\n## Cut\n(none) — no findings\n")
    check("missing Kept section is not an empty success", invoke(run, "build").returncode == 2)

    (run / "verify-1.md").unlink()
    write(run, "synthesis.md", "# Synthesis\n## Kept\n(none) — no findings\n## Cut\n"
          "C1 · P1 · Principle 1 · src/auth.py:4 · Risky cut · state: INFERRED · from: hunt#3\n")
    final_build = invoke(run, "build")
    check("cut P1 needs its own verification link", final_build.returncode == 0 and
          invoke(run, "check").returncode == 1)

for name, okay in results:
    print("[{}] {}".format("PASS" if okay else "FAIL", name))
passed = sum(okay for _, okay in results)
print("\n{}/{} checks passed".format(passed, len(results)))
sys.exit(0 if passed == len(results) else 1)
