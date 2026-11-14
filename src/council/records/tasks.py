"""A plan's tasks (`<home>/plans/<slug>.md`, `## Task Sequence`): each `### <n>. <title>` and its table of
`| **Field** | value |` rows, and the parts of a row the plan check reads (references/run/run-plan.md, Plan tasks)."""
from __future__ import annotations

import re
from typing import NamedTuple

SEQUENCE = "## Task Sequence"
STATES = ("OBSERVED", "REPRODUCED", "INFERRED", "ASSUMED", "UNVERIFIED")
NOTHING = ("", "-", "—", "none", "nothing")
FACT_STATE = re.compile(r"\((" + "|".join(STATES) + r")(\s*,\s*outside)?\)\s*$", re.IGNORECASE)
HEADING = re.compile(r"###\s+([0-9]+)[.)]?\s*(.*)")
ROW = re.compile(r"\|\s*\**([^|*]+?)\**\s*\|(.*)\|\s*$")


class Task(NamedTuple):
    """A task: its number, title, heading line and rows (field name lower-cased, value trimmed)."""

    number: int
    title: str
    line: int
    rows: dict


class Fact(NamedTuple):
    """One fact a task rests on, its evidence state (upper case, '' when it gives none) and whether it is about
    something outside the repo (a tool, a platform, an API)."""

    text: str
    state: str
    outside: bool


def read(content: str) -> list[Task]:
    """The tasks under `## Task Sequence`, in order; the first row of a repeated field wins."""
    found, inside = [], False
    for n, line in enumerate(content.split("\n"), 1):
        line = line.rstrip("\r")
        if line.startswith("## "):
            inside = line.rstrip() == SEQUENCE
            continue
        heading = HEADING.fullmatch(line.strip()) if inside else None
        if heading:
            found.append(Task(int(heading.group(1)), heading.group(2).strip(), n, {}))
            continue
        row = ROW.fullmatch(line.strip()) if inside and found else None
        if row:
            found[-1].rows.setdefault(row.group(1).strip().lower(), row.group(2).strip())
    return found


def facts(cell: str) -> list[Fact] | None:
    """A Rests on cell's facts, split on ';', each ending '(STATE)' or '(STATE, outside)'; [] for a task that
    rests on nothing ('—', 'none'); None when the cell is missing."""
    if cell is None:
        return None
    if cell.strip().lower() in NOTHING:
        return []
    out = []
    for part in cell.split(";"):
        part = part.strip()
        if not part:
            continue
        mark = FACT_STATE.search(part)
        out.append(Fact(part[:mark.start()].strip() if mark else part, mark.group(1).upper() if mark else "",
                        bool(mark and mark.group(2))))
    return out


def depends(cell: str | None) -> list[int]:
    """The task numbers a Depends on cell names ('Task 2', '1, 3'); none for '—'."""
    return [int(n) for n in re.findall(r"\b([0-9]+)\b", cell or "")]


def kind(owner: str | None) -> str:
    """What an Owner cell says the task is: 'probe' or 'research' (it measures or reads before others build),
    'new' (New way: and why), or 'way' (it extends an existing way)."""
    words = re.sub(r"[*`]", "", owner or "").strip().lower()
    for word in ("probe", "research"):
        if words.startswith(word + ":"):
            return word
    return "new" if words.startswith("new way:") else "way"
