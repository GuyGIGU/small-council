#!/usr/bin/env python3
"""What a council run is doing, in plain words.

This is the one reading of a run's records that every status view shares: the chat widget
(`council status --widget`), the short text summary (`council status`) and the terminal cockpit's
headline (`council tui`). It takes the cockpit's read-only snapshot and answers four questions:
- what is happening now;
- is the run moving;
- does anything need the user;
- what happened, and where is the evidence.

It writes nothing. Every fact comes from a file the helper or the Chair already writes. A value the
records do not support is shown as unknown, never guessed. Each reading carries the time it was
taken: a widget is a snapshot, and says so.
"""

import argparse
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cockpit  # noqa: E402  (the read-only run snapshot)

SCHEMA = "council.run-status/1"
QUIET_MINUTES = 60         # an open run with no recorded activity for this long reads as quiet (stale)
OLD_SNAPSHOT_MINUTES = 60  # a widget older than this tells the viewer to ask for a new one
ATTEMPTS = 3               # the repair loop's stop limit (scripts/repair.py)
STAGES = (("convene", "Setting up"), ("prepare", "Gathering context"), ("assign", "Choosing the experts"),
          ("brief", "Writing the briefs"), ("work", "Experts at work"), ("collect", "Collecting results"),
          ("judge", "Weighing the findings"), ("challenge", "Checking the findings"),
          ("deliver", "Writing the report"), ("learn", "Recording lessons"))
OTHER_PHASES = {"build": "Building the plan's tasks"}
MODES = {"council-review": "Review", "council-plan": "Plan", "council-implement": "Build",
         "council-research": "Research", "council-postgame": "Post-game check", "council-init": "Setup"}
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
SEAT_WORDS = {"running": "started", "done": "finished", "failed": "failed", "blocked": "reported it was blocked",
              "queued": "queued", "skipped": "skipped"}


# --- time -----------------------------------------------------------------------------------------------------
def local_time(text):
    """A helper's local 'YYYY-MM-DD HH:MM[:SS]' stamp as an aware time, or None."""
    text = (text or "").strip()[:19]
    for form in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, form).astimezone()
        except (ValueError, OverflowError, OSError):
            continue
    return None


def utc_time(text):
    try:
        return datetime.strptime((text or "").strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError):
        return None


