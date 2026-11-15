"""The cockpit's one screen of a run's snapshot (`council tui`): its header and budget, the seats, the gates, the
repairs, the evidence, memory and the timeline. Nothing from a file can move the cursor or retitle the window."""
from __future__ import annotations

import shutil
from typing import Any, Callable, Dict

from council import clock
from council.records.cells import CONTROL, number
from council.records.gates import failed_as_planned, kind as gate_kind
from council.records.usage import token_text

Snap = Dict[str, Any]    # a run's snapshot (cockpit.snapshot)
Add = Callable[..., None]
UNICODE = {"done": "✓", "running": "●", "queued": "○", "failed": "✗", "blocked": "■", "skipped": "–",
           "pass": "✓", "fail": "✗", "planned": "·", "unknown": "?", "top": "┌", "bottom": "└", "rule": "─"}
ASCII = {"done": "+", "running": "*", "queued": "o", "failed": "x", "blocked": "!", "skipped": "-",
         "pass": "+", "fail": "x", "planned": ".", "unknown": "?", "top": "+", "bottom": "+", "rule": "-"}
PLAIN = {"·": "|", "—": "-", "–": "-", "…": "...", "→": "->", "’": "'", "“": '"', "”": '"'}


def k(tokens: int | None) -> str:
    return token_text(tokens) if tokens is not None else "—"


def shown(value: Any) -> str:
    return "?" if value is None else str(value)


def seat_tokens(seat: dict[str, Any]) -> str:
    """A seat's tokens: the trusted count, or an unverified recorded one marked with '?'."""
    if seat["tokens"] is not None:
        return k(seat["tokens"])
    if seat.get("tokens_recorded"):
        return str(seat["tokens_recorded"]) + "?"
    return "—"


def usage_line(tokens: dict[str, Any]) -> str:
    """Spent tokens as far as the records support: a total only when every agent run reported one."""
    basis = tokens["basis"]
    if basis == "complete":
        return "{} (workers {}, verifiers {})".format(k(tokens["total"]), k(tokens["workers"]), k(tokens["verifiers"]))
    if basis == "running":
        return "{} so far".format(k(tokens["known"]))
    if basis == "partial":
        return "at least {} ({} agent run(s) without usage)".format(k(tokens["known"]), tokens["missing_runs"])
    if basis == "legacy":
        return "not reliably recorded (older records)"
    if basis == "suspect":
        return "not shown (implausible counts: {})".format(", ".join(tokens["suspect_seats"][:4]))
    return "—"


def render(snap: Snap, ascii_only: bool = False, width: int | None = None,
           reading: dict[str, Any] | None = None) -> str:
    g = ASCII if ascii_only else UNICODE
    width = max(60, min(width or shutil.get_terminal_size((100, 30)).columns, 120))
    lines = []

    def add(text: str = "") -> None:
        text = CONTROL.sub(" ", text)
        lines.append(text if len(text) <= width else text[:width - 1] + ("~" if ascii_only else "…"))

    title = " Small Council — {} ".format(snap["run"]["id"])
    add(g["top"] + g["rule"] + title + g["rule"] * max(0, width - len(title) - 2))
    _head(snap, reading, add)
    _seats(snap, g, add)
    _gates(snap, g, add)
    _records(snap, add)
    _timeline(snap["events"], add)
    add(g["bottom"] + g["rule"] * (width - 1))
    out = "\n".join(lines)
    if ascii_only:
        out = "".join(PLAIN.get(ch, ch if ord(ch) < 128 else "?") for ch in out)
    return out


def _section(add: Add, title: str) -> None:
    add()
    add(" " + title)


def _head(snap: Snap, reading: dict[str, Any] | None, add: Add) -> None:
    """The run's mode, phase and status, the shared reading's headline, the request, the plan and the budget."""
    run, plan = snap["run"], snap["plan"]
    add("  {} · phase {} · {} · updated {}".format(run["mode"] or "?", run["phase"] or "?", run["status"] or "?",
                                                   run["updated"] or "?"))
    if reading:
        said = reading["state"]
        add("  Status: " + (" — ".join((said["label"], said["summary"])) if said["summary"] else said["label"]))
        for item in reading["attention"][:4]:
            add("  {} {}".format("!" if item["severity"] >= 2 else "·", item["text"]))
    if run["ask"]:
        add("  Request: " + run["ask"])
    if plan.get("size"):
        add("  Plan: {} · risk {} · complexity {} · uncertainty {} · verification {}".format(
            plan.get("size", "?"), plan.get("risk", "?"), plan.get("complexity", "?"), plan.get("uncertainty", "?"),
            plan.get("level", "?")))
    runs = snap["usage"]["agents"]
    budget = "  Budget: estimated {} · spent {} · {} agent run(s)".format(
        k(number(plan.get("estimated-tokens"))), usage_line(snap["usage"]["tokens"]),
        runs["total"] if runs["total"] is not None else "at least {}".format(runs["at_least"]))
    if plan.get("agent-cap"):
        budget += " (cap {})".format(plan["agent-cap"])
    add(budget)
    if run["next"] and run["status"] == "in-progress":
        add("  Next: " + run["next"])


