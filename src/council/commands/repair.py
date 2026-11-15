"""council repair record|show|check|allow: a build's gate failures and repair outcomes (scripts/repair.py), and for a
gate whose trail stopped at three failures the user's go, in their words, in <run>/repair-allowances.tsv under the
run's event lock, then a repair.allowed event. The stopped trail stays closed: a later failure starts a new task."""
from __future__ import annotations

import contextlib
import io
from pathlib import Path

from council import clock
from council.commands import cli, closed, event_note, resolve
from council.commands.script_cmds import run_script
from council.records import events, locks, redact, repairs, state_write

USAGES = {"record": "usage: council repair record <task> <gate> [--run <folder>]",
          "show": "usage: council repair show [task] [--run <folder>]",
          "check": "usage: council repair check [task] [--run <folder>]",
          "allow": "usage: council repair allow <gate> --user-said \"<the user's words>\" [--run <folder>]"}
SPACE = " \t\n\v\f\r"


def main(args: cli.Args, words: list[str]) -> int:
    sub, words = (words[0], words[1:]) if words else ("", [])
    if sub not in USAGES:
        raise cli.Refusal("usage: council repair record <task> <gate> | repair show|check [task] | repair allow "
                          "<gate> --user-said \"…\"")
    cli.takes_flags(args, "repair " + sub, *(("user-said",) if sub == "allow" else ()))
    if not {"record": len(words) == 2, "allow": len(words) >= 1}.get(sub, len(words) <= 1):
        raise cli.Refusal(USAGES[sub])
    said = args.value("user-said")
    if sub == "allow" and not said.strip(SPACE):
        raise cli.Refusal("repair allow needs --user-said \"<the user's own words>\" — their answer, not a summary "
                          "of it")
    run = resolve.run_folder(args)
    if sub in ("record", "allow"):
        closed.refuse(run, "its repair trail is on record (council repair show)")
    if sub != "allow":
        return run_script("repair", [sub] + words + ["--run", run.as_posix()])
    return allow(run, " ".join(words), said)


def allow(run: Path, gate: str, said: str) -> int:
    trail = io.StringIO()
    with contextlib.redirect_stdout(trail):
        code = run_script("repair", ["trail", gate, "--run", run.as_posix()])
    if code:
        return 2
    if trail.getvalue().startswith("allowed\t"):
        cli.say("repair: the user's go for gate %s is already on record — it may run" % gate)
        return 0
    if not trail.getvalue().startswith("stop\t"):
        raise cli.Refusal("gate %s has no stopped repair trail in %s — there is nothing to allow" % (gate, run.name))
    task, seq = (trail.getvalue().rstrip("\n").split("\t") + [""])[1:3]
    lock = Path(str(events.path(run)) + ".lock")
    if not locks.acquire(lock):
        raise cli.Refusal("%s\ncouncil: the go was not recorded: the run's event lock is unavailable (%s)"
                          % (events.busy(lock), lock.as_posix()))
    try:
        repairs.allow(run, (clock.now_utc(), gate, task, seq, redact.said(said) or "[redacted]"))
    except OSError:
        raise cli.Refusal("the go was not recorded: cannot write " + (run / repairs.ALLOWANCES).as_posix()) from None
    finally:
        locks.release(lock)
    event_note.append(run, "repair.allowed", gate, task, "stop_seq=" + seq,
                      "the go is on record, but its event could not be written")
    state_write.clear_waiting(run)
    cli.say("repair: the user's go is on record — gate %s may run again; %s's trail stays closed, so a new failure is "
            "recorded under a new task id (the gate names one)" % (gate, task))
    return 0
