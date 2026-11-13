"""council gates: the project's configured gates, one line each — its command, when it runs, whether it is
mandatory, its side effects, and what its command's text gives away before it runs (gate_notes)."""
from __future__ import annotations

from council.commands import cli, gate_notes
from council.records import config
from council.records import home as where


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "gates")
    cli.no_words("gates", words)
    home = where.council_home()
    cfg = home + "/council.config.md"
    rows = config.gates(home)
    if not rows:
        if config.gates_listed(home):
            cli.say("the Gates section of %s is in an older layout (a list, not a table), so no gate can run — a "
                    "council-init refresh migrates it" % cfg)
        else:
            cli.say("no gates in %s" % cfg)
        return 0
    for row in rows:
        cli.say(line(row))
    return 0


def line(row: config.Gate) -> str:
    if row.command == "-":
        return "%s · (no command: its Command cell is empty, so it never runs) · run at: %s · mandatory: %s" % (
            row.name, row.at, row.mandatory)
    said = "%s · %s · run at: %s · mandatory: %s" % (row.name, row.command, row.at, row.mandatory)
    if row.side != "-":
        said += " · side effects: " + row.side
    notes = ([gate_notes.BACKSLASH] if gate_notes.backslash(row.command) else []) \
        + ([gate_notes.WINSWITCH] if gate_notes.winswitch(row.command) else []) + gate_notes.notes(row.command)
    return said + "".join(" · note: the command " + note for note in notes)