def _seats(snap: Snap, g: dict[str, str], add: Add) -> None:
    _section(add, "Seats")
    planned = snap["plan"].get("seats", {})
    drawn = set()
    for seat in snap["seats"]:
        drawn.add(seat["slug"])
        info = planned.get(seat["slug"], {})
        add("  {} {:<16} {:<8} {:>6}  {:<8} {}".format(g.get(seat["state"], "?"), seat["slug"][:16], seat["state"][:8],
                                                     seat_tokens(seat), info.get("role", "")[:8],
                                                     info.get("context", "")))
    for slug, info in sorted(planned.items()):
        if slug in drawn or info.get("disposition") not in ("selected", "skipped") or info.get("role") == "chair":
            continue                                # the Chair is no seat to wait for
        if info["disposition"] == "skipped":
            add("  {} {:<16} skipped  — {}".format(g["skipped"], slug[:16], info.get("reason", "")))
        else:
            add("  {} {:<16} planned  {:>6}  {:<8} {}".format(g["queued"], slug[:16], "", info.get("role", "")[:8],
                                                            info.get("context", "")))
    if not snap["seats"] and not planned:
        add("  none recorded yet")


def _gates(snap: Snap, g: dict[str, str], add: Add) -> None:
    if not snap["gates"]:
        return
    _section(add, "Gates")
    for gate in snap["gates"]:
        planned = failed_as_planned(gate)
        mark = g["unknown"] if gate["exit"] is None else (
            g["pass"] if gate["exit"] == 0 else g["planned"] if planned else g["fail"])
        void = gate_kind(gate["name"]) == "proof" and gate["exit"] not in (0, None) and gate.get("void")
        label = "failed as planned" if planned else "no proof yet: " + gate["void"] if void else ""
        note = " · ".join(words for words in (label, gate["note"]) if words)
        add("  {} {:<16} exit {:<4} {:>4}s  {}{}".format(mark, gate["name"][:16], shown(gate["exit"]),
                                                       gate["seconds"], gate["when"][-8:],
                                                       "  " + note if note else ""))


def _records(snap: Snap, add: Add) -> None:
    """The repair trail, the claim index and the memory proposals, each when there is one."""
    if snap["repairs"]:
        _section(add, "Repairs")
        for task, info in sorted(snap["repairs"].items()):
            add("  {} {}: attempt {} {} · {} · next {}".format(task, info["gate"], shown(info["attempts"]),
                                                             info["result"], info["category"] or "-",
                                                             info["next"] or "-"))
    claims = snap["claims"]
    if claims.get("stale") or claims["total"]:
        _section(add, "Evidence")
        add("  Claims index out of date" if claims.get("stale") else "  {} claim(s) · ".format(claims["total"])
            + " · ".join("{} {}".format(n, v) for v, n in claims["by_verdict"].items()))
    if snap["memory"]["proposed"]:
        _section(add, "Memory")
        add("  {} proposal(s) wait for the user's yes or no".format(snap["memory"]["proposed"]))


def _timeline(events: dict[str, Any], add: Add) -> None:
    add()
    if events.get("too_large"):
        add(" Timeline: events.tsv is over 4 MB and was not read — council run events check --run <folder>")
    elif not events["present"]:
        add(" Timeline: no events.tsv (a run from before the event stream)")
    else:
        malformed = ", {} malformed".format(events["malformed"]) if events["malformed"] else ""
        add(" Timeline ({} event(s){})".format(events["count"], malformed))
        for e in events["last"]:
            add("  {} {:<20} {:<12} {}".format(clock.event_clock(e["at"]), e["type"][:20], e["subject"][:12],
                                              e["value"]))
