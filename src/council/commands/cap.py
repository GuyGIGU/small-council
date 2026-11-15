"""council cap, cap check and cap allow: where a run stands against its agent stop, the agent gate's decision
(hooks/agent-gate.sh) and the user's go past it; and the note a seat call ends with. references/run/run-accounting.md,
"The stop at the limit".
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from council import clock
from council.commands import cli, resolve
from council.records import events, paths, redact, runs, seats, state_write, usage
from council.records import home as where

TOOLS = ("Agent", "Task", "Workflow")
DETAILS = ("type=", "seat=", "run=", "file=", "hunt=")
GO = 'council cap allow <n> --user-said "<their words>"'
HINT = "the next agent is refused until their go is recorded: " + GO
ASK = "tell the user, and ask before starting more; " + HINT
USAGE = ('usage: council cap [--run <folder>] | cap allow <n> --user-said "…" | cap check [--session ID] [<tool> '
         '[type=… seat=… run=… file=…]]')


def main(args: cli.Args, words: list[str]) -> int:
    """council cap [--run <folder>], cap check [--session ID] [<tool> [type=… seat=… run=… file=…]] and cap allow."""
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
    if sub != "allow":
        raise cli.Refusal(USAGE)
    cli.takes_flags(args, "cap allow", "user-said")
    if len(rest) != 1:
        raise cli.Refusal("usage: council cap allow <n> --user-said \"<the user's words>\" [--run <folder>]")
    if not args.value("user-said").strip(" \t\n\v\f\r"):
        raise cli.Refusal("cap allow needs --user-said \"<the user's own words>\" — their answer, not a summary of it")
    return allow(args, rest[0])


def allow(args: cli.Args, given: str) -> int:
    """The user's go for n more agent runs, filed under the run's event lock, then run.cap_allowed."""
    from council.commands import closed, event_note    # here: `council cap check`, the gate's, loads cap alone (D34)
    n = given.lstrip("0")
    if not re.fullmatch("[0-9]+", given) or not n or len(n) > 4 or int(n) > 1000:
        raise cli.Refusal("cap allow takes how many more agent runs the user allowed, a whole number from 1 to 1000 — "
                          "got: " + given)
    run = resolve.run_folder(args)
    closed.refuse(run, "no more agents start for it; open a new run")
    said, lock = redact.said(args.value("user-said")) or "[redacted]", Path(str(events.path(run)) + ".lock")
    with event_note.locked(lock, "the go was not recorded: the run's event lock is unavailable (%s)" % lock.as_posix()):
        used = _file_go(run, n, said)
    if events.path(run).is_file():
        event_note.append(run, "run.cap_allowed", "run", n, "used=%d;until=%d" % (used, used + int(n)),
                          "the go is on record, but its event could not be written")
    state_write.clear_waiting(run)
    cli.say("cap: the user's go is on record — %s more agent run(s) may start, up to %d in all for %s"
            % (n, used + int(n), run.name))
    return 0


def _file_go(run: Path, n: str, said: str) -> int:
    file, used = seats.path(run, seats.ALLOWANCES), usage.standing(run, where.council_home()).used
    try:
        paths.append_row(file, "at\tused\tn\tuntil\tsaid\n", (clock.now_utc(), str(used), n, str(used + int(n)), said))
    except OSError:
        raise cli.Refusal("the go was not recorded: cannot write " + file.as_posix()) from None
    return used


def note(run: Path) -> None:
    """After a seat call: the run against its cap and ceiling, on stderr; each first passing recorded once."""
    from council.commands import event_note
    stand = usage.standing(run, where.council_home())
    used, tokens, limit, ceiling = stand.used, stand.tokens, stand.cap, stand.ceiling
    if not resolve.field(run, "plan-schema"):
        if used > limit:
            cli.warn("council: this run has used %d agent runs, more than the cap of %d — it was opened before agent "
                     "limits, so new agents are not stopped; tell the user" % (used, limit))
        return
    go = "the user's go covers up to %s agent runs" % stand.until if stand.until is not None and used < stand.until \
        else ""
    estimate, past = usage.agents_share(run), ceiling is not None and tokens > ceiling
    at_cap = "this run has used all %d agent runs of its cap — %s" % (limit, go or "ask the user before starting "
                                                                     "more; " + HINT)
    for line, passed, kind, value, limit_of in (
            ("this run has used %d agent runs, over its cap of %d — %s" % (used, limit, go or ASK) if used > limit
             else at_cap if used == limit else "", used > limit, "cap", used, limit),
            ("", estimate is not None and tokens > estimate, "estimate", tokens, estimate),
            ("this run has used %d tokens, over its ceiling of %s — %s" % (tokens, ceiling, go or ASK) if past else "",
             past, "ceiling", tokens, ceiling)):
        if line:
            cli.warn("council: " + line)
        if passed and events.path(run).is_file():
            event_note.append(run, "run.%s_passed" % kind, "run", str(value), "%s=%s" % (kind, limit_of),
                              "the %s event could not be recorded" % kind, once=True)


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
