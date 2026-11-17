"""council pushes and council pushes check: the push freeze, `- pushes:` in the config (issue 49).

council pushes shows how the setting reads today, and whether push and PR are held. council pushes check
<git push|gh pr create> is the bash gate's decision (hooks/bash-gate.sh): silent, exit 0, while pushes are
on or COUNCIL_ALLOW_PUSH=1 is set; while the freeze holds, the reason on stdout and exit 2. A push let through
by COUNCIL_ALLOW_PUSH=1 while the freeze holds is recorded as a run.push_allowed event in the open run, so
council run audit shows it. A fault of its own never stops a push: the hook lets through anything that is not
exit 2 with "Small Council:" on stdout.
"""
from __future__ import annotations

import os

from council.commands import cli, resolve
from council.records import events
from council.records import pushes as freeze
from council.records import home as where

CHECKED = ("git push", "gh pr create")
LOCK_TRIES = 20                         # 2 s at most for the event lock: the hook has 5 s in all


def main(args: cli.Args, words: list[str]) -> int:
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
        return check(" ".join(rest), args)
    raise cli.Refusal("usage: council pushes | pushes check git push|gh pr create")


def check(what: str, args: cli.Args) -> int:
    """The bash gate's decision for one git push or gh pr create."""
    if os.environ.get("COUNCIL_ALLOW_PUSH") == "1":
        allowed(what, args)
        return 0
    held, reading = freeze.pushes(where.council_home())
    if not held:
        return 0
    cli.say("Small Council: %s (`- pushes: %s` in .council/council.config.md), so this %s was stopped. "
            "Record the commit and stop here; push or open the PR only on the user's word, run as "
            "COUNCIL_ALLOW_PUSH=1 %s …, or once the freeze is lifted (`- pushes: on`)."
            % (held[0].upper() + held[1:], reading.split(" (")[0], what, what))
    return 2


def allowed(what: str, args: cli.Args) -> None:
    """The user's escape used while the freeze holds: one run.push_allowed event in the open run, found as every
    command finds its run. Silent: no freeze, no open run, or any fault of its own records nothing and the push
    goes ahead (D20)."""
    try:
        held, reading = freeze.pushes(where.council_home())
        if held:
            events.append(resolve.run_folder(args), "run.push_allowed", "run", what,
                          "freeze=" + reading.split(" (")[0], tries=LOCK_TRIES)
    except Exception:                   # noqa: BLE001 — a refusal, a lost stream, a busy lock: the push still goes
        return
