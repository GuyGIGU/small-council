"""council pushes and council pushes check: the push freeze, `- pushes:` in the config (issue 49).

council pushes shows how the setting reads today, and whether push and PR are held. council pushes check
<git push|gh pr create> is the bash gate's decision (hooks/bash-gate.sh): silent, exit 0, while pushes are
on or COUNCIL_ALLOW_PUSH=1 is set; while the freeze holds, the reason on stdout and exit 2. A fault of its
own never stops a push: the hook lets through anything that is not exit 2 with "Small Council:" on stdout.
"""
from __future__ import annotations

import os

from council.commands import cli
from council.records import pushes as freeze
from council.records import home as where

CHECKED = ("git push", "gh pr create")


def main(args: cli.Args, words: list[str]) -> int:
    """council pushes [check <git push|gh pr create>]."""
    sub, rest = (words[0], words[1:]) if words else ("", [])
    if sub == "":
        cli.takes_flags(args, "pushes")
        held, reading = freeze.pushes(where.council_home())
        cli.say("pushes: " + reading + (" — " + held if held else ""))
        return 0
    if sub == "check":
        cli.takes_flags(args, "pushes check")
        if " ".join(rest) not in CHECKED:
            raise cli.Refusal("pushes check takes the command the bash gate found: git push or gh pr create")
        return check(" ".join(rest))
    raise cli.Refusal("usage: council pushes | pushes check git push|gh pr create")


def check(what: str) -> int:
    """The bash gate's decision for one git push or gh pr create."""
    held, reading = ("", "") if os.environ.get("COUNCIL_ALLOW_PUSH") == "1" else freeze.pushes(where.council_home())
    if not held:
        return 0
    cli.say("Small Council: %s (`- pushes: %s` in .council/council.config.md), so this %s was stopped. "
            "Record the commit and stop here; push or open the PR only on the user's word, run as "
            "COUNCIL_ALLOW_PUSH=1 %s …, or once the freeze is lifted (`- pushes: on`)."
            % (held[0].upper() + held[1:], reading.split(" (")[0], what, what))
    return 2
