"""The ported commands' dispatcher: COMMANDS maps a command's words to one module, imported only on use (D34)."""
from __future__ import annotations

import importlib
import importlib.util
import sys

from council.commands import cli

COMMANDS = {  # a `run <sub>` module's main takes (args, sub, words); every other's (args, words)
    "home": "home",
    "sharing": "sharing",
    "run status": "runs",
    "run plan": "plan",
    "run events": "run_events",
    "run open": "run_open",
    "run resume": "run_resume",
    "run turn-end": "turn_end",
    "run close": "run_close",
    "run session-start": "session_start",
    "run audit": "script_cmds",
    "state": "state",
    "seat": "seat",
    "correct": "correct",
    "cap": "cap",
    "route": "route",
    "gate": "gate",
    "gates": "gate_list",
    "changed": "changed",
    "collect": "collect",
    "check": "check",
    "index": "index",
    "impact": "impact",
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
    "evidence": "script_cmds",
    "tui": "script_cmds",
    "status": "script_cmds",
    "pet": "script_cmds",
    "history": "script_cmds",
    "outcomes": "script_cmds",
    "tune": "tune",
    "repair": "repair",
    "help": "help",
    "version": "help",
}


def main(argv: list[str]) -> int:
    """Run one council command line; the exit code is the command's (2 for a refusal)."""
    _plain_streams()
    try:
        args = cli.parse(argv)
        if not args.words:
            raise cli.Refusal("a flag needs a command — see: council help")
        return _route(args, args.words[0], args.words[1:])
    except cli.Refusal as refusal:
        cli.warn("council: %s" % refusal)
        return 2
    finally:
        sys.stdout.flush()


def _route(args: cli.Args, command: str, words: list[str]) -> int:
    key = command + " " + words[0] if command == "run" and words else command
    name = COMMANDS.get(key)
    if name is None or importlib.util.find_spec("council.commands." + name) is None:   # a row whose module is to come
        raise cli.Refusal("'%s' is not ported to Python yet — run it through bin/council" % " ".join(args.words))
    module = importlib.import_module("council.commands." + name)
    if command == "run":
        return int(module.main(args, words[0], words[1:]))
    return int(module.main(args, words))


def _plain_streams() -> None:
    """UTF-8 with newline endings on every system, as bash prints; bytes a file held that are not UTF-8
    go out as they came in."""
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="surrogateescape", newline="\n")  # type: ignore[attr-defined]
