#!/usr/bin/env python3
"""The desktop pet: a small pumpkin-ghost that shows how this project's council run is going.

`council pet` starts it and returns at once. Right-click it and choose Close, or run
`council pet --stop`. It shows one of five poses, with a one-line bubble under it:
- asleep: no run is open (or the run is paused, stopped early, or has been quiet for an hour);
- working: the run is under way;
- needs you: the run waits for the user's answer, or a build stopped on a failing check;
- stopped: the run is stopped at its agent cap or token ceiling until the user says go;
- done: the run finished — for two minutes, then asleep again.

It only reads. About every five seconds it runs `council status --json` for the run it follows: the
in-progress run of the session that started it, else this working tree's. It never writes to a run.
Its only files are in the OS temp folder, keyed by the project path: a lock held while it runs, its
pid, and a stop request from `council pet --stop`.

It needs Python 3.8+ with tkinter, and a display. The shapes are the approved design's SVG paths on a
100 x 100 view box, sampled into polygons and lines for a tkinter canvas. `--demo` cycles the poses
without reading any run; `--pose <name>` shows one; `--still` turns the motion off.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cockpit  # noqa: E402  (the run files' safe readers, and the token display rule)

POSES = ("asleep", "working", "needs-you", "stopped", "done")
POLL_SECONDS = 5          # how often the run is read
DONE_SECONDS = 120        # how long a finished (or paused) run stays on show before the pet sleeps
START_SECONDS = 15        # how long `council pet` waits for the window to show

# The design's colours: a coral body with a cream outline and face, darker ribs, a green stem and leaf.
CORAL, CREAM, RIB, STEM, PUPIL = "#D85A30", "#FAECE7", "#993C1D", "#639922", "#4A1B0C"
LEAF, BLUE, WHITE, SOFT = "#97C459", "#378ADD", "#FFFFFF", "#888780"
AMBER, PURPLE, TEAL = "#EF9F27", "#7F77DD", "#1D9E75"
TONES = {"neutral": ("#F1EFE8", "#444441"), "accent": ("#E6F1FB", "#0C447C"),
         "warning": ("#FAEEDA", "#633806"), "success": ("#EAF3DE", "#27500A")}
PLAIN_BG = "#F1EFE8"      # where the window can't be see-through
KEY = "#898881"           # Windows' see-through colour: a grey next to the "z"s, so their soft edges stay grey
MOTION = {"asleep": "drift", "needs-you": "hop", "done": "hop"}

BODY = ("M20 84 V50 A30 30 0 0 1 80 50 V84 q-5 8 -10 0 q-5 8 -10 0 q-5 8 -10 0 q-5 8 -10 0 q-5 8 -10 0 "
        "q-5 8 -10 0 Z")
BASE = [
    ("path", "M50 21 q-3 -8 4 -13", {"stroke": STEM, "width": 4}),
    ("ellipse", (60, 11, 6, 3, -25), {"fill": LEAF}),
    ("path", BODY, {"fill": CORAL}),
    ("path", BODY, {"stroke": CREAM, "width": 2, "shrink": (50, 58, 0.86)}),
    ("path", "M30 34 Q24 58 29 82 M70 34 Q76 58 71 82", {"stroke": RIB, "width": 1.5}),
]


def _nose(y):
    return ("path", "M48 {0} L52 {0} L50 {1} Z".format(y, y + 3), {"fill": CREAM})


FACES = {
    "asleep": [("path", "M31 52 q7 5 14 0 M55 52 q7 5 14 0", {"stroke": CREAM, "width": 2.5}), _nose(60),
               ("path", "M42 70 q4 3 8 0 q4 -3 8 0", {"stroke": CREAM, "width": 2.5}),
               ("text", (80, 26, "z", 13, "start"), {"fill": SOFT}), ("text", (88, 16, "z", 11, "start"), {"fill": SOFT})],
    "working": [("path", "M31 49 h14 a7 7 0 0 1 -14 0 Z M55 49 h14 a7 7 0 0 1 -14 0 Z", {"fill": CREAM}), _nose(60),
                ("path", "M38 69 l4 4 l4 -4 l4 4 l4 -4 l4 4 l4 -4", {"stroke": CREAM, "width": 2.5})],
    "needs-you": [("circle", (38, 50, 7.5), {"fill": CREAM}), ("circle", (62, 50, 7.5), {"fill": CREAM}),
                  ("circle", (38, 50, 3.5), {"fill": PUPIL}), ("circle", (62, 50, 3.5), {"fill": PUPIL}), _nose(61),
                  ("ellipse", (50, 72, 3.5, 4.5, 0), {"fill": PUPIL, "stroke": CREAM, "width": 2}),
                  ("circle", (14, 18, 10), {"fill": BLUE}), ("text", (14, 23, "?", 14, "middle"), {"fill": WHITE, "bold": True})],
    "stopped": [("path", "M30 45 L46 52 Q44 60 37 60 Q29 58 30 45 Z M70 45 L54 52 Q56 60 63 60 Q71 58 70 45 Z",
                 {"fill": CREAM}), _nose(62),
                ("path", "M34 76 l5 -6 l5 6 l6 -8 l6 8 l5 -6 l5 6", {"stroke": CREAM, "width": 2.5})],
    "done": [("path", "M31 54 q7 -8 14 0 M55 54 q7 -8 14 0", {"stroke": CREAM, "width": 2.5}), _nose(59),
             ("path", "M30 66 l5 7 l5 -5 l5 7 l5 -7 l5 7 l5 -7 l5 5 l5 -7", {"stroke": CREAM, "width": 2.5}),
             ("circle", (12, 22, 3), {"fill": AMBER}), ("circle", (88, 18, 3), {"fill": PURPLE}),
             ("circle", (92, 40, 2.5), {"fill": AMBER}), ("circle", (8, 44, 2.5), {"fill": TEAL}),
             ("circle", (22, 8, 2), {"fill": PURPLE})],
}
DEMO = (("asleep", "No run open", "neutral"), ("working", "2 of 4 seats in · 132k", "neutral"),
        ("needs-you", "Approve the 3-seat plan?", "accent"), ("stopped", "10 of 10 agents used · your go?", "warning"),
        ("done", "Review done · 4 findings confirmed", "success"))


# --- the design's geometry, sampled -----------------------------------------------------------------------
NUMBER = r"[-+]?(?:[0-9]*\.[0-9]+|[0-9]+\.?)(?:[eE][-+]?[0-9]+)?"


def _quad(p0, p1, p2, steps=10):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])
            for t in (k / float(steps) for k in range(1, steps + 1))]


def _arc(p0, rx, ry, angle, large, sweep, p1, step=7.5):
    """An SVG arc (endpoint form) as points, by the SVG spec's centre conversion."""
    (x1, y1), (x2, y2) = p0, p1
    if rx == 0 or ry == 0 or (x1, y1) == (x2, y2):
        return [p1]
    phi = math.radians(angle)
    cos_p, sin_p = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2.0, (y1 - y2) / 2.0
    xp, yp = cos_p * dx + sin_p * dy, -sin_p * dx + cos_p * dy
    rx, ry = abs(rx), abs(ry)
    grow = (xp * xp) / (rx * rx) + (yp * yp) / (ry * ry)
    if grow > 1:
        rx, ry = rx * math.sqrt(grow), ry * math.sqrt(grow)
    top = rx * rx * ry * ry - rx * rx * yp * yp - ry * ry * xp * xp
    bottom = rx * rx * yp * yp + ry * ry * xp * xp
    coef = math.sqrt(max(0.0, top / bottom)) if bottom else 0.0
    if bool(large) == bool(sweep):
        coef = -coef
    cxp, cyp = coef * rx * yp / ry, -coef * ry * xp / rx
    cx = cos_p * cxp - sin_p * cyp + (x1 + x2) / 2.0
    cy = sin_p * cxp + cos_p * cyp + (y1 + y2) / 2.0

    def angle_of(ux, uy, vx, vy):
        return math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)

    start = angle_of(1, 0, (xp - cxp) / rx, (yp - cyp) / ry)
    turn = angle_of((xp - cxp) / rx, (yp - cyp) / ry, (-xp - cxp) / rx, (-yp - cyp) / ry)
    if not sweep and turn > 0:
        turn -= 2 * math.pi
    elif sweep and turn < 0:
        turn += 2 * math.pi
    steps = max(2, int(math.ceil(abs(math.degrees(turn)) / step)))
    points = []
    for k in range(1, steps + 1):
        t = start + turn * k / steps
        ex, ey = rx * math.cos(t), ry * math.sin(t)
        points.append((cos_p * ex - sin_p * ey + cx, sin_p * ex + cos_p * ey + cy))
    return points


