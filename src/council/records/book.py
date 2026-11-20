"""The project's book (D52, references/run/book.md): its four pages, where each one is, and the one writer of a
known-problems line.

A page's path is its `- <page>: <path>` line under the config's `## Book` section (a project's own file, adopted at
setup), else its default under the council home. A relative path hangs off the folder that holds the council home, as
the memory file's does. The decisions log's word `memory` (and its default) is the memory file, whose
`## Decisions (D)` section holds the decisions when the project keeps no log of its own.
"""
from __future__ import annotations

import os
import re
from typing import NamedTuple

from council.records import cells, config, memory, paths
from council.records import home as where

PAGES = ("design", "stack", "decisions", "known problems")
READ_FIRST = PAGES[:3]                 # every agent reads these before anything else
DEFAULTS = {"design": "design.md", "stack": "stack.md", "known problems": "known-problems.md"}
MEMORY = "memory"                      # the decisions log's word for the memory file
FOUND, WAIVED = "Found, not fixed", "Not to raise again"
TEMPLATE = "known-problems.md"
LINES = {"design": 120, "stack": 60}   # a page's size, at most (references/run/book.md's table)


class Page(NamedTuple):
    """One page of the book: its name, its path (absolute, / separators), whether the config names it (adopted or
    set), whether a file or folder is there, and whether it is the memory file (the decisions log's default)."""

    name: str
    path: str
    configured: bool
    there: bool
    memory: bool = False


def _root(home: str) -> str:
    return home[:home.rfind("/")] if "/" in home else home


def _configured(home: str) -> dict[str, str]:
    """The `- <page>: <path>` lines under the config's ## Book section: the path as said (notes, quotes and a
    " — adopted" aside off, as the memory file's line is read)."""
    found: dict[str, str] = {}
    for number, line in config.section(where.native(home), "book"):
        pref = config.pref_of(line, number)
        said = config.path_said(pref.said).strip() if pref and pref.key in PAGES and pref.key not in found else ""
        if pref and said:
            found[pref.key] = said
    return found


def in_config(home: str) -> bool:
    """Whether the config has a `## Book` heading: one set up before the book (2.0) has none, and reads every page
    from its default place."""
    data = paths.contents(where.native(home + "/" + config.NAME)) or b""
    return any(cells.heading(line) == "book" for line in cells.lines_of(data.decode("utf-8", "replace")))


def default(home: str, name: str) -> str:
    """A page's place when the config names none (the decisions log's is the memory file)."""
    return memory.locate(home).path if name == "decisions" else home + "/" + DEFAULTS[name]


def pages(home: str) -> list[Page]:
    """The book's four pages, in PAGES order."""
    said, root, out = _configured(home), _root(home), []
    for name in PAGES:
        value = said.get(name, "")
        kept = name == "decisions" and (not value or value.lower() == MEMORY)
        path = memory.absolute(root, value) if value and not kept else default(home, name)
        path = path.replace("\\", "/")
        out.append(Page(name, path, bool(value), os.path.exists(where.native(path)), kept))
    return out


def page(home: str, name: str) -> Page:
    return next(one for one in pages(home) if one.name == name)


class Added(NamedTuple):
    """What a known-problems write did: the file, whether it made the file, and whether the line was there already."""

    path: str
    made: bool
    already: bool


def add(home: str, section: str, line: str, template: str, today: str) -> Added:
    """`- <today>: <line>` at the end of a section of the known-problems file (FOUND or WAIVED), the file made from
    the template first when it is missing; nothing written when that section already holds the same words, in any
    capitals. Raises paths.RecordError for a path outside the project, a folder, or a file it can't write."""
    target = page(home, "known problems")
    native = where.native(target.path)
    if not paths.contained(os.path.dirname(native) or ".", where.native(_root(home))):
        raise paths.RecordError("%s is outside the project" % target.path)
    if os.path.isdir(native) or os.path.islink(native):
        raise paths.RecordError("%s is a folder or a link, not a file" % target.path)
    made = not os.path.exists(native)
    data = template.encode("utf-8") if made else (paths.contents(native) or b"")
    text = data.decode("utf-8", "surrogateescape")
    if _holds(text, section, line):
        return Added(target.path, False, True)
    os.makedirs(os.path.dirname(native) or ".", exist_ok=True)
    out = placed(text, section, "- %s: %s" % (today, line))
    paths.atomic_write(native, out.encode("utf-8", "surrogateescape"), ".known-", keep_mode=True)
    return Added(target.path, made, False)


def _entries(text: str, section: str) -> list[str]:
    """The `- <date>: <words>` entries under a section, outside comments, as their words, lower-cased."""
    lines = cells.lines_of(text)
    span = _span(lines, section)
    if span is None:
        return []
    out = []
    for _, kept in _content(lines, *span):
        found = re.match(r"[ \t]*[-*][ \t]+(?:[0-9]{4}-[0-9]{2}-[0-9]{2}:[ \t]*)?(.*\S)", kept)
        if found:
            out.append(found.group(1).lower())
    return out


def _holds(text: str, section: str, line: str) -> bool:
    return line.strip().lower() in _entries(text, section)


def _span(lines: list[str], section: str) -> tuple[int, int] | None:
    """The first and past-the-last line under the section's heading; None when the text has no such heading."""
    at = next((i for i, line in enumerate(lines) if cells.heading(line) == section.lower()), None)
    if at is None:
        return None
    return at + 1, next((i for i in range(at + 1, len(lines)) if lines[i].startswith("## ")), len(lines))


def placed(text: str, section: str, entry: str) -> str:
    """The text with entry after the last line of the section's own (its blank lines and comments before the next
    heading left below it); the section added at the end when the file has none. The file's line ends kept."""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.replace("\r\n", "\n").split("\n")
    span = _span(lines, section)
    if span is None:
        body = "\n".join(lines).rstrip("\n")
        return ((body + "\n\n" if body else "") + "## %s\n%s\n" % (section, entry)).replace("\n", newline)
    last = max([i for i, _ in _content(lines, *span)] or [span[0] - 1])
    lines.insert(last + 1, entry)
    return "\n".join(lines).replace("\n", newline)


def _content(lines: list[str], start: int, end: int) -> list[tuple[int, str]]:
    """(index, the line with its HTML comments cut out) for each line from start to end with text outside one."""
    opened, out = False, []
    for i in range(start, end):
        line, kept = lines[i], ""
        while line:
            mark = line.find("-->" if opened else "<!--")
            if mark < 0:
                kept, line = kept + ("" if opened else line), ""
            elif opened:
                line, opened = line[mark + 3:], False
            else:
                kept, line, opened = kept + line[:mark], line[mark + 4:], True
        if kept.strip():
            out.append((i, kept))
    return out
