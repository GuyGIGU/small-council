"""The names the status gives seats and checks, so the user reads "Tests", not a slug."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from council.records import bytewise, config
from council.records.cells import clean
from council.views.snapshot import brief_names


def roster_names(snap: dict[str, Any]) -> dict[str, str]:
    """Seat names from the council config's roster table (| Seat | Slug | Lens | …): "Lens (Seat)" per slug, or the
    seat alone when its Lens is empty — for a seat no brief names, a skipped one most often. Read once per
    snapshot."""
    cached = snap.get("_roster")
    if cached is None:
        cached = {}
        home = Path(snap["run"].get("path") or ".").parent.parent
        for row in config.roster_table(home):
            seat, lens = clean(bytewise.shown(row.seat)), clean(bytewise.shown(row.lens))
            if row.slug:
                cached[bytewise.shown(row.slug)] = ("{} ({})".format(lens, seat) if lens else seat)[:40]
        snap["_roster"] = cached
    return cached


def seat_name(snap: dict[str, Any], slug: str) -> str:
    """A seat in plain words: the brief's name for it, else the roster's, else its slug made readable."""
    named = brief_names(snap).get(slug) or roster_names(snap).get(slug)
    if named:
        return named
    for prefix, word in (("verify-", "Verifier"), ("diagnose-", "Diagnosis"), ("task-", "Task")):
        if slug.startswith(prefix) and len(slug) > len(prefix):
            return "{} {}".format(word, slug[len(prefix):])
    words = re.sub(r"[-_.]+", " ", slug).strip()
    return words[:1].upper() + words[1:] if words else slug


def check_name(name: str) -> str:
    """A check in plain words: a build's after-check is the fix's check, not a name to decode."""
    if name.startswith("after-") and len(name) > 6:
        return "fix check for task " + name[6:]
    return name
