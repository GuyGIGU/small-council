"""council map status: how far the codebase map (.council/map.md) is behind HEAD — its map-commit stamp against the
history — and, when it is behind, the files changed since by top-level area (twelve areas at most, the busiest
first). council map touch is in map_touch."""
from __future__ import annotations

from council.commands import cli
from council.records import home as where
from council.records import map_file

AREAS = 12
USAGE = 'usage: council map status | map touch <dir>="<line>" …'


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "map")
    if words[:1] == ["touch"] and words[1:]:
        from council.commands import map_touch    # only a touch loads it (D34)
        return map_touch.main(words[1:])
    if words != ["status"]:
        raise cli.Refusal(USAGE)
    cli.say_all(status(where.council_home()))
    return 0


def status(home: str) -> list[str]:
    if not map_file.path(where.native(home)).is_file():
        return ["no map yet — council-init builds .council/" + map_file.NAME]
    found = map_file.stale(where.native(home))          # the whole repository, from any folder
    if not found.sha:
        return ["map.md has no map-commit stamp — refresh the map and stamp it"]
    if not found.known:
        return ["map-commit %s isn't in this repo's history — rebuild the map" % found.sha]
    if not found.behind:
        return ["map: up to date (map-commit %s)" % found.sha[:9]]
    lines = ["map: %d commits behind HEAD (map-commit %s). Files changed since, by area:" % (found.behind,
                                                                                           found.sha[:9])]
    return lines + by_area(found.areas)


def by_area(areas: list[tuple[str, int]]) -> list[str]:
    """'  <count>  <area>' per top-level area (map_file.areas), twelve at most."""
    return ["  %4d  %s" % (n, area) for area, n in areas][:AREAS]
