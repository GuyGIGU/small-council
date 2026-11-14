"""Writes to a run's session-state.md. So far the one that is Python: a wait that is over (`council state
waiting=`'s path, which `council gate` takes). bin/council's cmd_state writes the rest: two state writers until
the state writer is ported (S8b), which grows this module into the one."""
from __future__ import annotations

import os
import time
from pathlib import Path

from council.records import events, locks, paths
from council.records.state import field, path, text

NEXT_AT_OPEN = "size the run and ask for the go-ahead"   # a new run's next: — Convene's own step


def closed(run: Path) -> bool:
    """run_closed: complete or abandoned, its close recorded. A status set by hand is not a close."""
    content = text(run)
    return field(content, "status") in ("complete", "abandoned") and field(content, "closed") != ""


def clear_waiting(run: Path) -> bool:
    """The run moves on — a seat or a gate: its `waiting:` is cleared, as `council state waiting=` does (bin/council
    cmd_state), under the same lock, with the same lines and the one run.waiting_changed event. False, the state
    as it was, when there was no wait, the run is closed, or the lock or the event stream can't be had."""
    run = Path(run)
    if not field(text(run), "waiting") or closed(run) or not _takes_events(run):
        return False
    try:
        with locks.held(str(path(run)) + ".lock"):
            if closed(run):
                return False
            lines = _raw_lines(path(run))
            _put(lines, "waiting:", "waiting: ", header_only=False, add=True)
            content = "\n".join(lines)
            if field(content, "phase") not in ("", "convene") and field(content, "next") == NEXT_AT_OPEN:
                _put(lines, "next:", "next:", header_only=True, add=False)
            _put(lines, "updated:", "updated: " + time.strftime("%Y-%m-%d %H:%M"), header_only=False, add=False)
            _replace(path(run), "".join(line + "\n" for line in lines))
            events.append(run, "run.waiting_changed", "run", "off", "from=on")
    except (OSError, paths.RecordError):
        return False
    return True


def _takes_events(run: Path) -> bool:
    """event_ready: the run's event stream takes an event (or the run keeps none)."""
    if not field(text(run), "events-schema"):
        return True
    try:
        data = (run / "events.tsv").read_bytes()
    except OSError:
        return False
    if not data.endswith(b"\n"):                 # empty, or its last line is torn
        return False
    last = data[:-1].rsplit(b"\n", 1)[-1].replace(b"\r", b"").decode("utf-8", "surrogateescape").split("\t")
    return len(last) == 7 and last[0] == "1" and last[1].isdigit() and last[1].isascii()


def _raw_lines(file: Path) -> list[str]:
    """The state's lines as awk printed them: the BOM off line 1, a last line without a newline still a line. Git
    Bash's awk reads in text mode, so on Windows a line's carriage return is dropped; elsewhere it is kept."""
    content = file.read_bytes().decode("utf-8", "surrogateescape")
    if content.startswith(paths.BOM):
        content = content[len(paths.BOM):]
    if os.name == "nt":
        content = content.replace("\r\n", "\n")
    found = content.split("\n")
    return found[:-1] if found[-1] == "" else found


def _put(lines: list[str], key: str, line: str, header_only: bool, add: bool) -> None:
    """The first line starting with key becomes line. With add, one goes above the first heading (or at the end)
    when there is none; with header_only, a line below the first heading never counts."""
    for at, found in enumerate(lines):
        if found.startswith("## ") and (header_only or add):
            if add:
                lines.insert(at, line)
            return
        if found.startswith(key):
            lines[at] = line
            return
    if add:
        lines.append(line)


def _replace(file: Path, content: str) -> None:
    temporary = Path("%s.tmp%d" % (file, os.getpid()))
    try:
        temporary.write_bytes(content.encode("utf-8", "surrogateescape"))
        os.replace(str(temporary), str(file))
    finally:
        if temporary.exists():
            temporary.unlink()
