"""council gates: the project's configured gates, one line each — its command, when it runs, whether it is
mandatory, its side effects, the paths its Covers cell names, and what its command's text gives away before it runs
(gate_notes) — then how long the checks take, when that is measured. council gates timed <minutes> records it: the
config's `- checks take:` line, which a review's estimate uses."""
from __future__ import annotations

import re

from council import clock
from council.commands import cli
from council.records import config, gate_notes, gate_table, paths
from council.records import home as where

TIMED = ("usage: council gates timed <minutes> — the minutes the project's checks took, a whole number from 1 "
         "to %d" % config.MAX_MINUTES)


def main(args: cli.Args, words: list[str]) -> int:
    if words[:1] == ["timed"]:
        cli.takes_flags(args, "gates timed")
        return timed(words[1:])
    cli.takes_flags(args, "gates")
    cli.no_words("gates", words)
    home = where.council_home()
    cfg = config.path(home).as_posix()
    rows = gate_table.gates(home)
    if not rows:
        if gate_table.gates_listed(home):
            cli.say("the Gates section of %s is in an older layout (a list, not a table), so no gate can run — a "
                    "council-init refresh migrates it" % cfg)
        else:
            cli.say("no gates in %s" % cfg)
    for row in rows:
        cli.say(line(row))
    taken = config.checks_take(home)
    if taken is not None:
        cli.say(took(taken, config.checks_measured(home)))
    return 0


def timed(words: list[str]) -> int:
    """council gates timed <minutes>: the config's `- checks take:` line, replaced where it is, else after
    `- gate time limit:`, else at the end of the Run preferences list."""
    if len(words) != 1 or not re.fullmatch(r"[0-9]{1,12}", words[0]) or config.minutes(words[0]) is None:
        raise cli.Refusal(TIMED + (" (got: %s)" % " ".join(words) if words else ""))
    home = where.council_home()
    settings = config.path(home)
    if not settings.is_file():
        raise cli.Refusal("no %s at %s — %s" % (config.NAME, home, where.NO_SETUP))
    taken, date = int(words[0]), clock.now_date()
    try:
        data = config.with_pref(settings.read_bytes(), config.CHECKS_TAKE, "%d min (measured %s)" % (taken, date),
                                after="gate time limit", at_end=True)
        paths.atomic_write(settings, data, ".config-", keep_mode=True)
    except OSError:
        raise cli.Refusal("couldn't write %s/%s" % (home, config.NAME)) from None
    cli.say(took(taken, date))
    return 0


def took(taken: int, date: str) -> str:
    return "checks take: %d min%s — a review's estimate uses it" % (taken, " (measured %s)" % date if date else "")


def line(row: gate_table.Gate) -> str:
    if row.command == "-":
        return "%s · (no command: its Command cell is empty, so it never runs) · run at: %s · mandatory: %s" % (
            row.name, row.at, row.mandatory)
    said = "%s · %s · run at: %s · mandatory: %s" % (row.name, row.command, row.at, row.mandatory)
    if row.side != "-":
        said += " · side effects: " + row.side
    if row.covers:
        said += " · covers: " + ", ".join(row.covers)
    notes = ([gate_notes.BACKSLASH] if gate_notes.backslash(row.command) else []) \
        + ([gate_notes.WINSWITCH] if gate_notes.winswitch(row.command) else []) + gate_notes.notes(row.command)
    return said + "".join(" · note: the command " + note for note in notes)
