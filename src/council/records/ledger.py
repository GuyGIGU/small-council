"""ledger.tsv: one row per seat per completed run, written at close and refreshed by `council seat` and `correct`.

Columns: date, run, mode, seat, raised, kept, cut, refuted, tokens, and (from accounting 2) a tenth that
marks a row whose tokens were checked. A `(verifiers)` row carries the run's verifier tokens only.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Sequence

from council.records import bytewise, home, paths, seat_files, state, synthesis_counts, usage
from council.records.cells import lines_of

NAME = "ledger.tsv"
MAX_LEDGER = 8 * 1024 * 1024
COLUMNS = ("date", "run", "mode", "seat", "raised", "kept", "cut", "refuted", "tokens")
CHECKED = "2"           # the accounting column of a row whose tokens are a checked figure or "-"
VERIFIERS = "(verifiers)"
HEADER = "\t".join(COLUMNS) + "\taccounting\n"
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


def raw_rows(home: str | Path) -> list[list[str]] | None:
    """Every line of the ledger split at its tabs, as the helper's `council ledger` table read them (awk split at
    tabs: no cell checked, the header kept; on Windows Git Bash's awk reads a line's CR LF as LF); None when there is no
    ledger file. The checked rows the advice and history weigh come from read()."""
    where = path(home)
    if not where.is_file():
        return None
    try:
        text = where.read_bytes().decode("utf-8", "surrogateescape")
    except OSError:
        return []
    return [line.split("\t") for line in bytewise.records(text)]


def _rewrite(ledger: Path, name: str, new: bytes, failed: str) -> bool:
    """The ledger less the run's rows, then the new rows; no lock, as the helper took none (the last write wins)."""
    try:
        old = bytewise.records(bytewise.read(ledger.read_bytes()) if ledger.is_file() else HEADER)
        kept = "".join(line + "\n" for line in old if (line.split("\t") + [""])[1] != bytewise.text(name))
        paths.atomic_write(ledger, bytewise.bytes_of(kept) + new, ".ledger.", keep_mode=True)
        return True
    except OSError:
        sys.stdout.flush()
        sys.stderr.write("council: could not write %s — %s\n" % (ledger.as_posix(), failed))
        return False


def record(run: Path) -> int:
    """Rewrite the run's rows from its seats (ledger_record): the count of seat rows, 0 when none was written."""
    run = Path(run)
    if not (run / "seats.tsv").is_file():
        return 0
    lead = [run.name[:10], run.name, state.field(state.text(run), "mode") or "-"]
    counts, rows, spent = synthesis_counts.counts(run), [], []
    for seat in (seat for seat in usage.seat_list(run) if seat["executed"]):
        slug, tokens = seat["slug"], seat["tokens"] if seat["tokens_basis"] in ("reported", "corrected") else "-"
        if slug.startswith(("verify-", "diagnose-")):
            spent.append(tokens)
            continue
        raised = 0 if re.search("-r[0-9]", slug) else \
            sum(item.section == "index" for item in seat_files.items(seat_files.out_path(run, slug)))
        rows.append(lead + [slug, raised, *counts.get(slug, (0, 0, 0)), tokens])
    seated = len(rows)
    if spent:
        rows.append(lead + [VERIFIERS, "-", "-", "-", "-", "-" if "-" in spent else sum(spent)])
    new = "".join("\t".join(str(cell) for cell in row + [CHECKED]) + "\n" for row in rows)
    if not new or not _rewrite(path(home.run_home(run)), run.name, new.encode("utf-8", "surrogateescape"),
                               "the ledger was not updated"):
        return 0
    return seated


def forget(run: Path) -> None:
    """Take the run's rows out of the ledger (ledger_forget): a complete close taken back as abandoned."""
    ledger = path(home.run_home(run))
    if ledger.is_file():
        _rewrite(ledger, Path(run).name, b"", "its rows for %s are still there" % Path(run).name)