def path_points(d):
    """SVG path data as [(points, closed)]: M L H V Q A Z and their relative forms, repeats included."""
    tokens = re.findall(r"[MmLlHhVvQqAaZz]|" + NUMBER, d)
    shapes, points = [], []
    x = y = sx = sy = 0.0
    i, command = 0, None

    def take(count):
        nonlocal i
        chunk = tokens[i:i + count]
        if len(chunk) != count or any(re.match(r"[A-Za-z]", v) for v in chunk):
            raise ValueError("path data ends early: " + d)
        i += count
        return [float(v) for v in chunk]

    while i < len(tokens):
        if re.match(r"[A-Za-z]", tokens[i]):
            command = tokens[i]
            i += 1
        elif command is None:
            raise ValueError("path data starts without a command: " + d)
        op, rel = command.upper(), command.islower()
        if op == "Z":
            if points:
                shapes.append((points, True))
            points, (x, y) = [], (sx, sy)
            continue
        if op != "M" and not points:
            points = [(x, y)]
        if op == "M":
            nx, ny = take(2)
            if rel:
                nx, ny = nx + x, ny + y
            if len(points) > 1:
                shapes.append((points, False))
            points, (x, y), (sx, sy) = [(nx, ny)], (nx, ny), (nx, ny)
            command = "l" if rel else "L"            # coordinates after a move are lines
        elif op == "L":
            nx, ny = take(2)
            x, y = (nx + x, ny + y) if rel else (nx, ny)
            points.append((x, y))
        elif op == "H":
            nx, = take(1)
            x = nx + x if rel else nx
            points.append((x, y))
        elif op == "V":
            ny, = take(1)
            y = ny + y if rel else ny
            points.append((x, y))
        elif op == "Q":
            cx, cy, nx, ny = take(4)
            if rel:
                cx, cy, nx, ny = cx + x, cy + y, nx + x, ny + y
            points.extend(_quad((x, y), (cx, cy), (nx, ny)))
            x, y = nx, ny
        elif op == "A":
            rx, ry, angle, large, sweep, nx, ny = take(7)
            if rel:
                nx, ny = nx + x, ny + y
            points.extend(_arc((x, y), rx, ry, angle, large, sweep, (nx, ny)))
            x, y = nx, ny
        else:
            raise ValueError("unsupported path command {}: {}".format(command, d))
    if len(points) > 1:
        shapes.append((points, False))
    return shapes


