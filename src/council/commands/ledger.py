"""council ledger [N] | ledger advice [N] [--json]: each seat's record over the last N completed runs (default 10) —
runs, items raised, kept, cut and refuted, tokens per run and the share shipped — from the council home's
ledger.tsv; advice weighs each seat's judged runs with a plausible range and advises only past a stated bar
(scripts/ledger.py). Both only read: neither changes a roster, a route or a run."""
from __future__ import annotations

import re

from council.commands import cli, script
from council.records import home as where
from council.records import ledger

USAGE = "usage: council ledger [how many recent runs, default 10]"
ADVICE = "usage: council ledger advice [how many recent runs, default 20] [--json]"
_NUMBER = r"[+-]?([0-9]+[.]?[0-9]*|[.][0-9]+)([eE][+-]?[0-9]+)?"
_PREFIX = re.compile(r"[ \t\n\v\f\r]*(" + _NUMBER + ")")
_STRNUM = re.compile(r"[ \t\n]*" + _NUMBER + r"[ \t\n]*\Z")
_WORKER = re.compile(r"-(r[0-9]+|[a-z])\Z")


def main(args: cli.Args, words: list[str]) -> int:
    if words[:1] == ["advice"]:
        cli.takes_flags(args, "ledger advice", "json")
        if len(words) > 2:
            raise cli.Refusal("usage: council ledger advice [N] [--json]")
        return advice(args, words[1] if len(words) > 1 else "")
    cli.takes_flags(args, "ledger")
    if len(words) > 1:
        raise cli.Refusal("usage: council ledger [N] | ledger advice [N] [--json]")
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


def advice(args: cli.Args, last: str) -> int:
    last = last or "20"
    if not re.fullmatch(r"[0-9]+", last):
        raise cli.Refusal(ADVICE)
    if len(last) > 6:
        raise cli.Refusal("ledger advice: keep N under a million runs")
    if int(last) <= 0:
        raise cli.Refusal(ADVICE)
    words = ["advice", "--ledger", where.council_home() + "/" + ledger.NAME, "--last", last]
    if "json" in args.flags:
        words.append("--json")
    return script.run("ledger", words, faults=(ledger.LedgerError, OSError, ValueError))


def number(cell: str) -> float:
    """awk's reading of a cell as a number: its leading number, else 0."""
    found = _PREFIX.match(cell)
    return float(found.group(1)) if found else 0.0


def above_zero(cell: str) -> bool:
    """awk's `cell > 0`: a number compared as one, any other text against "0" as a string."""
    return number(cell) > 0 if _STRNUM.match(cell) else cell > "0"


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
            if cells[3] != ledger.VERIFIERS and number(cells[5]) + number(cells[6]) > 0:
                judged.add(cells[1])
        self.judged, self.first = judged, max(len(self.order) - last + 1, 1)

    def lines(self) -> list[str]:
        if not self.order:
            return ["the ledger has no runs yet"]
        kept_runs = set(self.order[self.first - 1:])
        seats: dict[str, dict[str, float]] = {}
        counted, priced, unjudged = set(), set(), False
        for cells in (c for c in self.rows if c[1] in kept_runs):
            seat = _WORKER.sub("", cells[3], count=1)
            s = seats.setdefault(seat, dict.fromkeys(("runs", "raised", "kept", "cut", "refd", "tok", "truns",
                                                      "jraised"), 0.0))
            if (cells[1], seat) not in counted:
                counted.add((cells[1], seat))
                s["runs"] += 1
            for key, at in (("raised", 4), ("kept", 5), ("cut", 6), ("refd", 7)):
                s[key] += number(cells[at])
            if cells[9] == ledger.CHECKED and re.fullmatch(r"[0-9]+", cells[8]) and len(cells[8]) <= 12:
                s["tok"] += number(cells[8])
                if (cells[1], seat) not in priced:
                    priced.add((cells[1], seat))
                    s["truns"] += 1
            if cells[1] in self.judged:
                s["jraised"] += number(cells[4])
            elif above_zero(cells[4]):
                unjudged = True
        return self.shown(seats, unjudged)

    def shown(self, seats: dict[str, dict[str, float]], unjudged: bool) -> list[str]:
        out = ["%-16s %4s %6s %5s %4s %7s %8s %9s" % ("seat", "runs", "raised", "kept", "cut", "refuted", "~k/run",
                                                       "shipped")]
        untrusted = False
        for seat, s in seats.items():
            ship = s["kept"] - s["refd"]
            pct = "%d%%" % _d(100 * ship / s["jraised"] + 0.5) if s["jraised"] > 0 else "-"
            per_run = "%d" % _d(s["tok"] / s["truns"] / 1000 + 0.5) if s["truns"] > 0 else "-"
            untrusted = untrusted or s["truns"] == 0
            out.append("%-16s %4d %6d %5d %4d %7d %8s %9s" % (seat, _d(s["runs"]), _d(s["raised"]), _d(s["kept"]),
                                                              _d(s["cut"]), _d(s["refd"]), per_run, pct))
        out.append("over the last %d completed run(s) · shipped = kept and not refuted, as a share of items raised"
                   % (len(self.order) - self.first + 1))
        if unjudged:
            out.append("raised counts every run; shipped only runs whose synthesis credited items (not council-init "
                       "or a build) · - = never judged")
        if untrusted:
            out.append("~k/run counts only runs whose token figures were checked (0.14+ or corrected) · - = none yet")
        out.append("what this record can support, seat by seat: council ledger advice")
        return out
