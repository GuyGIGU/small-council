"""council doctor's book findings (D52, references/run/book.md), read through the book's own reader: a config with
no `## Book` section (a setup from before the book); a page the section names at the project's own place that isn't
there; no design page or stack page yet (the decisions log and known problems may wait for their first entry); and a
design page or stack page past its size. All are warnings: a run still goes, but every agent starts weaker."""
from __future__ import annotations

import os

from council.commands.doctor import Doctor
from council.records import book, paths
from council.records import home as where

REFRESH = "run a council-init refresh: it adopts the project's own design, stack and decisions files or writes the " \
          "pages, and names each under ## Book (references/run/book.md)"
WHY = {"design": "the project's parts, who owns each folder and the one way each job is done",
       "stack": "what the project is built with and why, so nothing tells a builder that a new library is the "
                "owner's decision (D54)"}
NONE = {"design": "delete the line, then run a council-init refresh to write the page",
        "stack": "delete the line, then run a council-init refresh to write the page",
        "decisions": "delete the line: the decisions log is then the memory file's ## Decisions (D)",
        "known problems": "delete the line: the first council book note then starts {0}"}


def report(doc: Doctor) -> None:
    pages = book.pages(doc.home)
    if not book.in_config(doc.home):
        absent = [page.name for page in pages if page.name in ("design", "stack") and not page.there]
        doc.warn("the config has no ## Book section (set up before the book): every agent reads the design page, the "
                 "stack page and the decisions log before anything else, from their default places under %s%s"
                 % (_shown(doc, doc.home), "; not written yet: " + ", ".join(absent) if absent else ""), REFRESH)
        return
    said: set[str] = set()
    for page in pages:
        if not page.there and page.path not in said:
            said.add(page.path)
            missing(doc, page)
    for page in pages:
        if page.name in book.LINES and not (page.name == "stack" and page.path == book.page(doc.home, "design").path):
            size(doc, page)


def missing(doc: Doctor, page: book.Page) -> None:
    """A page that isn't there: named at a place of the project's own, or not written yet at its default."""
    if page.memory:
        return                                 # the memory file: doctor's memory findings name it
    if page.configured and page.path != book.default(doc.home, page.name):
        then = ("the next council book note starts a new file there" if page.name == "known problems"
                else "every agent is told to read it first and finds nothing")
        doc.warn("the config's ## Book names %s as the %s, and it doesn't exist: %s"
                 % (_shown(doc, page.path), _called(page.name), then),
                 "if it moved, point `- %s:` under ## Book at it; if the project has none, %s"
                 % (page.name, NONE[page.name].format(_shown(doc, book.default(doc.home, page.name)))))
    elif page.name in ("design", "stack"):
        doc.warn("no %s yet (%s): every agent reads it before anything else, so each starts without %s"
                 % (_called(page.name), _shown(doc, page.path), WHY[page.name]), REFRESH)


def size(doc: Doctor, page: book.Page) -> None:
    """A design or stack page past book.md's size: an agent reads all of it before anything else."""
    data = paths.contents(where.native(page.path)) if os.path.isfile(where.native(page.path)) else None
    lines = len(data.decode("utf-8", "replace").splitlines()) if data else 0
    if lines > book.LINES[page.name]:
        doc.warn("the %s (%s) is %d lines, past its %d-line limit: every agent reads all of it before anything else"
                 % (_called(page.name), _shown(doc, page.path), lines, book.LINES[page.name]),
                 "propose cuts to the owner as numbered lines, never a rewrite: a line stays only if removing it "
                 "would change what an agent does, and every rule keeps its reason and date (references/run/book.md, "
                 "What earns a line)")


def _called(name: str) -> str:
    return {"decisions": "decisions log", "known problems": "known-problems page"}.get(name, name + " page")


def _shown(doc: Doctor, path: str) -> str:
    """A path as the owner knows it: from the project's folder when it is inside it."""
    return path[len(doc.root) + 1:] if path.startswith(doc.root + "/") else path
