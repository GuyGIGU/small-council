#!/usr/bin/env python3
"""A thin, read-only terminal cockpit for one council run.

It reads what the run already records and draws one screen. The run's files are:
- session-state.md, run-plan.tsv and seats.tsv;
- events.tsv and gates/*.json;
- repairs.jsonl and claims.jsonl.
It also reads the memory proposals waiting in the council home. It never writes a file, appends an
event or changes a run, so it can be closed at any time. On Windows each file is opened with delete
sharing, so a helper that replaces a file by rename while the cockpit reads it is never refused.
Every value is stripped of control characters before it is drawn, and a file that is a link, leads
outside the run, is too large or does not parse is skipped rather than followed or trusted.
`--watch` redraws every two seconds until the run has read as closed twice in a row. `--json` prints
the same snapshot as data (`council.run-snapshot/1`) for other tools. Every fact on screen comes from
a file the helper or the Chair already writes; the cockpit adds no state of its own.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCHEMA = "council.run-snapshot/1"
MAX_FILE = 4 * 1024 * 1024
BOM = chr(0xFEFF)
UNICODE = {"done": "✓", "running": "●", "queued": "○", "failed": "✗", "blocked": "■", "skipped": "–",
           "pass": "✓", "fail": "✗", "unknown": "?", "top": "┌", "bottom": "└", "rule": "─"}
ASCII = {"done": "+", "running": "*", "queued": "o", "failed": "x", "blocked": "!", "skipped": "-",
         "pass": "+", "fail": "x", "unknown": "?", "top": "+", "bottom": "+", "rule": "-"}
# Every C0 and C1 control (tab and newline included: a value is one cell), DEL, and the Unicode line
# and paragraph separators: none may reach the terminal from a file.
CONTROL = re.compile("[" + chr(0) + "-" + chr(0x1F) + chr(0x7F) + "-" + chr(0x9F) + chr(0x2028) + chr(0x2029) + "]")
PLAIN = {"·": "|", "—": "-", "–": "-", "…": "...", "→": "->", "’": "'", "“": '"', "”": '"'}


# --- reading without getting in a live run's way ----------------------------------------------------------
def linked(path):
    """True when path itself is a symlink or a Windows junction (its parent may be linked; that is fine)."""
    path = Path(path)
    try:
        return path.is_symlink() or os.path.realpath(str(path)) != os.path.join(os.path.realpath(str(path.parent)), path.name)
    except (OSError, ValueError):
        return True


def contained(path, root):
    """True when path, links and junctions resolved, stays inside root, also resolved."""
    try:
        real, base = os.path.realpath(str(path)), os.path.realpath(str(root))
    except (OSError, ValueError):
        return False
    return real == base or real.startswith(base.rstrip("\\/") + os.sep)


def open_shared(path):
    """On Windows, the file opened with read, write and delete sharing — so the helper's rename of a
    file the cockpit is reading still succeeds. None where that is not available."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        import msvcrt
        from ctypes import wintypes
    except ImportError:
        return None
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.restype = wintypes.HANDLE
    create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    # GENERIC_READ; FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE; OPEN_EXISTING; FILE_ATTRIBUTE_NORMAL
    handle = create(str(path), 0x80000000, 0x7, None, 3, 0x80, None)
    if handle is None or handle == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(), "cannot open", str(path))
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    except OSError:
        kernel.CloseHandle(wintypes.HANDLE(handle))
        raise
    return os.fdopen(descriptor, "rb")


def read_bytes(path, limit):
    handle = open_shared(path) or open(str(path), "rb")
    with handle:
        return handle.read(limit + 1)


def text_of(path, root=None, limit=MAX_FILE):
    """A small regular file's text, or '' when it is missing, a link, outside root, too large or unreadable."""
    path = Path(path)
    try:
        if linked(path) or not path.is_file() or (root is not None and not contained(path, root)):
            return ""
        data = read_bytes(path, limit)
    except OSError:
        return ""
    if len(data) > limit:
        return ""
    return data.decode("utf-8", errors="replace").lstrip(BOM)


def too_large(path, limit=MAX_FILE):
    try:
        return Path(path).is_file() and Path(path).stat().st_size > limit
    except OSError:
        return False


def clean(value):
    return re.sub(r" {2,}", " ", CONTROL.sub(" ", str(value))).strip()


