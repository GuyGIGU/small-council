#!/usr/bin/env python3
"""Seat learning from the council ledger: how much each seat's record can support, and advice only
past a stated bar.

It reads .council/ledger.tsv (a row per seat per completed run) and writes nothing. A run counts
toward a seat's usefulness only when its synthesis credited some items (kept or cut); a run that
credited none (council-init, a build) adds tokens only. Tokens are priced only from rows the helper
marked as checked (accounting 2, see references/run-accounting.md); an older row's token figure was
never checked for units, and "-" is an unknown cost, never a zero. Ranges are Wilson intervals that count at
most a few items per run, because one run's items share a brief, a model and a day. The advice is
for the Chair to put to the user at a refresh; it never changes a roster, a route or a run.
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

SCHEMA = "council.seat-advice/1"
MAX_LEDGER = 8 * 1024 * 1024
COLUMNS = ("date", "run", "mode", "seat", "raised", "kept", "cut", "refuted", "tokens")
CHECKED = "2"           # the accounting column of a row whose tokens are a checked figure or "-"
VERIFIERS = "(verifiers)"
# The bar, stated once so the report, the doctrine and the tests read the same numbers.
BAR = {
    "min_runs": 3,          # judged runs before a seat's record is weighed at all
    "min_items": 15,        # items of evidence it raised in those runs, at most per_run from any one
    "per_run": 5,           # items of one run counted as independent evidence
    "z": 1.645,             # two-sided 90% plausible range
    "retain_floor": 0.5,    # useful share's lower bound at or above this → retain
    "low_ceiling": 0.3,     # useful share's upper bound below this → lower priority
    "refute_floor": 0.3,    # refuted share's lower bound at or above this → narrow or pair
    "min_verified": 10,     # kept items in verified runs before the refuted share is weighed
    "thin_items": 2.0,      # fewer items than this per judged run → pair with a related seat
    "drop_runs": 8,         # judged runs before dropping may even be suggested
    "drop_ceiling": 0.15,   # useful share's upper bound below this, after drop_runs → drop?
    "cost_ratio": 2.0,      # tokens per useful item above this multiple of the median → costly
}
CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class LedgerError(Exception):
    """The ledger cannot be read."""


def seat_of(slug):
    """A split worker (hunt-a) or a fresh round-2 one (hunt-r2) is its seat, as council ledger reads it."""
    return re.sub(r"-(r[0-9]+|[a-z])$", "", slug)


def count(cell):
    cell = cell.strip()
    if not re.fullmatch(r"[0-9]{1,12}", cell):
        raise ValueError(cell)
    return int(cell)


def tokens_of(cells):
    """A row's trusted token figure: a number on a checked row, else None (unknown or unchecked)."""
    checked = len(cells) > 9 and cells[9].strip() == CHECKED
    cell = cells[8].strip()
    if cell in ("-", ""):
        if checked:
            return None
        raise ValueError(cell)
    value = count(cell)
    return value if checked else None


def read_ledger(path):
    """Rows of the ledger as dicts, and how many lines could not be read. None when there is no ledger."""
    path = Path(path)
    if not path.exists():
        return None, 0
    if not path.is_file() or path.stat().st_size > MAX_LEDGER:
        raise LedgerError("the ledger is not a regular file under 8 MB: " + str(path))
    text = path.read_bytes().decode("utf-8-sig", errors="replace")    # a BOM (PowerShell 5.1) is no cell
    rows, bad = [], 0
    for number, line in enumerate(text.split("\n")):                   # as awk splits lines: \n only
        line = line.rstrip("\r")
        if not line.strip() or (number == 0 and line.startswith("date\t")):
            continue
        cells = line.split("\t")
        if len(cells) < len(COLUMNS) or not cells[1].strip() or not cells[3].strip():
            bad += 1
            continue
        row = {"date": cells[0].strip(), "run": cells[1].strip(), "mode": cells[2].strip() or "-",
               "seat": CONTROL.sub("", cells[3].strip())}
        try:
            if row["seat"] == VERIFIERS:
                row.update(raised=0, kept=0, cut=0, refuted=0, tokens=tokens_of(cells))
            else:
                row.update(raised=count(cells[4]), kept=count(cells[5]), cut=count(cells[6]),
                           refuted=count(cells[7]), tokens=tokens_of(cells))
        except ValueError:
            bad += 1
            continue
        rows.append(row)
    return rows, bad