def _ellipse(cx, cy, rx, ry, angle, steps=28):
    a = math.radians(angle)
    return [(cx + rx * math.cos(t) * math.cos(a) - ry * math.sin(t) * math.sin(a),
             cy + rx * math.cos(t) * math.sin(a) + ry * math.sin(t) * math.cos(a))
            for t in (2 * math.pi * k / steps for k in range(steps))]


def shapes(pose):
    """A pose as drawing steps in view-box units, back to front:
    ("polygon", points, fill, outline, width) · ("line", points, colour, width) · ("oval", (cx, cy, r), fill) ·
    ("text", (x, y), text, size, colour, bold, anchor) — x, y the text's baseline, as in SVG."""
    steps = []
    for kind, spec, style in BASE + FACES[pose]:
        if kind == "path":
            cx, cy, k = style.get("shrink", (0, 0, 1.0))
            for points, closed in path_points(spec):
                points = [(cx + k * (px - cx), cy + k * (py - cy)) for px, py in points]
                if "fill" in style and closed:
                    steps.append(("polygon", points, style["fill"], None, 0))
                elif "stroke" in style:
                    width = style["width"] * k
                    steps.append(("polygon", points, None, style["stroke"], width) if closed
                                 else ("line", points, style["stroke"], width))
        elif kind == "ellipse":
            steps.append(("polygon", _ellipse(*spec), style["fill"], style.get("stroke"), style.get("width", 0)))
        elif kind == "circle":
            steps.append(("oval", spec, style["fill"]))
        elif kind == "text":
            x, y, text, size, anchor = spec
            steps.append(("text", (x, y), text, size, style["fill"], bool(style.get("bold")), anchor))
    return steps


