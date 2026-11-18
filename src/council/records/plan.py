"""run-plan.tsv: the run's plan, five tab-separated columns a row (kind, id, field, value, reason)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from council.records import bytewise, cells, paths

NAME = "run-plan.tsv"


def path(run: Path) -> Path:
    return Path(run) / NAME


def text(run: Path, read: paths.Reader | None = None) -> str:
    return paths.run_text(run, NAME, read)


def rows(run: Path, limit: int = paths.MAX_FILE) -> list[dict[str, str]]:
    """The plan's rows as dicts keyed by its header line ("#" comments skipped)."""
    return cells.tsv_rows(paths.run_text(run, NAME, limit=limit))


def selected(run: Path, slug: str) -> bool:
    """The plan marks the seat selected (run_plan_has_selected): its `seat <slug> disposition` row says selected."""
    return keyed(text(run)).get(("seat", slug, "disposition")) == "selected"


def summary(run: Path) -> dict[str, Any]:
    """The run-wide fields (rows for run and plan) by field, and each seat's fields under "seats" (a
    disposition's reason as "reason", a context row's value as "context"); every cell cleaned, the first row wins."""
    plan, seats = {}, {}                          # type: Dict[str, Any], Dict[str, Dict[str, str]]
    for parts in cells.tab_rows(text(run)):
        if parts[0].startswith("#") or len(parts) < 5 or parts[0] == "kind":
            continue
        kind, ident, field, value, reason = (cells.clean(c) for c in parts[:5])
        if kind == "seat":
            if field not in seats.setdefault(ident, {}) and field == "disposition":
                seats[ident]["reason"] = reason
            seats[ident].setdefault(field, value)
        elif kind == "context":
            seats.setdefault(ident, {}).setdefault("context", value)
        elif ident in ("run", "plan"):
            plan.setdefault(field, value)
    plan["seats"] = seats
    return plan


def budget(run: Path, field: str, ident: str = "run") -> str:
    """The first `budget <ident> <field>` row's value when it is plain digits ('' when there is none or it is not)."""
    value = keyed(text(run)).get(("budget", ident, field), "")
    return value if re.fullmatch(r"[0-9]+", value) else ""


def keyed(content: str) -> dict[tuple[str, str, str], str]:
    """Each (kind, id, field) row's value (the fourth cell, '' when there is none), spaces and tabs trimmed and
    otherwise as written; the keys exact. The first row of a key wins."""
    found = {}
    for parts in cells.tab_rows(content):
        if len(parts) >= 3:
            found.setdefault((parts[0], parts[1], parts[2]), bytewise.trim(parts[3]) if len(parts) > 3 else "")
    return found
