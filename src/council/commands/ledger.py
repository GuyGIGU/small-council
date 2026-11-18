"""council ledger [N]: each seat's record over the last N completed runs (default 10) — runs, items raised, kept, cut
and refuted, tokens per run, the share shipped, and the roster bar's two facts (judged runs, and items counted at most
PER_RUN from any one) — from the council home's ledger.tsv. It only reads: it never
changes a roster or a run; the Chair weighs the record itself."""
from __future__ import annotations

import re

from council.commands import cli
from council.records import home as where
from council.records import ledger
from council.records.cells import leading

USAGE = "usage: council ledger [how many recent runs, default 10]"
PER_RUN = 5     # items of one run counted toward the roster bar, as the removed seat advice counted them


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "ledger")
    if len(words) > 1:
        raise cli.Refusal("usage: council ledger [N]")
    last = (words[0] if words else "") or "10"
    if not re.fullmatch(r"[0-9]+", last):
        raise cli.Refusal(USAGE)
    home = where.council_home()
    rows = ledger.raw_rows(where.native(home))
    if rows is None:
        cli.say("no ledger yet — every completed run adds its seats to %s/%s" % (home, ledger.NAME))
        return 0
    for line in Table(rows, int(last)).lines():
        cli.say(line)
    return 0


def _d(value: float) -> int:
    return int(value)                                    # printf %d: toward zero


class Table:
    """The seat table over the last N runs that have rows (a run's first row sets its place)."""

    def __init__(self, rows: list[list[str]], last: int) -> None:
        self.rows = [cells + [""] * (10 - len(cells)) for cells in rows[1:] if len(cells) > 1 and cells[1] != ""]
        self.order: list[str] = []
        judged = set()
        for cells in self.rows:
            if cells[1] not in self.order:
                self.order.append(cells[1])
            if cells[3] != ledger.VERIFIERS and leading(cells[5]) + leading(cells[6]) > 0:
                judged.add(cells[1])
        self.judged, self.first = judged, max(len(self.order) - last + 1, 1)

    def lines(self) -> list[str]:
        if not self.order:
            return ["the ledger has no runs yet"]
        kept_runs = set(self.order[self.first - 1:])
        seats: dict[str, dict[str, float]] = {}
        counted, priced, unjudged, per_run = set(), set(), False, {}
        for cells in (c for c in self.rows if c[1] in kept_runs):
            seat = ledger.seat_of(cells[3])
            s = seats.setdefault(seat, dict.fromkeys(("runs", "raised", "kept", "cut", "refd", "tok", "truns",
                                                      "jraised"), 0.0))
            if (cells[1], seat) not in counted:
                counted.add((cells[1], seat))
                s["runs"] += 1
            for key, at in (("raised", 4), ("kept", 5), ("cut", 6), ("refd", 7)):
                s[key] += leading(cells[at])
            if cells[9] == ledger.CHECKED and re.fullmatch(r"[0-9]+", cells[8]) and len(cells[8]) <= 12:
                s["tok"] += leading(cells[8])
                if (cells[1], seat) not in priced:
                    priced.add((cells[1], seat))
                    s["truns"] += 1
            if cells[1] in self.judged:
                s["jraised"] += leading(cells[4])
                if cells[3] != ledger.VERIFIERS:     # a judged run of the seat's, even at 0 items
                    per_run.setdefault(seat, {}).setdefault(cells[1], 0.0)
                    per_run[seat][cells[1]] += leading(cells[4])
            elif leading(cells[4]) > 0:              # a cell that is not a number is not above 0
                unjudged = True
        for seat, s in seats.items():
            runs = per_run.get(seat, {})
            s["judged"], s["counted"] = len(runs), sum(min(raised, PER_RUN) for raised in runs.values())
        return self.shown(seats, unjudged)

    def shown(self, seats: dict[str, dict[str, float]], unjudged: bool) -> list[str]:
        out = ["%-16s %4s %6s %5s %4s %7s %8s %9s %6s %7s" % ("seat", "runs", "raised", "kept", "cut", "refuted",
                                                               "~k/run", "shipped", "judged", "counted")]
        untrusted = False
        for seat, s in seats.items():
            ship = s["kept"] - s["refd"]
            pct = "%d%%" % _d(100 * ship / s["jraised"] + 0.5) if s["jraised"] > 0 else "-"
            per_run = "%d" % _d(s["tok"] / s["truns"] / 1000 + 0.5) if s["truns"] > 0 else "-"
            untrusted = untrusted or s["truns"] == 0
            out.append("%-16s %4d %6d %5d %4d %7d %8s %9s %6d %7d" % (
                seat, _d(s["runs"]), _d(s["raised"]), _d(s["kept"]), _d(s["cut"]), _d(s["refd"]), per_run, pct,
                s["judged"], _d(s["counted"])))
        out.append("over the last %d completed run(s) · shipped = kept and not refuted, as a share of items raised"
                   % (len(self.order) - self.first + 1))
        out.append("judged = runs whose synthesis credited items, counted = their items raised, at most %d from any "
                   "one run" % PER_RUN)
        if unjudged:
            out.append("raised counts every run; shipped only runs whose synthesis credited items (not council-init "
                       "or a build) · - = never judged")
        if untrusted:
            out.append("~k/run counts only runs whose token figures were checked (0.14+ or corrected) · - = none yet")
        return out
