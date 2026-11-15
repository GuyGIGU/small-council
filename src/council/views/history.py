"""History across a council home's runs, with each rate shown only when enough runs carry its data.

It reports what runs cost, how far their estimates were off, what their gates, verifiers and repair
trails caught, and how much each seat's record supports. It reads every run folder under
<home>/runs through the cockpit's read-only snapshot, and the seat ledger through
`council ledger advice`'s code. It writes nothing. A count is always shown. A median, a share or a
ratio needs MIN_RUNS runs that carry its data; below that the report says "too few" and gives the
count, never a number that could be mistaken for a trend. Five runs make a figure eligible to be
shown; they do not make it reliable. Nothing here tunes anything: `council tune` reads this report and
proposes, and the user decides.

Cost figures use only completed runs whose records support them (references/run/run-accounting.md):
every agent run's tokens reported or corrected from evidence, and an exact agent-run count. A run
from before that accounting, with a missing usage report or an implausible count, is left out and
counted under "Data", never folded in as a zero or a guess.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable

from council.commands import seat_advice as ledger     # seat evidence and advice; ledger.LedgerError is a fault
from council.records import ledger as ledger_file, paths, usage_gaps
from council.records.cells import number
from council.records.usage import token_text
from council.views import cockpit, outcomes as finding_outcomes

Snap = Dict[str, Any]
SCHEMA = "council.history/4"
MIN_RUNS = 5          # runs that carry a fact before a median, share or ratio over them is shown
MAX_RUNS = 1000       # the most recent runs read
SEAT_WINDOW = 20      # the runs of the ledger read for seat evidence, as council ledger advice reads them
CHAIR_ESTIMATE = 20000  # the Chair's share of a route estimate; seats.tsv never records the Chair
CATCHES = ("REFUTED", "MISCITED")
CHECKED = ("CONFIRMED", "REFUTED", "MISCITED")


def spread(values: Iterable[float]) -> dict[str, Any]:
    """Median and 10th–90th percentile of a list, when there are enough values to trust them."""
    values = sorted(values)
    if len(values) < MIN_RUNS:
        return {"n": len(values), "enough": False}

    def at(q: float) -> float:
        return values[min(len(values) - 1, max(0, math.ceil(q * len(values)) - 1))]

    return {"n": len(values), "enough": True, "median": round(statistics.median(values), 3), "p10": at(0.1),
            "p90": at(0.9)}


def rate(pairs: Iterable[tuple[int, int]]) -> dict[str, Any]:
    """k of n summed over runs, from (k, n) per run, with a 90% plausible range — only once MIN_RUNS
    runs carry the data. Items of one run count at most as the seat advice counts them."""
    pairs = [(k, n) for k, n in pairs if n > 0]
    k, n = sum(k for k, _ in pairs), sum(n for _, n in pairs)
    if len(pairs) < MIN_RUNS:
        return {"k": k, "n": n, "runs": len(pairs), "enough": False}
    got = ledger.share(pairs)
    return {"k": k, "n": n, "runs": len(pairs), "enough": True, "share": got["share"], "low": got["low"],
            "high": got["high"]}


def total_of(snap: Snap) -> int:
    return snap["usage"]["tokens"]["total"]


def runs_of(snap: Snap) -> int:
    return snap["usage"]["agents"]["total"]


def cost_gap(snap: Snap) -> str:
    """Why a completed run's cost can't be counted, or '' when it can: tokens known for every agent
    run, an exact agent-run count, and something spent."""
    tokens, agents = snap["usage"]["tokens"], snap["usage"]["agents"]
    gap = {"none": "no agent runs recorded", "legacy": "older records (units never checked)",
           "suspect": "implausible token counts", "complete": ""}.get(tokens["basis"], "usage reports missing")
    if gap or agents["total"] is None:
        return gap or "agent-run count not exact"
    if not tokens["total"] or not agents["total"]:
        return "nothing spent on record"
    return ""


def month_of(name: str) -> str:
    match = re.match(r"(\d{4}-\d{2})-\d{2}-", name)
    return match.group(1) if match else "unknown"


def history(home: str | Path, outcomes: bool = True) -> dict[str, Any]:
    """The run history report. outcomes=False skips the finding-outcome comparison (a few Git processes
    per cited file in every closed run) for a caller that never reads it; its section is then None."""
    home = Path(home)
    runs = [cockpit.snapshot(folder, None, last_events=0) for folder in paths.run_folders(home, MAX_RUNS)]  # no memory
    by_status = Counter(s["run"]["status"] or "unknown" for s in runs)
    complete = [s for s in runs if s["run"]["status"] == "complete"]
    seats = ledger.report(ledger_file.path(home), SEAT_WINDOW)
    opened = sorted(s["run"]["id"][:10] for s in runs)
    outcome_data = finding_outcomes.outcomes(home, Path.cwd()) if outcomes else None
    cost, ratios = cost_of(complete)
    gates, proofs = gates_of(runs)
    return {
        "schema": SCHEMA, "home": str(home), "min_runs": MIN_RUNS,
        "runs": {"total": len(runs), "by_status": dict(by_status),
                 "by_mode": dict(Counter(s["run"]["mode"] or "unknown" for s in runs)),
                 "by_month": dict(sorted(Counter(month_of(s["run"]["id"]) for s in runs).items())),
                 "first": opened[0] if opened else None, "last": opened[-1] if opened else None,
                 "sizes": dict(Counter(s["plan"].get("size", "") for s in runs
                                       if s["plan"].get("size", "") in ("solo", "squad", "full")))},
        "cost": cost,
        "estimates": {"actual_over_estimate": spread(ratios)},
        "gates": gates,
        "proofs": proofs,
        "repairs": repairs_of(runs),
        "claims": claims_of(runs),
        "outcomes": {"runs": len(outcome_data["runs"]), "kept": outcome_data["totals"]["kept"],
                     "cut": outcome_data["totals"]["cut"]} if outcome_data is not None else None,
        "seats": {"in_ledger": len(seats["seats"]),
                  "advice": dict(sorted(Counter(seat["advice"] for seat in seats["seats"]).items())),
                  "weighed": sorted(s["seat"] for s in seats["seats"] if s.get("weighed"))},
        "quality": {"no_plan": sum(1 for s in runs if not s["plan"].get("size")),
                    "no_events": sum(1 for s in runs if not s["events"]["present"]),
                    "bad_events": sum(1 for s in runs if s["events"]["present"] and
                                      (not s["events"]["header_ok"] or s["events"]["malformed"])),
                    "open": by_status.get("in-progress", 0) + by_status.get("paused", 0)},
    }


def cost_of(complete: list[Snap]) -> tuple[dict[str, Any], list[float]]:
    """What completed runs cost, only from a run whose record supports a total, and each costed run's agents'
    tokens over the plan's estimate less the Chair's share. Tokens are grouped by the plan's requested model,
    never inferred as the actual model used."""
    costed, left_out = [], Counter()
    for snap in complete:
        why = cost_gap(snap)
        if why:
            left_out[why] += 1
        else:
            costed.append(snap)
    by_model: dict[str, dict[str, Any]] = {}
    for snap in costed:
        planned = snap["plan"].get("seats", {})
        for seat in snap["seats"]:
            if not seat.get("executed") or seat.get("tokens") is None:
                continue
            entry = by_model.setdefault(planned.get(seat["slug"], {}).get("model") or "inherit",
                                        {"tokens": 0, "seats": 0, "runs": set()})
            entry["tokens"] += seat["tokens"]
            entry["seats"] += 1
            entry["runs"].add(snap["run"]["id"])
    ratios = []
    for snap in costed:
        chair = snap["plan"].get("chair-tokens")      # the plan's own Chair share, when it names one
        estimate = number(snap["plan"].get("estimated-tokens")) - (number(chair) if chair else CHAIR_ESTIMATE)
        if estimate > 0:
            ratios.append(total_of(snap) / estimate)
    return {"tokens_per_run": spread([total_of(s) for s in costed]),
            "agents_per_run": spread([runs_of(s) for s in costed]),
            "tokens_per_agent": spread([total_of(s) / runs_of(s) for s in costed]),
            "tokens_by_planned_model": {model: {"tokens": e["tokens"], "seats": e["seats"], "runs": len(e["runs"])}
                                        for model, e in sorted(by_model.items())},
            "left_out": dict(sorted(left_out.items())), "unfigured": usage_gaps.left_out(complete)}, ratios


def gates_of(runs: list[Snap]) -> tuple[dict[str, Any], dict[str, int]]:
    """Each project gate's runs and failed runs, and the builds' before and after proofs and dry runs."""
    gates: dict[str, dict[str, set[str]]] = {}
    proofs = {"before": [0, 0], "after": [0, 0], "probe": [0, 0]}
    preservation = [0, 0]
    for snap in runs:
        for gate in snap["gates"]:
            kind = next((p for p in proofs if gate["name"].startswith(p + "-")), None)
            if kind:                      # a build's before/after proof or a gate's dry run, not a project gate
                proofs[kind][0] += 1
                if kind == "before" and gate.get("proof") == "preserve":
                    preservation[0] += 1
                    preservation[1] += gate["exit"] == 0
                    continue
                proofs[kind][1] += gate["exit"] != 0 and not (kind == "before" and gate.get("void"))
                continue
            entry = gates.setdefault(gate["name"], {"runs": set(), "failed_runs": set()})
            entry["runs"].add(snap["run"]["id"])
            if gate["exit"] != 0:
                entry["failed_runs"].add(snap["run"]["id"])
    return ({name: {"runs": len(e["runs"]), "failed_runs": len(e["failed_runs"])} for name, e in sorted(gates.items())},
            {"before_checks": proofs["before"][0], "before_failed_as_intended": proofs["before"][1],
             "before_preserve_checks": preservation[0], "before_preserve_passed": preservation[1],
             "after_checks": proofs["after"][0], "after_failed": proofs["after"][1],
             "probes": proofs["probe"][0], "probes_failed": proofs["probe"][1]})


def repairs_of(runs: list[Snap]) -> dict[str, Any]:
    tasks, categories, finished = [], Counter(), []
    for snap in runs:
        resolved = stopped = 0
        for info in snap["repairs"].values():
            tasks.append(info["next"])
            resolved += info["next"] == "resolved"
            stopped += info["next"] == "stop"
            if info.get("failure_category"):
                categories[info["failure_category"]] += 1
        finished.append((resolved, resolved + stopped))
    return {"tasks": len(tasks), "resolved": tasks.count("resolved"), "stopped": tasks.count("stop"),
            "open": len(tasks) - tasks.count("resolved") - tasks.count("stop"),
            "resolved_share": rate(finished), "categories": dict(sorted(categories.items()))}


def claims_of(runs: list[Snap]) -> dict[str, Any]:
    verdicts, claim_runs, checked_runs = Counter(), 0, []
    for snap in runs:
        if snap["claims"]["total"]:
            claim_runs += 1
            by = snap["claims"]["by_verdict"]
            verdicts.update(by)
            checked_runs.append((sum(by.get(v, 0) for v in CATCHES), sum(by.get(v, 0) for v in CHECKED)))
    return {"runs": claim_runs, "verdicts": dict(sorted(verdicts.items())), "caught_share": rate(checked_runs)}


# --- the report as text ---------------------------------------------------------------------------------------
def too_few(n: int, what: str = "runs") -> str:
    return "too few {} ({} of {} needed)".format(what, n, MIN_RUNS)


def k(tokens: float) -> str:
    return "~{}".format(token_text(tokens))


def pairs(counts: dict[str, Any]) -> str:
    return " · ".join("{} {}".format(key, n) for key, n in counts.items())


def render(data: dict[str, Any]) -> str:
    runs = data["runs"]
    if not runs["total"]:
        return "no council runs yet in {}/runs".format(data["home"])
    lines = ["council history · {} run(s) · {} → {} · {}".format(
        runs["total"], runs["first"], runs["last"],
        ", ".join("{} {}".format(n, s) for s, n in sorted(runs["by_status"].items()))),
        "a median, share or ratio needs {} runs that carry its data; below that you see the count only. "
        "Reaching {} makes a figure eligible, not reliable: read its spread".format(data["min_runs"], data["min_runs"]),
        ""]
    lines.append("Runs by mode: " + pairs(dict(sorted(runs["by_mode"].items()))))
    lines.append("Runs by month: " + pairs(runs["by_month"]))
    if runs["sizes"]:
        lines.append("Planned size: " + pairs(dict(sorted(runs["sizes"].items()))))
    lines.append("")
    lines += _cost_lines(data)
    lines.append("")
    lines += _catch_lines(data)
    o, s = data["outcomes"], data["seats"]
    if o is not None:
        lines.append("Finding outcomes: {} run(s) · Kept {} changed at cited lines · Cut {} · changed after the run "
                     "does not prove cause".format(o["runs"], o["kept"]["changed at cited lines"],
                                                   o["cut"]["changed at cited lines"]))
    lines.append("Seats: {} in the ledger · {} weighed{} — council ledger advice".format(
        s["in_ledger"], len(s["weighed"]), " ({})".format(", ".join(s["weighed"])) if s["weighed"] else ""))
    notes = _data_notes(data)
    if notes:
        lines.append("")
        lines.append("Data: " + "; ".join(notes))
    return "\n".join(lines)


def _cost_lines(data: dict[str, Any]) -> list[str]:
    cost = data["cost"]
    t, a, w = cost["tokens_per_run"], cost["agents_per_run"], cost["tokens_per_agent"]
    lines = ["Cost per completed run: " + (
        "median {} tokens (10–90%: {}–{}), median {} agent(s)".format(k(t["median"]), k(t["p10"]), k(t["p90"]),
                                                                      a["median"])
        if t["enough"] else too_few(t["n"], "completed runs with a recorded cost")),
        "Tokens per agent (workers and verifiers): " + (
        "median {} (10–90%: {}–{})".format(k(w["median"]), k(w["p10"]), k(w["p90"]))
        if w["enough"] else too_few(w["n"], "completed runs with agents"))]
    if any(model != "inherit" for model in cost["tokens_by_planned_model"]):   # only once routing is used
        lines.append("Tokens by planned model (not money; inherited seats' actual model is unknown): " + " · ".join(
            "{}: {} tokens across {} seat(s), {} run(s)".format(model, info["tokens"], info["seats"], info["runs"])
            for model, info in cost["tokens_by_planned_model"].items()))
    e = data["estimates"]["actual_over_estimate"]
    lines.append("Estimates: " + (
        "agents cost {:.2f}× the plan's estimate less the Chair's share (the plan's, else 20k), at the median "
        "(10–90%: {:.2f}–{:.2f}×)".format(e["median"], e["p10"], e["p90"]) if e["enough"]
        else too_few(e["n"], "completed runs with both an estimate and a cost")))
    return lines


def _catch_lines(data: dict[str, Any]) -> list[str]:
    """What the gates, the build proofs, the repair trails and the verifiers caught."""
    lines = []
    if data["gates"]:
        ranked = sorted(data["gates"].items(), key=lambda item: (-item[1]["runs"], item[0]))
        shown = ["{} ran in {} run(s), failed in {}".format(name, g["runs"], g["failed_runs"])
                 for name, g in ranked[:8]]
        more = " · and {} more".format(len(ranked) - 8) if len(ranked) > 8 else ""
        lines.append("Gates: " + " · ".join(shown) + more)
    else:
        lines.append("Gates: none recorded")
    p = data["proofs"]
    if p["before_checks"] or p["after_checks"] or p["probes"]:
        lines.append("  build proofs: {} before-check(s), {} failing as intended · {} after-check(s), {} failed · "
                     "{} probe(s), {} failed".format(p["before_checks"], p["before_failed_as_intended"],
                                                     p["after_checks"], p["after_failed"], p["probes"],
                                                     p["probes_failed"]))
        if p["before_preserve_checks"]:
            lines.append("  preservation before-checks: {} ran, {} passed (paired proof is checked by council "
                         "check)".format(p["before_preserve_checks"], p["before_preserve_passed"]))
    r = data["repairs"]
    if r["tasks"]:
        share = r["resolved_share"]
        lines.append("Repairs: {} task(s) · {} resolved · {} stopped · {} still open · resolved {}".format(
            r["tasks"], r["resolved"], r["stopped"], r["open"],
            "{:.0%} (plausible {:.0%}–{:.0%})".format(share["share"], share["low"], share["high"]) if share["enough"]
            else too_few(share["runs"], "runs with a finished repair trail")))
        if r["categories"]:
            lines.append("  failure categories: " + pairs(r["categories"]))
    else:
        lines.append("Repairs: none recorded")
    c = data["claims"]
    if c["runs"]:
        caught = c["caught_share"]
        lines.append("Claims: {} run(s) with an evidence ledger · {} · verifier caught {}".format(
            c["runs"], pairs(c["verdicts"]),
            "{:.0%} of checked claims (plausible {:.0%}–{:.0%})".format(caught["share"], caught["low"], caught["high"])
            if caught["enough"] else too_few(caught["runs"], "runs with checked claims")))
    else:
        lines.append("Claims: none recorded (no run built an evidence ledger)")
    return lines


def _data_notes(data: dict[str, Any]) -> list[str]:
    """What the figures left out, and the runs whose records are short."""
    q, left_out, notes = data["quality"], data["cost"]["left_out"], []
    if left_out:
        notes.append("{} completed run(s) left out of cost figures: {}".format(
            sum(left_out.values()), ", ".join("{} {}".format(n, why) for why, n in left_out.items())))
    for key, said in (("open", "{} run(s) still open or paused"), ("no_plan", "{} run(s) have no filled run plan"),
                      ("no_events", "{} run(s) have no events.tsv (older than the event stream)"),
                      ("bad_events", "{} run(s) have a malformed events.tsv — council run events check --run "
                                     "<folder>")):
        if q[key]:
            notes.append(said.format(q[key]))
    return notes


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", required=True, type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    data = history(args.home)
    print(json.dumps(data, indent=2, sort_keys=True) if args.json else render(data))
    return 0
