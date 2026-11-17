"""map.md, the project's codebase map in the council home: its one-way-per-job table (job · owner · the one way ·
anchor path), which a plan task's Owner row names; its map-commit stamp; the top-level areas changed since a
commit, and how far the map is behind HEAD by area (stale); and its one writer, which adds the user's lines under a
dated ## Changes section."""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from council import git
from council.records import bytewise, paths

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
    """A Markdown table row's cells, trimmed, bold and backticks dropped."""
    inner = line.strip().strip("|")
    return [re.sub(r"[*`]", "", cell).strip() for cell in inner.split("|")]


def ways(content: str) -> list[Way] | None:
    """The table's rows (header and divider left out, a row with no job skipped); None when the map has no
    such table, so an older project's map is never read as one with no ways."""
    rows, inside, seen = [], False, False
    for line in content.split("\n"):
        line = line.rstrip("\r")
        if line.startswith("## "):
            inside = line.rstrip() == TABLE
            seen = seen or inside
            continue
        if not inside or not line.lstrip().startswith("|"):
            continue
        cells = (cells_of(line) + ["", "", "", ""])[:4]
        if re.fullmatch(r"[-: ]*", "".join(cells)) or cells[0].lower() == "job":
            continue
        if cells[0]:
            rows.append(Way(*cells))
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
    """How far map.md is behind HEAD: its map-commit stamp ('' with none), whether that commit is in this repo's
    history, the commits from it to HEAD, and the files changed since it by top-level area (areas), the busiest
    first: the staleness of each area."""
    sha: str
    known: bool
    behind: int
    areas: list[tuple[str, int]]


def stale(home: str | Path, top: str | Path = ".") -> Stale:
    """The one reader of the map's staleness, for council map status and the SessionStart banner: from top, the
    whole repository whatever folder top is."""
    sha = commit(home)
    if not sha or git.run(top, "cat-file", "-e", sha + "^{commit}")[0] != 0:
        return Stale(sha, False, 0, [])
    count = git.run(top, "rev-list", "--count", sha + "..HEAD")[1].decode("ascii", "replace").strip()
    behind = int(count) if count.isdigit() else 0
    return Stale(sha, True, behind, areas(changed(top, sha, "HEAD")) if behind else [])


def areas(names: list[str]) -> list[tuple[str, int]]:
    """(area, files) per top-level folder (with its slash) or root file, the busiest first and, at a tie, in
    reverse byte order (sort -rn), .council/ left out."""
    counts: dict[str, int] = {}
    for name in names:
        if name.startswith(".council/"):
            continue
        area = name.split("/", 1)[0] + "/" if "/" in name else name
        counts[area] = counts.get(area, 0) + 1
    return sorted(counts.items(), key=lambda pair: (pair[1], pair[0].encode("utf-8", "surrogateescape")),
                  reverse=True)


def changed(top: str | Path, since: str, until: str = "") -> list[str]:
    """The files changed from a commit to `until` (a commit) or, without it, to the tracked files on disk, named from
    the top of the repository whatever folder top is."""
    names = git.run(top, "-c", "diff.relative=false", "diff", "--name-only", since, *([until] if until else []),
                    names=True)[1]
    return bytewise.records(names.decode("utf-8", "surrogateescape"), fold=False)


def noted(home: str | Path, since: str) -> set[str]:
    """The areas a `- <area>: <line>` names under a ## Changes <YYYY-MM-DD> section dated on or after since."""
    found, inside = set(), False
    for line in paths.text_of(path(home), home).split("\n"):
        line = line.rstrip("\r")
        if line.startswith("## "):
            day = line[len(CHANGES):].strip() if line.startswith(CHANGES) else ""
            inside = bool(re.fullmatch(r"\d{4}-\d\d-\d\d", day)) and day >= since
        elif inside and line.startswith("- ") and ": " in line:
            found.add(line[2:].split(": ", 1)[0])
    return found


class Touched(NamedTuple):
    stamped: bool        # map-commit moved to HEAD
    left: list[str]      # the areas changed since the stamp that this touch did not cover


def touch(home: str | Path, lines: list[tuple[str, str]], head: str, behind: list[str], day: str) -> Touched:
    """Add `- <area>: <line>` for each pair under ## Changes <day> at the end of the map (to that section when it
    is already the last one), through the one atomic write. map-commit moves to head only when the pairs cover every
    area in behind (the areas changed since the stamp); no other line or section changes. Raises OSError."""
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
    text += "".join("- %s: %s%s" % (area, said, nl) for area, said in lines)
    paths.atomic_write(path(home), text.encode("utf-8", "surrogateescape"), ".map.", keep_mode=True)
    return Touched(bool(stamp) and not left, left)
