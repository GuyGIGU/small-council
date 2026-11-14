"""A run's seat files and the brief that names them: the brief's seat blocks, a reference doc's title as a worker
proves it read it, a seat file's item lines and the shape of its item sections, and a verify file's shape.
`council collect` and `council check` read seat files through these; hooks/seat-gate.sh keeps its own copy of
the item-section rule (index_shape): change both together."""
from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path
from typing import NamedTuple

BOM = "﻿"
ITEM = re.compile(r"[-*+]?[ \t]*[*_]*C?[0-9]+[a-z]?[*_]*\.?[ \t]+(·|\|)[ \t]")
SHAPE_ITEM = re.compile(r"[-*+]? *[*_]*C?[0-9]+[a-z]?[*_]*\.? +(·|\|) ")
HEADED_ITEM = re.compile(r"#+ *[*_]*C?[0-9]+[a-z]?[*_]* +(·|\|) ")
NONE_LINE = re.compile(r" *([-*+] +)?[*_]*\([Nn]one\)")
NOTE_ITEM = re.compile(r" +([-*+] +)?[*_]*C?[0-9]+[a-z]?[*_]*\.? +(·|\||-|—|–) ")
ATTEMPT = re.compile(r"([-*+] +)?[*_]*C?[0-9]+")
TABLE_ITEM = re.compile(r"\| *[*_]*C?[0-9]+[a-z]?[*_]* *\|")


class Seat(NamedTuple):
    """One "### <slug>" block under the brief's "## Seats": its ref docs (" ;; " between a paired worker's,
    "none" for none, "?" for a file no block names), its out file, and its item cap ("-" when none is set)."""

    slug: str
    ref: str
    out: str
    cap: str


def lines(path: str | Path) -> list[str]:
    """A file's lines as awk reads them (bytes kept; a last line without a newline still a line); [] when it
    can't be read."""
    try:
        content = Path(path).read_bytes().decode("utf-8", "surrogateescape")
    except OSError:
        return []
    found = content.split("\n")
    return found[:-1] if found[-1] == "" else found


def lower(text: str) -> str:
    """ASCII letters lowered, as awk and tr do byte by byte."""
    return "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in text)


def _key(line: str, name: str) -> str | None:
    """The value after "name:" however it is written ("- ref:", "ref:", "- **ref:**", "- Refs:", "- `ref:`",
    "- ref :", indented), or None: a near-miss spelling must never switch the proof of reading off."""
    found = re.match(r"[ \t]*[-*+]?[ \t]*[`*_]*" + name + r"(s|erence|erences)?[`*_]*[ \t]*:[`*_]*", lower(line))
    return line[found.end():] if found else None


def _clean(value: str) -> str:
    return re.sub(r"[`\"\r]", "", value).strip(" \t")


def brief_seats(path: str | Path) -> list[Seat]:
    """The "## Seats" blocks of a brief (or of debate.md), in order. Backticks and quotes around values go."""
    found: list[Seat] = []
    inside, slug, ref, out, cap = False, "", "none", "", "8"
    for line in lines(path):
        if line.startswith("## "):
            inside = re.fullmatch(r"## Seats[ \t\r]*", line) is not None
            continue
        if not inside:
            continue
        if line.startswith("### "):
            if slug:
                found.append(Seat(slug, ref, out, cap))
            slug = re.sub(r"[`\"\r]", "", re.sub(r"[ \t].*$", "", re.sub(r"^###[ \t]*", "", line), flags=re.S))
            ref, out, cap = "none", "seats/" + slug + ".md", "8"
            continue
        value = _key(line, "ref")
        if value is not None:
            value = _clean(value)
            if value and lower(value) != "none":
                ref = value if ref == "none" else ref + " ;; " + value
            continue
        value = _key(line, "out")
        if value is not None:
            out = _clean(value) or out
            continue
        value = _key(line, "cap")
        if value is not None:
            number = re.search(r"[0-9]+", value)
            cap = number.group(0) if number else cap
    if slug:
        found.append(Seat(slug, ref, out, cap))
    return found


def norm(text: str) -> str:
    """Letters and digits only, lowercased — for comparing a seat's ref: line with its doc's title."""
    return "".join(lower(c) for c in text if c.isascii() and c.isalnum())


WIDE_DROPS = (rb"\xe2\x80[\x80-\xbf]|\xe2\x81[\x80-\xbf]|\xe2[\x86-\xac][\x80-\xbf]",     # dashes, quotes, arrows
              rb"\xc2[\x80-\xbf]|\xe3\x80[\x80-\xbf]|\xef\xb8[\x80-\x8f]|\xef\xbb\xbf",     # NBSP, "·", CJK marks, BOM
              rb"\xf0\x9f[\x80-\xbf][\x80-\xbf]")                                          # emoji


def norm_wide(text: str) -> str:
    """The same, but keeping letters no ASCII rule knows — a title written in Hebrew, Chinese or Greek would
    otherwise come out empty. Punctuation that looks like a letter to a byte-wise tool still goes."""
    data = text.encode("utf-8", "surrogateescape")
    for drop in WIDE_DROPS:
        data = re.sub(drop, b"", data)
    data = re.sub(rb"[^A-Za-z0-9\x80-\xff]", b"", data)
    return lower(data.decode("utf-8", "surrogateescape"))


