"""A gate's saved verdict, gates/<name>.json, read the way the helper's sed read it: one line, written by council
gate (src/council/commands/gate_run.py). `council gate` reads a baseline's numbers and `council check` a proof's
exit, command and proof kind through these, so a verdict is read one way."""
from __future__ import annotations

import re
from pathlib import Path

COMMAND = re.compile(r'.*"command": "(.*)", "exit"')


def _lines(path: str | Path) -> list[str]:
    try:
        content = Path(path).read_bytes().decode("utf-8", "surrogateescape")
    except OSError:
        return []
    found = content.split("\n")
    return found[:-1] if found and found[-1] == "" else found


def _first(path: str | Path, pattern: re.Pattern) -> str:
    for line in _lines(path):
        found = pattern.match(line)
        if found:
            return found.group(1)
    return ""


def number(path: str | Path, key: str) -> str:
    """A verdict's number: the last `"key": N` on the first line that has one ('' when none)."""
    return _first(path, re.compile(r'.*"%s": *(%s)' % (key, "-?[0-9]+" if key == "exit" else "[0-9]+")))


def text(path: str | Path, key: str) -> str:
    """A verdict's string field with no quote in it (proof, invalid), as written ('' when none)."""
    return _first(path, re.compile(r'.*"%s": "([^"]*)"' % key))


def command(path: str | Path) -> str:
    """The command a verdict records, its JSON escapes undone."""
    return re.sub(r"\\(.)", r"\1", _first(path, COMMAND))


def holds(path: str | Path, words: str) -> bool:
    """Whether the verdict's text holds these words anywhere (grep -q)."""
    return any(words in line for line in _lines(path))