def wilson(k, n, z):
    if n <= 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(max(p * (1 - p) / n + z * z / (4 * n * n), 0.0)) / d
    return max(0.0, c - h), min(1.0, c + h)


def share(pairs, bar=BAR):
    """k of n summed over runs, from (k, n) per run, with a plausible range that counts at most
    bar['per_run'] items of any one run (its k scaled alike). A run with n = 0 adds nothing."""
    pairs = [(min(max(k, 0), n), n) for k, n in pairs if n > 0]
    n = sum(n for _, n in pairs)
    if n <= 0:
        return None
    k = sum(k for k, _ in pairs)
    counted = sum(min(m, bar["per_run"]) for _, m in pairs)
    low, high = wilson(sum(j * min(m, bar["per_run"]) / m for j, m in pairs), counted, bar["z"])
    return {"k": k, "n": n, "share": round(k / n, 4), "low": round(low, 4), "high": round(high, 4),
            "counted": counted}


def window(rows, last):
    """The rows of the last `last` runs, in the order runs first appear — as council ledger picks them."""
    order, seen = [], set()
    for row in rows:
        if row["run"] not in seen:
            seen.add(row["run"])
            order.append(row["run"])
    keep = set(order[-last:]) if last > 0 else seen
    return [row for row in rows if row["run"] in keep], [run for run in order if run in keep]


def records(rows, runs):
    """Per-seat tallies over judged runs (usefulness) and all runs (tokens), plus run-level facts."""
    facts = {run: {"judged": False, "verified": False, "mode": "-", "seat_rows": 0} for run in runs}
    for row in rows:
        fact = facts[row["run"]]
        fact["mode"] = row["mode"] if fact["mode"] == "-" else fact["mode"]
        if row["seat"] == VERIFIERS:
            fact["verified"] = True       # the helper writes this row only when verifiers ran
            continue
        fact["seat_rows"] += 1
        fact["judged"] = fact["judged"] or row["kept"] + row["cut"] > 0
        fact["verified"] = fact["verified"] or row["refuted"] > 0
    seats, loose = {}, []
    for row in rows:                        # fold split and round-2 workers into their seat, run by run
        if row["seat"] == VERIFIERS:
            continue
        seat = seats.setdefault(seat_of(row["seat"]), {"seat": seat_of(row["seat"]), "per_run": {}})
        tally = seat["per_run"].setdefault(row["run"], dict.fromkeys(("raised", "kept", "cut", "refuted", "tokens"), 0))
        for key in ("raised", "kept", "cut", "refuted"):
            tally[key] += row[key]
        if tally["tokens"] is not None:   # one unknown row makes the seat's cost in that run unknown
            tally["tokens"] = None if row["tokens"] is None else tally["tokens"] + row["tokens"]
    for name, seat in seats.items():
        tallies = seat["per_run"]
        mine = [run for run in runs if run in tallies]
        judged = [run for run in mine if facts[run]["judged"]]
        verified = [run for run in judged if facts[run]["verified"]]
        priced = [run for run in mine if tallies[run]["tokens"] is not None]
        priced_judged = [run for run in judged if tallies[run]["tokens"] is not None]
        seat.update(runs=mine, judged_runs=judged, verified_runs=verified, modes={},
                    verified_kept=sum(tallies[run]["kept"] for run in verified),
                    priced_runs=priced, priced_judged_runs=priced_judged,
                    tokens=sum(tallies[run]["tokens"] for run in priced),
                    judged_tokens=sum(tallies[run]["tokens"] for run in priced_judged))
        for key in ("raised", "kept", "cut", "refuted"):
            seat[key] = sum(tallies[run][key] for run in judged)
        for run in judged:
            seat["modes"][facts[run]["mode"]] = seat["modes"].get(facts[run]["mode"], 0) + 1
            if tallies[run]["kept"] + tallies[run]["cut"] > tallies[run]["raised"]:
                loose.append((name, run))
    return seats, facts, loose


