"""The ported commands' dispatcher: bin/council hands each of them here with the words it was given."""
from __future__ import annotations

import sys

from council.commands import cli, home, runs, sharing


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
    if command == "home":
        return home.main(args, words)
    if command == "sharing":
        return sharing.main(args, words)
    if command == "run" and words[:1] == ["status"]:
        return runs.main(args, words[0], words[1:])
    raise cli.Refusal("'%s' is not ported to Python yet — run it through bin/council" % " ".join(args.words))


def _plain_streams() -> None:
    """UTF-8 with newline endings on every system, as bash prints; bytes a file held that are not UTF-8
    go out as they came in."""
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="surrogateescape", newline="\n")  # type: ignore[attr-defined]
