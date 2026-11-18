"""The helper's one-line nudges to the Chair on stderr, and the card-due mark."""
from __future__ import annotations

import contextlib
from pathlib import Path

from council.commands import cli, resolve
from council.records import config
from council.records import home as where

CARD_DUE = "card-due"   # "due" from the first dispatch, "reminded" once the turn-end hook asked; gone once shown
TOOL = "with a PushNotification tool (it may be a deferred tool: search the tools for it before deciding there is none)"


def waiting_nudge(run: Path, named: bool) -> None:
    """The run now waits on the user: send them the alert line once. named: the call passed --run."""
    at = " --run " + Path(run).name if named else ""
    clears = "Their answer clears the wait at the next stage change, or council state waiting=%s clears it" % at
    if config.notifications_off(where.run_home(run)):
        cli.warn("council: the run now waits on the user. " + clears)
    else:
        cli.warn("council: the run now waits on the user: send the line `council status --line%s` prints, once, %s. %s"
                 % (at, TOOL, clears))


def status_nudge(run: Path, when: str, named: bool) -> None:
    """Show the status card: at the first dispatch (marks card-due) or the close (with the alert)."""
    at = " --run " + Path(run).name if named or when == "close" else ""
    lead = "first dispatch of this run — show the user its status now, once"
    alert = ""
    if when == "close":
        lead = "run closed — show the user its closing card now, once"
        if resolve.field(run, "status") == "complete" and not config.notifications_off(where.run_home(run)):
            alert = ("; then send the owner the line `council status --line%s` prints, once, with a PushNotification "
                     "tool" % at)
    cli.warn("council: %s: hand the output of `council status --widget%s` to a show_widget tool (it may be a deferred "
             "tool: search the tools for it before deciding there is none), else relay `council status%s` — and if the "
             "card fails to render, give that text and carry on%s"
             % (lead, at, at, alert))
    if when != "close":
        mark_card(run, "due")


def card_due(run: Path) -> bool:
    """The first line of the run's card-due mark is 'due'."""
    try:
        with open(str(Path(run) / CARD_DUE), "rb") as handle:
            return handle.readline().rstrip(b"\n") == b"due"
    except OSError:
        return False


def mark_card(run: Path, word: str) -> bool:
    """Write the card-due mark ('due' or 'reminded'); False when it can't be written."""
    try:
        (Path(run) / CARD_DUE).write_bytes(word.encode() + b"\n")
    except OSError:
        return False
    return True


def clear_card(run: Path) -> None:
    """The card was shown: the mark goes, silently."""
    with contextlib.suppress(OSError):
        (Path(run) / CARD_DUE).unlink()
