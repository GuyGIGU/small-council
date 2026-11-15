"""<run>/repairs.jsonl: a build's repair trail, one row per attempt on a task, written and read by repair_trail.py
(references/run/repair-loop.md); and <run>/repair-allowances.tsv, the user's go for a gate whose trail stopped."""
from __future__ import annotations

from pathlib import Path

from council.records import paths

NAME = "repairs.jsonl"
ALLOWANCES = "repair-allowances.tsv"


def kept(run: str | Path) -> bool:
    return (Path(run) / NAME).is_file()


def allow(run: Path, cells: tuple[str, ...]) -> None:
    """One row of the allowances (OSError)."""
    paths.append_row(Path(run) / ALLOWANCES, "at\tgate\ttask\tseq\tsaid\n", cells)
