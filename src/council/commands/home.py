"""council home [rule]: where the council lives, and the Edit permission rule for it."""
from __future__ import annotations

import re

from council.commands import cli
from council.records import home as where


def main(args: cli.Args, words: list[str]) -> int:
    """council home prints the council home; council home rule prints its Edit rule."""
    cli.takes_flags(args, "home")
    first = words[0] if words else ""
    if first == "":
        cli.say(where.council_home())
    elif first == "rule":
        cli.no_words("home rule", words[1:])
        cli.say(rule(where.council_home()))
    else:
        raise cli.Refusal("usage: council home [rule]")
    return 0


def rule(home: str) -> str:
    """The Edit permission rule for a home's real path, as Claude Code matches it: an absolute path after
    //, and a Windows drive as /c/… (lower case, no colon); a //C:/… rule never matches anything."""
    if re.match(r"[A-Za-z]:/", home):
        home = "/" + home[0].lower() + home[2:]
    return "Edit(/%s/**)" % home
