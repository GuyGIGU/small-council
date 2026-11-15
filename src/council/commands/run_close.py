"""council run close [--status complete|abandoned|paused]: under the run's close lock, refuse a complete close the
run has not earned, then write the state, the ledger and the close event, say what the close leaves open, and read
the run back with the method audit. A second close waits for the lock, then finds the run closed."""
from __future__ import annotations

import re
from pathlib import Path

from council import clock
from council.commands import cli, close_report, closed, event_note, nudges, resolve
from council.records import closing, events, ledger, locks, seats, state_write, usage
from council.records import home as where

STATUSES = ("complete", "abandoned", "paused")
BASIS = {"legacy": "older"}          # the close event's basis words are the helper's


def main(args: cli.Args, sub: str, words: list[str]) -> int:
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
    try:
        if code == 1:                                     # a torn line: refused with the repair; the lock is left
            events.writable(run)                          # to the stale-lock check, as a close that dies leaves it
    except events.EventError as failure:
        raise cli.Refusal(str(failure)) from None
    held = closing.undelivered(run) if status == "complete" and not state_write.closed(run) else ""
    if held:
        locks.release(lock)
        raise cli.Refusal(held)
    lost = lost if code == 2 else ""
    if lost:
        cli.warn("council: the event stream is lost (%s): the run closes, but its events were not recorded" % lost)
    old = (resolve.field(run, "status"), resolve.field(run, "closed"))
    retake = state_write.closed(run) and old[0] == "complete" and status == "abandoned" and closed.stopped_short(run)
    if state_write.closed(run) and not retake:
        locks.release(lock)
        if old[0] != status:
            closed.refuse(run, "it stays " + old[0])
            raise cli.Refusal("run %s changed while it was being closed — run the close again" % run.name)
        cli.say("%s is already closed — %s at %s; nothing changed" % (run.name, old[0], old[1]))
        close_report.claims_note(run)
        return 0
    _close(run, status, lost, retake, old[0] != status or not old[1])
    locks.release(lock)                                   # once: a second release could free another close's lock
    if old[0] != status or not old[1]:                    # a real close (a status set by hand had none), read back
        close_report.audit(run)
    return 0


def _close(run: Path, status: str, lost: str, retake: bool, real: bool) -> None:
    """The close under its lock: the state, the ledger, the lines it says and the close event."""
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
    if retake:
        ledger.forget(run)
    home = where.council_home()
    _empty_pointer(home, run)
    cli.say("closed %s — %s%s" % (run.name, status, " · " + words if words else ""))
    if busy and status != "abandoned":
        cli.warn("council: seats still marked running or queued: %s — their results will not be collected; wait for "
                 "them, or record each (council seat <slug> failed or skipped) before closing" % busy)
    close_report.claims_note(run)
    codes, follow = _complete(run, home) if status == "complete" else ("", "")
    if real:
        t = totals["tokens"]
        detail = "agent_runs=%d;reported=%d;tokens=%d;basis=%s" % (
            totals["agents"]["at_least"], usage.reported_runs(seat_list), t["known"], BASIS.get(t["basis"], t["basis"]))
        if not lost:
            close_report.chair(run)
            event_note.append(run, "run.paused" if status == "paused" else "run.closed", "run", status,
                              detail + (";warnings=" + codes if codes else ""), "the run is closed, but its close "
                              "event could not be recorded — council run events check --run " + run.name)
        nudges.status_nudge(run, "close", True, follow)


def _complete(run: Path, home: str) -> tuple[str, str]:
    """A complete close's warnings, ledger rows, filed request and build log: the warnings' codes for the close
    event, and the record's follow-up line."""
    found = closing.warnings(run)
    for _, line in found:
        cli.warn("council: " + line)
    rows = ledger.record(run)
    if rows:
        cli.say("ledger: %d seat row(s) recorded — council ledger shows each seat's record" % rows)
    mode = resolve.field(run, "mode")
    if mode in closing.MODES and not resolve.field(run, "ask-saved"):
        cli.warn("council: no request was filed for this run — council ask save --run " + run.name)
    follow = close_report.follow_up(home)
    log = closing.build_log(run, home) if mode == "council-implement" else ""
    if log:
        cli.warn("council: " + log)
    return ",".join(code for code, _ in found), follow


def _empty_pointer(home: str, run: Path) -> None:
    """The 0.1/0.2 single pointer (active-run): emptied when it names this run."""
    pointer = Path(where.native(home)) / "active-run"
    try:
        data = pointer.read_bytes()
        named = data.split(b"\n")[0].replace(b"\r", b"").decode("utf-8", "surrogateescape")
        named = named if re.match("/|[A-Za-z]:", named) else home.rsplit("/", 1)[0] + "/" + named
        if data and where.native(named) == run.as_posix():
            pointer.write_bytes(b"")
    except OSError:
        pass
