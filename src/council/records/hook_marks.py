"""Which of the plugin's hooks have run in a Claude Code session (issue 69).

A hook leaves a mark: an empty file named after the session id, with the hook's name after a dot, in a per-user
cache folder (not under the council home, so it exists before council-init makes one). A bare `<id>` mark says
that some hook ran: `council run open` looks for it. This is bin/council's `session_dirs` and
`mark_hooks_ran` in Python, for the hook whose decision the helper makes in Python (the agent gate), and for
reading all of them. A mark means the hook fired in this session: a hook whose event has not happened yet
(a Stop before the first turn ends, an agent gate before the first agent) is not seen, and is not broken.
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

from council.records.home import native

# (mark name, the event that runs it, when it first runs), in the order doctor says them.
HOOKS = (("session-start", "SessionStart", "when the session starts, resumes or compacts"),
         ("turn-end", "Stop", "when a turn ends"),
         ("bash-gate", "bash-gate", "before a Bash call that names council or pushes"),
         ("seat-gate", "seat-gate", "when a seat's agent stops"),
         ("agent-gate", "agent-gate", "before an agent is dispatched"))
SAFE = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]*")
PRUNED = ".pruned"                        # a dot name: no session id can be it


def folders() -> list[Path]:
    """The mark folders, as `session_dirs` lists them: $XDG_CACHE_HOME's, and ~/.cache's unless that is the same."""
    xdg, home = native(os.environ.get("XDG_CACHE_HOME", "")), native(os.environ.get("HOME", ""))
    found = [Path(xdg) / "small-council" / "sessions"] if xdg else []
    if home and xdg != home + "/.cache":
        found.append(Path(home) / ".cache" / "small-council" / "sessions")
    return found


def put(session: str, hook: str) -> None:
    """Leave this hook's mark (and the bare one), then trim the folder; silent when it can't."""
    if not SAFE.fullmatch(session or ""):
        return
    for folder in folders():
        try:
            folder.mkdir(parents=True, exist_ok=True)
            for name in (session, session + "." + hook):
                (folder / name).touch()
        except OSError:
            continue
        trim(folder)


def trim(folder: Path, now: float | None = None) -> None:
    """Clear the files over 30 days old, at most once a day (the PRUNED stamp's time): a walk over thousands of marks
    on every hook call cost a turn end 270 ms. The bash hooks leave marks without it; the SessionStart hook, which
    runs Python in every project, keeps the folder trimmed."""
    now = time.time() if now is None else now
    stamp = folder / PRUNED
    try:
        if stamp.is_file() and stamp.stat().st_mtime > now - 86400:
            return
        stamp.touch()
    except OSError:
        return
    old = now - 31 * 86400
    for top, _, names in os.walk(str(folder)):
        for file in (os.path.join(top, name) for name in names):
            try:
                if not os.path.islink(file) and os.path.isfile(file) and os.path.getmtime(file) <= old:
                    os.remove(file)
            except OSError:
                pass


def ran(session: str) -> bool:
    """hooks_ran: False only when no folder that a hook could write holds the session's bare mark."""
    found = folders()
    if not SAFE.fullmatch(session or "") or any((folder / session).is_file() for folder in found):
        return True
    for folder in found:
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            return True
        if not os.access(str(folder), os.W_OK):
            return True
    return not found


def seen(session: str) -> list[str]:
    """The hooks (their mark names) with a mark for this session, in HOOKS order."""
    if not SAFE.fullmatch(session or ""):
        return []
    return [hook for hook, _, _ in HOOKS if any((folder / (session + "." + hook)).exists() for folder in folders())]
