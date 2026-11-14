"""map.md, the project's codebase map in the council home: its one-way-per-job table (job · owner · the one way ·
anchor path), which a plan task's Owner row names."""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from council.records import paths

NAME = "map.md"
TABLE = "## One way per job"


class Way(NamedTuple):
    """One row of the table."""

    job: str
    owner: str
    way: str
    anchor: str


def path(home: str | Path) -> Path:
    """The map of a council home."""
    return Path(home) / NAME


def cells_of(line: str) -> list[str]:
    """A Markdown table row's cells, trimmed, bold and backticks dropped."""
    inner = line.strip().strip("|")
    return [re.sub(r"[*`]", "", cell).strip() for cell in inner.split("|")]


def ways(content: str) -> list[Way] | None:
    """The table's rows (header and divider left out, a row with no job skipped); None when the map has no
    such table, so an older project's map is never read as one with no ways."""
    rows, inside, seen = [], False, False
    for line in content.split("\n"):
        line = line.rstrip("\r")
        if line.startswith("## "):
            inside = line.rstrip() == TABLE
            seen = seen or inside
            continue
        if not inside or not line.lstrip().startswith("|"):
            continue
        cells = (cells_of(line) + ["", "", "", ""])[:4]
        if re.fullmatch(r"[-: ]*", "".join(cells)) or cells[0].lower() == "job":
            continue
        if cells[0]:
            rows.append(Way(*cells))
    return rows if seen else None


def read(home: str | Path) -> list[Way] | None:
    """The table from a council home's map; None when there is no map or no table."""
    content = paths.text_of(path(home), home)
    return ways(content) if content else None
