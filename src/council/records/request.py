"""The user's request in their own words (ask.md and the filed request it continues), and whether a quote is
word for word from it: the quote check `council check` runs on a post-game's parts and next tasks, read the
same way here for a plan task's Serves row."""
from __future__ import annotations

import re
from pathlib import Path

from council.records import paths, state

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


def filed(run: Path) -> Path | None:
    """The filed request this run's words belong to: the state's ask:, else ask.md's continues: (backticks and
    angle brackets dropped, its first word); a relative path is the project's (the council home's parent)."""
    run = Path(run)
    name = state.field(state.text(run), "ask")
    if not name:
        cont = state.field(paths.text_of(run / ASK, run), "continues")
        name = (re.sub(r"[`<>]", "", cont).split() or [""])[0]
    if not name:
        return None
    where = Path(name)
    return where if where.is_absolute() or re.match(r"[A-Za-z]:", name) else run.parent.parent.parent / where


def words(run: Path) -> str:
    """The user's words for this run, whitespace collapsed to single spaces, then folded. Unlike `council check`,
    nothing is redacted yet: redaction is still bash's (S8)."""
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
