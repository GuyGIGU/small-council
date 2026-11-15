"""The mkdir lock that keeps two writers of one run file (events.tsv, seats.tsv) apart.

A lock is a directory (`<file>.lock`) whose `owner` file names the holder's process (records/owners.py,
D33). A lock whose owner is no live process, or one with no readable owner that is ten seconds old, is
stale, and is reclaimed only through `<lock>.recover`, so two waiters never both remove it. A caller holds
a lock, or a `.recover`, only once it created the owner file exclusively (O_EXCL): the folder alone is not
a held lock.
"""
from __future__ import annotations

import os
import time
from contextlib import suppress
from pathlib import Path

from council.records.owners import first_line, holder_alive, named

TRIES = 200          # the helper's default: 200 tries, 0.1 s apart
PAUSE = 0.1
STALE_SECONDS = 10   # a lock with no owner number this old was left by a writer killed before writing it


def stale(lock: str | Path) -> bool:
    """The lock exists and its holder is gone."""
    lock = Path(lock)
    if not lock.is_dir():
        return False
    owner_file = lock / "owner"
    if owner_file.is_file():
        owner = first_line(owner_file)
        if owner is None:
            if not owner_file.is_file():
                return False          # the holder released between the test and the read
            owner = ""
        pid = named(owner)
        if pid is not None:
            if holder_alive(pid, owner_file):
                return False
            # Stale only while the file still names that writer: one that released has removed it,
            # and one that took the lock since has written its own number.
            return first_line(owner_file) == owner
    # A writer can be killed between mkdir and writing owner: only an old lock is stale.
    try:
        modified = int(lock.stat().st_mtime)
    except OSError:
        return False
    return int(time.time()) - modified >= STALE_SECONDS


def make(folder: Path) -> bool:
    """mkdir: True when this call made the folder."""
    try:
        os.mkdir(str(folder))
    except OSError:
        return False
    return True


HELD, TAKEN, FAILED = 0, 1, 2   # claim's answers


def claim(folder: Path, owner: str) -> int:
    """Create folder/owner exclusively and write the owner line. HELD; TAKEN when another
    caller's owner file is there or the folder went (leave it alone); FAILED when it couldn't be made or
    written (nothing of it is left)."""
    owner_file = folder / "owner"
    try:
        handle = os.open(str(owner_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0), 0o666)
    except OSError:
        if owner_file.exists() or not folder.is_dir():
            return TAKEN
        return FAILED
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write((owner + "\n").encode("ascii"))
    except OSError:
        with suppress(OSError):
            owner_file.unlink()
        return FAILED
    return HELD


def remove_folder(folder: Path) -> None:
    """rmdir, quietly: an empty lock folder whose owner file was never written."""
    with suppress(OSError):
        os.rmdir(str(folder))


def release(lock: str | Path) -> bool:
    """Remove the owner file, then the lock directory. False when either is refused."""
    lock = Path(lock)
    try:
        (lock / "owner").unlink()
    except FileNotFoundError:
        pass
    except OSError:
        return False
    try:
        os.rmdir(str(lock))
    except OSError:
        return False
    return True


def reclaim(lock: Path, recovery: Path, owner: str) -> bool:
    """A stale lock cleared through <lock>.recover (a stale .recover first); True when this call cleared it."""
    if stale(recovery):
        release(recovery)
    cleared = False
    if stale(lock) and make(recovery):
        claimed = claim(recovery, owner)
        cleared = claimed == HELD and stale(lock) and release(lock)
        if claimed != TAKEN:                      # another reclaimer's: leave it to that one
            release(recovery)
    return cleared


def acquire(lock: str | Path, tries: int = TRIES) -> bool:
    """Take the lock, reclaiming a stale one, trying `tries` times 0.1 s apart."""
    lock = Path(lock)
    recovery = Path(str(lock) + ".recover")
    owner = str(os.getpid())
    count = 0
    while True:
        if not recovery.is_dir() and make(lock):
            claimed = claim(lock, owner)              # the owner file decides who holds it, not mkdir
            if claimed == HELD:
                if recovery.is_dir():                 # a reclaim began just before: yield this lock to it
                    release(lock)
                    continue
                return True
            if claimed == FAILED:
                remove_folder(lock)
                return False
            # TAKEN: another caller holds it — wait like any other
        reclaim(lock, recovery, owner)
        count += 1
        if count >= tries:
            return False
        time.sleep(PAUSE)