# --- what the pet shows for a reading of `council status --json` ------------------------------------------
def short(text, limit=48):
    """One plain line: control marks and markup dropped, at most `limit` characters."""
    text = re.sub(r"\s+", " ", re.sub(r"[`*#<>\[\]]", "", cockpit.clean(text or ""))).strip()
    return text if len(text) <= limit else text[:limit - 1].rstrip(" ,;:·—-") + "…"


def _plural(n, one, many=None):
    return "{} {}".format(n, one if n == 1 else (many or one + "s"))


def view(reading):
    """(pose, bubble, tone) for one reading: {"kind": "none"} (no run to show), {"kind": "error", "note": …}
    or {"kind": "status", "status": <council status --json>}. Anything unreadable is a calm fallback."""
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


def _view(data):
    run, state, usage = data.get("run") or {}, data.get("state") or {}, data.get("usage") or {}
    status, key, limit = run.get("status") or "", state.get("key") or "", usage.get("limit") or {}
    if key == "completed" or status == "complete":
        counts = (data.get("closing") or {}).get("verdict_counts") or {}
        text = "{} done".format(run.get("mode_label") or "Run")
        if counts.get("confirmed"):
            text += " · {} confirmed".format(_plural(counts["confirmed"], "finding"))
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
            return ("stopped", "{} of {} tokens · your go?".format(cockpit.format_tokens(tokens),
                                                                   cockpit.format_tokens(ceiling)), "warning")
        return ("stopped", "At the limit · your go?", "warning")
    if key == "waiting":
        asked = next((a.get("text", "") for a in data.get("attention") or [] if a.get("kind") == "waiting"), "")
        asked = re.sub(r"^Waiting for your answer:\s*", "", asked)
        return ("needs-you", short(asked[:1].upper() + asked[1:]) if asked else "Waiting for your answer", "accent")
    if key == "blocked":
        return ("needs-you", "Build stopped · your decision?", "accent")
    if key == "stale":
        quiet = (data.get("freshness") or {}).get("quiet_minutes")
        return ("asleep", "Quiet for {}".format(_span(quiet)) if isinstance(quiet, int) else "Quiet for a while", "neutral")
    if key == "starting":
        return ("working", "Setting up the run", "neutral")
    if key == "recovering":
        return ("working", "Fixing a failed check", "neutral")
    if key == "failing":
        return ("working", "A check failed", "neutral")
    progress = data.get("progress") or {}
    done = (progress.get("counts") or {}).get("done", 0)
    total = len(data.get("seats") or []) + (progress.get("planned") or 0)
    tokens = usage.get("tokens_known") or 0
    text = "{} of {} seats in".format(done, total) if total else (run.get("phase_label") or "Working")
    if tokens:
        text += " · " + cockpit.format_tokens(tokens)
    return ("working", short(text), "neutral")


