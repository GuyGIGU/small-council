"""The desktop pet: a small pumpkin-ghost that shows how this project's council run is going.

`council pet` starts it and returns at once. Right-click it and choose Close, or run
`council pet --stop`. It shows one of five poses, with a one-line bubble under it:
- asleep: no run is open (or the run is paused, stopped early, or has been quiet for an hour);
- working: the run is under way;
- needs you: the run waits for the user's answer, or a build stopped on a failing check;
- stopped: the run is stopped at its agent cap or token ceiling until the user says go;
- done: the run finished — for two minutes, then asleep again.

It only reads. About every five seconds it runs the status reader (`status --run <run> --home <home> --json`, as
the council view does) for the run it follows: the in-progress run of the session that started it, else this
working tree's. It never writes to a run. Its only files are in the OS temp folder, keyed by the project path: a
lock held while it runs, its pid, and a stop request from `council pet --stop`.

It needs Python 3.8+ with tkinter, and a display (views/pet_window.py); its shapes are in views/pet_shapes.py.
`--demo` cycles the poses without reading any run; `--pose <name>` shows one; `--still` turns the motion off.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable

from council.records import state as run_state
from council.records.cells import clean
from council.records.usage import token_text
from council.views.words import plural, span

ENTRY = Path(__file__).resolve().parents[1] / "commands" / "script.py"   # the one way in by path (commands/script)
POSES = ("asleep", "working", "needs-you", "stopped", "done")
POLL_SECONDS = 5          # how often the run is read
DONE_SECONDS = 120        # how long a finished (or paused) run stays on show before the pet sleeps
START_SECONDS = 15        # how long `council pet` waits for the window to show
FIXED = {"blocked": ("needs-you", "Build stopped · your decision?", "accent"),
         "starting": ("working", "Setting up the run", "neutral"),
         "recovering": ("working", "Fixing a failed check", "neutral"),
         "failing": ("working", "A check failed", "neutral")}


# --- what the pet shows for a status reading ------------------------------------------------------------------
def short(text: str, limit: int = 48) -> str:
    """One plain line: control marks and markup dropped, at most `limit` characters."""
    text = re.sub(r"\s+", " ", re.sub(r"[`*#<>\[\]]", "", clean(text or ""))).strip()
    return text if len(text) <= limit else text[:limit - 1].rstrip(" ,;:·—-") + "…"


def view(reading: Any) -> tuple[str, str, str]:
    """(pose, bubble, tone) for one reading: {"kind": "none"} (no run to show), {"kind": "error", "note": …}
    or {"kind": "status", "status": <the status reading>}. Anything unreadable is a calm fallback."""
    reading = reading if isinstance(reading, dict) else {}
    if reading.get("kind") == "none":
        return ("asleep", "No run open", "neutral")
    data = reading.get("status") if reading.get("kind") == "status" else None
    if not isinstance(data, dict):
        return ("asleep", short(reading.get("note") or "Can't read the run right now"), "neutral")
    try:
        return _view(data)
    except (AttributeError, KeyError, TypeError, ValueError):
        return ("asleep", "Can't read the run right now", "neutral")


def _view(data: dict[str, Any]) -> tuple[str, str, str]:
    run, state, usage = data.get("run") or {}, data.get("state") or {}, data.get("usage") or {}
    status, key, limit = run.get("status") or "", state.get("key") or "", usage.get("limit") or {}
    if key == "completed" or status == "complete":
        counts = (data.get("closing") or {}).get("verdict_counts") or {}
        text = "{} done".format(run.get("mode_label") or "Run")
        if counts.get("confirmed"):
            text += " · {} confirmed".format(plural(counts["confirmed"], "finding"))
        return ("done", short(text), "success")
    if status == "paused":
        return ("asleep", "Run paused", "neutral")
    if status == "abandoned":
        return ("asleep", "Run stopped early", "neutral")
    if key == "unknown" or status != "in-progress":
        return ("asleep", "Can't read the run's records", "neutral")
    if limit.get("stopped"):
        used, cap = limit.get("agent_runs"), limit.get("agent_cap")
        if isinstance(used, int) and isinstance(cap, int) and used >= cap:
            return ("stopped", "{} of {} agents used · your go?".format(used, cap), "warning")
        tokens, ceiling = limit.get("tokens"), limit.get("ceiling")
        if isinstance(tokens, int) and isinstance(ceiling, int):
            return ("stopped", "{} of {} tokens · your go?".format(token_text(tokens), token_text(ceiling)), "warning")
        return ("stopped", "At the limit · your go?", "warning")
    if key == "waiting":
        asked = next((a.get("text", "") for a in data.get("attention") or [] if a.get("kind") == "waiting"), "")
        asked = re.sub(r"^Waiting for your answer:\s*", "", asked)
        return ("needs-you", short(asked[:1].upper() + asked[1:]) if asked else "Waiting for your answer", "accent")
    if key in FIXED:
        return FIXED[key]
    if key == "stale":
        quiet = (data.get("freshness") or {}).get("quiet_minutes")
        return ("asleep", "Quiet for {}".format(span(quiet)) if isinstance(quiet, int) else "Quiet for a while",
                "neutral")
    progress = data.get("progress") or {}
    done = (progress.get("counts") or {}).get("done", 0)
    total = len(data.get("seats") or []) + (progress.get("planned") or 0)
    tokens = usage.get("tokens_known") or 0
    text = "{} of {} seats in".format(done, total) if total else (run.get("phase_label") or "Working")
    if tokens:
        text += " · " + token_text(tokens)
    return ("working", short(text), "neutral")


# --- which run to follow -----------------------------------------------------------------------------------
def same_path(a: Any, b: Any) -> bool:
    try:
        return os.path.normcase(os.path.normpath(str(a))) == os.path.normcase(os.path.normpath(str(b)))
    except (TypeError, ValueError):
        return False


def pick(rows: Iterable[tuple[Any, str, str]], tree: str, session: str) -> Any:
    """The run to show: this session's, else one on this working tree that recorded no session, else any
    on this working tree — the newest of each. None when there is none."""
    rows = list(rows)

    def here(root: str) -> bool:
        return not root or same_path(root, tree)

    choices = []
    if session:
        choices.append([r for r in rows if r[2] == session])
        choices.append([r for r in rows if not r[2] and here(r[1])])
    choices.append([r for r in rows if here(r[1])])
    for found in choices:
        if found:
            return found[0][0]
    return None


class Follower:
    """The run the pet follows, and its reading. It asks the status reader as its own process — `<python>
    <entry> status --run <folder> --home <home> --json`, which only reads — and keeps a finished run on show
    for DONE_SECONDS."""

    def __init__(self, python: str, entry: str, home: Any, tree: str, session: str, cwd: str):
        self.python, self.entry, self.home, self.tree = python, entry, home, tree
        self.session, self.cwd = session, cwd
        self.last: Any = None
        self.ended: float | None = None

    def helper(self, *words: str) -> tuple[int, str, str]:
        env = dict(os.environ)
        env.pop("COUNCIL_RUN", None)
        extra: dict[str, Any] = {}
        if os.name == "nt":                      # no console window flashes up on every reading
            info = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
            info.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
            info.wShowWindow = 0
            extra = {"creationflags": 0x08000000, "startupinfo": info}      # CREATE_NO_WINDOW
        done = subprocess.run([self.python, self.entry, *words], cwd=self.cwd, env=env,
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=45, **extra)
        return done.returncode, done.stdout.decode("utf-8", "replace"), done.stderr.decode("utf-8", "replace")

    def read(self, now: float | None = None) -> dict[str, Any]:
        now = time.time() if now is None else now
        folder = pick(run_state.in_progress(self.home), self.tree, self.session)
        if folder is not None:
            self.last, self.ended = folder, None
        elif self.last is None:
            return {"kind": "none"}
        else:                                     # the run followed so far is no longer in progress
            self.ended = self.ended or now
            if now - self.ended > DONE_SECONDS:
                self.last = self.ended = None
                return {"kind": "none"}
        try:
            code, out, err = self.helper("status", "--run", Path(self.last).as_posix(), "--home", str(self.home),
                                         "--json")
            data = json.loads(out) if code == 0 else None
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            code, data, err = -1, None, str(exc)
        if not isinstance(data, dict):
            return {"kind": "error", "note": "Can't read the run right now", "detail": (err or "").strip()[-300:]}
        return {"kind": "status", "status": data}


# --- one pet per project: files in the OS temp folder -------------------------------------------------------
def pet_files(project: Any) -> dict[str, str]:
    key = hashlib.sha256(os.path.normcase(os.path.abspath(str(project))).encode("utf-8", "replace")).hexdigest()[:16]
    base = os.path.join(tempfile.gettempdir(), "small-council-pet-" + key)
    return {"lock": base + ".lock", "pid": base + ".pid", "stop": base + ".stop", "error": base + ".err"}


class Lock:
    """An exclusive lock on a file, held while a pet runs; the OS drops it when the process ends."""

    def __init__(self, path: str):
        self.path: str = path
        self.fd: int | None = None

    def take(self) -> bool:
        try:
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        except OSError:
            return False
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(fd, 0, 0)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # type: ignore[attr-defined]
        except OSError:
            os.close(fd)
            return False
        self.fd = fd
        return True

    def release(self) -> None:
        if self.fd is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(self.fd, 0, 0)
                msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
            else:
                import fcntl
                fcntl.flock(self.fd, fcntl.LOCK_UN)  # type: ignore[attr-defined]
        except OSError:
            pass
        os.close(self.fd)
        self.fd = None


def running(project: Any) -> bool:
    """True while a pet holds this project's lock."""
    probe = Lock(pet_files(project)["lock"])
    if not os.path.exists(probe.path):
        return False
    if probe.take():
        probe.release()
        return False
    return True


