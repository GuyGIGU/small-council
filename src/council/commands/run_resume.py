"""council run resume [--run <folder>]: an open run in progress again, driven by this session."""
from __future__ import annotations

import os
from pathlib import Path

from council.commands import cli, event_note, resolve
from council.records import runs, state, state_write
from council.records import home as where


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "run resume", "session")
    cli.no_words("run resume", words)
    home, tree = where.council_home(), where.this_tree()
    if args.value("run"):
        run = resolve.run_folder(args)
    else:
        mine = resolve.open_runs(home, tree)
        if not mine:
            raise cli.Refusal("no open run on this working tree to resume — council run status lists the runs")
        if len(mine) > 1:
            raise cli.Refusal("several runs are open on this working tree — pass --run <folder>: "
                              + resolve.names(mine))
        run = Path(mine[0])
    status, old = resolve.field(run, "status").split(" ")[0], resolve.field(run, "session")
    if status in ("complete", "abandoned"):
        raise cli.Refusal("%s is closed (%s) — open a new run instead: council run open %s"
                          % (run.name, status, runs.skill(resolve.field(run, "mode"))))
    session = args.value("session") or os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    try:
        state_write.change(run, ["status=in-progress", "session=" + session])
    except state_write.StateError as failure:
        raise cli.Refusal(str(failure)) from None
    _unclose(run)
    event_note.need(run, "run.resumed", "run", "in-progress", "from=%s;was=%s" % (status, old),
                    "run resumed, but its event could not be recorded")
    cli.say("resumed %s — in progress · phase %s · %s" % (run.name, resolve.field(run, "phase"),
                                                           "driven by this session" if session
                                                           else "no session id to record"))
    if old and old != session:
        cli.say("it was driven by session %s — if that session is still open, it may still be working on this run: "
                "ask the user before re-dispatching any seat" % old)
    seats = runs.seat_summary(run)
    if seats:
        cli.say("seats — " + seats)
    others = resolve.names([f for f in resolve.open_runs(home, tree, "in-progress") if f.split("/")[-1] != run.name])
    if others:
        cli.warn("council: another run is in progress on this working tree (%s) — pass --run %s to every command for "
                 "this one" % (others, run.name))
    croot = resolve.field(run, "code-root")
    if croot and croot != tree and os.path.isdir(where.native(croot)):
        cli.warn("council: its code root is %s, not this working tree — work there" % croot)
    elif croot and croot != tree:
        cli.warn("council: its code root %s no longer exists — the run cannot go on; close it: council run close --run "
                 "%s --status abandoned" % (croot, run.name))
    return 0


def _unclose(run: Path) -> None:
    """Under the state lock, the header's closed: and actual: lines dropped."""
    file = state.path(run)
    lock = Path(str(file) + ".lock")
    with event_note.locked(lock, "state lock unavailable: " + lock.as_posix()):
        try:
            kept, body = "", False
            for line in state_write.raw_lines(file):
                body = body or line.startswith("## ")
                kept += line + "\n" if body or not line.startswith(("closed:", "actual:")) else ""
            state_write.replace(file, kept)
        except OSError:
            raise cli.Refusal("cannot update " + file.as_posix()) from None
