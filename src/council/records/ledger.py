"""ledger.tsv: one row per seat per completed run, written by `council run close`.

Columns: date, run, mode, seat, raised, kept, cut, refuted, tokens, and (from accounting 2) a tenth that
marks a row whose tokens were checked. A `(verifiers)` row carries the run's verifier tokens only.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Sequence

from council.records import paths
from council.records.cells import lines_of

NAME = "ledger.tsv"
MAX_LEDGER = 8 * 1024 * 1024
COLUMNS = ("date", "run", "mode", "seat", "raised", "kept", "cut", "refuted", "tokens")
CHECKED = "2"           # the accounting column of a row whose tokens are a checked figure or "-"
VERIFIERS = "(verifiers)"
CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class LedgerError(paths.RecordError):
    """The ledger cannot be read."""


def path(home: str | Path) -> Path:
    """The ledger of a council home."""
    return Path(home) / NAME


def count(cell: str) -> int:
    """A count cell: up to 12 digits, else ValueError."""
    cell = cell.strip()
    if not re.fullmatch(r"[0-9]{1,12}", cell):
        raise ValueError(cell)
    return int(cell)


def tokens_of(cells: Sequence[str]) -> int | None:
    """A row's trusted token figure: a number on a checked row, else None (unknown or unchecked).
    ValueError for a cell that is no figure at all."""
    checked = len(cells) > 9 and cells[9].strip() == CHECKED
    cell = cells[8].strip()
    if cell in ("-", ""):
        if checked:
            return None
        raise ValueError(cell)
    value = count(cell)
    return value if checked else None


def _row(cells: list[str]) -> dict[str, Any]:
    row = {"date": cells[0].strip(), "run": cells[1].strip(), "mode": cells[2].strip() or "-",
           "seat": CONTROL.sub("", cells[3].strip())}            # type: Dict[str, Any]
    if row["seat"] == VERIFIERS:
        row.update(raised=0, kept=0, cut=0, refuted=0, tokens=tokens_of(cells))
    else:
        row.update(raised=count(cells[4]), kept=count(cells[5]), cut=count(cells[6]),
                   refuted=count(cells[7]), tokens=tokens_of(cells))
    return row


def read(where: str | Path) -> tuple[list[dict[str, Any]] | None, int]:
    """The ledger's rows and how many lines could not be read; (None, 0) when there is no ledger."""
    where = Path(where)
    if not where.exists():
        return None, 0
    if not where.is_file() or where.stat().st_size > MAX_LEDGER:
        raise LedgerError("the ledger is not a regular file under 8 MB: " + str(where))
    text = where.read_bytes().decode("utf-8-sig", errors="replace")    # a BOM (PowerShell 5.1) is no cell
    rows, bad = [], 0
    for number, line in enumerate(lines_of(text)):
        if not line.strip() or (number == 0 and line.startswith("date\t")):
            continue
        cells = line.split("\t")
        if len(cells) < len(COLUMNS) or not cells[1].strip() or not cells[3].strip():
            bad += 1
            continue
        try:
            rows.append(_row(cells))
        except ValueError:
            bad += 1
    return rows, bad
