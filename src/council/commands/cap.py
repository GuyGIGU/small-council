"""council cap and council cap check: where a run stands against its agent stop, and the agent gate's
decision (hooks/agent-gate.sh). references/run/run-accounting.md, "The stop at the limit".

council cap allow stays in bin/council until the user's words can be redacted (S8) and a state field
written (S8b) from Python.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from council.commands import cli, resolve
from council.records import home as where
from council.records import runs, seats, usage

TOOLS = ("Agent", "Task", "Workflow")
DETAILS = ("type=", "seat=", "run=", "file=", "hunt=")
GO = 'council cap allow <n> --user-said "<their words>"'


def main(args: cli.Args, words: list[str]) -> int:
    """council cap [--run <folder>] and council cap check [--session ID] [<tool> [type=… seat=… run=… file=…]]."""
    sub, rest = (words[0], words[1:]) if words else ("", [])
    if sub == "":
        cli.takes_flags(args, "cap")
        return show(resolve.run_folder(args))
    if sub == "check":
        cli.takes_flags(args, "cap check", "session")
        if args.value("run"):
            raise cli.Refusal("cap check looks at every in-progress run this session may be driving; "
                              "it does not take --run")
        if rest and rest[0] in TOOLS:
            for word in rest[1:]:
                if not (word.startswith(DETAILS) or word == "workflow=verifier"):
                    cli.no_words("cap check", [word])
        else:
            cli.no_words("cap check", rest)
        from council.commands import agent_gate
        return agent_gate.check(args.value("session") or os.environ.get("CLAUDE_CODE_SESSION_ID", ""), rest)
    raise cli.Refusal("cap %s is not ported to Python yet — run it through bin/council" % sub)


def show(run: Path) -> int:
    """Where the run stands, in one or two plain lines."""
    starts, recorded = seats.agent_starts(run), None
    stand = usage.standing(run, where.council_home())
    if starts:
        starts, recorded = starts + seats.workflow_extra(run), stand.recorded
    line = "%s: %d of %d agent runs used" % (run.name, stand.used, stand.cap)
    if recorded is not None and starts > recorded:
        line += " (%d started through the agent gate, %d recorded)" % (starts, recorded)
    if stand.ceiling is not None:
        line += " · %s tokens of a %s ceiling" % (usage.token_text(stand.tokens), usage.token_text(stand.ceiling))
    if stand.until is not None:
        line += " · the user's go allows up to %d" % stand.until
    cli.say(line)
    status = resolve.field(run, "status").split(" ")[0]
    if status != "in-progress":
        cli.say("new agents: not stopped — the stop holds only while a run is in progress (this one is %s)"
                % (status or "without a status"))
    elif not resolve.field(run, "plan-schema"):
        cli.say("new agents: not stopped — this run was opened before plans and agent limits, so the stop does not "
                "hold for it; tell the user when it passes the cap")
    elif stand.stopped:
        cli.say("new agents: stopped until the user says go — then: " + GO)
    elif stand.over:
        cli.say("new agents: may start — %d more under the user's go" % (stand.until - stand.used))
    elif stand.ceiling is None:
        cli.say("new agents: may start — %d more before the cap" % (stand.cap - stand.used))
    else:
        cli.say("new agents: may start — at most %d more before the cap, fewer if tokens pass the ceiling"
                % (stand.cap - stand.used))
    return 0


def words(name: str, stand: usage.Standing) -> str:
    """'run <name> has used 12 of its 10 agent runs and 1.5M tokens, over its 1.2M ceiling' (cap_words)."""
    said = "run %s has used %d of its %d agent runs" % (name, stand.used, stand.cap)
    if stand.ceiling is not None and stand.tokens > stand.ceiling:
        tokens, ceiling = usage.token_text(stand.tokens), usage.token_text(stand.ceiling)
        if tokens == ceiling:                 # 600,400 over 600,000 reads as a number, not "600k over 600k"
            tokens, ceiling = str(stand.tokens), str(stand.ceiling)
        said += " and %s tokens, over its %s ceiling" % (tokens, ceiling)
    if stand.until is not None:
        said += "; the user's last go allowed up to %d" % stand.until
    return said


def open_here(home: str, tree: str, session: str) -> list[str]:
    """The in-progress runs this session may drive: this tree's (a run with no code-root counts as this
    tree's) and, with a session id, the ones it drives on any tree."""
    return [run.folder for run in runs.listing(home, 1000000, "open")
            if run.status == "in-progress" and (run.code_root in (tree, "", "-")
                                                 or (session != "" and (run.session or "-") == session))]


def stamp() -> str:
    """The helper's UTC stamp, now (now_utc)."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
