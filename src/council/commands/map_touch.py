"""council map touch <dir>="<line>" …: the user's line for each top-level area, under today's ## Changes section of
.council/map.md; map-commit moves to HEAD once every area changed since it has a line in this touch."""
from __future__ import annotations

from council import clock, git
from council.commands import cli
from council.records import bytewise, map_file
from council.records import home as where

SHAPE = 'council map touch <dir>="<line>" …'


def main(words: list[str]) -> int:
    pairs = [_pair(word) for word in words]
    shown = where.council_home()
    home = where.native(shown)
    if not map_file.path(home).is_file():
        raise cli.Refusal("no map yet — council-init builds .council/%s, and map touch adds to it" % map_file.NAME)
    sha = map_file.commit(home)
    if not sha:
        raise cli.Refusal("%s has no map-commit stamp — refresh the map and stamp it (council-init's Refresh), then "
                          "%s" % (map_file.NAME, SHAPE))
    head = git.text(".", "rev-parse", "-q", "--verify", "HEAD") or ""
    if not head or git.run(".", "cat-file", "-e", sha + "^{commit}")[0] != 0:
        raise cli.Refusal("map-commit %s isn't in this repo's history — rebuild the map (council-init's Refresh), "
                          "then %s" % (sha, SHAPE))
    behind = [area for area, _ in map_file.areas(map_file.changed(".", sha, "HEAD"))]
    lines = _named(pairs, set(behind) | set(_tracked()))
    day = clock.now_date()
    try:
        touched = map_file.touch(home, lines, head, behind, day)
    except OSError:
        raise cli.Refusal("could not write %s/%s — nothing changed; make that folder writable, then %s again"
                          % (shown, map_file.NAME, SHAPE)) from None
    cli.say("Wrote %s/%s — %d line(s) under %s%s" % (shown, map_file.NAME, len(lines), map_file.CHANGES, day))
    if touched.stamped:
        cli.say("map-commit now at %s (HEAD): every area changed since the stamp has a line" % head[:9])
    else:
        cli.say("map-commit stays at %s: no line here yet for %s, changed since it — give each a line too (%s), or "
                "refresh the map" % (sha[:9], ", ".join(touched.left), SHAPE))
    return 0


def _pair(word: str) -> tuple[str, str]:
    """(dir, line) from one <dir>="<line>" word, refused unless it has an = and one line that isn't empty."""
    area, equals, said = word.partition("=")
    said = said.strip()
    if not equals or not area:
        raise cli.Refusal("map touch takes <dir>=\"<line>\" pairs, and '%s' isn't one — for example: council map touch "
                          "src/=\"the parser moved into records/\"" % word)
    if not said:
        raise cli.Refusal("the line for %s is empty — give one line, in the user's words: council map touch "
                          "%s=\"<line>\"" % (area, area))
    if "\n" in said or "\r" in said:
        raise cli.Refusal("the line for %s spans more than one line — give it as one: council map touch %s=\"<line>\""
                          % (area, area))
    return area, said


def _named(pairs: list[tuple[str, str]], known: set[str]) -> list[tuple[str, str]]:
    """Each pair with its area as the map names it (src is src/), refused for an area this repo hasn't or one named
    twice."""
    named: list[tuple[str, str]] = []
    for given, said in pairs:
        area = given if given in known else given.rstrip("/") + "/"
        if area not in known:
            raise cli.Refusal("%s is not a top-level area of this repo — name a top-level folder (src/) or a root "
                              "file, as council map status lists them: %s" % (given, SHAPE))
        if area in {done for done, _ in named}:
            raise cli.Refusal("%s is named twice — give each area one line: %s" % (area, SHAPE))
        named.append((area, said))
    return named


def _tracked() -> list[str]:
    """The top-level areas of the files git tracks, in the index or at HEAD, from any folder."""
    names = git.run(".", "ls-files", "--full-name", "--with-tree=HEAD", "--", ":/", names=True)[1]
    return [area for area, _ in map_file.areas(bytewise.records(names.decode("utf-8", "surrogateescape"),
                                                                fold=False))]
