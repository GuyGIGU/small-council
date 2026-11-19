"""What a council run is doing, in plain words.

This is the one reading of a run's records that every status view shares: the chat widget
(`council status --widget`) and the short text summary (`council status`). It takes the run's
read-only snapshot (views/snapshot.py) and answers four questions:
- what is happening now;
- is the run moving;
- does anything need the user;
- what happened, and where is the evidence.

It writes nothing. Every fact comes from a file the helper or the Chair already writes. A value the
records do not support is shown as unknown, never guessed. Each reading carries the time it was
taken: a widget is a snapshot, and says so.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from council.clock import local_moment, utc_moment as utc_time
from council.records import config, memory, paths
from council.records import events as event_stream
from council.records.cells import clean
from council.records.gates import kind as gate_kind    # one rule for every view: a proof fails first, a probe dry-runs
from council.views import snapshot
from council.views.status_card import notification_line, text, widget
from council.views.status_closing import closing_of
from council.views.status_names import check_name, seat_name
from council.views.status_usage import used
from council.views.words import clock, iso, listing, plural, span, tokens_text

Snap = Dict[str, Any]    # a run's snapshot (snapshot.snapshot)
SCHEMA = "council.run-status/1"
QUIET_MINUTES = 60         # an open run with no recorded activity for this long reads as quiet (stale)
ATTEMPTS = 3               # the repair loop's stop limit (commands/repair_trail.py)
STAGES = (("convene", "Setting up"), ("prepare", "Gathering context"), ("assign", "Choosing the experts"),
          ("brief", "Writing the briefs"), ("work", "Experts at work"), ("collect", "Collecting results"),
          ("judge", "Weighing the findings"), ("challenge", "Checking the findings"),
          ("deliver", "Writing the report"), ("learn", "Recording lessons"))
OTHER_PHASES = {"build": "Building the plan's tasks"}
MODES = {"council-review": "Review", "council-plan": "Plan", "council-implement": "Build",
         "council-research": "Research", "council-postgame": "Post-game check", "council-init": "Setup",
         "council-health": "Health check"}
STATES = {  # key: (label, role, icon) — the role colours the badge, the words and icon carry the meaning
    "starting": ("Starting", "accent", "ti-player-play"),
    "running": ("Running", "accent", "ti-activity"),
    "waiting": ("Waiting for you", "warning", "ti-message-question"),
    "recovering": ("Fixing a failed check", "warning", "ti-tool"),
    "failing": ("A check is failing", "warning", "ti-alert-triangle"),
    "blocked": ("Blocked", "danger", "ti-alert-octagon"),
    "completed": ("Completed", "success", "ti-circle-check"),
    "interrupted": ("Interrupted", "neutral", "ti-player-pause"),
    "stale": ("No recent activity", "warning", "ti-clock"),
    "unknown": ("Status unknown", "neutral", "ti-help-circle"),
}
SUMMARIES = {"completed": "The run finished.", "unknown": "The run's records can't be read.",
             "blocked": "The build stopped and waits for your decision.", "waiting": "Waiting for your answer.",
             "stale": "Nothing has been recorded for a while.", "recovering": "A repair is under way.",
             "failing": "",           # the label says it and the attention line names the check: said once
             "starting": "Setting up the run."}
SEAT_WORDS = {"running": "started", "done": "finished", "failed": "failed", "blocked": "reported it was blocked",
              "queued": "queued", "skipped": "skipped"}
MENDING = ("builder-diagnose", "independent-diagnosis")


def checks_of(snap: Snap) -> list[dict[str, Any]]:
    """The latest run of every check (proofs and probes aside), in time order, and which recovered. A
    re-run overwrites a check's saved result, so its earlier failures come from the event stream."""
    latest, failed_once = {}, set()
    for name, seen in (snap["events"].get("gates") or {}).items():
        if seen.get("failed"):
            failed_once.add(name)
    for gate in snap["gates"]:
        if gate_kind(gate["name"]) != "check":
            continue
        if gate["exit"] not in (0, None):
            failed_once.add(gate["name"])
        latest[gate["name"]] = gate      # gates arrive sorted by time, so the last one wins
    rows = []
    for name, gate in latest.items():
        result = result_of(gate)
        rows.append({"name": name, "result": result, "when": gate["when"],
                     "recovered": result == "passed" and name in failed_once})
    return sorted(rows, key=lambda r: r["when"])