def judge(seat, bar=BAR):
    """Fill in a seat's shares and its advice: (code, reason)."""
    judged, raised = len(seat["judged_runs"]), seat["raised"]
    tallies = seat["per_run"]
    seat["useful_share"] = share([(tallies[r]["kept"] - tallies[r]["refuted"], tallies[r]["raised"])
                                  for r in seat["judged_runs"]], bar)
    seat["refuted_share"] = share([(tallies[r]["refuted"], tallies[r]["kept"]) for r in seat["verified_runs"]], bar)
    useful = seat["useful_share"]["k"] if seat["useful_share"] else 0     # each run's useful capped at its items
    counted = seat["useful_share"]["counted"] if seat["useful_share"] else 0
    seat["useful"] = useful
    seat["tokens_per_run"] = round(seat["tokens"] / len(seat["priced_runs"])) if seat["priced_runs"] else None
    priced_useful = sum(max(0, min(tallies[r]["kept"] - tallies[r]["refuted"], tallies[r]["raised"]))
                        for r in seat["priced_judged_runs"])
    seat["tokens_per_useful"] = round(seat["judged_tokens"] / priced_useful) if priced_useful else None
    seat["weighed"] = judged >= bar["min_runs"] and counted >= bar["min_items"]
    if not judged:
        return "collect", ("never judged: no synthesis credited its items in {} run(s) — its runs count "
                           "toward tokens only".format(len(seat["runs"])))
    if not seat["weighed"]:
        return "collect", ("too little to judge: {} judged run(s) and {} item(s) of evidence (at most {} from "
                           "any run); the bar is {} runs and {} items".format(
                               judged, counted, bar["per_run"], bar["min_runs"], bar["min_items"]))
    use, ref = seat["useful_share"], seat["refuted_share"]
    if judged >= bar["drop_runs"] and use["high"] < bar["drop_ceiling"]:
        return "drop?", ("consider dropping it — the user decides: after {} judged runs at most {} of its "
                         "items ship".format(judged, pct(use["high"])))
    if use["high"] < bar["low_ceiling"]:
        return "lower", ("lower its priority — run it when its surface is touched: at most {} of its items "
                         "ship".format(pct(use["high"])))
    if ref and seat["verified_kept"] >= bar["min_verified"] and ref["low"] >= bar["refute_floor"]:
        return "narrow", ("narrow its surface or pair it with a verifier: the verifier refuted {} of {} kept "
                          "items (plausible {}–{})".format(ref["k"], ref["n"], pct(ref["low"]), pct(ref["high"])))
    if raised / judged < bar["thin_items"]:
        return "pair", "pair it with a related seat: it raises {:.1f} item(s) a run".format(raised / judged)
    if use["low"] >= bar["retain_floor"]:
        return "retain", "retain: at least {} of its items ship".format(pct(use["low"]))
    return "unclear", ("keep as is: {}–{} of its items ship, which points neither way "
                       "yet".format(pct(use["low"]), pct(use["high"])))


def pct(x):
    return "{:.0%}".format(x)