def remove(path: str) -> None:
    with contextlib.suppress(OSError):
        os.remove(path)


def read_pid(path: str) -> int | None:
    try:
        with open(path, encoding="utf-8") as handle:
            value = handle.read().split()
        return int(value[0]) if value and value[0].isdigit() else None
    except (OSError, ValueError):
        return None


def _terminate(pid: int) -> bool:
    """End the process that holds the lock (its own pid, from the pid file)."""
    try:
        if os.name == "nt":
            import ctypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
            handle = kernel.OpenProcess(0x0001, False, int(pid))            # PROCESS_TERMINATE
            if not handle:
                return False
            try:
                return bool(kernel.TerminateProcess(handle, 1))
            finally:
                kernel.CloseHandle(handle)
        import signal
        os.kill(int(pid), signal.SIGTERM)
        return True
    except (OSError, ValueError, AttributeError):
        return False


def stop_pet(project: Any, grace: float = 5.0) -> bool | None:
    """Close this project's pet: ask it (the stop file), then end it if it doesn't go. True when none is left."""
    files = pet_files(project)
    if not running(project):
        for name in ("pid", "stop"):
            remove(files[name])
        return None
    with open(files["stop"], "w", encoding="utf-8") as handle:
        handle.write("stop\n")
    deadline = time.time() + grace
    while time.time() < deadline and running(project):
        time.sleep(0.1)
    if running(project):
        pid = read_pid(files["pid"])
        if pid and _terminate(pid):
            deadline = time.time() + 3
            while time.time() < deadline and running(project):
                time.sleep(0.1)
    gone = not running(project)
    if gone:
        for name in ("pid", "stop"):
            remove(files[name])
    return gone