def _span(minutes):
    if minutes < 60:
        return "{} min".format(max(1, minutes))
    hours, rest = divmod(minutes, 60)
    if hours < 48:
        return "{} h {} min".format(hours, rest) if rest else "{} h".format(hours)
    return "{} days".format(hours // 24)


# --- which run to follow -----------------------------------------------------------------------------------
def same_path(a, b):
    try:
        return os.path.normcase(os.path.normpath(str(a))) == os.path.normcase(os.path.normpath(str(b)))
    except (TypeError, ValueError):
        return False


def open_runs(home):
    """In-progress runs under the council home, newest first: (folder, code-root, session), read from
    each run's session-state header the way the helper reads it."""
    runs, rows = Path(home) / "runs", []
    try:
        names = sorted(os.listdir(str(runs)), reverse=True)
    except OSError:
        return rows
    for name in names:
        fields = cockpit.header(runs / name)
        if fields.get("status", "").split(" ")[0] == "in-progress":
            rows.append((runs / name, fields.get("code-root", ""), fields.get("session", "")))
    return rows


def pick(rows, tree, session):
    """The run to show: this session's, else one on this working tree that recorded no session, else any
    on this working tree — the newest of each. None when there is none."""
    def here(root):
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
    """The run the pet follows, and its reading. It asks the helper — `council status --json --run
    <folder>`, which only reads — and keeps a finished run on show for DONE_SECONDS."""

    def __init__(self, bash, council, home, tree, session, cwd):
        self.bash, self.council, self.home, self.tree = bash, council, home, tree
        self.session, self.cwd = session, cwd
        self.last, self.ended = None, None

    def helper(self, *words):
        env = dict(os.environ)
        env.pop("COUNCIL_RUN", None)
        extra = {}
        if os.name == "nt":                      # no console window flashes up on every reading
            info = subprocess.STARTUPINFO()
            info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            info.wShowWindow = 0
            extra = {"creationflags": 0x08000000, "startupinfo": info}      # CREATE_NO_WINDOW
        done = subprocess.run([self.bash, self.council] + list(words), cwd=self.cwd, env=env,
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=45, **extra)
        return done.returncode, done.stdout.decode("utf-8", "replace"), done.stderr.decode("utf-8", "replace")

    def read(self, now=None):
        now = time.time() if now is None else now
        folder = pick(open_runs(self.home), self.tree, self.session)
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
            code, out, err = self.helper("status", "--json", "--run", Path(self.last).as_posix())
            data = json.loads(out) if code == 0 else None
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            code, data, err = -1, None, str(exc)
        if not isinstance(data, dict):
            return {"kind": "error", "note": "Can't read the run right now", "detail": (err or "").strip()[-300:]}
        return {"kind": "status", "status": data}


# --- one pet per project: files in the OS temp folder -------------------------------------------------------
def pet_files(project):
    key = hashlib.sha256(os.path.normcase(os.path.abspath(str(project))).encode("utf-8", "replace")).hexdigest()[:16]
    base = os.path.join(tempfile.gettempdir(), "small-council-pet-" + key)
    return {"lock": base + ".lock", "pid": base + ".pid", "stop": base + ".stop", "error": base + ".err"}


class Lock:
    """An exclusive lock on a file, held while a pet runs; the OS drops it when the process ends."""

    def __init__(self, path):
        self.path, self.fd = path, None

    def take(self):
        try:
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        except OSError:
            return False
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(fd, 0, 0)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return False
        self.fd = fd
        return True

    def release(self):
        if self.fd is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(self.fd, 0, 0)
                msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(self.fd)
        self.fd = None


def running(project):
    """True while a pet holds this project's lock."""
    probe = Lock(pet_files(project)["lock"])
    if not os.path.exists(probe.path):
        return False
    if probe.take():
        probe.release()
        return False
    return True


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _read_pid(path):
    try:
        with open(path, encoding="utf-8") as handle:
            value = handle.read().split()
        return int(value[0]) if value and value[0].isdigit() else None
    except (OSError, ValueError):
        return None


def _terminate(pid):
    """End the process that holds the lock (its own pid, from the pid file)."""
    try:
        if os.name == "nt":
            import ctypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
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


def stop_pet(project, grace=5.0):
    """Close this project's pet: ask it (the stop file), then end it if it doesn't go. True when none is left."""
    files = pet_files(project)
    if not running(project):
        for name in ("pid", "stop"):
            _remove(files[name])
        return None
    with open(files["stop"], "w", encoding="utf-8") as handle:
        handle.write("stop\n")
    deadline = time.time() + grace
    while time.time() < deadline and running(project):
        time.sleep(0.1)
    if running(project):
        pid = _read_pid(files["pid"])
        if pid and _terminate(pid):
            deadline = time.time() + 3
            while time.time() < deadline and running(project):
                time.sleep(0.1)
    gone = not running(project)
    if gone:
        for name in ("pid", "stop"):
            _remove(files[name])
    return gone


# --- starting it without holding up the caller ----------------------------------------------------------------
def gui_problem():
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
        return "there is no screen to show the pet on ({}) — council status gives the same reading as text".format(reason)
    try:
        root.withdraw()
        root.destroy()
    except Exception:  # noqa: BLE001
        pass
    return None


def gui_python():
    """The Python to run the window with: pythonw beside this one on Windows (no console), else this one."""
    exe = sys.executable
    if os.name == "nt":
        folder, name = os.path.split(exe)
        for candidate in (re.sub(r"(?i)^python", "pythonw", name), "pythonw.exe"):
            path = os.path.join(folder, candidate)
            if candidate.lower().startswith("pythonw") and os.path.isfile(path):
                return path
    return exe


def launch(opts, argv):
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
        _remove(files[name])
    words = [gui_python(), str(HERE / "pet.py")] + [w for w in argv if w != "--launch"]
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
    deadline = time.time() + START_SECONDS
    while time.time() < deadline:
        if os.path.exists(files["pid"]) and running(opts.project):
            what = ("showing its five poses" if opts.demo else "showing the {} pose".format(opts.pose) if opts.pose
                    else "following this project's council run")
            closes = " It closes by itself after {:g} s.".format(opts.exit_after) if opts.exit_after else ""
            print("The pet is on the desktop, {} — right-click it and choose Close, or run: council pet --stop.{}".format(
                what, closes))
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


# --- the window ------------------------------------------------------------------------------------------------
def _note(message):
    """A line in the file COUNCIL_PET_LOG names, when set (for checking a real window without looking)."""
    path = os.environ.get("COUNCIL_PET_LOG")
    if path:
        try:
            with open(path, "a", encoding="utf-8") as handle:
                handle.write("{} {}\n".format(time.strftime("%H:%M:%S"), message))
        except OSError:
            pass


def show(opts, files):
    import tkinter as tk
    from tkinter import font as tkfont

    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)           # crisp on a scaled screen
        except Exception:  # noqa: BLE001
            pass
    root = tk.Tk()
    root.withdraw()
    root.title("Small Council pet")
    root.overrideredirect(True)
    root.report_callback_exception = lambda *exc: _note("callback error: {}".format(exc[1]))
    try:
        root.wm_attributes("-topmost", True)
    except tk.TclError:
        pass
    background = PLAIN_BG
    if os.name == "nt":
        try:
            root.wm_attributes("-transparentcolor", KEY)
            background = KEY
        except tk.TclError:
            pass
    elif sys.platform == "darwin":
        try:
            root.wm_attributes("-transparent", True)
            background = "systemTransparent"
        except tk.TclError:
            pass
    root.configure(bg=background)
    ratio = max(1.0, root.winfo_fpixels("1i") / 96.0)
    family = tkfont.nametofont("TkDefaultFont").actual("family")
    scale = 1.12 * ratio                      # view-box units to pixels: a 112-pixel pet
    width = int(round(240 * ratio))
    top = 8 * scale                           # room for a hop
    left = (width - 100 * scale) / 2.0
    bubble_font = tkfont.Font(root=root, family=family, size=-int(round(12 * ratio)))
    pad_x, pad_y = 8 * ratio, 4 * ratio
    bubble_top = top + 95 * scale
    height = int(round(bubble_top + bubble_font.metrics("linespace") + 2 * pad_y + 4 * ratio))
    canvas = tk.Canvas(root, width=width, height=height, bg=background, highlightthickness=0, bd=0)
    canvas.pack()
    x = root.winfo_screenwidth() - width - int(24 * ratio)
    y = root.winfo_screenheight() - height - int(72 * ratio)
    root.geometry("{}x{}+{}+{}".format(width, height, x, y))
    fonts = {}

    def at(px, py):
        return left + px * scale, top + py * scale

    def flat(points):
        return [c for p in points for c in at(*p)]

    def text_font(size, bold):
        if (size, bold) not in fonts:
            fonts[(size, bold)] = tkfont.Font(root=root, family=family, size=-max(6, int(round(size * scale))),
                                              weight="bold" if bold else "normal")
        return fonts[(size, bold)]

    def draw_pet(pose):
        canvas.delete("pet")
        for step in shapes(pose):
            if step[0] == "polygon":
                _, points, fill, outline, line = step
                canvas.create_polygon(flat(points), fill=fill or "", outline=outline or "",
                                      width=line * scale if outline else 0, joinstyle="round", tags="pet")
            elif step[0] == "line":
                _, points, colour, line = step
                canvas.create_line(flat(points), fill=colour, width=line * scale, capstyle="round",
                                   joinstyle="round", tags="pet")
            elif step[0] == "oval":
                (cx, cy, r), fill = step[1], step[2]
                x0, y0 = at(cx - r, cy - r)
                x1, y1 = at(cx + r, cy + r)
                canvas.create_oval(x0, y0, x1, y1, fill=fill, outline="", tags="pet")
            elif step[0] == "text":
                _, (tx, ty), word, size, colour, bold, anchor = step
                face = text_font(size, bold)
                px, py = at(tx, ty)
                canvas.create_text(px, py + face.metrics("descent"), text=word, fill=colour, font=face,
                                   anchor="s" if anchor == "middle" else "sw", tags="pet")

    def fit(text, room):
        if bubble_font.measure(text) <= room:
            return text
        while text and bubble_font.measure(text + "…") > room:
            text = text[:-1]
        return text.rstrip() + "…"

    def draw_bubble(text, tone):
        canvas.delete("bubble")
        fill, ink = TONES.get(tone, TONES["neutral"])
        text = fit(text, width - 2 * pad_x - 4 * ratio)
        w, h = bubble_font.measure(text) + 2 * pad_x, bubble_font.metrics("linespace") + 2 * pad_y
        x0, y0, r = (width - w) / 2.0, bubble_top, 6 * ratio
        x1, y1 = x0 + w, y0 + h
        canvas.create_polygon([x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
                               x0, y1, x0, y1 - r, x0, y0 + r, x0, y0], smooth=True, fill=fill, outline="#D3D1C7",
                              tags="bubble")
        canvas.create_text(width / 2.0, y0 + h / 2.0, text=text, fill=ink, font=bubble_font, tags="bubble")

    shown = {"pose": None, "bubble": None, "since": time.time(), "dy": 0.0}

    def put(pose, bubble, tone):
        if pose != shown["pose"]:
            shown.update(pose=pose, since=time.time(), dy=0.0)
            draw_pet(pose)
            _note("pose " + pose)
        if (bubble, tone) != shown["bubble"]:
            shown["bubble"] = (bubble, tone)
            draw_bubble(bubble, tone)

    closing = threading.Event()

    def close(*_):
        if not closing.is_set():
            closing.set()
            _note("closing")
            root.destroy()

    def animate():
        if closing.is_set():
            return
        motion, t = MOTION.get(shown["pose"]), time.time() - shown["since"]
        dy = 0.0
        if motion == "hop":
            dy = -6 * scale * (1 - math.cos(2 * math.pi * t / 1.1)) / 2
        elif motion == "drift":
            dy = 3 * scale * (1 - math.cos(2 * math.pi * t / 3.0)) / 2
        if abs(dy - shown["dy"]) >= 0.25:
            canvas.move("pet", 0, dy - shown["dy"])
            shown["dy"] = dy
        root.after(40, animate)

    latest, guard = {"reading": None, "seq": 0}, threading.Lock()
    follower = None
    if not opts.demo and not opts.pose:
        follower = Follower(opts.bash, opts.council, opts.home, opts.project, opts.session, opts.project)

        def watch():
            while not closing.is_set():
                try:
                    reading = follower.read()
                except Exception as exc:  # noqa: BLE001 — a reading must never take the window down
                    reading = {"kind": "error", "note": "Can't read the run right now", "detail": str(exc)}
                if reading.get("detail"):
                    _note("reading: " + reading["detail"].replace("\n", " ")[:300])
                with guard:
                    latest["reading"], latest["seq"] = reading, latest["seq"] + 1
                closing.wait(POLL_SECONDS)

        threading.Thread(target=watch, daemon=True).start()
    seen = {"seq": 0}
    started = time.time()

    def tick():
        if closing.is_set():
            return
        if os.path.exists(files["stop"]):
            _remove(files["stop"])
            close()
            return
        if opts.demo:
            put(*DEMO[int((time.time() - started) / 2.0) % len(DEMO)])
        elif follower is not None:
            with guard:
                seq, reading = latest["seq"], latest["reading"]
            if seq != seen["seq"]:
                seen["seq"] = seq
                put(*view(reading))
        root.after(250, tick)

    if opts.pose:
        put(*next(d for d in DEMO if d[0] == opts.pose))
    elif opts.demo:
        put(*DEMO[0])
    else:
        put("asleep", "Looking for the council run…", "neutral")
    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label="Close", command=close)

    def popup(event):
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    grab = {}

    def press(event):
        grab["dx"], grab["dy"] = event.x_root - root.winfo_x(), event.y_root - root.winfo_y()

    def drag(event):
        root.geometry("+{}+{}".format(event.x_root - grab.get("dx", 0), event.y_root - grab.get("dy", 0)))

    canvas.bind("<ButtonPress-1>", press)
    canvas.bind("<B1-Motion>", drag)
    canvas.bind("<Button-3>", popup)
    if sys.platform == "darwin":
        canvas.bind("<Button-2>", popup)
        canvas.bind("<Control-Button-1>", popup)
    root.deiconify()
    root.update()
    with open(files["pid"], "w", encoding="utf-8") as handle:
        handle.write("{}\n".format(os.getpid()))
    _note("shown {}x{}+{}+{} viewable={} pid={}".format(width, height, x, y, root.winfo_viewable(), os.getpid()))
    if opts.exit_after:
        root.after(int(opts.exit_after * 1000), close)
    if not opts.still:
        root.after(40, animate)
    root.after(250, tick)
    root.mainloop()
    closing.set()


