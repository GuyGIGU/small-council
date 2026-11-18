"""A closed run keeps the record its ledger counted (the helper's refuse_closed): a command that would add to it
refuses before it writes anything, naming what to do instead."""
from __future__ import annotations

from pathlib import Path

from council.commands import cli
from council.records import state_write


def refuse(run: Path, why: str) -> None:
    """Refuse when the run is closed: 'run <name> is closed (<status> at <closed>) — <why>'."""
    if state_write.closed(run):
        raise cli.Refusal(state_write.closed_refusal(run, why))
