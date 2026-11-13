"""Seats that were real agent runs but have no token figure: the one rule `council run close`'s audit, the
status card's reader and `council tune`'s note share, over the per-seat figures of usage.py.

A seat is a gap when its agent ran (it is executed and its agent count is not declared zero) and its tokens
carry no trusted figure: a finished run with no usage report, a seat with no agent on record, or a figure no
agent run can have. A seat still working (pending), one the Chair did itself (no-agent) and a row from before
the accounting columns (legacy) are not gaps; a figure the user corrected is a figure.
"""
from __future__ import annotations

from typing import Any, Collection, Iterable, Mapping

from council.records import usage

GAPS = ("missing", "partial", "unrecorded", "suspect")    # the token bases that say an agent run has no figure
NO_ID, NO_REPORT, UNUSABLE = "no agent id recorded", "no usage report", "an unusable figure"   # the kinds of gap


def why(seat: usage.Seat) -> tuple[str, str]:
    """A gap's kind and what the record shows about it, in words."""
    basis, agent = seat["tokens_basis"], str(seat.get("agent") or "")[:10]
    if basis == "suspect":
        return UNUSABLE, "its recorded figure is under 1,000 tokens or blank, which no agent run has"
    if basis == "unrecorded" or not agent:
        return NO_ID, "no agent id recorded, so no usage report could be matched to it"
    if basis == "partial":
        return NO_REPORT, "%d of %d agent runs have no usage report" % (seat["missing_runs"], seat["agents"] or 0)
    return NO_REPORT, "agent %s finished with no usage report" % agent


def chairs(roles: Mapping[str, Any]) -> set[str]:
    """The seats that are the Chair's own work, never an agent run: the Chair's slug and any seat the plan
    gives the role chair (roles maps a seat to its plan role)."""
    return {"chair"} | {seat for seat, role in roles.items() if role == "chair"}


def unfigured(seat_rows: Iterable[usage.Seat], skip: Collection[str] = ()) -> list[dict[str, Any]]:
    """The seats of a run (usage.seat_list) that were agent runs with no token figure, each with its basis,
    its kind and why; skip names seats that are not agent work (chairs)."""
    found = []
    for seat in seat_rows:
        if seat["executed"] and seat["slug"] not in skip and seat["tokens_basis"] in GAPS:
            kind, reason = why(seat)
            found.append({"seat": seat["slug"], "basis": seat["tokens_basis"], "kind": kind, "why": reason})
    return found


def words(gaps: list[dict[str, Any]], most: int = 6) -> str:
    """The gaps as one line: each seat with its reason, the rest counted."""
    shown = ["%s (%s)" % (gap["seat"], gap["why"]) for gap in gaps[:most]]
    return "; ".join(shown) + ("; and %d more" % (len(gaps) - most) if len(gaps) > most else "")


def left_out(snapshots: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """What a measure over completed runs leaves out for want of a token figure: the seats and the runs
    they were in, and how many seats for each kind of gap (cockpit snapshots, each with its seats and plan)."""
    seats, runs, kinds = 0, 0, {}
    for snap in snapshots:
        roles = {slug: fields.get("role") for slug, fields in snap["plan"].get("seats", {}).items()}
        gaps = unfigured(snap["seats"], skip=chairs(roles))
        seats, runs = seats + len(gaps), runs + bool(gaps)
        for gap in gaps:
            kinds[gap["kind"]] = kinds.get(gap["kind"], 0) + 1
    return {"seats": seats, "runs": runs, "kinds": dict(sorted(kinds.items()))}


def note(gone: dict[str, Any]) -> list[str]:
    """The one line `council tune` says when seats were left out of its measurement, else nothing."""
    if not gone["seats"]:
        return []
    kinds = ", ".join("%d %s" % (n, kind) for kind, n in gone["kinds"].items())
    said = "left out of the measurement: %d seat(s) in %d completed run(s) ran as agents with no token figure (%s)"
    return [said % (gone["seats"], gone["runs"], kinds) + "; council run audit --run <run> names each"]
