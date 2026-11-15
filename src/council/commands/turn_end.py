"""council run turn-end --session ID: the Stop hook's decision (hooks/turn-end.sh)."""
from __future__ import annotations

import os

from council.commands import cli, nudges, resolve
from council.records import config, hook_marks, seats, state_write
from council.records import home as where

DEFERRED = "(it may be a deferred tool: search the tools for it first)"


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "run turn-end", "session")
    cli.no_words("run turn-end", words)
    if args.value("run"):
        raise cli.Refusal("run turn-end looks at every in-progress run this session drives; it does not take --run")
    session = args.value("session")
    if not session:
        return 0
    hook_marks.put(session, "turn-end")            # the Stop hook ran, council project or not
    home = where.council_home()
    if not os.path.isdir(where.native(home + "/runs")):
        return 0
    cards, waiting = [], []
    for run in resolve.session_runs(home, session):
        name = run.split("/")[-1]
        if nudges.card_due(run) and nudges.mark_card(run, "reminded"):
            cards.append(name)
        if any(row.get("state") == "running" for row in seats.rows(run)) or resolve.field(run, "waiting"):
            continue                               # a seat works, or the wait was recorded when it was asked for
        try:
            state_write.change(run, ["waiting=your answer in the chat"])
        except state_write.StateError:
            continue
        if not config.notifications_off(home):
            waiting.append(name)
    said = ""
    if len(cards) > 1:
        said = ("Runs %s made their first dispatch, and the user has not been shown their status: for each, hand the "
                "output of `council status --widget --run <folder>` to a show_widget tool %s, else relay `council "
                "status --run <folder>` — once." % (", ".join(cards), DEFERRED))
    elif cards:
        said = ("Run %s made its first dispatch, and the user has not been shown its status: hand the output of "
                "`council status --widget --run %s` to a show_widget tool %s, else relay `council status --run %s` — "
                "once." % (cards[0], cards[0], DEFERRED, cards[0]))
    if not waiting:
        if said:
            cli.say("Small Council: %s Then end your turn." % said)
        return 2 if said else 0
    at, label = (waiting[0], "run") if len(waiting) == 1 else ("<folder>", "runs")
    cli.say('Small Council: %s%s %s now waits on the user (no seat is working). If you stopped to ask them something: '
            'record the question if you haven\'t (council state waiting="<it, short>" --run %s), then — unless you '
            'already sent the owner an alert for this stop — send the line `council status --line --run %s` prints, '
            'once, with a PushNotification tool %s, and end your turn. If it only waits on a background task, clear it '
            'instead: council state waiting= --run %s.'
            % (said + " " if said else "", label.capitalize() if said else label, ", ".join(waiting), at, at, DEFERRED,
               at))
    return 2
