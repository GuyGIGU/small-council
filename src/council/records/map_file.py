"""map.md, the project's codebase map in the council home: its one-way-per-job table (job · owner · the one way ·
anchor path), which a plan task's Owner row names; its map-commit stamp; the top-level areas changed since a
commit, and how far the map is behind HEAD by area (stale); and its one writer, which adds the user's lines under a
dated ## Changes section."""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from council import git
from council.records import bytewise, cells, paths

NAME = "map.md"
TABLE = "## One way per job"
CHANGES = "## Changes "


class Way(NamedTuple):
    job: str
    owner: str
    way: str
    anchor: str


def path(home: str | Path) -> Path:
    return Path(home) / NAME


def cells_of(line: str) -> list[str]:
    """A Markdown table row's cells (cells.table_cells: a pipe in a code span, or escaped, stays in its cell),
    trimmed, bold and backticks dropped."""
    found = cells.table_cells(line.strip())
    found = found[1:] if found[:1] == [""] else found
    found = found[:-1] if len(found) > 1 and found[-1] == "" else found
    return [re.sub(r"[*`]", "", cell).strip() for cell in found]


def ways(content: str) -> list[Way] | None:
    """The table's rows (header and divider left out, a row with no job skipped); None when the map has no
    such table, so an older project's map is never read as one with no ways."""
    rows, inside, seen = [], False, False
    for line in content.split("\n"):
        line = line.rstrip("\r")
        if line.startswith("## "):
            inside = cells.heading(line) == TABLE[3:].lower()
            seen = seen or inside
            continue
        if not inside or not line.lstrip().startswith("|"):
            continue
        row = (cells_of(line) + ["", "", "", ""])[:4]
        if re.fullmatch(r"[-: ]*", "".join(row)) or row[0].lower() == "job":
            continue
        if row[0]:
            rows.append(Way(*row))
    return rows if seen else None


def read(home: str | Path) -> list[Way] | None:
    """The table from a council home's map; None when there is no map or no table."""
    content = paths.text_of(path(home), home)
    return ways(content) if content else None


_STAMP = re.compile(r"map-commit:[ \t\n\v\f\r]*([0-9a-fA-F]{7,40})")


def commit(home: str | Path) -> str:
    """The commit the map was built at (its first map-commit: line, 7 to 40 hex digits); '' when it has none."""
    try:
        data = path(home).read_bytes()
    except OSError:
        return ""
    found = _stamp(data.decode("utf-8", "surrogateescape").split("\n"))
    return found[1].group(1) if found else ""


def _stamp(lines: list[str]) -> tuple[int, re.Match] | None:
    """The first map-commit: line with a commit: its index and match."""
    for n, line in enumerate(lines):
        found = _STAMP.match(line)
        if found:
            return n, found
    return None


class Stale(NamedTuple):
    """How far map.md is from HEAD: its map-commit stamp ('' with none), whether that commit is in this repo's
    history, the commits from it to HEAD (behind), the files changed since it by top-level area (areas), the busiest
    first: the staleness of each area; and the commits of the map's line that HEAD doesn't have (aside): more than
    none, and the map was built on another line of history, or HEAD is behind it."""
    sha: str
    known: bool
    behind: int
    areas: list[tuple[str, int]]
    aside: int = 0


def stale(home: str | Path, top: str | Path = ".", disk: bool = False) -> Stale:
    """The one reader of the map's staleness, for council map status, map touch, council doctor, the close's map
    warning and the SessionStart banner: from top, the whole repository whatever folder top is. An area is stale
    when files under it changed after the later of map-commit and the area's last touch (touches). With disk, the
    files changed on disk and not yet committed count too: an area touched at HEAD counts them as covered."""
    sha = commit(home)
    if not sha or git.run(top, "cat-file", "-e", sha + "^{commit}")[0] != 0:
        return Stale(sha, False, 0, [])
    counts = git.run(top, "rev-list", "--left-right", "--count", sha + "...HEAD")[1].decode("ascii", "replace").split()
    aside, behind = (int(n) for n in counts) if len(counts) == 2 and all(n.isdigit() for n in counts) else (0, 0)
    if not (behind or aside or disk):
        return Stale(sha, True, 0, [], 0)
    names = changed(top, sha, "" if disk else "HEAD")
    return Stale(sha, True, behind, areas(_since_touch(home, top, sha, names)), aside)


