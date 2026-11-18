"""ledger.tsv: one row per seat per completed run, written at close and refreshed by `council seat` and `correct`.

Columns: date, run, mode, seat, raised, kept, cut, refuted, tokens, and (from accounting 2) a tenth that
marks a row whose tokens were checked. A `(verifiers)` row carries the run's verifier tokens only.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from council.records import bytewise, home, locks, owners, paths, seat_files, state, synthesis_counts, usage

NAME = "ledger.tsv"
COLUMNS = ("date", "run", "mode", "seat", "raised", "kept", "cut", "refuted", "tokens")
CHECKED = "2"           # the accounting column of a row whose tokens are a checked figure or "-"
VERIFIERS = "(verifiers)"
HEADER = "\t".join(COLUMNS) + "\taccounting\n"
WORKER = re.compile(r"-(r[0-9]+|[a-z])\Z")


def path(home: str | Path) -> Path:
    """The ledger of a council home."""
    return Path(home) / NAME


def seat_of(slug: str) -> str:
    """A split worker (hunt-a) or a fresh round-2 one (hunt-r2) is its seat."""
    return WORKER.sub("", slug, count=1)


def raw_rows(home: str | Path) -> list[list[str]] | None:
    """Every line of the ledger split at its tabs, as the helper's `council ledger` table read them (awk split at
    tabs: no cell checked, the header kept; on Windows Git Bash's awk reads a line's CR LF as LF); None when there is no
    ledger file."""
    where = path(home)
    if not where.is_file():
        return None
    try:
        text = where.read_bytes().decode("utf-8", "surrogateescape").lstrip("﻿")      # a BOM is no cell
    except OSError:
        return []
    return [line.split("\t") for line in bytewise.records(text)]


def _rewrite(ledger: Path, name: str, new: bytes, failed: str) -> bool:
    """The ledger less the run's rows, then the new rows, read and swapped in under `ledger.tsv.lock` (locks.py), so
    two runs closing in one council home at once keep each other's rows."""
    lock = Path(str(ledger) + ".lock")
    if not locks.acquire(lock):
        sys.stdout.flush()
        sys.stderr.write("council: could not write %s — %s: %s\n"
                         % (ledger.as_posix(), failed, owners.unavailable(lock).replace(str(lock), lock.as_posix())))
        return False
    try:
        old = bytewise.records(bytewise.read(ledger.read_bytes()) if ledger.is_file() else HEADER)
        kept = "".join(line + "\n" for line in old if (line.split("\t") + [""])[1] != bytewise.text(name))
        paths.atomic_write(ledger, bytewise.bytes_of(kept) + new, ".ledger.", keep_mode=True)
        return True
    except OSError as error:
        sys.stdout.flush()
        sys.stderr.write("council: could not write %s (%s) — %s; close what has it open, then run this again\n"
                         % (ledger.as_posix(), error.strerror or error, failed))
        return False
    finally:
        locks.release(lock)


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
