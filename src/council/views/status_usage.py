"""What a run used, against its estimate, its token ceiling and its agent limit, as the status says it. The stop
is read as the helper reads it (records/usage.standing): the hook refuses agents on that reading, so the card
must say the same thing. references/run/run-accounting.md, "The stop at the limit"."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from council.records import seats as seat_files, state as run_state
from council.records.usage import agents_share, budget_value, standing
from council.views.status_names import seat_name
from council.views.words import listing, plural, tokens_text

Snap = Dict[str, Any]    # a run's snapshot (views/cockpit.snapshot)


def usage_of(snap: Snap) -> dict[str, Any]:
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
        text = ("{} tokens reported so far; agents still working".format(tokens_text(known)) if known
                else "no usage reported yet; agents still working")
    elif basis == "partial":
        gaps = []
        if missing:
            gaps.append("{} without a usage report".format(plural(missing, "agent run")))
        if tokens.get("unrecorded_seats"):
            gaps.append("no agent on record for {}".format(
                listing([seat_name(snap, s) for s in tokens["unrecorded_seats"]], 3)))
        text = "at least {} tokens — {}".format(tokens_text(known), "; ".join(gaps) or "some usage unknown")
    elif basis == "legacy":
        text = "not reliably recorded (this run uses the older record format)"
    elif basis == "suspect":
        text = "not shown — some recorded counts look wrong ({})".format(listing(tokens.get("suspect_seats", []), 3))
    elif not at_least and not seat_files.agent_starts(snap["run"].get("path") or "."):   # a known zero is no unknown
        closed = snap["run"].get("status", "").split(" ")[0] in ("complete", "abandoned", "paused")
        text = "no agent ran" if closed else "no agent has run yet"
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


def cap_standing(snap: Snap, run_path: str | Path, home: str | Path | None = None) -> dict[str, Any]:
    """The helper's standing (usage.standing) in the card's words; home defaults to the run's council home."""
    held = standing(Path(run_path), home if home is not None else Path(run_path).parent.parent)
    return {"agent_runs": held.used, "agent_cap": held.cap, "tokens": held.tokens, "ceiling": held.ceiling,
            "allowed_until": held.until, "over": held.over, "stopped": held.stopped}


