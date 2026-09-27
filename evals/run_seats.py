#!/usr/bin/env python3
"""Focused, no-model checks for seat learning: `council ledger advice` and scripts/ledger.py.

The advice must stay quiet until a seat's record clears the bar, count only runs that judged its
items, and never read one run's many items as many runs' worth of evidence.
"""

import json
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
sys.path.insert(0, str(ROOT / "scripts"))
import ledger  # noqa: E402  (the helper's own seat-learning code)

checks = []
HEADER = "date\trun\tmode\tseat\traised\tkept\tcut\trefuted\ttokens\n"


def check(name, good, detail=""):
    checks.append((name, good, detail))


def row(run, seat, raised, kept, cut, refuted, tokens=50000, mode="council-review"):
    return "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n".format(run[:10], run, mode, seat, raised, kept, cut, refuted, tokens)


def runs_of(seat, n, raised, kept, cut=0, refuted=0, tokens=50000, start=1, mode="council-review"):
    return "".join(row("2026-09-{:02d}-0000{:02d}-review".format(1 + (start + i) % 28, start + i), seat,
                       raised, kept, cut, refuted, tokens, mode) for i in range(n))


def advise(text, last=20):
    with tempfile.TemporaryDirectory(prefix="council-seats-") as temporary:
        path = Path(temporary) / "ledger.tsv"
        path.write_text(HEADER + text, encoding="utf-8", newline="\n")
        data = ledger.report(path, last)
    return data, {seat["seat"]: seat for seat in data["seats"]}


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


# --- the arithmetic -------------------------------------------------------------------------------
low, high = ledger.wilson(0, 10, 1.645)
check("a range: none of 10 still leaves up to about a fifth plausible", low == 0 and 0.18 < high < 0.25, (low, high))
low, high = ledger.wilson(10, 10, 1.645)
check("a range: all of 10 still leaves the share plausibly under 80%", high == 1 and 0.75 < low < 0.85, (low, high))
one_run = ledger.share([(8, 8)])
eight_runs = ledger.share([(5, 5)] * 8)
check("one run's items count as at most five items of evidence",
      one_run["counted"] == 5 and eight_runs["counted"] == 40 and one_run["low"] < eight_runs["low"], (one_run, eight_runs))
check("a split or round-2 worker is its seat; a hyphenated name is not split",
      ledger.seat_of("hunt-a") == "hunt" and ledger.seat_of("leach-r2") == "leach"
      and ledger.seat_of("friedman-dodds") == "friedman-dodds", "")

# --- which runs count --------------------------------------------------------------------------------
data, seats = advise(row("2026-09-17-113250-init", "engine", 8, 0, 0, 0, 74304, "council-init")
                     + row("2026-09-20-013508-plan", "fowler", 8, 6, 2, 4, 200562, "council-plan")
                     + "2026-09-20\t2026-09-20-013508-plan\tcouncil-plan\t(verifiers)\t-\t-\t-\t-\t406202\n")
check("a run that credited no items is not judged: its seat is 'never judged', not 0% useful",
      seats["engine"]["advice"] == "collect" and "never judged" in seats["engine"]["reason"]
      and seats["engine"]["useful_share"] is None and data["window"] == {"last": 20, "runs": 2, "judged": 1}, data)
check("today's real record (one judged run) is too little to judge any seat",
      seats["fowler"]["advice"] == "collect" and "too little to judge" in seats["fowler"]["reason"]
      and seats["fowler"]["useful"] == 2 and seats["fowler"]["refuted_share"]["n"] == 6, seats["fowler"])
check("an unjudged run is named in the notes, with its mode",
      any("credited no items (council-init)" in note for note in data["notes"]), data["notes"])

_, seats = advise(runs_of("a", 2, 10, 9))
check("the bar: two judged runs are not enough, however many items", seats["a"]["advice"] == "collect", seats["a"])
_, seats = advise(runs_of("a", 3, 4, 4) + runs_of("b", 3, 5, 5, start=10))
check("the bar: three runs need fifteen items too (12 is short, 15 is enough)",
      seats["a"]["advice"] == "collect" and seats["b"]["advice"] == "retain", (seats["a"]["reason"], seats["b"]["reason"]))

# --- each piece of advice, well inside its region ------------------------------------------------------
_, seats = advise(runs_of("keep", 3, 6, 6, refuted=0) + runs_of("low", 5, 6, 0, cut=6, start=10)
                  + runs_of("drop", 8, 5, 0, cut=5, start=20) + runs_of("noisy", 4, 6, 5, cut=1, refuted=3, start=40)
                  + runs_of("thin", 16, 1, 1, start=50) + runs_of("mixed", 4, 5, 2, cut=3, start=70)
                  + "".join(row("2026-09-{:02d}-0000{:02d}-review".format(1 + (40 + i) % 28, 40 + i),
                                "(verifiers)", "-", "-", "-", "-", 9000) for i in range(4)), last=100)
