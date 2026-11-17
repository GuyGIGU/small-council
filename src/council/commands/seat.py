"""council seat <slug> <state> [agent= tokens= agents= tools= note=] (references/run/run-accounting.md)."""
from __future__ import annotations

import contextlib
import re
from pathlib import Path
from typing import Callable

from council import clock
from council.commands import build_seat, cap, cli, closed, event_note, nudges, plan, resolve, rounds, seat_notes
from council.records import cells, ledger, seat_rows, seat_write, seats, state_write
from council.records import home as where
from council.records import plan as run_plan

USAGE = ("usage: council seat <slug> <queued|running|done|failed|blocked|skipped> [agent=ID] [tokens=N] [agents=N] "
         "[note=TEXT]")
STATES = ("queued", "running", "done", "failed", "blocked", "skipped")
SLUG = re.compile("[A-Za-z0-9._-]*")
ROLES = ("agent", "worker", "verifier", "workflow", "builder", "chair", "explore", "general-purpose", "council-worker",
         "council-verifier", "small-council:council-worker", "small-council:council-verifier")
EXACT = "pass the exact count the usage report gives (like 159812)"
LATE = ("it takes only the Chair's own record (seat <chair> done agents=0) or a seat left working marked failed; a "
        "late agent report goes through: council correct <seat> tokens=… agents=… evidence=\"…\" --run %s")
DUPLICATE = ("council: %s already has this usage report on record, with no agent id to tell two agent runs apart — "
             "not counted again (another agent run needs its agent=<id>: a re-dispatched agent reports as council seat "
             "%s done agent=<new id> tokens=… agents=1; a resumed agent reports its running total under the same agent "
             "id)")


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "seat")
    slug, state = (words + ["", ""])[:2]
    if not slug or not state:
        raise cli.Refusal(USAGE)
    if state not in STATES:
        raise cli.Refusal("seat state must be queued, running, done, failed, blocked or skipped")
    if not SLUG.fullmatch(slug):
        raise cli.Refusal("bad seat slug: " + slug)
    got = _fields(words[2:])
    if (got["tokens"] or got["agents"] or got["tools"]) and state not in ("done", "failed", "blocked"):
        raise cli.Refusal("tokens=, agents= and tools= report a finished agent run — record them with done, failed or "
                          "blocked, not " + state)
    if got["agents"] == "0" and got["tokens"]:
        raise cli.Refusal("agents=0 says no agent ran for this seat — it takes no tokens=")
    run = resolve.run_folder(args)
    closed_out = _closed_out(run, slug, state, got)
    _may_record(run, slug, state, got)
    starting = build_seat.starts(run, slug, state)        # read before the write changes the seat's state
    state_write.clear_waiting(run)                       # the call is good: the run moves on
    lock = Path(str(seats.path(run)) + ".lock")
    with event_note.locked(lock, "seat lock unavailable: " + lock.as_posix(),
                           "seat changed, but its lock could not be released: " + lock.as_posix()):
        first, dup = _record(run, slug, state, got)
    if closed_out and resolve.field(run, "status") == "complete":       # the ledger copies the record
        cli.say("ledger: %d seat row(s) of %s refreshed" % (ledger.record(run), run.name))
    if got["tools"] and not dup:                          # tool calls, kept apart from usage.tsv's columns
        tools = seats.path(run, seat_rows.TOOLS)
        try:
            seat_write.add(tools, [[clock.now_utc(), slug, got["agent"] or seat_rows.cell(run, slug, "agent"),
                                    got["tools"]]], "at\tseat\tagent\ttools")
        except OSError:
            cli.warn("council: the tool-call count was not recorded (%s)" % tools.as_posix())
    seat_notes.report(run, slug, got)
    if starting:
        build_seat.say_outside(run, slug)
    cap.note(run)                                         # the reminders last, so they are seen
    if first:
        nudges.status_nudge(run, "dispatch", bool(args.value("run")))
    return 0


