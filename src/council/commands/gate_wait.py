"""The run moves on — a gate runs: a wait it recorded is over, and so is the alert asked for it (the helper's
wait_over). A narrow copy of what `council state waiting=` does (bin/council cmd_state), kept until the state
writer is ported (S8b): the same state lock, the same header rewrite, the same run.waiting_changed event. Any
fault leaves the state as it was and never stops the gate, as `( cmd_state waiting= ) >/dev/null 2>&1 || :` did."""
from __future__ import annotations

import os
import time
from pathlib import Path

from council.commands import resolve
from council.records import events, locks, paths, state

NEXT_AT_OPEN = "size the run and ask for the go-ahead"   # a new run's next: — Convene's own step


def closed(run: Path) -> bool:
    """run_closed: complete or abandoned, its close recorded. A status set by hand is not a close."""
    return resolve.field(run, "status") in ("complete", "abandoned") and resolve.field(run, "closed") != ""


def over(run: Path) -> None:
    """Clear the run's `waiting:`, when it has one and is still open."""
    if not resolve.field(run, "waiting") or closed(run):
        return
    try:
        _clear(run)
    except (OSError, events.EventError, locks.LockError):
        pass


def ready(run: Path) -> bool:
    """event_ready: the run's event stream takes an event (or the run keeps none)."""
    if not resolve.field(run, "events-schema"):
        return True
    try:
        data = events.path(run).read_bytes()
    except OSError:
        return False
    if not data.endswith(b"\n"):                 # empty, or its last line is torn
        return False
    last = data[:-1].rsplit(b"\n", 1)[-1].replace(b"\r", b"").decode("utf-8", "surrogateescape").split("\t")
    return len(last) == 7 and last[0] == "1" and last[1].isdigit() and last[1].isascii()


def _clear(run: Path) -> None:
    if not ready(run):
        return
    file = state.path(run)
    with locks.held(str(file) + ".lock"):
        if closed(run):
            return
        lines = _lines(file.read_bytes().decode("utf-8", "surrogateescape"))
        _set(lines, "waiting:", "waiting: ", header_only=False, before_heading=True)
        if state.field("\n".join(lines), "phase") not in ("", "convene") \
                and state.field("\n".join(lines), "next") == NEXT_AT_OPEN:
            _set(lines, "next:", "next:", header_only=True, before_heading=False)
        _set(lines, "updated:", "updated: " + time.strftime("%Y-%m-%d %H:%M"), header_only=False,
             before_heading=False)
        temporary = Path("%s.tmp%d" % (file, os.getpid()))
        try:
            temporary.write_bytes("".join(line + "\n" for line in lines).encode("utf-8", "surrogateescape"))
            os.replace(str(temporary), str(file))
        finally:
            if temporary.exists():
                temporary.unlink()
        events.append(run, "run.waiting_changed", "run", "off", "from=on")


def _lines(content: str) -> list[str]:
    """The state's lines as awk printed them: the BOM off line 1, a last line without a newline still a line."""
    if content.startswith(paths.BOM):
        content = content[len(paths.BOM):]
    found = content.split("\n")
    return found[:-1] if found[-1] == "" else found


def _set(lines: list[str], key: str, line: str, header_only: bool, before_heading: bool) -> None:
    """The first line starting with key becomes line; with before_heading, one is added above the first
    heading (or at the end) when there is none; with header_only, only a line above the first heading counts."""
    for at, found in enumerate(lines):
        if found.startswith("## ") and (header_only or before_heading):
            if before_heading:
                lines.insert(at, line)
            return
        if found.startswith(key):
            lines[at] = line
            return
    if before_heading:
        lines.append(line)
