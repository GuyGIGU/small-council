"""The helper's command line: its flags, as bin/council's main() read them, and its refusals. bin/council only
starts Python, so every command's words reach this module as typed."""
from __future__ import annotations

import sys
from typing import Iterable, NamedTuple

# Flags that take a value, with what the refusal says is missing.
VALUED = ("run", "code-root", "status", "base", "at", "proof", "session", "task", "risk", "complexity",
          "uncertainty", "surface", "agent-cap", "budget-tokens", "expand", "scope", "user-said", "pose",
          "exit-after", "transcript", "glob", "round")
GATE_VALUED = ("timeout", "invalid", "seat", "mode")   # gate's and route's own: "needs a value" whatever the flag
SWITCHES = ("alongside", "all", "classic", "json", "watch", "widget", "line", "preview", "stop", "demo",
            "still", "wait", "rerun", "each", "anon")
REPEATED = ("surface", "expand", "glob")
MISSING = {"run": "a folder", "code-root": "a folder", "base": "a ref", "at": "grounding or verify"}


class Refusal(Exception):
    """A refusal or usage error: 'council: <message>' on stderr, exit 2. The message names the next step (D19)."""


class Help(Exception):
    """-h or --help, met among the flags: the command list is printed, exit 0."""


class Args(NamedTuple):
    """What the command line said: the words, the flags in the order given, and each flag's value."""

    words: list[str]
    flags: list[str]
    values: dict[str, str]
    lists: dict[str, list[str]]
    after: list[str]

    def value(self, flag: str) -> str:
        """A flag's value, '' when it was not given ('1' for a switch that was)."""
        return self.values.get(flag, "")


def parse(argv: list[str]) -> Args:
    """The words and flags of a council command line, refusing what bin/council's main() refused."""
    words: list[str] = []
    flags: list[str] = []
    values: dict[str, str] = {}
    lists: dict[str, list[str]] = {name: [] for name in REPEATED}
    after: list[str] = []
    rest = list(argv)
    while rest:
        word = rest.pop(0)
        taken = _flag(word, rest, words)
        if taken is None:
            continue
        if taken == ("--", ""):
            after = rest
            break
        flag, value = taken
        if not value:
            raise Refusal("--%s needs a value" % flag)
        if flag in REPEATED:
            lists[flag].append(value)
        values[flag] = value
        flags.append(flag)
    return Args(words, flags, values, lists, after)


def _flag(word: str, rest: list[str], words: list[str]) -> tuple[str, str] | None:
    """(flag, value) for a flag, ('--', '') for the end of the flags, None for a word (added to words)."""
    name, equals, value = word[2:].partition("=")
    if word == "--":
        return ("--", "")
    if word in ("-h", "--help"):
        raise Help
    if word.startswith("--") and name in VALUED + GATE_VALUED:
        if equals:
            return (name, value)
        if not rest:
            raise Refusal("--%s needs %s" % (name, MISSING.get(name, "a value")))
        return (name, rest.pop(0))
    if word.startswith("--") and name in SWITCHES:
        if not equals:
            return (name, "1")
        if name == "wait":                        # --wait=<seconds>: "=<seconds>", so --wait=1 is not plain --wait
            return (name, "=" + value if value else "")
        raise Refusal("--%s takes no value" % name)
    if len(word) > 1 and word.startswith("-"):
        raise Refusal("unknown option '%s' — see: council help" % word)
    words.append(word)
    return None


def takes_flags(args: Args, label: str, *allowed: str) -> None:
    """Refuse a flag the command never reads; --run is taken everywhere, and '--' marks a command that
    takes a command of its own after --."""
    for flag in args.flags:
        if flag != "run" and flag not in allowed:
            raise Refusal("%s doesn't take --%s — see: council help" % (label, flag))
    if "--" not in allowed and args.after:
        raise Refusal("%s takes nothing after -- — see: council help" % label)


def takes_no_run(args: Args, reads: str) -> None:
    """--run refused for a command that reads no one run: '<what it reads>; it does not take --run'."""
    if args.value("run"):
        raise Refusal(reads + "; it does not take --run")


def no_words(label: str, words: list[str]) -> None:
    if words:
        raise Refusal("%s doesn't take '%s' — see: council help" % (label, " ".join(words)))


def say(line: str) -> None:
    sys.stdout.write(line + "\n")


def say_all(lines: Iterable[str]) -> None:
    for line in lines:
        say(line)


def warn(line: str) -> None:
    """One line on stderr, after whatever stdout holds so far."""
    sys.stdout.flush()
    sys.stderr.write(line + "\n")
    sys.stderr.flush()
