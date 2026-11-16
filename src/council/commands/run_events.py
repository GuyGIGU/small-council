"""council run events [show|check|repair]: the event stream judged, listed, or its torn last line mended."""
from __future__ import annotations

import os
from pathlib import Path

from council import clock
from council.commands import cli, event_note, resolve
from council.records import events, locks, paths

USAGE = "usage: council run events [show|check|repair]"


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "run events")
    if len(words) > 1:
        raise cli.Refusal(USAGE)
    run = resolve.run_folder(args)
    word = words[0] if words and words[0] else "show"
    if word == "check":
        return check(run)
    if word == "show":
        return check(run) or show(run)
    if word == "repair":
        return repair(run)
    raise cli.Refusal(USAGE)


def check(run: Path) -> int:
    """event_check's lines, each on stdout or (with its 'council: ') stderr; 1 for a stream that fails."""
    code, lines = events.check(run.as_posix())
    for line in lines:
        (cli.warn if line.startswith("council: ") else cli.say)(line)
    return 1 if code else 0


def show(run: Path) -> int:
    """Every row after the header: '<seq>  <at>  <type>  <subject> → <value>  (<detail>)'."""
    file = events.path(run)
    if not file.is_file():
        return 0
    lock = Path(str(file) + ".lock")
    if not locks.acquire(lock):
        cli.warn("council: " + events.busy(lock))
        return 1
    try:
        content = file.read_bytes().decode("utf-8", "surrogateescape")
    finally:
        released = locks.release(lock)
    rows = content.replace("\r\n", "\n").split("\n")[1:]   # a CR before a newline goes, on every OS; a checked
                                                           # stream ends in a newline: no row after it
    for line in rows[:-1]:
        c = (line.split("\t") + [""] * 7)[:7]
        cli.say("%s  %s  %s  %s → %s  (%s)" % tuple(c[1:]))
    return 0 if released else 1


def repair(run: Path) -> int:
    code, why = events.ready(run)
    if code == 0 and not resolve.field(run, "events-schema"):
        cli.say("events: legacy run · no event stream to repair")
        return 0
    if code == 0:
        cli.say("events: nothing to repair — " + events.check(run.as_posix())[1][-1])
        return 0
    if code == 2:
        raise cli.Refusal("events: not repairable — %s; nothing was changed (readers fall back to session-state.md)"
                          % why)
    file = events.path(run)
    lock = Path(str(file) + ".lock")
    copy = "events.tsv.bak-%s-%d" % (clock.now_utc().replace("-", "").replace(":", ""), os.getpid())
    with event_note.locked(lock, "events: the event lock is unavailable: " + lock.as_posix()):
        try:
            data = file.read_bytes()
            if not data or data.endswith(b"\n"):                # another repair got here first
                cli.say("events: nothing to repair — the last line is whole now")
                return 0
            part = len(data) - data.rfind(b"\n") - 1
            (run / copy).write_bytes(data)
            paths.atomic_write(file, data[:len(data) - part], "events.tsv.tmp", keep_mode=True)
        except OSError:
            raise cli.Refusal("events: could not repair %s (the copy, if made, is %s/%s)"
                              % (file.as_posix(), run.as_posix(), copy)) from None
    if events.check(run.as_posix())[0]:
        raise cli.Refusal("events: dropped the torn last line (%d bytes; copy: %s), but the stream still doesn't check "
                          "— council run events check" % (part, copy))
    event_note.need(run, "run.events_repaired", "run", "torn-tail", "dropped=%d;copy=%s" % (part, copy),
                    "events: repaired, but the repair could not be recorded")
    cli.say("events: repaired — dropped the torn last line (%d bytes); the old file is kept as %s" % (part, copy))
    return 0