def run_pet(opts):
    files = pet_files(opts.project)
    lock = Lock(files["lock"])
    if not lock.take():
        return 0                                  # this project's pet is already on the desktop
    _remove(files["stop"])
    try:
        show(opts, files)
        return 0
    except Exception as exc:  # noqa: BLE001 — pythonw has nowhere to print; the launcher relays this line
        _note("failed: {!r}".format(exc))
        try:
            with open(files["error"], "w", encoding="utf-8") as handle:
                handle.write("{}\n".format(str(exc).strip().splitlines()[0][:160] if str(exc).strip() else type(exc).__name__))
        except OSError:
            pass
        return 1
    finally:
        if _read_pid(files["pid"]) == os.getpid():
            _remove(files["pid"])
        _remove(files["stop"])
        lock.release()
        _note("closed")


# --- entry -----------------------------------------------------------------------------------------------------
class UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


def parse_args(argv):
    """The options, checked; a UsageError says what is wrong in one line."""
    parser = _Parser(prog="council pet", add_help=False, allow_abbrev=False)
    parser.add_argument("--launch", action="store_true")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--pose")
    parser.add_argument("--still", action="store_true")
    parser.add_argument("--exit-after")
    parser.add_argument("--project", default=os.getcwd())
    parser.add_argument("--home")
    parser.add_argument("--council", default=str(HERE.parent / "bin" / "council"))
    parser.add_argument("--bash", default="bash")
    parser.add_argument("--session", default=os.environ.get("CLAUDE_CODE_SESSION_ID", ""))
    opts = parser.parse_args(argv)
    if opts.exit_after is not None:
        try:
            seconds = float(opts.exit_after)
        except ValueError:
            seconds = float("nan")
        if not 0 < seconds <= 86400:                 # NaN fails this too
            raise UsageError("--exit-after takes a number of seconds above 0 (at most a day), got: {}".format(opts.exit_after))
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


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        opts = parse_args(argv)
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
        return launch(opts, argv)
    return run_pet(opts)


if __name__ == "__main__":
    sys.exit(main())
