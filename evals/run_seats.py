#!/usr/bin/env python3
"""Focused, no-model checks for the seat record: `council ledger` and records/ledger.py.

The record counts each seat over the runs that judged its items, with the roster bar's two facts (judged runs,
items counted at most 5 a run); the Chair weighs it (`council ledger advice`
was removed in 1.2.0, D44).
"""

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
sys.path.insert(0, str(ROOT / "src"))
from council.records import ledger  # noqa: E402  (the helper's own ledger)

checks = []
HEADER = "date\trun\tmode\tseat\traised\tkept\tcut\trefuted\ttokens\taccounting\n"


def check(name, good, detail=""):
    checks.append((name, good, detail))


def row(run, seat, raised, kept, cut, refuted, tokens=50000, mode="council-review", checked=True):
    """A ledger row as the helper writes it: accounting 2 marks a checked token figure (or "-")."""
    return "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}{}\n".format(run[:10], run, mode, seat, raised, kept, cut, refuted, tokens,
                                                         "\t2" if checked else "")


def runs_of(seat, n, raised, kept, cut=0, refuted=0, tokens=50000, start=1, mode="council-review"):
    return "".join(row("2026-09-{:02d}-0000{:02d}-review".format(1 + (start + i) % 28, start + i), seat,
                       raised, kept, cut, refuted, tokens, mode) for i in range(n))


def council(repo, *args, timeout=60):
    env = os.environ.copy()
    for var in ("COUNCIL_RUN", "CLAUDE_CODE_SESSION_ID"):
        env.pop(var, None)
    if os.environ.get("COUNCIL_EVAL_BASH"):
        env["PATH"] = str(Path(BASH).parent) + os.pathsep + env.get("PATH", "")
    words = [BASH, str(ROOT / "bin" / "council"), *args]
    if os.name == "nt":
        words = " ".join('"{}"'.format(word.replace('"', '\\"')) for word in words)
    try:
        result = subprocess.run(words, cwd=repo, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "", "council {}: still running after {} s".format(" ".join(args), timeout)
    return result.returncode, result.stdout, result.stderr


# --- the record's seats ---------------------------------------------------------------------------
check("a split or round-2 worker is its seat; a hyphenated name is not split",
      ledger.seat_of("hunt-a") == "hunt" and ledger.seat_of("leach-r2") == "leach"
      and ledger.seat_of("friedman-dodds") == "friedman-dodds", "")

# --- through the helper -------------------------------------------------------------------------------
if not BASH or not GIT:
    print("[SKIP] bash or git unavailable — helper checks skipped")
else:
    with tempfile.TemporaryDirectory(prefix="council-seats-") as temporary:
        repo = Path(temporary) / "repo"
        (repo / ".council").mkdir(parents=True)
        subprocess.run([GIT, "init", "-q"], cwd=repo, check=True)
        (repo / ".council" / "council.config.md").write_text("# Council config\n", encoding="utf-8")
        code, out, err = council(repo, "ledger")
        check("helper: no ledger yet", code == 0 and "no ledger yet" in out, out + err)
        (repo / ".council" / "ledger.tsv").write_bytes((
            HEADER + row("2026-09-17-113250-init", "engine", 8, 0, 0, 0, 74304, "council-init")
            + runs_of("beck", 3, 6, 6, start=5)).encode("utf-8"))
        for words in (("ledger", "advice"), ("ledger", "advice", "2", "--json")):
            code, out, err = council(repo, *words)
            check("helper: %s is refused as removed in 1.2.0, naming council ledger instead" % " ".join(words),
                  code == 2 and not out and "unknown command 'ledger advice' — removed in 1.2.0" in err
                  and "council ledger [N]" in err, out + err)
        code, out, err = council(repo, "ledger")
        check("helper: the plain ledger shows '-' for a seat no run judged, and points to no advice",
              code == 0 and any(line.split()[:1] == ["engine"] and line.split()[7:8] == ["-"] for line in out.splitlines())
              and "advice" not in out, out)
        refusals = [(council(repo, *words), want) for words, want in (
            (("ledger", "3", "x"), "usage: council ledger [N]"), (("ledger", "--json"), "ledger doesn't take --json"))]
        check("helper: an extra word and --json on the ledger are refused, each saying why",
              all(code == 2 and want in err for (code, _, err), want in refusals), [(c, e) for (c, _, e), _ in refusals])
        (repo / ".council" / "ledger.tsv").write_bytes((
            HEADER + row("2026-09-17-113250-init", "mix", 8, 0, 0, 0, 1000, "council-init")
            + row("2026-09-18-000000-review", "mix", 4, 4, 0, 0, 1000) + "\n").encode("utf-8"))
        code, out, err = council(repo, "ledger", "1")
        mix = next((line.split() for line in out.splitlines() if line.startswith("mix")), [])
        check("helper: a blank line is no run, and shipped counts only the items a synthesis judged",
              code == 0 and mix[7:8] == ["100%"] and not any(line.startswith(" ") and "%" in line for line in out.splitlines()), out)
        # The roster bar's two facts (3 judged runs, 15 items, at most 5 from any one run): totals can't give them.
        (repo / ".council" / "ledger.tsv").write_bytes((
            HEADER + row("2026-09-20-000001-review", "ux", 12, 10, 2, 0) + row("2026-09-21-000002-review", "ux", 2, 2, 0, 0)
            + row("2026-09-22-000003-review", "ux", 1, 1, 0, 0)
            + row("2026-09-20-000001-review", "lens", 3, 2, 1, 0) + row("2026-09-23-000004-init", "lens", 4, 0, 0, 0,
                                                                         mode="council-init")).encode("utf-8"))
        code, out, err = council(repo, "ledger", "20")
        table = {line.split()[0]: line.split() for line in out.splitlines() if line.split()[:1] in (["ux"], ["lens"])}
        header = out.splitlines()[0].split() if out else []
        check("helper: 12, 2 and 1 items in three judged runs show 3 judged runs and 8 counted (at most 5 a run), "
              "beside the unchanged columns", code == 0 and header[-2:] == ["judged", "counted"]
              and header[:8] == ["seat", "runs", "raised", "kept", "cut", "refuted", "~k/run", "shipped"]
              and table.get("ux", [])[1:3] == ["3", "15"] and table.get("ux", [])[-2:] == ["3", "8"], out + err)
        check("helper: a seat with a run that judged nothing shows fewer judged runs than runs, and counts only the "
              "judged one", table.get("lens", [])[1:3] == ["2", "7"] and table.get("lens", [])[-2:] == ["1", "3"]
              and "at most 5 from any one run" in out, out + err)

passed = sum(good for _, good, _ in checks)
for name, good, detail in checks:
    print(f"[{'PASS' if good else 'FAIL'}] {name}" + ("" if good else f"\n        {str(detail)[:900]}"))
print(f"\n{passed}/{len(checks)} checks passed")
sys.exit(0 if passed == len(checks) else 1)
