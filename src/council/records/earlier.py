"""Earlier council work on some paths: the deliverables under the council home (reviews, logs, research, plans and
post-games) that mention each path, or whose frontmatter areas: cover it; and the paths a run's change index lists,
which are what `council index` and `council prior` look up. Text is read bytewise, as the helper's awk read it in
the C locale (records/bytewise.py): hits come back as that text, a command shows them with bytewise.shown."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import NamedTuple

from council.records import bytewise, scope
from council.records import home as where
from council.records.paths import contents
from council.records.run_files import INDEX

DELIVERABLES = ("reviews", "logs", "research", "plans", "postgames")
_NAMED = re.compile(rb"## (.*)  \(")
_PATHISH = re.compile(r"[A-Za-z0-9_./-]")
_DOTS = re.compile(r"(^|[^A-Za-z0-9_./-])(\./)+\Z")
_AFTER = re.compile(r"[A-Za-z0-9_/-]|\.[A-Za-z0-9_]")


def indexed(run: Path) -> list[str]:
    """The changed files a run's index.md lists (its "## <path>  (…)" headings), as C-locale text; none when it has
    no index."""
    try:
        data = (run / INDEX).read_bytes()
    except OSError:
        return []
    found = (_NAMED.match(line) for line in data.split(b"\n"))
    return [bytewise.read(m.group(1)) for m in found if m]


def deliverables(home: str) -> list[str]:
    """Every deliverable under the council home, folder by folder in DELIVERABLES' order, names in byte order."""
    found = []
    for folder in DELIVERABLES:
        base = home + "/" + folder
        try:
            names = os.listdir(where.native(base))
        except OSError:
            continue
        for name in sorted((n for n in names if n.endswith(".md") and not n.startswith(".")),
                           key=lambda n: n.encode("utf-8", "surrogateescape")):
            if os.path.isfile(where.native(base + "/" + name)):
                found.append(folder + "/" + name)
    return found


class Hit(NamedTuple):
    """One mention, as C-locale text: the path, where (<folder>/<file>:<line>) and the line clipped; or, for a
    deliverable whose areas cover the path, <folder>/<file> and "(its areas cover <item>)"."""

    path: str
    where: str
    text: str


def hits(home: str, paths: list[str]) -> list[Hit]:
    """For each deliverable, each path it names, else whose areas cover it. paths are C-locale text, each taken
    as given."""
    if not any(paths):
        return []
    wanted = [scope.normp(p) for p in paths]
    top = home[:home.rfind("/")] if "/" in home else home
    reader = Reader(wanted, bytewise.lower(bytewise.text(top)))
    found: list[Hit] = []
    for shown in deliverables(home):
        data = contents(where.native(home + "/" + shown))
        if data:
            found.extend(reader.file(bytewise.text(shown), bytewise.read(data)))
    return found


class Reader:
    """One pass over each deliverable for every path."""

    def __init__(self, paths: list[str], top: str) -> None:
        self.paths, self.top = paths, top

    def file(self, shown: str, text: str) -> list[Hit]:
        hit: list[Hit | None] = [None] * len(self.paths)
        areas: list[str] = []
        in_front = in_areas = False
        for n, line in enumerate(bytewise.lines(text), 1):
            if n == 1 and line == "---":
                in_front = True
            elif in_front:
                in_front, in_areas = self.front(line, in_areas, areas)
            else:
                self.mentions(line, "%s:%d" % (shown, n), hit)
        return self.rows(shown, hit, areas)

    @staticmethod
    def front(line: str, in_areas: bool, areas: list[str]) -> tuple[bool, bool]:
        """One frontmatter line: (still in the frontmatter, inside a block areas: list)."""
        if line == "---":
            return False, False
        if line.startswith("areas:"):
            value = re.sub(r"\Aareas:[ \t]*", "", line)
            if value == "" or value.startswith("#"):
                return True, True
            _areas(value, areas)
            return True, False
        if in_areas and re.match(r"[ \t]*-", line):
            _areas(re.sub(r"\A[ \t]*-[ \t]*", "", line), areas)
            return True, True
        return True, bool(in_areas and re.match(r"[ \t]*(#|\Z)", line))

    def mentions(self, line: str, where_at: str, hit: list[Hit | None]) -> None:
        """A path counts where it appears whole: not inside a longer path or name (api.py.bak), though ./, res://
        or the repo's own absolute path may come before it, and backslashes read as slashes."""
        s0 = line.replace("\\", "/")
        for i, path in enumerate(self.paths):
            if not path or hit[i]:
                continue
            at = s0.find(path)
            while at >= 0:
                after = s0[at + len(path):at + len(path) + 2]
                if self.boundary(s0, at) and not _AFTER.match(after):
                    hit[i] = Hit(path, where_at, bytewise.clip(line.lstrip(" \t"), 120))
                    break
                at = s0.find(path, at + 1)

    def boundary(self, s: str, at: int) -> bool:
        """May a mention start at s[at]?"""
        if at == 0 or not _PATHISH.match(s[at - 1]):
            return True
        pre = bytewise.lower(s[:at])
        if _DOTS.search(pre) or pre.endswith("res://"):
            return True
        top = self.top
        return top != "" and len(pre) >= len(top) + 1 and pre[len(pre) - len(top) - 1:] == top + "/"

    def rows(self, shown: str, hit: list[Hit | None], areas: list[str]) -> list[Hit]:
        found = []
        for i, path in enumerate(self.paths):
            if not path:
                continue
            named = hit[i]
            if named:
                found.append(named)
                continue
            area = next((a for a in areas if scope.covers(path, a, "[^/]*", False)), None)
            if area is not None:
                found.append(Hit(path, shown, "(its areas cover %s)" % area))
        return found


def line(hit: Hit) -> str:
    """A hit as it is listed: its three fields joined by em dashes."""
    return (" %s " % bytewise.EM).join(hit)


def _areas(value: str, areas: list[str]) -> None:
    """An areas: value's items (inline, [bracketed] or one item of a - list; a # comment dropped)."""
    value = re.sub(r"(^|[ \t])#.*\Z", "", value, count=1, flags=re.S).replace("[", "").replace("]", "")
    areas.extend(item.text for item in scope.items(value))
