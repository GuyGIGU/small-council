"""How a scope or an areas: list matches paths, seat slugs and modes: the memory's **Scope:**, the frontmatter areas:
of earlier council work. Text is read as the helper's awk read it in the C locale (bytewise): a byte past ASCII is
one character and only ASCII letters change case.

items() splits a list at commas and semicolons outside braces (and at blanks when every piece looks like a path),
drops ./, a leading /, backticks, quotes and a trailing note; covers(k, g) is true when key k is g, sits inside
folder g, or matches glob g — {a,b} is either, **/ may match no folder, and a single * matches STAR (a regex). A glob
with brackets is tried both as a character class and as literal brackets (app/[id]/**)."""
from __future__ import annotations

import re
from typing import NamedTuple

from council.records.bytewise import EM, EN, lower, trim

EVERY_RUN = ("all", "all files", "everywhere", "every run", "always", "global", "any", "repo-wide", "project-wide",
             "whole repo", "none", "n/a", "(none)", "*", "**", "-", EM, EN)
_NOTE = re.compile(r"[ \t]+\([^()]*\)\Z")
_ASIDE = re.compile(r"[ \t]+(" + EM + "|" + EN + r"|-)[ \t].*\Z", re.S)


class Item(NamedTuple):
    """One item of a list: its text, whether it is a blank-separated list read whole, and the whole item it is a
    piece of (its number in the list, from 1; 0 for none)."""

    text: str
    whole: bool
    piece_of: int


def normp(x: str) -> str:
    """A path as a scope item writes it: quotes, ./ and a leading / off, backslashes as slashes, no trailing dot or
    slash; res:// names the same file."""
    x = trim(re.sub("[`\"']", "", x).replace("\\", "/"))
    x = re.sub(r"^[Rr][Ee][Ss]://", "", x)
    while x.startswith("./"):
        x = x[2:]
    return re.sub(r"/+\Z", "", re.sub(r"[.]+\Z", "", re.sub(r"\A/+", "", x)))


def _add(x: str, out: list[Item], whole_at: list[int]) -> None:
    """One item. Blank-separated paths ("docs/** webapp/**") are separate items, but a path may hold a blank too
    ("docs/My Notes/**"), and nothing in the text says which: both readings are kept, the whole and its pieces, so a
    match either way counts. A quoted item is never split."""
    x = trim(x)
    quoted = bool(re.match(r"[`\"'].*[`\"']\Z", x, re.S))
    x = _ASIDE.sub("", _NOTE.sub("", x, count=1), count=1)
    if not quoted and re.search("[ \t]", x):
        parts = re.split("[ \t]+", x)
        if all(re.search("[/*]", part) for part in parts):
            w = normp(x)
            if w:
                out.append(Item(w, True, 0))
                whole_at[0] = len(out)
            out.extend(Item(p, False, whole_at[0]) for p in (normp(part) for part in parts) if p)
            return
    x = normp(x)
    if x:
        out.append(Item(x, False, 0))


def items(s: str) -> list[Item]:
    """A scope or areas list as its items."""
    out: list[Item] = []
    whole_at, depth, cur = [0], 0, ""
    for c in s:
        if c == "{":
            depth += 1
        elif c == "}" and depth:
            depth -= 1
        if c in ",;" and not depth:
            _add(cur, out, whole_at)
            cur = ""
        else:
            cur += c
    _add(cur, out, whole_at)
    return out


def expand(g: str, out: list[str] | None = None) -> list[str]:
    """A glob's {a,b} alternatives, each its own glob (64 at most)."""
    out = [] if out is None else out
    start = end = depth = 0
    for i, c in enumerate(g, 1):
        if c == "{":
            if not depth:
                start = i
            depth += 1
        elif c == "}" and depth:
            depth -= 1
            if not depth:
                end = i
                break
    if not start or not end or len(out) >= 64:
        out.append(g)
        return out
    body, alts, depth, cur = g[start:end - 1], [], 0, ""
    for c in body:
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        if c == "," and not depth:
            alts.append(cur)
            cur = ""
        else:
            cur += c
    alts.append(cur)
    if len(alts) < 2:
        out.append(g)
        return out
    for alt in alts:
        expand(g[:start - 1] + alt + g[end:], out)
    return out


def glob_re(g: str, star: str, literal: bool) -> str:
    """A glob as a regex for the whole key: **/ any folders or none, ** anything, * STAR, ? one character (not a
    slash unless STAR is .*), [abc] a class unless literal."""
    r, i = "", 0
    while i < len(g):
        if g.startswith("**/", i):
            r, i = r + "(.*/)?", i + 3
            continue
        if g.startswith("**", i):
            r, i = r + ".*", i + 2
            continue
        c = g[i]
        j = g.find("]", i + 1) - i
        if c == "[" and not literal and j > 1 and re.fullmatch(r"!?[A-Za-z0-9_.-]+", g[i + 1:i + j]):
            r, i = r + "[" + re.sub("^!", "^", g[i + 1:i + j]) + "]", i + j + 1
            continue
        if c == "*":
            r += star
        elif c == "?":
            r += "." if star == ".*" else "[^/]"
        elif c in "\\^$.[]|()+{}":
            r += "\\" + c
        else:
            r += c
        i += 1
    return r


class Glob(NamedTuple):
    """One expansion of a glob: its text, and its regexes as a class and with literal brackets (None: no glob)."""

    text: str
    rx: re.Pattern | None
    literal: re.Pattern | None


_PREPPED: dict[tuple[str, str], list[Glob]] = {}


def _compiled(pattern: str) -> re.Pattern | None:
    try:
        return re.compile(pattern, re.S)
    except re.error:                       # awk stops on a range it can't read: it matches nothing here
        return None


def prep(g: str, star: str) -> list[Glob]:
    """The expansions and regexes of g, once."""
    key = (star, g)
    if key not in _PREPPED:
        found = []
        for e in expand(g):
            rx = _compiled(glob_re(e, star, False)) if re.search(r"[*?\[]", e) else None
            lit = _compiled(glob_re(e, star, True)) if "[" in e and rx is not None else None
            found.append(Glob(e, rx, lit))
        _PREPPED[key] = found
    return _PREPPED[key]


def covers(k: str, g: str, star: str, folder: bool) -> bool:
    """Key k (a path, a slug, a mode) is g, sits inside folder g, or matches glob g. A folder key also covers a scope
    that sits inside it."""
    if k == g or k.startswith(g + "/"):
        return True
    if folder and g.startswith(k + "/"):
        return True
    for e in prep(g, star):
        if k == e.text or k.startswith(e.text + "/"):
            return True
        for rx in (e.rx, e.literal):
            if rx is not None and (rx.fullmatch(k) or (folder and rx.fullmatch(k + "/"))):
                return True
    return False


def everyrun(s: str) -> bool:
    """A scope that means every run."""
    return re.sub("[.`]", "", lower(trim(s))) in EVERY_RUN
