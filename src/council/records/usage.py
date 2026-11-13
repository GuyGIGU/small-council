"""What a run's agents used, under the one per-seat rule of references/run/run-accounting.md, and where
the agent stop stands (the helper's seat_rows, run_usage and cap_standing).

seats.tsv, usage.tsv, agent-starts.tsv, cap-allowances.tsv and corrections.jsonl are read through
seats.py; this module only applies the rule to what they hold, so the status card, the cockpit and the
agent stop count alike.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, NamedTuple

from council.records import cells, config, plan, seats, state

INTMAX = 2 ** 63 - 1    # the largest whole number bash's test reads; a comparison with more fails, and stops nothing
Seat = Dict[str, Any]   # one seat's row and its figures, as seat_list builds it


def seat_usage(row: dict[str, Any], fixes: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    """One seat's agent runs and tokens, each with how far the record supports it — kept identical to
    the helper's seat_rows (bin/council), which states the close line and the ledger. Bases: reported,
    corrected, pending (still working), partial or missing (a finished run's usage is unknown),
    unrecorded (no agent on record: unknown, never zero), no-agent (declared with agents=0, or corrected
    so), suspect (a count no agent run can have), legacy (a row from before the accounting columns)."""
    slug, status = row["slug"], row["state"]
    executed = status not in ("", "queued", "skipped")      # as the helper's seat_rows selects rows
    finished = executed and status != "running"
    cell = str(row["raw_tokens"] if row["raw_tokens"] is not None else "").strip()
    recorded = cells.optional_number(cell)
    runs, reported = cells.optional_number(row["raw_agents"]), row["raw_reported"]
    legacy = reported is None
    fix_t, fix_a = fixes.get((slug, "tokens")), fixes.get((slug, "agents"))
    if fix_a:
        agents, basis_a, at_least = fix_a["to"], "corrected", fix_a["to"]
    elif legacy:
        agents, basis_a, at_least = None, "at-least", max(runs if runs is not None else 1, 1) if executed else 0
    elif runs is None:
        agents, basis_a, at_least = None, "unknown", 0          # no agent on record: not a zero
    else:
        agents, basis_a, at_least = runs, "counted", runs
    tokens, basis_t, missing, pending = _seat_tokens(status, executed, recorded, agents, reported, fix_t)
    return {"tokens": tokens, "tokens_basis": basis_t, "tokens_recorded": recorded, "agents": agents,
            "agents_basis": basis_a, "agents_at_least": at_least, "missing_runs": missing, "pending_runs": pending,
            "executed": executed, "finished": finished}


def _seat_tokens(status: str, executed: bool, recorded: int | None, agents: int | None, reported: int | None,
                 fix: dict[str, Any] | None) -> tuple[int | None, str, int, int]:
    """A seat's tokens and their basis, with the agent runs whose usage is missing or still pending."""
    if fix:
        return (None, "suspect", 0, 0) if 0 < fix["to"] < 1000 else (fix["to"], "corrected", 0, 0)
    if reported is None:
        return None, "legacy", 0, 0
    if not executed:
        return None, "none", 0, 0
    if agents is None:
        return None, "unrecorded", 0, 0
    if agents == 0 and reported == 0:
        return None, "no-agent", 0, 0
    if reported > 0 and (recorded is None or recorded < 1000):
        return None, "suspect", 0, 0   # a count no agent run can have (a unit slip or a broken cell)
    if reported >= agents and reported > 0:
        return recorded, "reported", 0, 0
    gap = max(0, agents - reported)
    tokens = recorded if reported > 0 else None
    if status == "running":
        return tokens, "pending", 0, gap
    return tokens, ("partial" if reported > 0 else "missing"), gap, 0


def seat_list(run: Path, fixes: dict[tuple[str, str], dict[str, Any]] | None = None) -> list[Seat]:
    """Every seat of the run with its figures: seats.tsv's rows, then each agent run never recorded but
    added from evidence (council correct unrecorded=yes)."""
    run = Path(run)
    fixes = seats.corrections(run) if fixes is None else fixes
    found = []
    for row in seats.rows(run):
        slug = cells.clean(row.get("slug", ""))
        if not slug:
            continue
        found.append(_figured({"slug": slug, "state": cells.clean(row.get("state", "")),
                               "agent": cells.clean(row.get("agent", "")),
                               "updated": cells.clean(row.get("updated", "")),
                               "note": cells.clean(row.get("note", ""))[:120], "raw_tokens": row.get("tokens"),
                               "raw_agents": row.get("agents"),
                               "raw_reported": cells.optional_number(row.get("reported"))}, fixes))
    recorded = {s["slug"] for s in found} | {cells.clean(r.get("slug", "")) for r in seats.rows(run)}
    for slug in sorted({f["seat"] for f in fixes.values() if f["added"]} - recorded):
        if (slug, "agents") in fixes:        # added from evidence; its figure may be unknown
            found.append(_figured({"slug": slug, "state": "done", "agent": "", "updated": "", "added": True,
                                   "note": "never recorded; added from evidence", "raw_tokens": None,
                                   "raw_agents": None, "raw_reported": 0}, fixes))
    return found


def _figured(seat: Seat, fixes: dict[tuple[str, str], dict[str, Any]]) -> Seat:
    seat.update(seat_usage(seat, fixes))
    for key in ("raw_tokens", "raw_agents", "raw_reported"):
        seat.pop(key)
    return seat


def usage_totals(seat_rows: list[Seat]) -> dict[str, Any]:
    """Run totals only as complete as their least complete seat — the helper's run_usage rule. A total
    over rows that cannot be trusted is None and the basis says why: legacy, then suspect, then partial
    (a finished run's usage is unknown, or a seat has no agent on record), then none (no agent ran), then
    running (a seat is still at work), else complete."""
    ran = [s for s in seat_rows if s["executed"]]
    counted = [s for s in ran if s["tokens"] is not None]
    known = sum(s["tokens"] for s in counted)
    agent_runs = sum((s["agents"] if s["agents"] is not None else s["agents_at_least"]) for s in ran)
    basis = _basis({s["tokens_basis"] for s in ran}, ran, agent_runs, bool(counted))
    verifier = [s for s in counted if s["slug"].startswith(("verify-", "diagnose-"))]
    complete = basis == "complete"
    exact = bool(ran) and all(s["agents"] is not None for s in ran)
    named = {kind: [s["slug"] for s in ran if s["tokens_basis"] == kind]
             for kind in ("legacy", "suspect", "unrecorded")}
    return {
        "tokens": {"basis": basis, "known": known, "total": known if complete else None,
                   "workers": sum(s["tokens"] for s in counted if s not in verifier) if complete else None,
                   "verifiers": sum(s["tokens"] for s in verifier) if complete else None,
                   "missing_runs": sum(s["missing_runs"] for s in ran),
                   "pending_runs": sum(s["pending_runs"] for s in ran),
                   "legacy_seats": named["legacy"], "suspect_seats": named["suspect"],
                   "unrecorded_seats": named["unrecorded"],
                   "added_seats": [s["slug"] for s in seat_rows if s.get("added")],
                   "corrected_seats": [s["slug"] for s in seat_rows
                                       if "corrected" in (s["tokens_basis"], s["agents_basis"])]},
        "agents": {"total": sum(s["agents"] for s in ran) if exact else None,
                   "at_least": sum(s["agents_at_least"] for s in ran),
                   "basis": "exact" if exact else ("at-least" if ran else "none")},
    }


def _basis(bases: set[str], ran: list[Seat], agent_runs: int, priced: bool) -> str:
    if "legacy" in bases:
        return "legacy"
    if "suspect" in bases:
        return "suspect"
    if bases & {"missing", "partial", "unrecorded"}:
        return "partial"
    if not ran or (agent_runs == 0 and not priced):
        return "none"
    if "pending" in bases or any(s["state"] == "running" for s in ran):
        return "running"
    return "complete"


def token_text(tokens: int) -> str:
    """An exact token count for display, rounded half up as the helper's usage_token_text: M from 995,000."""
    if tokens >= 995000:
        tenths = int(tokens + 50000) // 100000
        if tenths % 10 == 0:
            return "{}M".format(tenths // 10)
        return "{}.{}M".format(tenths // 10, tenths % 10)
    return "{}k".format(int(tokens + 500) // 1000)


def budget_value(run: Path, field: str) -> int | None:
    """A run-wide budget as a whole number (run_budget_value), or None: missing, not a number, too large
    for bash, or a zero ceiling (an estimate may be 0)."""
    value = plan.budget(run, field)
    if not re.fullmatch(r"[0-9]+", value) or int(value) > INTMAX:
        return None
    return int(value) if field == "estimated-tokens" or int(value) > 0 else None


def agent_cap(run: Path, home: str | Path | None) -> int:
    """The run's agent ceiling (run_agent_cap): its plan's budget/run/agent-cap, else the configured cap."""
    value = plan.budget(run, "agent-cap")
    if value in ("", "0") or not re.fullmatch(r"[0-9]+", value):
        return config.agent_cap(home)
    return int(value)


class Standing(NamedTuple):
    """Where a run stands against the agent stop (cap_standing). Agent runs: the larger of those recorded
    and the starts the gate let through, a Workflow's further agents added. Over: at the cap or past the
    ceiling. Stopped: over, no go of the user's covers the next agent, and the run has agent limits."""

    used: int
    recorded: int
    cap: int
    tokens: int
    ceiling: int | None
    until: int | None
    over: bool
    stopped: bool


def standing(run: Path, home: str | Path | None) -> Standing:
    """The run's standing; home is the council home whose config gives the cap when the plan names none."""
    run = Path(run)
    totals = usage_totals(seat_list(run))
    recorded = totals["agents"]["at_least"]
    used = max(recorded, seats.agent_starts(run) + seats.workflow_extra(run))    # counted from its start, once
    tokens = totals["tokens"]["known"]
    cap, ceiling, until = agent_cap(run, home), budget_value(run, "token-ceiling"), seats.allowed_until(run)
    over = (cap <= INTMAX and used >= cap) or (ceiling is not None and tokens <= INTMAX and tokens > ceiling)
    limited = state.header(state.text(run), exact_keys=True).get("plan-schema", "") != ""   # opened with agent limits
    stopped = over and limited and (until is None or used >= until)
    return Standing(used, recorded, cap, tokens, ceiling, until, over, stopped)