def report(ledger, last, bar=BAR):
    got, bad = read_ledger(ledger)
    if got is None:
        return {"schema": SCHEMA, "ledger": str(ledger), "window": {"last": last, "runs": 0, "judged": 0},
                "bar": bar, "seats": [], "tokens": None,
                "notes": ["no ledger yet — every completed run adds its seats to " + str(ledger)]}
    rows, runs = window(got, last)
    seats, facts, loose = records(rows, runs)
    notes = []
    for name in sorted(seats):
        seat = seats[name]
        seat["advice"], seat["reason"] = judge(seat, bar)
        seat["costly"] = None
    priced = [s for s in seats.values() if s["weighed"] and s["tokens_per_useful"]]
    if len(priced) >= 3:
        median = statistics.median(s["tokens_per_useful"] for s in priced)
        for seat in priced:
            if seat["tokens_per_useful"] > bar["cost_ratio"] * median:
                seat["costly"] = ("~{}k tokens per useful item against a median of ~{}k"
                                  .format(round(seat["tokens_per_useful"] / 1000), round(median / 1000)))
    unjudged = [run for run in runs if not facts[run]["judged"] and facts[run]["seat_rows"]]
    if unjudged:
        modes = sorted({facts[run]["mode"] for run in unjudged})
        notes.append("{} run(s) credited no items ({}): their seats count toward tokens only"
                     .format(len(unjudged), ", ".join(modes)))
    if loose:
        notes.append("kept and cut exceed raised in {} seat-run(s) (first: {} in {}): items were credited "
                     "loosely, so shares are capped at 100%".format(len(loose), loose[0][0], loose[0][1]))
    if bad:
        notes.append("{} ledger line(s) could not be read and were left out".format(bad))
    per_run = sorted(t["tokens"] for s in seats.values() for t in s["per_run"].values() if t["tokens"])
    unpriced = sum(1 for s in seats.values() for t in s["per_run"].values() if t["tokens"] is None)
    if unpriced:
        notes.append("{} seat-run(s) have no checked token figure (older rows, or usage not reported): "
                     "they are left out of every cost figure".format(unpriced))
    tokens = None
    if per_run:
        tokens = {"seat_runs": len(per_run), "median": round(statistics.median(per_run)),
                  "p90": per_run[min(len(per_run) - 1, math.ceil(0.9 * len(per_run)) - 1)]}
    judged = sum(1 for run in runs if facts[run]["judged"])
    return {"schema": SCHEMA, "ledger": str(ledger),
            "window": {"last": last, "runs": len(runs), "judged": judged},
            "bar": bar, "tokens": tokens, "notes": notes,
            "seats": [seats[name] for name in sorted(seats)]}


def render(data):
    lines = []
    w = data["window"]
    if not w["runs"]:
        return "\n".join(data["notes"] or ["the ledger has no runs yet"])
    bar = data["bar"]
    lines.append("seat advice · the last {} completed run(s): {} judged, {} not".format(
        w["runs"], w["judged"], w["runs"] - w["judged"]))
    lines.append("a seat is weighed after {} judged runs and {} items of evidence, at most {} from any run · "
                 "useful = kept and not refuted · ranges are 90% plausible ranges on that evidence".format(
                     bar["min_runs"], bar["min_items"], bar["per_run"]))
    lines.append("")
    lines.append("{:<16} {:>6} {:>5} {:>7} {:>11} {:>8} {:>6} {:>9}  {}".format(
        "seat", "judged", "items", "useful", "plausible", "refuted", "~k/run", "~k/useful", "advice"))
    for seat in data["seats"]:
        use, ref = seat["useful_share"], seat["refuted_share"]
        lines.append("{:<16} {:>6} {:>5} {:>7} {:>11} {:>8} {:>6} {:>9}  {}".format(
            seat["seat"][:16], len(seat["judged_runs"]), seat["raised"],
            "{}/{}".format(seat["useful"], seat["raised"]) if use else "-",
            "{}–{}".format(pct(use["low"]), pct(use["high"])) if use else "-",
            "{}/{}".format(ref["k"], ref["n"]) if ref else "-",
            round(seat["tokens_per_run"] / 1000) if seat["tokens_per_run"] is not None else "-",
            round(seat["tokens_per_useful"] / 1000) if seat["tokens_per_useful"] else "-",
            seat["advice"]))
    lines.append("")
    lines.append("advice — for the user to decide; nothing changes without their yes:")
    for seat in data["seats"]:
        extra = " · costly: " + seat["costly"] if seat["costly"] else ""
        lines.append("- {}: {}{}".format(seat["seat"], seat["reason"], extra))
    if data["tokens"]:
        t = data["tokens"]
        lines.append("tokens per seat-run: median ~{}k, 90th percentile ~{}k over {} seat-run(s)".format(
            round(t["median"] / 1000), round(t["p90"] / 1000), t["seat_runs"]))
    for note in data["notes"]:
        lines.append("note: " + note)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("advice",))
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--last", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.last < 1:
        parser.error("--last must be at least 1")
    data = report(args.ledger, args.last)
    print(json.dumps(data, indent=2, sort_keys=True) if args.json else render(data))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (LedgerError, OSError, ValueError) as exc:
        print("ledger: " + str(exc), file=sys.stderr)
        sys.exit(2)
