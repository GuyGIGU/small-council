"""council map status: how far the codebase map (.council/map.md) is behind HEAD — its map-commit stamp against the
history — and, when it is behind, the files changed since by top-level area (twelve areas at most, the busiest
first). council map touch is in map_touch."""
from __future__ import annotations


from council import git
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
    sha = map_file.commit(where.native(home))
    if not sha:
        return ["map.md has no map-commit stamp — refresh the map and stamp it"]
    if git.run(".", "cat-file", "-e", sha + "^{commit}")[0] != 0:
        return ["map-commit %s isn't in this repo's history — rebuild the map" % sha]
    behind = git.run(".", "rev-list", "--count", sha + "..HEAD")[1].decode().strip()
    if not behind or int(behind) == 0:
        return ["map: up to date (map-commit %s)" % sha[:9]]
    lines = ["map: %s commits behind HEAD (map-commit %s). Files changed since, by area:" % (behind, sha[:9])]
    return lines + by_area(map_file.changed(".", sha, "HEAD"))     # the whole repository, from any folder


def by_area(names: list[str]) -> list[str]:
    """'  <count>  <area>' per top-level area (map_file.areas), twelve at most."""
    return ["  %4d  %s" % (n, area) for area, n in map_file.areas(names)][:AREAS]
