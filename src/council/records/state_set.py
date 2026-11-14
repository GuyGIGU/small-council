"""A header field of a run's session-state.md set as `council state <key>=<value>` sets one that records no event
(bin/council's cmd_state): under the state lock, the first `<key>:` line above the first heading rewritten (or one
added there), a stale Convene next: emptied, and updated: stamped. `council index` records its base= this way. Until
the state writer is ported (S8b) bin/council's cmd_state writes the rest: two state writers, this module and
state_write's clear_waiting beside it."""
from __future__ import annotations

import time
from pathlib import Path

from council.records import locks, paths
from council.records.state import field, path
from council.records.state_write import NEXT_AT_OPEN, _put, _raw_lines, _replace, closed


class StateError(Exception):
    """The state could not be written: its lock, a close, or the file itself — said as the helper says it."""


def put(run: Path, key: str, value: str) -> None:
    """Set the header field key to value. StateError when the run is closed or the state can't be written."""
    run = Path(run)
    lock = str(path(run)) + ".lock"
    try:
        with locks.held(lock):
            if closed(run):
                raise StateError("closed")
            lines = _raw_lines(path(run))
            _put(lines, key + ":", "%s: %s" % (key, value.replace("\r", " ").replace("\n", " ")),
                 header_only=False, add=True)
            content = "\n".join(lines)
            if field(content, "phase") not in ("", "convene") and field(content, "next") == NEXT_AT_OPEN:
                _put(lines, "next:", "next:", header_only=True, add=False)
            _put(lines, "updated:", "updated: " + time.strftime("%Y-%m-%d %H:%M"), header_only=False, add=False)
            _replace(path(run), "".join(line + "\n" for line in lines))
    except locks.LockError as failure:
        raise StateError("state lock unavailable: %s" % Path(lock).as_posix()) from failure
    except (OSError, paths.RecordError) as failure:
        raise StateError("cannot update %s" % path(run).as_posix()) from failure
