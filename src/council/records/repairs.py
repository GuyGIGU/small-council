"""<run>/repairs.jsonl: a build's repair trail, one row per attempt on a task, written and read by scripts/repair.py
(references/run/repair-loop.md); and <run>/repair-allowances.tsv, the user's go for a gate whose trail stopped."""
from __future__ import annotations

from pathlib import Path

NAME = "repairs.jsonl"
ALLOWANCES = "repair-allowances.tsv"


def kept(run: str | Path) -> bool:
    """The run keeps a repair trail: its file is there."""
    return (Path(run) / NAME).is_file()


def allow(run: Path, cells: tuple[str, ...]) -> None:
    """One row of the allowances: a header first in a new file, and never joined to a torn last line. OSError."""
    file = Path(run) / ALLOWANCES
    old = file.read_bytes() if file.is_file() else b""
    with open(str(file), "ab") as out:
        out.write((b"" if old.endswith(b"\n") else b"\n" if old else b"at\tgate\ttask\tseq\tsaid\n")
                  + ("\t".join(cells) + "\n").encode("utf-8", "surrogateescape"))
