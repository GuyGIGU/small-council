"""council book | book note "<line>" | book waive "<the owner's words>": the project's book (D52,
references/run/book.md).

council book prints where the book's four pages are (the design page, the stack page, the decisions log and known
problems), each with whether it is there yet; every agent reads the first three before anything else. council book
note adds a dated line under known problems' `## Found, not fixed`: a true thing found and not fixed, such as a
review's item below the worth bar. council book waive adds one under `## Not to raise again`: a kind of item the owner
waved off, in their words. A review raises neither again. The same words twice are written once; the line is redacted
as the user's words are. Writes nothing else.
"""
from __future__ import annotations

import os
from pathlib import Path

from council import clock
from council.commands import cli
from council.records import book, config, paths, redact
from council.records import home as where

USAGE = ('usage: council book | book note "<what is wrong — path:line>" | book waive "<the kind of item, in the '
         "owner's words>\"")
SECTIONS = {"note": book.FOUND, "waive": book.WAIVED}
MISSING = {
    "design": "not written yet — setup writes it or adopts the project's own (council-init, references/run/book.md)",
    "stack": "not written yet — setup writes it or adopts the project's own (council-init, references/run/book.md)",
    "decisions": "not written yet — no decision is on record",
    "known problems": "none yet — council book note starts it",
}


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "book")
    home = where.council_home()
    if not os.path.isfile(where.native(home + "/" + config.NAME)):
        raise cli.Refusal("no %s at %s — %s" % (config.NAME, home, where.NO_SETUP))
    sub, rest = (words[0], words[1:]) if words else ("", [])
    if sub == "":
        cli.say_all(lines(home))
        return 0
    if sub not in SECTIONS:
        raise cli.Refusal(USAGE)
    if len(rest) != 1 or not rest[0].strip():
        raise cli.Refusal("book %s takes one quoted line — %s" % (sub, USAGE))
    return _add(home, sub, rest[0])


def described(page: book.Page) -> str:
    """One page's line: its name, its path, and what is so of it."""
    said = "%s: %s" % (page.name, page.path)
    if page.memory:
        said += " (the memory file: its ## Decisions (D) section)"
    return said if page.there else said + " — " + MISSING[page.name]


def lines(home: str) -> list[str]:
    """council book's output: a line per page, then who reads which."""
    return [described(page) for page in book.pages(home)] + [
        "Read first: %s — every agent, before anything else; a review also reads known problems and raises nothing "
        "listed there again" % ", ".join(book.READ_FIRST)]


def read_first(home: str) -> list[str]:
    """The first three pages as a brief lists them: `- <page>: <path>`, or what stands in for a page not there."""
    return ["- " + described(page) for page in book.pages(home) if page.name in book.READ_FIRST]


def known(home: str) -> str:
    """Known problems' path and state, as a review's brief names it."""
    return described(book.page(home, "known problems"))[len("known problems: "):]


def one_line(home: str) -> str:
    """The first three pages on one line, for a build task's orders."""
    return "Read first, before anything else — the book: " + " · ".join(
        "%s %s" % (page.name, page.path if page.there else "(none yet)")
        for page in book.pages(home) if page.name in book.READ_FIRST)


def _template(project: str) -> str:
    file = Path(where.native(where.plugin_root())) / "references" / "templates" / book.TEMPLATE
    try:
        text = file.read_bytes().decode("utf-8", "surrogateescape").replace("\r\n", "\n")
    except OSError:
        text = "# Known problems — <project>\n\n## %s\n\n## %s\n" % (book.FOUND, book.WAIVED)
    return text.replace("<project>", project, 1)


def _add(home: str, sub: str, words: str) -> int:
    words = " ".join(words.split())      # one line: a line end can't start a heading, and the same words match
    line = redact.said(words).strip()
    hidden = line.count("[redacted") - words.count("[redacted")
    if hidden > 0:
        cli.warn("council: %d secret-looking string(s) redacted from the line" % hidden)
    section = SECTIONS[sub]
    project = os.path.basename(home.rsplit("/", 1)[0]) if "/" in home else home
    try:
        added = book.add(home, section, line, _template(project), clock.now_date())
    except (paths.RecordError, OSError) as failure:
        raise cli.Refusal("cannot write known problems: %s — name a file inside the project as `- known problems: "
                          "<path>` under the config's ## Book, then run this again" % failure) from None
    if added.already:
        cli.say("Kept %s — its ## %s already holds these words; nothing written" % (added.path, section))
    else:
        cli.say("Wrote %s — the line under ## %s%s" % (added.path, section,
                                                       ", in a new file from the template" if added.made else ""))
    return 0