def integer(value):
    """An int from an int or a string of digits, else None — never a list, a bool or a null."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if abs(value) < 10 ** 12 else None
    if isinstance(value, str) and re.fullmatch(r"-?[0-9]{1,12}", value.strip()):
        return int(value.strip())
    return None


def parse_json(text):
    try:
        return json.loads(text)
    except (ValueError, RecursionError):
        return None


# --- the run's files ------------------------------------------------------------------------------------------
def header(run):
    """The key: value lines of session-state.md, above its first heading."""
    fields = {}
    for line in text_of(run / "session-state.md", run).splitlines():
        if line.startswith("## "):
            break
        key, sep, value = line.partition(":")
        if sep and re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*", key.strip()):
            fields[key.strip()] = clean(value)
    return fields


def tsv(run, name):
    lines = [line.rstrip("\r") for line in text_of(run / name, run).splitlines() if line.strip() and not line.startswith("#")]
    if not lines:
        return []
    keys = lines[0].split("\t")
    return [dict(zip(keys, line.split("\t"))) for line in lines[1:]]


def jsonl(run, name):
    rows = []
    for line in text_of(run / name, run).splitlines():
        row = parse_json(line)
        if isinstance(row, dict):
            rows.append(row)
    return rows


def number(value):
    value = str(value or "").strip()
    return int(value) if re.fullmatch(r"[0-9]{1,12}", value) else 0


def plan_of(run):
    plan, seats = {}, {}
    for line in text_of(run / "run-plan.tsv", run).splitlines():
        cells = line.rstrip("\r").split("\t")
        if not line.strip() or line.startswith("#") or len(cells) < 5 or cells[0] == "kind":
            continue
        kind, ident, field, value, reason = (clean(c) for c in cells[:5])
        if kind == "seat":
            seats.setdefault(ident, {})[field] = value
            if field == "disposition":
                seats[ident]["reason"] = reason
        elif kind == "context":
            seats.setdefault(ident, {})["context"] = value
        elif ident in ("run", "plan"):
            plan[field] = value
    plan["seats"] = seats
    return plan


def gates_of(run):
    gates = []
    folder = run / "gates"
    if not folder.is_dir() or linked(folder):
        return gates
    for path in sorted(folder.glob("*.json")):
        data = parse_json(text_of(path, run) or "{}")
        if isinstance(data, dict) and "exit" in data:
            gates.append({"name": clean(data.get("gate", path.stem)) or path.stem, "exit": integer(data.get("exit")),
                          "seconds": integer(data.get("seconds")) or 0, "when": clean(data.get("when", "")),
                          "command": clean(data.get("command", ""))[:200], "note": clean(data.get("note", ""))})
    return sorted(gates, key=lambda g: g["when"])


def repairs_of(run):
    tasks = {}
    for row in jsonl(run, "repairs.jsonl"):
        task = clean(row.get("task", "?")) or "?"
        tasks[task] = {"gate": clean(row.get("gate", "")), "attempts": integer(row.get("attempt")),
                       "result": clean(row.get("result", "")), "category": clean(row.get("category", "")),
                       "next": clean(row.get("action", ""))}
    return tasks


def claims_of(run):
    rows = jsonl(run, "claims.jsonl")
    verdicts = {}
    for row in rows:
        verdict = clean(row.get("verdict") or "UNVERIFIED").upper()[:24] or "UNVERIFIED"
        verdicts[verdict] = verdicts.get(verdict, 0) + 1
    return {"total": len(rows), "by_verdict": dict(sorted(verdicts.items()))}


def events_of(run, last):
    path = run / "events.tsv"
    if too_large(path):
        return {"count": None, "malformed": 0, "last": [], "present": True, "header_ok": None, "too_large": True}
    lines = [line.rstrip("\r") for line in text_of(path, run).splitlines() if line.strip()]
    rows = [line.split("\t") for line in lines[1:]]
    good = [r for r in rows if len(r) == 7]
    shown = [{"seq": clean(r[1]), "at": clean(r[2]), "type": clean(r[3]), "subject": clean(r[4]),
              "value": clean(r[5]), "detail": clean(r[6])} for r in good[-last:]] if last else []
    return {"count": len(good), "malformed": len(rows) - len(good), "last": shown, "present": bool(lines),
            "header_ok": bool(lines) and lines[0] == "schema\tseq\tat\ttype\tsubject\tvalue\tdetail", "too_large": False}


def proposals_in(home):
    """How many entries wait under memory's ## Proposed section (### headings or - PROPOSED lines)."""
    if not home:
        return None
    text = text_of(Path(home) / "conventions.md", home)
    if not text:
        return None
    count, inside = 0, False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip().lower().startswith("propos")
        elif inside and (line.startswith("### ") or re.match(r"\s*-\s+PROPOSED\b", line)):
            count += 1
    return count


