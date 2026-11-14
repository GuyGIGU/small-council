"""One seat's rows across a run's files, as `council collect` lists a seat: its seats.tsv cells, the tool calls its
agents reported (tools.tsv) and the plan's word on it (run-plan.tsv: a verifier's role, a tool-call budget)."""
from __future__ import annotations

import re
from pathlib import Path

from council.records import cells, paths, plan, seats

TOOLS = "tools.tsv"


def cell(run: Path, slug: str, column: str) -> str:
    """The first seats.tsv row's cell for this seat (slug, state, agent, tokens, updated, note, agents,
    reported); '' when the seat has no row."""
    for row in seats.rows(run):
        if row.get("slug") == slug:
            return row.get(column, "")
    return ""


def _lines(file: Path, run: Path) -> list[list[str]]:
    return [line.split("\t") for line in cells.lines_of(paths.text_of(file, run))]


def tool_calls(run: Path, slug: str) -> str:
    """The seat's tool calls: per agent id the latest figure (a resumed agent reports a running total), and each
    report with no id on its own. '' when none was reported."""
    run = Path(run)
    total, latest, seen = 0, {}, False
    for row in _lines(run / TOOLS, run)[1:]:
        if len(row) > 3 and row[1] == slug and re.fullmatch(r"[0-9]+", row[3]):
            seen = True
            if row[2] == "":
                total += int(row[3])
            else:
                latest[row[2]] = int(row[3])
    return str(total + sum(latest.values())) if seen else ""


def tool_budget(run: Path, slug: str) -> str:
    """The plan's tool-call budget for the seat (its last `budget <slug> tool-calls <n>` row), or ''."""
    found = ""
    for row in _lines(plan.path(run), Path(run)):
        if len(row) > 3 and row[:3] == ["budget", slug, "tool-calls"] and re.fullmatch(r"[0-9]+", row[3]):
            found = row[3]
    return found


def is_verifier(run: Path, slug: str) -> bool:
    """The plan names the seat a verifier (`seat <slug> role verifier`): a Challenge verifier writes no seat file."""
    return any(len(row) > 3 and row[:4] == ["seat", slug, "role", "verifier"]
               for row in _lines(plan.path(run), Path(run)))