# --- starting it without holding up the caller ----------------------------------------------------------------
def gui_problem() -> str | None:
    """None when tkinter and a display are there; else one plain line saying what is missing."""
    try:
        import tkinter
    except Exception:  # noqa: BLE001 — ImportError, or a broken Tcl/Tk install
        return ("the pet needs Python's tkinter, which this Python ({}) doesn't have — council status gives "
                "the same reading as text".format(sys.version.split()[0]))
    try:
        root = tkinter.Tk()
    except Exception as exc:  # noqa: BLE001 — TclError: no display
        reason = (str(exc).strip().splitlines() or ["no display"])[0][:80]
        return "there is no screen to show the pet on ({}) — council status gives the same reading as text".format(
            reason)
    try:
        root.withdraw()
        root.destroy()
    except Exception:  # noqa: BLE001
        pass
    return None


def gui_python() -> str:
    """The Python to run the window with: pythonw beside this one on Windows (no console), else this one."""
    exe = sys.executable
    if os.name == "nt":
        folder, name = os.path.split(exe)
        for candidate in (re.sub(r"(?i)^python", "pythonw", name), "pythonw.exe"):
            path = os.path.join(folder, candidate)
            if candidate.lower().startswith("pythonw") and os.path.isfile(path):
                return path
    return exe


def launch(opts: argparse.Namespace, argv: list[str]) -> int:
    """Start the window as its own detached process and return once it shows (or fails)."""
    files = pet_files(opts.project)
    if running(opts.project):
        print("The pet is already on the desktop — right-click it and choose Close, or run: council pet --stop")
        return 0
    problem = gui_problem()
    if problem:
        print("council: " + problem, file=sys.stderr)
        return 1
    for name in ("pid", "stop", "error"):
        remove(files[name])
    words = [gui_python(), str(ENTRY), "pet"] + [w for w in argv if w != "--launch"]
    quiet = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
             "close_fds": True, "cwd": opts.project}
    try:
        if os.name == "nt":                        # its own process, out of the caller's job and console
            detached = 0x00000008 | 0x00000200     # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            try:
                child = subprocess.Popen(words, creationflags=detached | 0x01000000, **quiet)   # + BREAKAWAY_FROM_JOB
            except OSError:
                child = subprocess.Popen(words, creationflags=detached, **quiet)
        else:
            child = subprocess.Popen(words, start_new_session=True, **quiet)
    except OSError as exc:
        print("council: the pet could not start: {}".format(exc), file=sys.stderr)
        return 1
    return _shown(opts, files, child)


