"""A builder's report on one round of a build task (`<run>/report-<n>.md`): its fixed head, read before anything
else, and the prose below it, which the helper never reads (references/run/builder-report.md).

    Cause: <for a fix: what was wrong, in one sentence> · state: OBSERVED|REPRODUCED   (or: Cause: none)
    Owner: <where the change was made>
    Removed: <each rule, behaviour, test or assertion taken out, and where it stands now> | none
    Assumed: <what it relied on without checking> | nothing
    Redesign: <what the design changes, and why the patches failed>   (only for a third fix round)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from council.records import paths

KEYS = ("cause", "owner", "removed", "assumed")
STATES = ("OBSERVED", "REPRODUCED", "INFERRED", "ASSUMED", "UNVERIFIED")
EARNED = ("OBSERVED", "REPRODUCED")          # a cause that has earned a code change
LINE = re.compile(r"\**(Cause|Owner|Removed|Assumed|Redesign)\**\s*:\**\s*(.*?)\s*", re.IGNORECASE)
STATE = re.compile(r"^(.*?)[\s·;,(—-]*\bstate\s*:\s*([A-Za-z]+)\)?\s*$", re.IGNORECASE)
WHAT = {"cause": "what was wrong, and its state, or none on a first build", "owner": "where the change was made",
        "removed": "each thing taken out, or none", "assumed": "what you relied on unchecked, or nothing"}
SHAPE = ("Cause: <what was wrong> · state: OBSERVED|REPRODUCED (or Cause: none, on a first build) / Owner: <where> / "
         "Removed: <each one taken out, and where it stands now> | none / Assumed: <what you relied on> | nothing")


class Head(NamedTuple):
    """The head as written: each field's words, the cause's evidence state ('' for Cause: none) and the
    redesign note ('' when there is none)."""

    cause: str
    state: str
    owner: str
    removed: str
    assumed: str
    redesign: str

    def fix(self) -> bool:
        """The head names a cause: the round is a fix."""
        return not _none(self.cause)

    def removed_none(self) -> bool:
        return _none(self.removed)


def report(run: str | Path, task: int) -> Path:
    """Where the builder writes its report on task <n>: one file, rewritten each round."""
    return Path(run) / ("report-%d.md" % task)


def _none(words: str) -> bool:
    return re.split(r"[\s—–:.(-]", words.strip().lower() + " ", maxsplit=1)[0] in ("none", "nothing", "")


def read(path: str | Path) -> tuple[Head | None, list[str]]:
    """The head of a report and what is wrong with it; (None, problems) when it can't be read as one. The
    head is its first lines: after an optional '# ' title and blank lines, Cause, Owner, Removed and Assumed in
    that order, then an optional Redesign; the prose below is the builder's own."""
    if not Path(path).is_file():
        return None, ["%s isn't there — write the round's report, its head first (%s)" % (Path(path).as_posix(), SHAPE)]
    found: dict = {}
    for line in _head_lines(paths.text_of(Path(path))):
        match = LINE.fullmatch(line)
        if not match:
            break
        found.setdefault(match.group(1).lower(), (len(found), match.group(2)))
    problems = [_missing(key, found) for key in KEYS if key not in found or not found[key][1]]
    order = [key for key in KEYS if key in found]
    if not problems and [found[key][0] for key in order] != sorted(found[key][0] for key in order):
        problems.append("the head's lines are out of order — Cause, Owner, Removed, Assumed")
    if problems:
        return None, problems
    cause, state = _cause(found["cause"][1])
    if cause is None:
        return None, ["Cause: '%s' gives no evidence state — end it '· state: OBSERVED' or '· state: REPRODUCED', "
                      "or write Cause: none on a first build" % found["cause"][1]]
    return Head(cause, state, found["owner"][1], found["removed"][1], found["assumed"][1],
                found.get("redesign", (0, ""))[1]), []


def _head_lines(content: str) -> list[str]:
    """The report's lines from its first that is neither blank nor a '# ' title."""
    lines = [line.rstrip("\r").strip() for line in content.split("\n")]
    start = 0
    while start < len(lines) and (not lines[start] or lines[start].startswith("# ")):
        start += 1
    return lines[start:]


def _missing(key: str, found: dict) -> str:
    if key in found:
        return "the head's %s: line is empty — %s" % (key.capitalize(), WHAT[key])
    return "the report has no %s: line in its head — the head is its first lines, before any prose (%s)" % (
        key.capitalize(), SHAPE)


def _cause(words: str) -> tuple[str | None, str]:
    """(the cause, its state) — ('none', '') for none; (None, '') when a cause gives no state it can read."""
    if _none(words):
        return words, ""
    match = STATE.match(words)
    if not match or match.group(2).upper() not in STATES:
        return None, ""
    return match.group(1).strip(), match.group(2).upper()
