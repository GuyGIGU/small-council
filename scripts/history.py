#!/usr/bin/env python3
"""History across a council home's runs, with each rate shown only when enough runs carry its data.

It reports what runs cost, how far their estimates were off, what their gates, verifiers and repair
trails caught, and how much each seat's record supports. It reads every run folder under
<home>/runs through the cockpit's read-only snapshot, and the seat ledger through
`council ledger advice`'s code. It writes nothing. A count is always shown. A median, a share or a
ratio needs MIN_RUNS runs that carry its data; below that the report says "too few" and gives the
count, never a number that could be mistaken for a trend. Nothing here tunes anything: `council tune`
reads this report and proposes, and the user decides.
"""

import argparse
import json
import math
from pathlib import Path
import re
import statistics
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cockpit  # noqa: E402  (the read-only run snapshot)
import ledger   # noqa: E402  (seat evidence and advice)

SCHEMA = "council.history/2"
MIN_RUNS = 5          # runs that carry a fact before a median, share or ratio over them is shown
MAX_RUNS = 1000       # the most recent runs read
SEAT_WINDOW = 20      # the runs of the ledger read for seat evidence, as council ledger advice reads them
CHAIR_ESTIMATE = 20000  # the Chair's share of a route estimate; seats.tsv never records the Chair
CATCHES = ("REFUTED", "MISCITED")
CHECKED = ("CONFIRMED", "REFUTED", "MISCITED")


def run_folders(home):
    runs = Path(home) / "runs"
    if not runs.is_dir() or cockpit.linked(runs):
        return []
    found = [p for p in runs.iterdir()
             if p.is_dir() and not cockpit.linked(p) and (p / "session-state.md").is_file()]
    return sorted(found, key=lambda p: p.name)[-MAX_RUNS:]


def spread(values):
    """Median and 10th–90th percentile of a list, when there are enough values to trust them."""
    values = sorted(values)
    if len(values) < MIN_RUNS:
        return {"n": len(values), "enough": False}
    at = lambda q: values[min(len(values) - 1, max(0, math.ceil(q * len(values)) - 1))]  # noqa: E731
    return {"n": len(values), "enough": True, "median": round(statistics.median(values), 3), "p10": at(0.1),
            "p90": at(0.9)}


def rate(pairs):
    """k of n summed over runs, from (k, n) per run, with a 90% plausible range — only once MIN_RUNS
    runs carry the data. Items of one run count at most as the seat advice counts them."""
    pairs = [(k, n) for k, n in pairs if n > 0]
    k, n = sum(k for k, _ in pairs), sum(n for _, n in pairs)
    if len(pairs) < MIN_RUNS:
        return {"k": k, "n": n, "runs": len(pairs), "enough": False}
    got = ledger.share(pairs)
    return {"k": k, "n": n, "runs": len(pairs), "enough": True, "share": got["share"], "low": got["low"],
            "high": got["high"]}


def month_of(name):
    match = re.match(r"(\d{4}-\d{2})-\d{2}-", name)
    return match.group(1) if match else "unknown"