def result_of(gate: dict[str, Any]) -> str:
    return "unknown" if gate["exit"] is None else ("passed" if gate["exit"] == 0 else "failed")


def last_activity(snap: Snap) -> datetime | None:
    """The newest time any record of the run was written."""
    stamps = [local_moment(snap["run"].get("updated")), local_moment(snap["run"].get("closed"))]
    stamps += [local_moment(s["updated"]) for s in snap["seats"]]
    stamps += [local_moment(g["when"]) for g in snap["gates"]]
    stamps += [utc_time(e["at"]) for e in snap["events"]["last"]]
    stamps = [s for s in stamps if s]
    return max(stamps) if stamps else None


def event_text(event: dict[str, Any], snap: Snap) -> str | None:
    kind, subject, value = event["type"], event["subject"], event["value"]
    if kind == "run.opened":
        return "Run started"
    if kind == "run.phase_changed":
        return "Moved on to: " + phase_label(value)
    if kind in ("run.status_changed", "run.closed", "run.paused", "run.resumed"):
        return {"paused": "Run paused", "complete": "Run finished", "abandoned": "Run stopped early",
                "in-progress": "Run resumed"}.get(value, "Run " + value)
    if kind == "run.waiting_changed":
        return "Waiting for your answer" if value == "on" else "Your answer came in; work resumed"
    if kind == "seat.updated":
        return "{} {}".format(seat_name(snap, subject), SEAT_WORDS.get(value, value))
    if kind == "seat.usage_corrected":
        return "Record for {} corrected from its source".format(seat_name(snap, subject))
    if kind == "gate.finished":
        if gate_kind(subject) != "check":
            return None                  # a build's before-proof or a dry run: detail, not news
        return "Check {} {}".format(check_name(subject), value)
    if kind == "collect.finished":
        return "Results collected" if value == "passed" else "Collecting results found gaps"
    if kind == "verification.finished":
        return "Verification finished ({})".format(value)
    if kind == "memory.proposed":
        return "A lesson was drafted for your yes or no"
    if kind == "run.cap_passed":
        return "Went past the agent limit ({} agent runs, limit {})".format(
            value, (event.get("detail") or "").replace("cap=", ""))
    if kind == "run.chair_usage":
        return "The Chair's own work recorded: {} tokens".format(tokens_text(int(value))) if value.isdigit() else None
    if kind == "run.estimate_passed":
        return "Went past the run's token estimate"
    if kind == "run.ceiling_passed":
        return "Went past the owner's token ceiling"
    if kind == "run.cap_allowed":
        until = re.search(r"(?:^|;)until=([0-9]{1,9})(?:;|$)", event.get("detail") or "")
        return "Your go: up to {} agent runs".format(until.group(1)) if until else "Your go was recorded"
    return None                          # context builds and other bookkeeping stay out of the main view


def phase_label(phase: str) -> str:
    for key, label in STAGES:
        if key == phase:
            return label
    return OTHER_PHASES.get(phase, phase or "not recorded")


def stage_of(phase: str) -> dict[str, int] | None:
    for n, (key, _) in enumerate(STAGES, 1):
        if key == phase:
            return {"n": n, "of": len(STAGES)}
    return None


def recent_of(snap: Snap, ref: datetime, limit: int) -> tuple[list[dict[str, Any]], str]:
    """The last few things that happened, from the event stream — or, for a run from before it, from
    the seat and check records' own times (said as such)."""
    items: list[Any] = []
    if snap["events"]["present"] and snap["events"]["last"]:
        for event in snap["events"]["last"]:
            said = event_text(event, snap)
            moment = utc_time(event["at"])
            if said and not (items and items[-1]["text"] == said):   # one change can write two events
                items.append({"at": iso(moment), "clock": clock(moment, ref), "text": said})
        return items[-limit:], "events"
    for seat in snap["seats"]:
        moment = local_moment(seat["updated"])
        if moment:
            items.append((moment, "{} {}".format(seat_name(snap, seat["slug"]),
                                                 SEAT_WORDS.get(seat["state"], seat["state"]))))
    for gate in snap["gates"]:
        moment = local_moment(gate["when"])
        if moment and gate_kind(gate["name"]) == "check":
            items.append((moment, "Check {} {}".format(check_name(gate["name"]), result_of(gate))))
    items.sort(key=lambda item: item[0])
    return [{"at": iso(m), "clock": clock(m, ref), "text": t} for m, t in items[-limit:]], "records"


