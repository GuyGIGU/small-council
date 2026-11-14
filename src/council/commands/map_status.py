"""council map status: how far the codebase map (.council/map.md) is behind HEAD — its map-commit stamp against the
history — and, when it is behind, the files changed since by top-level area (twelve areas at most, the busiest
first)."""
from __future__ import annotations

import subprocess

from council.commands import cli
from council.records import home as where
from council.records import map_file

AREAS = 12


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "map")
    if words != ["status"]:
        raise cli.Refusal("usage: council map status")
    for line in status(where.council_home()):
        cli.say(line)
    return 0


def _git(*args: str) -> tuple[int, str]:
    try:
        done = subprocess.run(["git"] + list(args), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        return 127, ""
    return done.returncode, done.stdout.decode("utf-8", "surrogateescape")


def status(home: str) -> list[str]:
    """The lines map status prints."""
    if not map_file.path(where.native(home)).is_file():
        return ["no map yet — council-init builds .council/" + map_file.NAME]
    sha = map_file.commit(where.native(home))
    if not sha:
        return ["map.md has no map-commit stamp — refresh the map and stamp it"]
    if _git("cat-file", "-e", sha + "^{commit}")[0] != 0:
        return ["map-commit %s isn't in this repo's history — rebuild the map" % sha]
    behind = _git("rev-list", "--count", sha + "..HEAD")[1].strip()
    if not behind or int(behind) == 0:
        return ["map: up to date (map-commit %s)" % sha[:9]]
    lines = ["map: %s commits behind HEAD (map-commit %s). Files changed since, by area:" % (behind, sha[:9])]
    # The whole repository, from any folder (paths are printed from the top).
    names = _git("-c", "core.quotePath=false", "-c", "diff.relative=false", "diff", "--name-only", sha, "HEAD")[1]
    return lines + by_area(names[:-1].split("\n") if names.endswith("\n") else names.split("\n") if names else [])


def by_area(names: list[str]) -> list[str]:
    """'  <count>  <area>' per top-level folder (with its slash) or root file, the busiest first and, at a tie, in
    reverse byte order (sort -rn), .council/ left out."""
    counts: dict[str, int] = {}
    for name in names:
        if name.startswith(".council/"):
            continue
        area = name.split("/", 1)[0] + "/" if "/" in name else name
        counts[area] = counts.get(area, 0) + 1
    rows = ["  %4d  %s" % (n, area) for area, n in counts.items()]
    rows.sort(key=lambda row: (int(row.split()[0]), row.encode("utf-8", "surrogateescape")), reverse=True)
    return rows[:AREAS]