expected = {"keep": "retain", "low": "lower", "drop": "drop?", "noisy": "narrow", "thin": "pair", "mixed": "unclear"}
check("each advice is reached: retain, lower, drop?, narrow, pair and unclear",
      all(seats[name]["advice"] == want for name, want in expected.items()),
      {name: (seats[name]["advice"], seats[name]["reason"]) for name in expected})
check("dropping is only ever a question for the user, after eight judged runs",
      "the user decides" in seats["drop"]["reason"] and len(seats["drop"]["judged_runs"]) == 8, seats["drop"]["reason"])
_, seats = advise(runs_of("fewer", 4, 5, 0, cut=5) + runs_of("fifth", 4, 5, 1, cut=4, start=10))
check("the same poor record over four runs says 'lower', never 'drop?'", seats["fewer"]["advice"] == "lower", seats["fewer"])
check("one useful item in five over four runs is still 'unclear': 20% could plausibly be 38%",
      seats["fifth"]["advice"] == "unclear" and seats["fifth"]["useful_share"]["high"] >= 0.3, seats["fifth"]["reason"])

# --- cost, windows, split workers and loose credit ------------------------------------------------------
_, seats = advise(runs_of("a", 3, 6, 6, tokens=30000) + runs_of("b", 3, 6, 6, tokens=30000, start=10)
                  + runs_of("c", 3, 6, 6, tokens=30000, start=20) + runs_of("d", 3, 6, 6, tokens=300000, start=30))
check("a seat that costs far more per useful item than the others is marked costly",
      seats["d"]["costly"] and not seats["a"]["costly"] and seats["d"]["advice"] == "retain", seats["d"]["costly"])
data, seats = advise(runs_of("old", 5, 6, 0, cut=6) + runs_of("new", 3, 6, 6, start=10), last=3)
check("the window keeps the last N runs only", "old" not in seats and data["window"]["runs"] == 3, data["window"])
_, seats = advise(row("2026-09-16-000000-review", "hunt-a", 2, 1, 0, 0, 10000)
                  + row("2026-09-16-000000-review", "hunt-b", 2, 1, 0, 0, 20000)
                  + row("2026-09-16-000000-review", "leach-r2", 0, 0, 0, 0, 4000))
check("split workers add up to one seat in one run; a round-2 worker raises nothing new",
      seats["hunt"]["raised"] == 4 and len(seats["hunt"]["runs"]) == 1 and seats["hunt"]["tokens"] == 30000
      and seats["leach"]["raised"] == 0, (seats["hunt"], seats["leach"]))
data, seats = advise(row("2026-09-20-013508-plan", "nygard-perf", 8, 5, 4, 1) + row("2026-09-20-013508-plan", "z", 2, 5, 0, 0))
check("kept and cut beyond raised is noted, and a run's useful items never exceed its raised items",
      any("credited loosely" in note for note in data["notes"]) and seats["z"]["useful"] == 2
      and seats["z"]["useful_share"]["share"] == 1.0, (data["notes"], seats["z"]["useful_share"]))
data, seats = advise(runs_of("hunt", 3, 5, 1, cut=4) + "".join(
    row("2026-09-{:02d}-0000{:02d}-review".format(1 + (1 + i) % 28, 1 + i), "hunt-r2", 0, 4, 0, 0) for i in range(3)))
check("credit that arrives through a round-2 worker is folded in before the loose-credit check",
      any("credited loosely" in note and "hunt" in note for note in data["notes"]) and seats["hunt"]["useful"] == 15,
      (data["notes"], seats["hunt"]["useful_share"]))

# --- one big run is not many runs' worth of evidence --------------------------------------------------------
_, seats = advise(row("2026-09-01-000001-review", "x", 15, 0, 15, 0) + row("2026-09-02-000002-review", "o", 5, 5, 0, 0)
                  + row("2026-09-03-000003-review", "o", 5, 5, 0, 0) + row("2026-09-02-000002-review", "x", 0, 0, 0, 0)
                  + row("2026-09-03-000003-review", "x", 0, 0, 0, 0))
check("fifteen items in one run and none in two others are five items of evidence, so too little to judge",
      seats["x"]["advice"] == "collect" and seats["x"]["useful_share"]["counted"] == 5 and "5 item(s) of evidence" in seats["x"]["reason"],
      seats["x"]["reason"])
_, seats = advise(row("2026-09-01-000001-review", "u", 20, 0, 20, 0) + runs_of("u", 3, 5, 5, start=10))
check("one big bad run cannot outweigh three good ones: each run counts at most five items",
      seats["u"]["advice"] == "retain" and seats["u"]["useful_share"]["counted"] == 20
      and seats["u"]["useful_share"]["share"] < 0.5 < seats["u"]["useful_share"]["low"], seats["u"]["useful_share"])
_, seats = advise(runs_of("s", 8, 0, 0) + "".join(row("2026-09-{:02d}-0000{:02d}-review".format(1 + (1 + i) % 28, 1 + i), "s", 10, 0, 10, 0)
                                                    for i in range(2)) + runs_of("o", 8, 5, 5))
check("eight judged runs with items in only two are ten items of evidence: never 'drop?'",
      seats["s"]["advice"] == "collect" and len(seats["s"]["judged_runs"]) == 8, seats["s"]["reason"])
