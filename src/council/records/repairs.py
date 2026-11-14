"""<run>/repairs.jsonl: a build's repair trail, one row per attempt on a task, written and read by scripts/repair.py
(references/run/repair-loop.md)."""
from __future__ import annotations

from pathlib import Path

NAME = "repairs.jsonl"


def kept(run: str | Path) -> bool:
    """The run keeps a repair trail: its file is there."""
    return (Path(run) / NAME).is_file()
