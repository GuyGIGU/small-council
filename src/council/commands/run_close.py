"""council run close [--status complete|abandoned|paused], under the run's close lock."""
from __future__ import annotations

from pathlib import Path

from council import clock
from council.commands import cli, close_report, closed, event_note, nudges, resolve
from council.records import audit_file, closing, events, locks, seats, state_write, usage
from council.records import home as where

STATUSES = ("complete", "abandoned", "paused")
BASIS = {"legacy": "older"}          # the close event's basis words are the helper's


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "run close", "status")
    cli.no_words("run close", words)
    status = args.value("status") or "complete"
    if status not in STATUSES:
        raise cli.Refusal("--status must be complete, abandoned or paused")
    run = resolve.run_folder(args)
    lock = run / "close.lock"
    if not locks.acquire(lock):
        cli.warn("council: " + events.busy(lock))
        raise cli.Refusal("close lock unavailable: %s — another close of this run is still going; if none is, "
                          "remove that folder and close again" % lock.as_posix())
    code, lost = events.ready(run)
    if code == 1:                                         # a torn line: refused with the repair; the lock is left
        event_note.writable(run)                          # to the stale-lock check, as a close that dies leaves it
    held = closing.undelivered(run) if status == "complete" and not state_write.closed(run) else ""
    if held:
        locks.release(lock)
        raise cli.Refusal(held)
    lost = lost if code == 2 else ""
    if lost:
        cli.warn("council: the event stream is lost (%s): the run closes, but its events were not recorded" % lost)
    old = (resolve.field(run, "status"), resolve.field(run, "closed"))
    retake = state_write.closed(run) and old[0] == "complete" and status == "abandoned" and closing.stopped_short(run)
    if state_write.closed(run) and not retake:
        added = _finished(run, lost) if old[0] == status == "complete" else []
        locks.release(lock)
        if old[0] != status:
            closed.refuse(run, "it stays %s; for more work, open a new run: council run open %s"
                          % (old[0], resolve.field(run, "mode") or "<mode>"))
            raise cli.Refusal("run %s changed while it was being closed — run the close again" % run.name)
        cli.say("%s is already closed — %s at %s; %s" % (run.name, old[0], old[1], "the close stopped before its own "
                "records, now done: " + ", ".join(added) if added else "nothing changed"))
        close_report.claims_note(run, old[0])           # the index first, so the audit it saves reads it current
        if old[0] == "complete" and not audit_file.present(run):
            close_report.audit(run)
        return 0
    _close(run, status, lost, old[0] != status or not old[1])
    locks.release(lock)                                   # once: a second release could free another close's lock
    if old[0] != status or not old[1]:                    # a real close (a status set by hand had none), read back
        close_report.audit(run)
    return 0


def _close(run: Path, status: str, lost: str, real: bool) -> None:
    """The close under its lock: the state, the lines it says and the close event."""
    seat_list = usage.seat_list(run)
    totals = usage.usage_totals(seat_list)
    words = closing.actual(run, totals)
    busy = ", ".join(row.get("slug", "") for row in seats.rows(run) if row.get("state") in ("running", "queued"))
    try:
        changed = state_write.change(run, ["status=" + status, "closed=" + clock.now_sec()] +
                                     ["actual=" + words] * bool(words), closing=True, events_lost=bool(lost))
    except state_write.StateError as failure:
        raise cli.Refusal(str(failure)) from None
    for line in changed.warnings:
        cli.warn("council: " + line)
    home = where.council_home()
    cli.say("closed %s — %s%s" % (run.name, status, " · " + words if words else ""))
    if busy and status != "abandoned":
        cli.warn("council: seats still marked running or queued: %s — their results will not be read; wait for "
                 "them, or record each (council seat <slug> failed or skipped) before closing" % busy)
    close_report.claims_note(run, status)
    codes = _complete(run, home) if status == "complete" else ""
    if real:
        detail = _detail(seat_list, totals)
        if not lost:
            close_report.chair(run)
            event_note.append(run, "run.paused" if status == "paused" else "run.closed", "run", status,
                              detail + (";warnings=" + codes if codes else ""), "the run is closed, but its close "
                              "event could not be recorded — council run events check --run " + run.name)
        nudges.status_nudge(run, "close", True)


def _detail(seat_list: list, totals: dict) -> str:
    """The close event's detail: the agent runs, how many reported, the tokens and their basis."""
    t = totals["tokens"]
    return "agent_runs=%d;reported=%d;tokens=%d;basis=%s" % (
        totals["agents"]["at_least"], usage.reported_runs(seat_list), t["known"], BASIS.get(t["basis"], t["basis"]))


def _finished(run: Path, lost: str) -> list:
    """A complete close's own record, when the close that set the state stopped before it: its close event, added
    once. What it added, as words."""
    added = []
    seat_list = usage.seat_list(run)
    detail = _detail(seat_list, usage.usage_totals(seat_list))
    if not lost and event_note.append(run, "run.closed", "run", "complete", detail, "its close event could not be "
                                      "recorded — council run events check --run " + run.name, once=True):
        added.append("the close event")
    return added


def _complete(run: Path, home: str) -> str:
    """A complete close's warnings, request and build log: the warning codes."""
    found = closing.warnings(run)
    for _, line in found:
        cli.warn("council: " + line)
    mode = resolve.field(run, "mode")
    if mode in closing.MODES and not resolve.field(run, "ask-saved"):
        cli.warn("council: no request was filed for this run — council ask save --run " + run.name)
    log = closing.build_log(run, home) if mode == "council-implement" else ""
    if log:
        cli.warn("council: " + log)
    return ",".join(code for code, _ in found)

