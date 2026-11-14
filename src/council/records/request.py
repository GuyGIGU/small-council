"""The user's request in their own words (ask.md and the filed request it continues), and whether a quote is
word for word from it: the quote check `council check` runs on a post-game's parts and next tasks, read the
same way here for a plan task's Serves row."""
from __future__ import annotations

import re
from pathlib import Path

from council.records import cells, paths, state

ASK = "ask.md"
# Curly quotes, odd and invisible spaces fold to what a person typing a quote would write.
FOLDS = (("‘", "'"), ("’", "'"), ("“", '"'), ("”", '"'), (" ", " "), (" ", " "),
         (" ", " "), ("​", ""), ("‌", ""), ("‍", ""), ("⁠", ""), ("﻿", ""),
         ("…", "..."))
LATER = re.compile(r"## Later|## [0-9]{4}-[0-9]{2}-[0-9]{2} |\(no new words\)[ \t\r]*$")


def fold(text: str) -> str:
    """Text as the quote check compares it: folded marks and spaces, runs of blanks one space, ends trimmed."""
    for mark, plain in FOLDS:
        text = text.replace(mark, plain)
    return re.sub(r"[ \t]+", " ", text).strip(" ")


def in_your_words(content: str) -> list[str]:
    """The lines from '## In your words' on, without a later heading or '(no new words)'."""
    found, inside = [], False
    for line in content.split("\n"):
        if line.startswith("## In your words"):
            inside = True
        elif inside and not LATER.match(line):
            found.append(line)
    return found


def continued(run: Path) -> str:
    """The filed request this run continues, as written: the state's ask:, else ask.md's continues: (backticks and
    angle brackets dropped, up to its first blank); '' for a new request."""
    run = Path(run)
    name = state.field(state.text(run), "ask")
    if not name:
        cont = cells.field(paths.text_of(run / ASK, run), "continues")
        name = re.sub(r"[ \t\n\v\f\r].*$", "", re.sub(r"[`<>]", "", cont), flags=re.S)
    return name


def filed(run: Path) -> Path | None:
    """The filed request this run's words belong to (continued); a relative path is the project's (the council
    home's parent)."""
    run = Path(run)
    name = continued(run)
    if not name:
        return None
    where = Path(name)
    return where if where.is_absolute() or re.match(r"[A-Za-z]:", name) else run.parent.parent.parent / where


def lines_kept(data: bytes) -> list[bytes]:
    """A file's lines byte for byte, each with its newline: a last line with none stays without one."""
    found = data.split(b"\n")
    last = found.pop()
    return [line + b"\n" for line in found] + ([last] if last else [])


def _bare(line: bytes) -> bytes:
    return line[:-1] if line.endswith(b"\n") else line


def ask_words(data: bytes) -> bytes:
    """An ask.md's "In your words" body, byte for byte: only "## In your words" and "## Later" end it, so a pasted
    PR or issue with its own "## Summary" stays whole."""
    out, inside = [], False
    for line in lines_kept(data):
        bare = _bare(line)
        if not inside:
            if not bare.startswith(b"## In your words"):
                continue
            inside = True
        elif bare.startswith(b"## Later"):
            inside = False
        if not (bare.startswith(b"## In your words") or bare.startswith(b"## Later")):
            out.append(line)
    return b"".join(out)


def ask_later(data: bytes) -> bytes:
    """An ask.md's "Later" lines, from its first "## Later" heading on, without the headings and blank lines."""
    out, inside = [], False
    for line in lines_kept(data):
        bare = _bare(line)
        inside = inside or bare.startswith(b"## Later")
        if inside and not bare.startswith(b"## Later") and not re.fullmatch(rb"[ \t\v\f\r]*", bare):
            out.append(line)
    return b"".join(out)


def ask_sections(data: bytes, run: str = "") -> list[int]:
    """The line numbers of the sections continuing runs add to a filed request ("## <date> — <mode>, run
    <folder>"); with run, a run folder's name, only that run's (the whole name: …-review is not …-review-2). Only
    a run folder's name counts: a dated heading in the user's own words is no section."""
    who = re.escape(run.encode("utf-8", "surrogateescape")) if run else \
        rb"[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{6}-[A-Za-z0-9-]+"
    heading = re.compile(rb"## [0-9]{4}-[0-9]{2}-[0-9]{2} .*, run " + who + rb"[ \t\v\f\r]*", re.S)
    return [at for at, line in enumerate(data.split(b"\n"), 1) if heading.fullmatch(line)]


def words(run: Path) -> str:
    """The user's words for this run, whitespace collapsed to single spaces, then folded; nothing is redacted (the
    plan check reads them; `council check` redacts them first)."""
    run = Path(run)
    lines = in_your_words(paths.text_of(run / ASK, run))
    other = filed(run)
    if other is not None:
        lines += in_your_words(paths.text_of(other))
    return fold(re.sub(r"[ \t\r\n]+", " ", "\n".join(lines)))


def found(request: str, quote: str) -> bool:
    """The quote stands in the request as whole words: no letter or digit runs on at either end."""
    start = request.find(quote)
    while start >= 0:
        end = start + len(quote)
        if not (start and request[start - 1].isascii() and request[start - 1].isalnum()) \
                and not (end < len(request) and request[end].isascii() and request[end].isalnum()):
            return True
        start = request.find(quote, start + 1)
    return False


def trimmed(quote: str) -> str:
    """A quote without its end spaces and a trailing ellipsis."""
    return re.sub(r"(\.\.\.)$", "", quote.strip(" ")).rstrip(" ")


def verdict(cell: str, request: str) -> str:
    """A cell's first quoted words against the request: ok, NO-QUOTE, TOO-SHORT (under three words, unless the
    request is that short) or NOT-IN-THE-REQUEST. Quoted words may hold quotes of their own, so the quote runs to
    whichever closing mark makes it the request's words."""
    cell = fold(cell)
    if cell.count('"') < 2:
        return "NO-QUOTE"
    rest = cell[cell.index('"') + 1:]
    marks = [i for i, c in enumerate(rest) if c == '"']

    def short(quote: str) -> bool:
        return len(quote.split()) < 3 and quote != request
    for end in marks:
        quote = trimmed(rest[:end])
        if quote and not short(quote) and found(request, quote):
            return "ok"
    first = trimmed(rest[:marks[0]])
    if not first:
        return "NO-QUOTE"
    return "TOO-SHORT" if short(first) else "NOT-IN-THE-REQUEST"
