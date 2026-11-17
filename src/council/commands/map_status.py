"""council map status: how far the codebase map (.council/map.md) is behind HEAD — its map-commit stamp against the
history — and, when it is behind, the files changed since by top-level area (twelve areas at most, the busiest
first). council map touch is in map_touch."""
from __future__ import annotations

from council.commands import cli
from council.records import home as where
from council.records import map_file

AREAS = 12
NO_MAP = ("no map yet — write .council/%s from the plugin's references/templates/%s, as Prepare says, or run "
          "council-init, which builds it" % (map_file.NAME, map_file.NAME))
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
        return [NO_MAP]
    found = map_file.stale(where.native(home))          # the whole repository, from any folder
    if not found.sha:
        return ["map.md has no map-commit stamp — refresh the map and stamp it"]
    if not found.known:
        return ["map-commit %s isn't in this repo's history — rebuild the map" % found.sha]
    if found.aside:
        return ["map: from another line of history — map-commit %s has %d commit(s) HEAD doesn't%s, so it can't say "
                "what is up to date here; refresh the map on this branch, or check out the one it was built on"
                % (found.sha[:9], found.aside, " (HEAD has %d of its own)" % found.behind if found.behind else "")
                ] + (["Files that differ from it, by area:"] + by_area(found.areas) if found.areas else [])
    if not found.behind:
        return ["map: up to date (map-commit %s)" % found.sha[:9]]
    if not found.areas:
        return ["map: up to date by area (map-commit %s, %d commits behind HEAD: no area's files changed since it, or "
                "since the area's last touch)" % (found.sha[:9], found.behind)]
    lines = ["map: %d commits behind HEAD (map-commit %s). Files changed since, by area:" % (found.behind,
                                                                                           found.sha[:9])]
    return lines + by_area(found.areas)


def by_area(areas: list[tuple[str, int]]) -> list[str]:
    """'  <count>  <area>' per top-level area (map_file.areas), twelve at most."""
    return ["  %4d  %s" % (n, area) for area, n in areas][:AREAS]
