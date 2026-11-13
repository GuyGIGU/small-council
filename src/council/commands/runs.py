"""council run status: the council's runs, one line each."""
from __future__ import annotations

import os

from council.commands import cli
from council.records import audit_file
from council.records import home as where
from council.records import runs

SHOWN = 20          # lines of runs before "… and N more"


def main(args: cli.Args, sub: str, words: list[str]) -> int:
    """council run <sub> for the subcommands ported to Python."""
    if sub == "status":
        cli.takes_flags(args, "run status", "all")
        cli.no_words("run status", words)
        return status(bool(args.value("all")))
    raise cli.Refusal("run %s is not ported to Python yet — run it through bin/council" % sub)


def status(every: bool) -> int:
    """Every open run on this tree, then other trees' open runs up to 20 lines in all and a count of the
    rest; with every (--all), the newest 20 runs."""
    home = where.council_home()
    if not os.path.isdir(home):
        cli.say("no council here (no %s) — run council-init" % home)
        return 0
    listed = runs.listing(home, SHOWN, "all") if every else runs.listing(home, 1000000, "open")
    if not listed:
        cli.say("no open council runs" if not every else "no council runs yet")
        return 0
    tree = where.this_tree()
    others, shown = [], 0
    for run in listed:
        here = run.code_root in (tree, "")
        line = "%s · %s · phase %s · %s · updated %s · %s" % (
            run.folder.split("/")[-1], dash(run.mode), dash(run.phase), dash(run.status), dash(run.updated),
            "here" if here else "elsewhere: " + run.code_root)
        line += "".join(" · " + part for part in (run.actual, audit_file.said(run.folder)) if part)
        if here or every:
            cli.say(line)
            shown += 1
        else:
            others.append(line)
    room = max(SHOWN - shown, 0)
    for line in others[:room]:
        cli.say(line)
    if len(others) > room:
        cli.say("… and %d more open in other working trees" % (len(others) - room))
    return 0


def dash(value: str) -> str:
    """A value as the helper's run rows write it: '-' for an empty one."""
    return value or "-"