def evidence_of(snap: Snap, run_path: Path) -> list[dict[str, str]]:
    """Where the supporting records are, as paths the user (or the Chair) can open."""
    run = Path(run_path)
    base = run.parent.parent.parent if run.parent.name == "runs" else run.parent
    def rel(path: Path) -> str:
        try:
            return str(Path(path).relative_to(base)).replace("\\", "/")
        except ValueError:
            return str(path).replace("\\", "/")
    def count(pattern: str) -> int:
        try:
            return sum(1 for p in run.glob(pattern) if p.is_file() and not paths.linked(p))
        except OSError:
            return 0
    items = [{"label": "Run folder", "path": rel(run) + "/"}]
    def add(label: str, path: str) -> None:
        items.append({"label": label, "path": path})
    ask = snap["run"].get("ask") or ("ask.md" if (run / "ask.md").is_file() else "")
    if ask:
        add("Your request", ask if "/" in ask or "\\" in ask else rel(run / ask))
    if snap["run"].get("deliverable"):
        add("Deliverable", snap["run"]["deliverable"])
    seats, verifies, claims = count("seats/*.md"), count("verify-*.md"), snap["claims"]
    if seats:
        add("Expert reports ({})".format(seats), rel(run / "seats") + "/")
    if verifies:
        add("Verifier reports ({})".format(verifies), rel(run) + "/verify-*.md")
    if claims.get("stale"):
        add("Claims index out of date — council evidence check --run {} updates it".format(run.name),
            rel(run / "claims.jsonl"))
    elif claims["total"]:
        verdicts = ", ".join("{} {}".format(n, v.lower()) for v, n in claims["by_verdict"].items())
        add("Claims and their verdicts ({})".format(verdicts), rel(run / "claims.jsonl"))
    if snap["gates"]:
        add("Check results ({})".format(len(snap["gates"])), rel(run / "gates") + "/")
    if snap["repairs"]:
        add("Repair trail", rel(run / "repairs.jsonl"))
    if snap.get("corrections"):
        add("Corrected figures ({})".format(len(snap["corrections"])), rel(run / "corrections.jsonl"))
    return items


# --- the reading ----------------------------------------------------------------------------------------------
def interpret(snap: Snap, now: datetime | None = None, quiet_minutes: int = QUIET_MINUTES, recent: int = 5,
              home: str | Path | None = None) -> dict[str, Any]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    run = snap["run"]
    status, phase = (run.get("status") or "").split(" ")[0], run.get("phase") or ""
    run_path = Path(os.path.abspath(run.get("path") or "."))
    project = run_path.parent.parent.parent.name if run_path.parent.name == "runs" else run_path.parent.name
    checks, moment, open_run = checks_of(snap), last_activity(snap), status == "in-progress"
    quiet = (now - moment).total_seconds() / 60.0 if moment else None
    flow = {"status": status, "waiting": (run.get("waiting") or "").strip(), "quiet": quiet,
            "stale": quiet is not None and quiet >= quiet_minutes,
            "failing": [c for c in checks if c["result"] == "failed"],
            "stopped": {t: r for t, r in snap["repairs"].items() if r["next"] == "stop"},
            "mending": {t: r for t, r in snap["repairs"].items() if r["next"] in MENDING}}
    usage, over = used(snap, run_path, home, open_run)
    attention = flow_attention(flow, now) + over + notes_of(snap, run_path, status, open_run)
    attention.sort(key=lambda a: -a["severity"])
    progress = progress_of(snap, checks)
    progress["next"] = run.get("next") if open_run else ""
    items, source = recent_of(snap, now, recent)
    opened, state = local_moment(run.get("opened")), state_of(snap, flow, phase, progress["working"])
    return {
        "schema": SCHEMA,
        "snapshot_at": iso(now),
        "run": {"id": run.get("id", ""), "path": str(run_path), "project": project, "mode": run.get("mode", ""),
                "started": clock(opened, now) if opened else "",
                "mode_label": MODES.get(run.get("mode", ""), run.get("mode", "") or "Council run"),
                "status": status, "phase": phase, "phase_label": phase_label(phase), "stage": stage_of(phase),
                "opened": run.get("opened", ""), "closed": run.get("closed", "")},
        "state": state,
        "attention": attention,
        "progress": progress,
        "latest_check": latest_of(checks, now),
        "recent": items, "recent_source": source,
        "freshness": {"last_activity": iso(moment), "last_activity_clock": clock(moment, now) if moment else None,
                      "quiet_minutes": None if quiet is None else int(quiet),
                      "quiet": state["key"] == "stale"},
        "usage": usage,
        "closing": closing_of(snap, run_path, usage, progress["checks"], attention),
        "checks": checks,
        "seats": [{"slug": s["slug"], "name": seat_name(snap, s["slug"]), "state": s["state"],
                   "tokens": s.get("tokens"), "tokens_basis": s.get("tokens_basis", ""), "agent_runs": s.get("agents"),
                   "note": s["note"]} for s in snap["seats"]],
        "evidence": evidence_of(snap, run_path),
        "decisions": list(snap.get("decisions", []))[-3:],
    }


