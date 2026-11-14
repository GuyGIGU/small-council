"""council doctor's hook report (issue 69): one line per hook of the plugin, live or not seen in this session.

A hook is live when it has fired in this session (records/hook_marks.py). A hook whose event has not happened yet
is not broken, so the report says when each one first runs. Two hooks have run by the time doctor does, if the
plugin was loaded: SessionStart, which ran when the session began, and the bash gate, which runs before the Bash
call that carries `council doctor`. Either one missing is a finding naming the fix.
"""
from __future__ import annotations

import os

from council.commands import cli
from council.commands.doctor import Doctor
from council.records import hook_marks

EXPECTED = ("session-start", "bash-gate")      # the hooks that have run by the time doctor does
NO_SESSION = ("hooks: not known — this shell has no Claude Code session id; "
              "run council doctor from a Claude Code session")


def session_id(args: cli.Args) -> str:
    """The session asked about: --session, else the one Claude Code gave this Bash call."""
    return args.value("session") or os.environ.get("CLAUDE_CODE_SESSION_ID", "")


def count_line(session: str) -> str:
    """'hooks: 3 of 5 live', with what the rest are waiting for when any is missing."""
    live, total = len(hook_marks.seen(session)), len(hook_marks.HOOKS)
    line = "hooks: %d of %d live" % (live, total)
    return line if live == total else line + " — the rest show as they fire (council doctor lists them)"


def report(doc: Doctor, session: str) -> None:
    """The per-hook lines, the count, and a finding for a hook that must have run by now."""
    if not session:
        cli.say(NO_SESSION)
        return
    live = hook_marks.seen(session)
    for hook, event, first in hook_marks.HOOKS:
        cli.say("hook %-12s  %s" % (event, "live" if hook in live else "not seen in this session (runs %s)" % first))
    cli.say(count_line(session))
    for hook, event, _ in hook_marks.HOOKS:
        if hook in EXPECTED and hook not in live:
            doc.warn("the %s hook has not run in this session: the plugin was enabled or updated after it began, so "
                     "Small Council's hooks may not run here" % event, "restart the session")


def main(args: cli.Args, words: list[str]) -> int:
    """council doctor hooks [--session ID] [--line]: this report alone; --line is its count, for the session banner."""
    cli.no_words("doctor hooks", words)
    session = session_id(args)
    if args.value("line"):
        if session:
            cli.say(count_line(session))
        return 0
    report(Doctor(""), session)
    return 0