def spend_of(usage: dict[str, Any], run_path: Path) -> dict[str, Any]:
    """Compare only known exact token counts with the run's planned estimate and ceiling."""
    estimate, ceiling = budget_value(run_path, "estimated-tokens"), budget_value(run_path, "token-ceiling")
    share = agents_share(run_path)            # seats record agents only: compare them with their share
    whose = "" if share == estimate else " the agents' {} share".format(tokens_text(share))
    known = usage["tokens_known"]
    if usage["text"].startswith("no agent"):           # nothing to compare: say so, and the estimate if there was one
        message = usage["text"] + (" (estimated {})".format(tokens_text(estimate)) if estimate else "")
        if ceiling is not None:
            message += "; ceiling {}".format(tokens_text(ceiling))
        return {"estimate": estimate, "ceiling": ceiling, "spend_text": message}
    if estimate is None and ceiling is None:
        message = ""
    elif usage["basis"] == "complete":
        message = "spent {}".format(tokens_text(known))
    elif known:
        message = "at least {} used".format(tokens_text(known))
    else:
        message = "usage not known yet"
    if estimate is not None and whose:
        message += " of{} (estimated {})".format(whose, tokens_text(estimate))
    elif estimate is not None:
        message += (" of estimated {}" if known else " against estimated {}").format(tokens_text(estimate))
    if ceiling is not None:
        message += "; ceiling {}".format(tokens_text(ceiling))
    if share is not None and known > share and share > 0:
        over = ((known - share) * 100 + share // 2) // share
        message += " ({}about {}% over{})".format("at least " if usage["basis"] != "complete" else "", over,
                                                 whose or " estimate")
    return {"estimate": estimate, "share": share, "ceiling": ceiling, "spend_text": message}


def chair_text(snap: Snap) -> str | None:
    """The Chair's own tokens, once a close has read them."""
    chair = (snap.get("events") or {}).get("chair")
    if not chair:
        return None
    return "{}{} tokens{} (its context's growth, from the session transcript)".format(
        "at least " if chair.get("partial") else "", tokens_text(chair["tokens"]),
        " over " + plural(chair["calls"], "model call") if chair.get("calls") is not None else "")


def used(snap: Snap, run_path: Path, home: str | Path | None, open_run: bool) -> tuple[dict[str, Any], list[Any]]:
    """The reading's usage, with the stop's standing as usage["limit"], and what of it needs the user."""
    usage = usage_of(snap)
    usage.update(spend_of(usage, run_path))
    usage["chair_text"] = chair_text(snap)
    limit = cap_standing(snap, run_path, home)
    cap, runs = limit["agent_cap"], limit["agent_runs"]
    usage["agent_cap"] = cap
    recorded = usage["agent_runs"] if usage["agent_runs"] is not None else (usage["agent_runs_at_least"] or 0)
    if runs > recorded:              # the stop's own count, so "limit reached" never sits beside a smaller one
        usage["agent_runs_text"] = "{} started ({} recorded)".format(runs, recorded)
    if runs and usage["basis"] == "complete":
        usage["text"] += " (limit {})".format(cap)
    elif runs:
        usage["agent_runs_text"] += " (limit {})".format(cap)
    held = open_run and limit["stopped"]
    limit.update({"stopped": held, "text": go_text(limit, held, open_run, run_path)})
    usage["limit"] = limit
    return usage, over_limits(usage, open_run)


def go_text(limit: dict[str, Any], held: bool, open_run: bool, run_path: Path) -> str:
    """The stop holds only while the run is in progress (council cap, the agent gate); a go the user gave is
    said as such, so "stopped, waiting for your go" never reads like "over, on your go"."""
    if held:
        return "Stopped at the limit — waiting for your go."
    if open_run and limit["over"] and limit["allowed_until"] is not None:
        return "Your go allows up to {}.".format(plural(limit["allowed_until"], "agent run"))
    if open_run and limit["over"] and not run_state.planned(run_state.text(run_path)):
        return "It was opened before agent limits, so new agents are not stopped."
    return ""


def over_limits(usage: dict[str, Any], open_run: bool) -> list[dict[str, Any]]:
    """The attention items for a run past its agent limit, its estimate or its ceiling, or at its cap."""
    limit, attention = usage["limit"], []
    cap, runs, go, held = limit["agent_cap"], limit["agent_runs"], limit["text"], limit["stopped"]
    if runs and runs > cap:
        many = ("" if usage["agent_runs"] is not None else "at least ") + plural(runs, "agent run")
        if open_run:
            attention.append({"kind": "cap", "severity": 2 if held else 1, "text": (
                "This run has used {}, over its limit of {}. {}".format(
                    many, cap, go or "More should start only after you say so."))})
        else:
            attention.append({"kind": "cap", "severity": 1,
                              "text": "This run used {}, over its limit of {}.".format(many, cap)})
    known = usage["tokens_known"]
    if usage.get("share") is not None and known > usage["share"]:
        attention.append({"kind": "estimate", "severity": 1,
                          "text": "Token use is over the agents' share of the estimate."
                          if usage.get("share") != usage["estimate"] else "Token use is over the run's estimate."})
    if usage["ceiling"] and known > usage["ceiling"]:
        said = "Token use is over the run's ceiling. " + (go or "More should start only after you say so.")
        attention.append({"kind": "ceiling", "severity": (2 if held else 1) if open_run else 1,
                          "text": said if open_run else "The run used more tokens than its ceiling."})
    if go and not any(a["kind"] in ("cap", "ceiling") for a in attention):     # exactly at the cap
        attention.append({"kind": "stop", "severity": 1, "text": "Agent limit reached ({}). {}".format(cap, go)})
    return attention
