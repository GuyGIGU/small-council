"""Watch lists (D73, references/watch-lists.md): the checklist pages a row of the book's stack page names for its
part of the stack, and where each one is.

The stack page's table has a `Watch lists` column. A cell names zero or more lists, comma separated: a shipped list
by its name (`quality-postgres`, which is the plugin's references/quality-postgres.md) or a page by its path
(`references/security.md` in the plugin; anything else, such as `.council/refs/godot.md`, from the folder that holds
the council home). A page with no such column names none.
"""
from __future__ import annotations

import os
import re
from typing import NamedTuple

from council.records import book, cells, paths
from council.records import home as where

COLUMN = "watch lists"
NONE = ("", "-", "—", "none", "n/a")


class Row(NamedTuple):
    """One stack row that names watch lists: the part (its What cell, else its first) and each list as
    (the name as written, its path, whether a file is there)."""

    part: str
    lists: list[tuple[str, str, bool]]


def _clean(cell: str) -> str:
    return re.sub(r"[`*]", "", cell).strip(" \t\r")


def place(name: str, root: str) -> str:
    """Where a list is: a bare name is the plugin's references/<name>.md, a references/ path the plugin's file, any
    other path the project's (an absolute one as it stands)."""
    if "/" not in name and not name.endswith(".md"):
        return "%s/references/%s.md" % (where.plugin_root(), name)
    if name.startswith("references/"):
        return "%s/%s" % (where.plugin_root(), name)
    return name if where.absolute(name) else "%s/%s" % (root, name)


def named(cell: str) -> list[str]:
    """The lists a Watch lists cell names, in order, each once; a placeholder (`<…>`) or a word for none names
    none."""
    found: list[str] = []
    for piece in _clean(cell).replace("\\", "/").split(","):
        name = piece.strip(" \t")
        if name.lower() not in NONE and not name.startswith("<") and name not in found:
            found.append(name)
    return found


def rows(home: str) -> list[Row]:
    """Each row of the stack page that names a watch list, in the page's order; none when the page is missing, is a
    folder, or has no table with a Watch lists column."""
    page = book.page(home, "stack")
    data = paths.contents(where.native(page.path)) if page.there and not os.path.isdir(where.native(page.path)) else None
    if data is None:
        return []
    root = home[:home.rfind("/")] if "/" in home else home
    found, at, what = [], None, 1
    for line in cells.lines_of(data.decode("utf-8", "replace")):
        if not line.startswith("|"):
            at = None                                     # a table ends at the first line outside it
            continue
        cut = cells.table_cells(line)
        if at is None:
            names = [_clean(c).lower() for c in cut]
            at = names.index(COLUMN) if COLUMN in names else 0
            what = names.index("what") if "what" in names else 1
            continue
        if at == 0 or at >= len(cut) or re.fullmatch(r":?-+:?", _clean(cut[at]) or "-"):
            continue
        lists = [(name, place(name, root).replace("\\", "/")) for name in named(cut[at])]
        if lists:
            part = _clean(cut[what]) if what < len(cut) else ""
            found.append(Row(part, [(name, path, os.path.isfile(where.native(path))) for name, path in lists]))
    return found
