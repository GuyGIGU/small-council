"""session-state.md: a run's header fields and its recorded decisions.

The header is every `key: value` line above the first `## ` heading. The helper's state_field reads a
key only there, so a note below the heading never reads as a field.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from council.records import cells, paths

NAME = paths.STATE
KEY = re.compile(r"[A-Za-z][A-Za-z0-9-]*")
SCOPED = re.compile(r"(?P<minute>[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}): (?:task (?P<task>[0-9]+): )?"
                    r"(?P<words>.*)", re.S)


def path(run: Path) -> Path:
    return Path(run) / NAME


def text(run: Path, read: paths.Reader | None = None) -> str:
    return paths.run_text(run, NAME, read)


def unread(run: Path, so: str) -> str:
    """Why text leaves the run's state out (a link, a file outside the run, one over the size limit), with what that
    stops (`so`) and the next step (D19); '' when text reads it."""
    found = path(run)
    if not (paths.linked(found) or paths.too_large(found) or (found.is_file() and not paths.contained(found, run))):
        return ""
    return ("the run's %s is a link, lies outside the run or is over %s, so %s — put a plain copy of it, under that "
            "size, in its place: %s" % (NAME, paths.megabytes(paths.MAX_FILE), so, found.as_posix()))


def header(content: str, exact_keys: bool = False, comments: bool = True) -> dict[str, str]:
    """The header's fields, the first of a repeated key winning, with the value's leading space dropped
    and, with comments, a trailing '  # comment'. exact_keys takes only a key at the start of its line,
    as the helper's state_field does; otherwise space around the key is allowed (the snapshot's rule)."""
    fields = {}
    for line in cells.lines_of(content.lstrip(paths.BOM)):    # the helper drops the BOM from line 1
        if line.startswith("## "):
            break
        key, sep, value = line.partition(":")
        name = key if exact_keys else key.strip()
        if sep and KEY.fullmatch(name) and name not in fields:
            value = value.lstrip(" \t")
            fields[name] = re.sub(r"[ \t]{2,}#.*$", "", value) if comments else value
    return fields


def field(content: str, key: str) -> str:
    """One header field as the helper's state_field reads it: the first `key:` line above the first `## `
    heading, a trailing '  # comment' taken off; '' when the header has none. A line below a heading that
    starts with the key (a decision or note beginning `mode:`) is never the field."""
    return header(content, exact_keys=True).get(key, "")


def is_build_run(content: str) -> bool:
    return field(content, "mode") == "council-implement"


def planned(content: str) -> bool:
    """Opened with plans and agent limits: the header's `plan-schema:` has a value (bin/council cap_standing)."""
    return field(content, "plan-schema") != ""


def unquote(entry: str) -> str:
    """'<time>: "<words>"' with the words as the user gave them. The helper escapes only quote marks and
    backslashes; an entry holding anything else after a backslash, or a bare quote mark, is shown as it is."""
    found = re.match(r'^(.*?: )"((?:[^"\\]|\\["\\])*)"\s*$', entry)
    if not found:
        return entry
    return '%s"%s"' % (found.group(1), re.sub(r'\\(["\\])', r"\1", found.group(2)))


def decisions(content: str) -> list[str]:
    """The entries under '## Decisions so far' (council state decision=), oldest first, unquoted."""
    found, inside = [], False
    for line in cells.lines_of(content):
        if line.startswith("## "):
            inside = line.strip() == "## Decisions so far"
            continue
        if inside and line.startswith("- "):
            found.append(unquote(line[2:]))
    return found


class Decision(NamedTuple):
    """One entry read back: its local minute, the task it is for (None: the whole run) and the user's words."""

    minute: str
    task: int | None
    words: str


def decision(entry: str) -> Decision:
    """An unquoted entry as '<minute>: [task <n>: ]"<words>"' (council state decision="…" [task=<n>]); an entry
    with no task, as every one written before task scope was, is the whole run's. Words not in quotes are taken as
    they stand."""
    found = SCOPED.match(entry)
    if not found:
        return Decision("", None, entry)
    words = found.group("words")
    quoted = re.fullmatch(r'"(.*)"\s*', words, re.S)
    return Decision(found.group("minute"), int(found.group("task")) if found.group("task") else None,
                    quoted.group(1) if quoted else words)


def decisions_for(content: str, task: int) -> list[str]:
    """The entries a task's orders carry: the whole run's and that task's own, never another task's."""
    return [entry for entry in decisions(content) if decision(entry).task in (None, task)]
