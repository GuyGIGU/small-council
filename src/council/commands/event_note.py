"""Record one event for a command whose result doesn't hang on it: a failure is said on stderr, with what it
means for the command's own result, and never changes that result."""
from __future__ import annotations

from pathlib import Path

from council.commands import cli
from council.records import events


def append(run: str | Path, kind: str, subject: str, value: str, detail: str, said: str) -> bool:
    """events.append; on a failure its reason (the events file written as the helper writes paths) and then
    `said` go to stderr. False when nothing was recorded."""
    try:
        return events.append(Path(run), kind, subject, value, detail)
    except events.EventError as failure:
        where = events.path(Path(run))
        cli.warn("council: " + str(failure).replace(str(where), where.as_posix()))
        cli.warn("council: " + said)
        return False