def history(home):
    home = Path(home)
    runs = [cockpit.snapshot(folder, None, last_events=0) for folder in run_folders(home)]  # memory is not read
    by_status, by_mode, by_month = {}, {}, {}
    for snap in runs:
        info = snap["run"]
        by_status[info["status"] or "unknown"] = by_status.get(info["status"] or "unknown", 0) + 1
        by_mode[info["mode"] or "unknown"] = by_mode.get(info["mode"] or "unknown", 0) + 1
        by_month[month_of(info["id"])] = by_month.get(month_of(info["id"]), 0) + 1
    complete = [s for s in runs if s["run"]["status"] == "complete"]
    costed = [s for s in complete if s["tokens"]["total"] > 0]
    ratios = []
    for snap in costed:                  # agents' tokens against the plan's estimate less the Chair's share
        estimate = cockpit.number(snap["plan"].get("estimated-tokens")) - CHAIR_ESTIMATE
        if estimate > 0:
            ratios.append(snap["tokens"]["total"] / estimate)
    agents = [s["tokens"]["total"] / s["agents"] for s in costed if s["agents"] > 0]
    sizes = {}
    for snap in runs:
        size = snap["plan"].get("size", "")
        if size in ("solo", "squad", "full"):
            sizes[size] = sizes.get(size, 0) + 1
    gates, proofs = {}, {"before": [0, 0], "after": [0, 0], "probe": [0, 0]}
    for snap in runs:
        for gate in snap["gates"]:
            kind = next((p for p in proofs if gate["name"].startswith(p + "-")), None)
            if kind:                      # a build's before/after proof or a gate's dry run, not a project gate
                proofs[kind][0] += 1
                proofs[kind][1] += gate["exit"] != 0
                continue
            entry = gates.setdefault(gate["name"], {"runs": set(), "failed_runs": set()})
            entry["runs"].add(snap["run"]["id"])
            if gate["exit"] != 0:
                entry["failed_runs"].add(snap["run"]["id"])
    tasks, categories, finished = [], {}, []
    for snap in runs:
        resolved = stopped = 0
        for task, info in snap["repairs"].items():
            tasks.append(info["next"])
            resolved += info["next"] == "resolved"
            stopped += info["next"] == "stop"
            if info.get("failure_category"):
                categories[info["failure_category"]] = categories.get(info["failure_category"], 0) + 1
        finished.append((resolved, resolved + stopped))
    verdicts, claim_runs, checked_runs = {}, 0, []
    for snap in runs:
        if snap["claims"]["total"]:
            claim_runs += 1
            for verdict, n in snap["claims"]["by_verdict"].items():
                verdicts[verdict] = verdicts.get(verdict, 0) + n
            by = snap["claims"]["by_verdict"]
            checked_runs.append((sum(by.get(v, 0) for v in CATCHES), sum(by.get(v, 0) for v in CHECKED)))
    seats = ledger.report(home / "ledger.tsv", SEAT_WINDOW)
    advice = {}
    for seat in seats["seats"]:
        advice[seat["advice"]] = advice.get(seat["advice"], 0) + 1
    quality = {"no_plan": sum(1 for s in runs if not s["plan"].get("size")),
               "no_events": sum(1 for s in runs if not s["events"]["present"]),
               "bad_events": sum(1 for s in runs if s["events"]["present"] and
                                 (not s["events"]["header_ok"] or s["events"]["malformed"])),
               "open": by_status.get("in-progress", 0) + by_status.get("paused", 0)}
    opened = sorted(s["run"]["id"][:10] for s in runs)
    return {
        "schema": SCHEMA, "home": str(home), "min_runs": MIN_RUNS,
        "runs": {"total": len(runs), "by_status": by_status, "by_mode": by_mode, "by_month": dict(sorted(by_month.items())),
                 "first": opened[0] if opened else None, "last": opened[-1] if opened else None, "sizes": sizes},
        "cost": {"tokens_per_run": spread([s["tokens"]["total"] for s in costed]),
                 "agents_per_run": spread([s["agents"] for s in costed]),
                 "tokens_per_agent": spread(agents)},
        "estimates": {"actual_over_estimate": spread(ratios)},
        "gates": {name: {"runs": len(e["runs"]), "failed_runs": len(e["failed_runs"])} for name, e in sorted(gates.items())},
        "proofs": {"before_checks": proofs["before"][0], "before_failed_as_intended": proofs["before"][1],
                   "after_checks": proofs["after"][0], "after_failed": proofs["after"][1],
                   "probes": proofs["probe"][0], "probes_failed": proofs["probe"][1]},
        "repairs": {"tasks": len(tasks), "resolved": tasks.count("resolved"), "stopped": tasks.count("stop"),
                    "open": len(tasks) - tasks.count("resolved") - tasks.count("stop"),
                    "resolved_share": rate(finished),
                    "categories": dict(sorted(categories.items()))},
        "claims": {"runs": claim_runs, "verdicts": dict(sorted(verdicts.items())),
                   "caught_share": rate(checked_runs)},
        "seats": {"in_ledger": len(seats["seats"]), "advice": dict(sorted(advice.items())),
                  "weighed": sorted(s["seat"] for s in seats["seats"] if s.get("weighed"))},
        "quality": quality,
    }


def too_few(n, what="runs"):
    return "too few {} ({} of {} needed)".format(what, n, MIN_RUNS)


def k(tokens):
    return "~{}k".format(round(tokens / 1000))