def snapshot(run, home=None, last_events=8):
    run = Path(run)
    state = header(run)
    seats = []
    for row in tsv(run, "seats.tsv"):
        slug = clean(row.get("slug", ""))
        if not slug:
            continue
        seats.append({"slug": slug, "state": clean(row.get("state", "")), "agent": clean(row.get("agent", "")),
                      "tokens": number(row.get("tokens")), "updated": clean(row.get("updated", "")),
                      "note": clean(row.get("note", ""))[:120], "agents": number(row.get("agents")) or 1})
    active = [s for s in seats if s["state"] not in ("queued", "skipped")]
    verifier = [s for s in active if s["slug"].startswith(("verify-", "diagnose-"))]
    return {
        "schema": SCHEMA,
        "run": {"id": clean(run.name), "path": str(run), **{k: state.get(k, "") for k in (
            "status", "mode", "phase", "updated", "opened", "closed", "size", "ask", "deliverable", "next", "actual")}},
        "plan": plan_of(run),
        "seats": seats,
        "tokens": {"workers": sum(s["tokens"] for s in active if s not in verifier),
                   "verifiers": sum(s["tokens"] for s in verifier), "total": sum(s["tokens"] for s in active)},
        "agents": sum(s["agents"] for s in active),
        "gates": gates_of(run),
        "repairs": repairs_of(run),
        "claims": claims_of(run),
        "events": events_of(run, last_events),
        "memory": {"proposed": proposals_in(home)},
    }


# --- drawing --------------------------------------------------------------------------------------------------
def k(tokens):
    return "{}k".format(round(tokens / 1000)) if tokens else "—"


def shown(value):
    return "?" if value is None else str(value)


def render(snap, ascii_only=False, width=None):
    g = ASCII if ascii_only else UNICODE
    width = max(60, min(width or shutil.get_terminal_size((100, 30)).columns, 120))
    run, plan = snap["run"], snap["plan"]
    lines = []

    def add(text=""):
        text = CONTROL.sub(" ", text)            # nothing from a file can move the cursor or retitle the window
        lines.append(text if len(text) <= width else text[:width - 1] + ("~" if ascii_only else "…"))

    title = " Small Council — {} ".format(run["id"])
    add(g["top"] + g["rule"] + title + g["rule"] * max(0, width - len(title) - 2))
    add("  {} · phase {} · {} · updated {}".format(run["mode"] or "?", run["phase"] or "?", run["status"] or "?",
                                                   run["updated"] or "?"))
    if run["ask"]:
        add("  Request: " + run["ask"])
    if plan.get("size"):
        add("  Plan: {} · risk {} · complexity {} · uncertainty {} · verification {}".format(
            plan.get("size", "?"), plan.get("risk", "?"), plan.get("complexity", "?"), plan.get("uncertainty", "?"),
            plan.get("level", "?")))
    budget = "  Budget: estimated {} · spent {} (workers {}, verifiers {}) · {} agent(s)".format(
        k(number(plan.get("estimated-tokens"))), k(snap["tokens"]["total"]), k(snap["tokens"]["workers"]),
        k(snap["tokens"]["verifiers"]), snap["agents"])
    if plan.get("agent-cap"):
        budget += " of {}".format(plan["agent-cap"])
    add(budget)
    if run["next"] and run["status"] == "in-progress":
        add("  Next: " + run["next"])
    add()
    add(" Seats")
    planned = plan.get("seats", {})
    drawn = set()
    for seat in snap["seats"]:
        drawn.add(seat["slug"])
        info = planned.get(seat["slug"], {})
        add("  {} {:<16} {:<8} {:>6}  {:<8} {}".format(g.get(seat["state"], "?"), seat["slug"][:16], seat["state"][:8],
                                                     k(seat["tokens"]), info.get("role", "")[:8], info.get("context", "")))
    for slug, info in sorted(planned.items()):
        if slug in drawn or info.get("disposition") not in ("selected", "skipped"):
            continue
        if info["disposition"] == "skipped":
            add("  {} {:<16} skipped  — {}".format(g["skipped"], slug[:16], info.get("reason", "")))
        else:
            add("  {} {:<16} planned  {:>6}  {:<8} {}".format(g["queued"], slug[:16], "", info.get("role", "")[:8],
                                                            info.get("context", "")))
    if not snap["seats"] and not planned:
        add("  none recorded yet")
    if snap["gates"]:
        add()
        add(" Gates")
        for gate in snap["gates"]:
            mark = g["unknown"] if gate["exit"] is None else (g["pass"] if gate["exit"] == 0 else g["fail"])
            add("  {} {:<16} exit {:<4} {:>4}s  {}{}".format(mark, gate["name"][:16], shown(gate["exit"]),
                                                           gate["seconds"], gate["when"][-8:],
                                                           "  " + gate["note"] if gate["note"] else ""))
    if snap["repairs"]:
        add()
        add(" Repairs")
        for task, info in sorted(snap["repairs"].items()):
            add("  {} {}: attempt {} {} · {} · next {}".format(task, info["gate"], shown(info["attempts"]), info["result"],
                                                             info["category"] or "-", info["next"] or "-"))
    if snap["claims"]["total"]:
        add()
        add(" Evidence")
        add("  {} claim(s) · ".format(snap["claims"]["total"])
            + " · ".join("{} {}".format(n, v) for v, n in snap["claims"]["by_verdict"].items()))
    if snap["memory"]["proposed"]:
        add()
        add(" Memory")
        add("  {} proposal(s) wait for the user's yes or no".format(snap["memory"]["proposed"]))
    events = snap["events"]
    add()
    if events.get("too_large"):
        add(" Timeline: events.tsv is over 4 MB and was not read — council run events check --run <folder>")
    elif not events["present"]:
        add(" Timeline: no events.tsv (a run from before the event stream)")
    else:
        add(" Timeline ({} event(s){})".format(events["count"],
                                               ", {} malformed".format(events["malformed"]) if events["malformed"] else ""))
        for e in events["last"]:
            add("  {} {:<20} {:<12} {}".format(local_time(e["at"]), e["type"][:20], e["subject"][:12], e["value"]))
    add(g["bottom"] + g["rule"] * (width - 1))
    out = "\n".join(lines)
    if ascii_only:
        out = "".join(PLAIN.get(ch, ch if ord(ch) < 128 else "?") for ch in out)
    return out


