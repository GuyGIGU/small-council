"""One `council gate` per run at a time. Two copies write the same gates/<name>.txt and .json: a real run started
`gate --all` twice, the second copy overwrote the first's output, and its results became the run's events and
its baseline — a test failure that never happened.

The lock is <run>/gates.lock, the mkdir lock of records/locks.py; its owner file holds the holder's process id
(the operating system's, D33), then when it started. A second call never waits unless asked (--wait): it refuses
before it writes anything. The holder releases on every way out, a stop by HUP, INT or TERM too; a lock whose
process is gone is cleared by the next call, which says so."""
from __future__ import annotations

import contextlib
import os
import signal
import time
from pathlib import Path

from council.commands import cli, gate_exec
from council.records import locks, owners

WAIT_LIMIT = 1200          # plain --wait queues up to 20 minutes
TRIES = 150
EXITS = {"SIGHUP": 129, "SIGINT": 130, "SIGTERM": 143}
HELD: list[Path] = []


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def take(run: str, wait: bool, limit: str = str(WAIT_LIMIT)) -> None:
    """Hold the run's gate lock until release(), or refuse (exit 2) before anything is written. limit is
    --wait's, in seconds, as given: one that is no number refuses at the first wait, as bash's test did."""
    lock, recovery, me = Path(run + "/gates.lock"), Path(run + "/gates.lock.recover"), str(os.getpid())
    tries = waited = 0
    while True:
        if not recovery.is_dir() and _make(lock):
            claimed = locks.claim(lock, me + "\n" + now())     # the owner file decides who holds it, not mkdir
            if claimed == locks.HELD:
                if recovery.is_dir():                             # a reclaimer got in first: yield
                    locks.release(lock)
                    continue
                _hold(lock)
                return
            if claimed == locks.FAILED:
                _rmdir(lock)
                raise cli.Refusal("cannot write the gate lock %s — nothing was started" % lock.as_posix())
        pid, since = _owner(lock)
        _reclaim(lock, recovery, me, pid, since)
        holder = owners.named(pid) if pid.isdigit() else None
        if holder is not None and owners.holder_alive(holder, lock / "owner"):
            if not wait:
                raise cli.Refusal("checks are already running for this run (%s, started %s, process %s) — wait for "
                                  "them to finish; nothing was started (to queue behind them instead: council gate "
                                  "--wait …)" % (Path(run).name, since or "a moment ago", pid))
            waited += 1
            if waited > (int(limit) if limit.isdigit() and limit.isascii() else -1):
                raise cli.Refusal("checks are still running for this run (%s, started %s, process %s) after %s "
                                  "seconds of --wait — nothing was started"
                                  % (Path(run).name, since or "a moment ago", pid, limit))
            time.sleep(1)
            continue
        tries += 1
        if tries >= TRIES:
            raise cli.Refusal("the gate lock is unavailable: %s — nothing was started" % lock.as_posix())
        time.sleep(0.1)


def _owner(lock: Path) -> tuple[str, str]:
    """(pid, since) from the owner file; empty while it is being written or removed — never a stale lock."""
    try:
        with open(str(lock / "owner"), "rb") as handle:
            lines = handle.read(4096).decode("utf-8", "replace").split("\n")
    except OSError:
        return "", ""
    return lines[0], (lines[1] if len(lines) > 1 else "")


def _reclaim(lock: Path, recovery: Path, me: str, pid: str, since: str) -> None:
    """A lock left by a call that is no longer running is cleared, through <lock>.recover, and said once."""
    if locks.stale(recovery):
        locks.release(recovery)
    if locks.stale(lock) and _make(recovery):
        claimed = locks.claim(recovery, me)
        if claimed == locks.HELD and locks.stale(lock) and locks.release(lock):
            cli.warn("council: cleared a gate lock left by a call that is no longer running%s"
                     % (" (process %s, started %s)" % (pid, since or "unknown") if pid else ""))
        if claimed != locks.TAKEN:                       # another reclaimer's: leave it to that one
            locks.release(recovery)


def _make(folder: Path) -> bool:
    try:
        os.mkdir(str(folder))
    except OSError:
        return False
    return True


def _rmdir(folder: Path) -> None:
    with contextlib.suppress(OSError):
        os.rmdir(str(folder))


def _stopped(number: int, frame: object) -> None:
    raise SystemExit(EXITS.get(signal.Signals(number).name, 128 + number))


def _hold(lock: Path) -> None:
    HELD.append(lock)
    for name in EXITS:
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), _stopped)


def release() -> None:
    """Every way out: a gate still running goes with this call, then the lock, if it is still this call's."""
    gate_exec.stop_running()
    while HELD:
        lock = HELD.pop()
        if owners.first_line(lock / "owner") == str(os.getpid()):
            locks.release(lock)
