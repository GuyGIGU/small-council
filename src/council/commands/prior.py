"""council prior [path …]: the earlier council work that mentions these paths (by default the files the run's change
index lists) — a deliverable line that names one, or a deliverable whose areas: cover it — 40 at most, for the
brief's Landscape."""
from __future__ import annotations

from council.commands import cli, resolve
from council.records import bytewise, earlier
from council.records import home as where
from council.records.run_files import INDEX

SHOWN = 40


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "prior")
    home = where.council_home()
    if words:
        paths = [bytewise.text(word) for word in words]
    else:
        run = resolve.run_folder(args)
        if not (run / INDEX).is_file():
            raise cli.Refusal("no paths given and no change index in this run — pass them: council prior <path> …")
        paths = earlier.indexed(run)
    found = earlier.hits(home, paths)
    if not found:
        cli.say("prior: no earlier council work mentions these paths")
        return 0
    for row in found[:SHOWN]:
        cli.say(bytewise.shown(earlier.line(row)))
    if len(found) > SHOWN:
        cli.say("prior: %d of %d mention(s) shown — list them in the brief's Landscape as ids plus one line; pass "
                "fewer paths to see the rest" % (SHOWN, len(found)))
    else:
        cli.say("prior: %d mention(s) — list them in the brief's Landscape as ids plus one line" % len(found))
    return 0
