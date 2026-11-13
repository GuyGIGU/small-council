"""seats.tsv, usage.tsv, agent-starts.tsv, cap-allowances.tsv and corrections.jsonl: who worked, what they
used, the agent stop's count and the user's go past it, and figures corrected from evidence.

seats.tsv and usage.tsv are written by `council seat` under `seats.tsv.lock` (locks.py).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from council.records import cells, paths

SEATS = "seats.tsv"
USAGE = "usage.tsv"
STARTS = "agent-starts.tsv"
ALLOWANCES = "cap-allowances.tsv"
CORRECTIONS = "corrections.jsonl"


def path(run: Path, name: str = SEATS) -> Path:
    """One of the seat files of a run folder (seats.tsv by default)."""
    return Path(run) / name


def _rows(run: Path, name: str, limit: int) -> list[dict[str, str]]:
    run = Path(run)
    return cells.tsv_rows(paths.text_of(path(run, name), run, limit))


def rows(run: Path, limit: int = paths.MAX_FILE) -> list[dict[str, str]]:
    """seats.tsv's rows, keyed by its header (slug, state, agent, tokens, updated, note, agents, reported)."""
    return _rows(run, SEATS, limit)


def usage_rows(run: Path, limit: int = paths.MAX_FILE) -> list[dict[str, str]]:
    """usage.tsv's rows (at, seat, agent, kind, runs, tokens): one per dispatch and per finished report."""
    return _rows(run, USAGE, limit)


def start_rows(run: Path, limit: int = paths.MAX_FILE) -> list[dict[str, str]]:
    """agent-starts.tsv's rows, as the agent gate wrote them."""
    return _rows(run, STARTS, limit)


def allowance_rows(run: Path, limit: int = paths.MAX_FILE) -> list[dict[str, str]]:
    """cap-allowances.tsv's rows (at, used, n, until, said): the user's go past the agent limit."""
    return _rows(run, ALLOWANCES, limit)


def _raw_lines(run: Path, name: str) -> list[str]:
    """The file's lines as the helper's awk reads them (cells.lines_of: a CRLF file's last cell has no CR)."""
    run = Path(run)
    return cells.lines_of(paths.text_of(path(run, name), run))


def agent_starts(run: Path) -> int:
    """The agent starts the gate let through (bin/council cap_starts): the rows after the header, a
    "before:<n>" row counting n."""
    count = 0
    for line in _raw_lines(run, STARTS)[1:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        seed = re.fullmatch(r"before:([0-9]{1,9})", parts[1]) if len(parts) > 1 else None
        count += int(seed.group(1)) if seed else 1
    return count


def workflow_extra(run: Path) -> int:
    """A Workflow's agents beyond the one start the gate counted (bin/council cap_extra): for each
    finished usage report of N > 1 agent runs (per agent id, the latest), N - 1."""
    by_id, loose = {}, 0
    for line in _raw_lines(run, USAGE)[1:]:
        parts = line.split("\t")
        if len(parts) < 5 or parts[3] != "finished" or not re.fullmatch(r"[0-9]{0,4}", parts[4]):
            continue
        runs = int(parts[4]) if parts[4] else 1
        if parts[2] == "":
            loose += max(0, runs - 1)
        else:
            by_id[parts[2]] = runs
    return loose + sum(max(0, runs - 1) for runs in by_id.values())


def allowed_until(run: Path) -> int | None:
    """The user's latest go (council cap allow): the until of the last readable row; None when no go is
    on record. A torn or garbage row is passed over."""
    until = None
    for n, line in enumerate(_raw_lines(run, ALLOWANCES)):
        parts = line.split("\t")
        if n and len(parts) >= 4 and re.fullmatch(r"[0-9]{1,9}", parts[3]):
            until = int(parts[3])
    return until


def evidenced(text: Any) -> bool:
    """Evidence names a source: at least one letter or digit once cleaned (the helper's awk asks the same)."""
    return bool(re.search(r"[A-Za-z0-9]", cells.clean(text or "")))


def corrections(run: Path) -> dict[tuple[str, str], dict[str, Any]]:
    """The latest evidence-backed correction per (seat, field), from the append-only corrections.jsonl,
    read as the helper's corrections_tsv reads it: a whole number of at most 12 digits, and evidence
    that names something."""
    run = Path(run)
    latest = {}
    for row in cells.jsonl_rows(paths.text_of(path(run, CORRECTIONS), run)):
        seat, field = cells.clean(row.get("seat", "")), cells.clean(row.get("field", ""))
        to = cells.integer(row.get("to")) if isinstance(row.get("to"), int) else None   # a bare number, like the helper
        if seat and field in ("tokens", "agents") and to is not None and to >= 0 and evidenced(row.get("evidence")):
            latest[(seat, field)] = {"seat": seat, "field": field, "to": to, "from": cells.clean(row.get("from", "")),
                                     "evidence": cells.clean(row.get("evidence", ""))[:300],
                                     "at": cells.clean(row.get("at", "")), "added": row.get("added") is True}
    return latest
