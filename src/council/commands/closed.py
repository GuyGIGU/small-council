"""A closed run keeps its record (the helper's refuse_closed): a command that would add to it refuses before it writes
anything, naming what to do instead. So does a run opened on the path 2.1.0 removed, when it is carried on (D77)."""
from __future__ import annotations

from pathlib import Path

from council.commands import cli
from council.records import stages, state, state_write


def refuse(run: Path, why: str) -> None:
    """Refuse when the run is closed: 'run <name> is closed (<status> at <closed>) — <why>'."""
    if state_write.closed(run):
        raise cli.Refusal(state_write.closed_refusal(run, why))


def refuse_old(run: Path, doing: str) -> None:
    """Refuse to carry on (doing: resumed, advanced) a run opened on the path 2.1.0 removed (stages.old_path), with its
    next step: close it paused, or leave it paused, and start the work again. Closing and reading it are never
    refused."""
    why = stages.old_path(run)
    if not why:
        return
    content = state.text(run)
    mode, paused = state.field(content, "mode"), state.field(content, "status").startswith("paused")
    again = "council run open %s" % mode if mode in stages.ONE_PAGE else "the council command for the work"
    close = ("it is paused, so leave it as it is" if paused else
             "close it paused: council run close --run %s --status paused" % run.name)
    raise cli.Refusal("run %s can't be %s: an older Small Council opened it on a path this version no longer runs "
                      "(%s) — next: %s, then start the work again (%s). Its record stays readable: council status "
                      "--run %s" % (run.name, doing, why, close, again, run.name))