def flow_attention(flow: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
    """What the run's flow asks of the user: a stopped build, a question, a failing check, a repair under way,
    a quiet run, a pause."""
    attention, open_run, waiting = [], flow["status"] == "in-progress", flow["waiting"]
    for task, info in sorted(flow["stopped"].items()):
        attention.append({"kind": "blocked", "severity": 3, "text": (
            "The build stopped on {}: check {} failed {}. It needs your decision.".format(
                task, info["gate"] or "?", plural(info["attempts"] or ATTEMPTS, "time")))})
    if waiting and open_run:
        attention.append({"kind": "waiting", "severity": 2, "text": "Waiting for your answer: " + waiting})
    mending_gates = {info["gate"] for info in list(flow["mending"].values()) + list(flow["stopped"].values())}
    for check in flow["failing"]:
        if check["name"] in mending_gates:
            continue
        if open_run:
            said = "Check {} failed at {} and hasn't passed since.".format(
                check["name"], clock(local_moment(check["when"]), now))
        else:
            said = "The run ended with check {} failing.".format(check["name"])
        attention.append({"kind": "failure", "severity": 2, "text": said})
    for task, info in sorted(flow["mending"].items()):
        who = ("the builder is looking into it" if info["next"] == "builder-diagnose"
               else "an independent diagnosis is under way")
        attention.append({"kind": "recovering", "severity": 1, "text": (
            "Check {} failed on {} (attempt {} of {}); {}.".format(info["gate"] or "?", task, info["attempts"] or 1,
                                                                   ATTEMPTS, who))})
    if open_run and not waiting and flow["stale"]:
        attention.append({"kind": "stale", "severity": 1, "text": (
            "No activity recorded for {}. Agents may still be working, or the session may have stopped.".format(
                span(flow["quiet"])))})
    if flow["status"] == "paused":
        attention.append({"kind": "paused", "severity": 1,
                          "text": "The run is paused. Ask to resume it when you're ready."})
    return attention


def notes_of(snap: Snap, run_path: Path, status: str, open_run: bool) -> list[dict[str, Any]]:
    """Drafted lessons waiting, a memory file grown too large, a status file that can't be read, and an event stream
    that refuses the run's next state change."""
    attention = []
    if snap["memory"].get("proposed"):
        attention.append({"kind": "memory", "severity": 1, "text": "{} for your yes or no.".format(
            plural(snap["memory"]["proposed"], "drafted lesson waits", "drafted lessons wait"))})
    large = memory.size_note(run_path.parent.parent.as_posix()) if open_run and run_path.parent.name == "runs" else ""
    if large:
        attention.append({"kind": "memory-size", "severity": 1, "text": clean(large) + "."})
    if not status:
        attention.append({"kind": "data", "severity": 2, "text": "The run's status file is missing or can't be read."})
    code, why = event_stream.ready(run_path) if status in ("in-progress", "paused") else (0, "")
    if code:                                 # the stream the next state write checks (records.events.writable)
        step = ("repair it: council run events repair --run {}" if code == 1 else
                "it can't be rebuilt; close the run: council run close --run {}").format(run_path.name)
        attention.append({"kind": "events", "severity": 2, "text": "The run's event history is {} ({}), so it can't "
                          "move to another stage — {}.".format("damaged" if code == 1 else "lost", clean(why), step)})
    return attention


def state_key(snap: Snap, flow: dict[str, Any], phase: str) -> str:
    """The one state the run is in, the first that holds in this order."""
    status = flow["status"]
    active = any(s["state"] in ("running", "done", "failed", "blocked") for s in snap["seats"]) or bool(snap["gates"])
    return next(key for key, holds in (
        ("unknown", not status), ("completed", status == "complete"),
        ("interrupted", status in ("paused", "abandoned")), ("blocked", bool(flow["stopped"])),
        ("waiting", bool(flow["waiting"])), ("recovering", bool(flow["mending"])), ("failing", bool(flow["failing"])),
        ("stale", flow["stale"]), ("starting", not active and phase in ("", "convene", "prepare", "assign", "brief")),
        ("running", True)) if holds)


def state_of(snap: Snap, flow: dict[str, Any], phase: str, working: list[str]) -> dict[str, str]:
    key, status = state_key(snap, flow, phase), flow["status"]
    label, role, icon = STATES[key]
    if key == "interrupted":
        label = "Paused" if status == "paused" else "Stopped early"
        summary = "The run is paused." if status == "paused" else "The run was stopped before it finished."
    elif working and key in ("recovering", "failing", "starting", "running"):
        summary = "Working now: {}.".format(listing(working))
    else:
        summary = SUMMARIES.get(key, "In progress: {}.".format(phase_label(phase)))
    return {"key": key, "label": label, "role": role, "icon": icon, "summary": summary}


def progress_of(snap: Snap, checks: list[dict[str, Any]]) -> dict[str, Any]:
    """The seats and checks in words, the seats at work, and how many planned seats have not started."""
    seats = snap["seats"]
    counts: dict[str, int] = {}
    for seat in seats:
        counts[seat["state"]] = counts.get(seat["state"], 0) + 1
    planned = [slug for slug, info in snap["plan"].get("seats", {}).items()   # the Chair is no seat to wait for
               if info.get("disposition") == "selected" and info.get("role") != "chair" and slug != "chair"
               and slug not in {s["slug"] for s in seats}]
    total = len([s for s in seats if s["state"] != "skipped"]) + len(planned)    # a skipped seat is none to finish
    parts = ["{} of {} done".format(counts.get("done", 0), total)] if total else []
    for state, word in (("running", "working"), ("queued", "queued"), ("failed", "failed"), ("blocked", "blocked")):
        if counts.get(state):
            parts.append("{} {}".format(counts[state], word))
    if planned:
        parts.append("{} not started".format(len(planned)))
    seat_text = " · ".join(parts) if parts else (
        "none to run · {} skipped".format(counts["skipped"]) if counts.get("skipped") else "no seats recorded yet")
    failing = sum(1 for c in checks if c["result"] == "failed")
    passed, recovered = sum(1 for c in checks if c["result"] == "passed"), sum(1 for c in checks if c["recovered"])
    probes = any(gate_kind(g["name"]) == "probe" for g in snap["gates"])
    check_text = ("dry runs only, no check yet" if probes else "no checks run yet") if not checks else \
        "{} passing{}{}".format(passed, ", {} failing".format(failing) if failing else "",
                                " ({} recovered after failing)".format(recovered) if recovered else "")
    return {"seats": seat_text, "checks": check_text, "counts": counts, "planned": len(planned),
            "working": [seat_name(snap, s["slug"]) for s in seats if s["state"] == "running"]}


def latest_of(checks: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    """The check that ran last (checks_of's last row), with its time as the card shows it."""
    if not checks:
        return None
    last = checks[-1]
    return {"name": check_name(last["name"]), "result": last["result"], "at": iso(local_moment(last["when"])),
            "clock": clock(local_moment(last["when"]), now)}


# --- entry ----------------------------------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--home", type=Path)
    parser.add_argument("--widget", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--line", action="store_true", help="one short line for a notification")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--at", help="read the run as of this UTC time (YYYY-MM-DDTHH:MM:SSZ), for tests")
    args = parser.parse_args(argv)
    if not paths.is_run(args.run):
        print("status: not a council run folder (or a link to one): {}".format(args.run), file=sys.stderr)
        return 2
    now = utc_time(args.at) if args.at else None
    if args.at and not now:
        print("status: --at takes a UTC time like 2026-09-27T15:40:00Z", file=sys.stderr)
        return 2
    if args.line and config.notifications_off(args.home or args.run.parent.parent):
        return 0
    reading = interpret(snapshot.snapshot(args.run, args.home, 40), now, home=args.home)
    if args.json:
        print(json.dumps(reading, indent=2, sort_keys=True))
    elif args.widget:
        print(widget(reading, preview=args.preview))
    elif args.line:
        print(notification_line(reading))
    else:
        print(text(reading))
    return 0