def _tokens(value: str) -> str:
    plain = "\n".join(re.sub("[ \t\v\f\r]*[Tt][Oo][Kk][Ee][Nn][Ss]?$", "", line.strip(" \t\v\f\r"))
                      for line in value.split("\n"))
    if re.search("[kKmM]", plain):
        raise cli.Refusal("tokens=%s is a rounded figure — %s" % (value, EXACT))
    count = cells.token_count(value)
    if value and count is None:
        raise cli.Refusal("tokens= takes one exact token count (74304, 74,304 or 74 304), got: " + value)
    if count is None or count < 1000:
        raise cli.Refusal("tokens=%s is below any real agent run (1,000 tokens) — pass the exact figure the usage "
                          "report gives (like 159812)" % value)
    return str(count)


def _agent(value: str) -> str:
    if not re.fullmatch("[A-Za-z0-9._:-]*", value):
        raise cli.Refusal("agent= takes the id the Agent or Workflow tool returned, got: " + value)
    if value.lower() in ROLES:
        raise cli.Refusal("agent=%s is a role, not an agent id — pass the id the Agent or Workflow tool returned (like "
                          "a0a66e66dae8005a1 or wf_1b2fc8d3-b14), or leave agent= out" % value)
    return value


def _digits(value: str, what: str) -> str:
    if not re.fullmatch("[0-9]+", value):
        raise cli.Refusal("%s, got: %s" % (what, value))
    return value


def _agents(value: str) -> str:
    if int(_digits(value, "agents= takes how many agent runs this report covers (0 = none ran)")) > 1000:
        raise cli.Refusal("agents= takes a count from 0 to 1000, got: " + value)
    return value


def _tools(value: str) -> str:
    if len(_digits(value, "tools= takes the tool calls the notification reports (tool_uses), a whole number")) > 6:
        raise cli.Refusal("tools= takes a count up to 999999, got: " + value)
    return value


CHECKS: dict[str, Callable[[str], str]] = {"agent": _agent, "tokens": _tokens, "agents": _agents, "tools": _tools,
                                           "note": lambda v: re.sub("[\t\r\n\v\f]", " ", v)}


def _fields(words: list[str]) -> dict[str, str]:
    got = dict.fromkeys(CHECKS, "")
    for word in words:
        key, equals, value = word.partition("=")
        if not equals or key not in CHECKS:
            raise cli.Refusal("unknown seat field: %s (use agent=, tokens=, agents=, tools=, note=)" % word)
        got[key] = CHECKS[key](value)
    return got


def _closed_out(run: Path, slug: str, state: str, got: dict[str, str]) -> bool:
    """A closed run takes only a close-out that keeps every counted figure; True when the run is closed."""
    if not state_write.closed(run):
        return False
    key = (state, got["agents"], got["tokens"] + got["agent"], seat_rows.cell(run, slug, "state"),
           seat_rows.cell(run, slug, "agent"))
    chair = any((r.get("kind"), r.get("id"), r.get("field"), r.get("value")) == ("seat", slug, "role", "chair")
                for r in run_plan.rows(run))
    if not ((key == ("done", "0", "", "", "") and chair) or key == ("skipped", "", "", "queued", "")
            or (key[:3] == ("failed", "", "") and key[3] in ("running", "queued"))):
        closed.refuse(run, LATE % run.name)
    return True


def _may_record(run: Path, slug: str, state: str, got: dict[str, str]) -> None:
    """The refusals that read the run before anything is written."""
    missing = seat_write.missing_file(run, slug) or build_seat.missing_report(run, slug, got["note"]) \
        if state == "done" and got["agents"] != "0" else ""
    if missing:
        raise cli.Refusal("seat %s has no file yet (%s), so it isn't done — resume its agent with SendMessage "
                          "(\"write your file now with what you have, then finish\"), or record it: council seat %s "
                          "failed note=\"…\"" % (slug, missing, slug))
    event_note.writable(run)
    if got["agents"] == "0" and (got["agent"] or seat_rows.cell(run, slug, "agent")):
        raise cli.Refusal("agents=0 says no agent ran for %s, but an agent id is on record for it — report that "
                          "agent's usage instead" % slug)
    if any(fix["added"] for (seat, _), fix in seats.corrections(run).items() if seat == slug):
        raise cli.Refusal("%s was added from evidence as an agent run the record missed — record new work under a new "
                          "slug: council seat <new slug> running agent=<id> (with its own run-plan rows); %s's row "
                          "stays as corrected" % (slug, slug))
    if state in ("queued", "running"):
        plan.require(run, "start seat " + slug)
        if run_plan.path(run).is_file() and not run_plan.selected(run, slug):
            raise cli.Refusal("cannot start seat %s — run-plan.tsv does not mark it selected; update the plan and "
                              "run: council run plan check --run %s" % (slug, run.name))
        why = rounds.batch_check(run, slug, where.council_home()) or rounds.check_round(run, slug) \
            or build_seat.start_refusal(run, slug)
        if why:
            raise cli.Refusal(why)


