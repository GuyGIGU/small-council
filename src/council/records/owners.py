"""Who holds a lock (D33): the process its owner file names (the system's id, whichever language wrote it;
bin/council: lock_owner), whether it runs, and what a waiter that gives up says. A lock is taken only from a
dead holder, never from one that reads alive; a line no process could have written (named) is no owner,
stale once 10 s old, as bash reads it too. Windows soon reuses a dead process's id: there a live process made
REUSE_SECONDS after the owner file was written is not its holder (Python only: bash can't read a start)."""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

from council.records.paths import open_shared

REUSE_SECONDS = 2       # a holder writes its owner file after it starts; the slack is for coarse file clocks
PID_LIMIT = 2 ** 32 - 1 if os.name == "nt" else 2 ** 31 - 1    # the largest id the system's type holds
_EPOCH_TICKS = 116444736000000000    # 1970-01-01 in Windows FILETIME units (100 ns since 1601)
_QUERY = 0x1000         # PROCESS_QUERY_LIMITED_INFORMATION
_DENIED = 5             # ERROR_ACCESS_DENIED: the process exists, this user may not ask about it
_ACTIVE = 259           # STILL_ACTIVE


def named(owner: str) -> int | None:
    """The process id an owner line names; None when no process could have one: not digits, 0 (to kill(),
    the caller's own group), or past PID_LIMIT (a DWORD on Windows, a pid_t elsewhere)."""
    pid = int(owner) if re.fullmatch(r"0*[0-9]{1,10}", owner) else 0
    return pid if 0 < pid <= PID_LIMIT else None


def alive(pid: int) -> bool:
    """True when pid runs, as `kill -0` answers: one this user may not signal, or an id named() refuses, is
    gone. On Windows os.kill(pid, 0) sends CTRL_C_EVENT: never used."""
    if not 0 < pid <= PID_LIMIT:
        return False
    if os.name == "nt":
        return _windows(pid)[0]
    try:
        os.kill(pid, 0)
    except (OSError, OverflowError, ValueError):
        return False
    return True


def holder_alive(pid: int, owner_file: Path) -> bool:
    """alive(pid), and on Windows also not a later process given the dead holder's id."""
    if os.name != "nt" or not 0 < pid <= PID_LIMIT:
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
    """Made (seconds since 1970) over REUSE_SECONDS after its owner file was written: not its writer."""
    return created is not None and created > written + REUSE_SECONDS


def _windows(pid: int) -> tuple[bool, float | None]:
    """(running, when it was made) for a Windows process id; (True, None) when it exists but can't be asked."""
    try:
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)   # a DWORD id: no wrap
        handle = kernel.OpenProcess(_QUERY, False, pid)
    except (OSError, OverflowError, ValueError, TypeError, AttributeError, ImportError):
        return False, None
    if not handle:
        return ctypes.get_last_error() == _DENIED, None
    try:
        code, times = ctypes.c_ulong(), (ctypes.c_ulonglong * 4)()    # made, ended, in kernel, in user
        if kernel.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value != _ACTIVE:
            return False, None
        if not kernel.GetProcessTimes(handle, *(ctypes.byref(times, 8 * i) for i in range(4))):
            return True, None
        return True, (times[0] - _EPOCH_TICKS) / 1e7
    finally:
        kernel.CloseHandle(handle)


def first_line(path: Path) -> str | None:
    """The first line as bash's `IFS= read -r` reads it, None if unreadable; shared for delete on Windows."""
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
    if named(owner) is None:
        return "event lock unavailable: %s (no holder named in it, age %s) — run this again" % (lock, age)
    return ("event lock unavailable: %s (held by process %s, age %s) — run this again once that call ends; "
            "if process %s is not a council call, remove that folder first" % (lock, owner, age, owner))
