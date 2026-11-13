"""Who holds a lock (D33): the process its owner file names, whether that process still runs, and what a
waiter that gives up says about it.

The owner file names its holder by the operating system's process id, whichever language wrote it: Python
writes os.getpid(), bash writes its Windows id under Git Bash, MSYS2 and Cygwin (bin/council: lock_owner).
A lock is taken only from a holder that is dead, never from one that reads alive, however old.

Windows hands a dead process's id to a new process soon after. So on Windows a live process is the holder
only if it was made before its owner file was written: one made more than REUSE_SECONDS after is another
process that got the dead holder's id. bash has no cheap way to read a process's start, so this check is
Python's alone.
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

from council.records.paths import open_shared

REUSE_SECONDS = 2       # a holder writes its owner file after it starts; the slack is for coarse file clocks
_EPOCH_TICKS = 116444736000000000    # 1970-01-01 in Windows FILETIME units (100 ns since 1601)
_QUERY = 0x1000         # PROCESS_QUERY_LIMITED_INFORMATION
_DENIED = 5             # ERROR_ACCESS_DENIED: the process exists, this user may not ask about it
_ACTIVE = 259           # STILL_ACTIVE


def alive(pid: int) -> bool:
    """True when pid is a running process, as `kill -0` answers: a process this user may not signal
    counts as gone, as it does for the helper. On Windows os.kill(pid, 0) sends CTRL_C_EVENT: never used."""
    if os.name == "nt":
        return _windows(pid)[0]
    try:
        os.kill(pid, 0)
    except (OSError, OverflowError, ValueError):
        return False
    return True


def holder_alive(pid: int, owner_file: Path) -> bool:
    """alive(pid), and on Windows also not a later process given the dead holder's id."""
    if os.name != "nt":
        return alive(pid)
    running, created = _windows(pid)
    if not running:
        return False
    try:
        written = owner_file.stat().st_mtime
    except OSError:
        return True
    return not reused(created, written)


def reused(created: float | None, written: float) -> bool:
    """A process made (created, seconds since 1970) more than REUSE_SECONDS after its owner file was written
    is not the one that wrote it. An unknown start time is no evidence: it counts as the holder."""
    return created is not None and created > written + REUSE_SECONDS


def _windows(pid: int) -> tuple[bool, float | None]:
    """(running, when it was made) for a Windows process id; (True, None) when it exists but can't be asked."""
    try:
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel.OpenProcess(_QUERY, False, pid)
    except (OSError, OverflowError, ValueError, TypeError, AttributeError, ImportError):
        return False, None
    if not handle:
        return ctypes.get_last_error() == _DENIED, None
    try:
        code = ctypes.c_ulong()
        if kernel.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value != _ACTIVE:
            return False, None
        made, ended, in_kernel, in_user = (ctypes.c_ulonglong() for _ in range(4))
        if not kernel.GetProcessTimes(handle, ctypes.byref(made), ctypes.byref(ended),
                                      ctypes.byref(in_kernel), ctypes.byref(in_user)):
            return True, None
        return True, (made.value - _EPOCH_TICKS) / 1e7
    finally:
        kernel.CloseHandle(handle)


def first_line(path: Path) -> str | None:
    """The file's first line without its newline (bash's `IFS= read -r`), or None when it can't be read.
    On Windows it is read with delete sharing: a plain open would stop the holder removing it on release."""
    try:
        shared = open_shared(path)
        with shared if shared is not None else open(str(path), "rb") as handle:
            return handle.readline().decode("utf-8", "replace").rstrip("\n")
    except OSError:
        return None


def unavailable(lock: Path) -> str:
    """A waiter's refusal (D19): which lock, who holds it and for how long, and what to do next."""
    owner = first_line(lock / "owner") or ""
    try:
        age = "%d s" % max(0, int(time.time()) - int(lock.stat().st_mtime))
    except OSError:
        age = "unknown"
    if not re.fullmatch(r"[0-9]+", owner):
        return "event lock unavailable: {} (no holder named in it, age {}) — run this again".format(lock, age)
    return ("event lock unavailable: {lock} (held by process {pid}, age {age}) — run this again once that call "
            "ends; if process {pid} is not a council call, remove that folder first").format(
                lock=lock, pid=owner, age=age)