def _since_touch(home: str | Path, top: str | Path, sha: str, names: list[str]) -> list[str]:
    """The names changed since map-commit, less those in an area whose last touch is later than it (map-commit is
    its ancestor) and that haven't changed since that touch."""
    later: dict[str, set[str]] = {}
    for where, at in touches(home).items():
        if git.run(top, "merge-base", "--is-ancestor", sha, at)[0] == 0:
            later[where] = set(changed(top, at, "HEAD"))
    return [name for name in names if area_of(name) not in later or name in later[area_of(name)]]


_AT = re.compile(r" \(at ([0-9a-fA-F]{7,40})\)$")


def touches(home: str | Path) -> dict[str, str]:
    """Each area's last touch: the commit that ends its last `- <area>: <line> (at <commit>)` under a ## Changes
    section. A line written before touches named their commit has none, and is passed over."""
    found: dict[str, str] = {}
    inside = False
    for line in paths.text_of(path(home), home).split("\n"):
        line = line.rstrip("\r")
        if line.startswith("## "):
            inside = line.startswith(CHANGES)
        elif inside and line.startswith("- ") and ": " in line:
            at = _AT.search(line)
            if at:
                found[line[2:].split(": ", 1)[0]] = at.group(1)
    return found


def area_of(name: str) -> str:
    """A file's top-level area: its top folder with the slash, or the root file itself."""
    return name.split("/", 1)[0] + "/" if "/" in name else name


def areas(names: list[str]) -> list[tuple[str, int]]:
    """(area, files) per top-level folder (with its slash) or root file, the busiest first and, at a tie, in
    reverse byte order (sort -rn), .council/ left out."""
    counts: dict[str, int] = {}
    for name in names:
        if name.startswith(".council/"):
            continue
        area = area_of(name)
        counts[area] = counts.get(area, 0) + 1
    return sorted(counts.items(), key=lambda pair: (pair[1], pair[0].encode("utf-8", "surrogateescape")),
                  reverse=True)


def changed(top: str | Path, since: str, until: str = "") -> list[str]:
    """The files changed from a commit to `until` (a commit) or, without it, to the tracked files on disk, named from
    the top of the repository whatever folder top is."""
    names = git.run(top, "-c", "diff.relative=false", "diff", "--name-only", since, *([until] if until else []),
                    names=True)[1]
    return bytewise.records(names.decode("utf-8", "surrogateescape"), fold=False)


class Touched(NamedTuple):
    stamped: bool        # map-commit moved to HEAD
    left: list[str]      # the areas changed since the stamp that this touch did not cover


def touch(home: str | Path, lines: list[tuple[str, str]], head: str, behind: list[str], day: str) -> Touched:
    """Add `- <area>: <line> (at <head>)` for each pair under ## Changes <day> at the end of the map (to that section
    when it is already the last one), through the one atomic write; the commit is what stale reads the area from.
    map-commit moves to head only when the pairs cover every area in behind (the stale areas); no other line or
    section changes. Raises OSError."""
    data = path(home).read_bytes().decode("utf-8", "surrogateescape")
    nl = "\r\n" if "\r\n" in data else "\n"
    rows = data.split("\n")
    left = [area for area in behind if area not in {area for area, _ in lines}]
    stamp = _stamp(rows)
    if stamp and not left:
        n, found = stamp
        rows[n] = rows[n][:found.start(1)] + head + rows[n][found.end(1):]
    text = "\n".join(rows)
    if text and not text.endswith("\n"):
        text += nl
    heads = [row.rstrip("\r") for row in text.split("\n") if row.startswith("## ")]
    if heads[-1:] != [CHANGES + day]:
        text += (nl if text and not text.endswith(nl + nl) else "") + CHANGES + day + nl
    text += "".join("- %s: %s (at %s)%s" % (area, said, head[:12], nl) for area, said in lines)
    paths.atomic_write(path(home), text.encode("utf-8", "surrogateescape"), ".map.", keep_mode=True)
    return Touched(bool(stamp) and not left, left)
