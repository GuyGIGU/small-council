"""Record one event for a command: `append` for one whose result doesn't hang on it (a failure is said on stderr
and never changes the result), `need` for one that refuses without it (event_append || die)."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from council.commands import cli
from council.records import events, locks


def append(run: str | Path, kind: str, subject: str, value: str, detail: str, said: str, once: bool = False) -> bool:
    """events.append; on a failure its reason and then `said` go to stderr. False when nothing was recorded."""
    try:
        return events.append(Path(run), kind, subject, value, detail, once)
    except events.EventError as failure:
        cli.warn("council: %s" % failure)
        cli.warn("council: " + said)
        return False


def need(run: str | Path, kind: str, subject: str, value: str, detail: str, refusal: str) -> bool:
    """events.append, or a Refusal: the event's reason, then `refusal`. False is success too."""
    try:
        return events.append(Path(run), kind, subject, value, detail)
    except events.EventError as failure:
        raise cli.Refusal("%s\ncouncil: %s" % (failure, refusal)) from None


@contextmanager
def locked(lock: Path, unavailable: str, unreleased: str = "") -> Iterator[None]:
    """A with block under a run file's lock: refused with its holder and `unavailable` when it can't be taken,
    and with `unreleased`, when one is given, if the lock stays held after the block."""
    if not locks.acquire(lock):
        raise cli.Refusal("%s\ncouncil: %s" % (events.busy(lock), unavailable))
    try:
        yield
    finally:
        released = locks.release(lock)
    if not released and unreleased:
        raise cli.Refusal(unreleased)


def writable(run: Path) -> None:
    """events.writable, as a Refusal."""
    try:
        events.writable(run)
    except events.EventError as failure:
        raise cli.Refusal(str(failure)) from None
