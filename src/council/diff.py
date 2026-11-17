"""A unified diff as git writes it, read into files, their removed and added lines, each with its line number.
For council patch's checks (references/run/builder-report.md); git's own headers are all it trusts."""
from __future__ import annotations

import re
from typing import NamedTuple

ESCAPES = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13}     # git's one-letter C escapes
HUNK = re.compile(r"@@ -([0-9]+)(?:,[0-9]+)? \+([0-9]+)(?:,([0-9]+))? @@")


class Hunk(NamedTuple):
    """A hunk header's old start, new start and new count (a count git leaves out is 1)."""

    old: int
    new: int
    count: int


def header(line: str) -> Hunk | None:
    """The numbers of a hunk header as git writes it, '@@ -a[,b] +c[,d] @@'; None for any other line. The one
    reader of a header: a caller skips a None one, and the numbering in force stays."""
    found = HUNK.match(line)
    return Hunk(int(found.group(1)), int(found.group(2)), int(found.group(3) or 1)) if found else None


class Line(NamedTuple):
    """One removed or added line: its number on its own side (old for removed, new for added) and its text."""

    number: int
    text: str


class File(NamedTuple):
    """One file of the diff: its path (the new one; the old one when it was deleted), whether it was deleted or
    is new, and its removed and added lines."""

    path: str
    deleted: bool
    created: bool
    removed: list
    added: list


def unquote(name: str) -> str:
    """A path as git C-quotes it (core.quotePath on, or a name holding a quote, a backslash or a control character:
    "a/t\\303\\251st.py") read back as written, a/tést.py; any other name as it is."""
    if len(name) < 2 or name[0] != '"' or name[-1] != '"':
        return name
    body, out, at = name[1:-1], bytearray(), 0
    while at < len(body):
        if body[at] == "\\" and re.fullmatch(r"[0-7]{3}", body[at + 1:at + 4]):
            out.append(int(body[at + 1:at + 4], 8) & 0xFF)
            at += 4
        elif body[at] == "\\" and at + 1 < len(body):
            out += bytes([ESCAPES.get(body[at + 1], ord(body[at + 1]) if body[at + 1].isascii() else 63)])
            at += 2
        else:
            out += body[at].encode("utf-8", "surrogateescape")
            at += 1
    return out.decode("utf-8", "surrogateescape")


def _path(header: str) -> str:
    """The path of a ---/+++ line: a/ or b/ dropped, /dev/null kept, a quoted path unquoted."""
    name = unquote(header[4:].rstrip("\t"))
    return name[2:] if name[:2] in ("a/", "b/") else name


def files(text: str) -> list[File]:
    """Every file of a diff, in order; a binary file has no lines."""
    found: list[File] = []
    old = new = 0
    head = False                          # in a file's header, before its first hunk: ---, +++ and modes
    for line in text.split("\n"):
        if line.startswith("diff --git "):
            found.append(File(_git_path(line), False, False, [], []))
            head = True
        elif not found:
            continue
        elif line.startswith("@@"):
            hunk = header(line)
            if hunk:
                old, new, head = hunk.old, hunk.new, False
        elif head:
            found[-1] = _header(found[-1], line)
        elif line.startswith("-"):
            found[-1].removed.append(Line(old, line[1:].rstrip("\r")))
            old += 1
        elif line.startswith("+"):
            found[-1].added.append(Line(new, line[1:].rstrip("\r")))
            new += 1
        elif line.startswith(" "):
            old, new = old + 1, new + 1
    return [file for file in found if file.path]


def _header(file: File, line: str) -> File:
    """A file as one more line of its header says it is."""
    if line.startswith("deleted file mode"):
        return file._replace(deleted=True)
    if line.startswith("new file mode"):
        return file._replace(created=True)
    if line.startswith(("--- ", "+++ ")) and _path(line) != "/dev/null":
        return file._replace(path=_path(line))      # --- first, then +++: a deleted file keeps its old path
    return file


def _git_path(line: str) -> str:
    """The path a 'diff --git a/x b/x' line names, for a file with no ---/+++ lines (a binary one, a mode
    change): what follows its last ' b/', or its last ' "b/' read back from git's quoting."""
    if line.endswith('"') and ' "b/' in line:
        return unquote(line[line.rfind(' "b/') + 1:])[2:]
    at = line.rfind(" b/")
    return line[at + 3:] if at >= 0 else ""