def local_time(stamp):
    """An event's UTC time as local HH:MM:SS, so it reads like the gates' local times."""
    try:
        moment = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return moment.astimezone().strftime("%H:%M:%S")
    except (ValueError, OverflowError, OSError):
        return stamp[11:19]


def ascii_needed():
    """Plain ASCII on request (COUNCIL_ASCII=1), for a console that shows UTF-8 as mojibake."""
    return os.environ.get("COUNCIL_ASCII", "") not in ("", "0")


def enable_vt():
    """Ask a Windows console to honour ANSI escapes; harmless where they already work."""
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel = ctypes.windll.kernel32
        handle = kernel.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel.SetConsoleMode(handle, mode.value | 0x0004)
    except (AttributeError, OSError, ValueError):
        pass


def watch(run, home, events, ascii_only, interval):
    """Redraw until the run reads as closed twice in a row. A state file that is briefly missing or
    empty (a helper replacing it) is read again, never taken for a closed run; one gone for ten polls
    ends the watch with an error."""
    interactive = sys.stdout.isatty()
    if interactive:
        enable_vt()
    last, closed, missing = None, 0, 0
    while True:
        snap = snapshot(run, home, events)
        status = snap["run"]["status"]
        frame = render(snap, ascii_only)
        sys.stdout.write(("\x1b[2J\x1b[H" if interactive else "") + frame + "\n")
        sys.stdout.flush()
        if not status:
            missing += 1
            closed = 0
            if missing >= 10:
                print("tui: the run's session-state.md has been unreadable for {} polls — stopping".format(missing),
                      file=sys.stderr)
                return 1
        else:
            missing = 0
            closed = closed + 1 if status != "in-progress" and status == last else (1 if status != "in-progress" else 0)
            if closed >= 2:
                print("the run is {} — nothing more will change here".format(status))
                return 0
        last = status
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--home", type=Path)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--ascii", action="store_true")
    parser.add_argument("--events", type=int, default=8)
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()
    if linked(args.run) or not args.run.is_dir() or not (args.run / "session-state.md").is_file():
        print("tui: not a council run folder (or a link to one): {}".format(args.run), file=sys.stderr)
        return 2
    ascii_only = args.ascii or ascii_needed()
    events = max(0, min(args.events, 200))
    if args.json:
        print(json.dumps(snapshot(args.run, args.home, events), indent=2, sort_keys=True))
        return 0
    if not args.watch:
        print(render(snapshot(args.run, args.home, events), ascii_only))
        return 0
    try:
        return watch(args.run, args.home, events, ascii_only, max(0.5, min(args.interval, 60.0)))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