def _same(a: str, b: str) -> bool:
    """Two cells equal as awk compares them: as numbers when both are."""
    return a == b or bool(re.fullmatch("[0-9]+", a) and re.fullmatch("[0-9]+", b) and int(a) == int(b))


def _record(run: Path, slug: str, state: str, got: dict[str, str]) -> tuple[bool, bool]:
    """usage.tsv's rows, the seat's row and its seat.updated event; (the run's first dispatch, a repeated report)."""
    file, use = seats.path(run), seats.path(run, seats.USAGE)
    with contextlib.suppress(OSError):
        seat_write.add(file, [], "\t".join(seat_write.HEADER))
    try:
        seat_write.add(use, [], "at\tseat\tagent\tkind\truns\ttokens")
        cur = seat_rows.cell(run, slug, "agent")
        first = bool(got["agent"]) and got["agent"] != cur
        if first:
            first = not any(c[3] == "dispatched" for c in seat_write.table(use)[1:])
            seat_write.add(use, [[clock.now_utc(), slug, got["agent"], "dispatched", "", ""]], "")
        report, runs, agent = got["tokens"] or got["agents"], got["agents"] or "1", got["agent"] or cur
        dup = bool(report) and not agent and any(
            c[1:4] == [slug, "", "finished"] and _same(c[4], runs) and _same(c[5], got["tokens"])
            for c in seat_write.table(use)[1:])
        if dup:
            cli.warn(DUPLICATE % (slug, slug))
        elif report:
            seat_write.add(use, [[clock.now_utc(), slug, agent, "finished", runs, got["tokens"]]], "")
    except OSError:
        raise cli.Refusal("cannot write " + use.as_posix()) from None
    agents, reported, tokens, declared = seat_write.seat_usage(run, slug)
    new = dict(got, state=state, updated=clock.now_min(), total=str(tokens) if tokens > 0 else "",
               agents=str(agents) if agents > 0 or declared else "", reported=str(reported))
    try:
        seat_write.rewrite(run, slug, new)
    except OSError:
        raise cli.Refusal("cannot update " + file.as_posix()) from None
    event_note.need(run, "seat.updated", slug, state, "tokens=%s;agent_runs=%s;reported=%s" % tuple(
        seat_rows.cell(run, slug, column) for column in ("tokens", "agents", "reported")),
        "seat changed, but its event could not be recorded")
    return first, dup


def taken(run: Path, slug: str) -> str | None:
    """The agent gate's record of a council-builder going out for build seat <slug>: under the seat lock,
    build_seat.dispatch_refusal is asked again and, with none, the queued seat is recorded running with no agent
    yet. So of two builders sent for one seat, together or before the Chair records the first one's agent, the
    second is refused. That refusal; None once the seat is taken, for any other seat, and when the record can't be
    taken (the gate lets the call through on its own fault, D20)."""
    if build_seat.task_of(run, slug) is None:
        return None
    lock = Path(str(seats.path(run)) + ".lock")
    try:
        with event_note.locked(lock, "seat lock unavailable: " + lock.as_posix()):
            why = build_seat.dispatch_refusal(run, slug)
            if why is None:
                _record(run, slug, "running", dict.fromkeys(CHECKS, ""))
    except (cli.Refusal, OSError):
        return None
    return why
