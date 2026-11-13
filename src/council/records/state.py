"""session-state.md: a run's header fields, its recorded decisions, and the runs open in a council home.

The header is every `key: value` line above the first `## ` heading. The helper's state_field reads a
key only there, so a note below the heading never reads as a field.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional

from council.records import cells, paths

NAME = paths.STATE
KEY = re.compile(r"[A-Za-z][A-Za-z0-9-]*")
Reader = Callable[[Path], Optional[str]]


def path(run: Path) -> Path:
    """The state file of a run folder."""
    return Path(run) / NAME


def text(run: Path, read: Reader | None = None) -> str:
    """The state file's text: by default the guarded read (a link, a file outside the run, one over
    4 MB or a missing one reads as ''); `read` gives a caller's own policy, such as one that refuses."""
    run = Path(run)
    if read is None:
        return paths.text_of(path(run), run)
    return read(path(run)) or ""


def header(content: str, exact_keys: bool = False, comments: bool = True) -> dict[str, str]:
    """The header's fields, the first of a repeated key winning, with the value's leading space dropped
    and, with comments, a trailing '  # comment'. exact_keys takes only a key at the start of its line,
    as the helper's state_field does; otherwise space around the key is allowed (the cockpit's rule)."""
    fields = {}
    for line in cells.lines_of(content):
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
    """A `mode: council-implement` line anywhere in the file (the repair loop's own test)."""
    return re.search(r"^mode: council-implement\s*$", content, re.MULTILINE) is not None


def planned(content: str) -> bool:
    """Opened with plans and agent limits: a plan-schema: line with a value (bin/council cap_standing)."""
    return re.search(r"^\ufeff?plan-schema:[ \t]*[^ \t\r\n#]", content, re.MULTILINE) is not None


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


def in_progress(home: Path) -> list[tuple[Path, str, str]]:
    """The in-progress runs under a council home, newest first: (folder, code-root, session), each read
    from its header with the cockpit's rule. Every entry of runs/ is tried; one with no state is skipped."""
    runs, rows = Path(home) / "runs", []
    try:
        names = sorted((entry.name for entry in runs.iterdir()), reverse=True)
    except OSError:
        return rows
    for name in names:
        fields = {k: cells.clean(v) for k, v in header(text(runs / name)).items()}
        if fields.get("status", "").split(" ")[0] == "in-progress":
            rows.append((runs / name, fields.get("code-root", ""), fields.get("session", "")))
    return rows
