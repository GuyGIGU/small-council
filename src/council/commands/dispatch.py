"""The ported commands' dispatcher: COMMANDS maps a command's words to one module, imported only on use (D34)."""
from __future__ import annotations

import importlib
import sys

from council.commands import cli

COMMANDS = {"home": "home", "sharing": "sharing", "run status": "runs", "cap": "cap", "run plan": "plan",
            "route": "route"}


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
    if name is None:
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