def _shown(opts: argparse.Namespace, files: dict[str, str], child: subprocess.Popen) -> int:
    """Wait for the window to show, then say so; else say why it did not."""
    deadline = time.time() + START_SECONDS
    while time.time() < deadline:
        if os.path.exists(files["pid"]) and running(opts.project):
            what = ("showing its five poses" if opts.demo else "showing the {} pose".format(opts.pose) if opts.pose
                    else "following this project's council run")
            closes = " It closes by itself after {:g} s.".format(opts.exit_after) if opts.exit_after else ""
            print("The pet is on the desktop, {} — right-click it and choose Close, or run: council pet --stop.{}"
                  .format(what, closes))
            return 0
        if child.poll() is not None:
            break
        time.sleep(0.1)
    reason = ""
    try:
        with open(files["error"], encoding="utf-8") as handle:
            reason = handle.read().strip().splitlines()[0][:160]
    except (OSError, IndexError):
        pass
    print("council: the pet could not start{}".format(": " + reason if reason else
                                                       " (it did not show within {} s)".format(START_SECONDS)),
          file=sys.stderr)
    return 1


def run_pet(opts: argparse.Namespace) -> int:
    from council.views import pet_window       # tkinter and the window code: only where a window opens
    files = pet_files(opts.project)
    lock = Lock(files["lock"])
    if not lock.take():
        return 0                                  # this project's pet is already on the desktop
    remove(files["stop"])
    try:
        follower = None if opts.demo or opts.pose else Follower(sys.executable, str(ENTRY), opts.home, opts.project,
                                                                 opts.session, opts.project)
        pet_window.show(opts, files, follower)
        return 0
    except Exception as exc:  # noqa: BLE001 — pythonw has nowhere to print; the launcher relays this line
        pet_window.note("failed: {!r}".format(exc))
        try:
            with open(files["error"], "w", encoding="utf-8") as handle:
                handle.write("{}\n".format(str(exc).strip().splitlines()[0][:160] if str(exc).strip()
                                           else type(exc).__name__))
        except OSError:
            pass
        return 1
    finally:
        if read_pid(files["pid"]) == os.getpid():
            remove(files["pid"])
        remove(files["stop"])
        lock.release()
        pet_window.note("closed")


# --- entry -----------------------------------------------------------------------------------------------------
class UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> Any:
        raise UsageError(message)


def parse_args(argv: list[str]) -> argparse.Namespace:
    """The options, checked; a UsageError says what is wrong in one line."""
    parser = _Parser(prog="council pet", add_help=False, allow_abbrev=False)
    for flag in ("--launch", "--stop", "--demo", "--still"):
        parser.add_argument(flag, action="store_true")
    for flag in ("--pose", "--exit-after", "--home"):
        parser.add_argument(flag)
    parser.add_argument("--project", default=os.getcwd())
    parser.add_argument("--session", default=os.environ.get("CLAUDE_CODE_SESSION_ID", ""))
    opts = parser.parse_args(argv)
    if opts.exit_after is not None:
        try:
            seconds = float(opts.exit_after)
        except ValueError:
            seconds = float("nan")
        if not 0 < seconds <= 86400:                 # NaN fails this too
            raise UsageError("--exit-after takes a number of seconds above 0 (at most a day), got: {}".format(
                opts.exit_after))
        opts.exit_after = seconds
    if opts.pose is not None and opts.pose not in POSES:
        raise UsageError("unknown pose '{}' — use asleep, working, needs-you, stopped or done".format(opts.pose))
    if opts.demo and opts.pose:
        raise UsageError("--demo cycles every pose; --pose shows one — not both")
    if opts.stop and (opts.demo or opts.pose or opts.still or opts.exit_after):
        raise UsageError("--stop closes the pet and takes no other option")
    opts.project = os.path.abspath(opts.project)
    opts.home = opts.home or os.path.join(opts.project, ".council")
    return opts


def main(argv: list[str]) -> int:
    try:
        opts = parse_args(list(argv))
    except UsageError as exc:
        print("council: pet: {}".format(exc), file=sys.stderr)
        return 2
    if opts.stop:
        closed = stop_pet(opts.project)
        if closed is None:
            print("No pet is open for this project.")
        elif closed:
            print("The pet is closed.")
        else:
            print("council: the pet did not close — right-click it and choose Close", file=sys.stderr)
            return 1
        return 0
    if opts.launch:
        return launch(opts, list(argv))
    return run_pet(opts)
