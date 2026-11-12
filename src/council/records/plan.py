"""run-plan.tsv: the run's plan, five tab-separated columns a row (kind, id, field, value, reason)."""

from pathlib import Path
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from council.records import cells, paths

NAME = "run-plan.tsv"
Reader = Callable[[Path], Optional[str]]


def path(run: Path) -> Path:
    """The plan of a run folder."""
    return Path(run) / NAME


def text(run: Path, read: Optional[Reader] = None) -> str:
    """The plan's text, by the guarded read unless `read` gives a caller's own policy."""
    run = Path(run)
    if read is None:
        return paths.text_of(path(run), run)
    return read(path(run)) or ""


def rows(run: Path, limit: int = paths.MAX_FILE) -> List[Dict[str, str]]:
    """The plan's rows as dicts keyed by its header line ("#" comments skipped)."""
    run = Path(run)
    return cells.tsv_rows(paths.text_of(path(run), run, limit))


def summary(run: Path) -> Dict[str, Any]:
    """The run-wide fields (rows for run and plan) by field, and each seat's fields under "seats" (a
    disposition's reason as "reason", a context row's value as "context"); every cell cleaned."""
    plan, seats = {}, {}                          # type: Dict[str, Any], Dict[str, Dict[str, str]]
    for line in cells.lines_of(text(run)):
        parts = line.split("\t")
        if not line.strip() or line.startswith("#") or len(parts) < 5 or parts[0] == "kind":
            continue
        kind, ident, field, value, reason = (cells.clean(c) for c in parts[:5])
        if kind == "seat":
            seats.setdefault(ident, {})[field] = value
            if field == "disposition":
                seats[ident]["reason"] = reason
        elif kind == "context":
            seats.setdefault(ident, {})["context"] = value
        elif ident in ("run", "plan"):
            plan[field] = value
    plan["seats"] = seats
    return plan


def budget(run: Path, field: str) -> str:
    """The last `budget run <field>` row's value, spaces, tabs and carriage returns removed ('' when none)."""
    value = ""
    for line in text(run).split("\n"):
        parts = line.split("\t")
        if parts[:3] == ["budget", "run", field]:
            value = parts[3] if len(parts) > 3 else ""
    return re.sub(r"[ \t\r]", "", value)


def keyed(content: str) -> Dict[Tuple[str, str, str], str]:
    """Each (kind, id, field) row's value, trimmed and lower-cased; a later row wins."""
    found = {}
    for line in content.splitlines():
        parts = line.split("\t")
        if len(parts) >= 4:
            found[(parts[0], parts[1], parts[2])] = parts[3].strip().lower()
    return found
