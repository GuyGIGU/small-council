"""The quotes `council check` holds to the user's own words: a request part's `quote: "…"` on an item line, and a
post-game next task's Done-when row. Both are matched by records.request's rule (fold, then whole words)."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import NamedTuple

from council.records import request

ITEM = re.compile(r"[-*+]? *[*_]*C?[0-9]+[a-z]?[*_]*\.? +(·|\|) ")
NOT_EXACT = "NOT-EXACT (only capitals or * _ ` marks differ — copy the words exactly)"


class Quote(NamedTuple):
    """One item's quote: its number, its status, and the words as written (before folding; '' when none)."""

    n: str
    status: str
    words: str


def _lower(text: str) -> str:
    return "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in text)


def loose(text: str) -> str:
    """Capitals, ** and ` marks don't count: what a near miss is compared on."""
    return _lower(re.sub(r" +", " ", re.sub(r"[*_`]", "", text)))


def word_count(text: str) -> int:
    return len([word for word in re.split(r"[ \t\n]+", text) if word])


def file_lines(path: str | Path) -> list[str]:
    """A file's lines as awk reads them, bytes kept; Git Bash's awk drops a CR before each newline on Windows."""
    try:
        content = Path(path).read_bytes().decode("utf-8", "surrogateescape")
    except OSError:
        return []
    if os.name == "nt":
        content = content.replace("\r\n", "\n")
    found = content.split("\n")
    return found[:-1] if found and found[-1] == "" else found


def opened_at(line: str) -> int:
    """Where the last "quote:" that opens a quote starts (it may be introduced "· quote:", "— quote:", "(quote:");
    a title may say "Quote:" too, so the word must start a quote to count). -1 when none does."""
    low, found, at = _lower(line), -1, 0
    while True:
        at = low.find("quote:", at)
        if at < 0:
            return found
        before = low[at - 1] if at else ""
        rest = low[at + 6:].lstrip(" \t")
        if not re.match(r"[a-z0-9]", before) and (rest.startswith('"') or rest.startswith("“")):
            found = at
        at += 1


def quoted(line: str, at: int) -> str | None:
    """The words of the quote that opens at `at`, up to its last closing mark; None when no mark opens it."""
    text = line[at + len("quote:"):].lstrip(" ")
    if text.startswith('"'):
        text, close = text[1:], '"'
    elif text.startswith("“"):
        text, close = text[1:], "”"
    else:
        return None
    end = text.rfind(close)
    return text[:end] if end >= 0 else text


def status(words: str, said: str) -> str:
    """A quote's words against the request (folded): ok, TOO-SHORT, NOT-EXACT, NOT-IN-THE-REQUEST or NO-QUOTE."""
    folded = request.fold(words)
    if not folded:
        return "NO-QUOTE"
    if word_count(folded) < 3 and folded != said:
        return "TOO-SHORT"
    if request.found(said, folded):
        return "ok"
    if request.found(loose(said), loose(folded)):
        return NOT_EXACT
    return "NOT-IN-THE-REQUEST"


def item_quotes(path: str | Path, said: str, mode: str) -> list[Quote]:
    """A request part's quote on each item line: an item whose principle reads "ask", and in a post-game every
    must or should item, quotes the request word for word."""
    found = []
    said = request.fold(said)
    for raw in file_lines(path):
        line = raw.replace("\r", "").replace("\t", " ")
        if not ITEM.match(line):
            continue
        parts = re.split(r" +· +", re.sub(r"^[-*+]? *", "", line)) if "·" in line else \
            re.split(r" +\| +", re.sub(r"^[-*+]? *", "", line))
        n = re.sub(r"[*_.]", "", parts[0])
        part = len(parts) > 2 and _lower(parts[2]) == "ask" or (
            mode == "council-postgame" and len(parts) > 1 and _lower(parts[1]) in ("must", "should"))
        if len(parts) < 4 or not part:
            continue
        at = opened_at(line)
        words = quoted(line, at) if at >= 0 else None
        found.append(Quote(n, "NO-QUOTE", "") if words is None else Quote(n, status(words, said), words))
    return found


class Task(NamedTuple):
    """A post-game next task: its number ("?" without one), its Done-when verdict and its title."""

    n: str
    status: str
    title: str


def next_tasks(path: str | Path, said: str) -> list[Task]:
    """Every "#### <n>. <title>" under "### Next tasks", with its Done-when row's verdict (request.verdict):
    a next task closes a gap against the request, so its Done-when quotes a part of it word for word."""
    said = request.fold(said)
    found: list[Task] = []
    on, task = False, None
    for raw in file_lines(path):
        line = raw[:-1] if raw.endswith("\r") else raw
        if re.match(r"###[ \t]+Next tasks", line):
            on = True
        elif on and re.match(r"##?[ \t]", line):
            found += _flush(task)
            on, task = False, None
        elif on and re.match(r"####[ \t]", line):
            found += _flush(task)
            title = re.sub(r"^####[ \t]+", "", line)
            number = re.match(r"[0-9]+[.)]?[ \t]*", title)
            task = [re.sub(r"[.)]?[ \t]*$", "", number.group(0)), "", title[number.end():]] if number else \
                ["?", "", title]
        elif on and task and not task[1] and re.match(r"\|[ \t]*\**done when\**[ \t]*\|", _lower(line)):
            cell = re.sub(r"\|[ \t]*$", "", re.sub(r"^\|[^|]*\|", "", line))
            task[1] = request.verdict(cell, said)
    return found + _flush(task)


def _flush(task: list[str] | None) -> list[Task]:
    return [Task(task[0], task[1] or "NO-DONE-WHEN", task[2])] if task else []
