"""The helper's mkdir lock (bin/council: event_lock, event_unlock, event_lock_stale), step for step, so a
Python writer and a bash writer of events.tsv or seats.tsv exclude each other.

A lock is a directory (`<file>.lock`) holding an `owner` file with the holder's process id. A lock
whose owner is no live process, or one with no readable owner that is ten seconds old, is stale. A stale
lock is reclaimed only through a second directory, `<lock>.recover`, so two waiters never both remove it,
and a writer never takes the lock while a reclaim is under way.

A made directory is not yet a held lock: the owner file decides (bin/council's lock_claim). uutils mkdir
0.10.0 exits 0 when the directory is already there, so a bash caller can be told it made a lock another
holds. Both languages therefore hold a lock, or a `.recover`, only once they created its owner file
exclusively (O_EXCL).
"""

from contextlib import contextmanager
import os
from pathlib import Path
import re
import time
from typing import Iterator, Optional, Union

from council.records.paths import RecordError

TRIES = 200          # the helper's default: 200 tries, 0.1 s apart
PAUSE = 0.1
STALE_SECONDS = 10   # a lock with no owner number this old was left by a writer killed before writing it


class LockError(RecordError):
    """A lock that could not be taken in the tries allowed."""


def alive(pid: int) -> bool:
    """True when pid is a running process, as `kill -0` answers: a process this user may not signal
    counts as gone, as it does for the helper."""
    if os.name == "nt":
        return _alive_windows(pid)
    try:
        os.kill(pid, 0)
    except (OSError, OverflowError, ValueError):
        return False
    return True


def _alive_windows(pid: int) -> bool:
    try:
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
    except (OSError, OverflowError, ValueError, TypeError, AttributeError, ImportError):
        return False
    if not handle:
        return ctypes.get_last_error() == 5                     # access denied: it exists
    try:
        code = ctypes.c_ulong()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True
        return code.value == 259                                 # STILL_ACTIVE
    finally:
        kernel.CloseHandle(handle)


def _first_line(path: Path) -> Optional[str]:
    """The file's first line without its newline (bash's `IFS= read -r`), or None when it can't be read."""
    try:
        with open(str(path), "rb") as handle:
            return handle.readline().decode("utf-8", "replace").rstrip("\n")
    except OSError:
        return None


def stale(lock: Union[str, Path]) -> bool:
    """event_lock_stale: the lock exists and its holder is gone."""
    lock = Path(lock)
    if not lock.is_dir():
        return False
    owner_file = lock / "owner"
    if owner_file.is_file():
        owner = _first_line(owner_file)
        if owner is None:
            if not owner_file.is_file():
                return False          # the holder released between the test and the read
            owner = ""
        if re.fullmatch(r"[0-9]+", owner):
            if alive(int(owner)):
                return False
            # Stale only while the file still names that writer: one that released has removed it,
            # and one that took the lock since has written its own number.
            return _first_line(owner_file) == owner
    # A writer can be killed between mkdir and writing owner: only an old lock is stale.
    try:
        modified = int(lock.stat().st_mtime)
    except OSError:
        return False
    return int(time.time()) - modified >= STALE_SECONDS


def _make(folder: Path) -> bool:
    try:
        os.mkdir(str(folder))
    except OSError:
        return False
    return True


HELD, TAKEN, FAILED = 0, 1, 2   # lock_claim's exits


def _claim(folder: Path, owner: str) -> int:
    """lock_claim: create folder/owner exclusively and write the owner line. HELD; TAKEN when another
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
        try:
            owner_file.unlink()
        except OSError:
            pass
        return FAILED
    return HELD


def _remove_folder(folder: Path) -> None:
    try:
        os.rmdir(str(folder))
    except OSError:
        pass


def release(lock: Union[str, Path]) -> bool:
    """event_unlock: remove the owner file, then the lock directory. False when either is refused."""
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


def acquire(lock: Union[str, Path], tries: int = TRIES) -> bool:
    """event_lock: take the lock, reclaiming a stale one, trying `tries` times 0.1 s apart."""
    lock = Path(lock)
    recovery = Path(str(lock) + ".recover")
    owner = str(os.getpid())
    count = 0
    while True:
        if not recovery.is_dir() and _make(lock):
            claimed = _claim(lock, owner)             # the owner file decides who holds it, not mkdir
            if claimed == HELD:
                if recovery.is_dir():                 # a reclaim began just before: yield this lock to it
                    release(lock)
                    continue
                return True
            if claimed == FAILED:
                _remove_folder(lock)
                return False
            # TAKEN: another caller holds it — wait like any other
        if stale(recovery):
            release(recovery)
        if stale(lock) and _make(recovery):
            claimed = _claim(recovery, owner)
            if claimed == HELD and stale(lock):
                release(lock)
            if claimed != TAKEN:                      # another reclaimer's: leave it to that one
                release(recovery)
        count += 1
        if count >= tries:
            return False
        time.sleep(PAUSE)


@contextmanager
def held(lock: Union[str, Path], tries: int = TRIES) -> Iterator[Path]:
    """The lock for the length of a with block; LockError when it can't be taken."""
    lock = Path(lock)
    if not acquire(lock, tries):
        raise LockError("event lock unavailable: {}".format(lock))
    try:
        yield lock
    finally:
        release(lock)