def iso(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if moment else None


def clock(moment, ref):
    """HH:MM on the reference's day, else 'Sep 26 15:49' — both in local time."""
    if not moment:
        return "?"
    local, day = moment.astimezone(), ref.astimezone()
    if local.date() == day.date():
        return local.strftime("%H:%M")
    return "{} {} {}".format(local.strftime("%b"), local.day, local.strftime("%H:%M"))


def span(minutes):
    minutes = max(0, int(minutes))
    if minutes < 1:
        return "under a minute"
    if minutes < 60:
        return "{} min".format(minutes)
    hours, rest = divmod(minutes, 60)
    if hours < 48:
        return "{} h {} min".format(hours, rest) if rest else "{} h".format(hours)
    return "{} days".format(hours // 24)


def minutes_between(earlier, later):
    return (later - earlier).total_seconds() / 60.0


# --- numbers --------------------------------------------------------------------------------------------------
def tokens_text(value):
    """A display form (160k, 1.2M) of an exact token count; the stored value is never rounded."""
    if value is None:
        return "unknown"
    if value >= 995000:
        return "{:.1f}M".format(value / 1000000.0).replace(".0M", "M")
    if value >= 1000:
        return "{}k".format(int(round(value / 1000.0)))
    return str(value)


def plural(n, one, many=None):
    return "{} {}".format(n, one if n == 1 else (many or one + "s"))


def listing(names, limit=4):
    names = list(names)
    if len(names) <= limit:
        return ", ".join(names)
    return "{} and {} more".format(", ".join(names[:limit]), len(names) - limit)


# --- reading the snapshot -------------------------------------------------------------------------------------
def gate_kind(name):
    """A build's before-proof is meant to fail and a probe is a dry run: neither is a check of the work."""
    if name.startswith("before-"):
        return "proof"
    if name.startswith("probe-"):
        return "probe"
    return "check"


def checks_of(snap):
    """The latest run of every check (proofs and probes aside), in time order, and which recovered."""
    latest, failed_once = {}, set()
    for gate in snap["gates"]:
        if gate_kind(gate["name"]) != "check":
            continue
        if gate["exit"] not in (0, None):
            failed_once.add(gate["name"])
        latest[gate["name"]] = gate      # gates arrive sorted by time, so the last one wins
    rows = []
    for name, gate in latest.items():
        result = "unknown" if gate["exit"] is None else ("passed" if gate["exit"] == 0 else "failed")
        rows.append({"name": name, "result": result, "when": gate["when"],
                     "recovered": result == "passed" and name in failed_once})
    return sorted(rows, key=lambda r: r["when"])


def last_activity(snap):
    """The newest time any record of the run was written, and the list it came from."""
    stamps = [local_time(snap["run"].get("updated")), local_time(snap["run"].get("closed"))]
    stamps += [local_time(s["updated"]) for s in snap["seats"]]
    stamps += [local_time(g["when"]) for g in snap["gates"]]
    stamps += [utc_time(e["at"]) for e in snap["events"]["last"]]
    stamps = [s for s in stamps if s]
    return max(stamps) if stamps else None


def event_text(event, repairs_by_gate):
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
        return "{} {}".format(subject, SEAT_WORDS.get(value, value))
    if kind == "seat.usage_corrected":
        return "Record for {} corrected from its source".format(subject)
    if kind == "gate.finished":
        if gate_kind(subject) != "check":
            return None                  # a build's before-proof or a dry run: detail, not news
        return "Check {} {}".format(subject, value)
    if kind == "collect.finished":
        return "Results collected" if value == "passed" else "Collecting results found gaps"
    if kind == "verification.finished":
        return "Verification finished ({})".format(value)
    if kind == "memory.proposed":
        return "A lesson was drafted for your yes or no"
    return None                          # context builds and other bookkeeping stay out of the main view


def phase_label(phase):
    for key, label in STAGES:
        if key == phase:
            return label
    return OTHER_PHASES.get(phase, phase or "not recorded")


def stage_of(phase):
    for n, (key, _) in enumerate(STAGES, 1):
        if key == phase:
            return {"n": n, "of": len(STAGES)}
    return None


def recent_of(snap, ref, limit):
    """The last few things that happened, from the event stream — or, for a run from before it, from
    the seat and check records' own times (said as such)."""
    items = []
    if snap["events"]["present"] and snap["events"]["last"]:
        for event in snap["events"]["last"]:
            text = event_text(event, None)
            moment = utc_time(event["at"])
            if text:
                items.append({"at": iso(moment), "clock": clock(moment, ref), "text": text})
        return items[-limit:], "events"
    for seat in snap["seats"]:
        moment = local_time(seat["updated"])
        if moment:
            items.append((moment, "{} {}".format(seat["slug"], SEAT_WORDS.get(seat["state"], seat["state"]))))
    for gate in snap["gates"]:
        moment = local_time(gate["when"])
        if moment and gate_kind(gate["name"]) == "check":
            result = "unknown" if gate["exit"] is None else ("passed" if gate["exit"] == 0 else "failed")
            items.append((moment, "Check {} {}".format(gate["name"], result)))
    items.sort(key=lambda item: item[0])
    return [{"at": iso(m), "clock": clock(m, ref), "text": t} for m, t in items[-limit:]], "records"


def usage_of(snap):
    """Token and agent-run totals, said only as far as the records support them."""
    usage = snap.get("usage") or {}
    tokens, agents = usage.get("tokens") or {}, usage.get("agents") or {}
    basis = tokens.get("basis", "none")
    total, known = tokens.get("total"), tokens.get("known", 0)
    runs, at_least = agents.get("total"), agents.get("at_least", 0)
    missing = tokens.get("missing_runs", 0)
    if basis == "complete":
        text = "{} tokens across {}".format(tokens_text(total), plural(runs, "agent run"))
    elif basis == "running":
        text = "{} tokens so far across {}".format(tokens_text(known), plural(at_least, "finished agent run"))
    elif basis == "partial":
        text = "at least {} tokens — {} without a usage report".format(tokens_text(known), plural(missing, "agent run"))
    elif basis == "legacy":
        text = "not reliably recorded (this run uses the older record format)"
    elif basis == "suspect":
        text = "not shown — some recorded counts look wrong ({})".format(listing(tokens.get("suspect_seats", []), 3))
    else:
        text = "no usage recorded yet"
    if runs is not None:
        runs_text = str(runs)
    elif at_least:
        runs_text = "at least {} (some counts are missing)".format(at_least)
    else:
        runs_text = "none yet"
    return {"tokens": total if basis == "complete" else None, "tokens_known": known, "basis": basis,
            "text": text, "agent_runs": runs, "agent_runs_at_least": at_least, "agent_runs_text": runs_text,
            "corrected_seats": tokens.get("corrected_seats", [])}


def evidence_of(snap, run_path):
    """Where the supporting records are, as paths the user (or the Chair) can open."""
    run = Path(run_path)
    base = run.parent.parent.parent if run.parent.name == "runs" else run.parent
    def rel(path):
        try:
            return str(Path(path).relative_to(base)).replace("\\", "/")
        except ValueError:
            return str(path).replace("\\", "/")
    def count(pattern):
        try:
            return sum(1 for p in run.glob(pattern) if p.is_file() and not cockpit.linked(p))
        except OSError:
            return 0
    items = [{"label": "Run folder", "path": rel(run) + "/"}]
    ask = snap["run"].get("ask") or ("ask.md" if (run / "ask.md").is_file() else "")
    if ask:
        items.append({"label": "Your request", "path": ask if "/" in ask or "\\" in ask else rel(run / ask)})
    if snap["run"].get("deliverable"):
        items.append({"label": "Deliverable", "path": snap["run"]["deliverable"]})
    seats = count("seats/*.md")
    if seats:
        items.append({"label": "Expert reports ({})".format(seats), "path": rel(run / "seats") + "/"})
    verifies = count("verify-*.md")
    if verifies:
        items.append({"label": "Verifier reports ({})".format(verifies), "path": rel(run) + "/verify-*.md"})
    claims = snap["claims"]
    if claims["total"]:
        verdicts = ", ".join("{} {}".format(n, v.lower()) for v, n in claims["by_verdict"].items())
        items.append({"label": "Claims and their verdicts ({})".format(verdicts), "path": rel(run / "claims.jsonl")})
    if snap["gates"]:
        items.append({"label": "Check results ({})".format(len(snap["gates"])), "path": rel(run / "gates") + "/"})
    if snap["repairs"]:
        items.append({"label": "Repair trail", "path": rel(run / "repairs.jsonl")})
    if snap.get("corrections"):
        items.append({"label": "Corrected figures ({})".format(len(snap["corrections"])),
                      "path": rel(run / "corrections.jsonl")})
    return items


# --- the reading ----------------------------------------------------------------------------------------------
def interpret(snap, now=None, quiet_minutes=QUIET_MINUTES, recent=5):
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    run = snap["run"]
    status = (run.get("status") or "").split(" ")[0]
    phase = run.get("phase") or ""
    run_path = Path(os.path.abspath(run.get("path") or "."))
    project = run_path.parent.parent.parent.name if run_path.parent.name == "runs" else run_path.parent.name
    waiting = (run.get("waiting") or "").strip()
    checks = checks_of(snap)
    failing = [c for c in checks if c["result"] == "failed"]
    repairs = snap["repairs"]
    stopped = {t: r for t, r in repairs.items() if r["next"] == "stop"}
    mending = {t: r for t, r in repairs.items() if r["next"] in ("builder-diagnose", "independent-diagnosis")}
    seats = snap["seats"]
    counts = {}
    for seat in seats:
        counts[seat["state"]] = counts.get(seat["state"], 0) + 1
    planned = [slug for slug, info in snap["plan"].get("seats", {}).items()
               if info.get("disposition") == "selected" and slug not in {s["slug"] for s in seats}]
    working = [s["slug"] for s in seats if s["state"] == "running"]
    active = any(s["state"] in ("running", "done", "failed", "blocked") for s in seats) or bool(snap["gates"])
    moment = last_activity(snap)
    quiet = minutes_between(moment, now) if moment else None
    open_run = status == "in-progress"

    attention = []
    for task, info in sorted(stopped.items()):
        attention.append({"kind": "blocked", "severity": 3, "text": (
            "The build stopped on {}: check {} failed {}. It needs your decision.".format(
                task, info["gate"] or "?", plural(info["attempts"] or ATTEMPTS, "time")))})
    if waiting and open_run:
        attention.append({"kind": "waiting", "severity": 2, "text": "Waiting for your answer: " + waiting})
    mending_gates = {info["gate"] for info in list(mending.values()) + list(stopped.values())}
    for check in failing:
        if check["name"] in mending_gates:
            continue
        if open_run:
            text = "Check {} failed at {} and hasn't passed since.".format(check["name"], clock(local_time(check["when"]), now))
        else:
            text = "The run ended with check {} failing.".format(check["name"])
        attention.append({"kind": "failure", "severity": 2, "text": text})
    for task, info in sorted(mending.items()):
        attempt = info["attempts"] or 1
        who = "the builder is looking into it" if info["next"] == "builder-diagnose" else "an independent diagnosis is under way"
        attention.append({"kind": "recovering", "severity": 1, "text": (
            "Check {} failed on {} (attempt {} of {}); {}.".format(info["gate"] or "?", task, attempt, ATTEMPTS, who))})
    if open_run and not waiting and quiet is not None and quiet >= quiet_minutes:
        attention.append({"kind": "stale", "severity": 1, "text": (
            "No activity recorded for {}. Agents may still be working, or the session may have stopped.".format(
                span(quiet)))})
    if status == "paused":
        attention.append({"kind": "paused", "severity": 1, "text": "The run is paused. Ask to resume it when you're ready."})
    if snap["memory"].get("proposed"):
        attention.append({"kind": "memory", "severity": 1, "text": "{} for your yes or no.".format(
            plural(snap["memory"]["proposed"], "drafted lesson waits", "drafted lessons wait"))})
    if not status:
        attention.append({"kind": "data", "severity": 2, "text": "The run's status file is missing or can't be read."})
    attention.sort(key=lambda a: -a["severity"])

    if not status:
        key = "unknown"
    elif status == "complete":
        key = "completed"
    elif status in ("paused", "abandoned"):
        key = "interrupted"
    elif stopped:
        key = "blocked"
    elif waiting:
        key = "waiting"
    elif mending:
        key = "recovering"
    elif failing:
        key = "failing"
    elif quiet is not None and quiet >= quiet_minutes:
        key = "stale"
    elif not active and phase in ("", "convene", "prepare", "assign", "brief"):
        key = "starting"
    else:
        key = "running"
    label, role, icon = STATES[key]
    if key == "interrupted":
        label = "Paused" if status == "paused" else "Stopped early"

    total = len(seats) + len(planned)
    parts = []
    if total:
        parts.append("{} of {} done".format(counts.get("done", 0), total))
    for state, word in (("running", "working"), ("queued", "queued"), ("failed", "failed"), ("blocked", "blocked")):
        if counts.get(state):
            parts.append("{} {}".format(counts[state], word))
    if planned:
        parts.append("{} not started".format(len(planned)))
    seat_text = " · ".join(parts) if parts else "no seats recorded yet"
    passed = sum(1 for c in checks if c["result"] == "passed")
    recovered = sum(1 for c in checks if c["recovered"])
    check_text = "no checks run yet" if not checks else "{} passing{}{}".format(
        passed, ", {} failing".format(len(failing)) if failing else "",
        " ({} recovered after failing)".format(recovered) if recovered else "")
    latest = None
    real = [g for g in snap["gates"] if gate_kind(g["name"]) == "check"]
    if real:
        g = real[-1]
        result = "unknown" if g["exit"] is None else ("passed" if g["exit"] == 0 else "failed")
        latest = {"name": g["name"], "result": result, "at": iso(local_time(g["when"])),
                  "clock": clock(local_time(g["when"]), now)}
    items, source = recent_of(snap, now, recent)
    stage = stage_of(phase)
    usage = usage_of(snap)
    next_step = run.get("next") if open_run else ""
    if key == "completed":
        summary = "The run finished."
    elif key == "interrupted":
        summary = "The run is paused." if status == "paused" else "The run was stopped before it finished."
    elif key == "unknown":
        summary = "The run's records can't be read."
    elif key == "blocked":
        summary = "The build stopped and waits for your decision."
    elif key == "waiting":
        summary = "Waiting for your answer."
    elif key == "stale":
        summary = "Nothing has been recorded for a while."
    elif working:
        summary = "Working now: {}.".format(listing(working))
    elif key == "recovering":
        summary = "A repair is under way."
    elif key == "failing":
        summary = "A check failed."
    elif key == "starting":
        summary = "Setting up the run."
    else:
        summary = "In progress: {}.".format(phase_label(phase))
    return {
        "schema": SCHEMA,
        "snapshot_at": iso(now),
        "run": {"id": run.get("id", ""), "path": str(run_path), "project": project, "mode": run.get("mode", ""),
                "mode_label": MODES.get(run.get("mode", ""), run.get("mode", "") or "Council run"),
                "status": status, "phase": phase, "phase_label": phase_label(phase), "stage": stage,
                "opened": run.get("opened", ""), "closed": run.get("closed", "")},
        "state": {"key": key, "label": label, "role": role, "icon": icon, "summary": summary},
        "attention": attention,
        "progress": {"seats": seat_text, "checks": check_text, "working": working, "next": next_step,
                     "counts": counts, "planned": len(planned)},
        "latest_check": latest,
        "recent": items, "recent_source": source,
        "freshness": {"last_activity": iso(moment), "last_activity_clock": clock(moment, now) if moment else None,
                      "quiet_minutes": None if quiet is None else int(quiet), "quiet": key == "stale"},
        "usage": usage,
        "checks": checks,
        "seats": [{"slug": s["slug"], "state": s["state"], "tokens": s.get("tokens"),
                   "tokens_basis": s.get("tokens_basis", ""), "agent_runs": s.get("agents"),
                   "note": s["note"]} for s in seats],
        "evidence": evidence_of(snap, run_path),
    }


# --- text -----------------------------------------------------------------------------------------------------
def text(status, tui_commands=()):
    run, state = status["run"], status["state"]
    now = utc_time(status["snapshot_at"])
    lines = ["{} · {} · {}".format(run["project"] or "council", run["mode_label"], run["id"])]
    stage = status["run"]["stage"]
    where = run["phase_label"] + (" (stage {} of {})".format(stage["n"], stage["of"]) if stage else "")
    line = "Status: {}. {}".format(state["label"], state["summary"])
    if state["key"] not in ("completed", "interrupted"):
        line += " Stage: {}.".format(where)
    lines.append(line)
    if status["attention"]:
        for item in status["attention"]:
            lines.append("Needs you: " + item["text"] if item["severity"] >= 2 else "Note: " + item["text"])
    else:
        lines.append("Needs you: nothing right now.")
    lines.append("Seats: {} · Checks: {}".format(status["progress"]["seats"], status["progress"]["checks"]))
    if status["latest_check"]:
        c = status["latest_check"]
        lines.append("Latest check: {} {} at {}".format(c["name"], c["result"], c["clock"]))
    if status["progress"]["next"]:
        lines.append("Next: " + status["progress"]["next"][:200])
    if status["recent"]:
        lines.append("Recent: " + " · ".join("{} {}".format(i["clock"], i["text"]) for i in status["recent"][-4:]))
    fresh = status["freshness"]
    usage = status["usage"]
    lines.append("Token use: " + usage["text"] + ("" if usage["basis"] == "complete" else
                                                  " · Agent runs: " + usage["agent_runs_text"]))
    lines.append("As of {} (last activity {}).".format(clock(now, now), fresh["last_activity_clock"] or "unknown"))
    for command in tui_commands or ():
        lines.append("Live view in a terminal — " + command)
    return "\n".join(lines)


# --- the chat widget ------------------------------------------------------------------------------------------
STYLE = (
    "<style>"
    ".sc{font-size:14px;line-height:1.55;color:var(--text-primary)}"
    ".sc p{margin:0}"
    ".sc .card{background:var(--surface-2);border:0.5px solid var(--border);border-radius:12px;padding:1rem 1.25rem}"
    ".sc .row{display:flex;flex-wrap:wrap;align-items:center;gap:8px}"
    ".sc .badge{display:inline-flex;align-items:center;gap:6px;padding:2px 10px;border-radius:var(--radius);font-weight:500}"
    ".sc .accent{background:var(--bg-accent);color:var(--text-accent)}"
    ".sc .warning{background:var(--bg-warning);color:var(--text-warning)}"
    ".sc .danger{background:var(--bg-danger);color:var(--text-danger)}"
    ".sc .success{background:var(--bg-success);color:var(--text-success)}"
    ".sc .neutral{background:var(--surface-1);color:var(--text-secondary)}"
    ".sc .muted{color:var(--text-secondary);font-size:13px}"
    ".sc .box{border-radius:var(--radius);padding:8px 12px;margin:12px 0 0}"
    ".sc .tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:12px 0 0}"
    ".sc .tile{background:var(--surface-1);border-radius:var(--radius);padding:8px 12px}"
    ".sc ul{margin:4px 0 0;padding-left:18px}"
    ".sc .sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}"
    "</style>")
SCRIPT = (
    "<script>(function(){var c=document.getElementById('sc-card');if(!c)return;"
    "var at=Date.parse(c.getAttribute('data-at'));if(isNaN(at))return;"
    "function f(){var m=Math.max(0,Math.round((Date.now()-at)/60000));"
    "var t=m<1?'just now':m<60?m+' min ago':m<2880?Math.floor(m/60)+' h '+(m%60)+' min ago':Math.floor(m/1440)+' days ago';"
    "var e=document.getElementById('sc-age');if(e)e.textContent=t;"
    "var o=document.getElementById('sc-old');if(o&&m>=" + str(OLD_SNAPSHOT_MINUTES) + ")o.hidden=false}"
    "f();setInterval(f,60000)})();</script>")


def esc(value):
    return html.escape(cockpit.clean(value), quote=True)


def widget(status, preview=False, limit=5):
    """One self-contained HTML fragment for a chat widget host (no page, no network, no local reads).
    Every value from the run is escaped; the script only computes the snapshot's age from its time."""
    run, state, prog = status["run"], status["state"], status["progress"]
    now = utc_time(status["snapshot_at"])
    stage = run["stage"]
    out = [STYLE]
    attention = status["attention"]
    sr = "{} {}: {}. {} Seats: {}. {}".format(
        run["project"], run["mode_label"], state["label"], state["summary"], prog["seats"],
        "{} needs your attention.".format(plural(len(attention), "item")) if attention else "Nothing needs your attention.")
    out.append('<div class="sc"><h2 class="sr">{}</h2>'.format(esc(sr)))
    out.append('<div class="card" id="sc-card" data-at="{}">'.format(esc(status["snapshot_at"])))
    if preview:
        out.append('<p class="box neutral" style="margin:0 0 12px"><i class="ti ti-eye" aria-hidden="true"></i> '
                   'Preview built from a fixed snapshot taken {}. It does not update.</p>'.format(esc(clock(now, now))))
    out.append('<div class="row"><span class="badge {}"><i class="ti {}" aria-hidden="true"></i>{}</span>'
               '<span style="font-weight:500">{}</span><span class="muted">{} · {}</span></div>'.format(
                   state["role"], state["icon"], esc(state["label"]), esc(run["project"] or "Council run"),
                   esc(run["mode_label"]), esc(run["id"])))
    out.append('<p style="margin-top:6px">{}</p>'.format(esc(state["summary"])))
    if attention:
        top = attention[0]["severity"]
        role = "danger" if any(a["kind"] == "blocked" for a in attention) else ("warning" if top >= 1 else "neutral")
        out.append('<div class="box {}"><p style="font-weight:500"><i class="ti ti-alert-triangle" aria-hidden="true"></i> '
                   'Needs your attention</p><ul>{}</ul></div>'.format(
                       role, "".join("<li>{}</li>".format(esc(a["text"])) for a in attention[:limit])))
    else:
        out.append('<p class="muted" style="margin-top:8px"><i class="ti ti-check" aria-hidden="true"></i> '
                   'Nothing needs you right now.</p>')
    tiles = [("Stage", "{}{}".format(run["phase_label"], " · {} of {}".format(stage["n"], stage["of"]) if stage else "")
              if state["key"] not in ("completed", "interrupted") else state["label"]),
             ("Seats", prog["seats"]), ("Checks", prog["checks"])]
    out.append('<div class="tiles">' + "".join(
        '<div class="tile"><p class="muted">{}</p><p style="font-weight:500">{}</p></div>'.format(esc(k), esc(v))
        for k, v in tiles) + "</div>")
    if status["latest_check"]:
        c = status["latest_check"]
        out.append('<p class="muted" style="margin-top:10px">Latest check: {} {} at {}</p>'.format(
            esc(c["name"]), esc(c["result"]), esc(c["clock"])))
    if prog["next"]:
        next_text = prog["next"] if len(prog["next"]) <= 220 else prog["next"][:219] + "…"
        out.append('<p style="margin-top:8px"><span class="muted">Next:</span> {}</p>'.format(esc(next_text)))
    if status["recent"]:
        out.append('<p class="muted" style="margin-top:10px">Recent{}</p><ul>{}</ul>'.format(
            "" if status["recent_source"] == "events" else " (from older records)",
            "".join("<li><span class=\"muted\">{}</span> {}</li>".format(esc(i["clock"]), esc(i["text"]))
                    for i in status["recent"][-limit:])))
    fresh = status["freshness"]
    out.append('<p class="muted" style="margin-top:12px"><i class="ti ti-clock" aria-hidden="true"></i> '
               'Snapshot {} (<span id="sc-age">{}</span>) · last activity {}</p>'.format(
                   esc(clock(now, now)), "at " + esc(clock(now, now)), esc(fresh["last_activity_clock"] or "unknown")))
    out.append('<p class="muted" id="sc-old" hidden>This card is over an hour old. Ask for the council status '
               'to see the run now.</p>' if not preview else "")
    out.append(details(status))
    out.append("</div></div>")
    out.append(SCRIPT)
    return "".join(out).encode("ascii", "xmlcharrefreplace").decode("ascii")


def details(status, limit=12):
    usage = status["usage"]
    rows = ['<p><span class="muted">Token use:</span> {}</p>'.format(esc(usage["text"]))]
    if usage["basis"] in ("complete", "running", "partial"):
        rows.append('<p class="muted">Token figures measure how large each agent\'s work grew, not what it '
                    'cost.</p>')
    if usage["basis"] != "complete":
        rows.append('<p><span class="muted">Agent runs:</span> {}</p>'.format(esc(usage["agent_runs_text"])))
    if usage["corrected_seats"]:
        rows.append('<p class="muted">Corrected from source records: {}</p>'.format(esc(listing(usage["corrected_seats"], 6))))
    seats = status["seats"]
    if seats:
        shown = ["{} — {}{}".format(s["slug"], s["state"], "" if not s["note"] else ": " + s["note"][:80]) for s in seats[-limit:]]
        more = len(seats) - len(shown)
        rows.append('<p class="muted" style="margin-top:8px">Seats{}</p><ul>{}</ul>'.format(
            " (latest {} of {})".format(len(shown), len(seats)) if more else "",
            "".join("<li>{}</li>".format(esc(line)) for line in shown)))
    checks = status["checks"]
    if checks:
        shown = checks[-limit:]
        rows.append('<p class="muted" style="margin-top:8px">Checks, latest result of each{}</p><ul>{}</ul>'.format(
            " (latest {} of {})".format(len(shown), len(checks)) if len(checks) > len(shown) else "",
            "".join("<li>{} — {}{}</li>".format(esc(c["name"]), esc(c["result"]),
                                                 esc(", recovered after failing") if c["recovered"] else "")
                    for c in shown)))
    rows.append('<p class="muted" style="margin-top:8px">Where the evidence is</p><ul>{}</ul>'.format(
        "".join("<li>{}: <code>{}</code></li>".format(esc(e["label"]), esc(e["path"])) for e in status["evidence"])))
    return '<details style="margin-top:10px"><summary class="muted">Details and evidence</summary>{}</details>'.format(
        "".join(rows))


# --- entry ----------------------------------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--home", type=Path)
    parser.add_argument("--widget", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--at", help="read the run as of this UTC time (YYYY-MM-DDTHH:MM:SSZ), for tests")
    parser.add_argument("--tui-command", action="append", default=[],
                        help="the exact terminal-view command to print (repeatable, e.g. per shell)")
    args = parser.parse_args()
    if cockpit.linked(args.run) or not args.run.is_dir() or not (args.run / "session-state.md").is_file():
        print("status: not a council run folder (or a link to one): {}".format(args.run), file=sys.stderr)
        return 2
    now = utc_time(args.at) if args.at else None
    if args.at and not now:
        print("status: --at takes a UTC time like 2026-09-27T15:40:00Z", file=sys.stderr)
        return 2
    reading = interpret(cockpit.snapshot(args.run, args.home, 40), now)
    if args.json:
        print(json.dumps(reading, indent=2, sort_keys=True))
    elif args.widget:
        print(widget(reading, preview=args.preview))
    else:
        print(text(reading, args.tui_command))
    return 0


if __name__ == "__main__":
    sys.exit(main())
