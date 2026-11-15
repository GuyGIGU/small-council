"""Record one event for a command: `append` for one whose result doesn't hang on it (a failure is said on stderr
and never changes the result), `need` for one that refuses without it (event_append || die)."""
from __future__ import annotations

from pathlib import Path

from council.commands import cli
from council.records import events


def append(run: str | Path, kind: str, subject: str, value: str, detail: str, said: str, once: bool = False) -> bool:
    """events.append; on a failure its reason and then `said` go to stderr. False when nothing was recorded."""
    try:
        return events.append(Path(run), kind, subject, value, detail, once)
    except events.EventError as failure:
        cli.warn("council: %s" % failure)
        cli.warn("council: " + said)
        return False


def need(run: str | Path, kind: str, subject: str, value: str, detail: str, refusal: str) -> bool:
    """events.append, or a Refusal that says the event's own reason and then `refusal` (two stderr lines, exit 2).
    False is success too: a run from before the stream, or a once-only event already on record."""
    try:
        return events.append(Path(run), kind, subject, value, detail)
    except events.EventError as failure:
        raise cli.Refusal("%s\ncouncil: %s" % (failure, refusal)) from None


def writable(run: Path) -> None:
    """events.writable, as a Refusal."""
    try:
        events.writable(run)
    except events.EventError as failure:
        raise cli.Refusal(str(failure)) from None