data, seats = advise("not\ta\trow\n" + row("2026-09-16-000000-review", "x", "three", 1, 0, 0)
                     + row("2026-09-16-000000-review", "y", 2, 1, 0, 0).replace("\n", "\r\n"))
check("an unreadable line is left out and counted; a CRLF line is still read",
      "x" not in seats and "y" in seats and any("2 ledger line(s) could not be read" in n for n in data["notes"]), data["notes"])
data, seats = advise("", 20)
with tempfile.TemporaryDirectory(prefix="council-seats-") as temporary:
    odd = Path(temporary) / "ledger.tsv"
    odd.write_bytes(("\ufeff" + HEADER + row("2026-09-16-000000-review", "y", 2, 1, 0, 0)
                     + row("2026-09-17-000000-review", "f", 2, 2, 0, 0).replace("council-review", "council\freview")).encode("utf-8"))
    data = ledger.report(odd, 20)
check("a byte-order mark before the header, and a form feed inside a cell, are read the way awk reads them",
      not data["notes"] and sorted(s["seat"] for s in data["seats"]) == ["f", "y"], data["notes"])

with tempfile.TemporaryDirectory(prefix="council-seats-") as temporary:
    missing = ledger.report(Path(temporary) / "ledger.tsv", 20)
    empty = Path(temporary) / "empty.tsv"
    empty.write_text(HEADER, encoding="utf-8")
    check("no ledger, or a header only, says so plainly",
          "no ledger yet" in ledger.render(missing) and ledger.render(ledger.report(empty, 20)) == "the ledger has no runs yet",
          ledger.render(missing))

# --- through the helper -------------------------------------------------------------------------------
if not BASH or not GIT:
    print("[SKIP] bash or git unavailable — helper checks skipped")
else:
    with tempfile.TemporaryDirectory(prefix="council-seats-") as temporary:
        repo = Path(temporary) / "repo"
        (repo / ".council").mkdir(parents=True)
        subprocess.run([GIT, "init", "-q"], cwd=repo, check=True)
        (repo / ".council" / "council.config.md").write_text("# Council config\n", encoding="utf-8")
        code, out, err = council(repo, "ledger", "advice")
        check("helper: no ledger yet", code == 0 and "no ledger yet" in out, out + err)
        (repo / ".council" / "ledger.tsv").write_text(
            HEADER + row("2026-09-17-113250-init", "engine", 8, 0, 0, 0, 74304, "council-init")
            + runs_of("beck", 3, 6, 6, start=5), encoding="utf-8", newline="\n")
        code, out, err = council(repo, "ledger", "advice")
        check("helper: ledger advice prints the bar, the table and the advice",
              code == 0 and "a seat is weighed after 3 judged runs and 15 items of evidence" in out
              and "- beck: retain" in out and "- engine: never judged" in out, out + err)
        code, out, err = council(repo, "ledger", "advice", "2", "--json")
        try:
            parsed = json.loads(out)
        except ValueError:
            parsed = {}
        check("helper: --json is the same report as data, over the last N runs",
              code == 0 and parsed.get("schema") == "council.seat-advice/1" and parsed["window"]["runs"] == 2, out + err)
        code, out, err = council(repo, "ledger")
        check("helper: the plain ledger shows '-' for a seat no run judged, and points to the advice",
              code == 0 and any(line.split()[:1] == ["engine"] and line.split()[-1] == "-" for line in out.splitlines())
              and "council ledger advice" in out, out)
        refusals = [(council(repo, *words), want) for words, want in (
            (("ledger", "advice", "0"), "usage: council ledger advice"), (("ledger", "advice", "00"), "usage: council ledger advice"),
            (("ledger", "advice", "3", "x"), "usage: council ledger advice [N] [--json]"),
            (("ledger", "--json"), "ledger doesn't take --json"), (("ledger", "advice", "--json=yes"), "--json takes no value"))]
        check("helper: a zero window (0 or 00), an extra word, --json on the plain ledger and --json=… are refused, each saying why",
              all(code == 2 and want in err for (code, _, err), want in refusals), [(c, e) for (c, _, e), _ in refusals])
        (repo / ".council" / "ledger.tsv").write_text(
            HEADER + row("2026-09-17-113250-init", "mix", 8, 0, 0, 0, 1000, "council-init")
            + row("2026-09-18-000000-review", "mix", 4, 4, 0, 0, 1000) + "\n", encoding="utf-8", newline="\n")
        code, out, err = council(repo, "ledger", "1")
        mix = next((line.split() for line in out.splitlines() if line.startswith("mix")), [])
        check("helper: a blank line is no run, and shipped counts only the items a synthesis judged",
              code == 0 and mix[-1:] == ["100%"] and not any(line.startswith(" ") and "%" in line for line in out.splitlines()), out)

passed = sum(good for _, good, _ in checks)
for name, good, detail in checks:
    print(f"[{'PASS' if good else 'FAIL'}] {name}" + ("" if good else f"\n        {str(detail)[:900]}"))
print(f"\n{passed}/{len(checks)} checks passed")
sys.exit(0 if passed == len(checks) else 1)