def render(data):
    runs = data["runs"]
    if not runs["total"]:
        return "no council runs yet in {}/runs".format(data["home"])
    lines = ["council history · {} run(s) · {} → {} · {}".format(
        runs["total"], runs["first"], runs["last"],
        ", ".join("{} {}".format(n, s) for s, n in sorted(runs["by_status"].items()))),
        "a median, share or ratio needs {} runs that carry its data; below that you see the count only".format(
            data["min_runs"]), ""]
    lines.append("Runs by mode: " + " · ".join("{} {}".format(m, n) for m, n in sorted(runs["by_mode"].items())))
    lines.append("Runs by month: " + " · ".join("{} {}".format(m, n) for m, n in runs["by_month"].items()))
    if runs["sizes"]:
        lines.append("Planned size: " + " · ".join("{} {}".format(s, n) for s, n in sorted(runs["sizes"].items())))
    cost = data["cost"]
    t, a, w = cost["tokens_per_run"], cost["agents_per_run"], cost["tokens_per_agent"]
    lines.append("")
    lines.append("Cost per completed run: " + (
        "median {} tokens (10–90%: {}–{}), median {} agent(s)".format(k(t["median"]), k(t["p10"]), k(t["p90"]), a["median"])
        if t["enough"] else too_few(t["n"], "completed runs with a recorded cost")))
    lines.append("Tokens per agent (workers and verifiers): " + (
        "median {} (10–90%: {}–{})".format(k(w["median"]), k(w["p10"]), k(w["p90"]))
        if w["enough"] else too_few(w["n"], "completed runs with agents")))
    e = data["estimates"]["actual_over_estimate"]
    lines.append("Estimates: " + (
        "agents cost {:.2f}× the plan's estimate less the Chair's 20k, at the median (10–90%: {:.2f}–{:.2f}×)".format(
            e["median"], e["p10"], e["p90"]) if e["enough"]
        else too_few(e["n"], "completed runs with both an estimate and a cost")))
    lines.append("")
    if data["gates"]:
        ranked = sorted(data["gates"].items(), key=lambda item: (-item[1]["runs"], item[0]))
        shown = ["{} ran in {} run(s), failed in {}".format(name, g["runs"], g["failed_runs"]) for name, g in ranked[:8]]
        more = " · and {} more".format(len(ranked) - 8) if len(ranked) > 8 else ""
        lines.append("Gates: " + " · ".join(shown) + more)
    else:
        lines.append("Gates: none recorded")
    p = data["proofs"]
    if p["before_checks"] or p["after_checks"] or p["probes"]:
        lines.append("  build proofs: {} before-check(s), {} failing as intended · {} after-check(s), {} failed · "
                     "{} probe(s), {} failed".format(p["before_checks"], p["before_failed_as_intended"],
                                                     p["after_checks"], p["after_failed"], p["probes"], p["probes_failed"]))
    r = data["repairs"]
    if r["tasks"]:
        share = r["resolved_share"]
        lines.append("Repairs: {} task(s) · {} resolved · {} stopped · {} still open · resolved {}".format(
            r["tasks"], r["resolved"], r["stopped"], r["open"],
            "{:.0%} (plausible {:.0%}–{:.0%})".format(share["share"], share["low"], share["high"]) if share["enough"]
            else too_few(share["runs"], "runs with a finished repair trail")))
        if r["categories"]:
            lines.append("  failure categories: " + " · ".join("{} {}".format(c, n) for c, n in r["categories"].items()))
    else:
        lines.append("Repairs: none recorded")
    c = data["claims"]
    if c["runs"]:
        caught = c["caught_share"]
        lines.append("Claims: {} run(s) with an evidence ledger · {} · verifier caught {}".format(
            c["runs"], " · ".join("{} {}".format(v, n) for v, n in c["verdicts"].items()),
            "{:.0%} of checked claims (plausible {:.0%}–{:.0%})".format(caught["share"], caught["low"], caught["high"])
            if caught["enough"] else too_few(caught["runs"], "runs with checked claims")))
    else:
        lines.append("Claims: none recorded (no run built an evidence ledger)")
    s = data["seats"]
    lines.append("Seats: {} in the ledger · {} weighed{} — council ledger advice".format(
        s["in_ledger"], len(s["weighed"]), " ({})".format(", ".join(s["weighed"])) if s["weighed"] else ""))
    q, notes = data["quality"], []
    if q["open"]:
        notes.append("{} run(s) still open or paused".format(q["open"]))
    if q["no_plan"]:
        notes.append("{} run(s) have no filled run plan".format(q["no_plan"]))
    if q["no_events"]:
        notes.append("{} run(s) have no events.tsv (older than the event stream)".format(q["no_events"]))
    if q["bad_events"]:
        notes.append("{} run(s) have a malformed events.tsv — council run events check --run <folder>".format(q["bad_events"]))
    if notes:
        lines.append("")
        lines.append("Data: " + "; ".join(notes))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", required=True, type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    data = history(args.home)
    print(json.dumps(data, indent=2, sort_keys=True) if args.json else render(data))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ledger.LedgerError, OSError, ValueError) as exc:
        print("history: " + str(exc), file=sys.stderr)
        sys.exit(2)
