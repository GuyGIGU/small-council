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


def check(name, okay, detail=""):
    results.append((name, bool(okay), detail))


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


def invoke_table(path):
    return subprocess.run((sys.executable, str(ENGINE), "table", "--file", str(path)), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def claims(run):
    return [json.loads(line) for line in (run / "claims.jsonl").read_text(encoding="utf-8").splitlines()]


def fresh(root, name, mode, synthesis, verifies, level="independent", size="squad"):
    """A run folder of its own: its mode, its plan's size and verification level, synthesis and verify files."""
    run = Path(root) / "runs" / name
    write(run, "session-state.md", "mode: {}\nstatus: in-progress\n".format(mode))
    write(run, "run-plan.tsv", "kind\tid\tfield\tvalue\treason\nrun\trun\tsize\t{}\tx\n"
          "verification\trun\tlevel\t{}\tx\n".format(size, level))
    write(run, "synthesis.md", synthesis)
    for file_name, body in verifies.items():
        write(run, file_name, body)
    return run


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
    # Ordinary ways to write the table (a real run's verifier bolded its verdicts; run 1's wrote
    # 'Evidence (path:line …)'): each is read as the verdict it states, never dropped.
    variants = {
        "a bold id": "| **1** | Expiry skipped | REFUTED | guarded |\n",
        "an id written #1": "| #1 | Expiry skipped | REFUTED | guarded |\n",
        "a bold verdict": "| 1 | Expiry skipped | **REFUTED** | guarded |\n",
        "an indented row with no closing pipe": "  | 1 | Expiry skipped | REFUTED | guarded\n",
        "prose after the verdict": "| 1 | Expiry skipped | REFUTED — confirmed only for admins | guarded |\n",
    }
    for label, row in variants.items():
        write(run, "verify-1.md", "# Verification\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n" + row)
        check("verifier table: " + label + " is read", invoke(run, "build").returncode == 0 and
              claims(run)[0]["verdict"] == "REFUTED" and claims(run)[0]["verification"][0]["evidence"] == "guarded")
    write(run, "verify-1.md", "# Verification\n| # | Item | Verdict | Evidence (path:line, reachability) |\n"
          "|---|---|---|---|\n| 1 | Expiry skipped | REFUTED | `git grep expiry | wc -l` is 0 |\n")
    check("verifier table: a longer Evidence heading and a | inside the evidence are read, the evidence whole",
          invoke(run, "build").returncode == 0 and claims(run)[0]["verdict"] == "REFUTED" and
          claims(run)[0]["verification"][0]["evidence"] == "`git grep expiry | wc -l` is 0")
    write(run, "verify-1.md", "# Verification\n| # | Claim | Verdict | Notes |\n|---|---|---|---|\n"
          "| 1 | Expiry skipped | REFUTED | guarded |\n")
    unread = invoke(run, "build")
    check("verifier table: a table with another heading is named, not skipped in silence",
          unread.returncode == 2 and "heading isn't" in unread.stderr, unread.stderr)
    write(run, "verify-1.md", "# Verification\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
          "| 1a | Expiry skipped | REFUTED | guarded |\n")
    unread = invoke(run, "build")
    check("verifier table: a row whose id matches no claim is named, whatever the id's shape",
          unread.returncode == 2 and "unknown claim 1a" in unread.stderr, unread.stderr)
    sent_back = invoke_table(run / "verify-1.md")
    write(run, "verify-1.md", "# Verification\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
          "| **1** | Expiry skipped | **REFUTED** | guarded\n")
    passed = invoke_table(run / "verify-1.md")
    check("verifier table: the seat check's reading of one file sends back what the index can't read, "
          "and passes what it can", sent_back.returncode == 1 and "unknown claim 1a" in sent_back.stdout and
          passed.returncode == 0 and passed.stdout == "", (sent_back.stdout, passed.stdout))
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
    # A section is Kept or Cut by its first word, as council check reads it.
    write(run, "synthesis.md", "# Synthesis\n## Kept (1)\n"
          "1 · P1 · gate · src/auth.py:4 · Lint failed · state: OBSERVED · from: gate:lint\n"
          "## Cut (not shipped)\nC1 · P1 · Principle 1 · src/auth.py:4 · Risky cut · state: INFERRED · from: hunt#3\n")
    write(run, "verify-1.md", "# Verification\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
          "| 1 | Lint failed | CONFIRMED | lint.json exit 1 |\n")
    headed = invoke(run, "build")
    checked = invoke(run, "check")
    check("sections: '## Kept (1)' and '## Cut (not shipped)' are read, so an unverified cut P1 still fails",
          headed.returncode == 0 and [c["id"] for c in claims(run)] == ["1", "C1"] and checked.returncode == 1
          and "claim C1: cut P1 has no verification link" in checked.stdout, headed.stdout + headed.stderr + checked.stdout)
    write(run, "synthesis.md", "# Synthesis\n## Kept\n"
          "1 · P1 · gate · src/auth.py:4 · Lint failed · state: OBSERVED · from: gate:lint\n"
          "## Findings we cut\nC1 · P1 · Principle 1 · src/auth.py:4 · Risky cut · state: INFERRED · from: hunt#3\n")
    unread = invoke(run, "build")
    check("sections: a heading that names cut but doesn't start with it is said, not skipped",
          unread.returncode == 2 and "'Findings we cut' is not read" in unread.stderr, unread.stderr)

    # A cut claim the verifier CONFIRMED (run 1's main finding stayed on record as cut): restored to Kept
    # with its id, or kept out with a reason — never left as a cut item that is true.
    head = "# Verification\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
    rows = "| 1 | Minor | CONFIRMED | a.py:1 |\n| C1 | Rules changed | CONFIRMED | a.py:9 |\n"
    kept = "1 · P3 · P · a.py:1 · Minor · state: OBSERVED · from: chair\n"
    cut = "C1 · P2 · P · a.py:9 · Rules changed · why: overlaps 1 · {}state: OBSERVED · from: chair\n"
    confirmed = fresh(folder, "cut-confirmed", "council-review",
                      "# Synthesis\n## Kept\n" + kept + "## Cut\n" + cut.format(""), {"verify-1.md": head + rows})
    invoke(confirmed, "build")
    left = invoke(confirmed, "check")
    check("a cut claim the verifier confirmed fails the check until it is restored or kept out with a reason",
          left.returncode == 1 and "claim C1: cut, but its verifier found it CONFIRMED" in left.stdout, left.stdout)
    write(confirmed, "synthesis.md", "# Synthesis\n## Kept\n" + kept + cut.format("") + "## Cut\n(none)\n")
    restored = invoke(confirmed, "build")
    check("a restored claim moves to Kept with its id: checked as kept, recorded as restored",
          restored.returncode == 0 and invoke(confirmed, "check").returncode == 0 and
          claims(confirmed)[1]["disposition"] == "kept" and claims(confirmed)[1].get("restored") is True and
          "C1 kept (restored)" in invoke(confirmed, "show").stdout, restored.stdout + restored.stderr)
    write(confirmed, "synthesis.md", "# Synthesis\n## Kept\n" + kept + "## Cut\n" +
          cut.format("still-cut: the user ruled it out of scope · "))
    invoke(confirmed, "build")
    check("a confirmed cut claim may stay cut with its reason recorded",
          invoke(confirmed, "check").returncode == 0 and
          claims(confirmed)[1].get("still_cut") == "the user ruled it out of scope")

    # A plan sends one claim per task assumption, numbered with its recommendation: several rows, worst stands.
    plan_rows = head + ("| 1 | task 1: the join exists | CONFIRMED | db.sql:4 |\n"
                        "| 1 | task 2: the index is unique | REFUTED | db.sql:9 has none |\n"
                        "| - | task 3: a new file | CONFIRMED | nothing by that name |\n"
                        "| 2 | task 3: the queue is ordered | UNCERTAIN | no test covers it |\n"
                        "| 2 | task 4: the queue drains | CONFIRMED | q.py:7 |\n")
    plan_syn = ("# Synthesis\n## Kept\n1 · P1 · P · db.sql · One table · state: INFERRED · from: chair\n"
                "2 · P2 · P · q.py · A queue · state: INFERRED · from: chair\n## Cut\n(none)\n")
    planned = fresh(folder, "plan", "council-plan", plan_syn, {"verify-1.md": plan_rows})
    built = invoke(planned, "build")
    check("plan: several verifier rows per recommendation build, and the worst verdict stands",
          built.returncode == 0 and [c["verdict"] for c in claims(planned)] == ["REFUTED", "UNCERTAIN"] and
          [len(c["verification"]) for c in claims(planned)] == [2, 2] and invoke(planned, "check").returncode == 0,
          built.stdout + built.stderr)
    sys.path.insert(0, str(ROOT / "scripts"))
    import evidence                    # noqa: E402  (memory propose reads the index through it)
    again, _ = evidence.synthesis(planned)
    check("plan: a reader that doesn't name the mode (memory propose) finds the index current",
          evidence.verifier_rows(planned, again) == [] and
          evidence.render(again) == (planned / "claims.jsonl").read_text(encoding="utf-8"))
    reviewed = fresh(folder, "not-a-plan", "council-review", plan_syn, {"verify-1.md": plan_rows})
    check("review: several rows for one claim are still a conflict to resolve", invoke(reviewed, "build").returncode == 2)

    # Solo: the Chair checks its own items into verify-self.md, labelled self-checked, never as independent.
    own = head + "| 1 | One table | CONFIRMED | db.sql:4 read |\n| 2 | A queue | REFUTED | q.py:7 drains |\n"
    solo = fresh(folder, "solo", "council-review", plan_syn, {"verify-self.md": own}, level="self", size="solo")
    built = invoke(solo, "build")
    check("solo: the Chair's own check is a recorded verdict the index labels self-checked, and the check passes",
          built.returncode == 0 and invoke(solo, "check").returncode == 0 and
          all(c["verification"][0].get("self") is True for c in claims(solo)) and
          "(self-checked)" in invoke(solo, "show").stdout, built.stdout + built.stderr)
    squad = fresh(folder, "squad-self", "council-review", plan_syn, {"verify-self.md": own})
    invoke(squad, "build")
    alone = invoke(squad, "check")
    check("squad: a self-check alone does not stand in for the independent verifier the plan calls for",
          alone.returncode == 1 and "only the Chair's own check" in alone.stdout, alone.stdout)
    write(squad, "verify-1.md", head + "| 1 | One table | REFUTED | no join |\n| 2 | A queue | REFUTED | q.py:7 |\n")
    both = invoke(squad, "build")
    check("squad: the independent verifier's verdict outranks the Chair's own, with no conflict",
          both.returncode == 0 and claims(squad)[0]["verdict"] == "REFUTED" and
          invoke(squad, "check").returncode == 0, both.stdout + both.stderr)

    (run / "verify-1.md").unlink()
    write(run, "synthesis.md", "# Synthesis\n## Kept\n(none) — no findings\n## Cut\n"
          "C1 · P1 · Principle 1 · src/auth.py:4 · Risky cut · state: INFERRED · from: hunt#3\n")
    final_build = invoke(run, "build")
    check("cut P1 needs its own verification link", final_build.returncode == 0 and
          invoke(run, "check").returncode == 1)

    # A summary table after the verdict table is not read as more verdict rows; a | inside `code` is text.
    tail = fresh(folder, "summary-after", "council-review",
                 "# Synthesis\n## Kept\n1 · P2 · Principle 1 · src/gate.sh:3 · Gate a|b hides failures · state: OBSERVED · from: hunt#1\n",
                 {"verify-1.md": "# Verification\n| # | Item | Verdict | Evidence |\n|---|---|---|---|\n"
                                 "| 1 | Gate `a | b` hides failures | CONFIRMED | src/gate.sh:3 pipes into tee |\n\n"
                                 "## Summary\n| Seat | Items | Confirmed | Refuted |\n|---|---|---|---|\n| hunt | 1 | 1 | 0 |\n"})
    table = invoke_table(tail / "verify-1.md")
    built = invoke(tail, "build")
    check("verifier table: a later summary table is left alone, and a | inside backticks stays in its cell",
          table.returncode == 0 and built.returncode == 0 and claims(tail)[0]["verdict"] == "CONFIRMED",
          table.stdout + table.stderr + built.stdout + built.stderr)

for name, okay, detail in results:
    print("[{}] {}".format("PASS" if okay else "FAIL", name))
    if not okay and detail:
        print("       " + str(detail)[:900].replace("\n", "\n       "))
passed = sum(okay for _, okay, _ in results)
print("\n{}/{} checks passed".format(passed, len(results)))
sys.exit(0 if passed == len(results) else 1)
