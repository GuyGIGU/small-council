"""Running one gate command under its time limit, and stopping it with every process it started.

The command runs as `bash -c` in a process group of its own. A watchdog, a separate process in a group of its
own, stops it at the limit: it outlives a helper killed outright, so even then nothing is left running past the
limit. A stop is TERM to the whole group, CONT (a stopped process takes TERM only once it runs again), up to 3 s
for it to go, then KILL. On Windows a Python process can't signal Git Bash's processes (its os.kill is
TerminateProcess), so that one step runs in bash (WINDOWS_STOP): the group's MSYS id is found from the
gate's Windows id, signalled as on POSIX, and the Windows process tree is ended with taskkill, which reaches
the native programs a group signal may miss."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import NamedTuple

from council.commands import shell

SRC = str(Path(__file__).resolve().parents[2])
TIMED_OUT = 124
NO_ROOT = 97               # the code root could not be entered
WINDOWS_STOP = r"""
w="$1" g="" n=0
for d in /proc/[0-9]*; do
  { IFS= read -r p < "$d/winpid"; } 2>/dev/null || continue
  if [ "$p" = "$w" ]; then g="${d#/proc/}"; break; fi
done
if [ -n "$g" ]; then
  kill -TERM -- -"$g" 2>/dev/null || kill -TERM "$g" 2>/dev/null
  kill -CONT -- -"$g" 2>/dev/null
  while [ "$n" -lt 30 ] && kill -0 -- -"$g" 2>/dev/null; do sleep 0.1; n=$((n + 1)); done
fi
taskkill //F //T //PID "$w" >/dev/null 2>&1
if [ -n "$g" ]; then kill -KILL -- -"$g" 2>/dev/null; kill -KILL "$g" 2>/dev/null; fi
exit 0
"""
WATCH = ("import sys; sys.path.insert(0, sys.argv[1]); from council.commands import gate_exec; "
         "gate_exec.watch(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])")


class Running(NamedTuple):
    gate: subprocess.Popen
    watchdog: subprocess.Popen | None


RUNNING: list[Running] = []          # the gate this call is running, for stop_running on every way out


def _detached() -> dict:
    """Popen's arguments for a process in a group of its own."""
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    return {"start_new_session": True}


def execute(top: str, base: str, command: str, out: str, limit: int) -> tuple[int, bool]:
    """Run command in code root top (COUNCIL_BASE=base), all its output to file out, under limit seconds:
    (its exit code, False), or (124, True) when the watchdog stopped it."""
    flag = Path(out + ".timed-out")
    _remove(flag)
    with open(out, "wb") as handle:
        if not os.path.isdir(top):
            return NO_ROOT, False
        shell.flush()
        try:
            gate = subprocess.Popen(shell.argv_for([shell.bash(), "-c", command]), cwd=top, stdin=subprocess.DEVNULL,
                                    stdout=handle, stderr=subprocess.STDOUT,
                                    env=shell.child_env({"COUNCIL_BASE": base}), **_detached())
        except OSError:
            return NO_ROOT, False
    RUNNING.append(Running(gate, None))
    watchdog = _watch(gate.pid, limit, flag)
    RUNNING[-1] = Running(gate, watchdog)
    code = gate.wait() if watchdog is not None else _wait(gate, limit, flag)
    timed_out = flag.exists()
    if timed_out and watchdog is not None:
        watchdog.wait()                      # let it finish stopping what is left
    elif watchdog is not None:
        _end_watchdog(watchdog)
    RUNNING.clear()
    _remove(flag)
    return (TIMED_OUT, True) if timed_out else (shell.status(code), False)


def _wait(gate: subprocess.Popen, limit: int, flag: Path) -> int:
    """With no watchdog process, the helper holds the limit itself."""
    try:
        return gate.wait(timeout=limit)
    except subprocess.TimeoutExpired:
        flag.touch()
        stop(gate.pid)
        return gate.wait()


def _watch(pid: int, limit: int, flag: Path) -> subprocess.Popen | None:
    try:
        return subprocess.Popen([sys.executable, "-E", "-s", "-c", WATCH, SRC, str(pid), str(limit), str(flag)],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                **_detached())
    except OSError:
        return None


def watch(pid: int, limit: int, flag: str) -> None:
    """The watchdog: once the gate has run `limit` seconds, mark it timed out and stop it; it ends by itself
    as soon as the gate has."""
    started = time.monotonic()
    while time.monotonic() - started < limit:
        time.sleep(1)
        if not _alive(pid):
            return
    Path(flag).touch()
    stop(pid)


def _alive(pid: int) -> bool:
    if os.name == "nt":
        from council.records import owners
        return owners.alive(pid)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def stop(pid: int) -> None:
    """Stop the gate whose process group pid leads, and every process it started."""
    if os.name == "nt":
        try:
            subprocess.run(shell.argv_for([shell.bash(), "-c", WINDOWS_STOP, "council", str(pid)]), stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        return
    if not _signal_group(pid, signal.SIGTERM):
        _signal(pid, signal.SIGTERM)
    _signal_group(pid, signal.SIGCONT)
    for _ in range(30):
        if not _signal_group(pid, 0):
            break
        time.sleep(0.1)
    _signal_group(pid, signal.SIGKILL)
    _signal(pid, signal.SIGKILL)


def _signal_group(pid: int, number: int) -> bool:
    try:
        os.killpg(pid, number)  # type: ignore[attr-defined]
    except OSError:
        return False
    return True


def _signal(pid: int, number: int) -> None:
    try:
        os.kill(pid, number)
    except OSError:
        pass


def _end_watchdog(watchdog: subprocess.Popen) -> None:
    if os.name == "nt" or not _signal_group(watchdog.pid, signal.SIGTERM):
        try:
            watchdog.terminate()
        except OSError:
            pass
    try:
        watchdog.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass


def stop_running() -> None:
    """The gate still running and its watchdog, stopped: every way out of the helper (gate_unlock)."""
    while RUNNING:
        running = RUNNING.pop()
        stop(running.gate.pid)
        if running.watchdog is not None:
            _end_watchdog(running.watchdog)


def _remove(flag: Path) -> None:
    try:
        flag.unlink()
    except OSError:
        pass
