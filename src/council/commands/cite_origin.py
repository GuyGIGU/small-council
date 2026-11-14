"""Where the lines a citation names come from: introduced | touched | pre-existing | new file | run file | origin
unknown [(…)], from git blame against the change's base and from the change's own hunks. `council check` reads
it for every citation that resolved."""
from __future__ import annotations

import os
import re

from council.commands.cite_check import Scope, absolute, git_ok, git_out, rel, run_cited
from council.records import citations
from council.records.home import native

SHA = re.compile(r"[0-9a-f]+")


def _number(text: str) -> int:
    """awk's numeric reading of a string: its leading digits, 0 without."""
    found = re.match(r"[ \t]*[+-]?[0-9]+", text)
    return int(found.group(0)) if found else 0


def hunks(diff: bytes, spans: list[tuple[int, int]]) -> tuple[int, int, int]:
    """From a -U0 diff and the cited spans: (a hunk inside or right next to a span, an added line inside a span,
    the file is not in the base under this name), each 0 or 1. A hunk's new side "+c,0" is lines removed after
    line c. A file the change added — or only renamed — shows as one big added hunk."""
    near = inside = new = 0
    for line in diff.decode("utf-8", "surrogateescape").split("\n"):
        if line.startswith("new file mode "):
            new = 1
        if not line.startswith("@@ "):
            continue
        words = [w for w in re.split(r"[ \t]+", line) if w]
        side = words[2][1:] if len(words) > 2 and words[2].startswith("+") else (words[2] if len(words) > 2 else "")
        start, count = _number(side), 1
        if "," in side:
            start, count = _number(side[:side.index(",")]), _number(side[side.index(",") + 1:])
        for first, last in spans:
            if count == 0:
                near |= first - 1 <= start <= last
                continue
            near |= start <= last + 1 and start + count - 1 >= first - 1
            inside |= start <= last and start + count - 1 >= first
    return int(near), int(inside), new


class _Tally:
    def __init__(self) -> None:
        self.old = self.new = self.near = self.unknown = self.crlf = self.untracked = self.own = 0


def origin(where: Scope, rows: list[tuple[str, ...]]) -> str:
    """The origin of every line place the rows name, as one word (see the module's doc); '' when none applies.
    Lines the change removed or added inside or right next to a cited span make it "touched" even when every
    cited line is old. A file the change deleted is "touched". When blame can't read a tracked file, or a line
    reads as new only because its line ending changed, the origin is unknown rather than a guess."""
    tally = _Tally()
    for row in rows:
        if row[0] == "L":
            spans = citations.ranges(row[2])
            if spans is not None:
                _one(where, tally, row[1], spans)
    if tally.old == 0 and tally.new == 0:
        for count, word in ((tally.near, "touched"), (tally.untracked, "new file"), (tally.own, "run file"),
                            (tally.crlf, "origin unknown (only line endings changed)"),
                            (tally.unknown, "origin unknown")):
            if count:
                return word
        return ""
    new = tally.new + tally.untracked
    if new == 0:
        return "pre-existing" if tally.near == 0 else "touched"
    return "introduced" if tally.old == 0 else "touched"


def _one(where: Scope, tally: _Tally, path: str, spans: list[tuple[int, int]]) -> None:
    top, base = where.top, where.base
    if run_cited(where, path, top):
        tally.own += 1                                       # the run's own record, not code
        return
    file = path if absolute(path) else top + "/" + path
    inside = rel(top, file)
    if not os.path.isfile(native(file)):
        tally.near += git_ok(top, "cat-file", "-e", "%s:%s" % (base, inside))    # the change deleted it
        return
    if inside == file:
        tally.unknown += 1                                   # outside this repository
        return
    real = git_out(top, "-c", "core.quotePath=false", "ls-files", "--", ":(icase,literal)" + inside)
    named = [line for line in real.decode("utf-8", "surrogateescape").rstrip("\n").split("\n") if line]
    if len(named) == 1:
        inside = real.decode("utf-8", "surrogateescape").rstrip("\n")    # its real name, case and all
    old, new = _blamed(where, inside, spans)
    if old is None:
        if git_ok(top, "ls-files", "--error-unmatch", "--", inside):
            tally.unknown += 1
        else:
            tally.untracked += 1
        return
    near, added, created = hunks(git_out(top, "diff", "-U0", "--no-color", "--no-ext-diff", "--ignore-cr-at-eol",
                                         base, "--", inside), spans)
    if created:
        near, added = 0, 0                                   # added or renamed under this name: blame decides
    if old == 0 and added == 0 and not created and hunks(
            git_out(top, "diff", "-U0", "--no-color", "--no-ext-diff", base, "--", inside), spans)[1] == 1:
        tally.crlf += 1                                      # new only by its line endings
        return
    tally.old, tally.new = tally.old + old, tally.new + new
    tally.near += near != 0


def _blamed(where: Scope, inside: str, spans: list[tuple[int, int]]) -> tuple[int | None, int]:
    """(commits in the base, commits after it) among the cited lines' blame; (None, 0) when blame names none."""
    args = []
    for first, last in spans:
        args += ["-L", "%d,%d" % (first, last)]
    found = set()
    for line in git_out(where.top, "blame", "--porcelain", *args, "--", inside).decode("utf-8", "surrogateescape") \
            .split("\n"):
        words = [w for w in re.split(r"[ \t]+", line.rstrip("\r")) if w]
        if len(words) >= 3 and SHA.fullmatch(words[0]) and len(words[0]) in (40, 64):
            found.add(words[0])
    if not found:
        return None, 0
    old = new = 0
    for sha in found:
        if set(sha) == {"0"}:
            new += 1
        elif git_ok(where.top, "merge-base", "--is-ancestor", sha, where.base):
            old += 1
        else:
            new += 1
    return old, new