def ref_title(path: str | Path) -> str:
    """A reference doc's title as a worker copies it — its first heading, after any front matter; else its first
    line of text — normalised (norm, else norm_wide)."""
    front, first, title = False, "", ""
    for at, line in enumerate(lines(path)):
        if at == 0:
            line = line[1:] if line.startswith(BOM) else line
            if re.fullmatch(r"---[ \t\r]*", line):
                front = True
                continue
        if front:
            front = re.fullmatch(r"---[ \t\r]*", line) is None
            continue
        if re.match(r"#+[ \t]", line):
            title = re.sub(r"^#+[ \t]*", "", line)
            break
        if not first and re.search(r"[^ \t\r]", line):
            first = line
    raw = title or first
    return norm(raw) or norm_wide(raw)


class Item(NamedTuple):
    """An item line — "<n> · <severity> · <principle> · <path:line> · <title>" — its fields ("-" when empty)."""

    n: str
    severity: str
    principle: str
    cite: str
    title: str
    section: str


def fields(line: str) -> list[str]:
    """An item line's fields: split on " · ", or on " | " when the line has no "·"."""
    return re.split(r" +· +", line) if "·" in line else re.split(r" +\| +", line)


def items(path: str | Path) -> list[Item]:
    """A file's item lines, with the first word of the "## " heading above each, lowercased."""
    found: list[Item] = []
    section = ""
    for line in lines(path):
        if line.startswith("## "):
            section = re.sub(r"[ \t\r].*$", "", re.sub(r"^## +", "", lower(line)), flags=re.S)
            continue
        if not ITEM.match(line):
            continue
        parts = fields(re.sub(r"^[-*+]? *", "", line.replace("\r", "").replace("\t", " ")))
        if len(parts) < 4:
            continue
        number = re.sub(r"[*_.]", "", parts[0])
        found.append(Item(number, *(part or "-" for part in (parts[1:4] + [parts[4] if len(parts) > 4 else ""])),
                          section or "-"))
    return found


class Shape(NamedTuple):
    """An item section's shape: item lines that parse, attempted item lines that don't, and a "(none)" line."""

    parsed: int
    unparsed: int
    none: bool


def shape(path: str | Path, sections: str = "Index") -> Shape:
    """The shape of a file's item sections: "## Index", or the "## " headings named in sections ("Kept|Cut"). A
    heading counts when it holds that word ("## KEPT", "## Kept:", "## 📋 Index"). Inside a section a "###"
    heading with item lines under it is a group heading and is skipped; one with prose under it is an item's body,
    and ends the section. An attempted item is a line that starts with a number (after a bullet or bold), a table
    row or a heading that does, or any line holding " · "; it parses with at least four fields. An indented line
    is a note under an item unless it is written as one. Other prose is ignored."""
    wanted = re.compile("(^|[^a-z])(" + lower(sections) + ")([^a-z]|$)")
    parsed = unparsed = 0
    none = inside = pending = False
    for raw in lines(path):
        if raw.startswith("## "):
            inside, pending = wanted.search(re.sub(r"^## +", "", lower(raw))) is not None, False
            continue
        if not inside:
            continue
        line = raw.replace("\r", "").replace("\t", " ")
        if line.startswith("###"):
            pending = HEADED_ITEM.match(line) is None          # a group heading, or an item body: what follows says
            unparsed += not pending
            continue
        if re.fullmatch(r" *", line):
            continue
        if pending:
            pending = False
            if not SHAPE_ITEM.match(line) and not NONE_LINE.match(line):
                inside = False
                continue
        if NONE_LINE.match(line):
            none = True
        elif SHAPE_ITEM.match(line):
            if len(fields(line)) >= 4:
                parsed += 1
            else:
                unparsed += 1
        elif line.startswith((" ", "\t")):                     # a note under an item
            unparsed += NOTE_ITEM.match(line) is not None
        elif ATTEMPT.match(line) or " · " in line or TABLE_ITEM.match(line):
            unparsed += 1
    return Shape(parsed, unparsed, none)


def verify_problems(path: str | Path) -> str:
    """The problems of a verify file's shape, each ending "; " ('' when none): line 1 '# Verification — <run
    title>', a verdict table, at most 16 KB. The seat-check hook holds a verifier to the same rule."""
    found = lines(path)
    first = found[0].replace("\r", "") if found else ""
    first = first[1:] if first.startswith(BOM) else first
    problems = "" if first.startswith("# Verification") else "line 1 isn't '# Verification — <run title>'; "
    if not any(re.match(r"[ \t\n\v\f\r]*\|", line) for line in found):
        problems += "no verdict table (| # | Item | Verdict | Evidence |); "
    try:
        size = Path(path).stat().st_size
    except OSError:
        size = 0
    return problems + ("over 16 KB; " if size > 16384 else "")


def listed(folder: Path, pattern: str) -> list[str]:
    """The names a bash glob gives in folder: matched with case, no dot files, in byte order."""
    try:
        names = os.listdir(str(folder))
    except OSError:
        return []
    return sorted((name for name in names if not name.startswith(".") and fnmatch.fnmatchcase(name, pattern)),
                  key=lambda name: name.encode("utf-8", "surrogateescape"))
