"""The helper's dispatcher: COMMANDS maps a command's words to one module, imported only on use (D34)."""
from __future__ import annotations

import importlib
import sys

from council.commands import cli

COMMANDS = {  # each module's main takes (args, the words after the command's own)
    "home": "home",
    "sharing": "sharing",
    "init": "init",
    "run status": "runs",
    "run plan": "plan",
    "run events": "run_events",
    "run open": "run_open",
    "run resume": "run_resume",
    "run turn-end": "turn_end",
    "run close": "run_close",
    "run session-start": "session_start",
    "run audit": "script_cmds",
    "run export": "run_export",
    "state": "state",
    "seat": "seat",
    "correct": "correct",
    "cap": "cap",
    "gate": "gate",
    "gates": "gate_list",
    "changed": "changed",
    "collect": "collect",
    "check": "check",
    "index": "index",
    "prior": "prior",
    "map": "map_status",
    "fingerprint": "fingerprint",
    "ledger": "ledger",
    "ask": "ask",
    "memory": "memory",
    "doctor": "doctor",
    "pushes": "pushes",
    "patch": "patch",
    "context": "context",
    "tree": "tree",
    "evidence": "script_cmds",
    "status": "script_cmds",
    "repair": "repair",
    "help": "help",
    "version": "help",
}
RUN_WORDS = {  # what each `run` sub takes, for its usage line; a sub of COMMANDS with no entry is shown bare
    "open": "<mode>", "status": "[--all]", "close": "[--status …]", "resume": "[--run <folder>]",
    "plan": "[check|show]", "events": "[show|check|repair]", "audit": "[--transcript <file>]",
    "export": "--anon <run> <dest>", "turn-end": "--session ID",
}
USAGES = {  # a sub of `run` or `cap` with no row; run's is built from COMMANDS, so no sub is left out of it
    "run": "usage: council " + " | ".join(" ".join(["run", key[4:]] + [RUN_WORDS.get(key[4:], "")]).strip()
                                         for key in COMMANDS if key.startswith("run ")),
    "cap": 'usage: council cap [--run <folder>] | cap allow <n> --user-said "…" | cap check [--session ID] '
           "[<tool> [type=… seat=… run=… file=…]]",
}
CAP_SUBS = ("", "check", "allow")
TOP = {key.split(" ")[0] for key in COMMANDS}
RETIRED = {  # a command 1.2.0 removed (D44), by its words, and what to do instead
    "route": "size the run from the doctrine's size limits and the config's `- estimates:` line, record it in "
             "run-plan.tsv, then: council run plan check",
    "ledger advice": "council ledger [N] shows each seat's record over the last N runs; weigh it from there",
    "evidence show": "the claims and their verdicts are in <run>/claims.jsonl, which council evidence check builds "
                     "and checks; council status counts them",
}


def main(argv: list[str]) -> int:
    """Run one council command line; the exit code is the command's (2 for a refusal)."""
    _plain_streams()
    try:
        try:
            args = cli.parse(argv)
        except cli.Refusal:
            _retired([word for word in argv if not word.startswith("-")])   # its old flags are unknown now
            raise
        _retired(args.words)
        if args.flags and not args.words:
            raise cli.Refusal("a flag needs a command — see: council help")
        return _route(args, args.words[0], args.words[1:]) if args.words else _usage()
    except cli.Help:
        return _usage()
    except cli.Refusal as refusal:
        cli.warn("council: %s" % refusal)
        return 2
    finally:
        sys.stdout.flush()


def _route(args: cli.Args, command: str, words: list[str]) -> int:
    key = command + " " + words[0] if command == "run" and words else command
    if command not in TOP:
        raise cli.Refusal("unknown command '%s' — see: council help" % command)
    if key not in COMMANDS or (command == "cap" and words[:1] and words[0] not in CAP_SUBS):
        raise cli.Refusal(USAGES[command])
    name = COMMANDS[key]
    module = importlib.import_module("council.commands." + name)
    return int(module.main(args, words[1:] if command == "run" else words))


def _retired(words: list[str]) -> None:
    """Refuse a removed command as an unknown one, naming what to do instead (D19)."""
    for key in (" ".join(words[:2]), " ".join(words[:1])):
        if key in RETIRED:
            raise cli.Refusal("unknown command '%s' — removed in 1.2.0: %s" % (key, RETIRED[key]))


def _usage() -> int:
    return int(importlib.import_module("council.commands.help").usage())


def _plain_streams() -> None:
    """UTF-8 with newline endings on every system, as bash prints; bytes a file held that are not UTF-8
    go out as they came in."""
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="surrogateescape", newline="\n")  # type: ignore[attr-defined]
