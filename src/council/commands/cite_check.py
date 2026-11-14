"""Whether each place a citation names is there: on disk, in the change's base, or among the run's own files.
`council collect` and `council check` read every item's citation with it."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import NamedTuple

from council.records import citations
from council.records.home import native

AREA_MODES = ("council-plan", "council-research", "council-postgame")


class Scope(NamedTuple):
    """Where citations are read from: the code root, the change's base ('' when none), the run folder (its own
    files are found there), and how the mode reads a field. A plan, research and a post-game cite "<path or
    area>" (area): a name on disk nowhere is an area, or a file still to write. A review item must name a
    place (needs_place: "no evidence, no item")."""

    top: str
    base: str
    run: str
    area: bool
    needs_place: bool


def scope(top: str, base: str, run: str, mode: str) -> Scope:
    """The scope a mode's citations are read in."""
    return Scope(top, base, run, mode in AREA_MODES, mode == "council-review")


def git_ok(top: str, *args: str) -> bool:
    """Whether git -C top <args> succeeds; its output is not read."""
    try:
        return subprocess.run(["git", "-C", native(top)] + list(args), stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL).returncode == 0
    except OSError:
        return False


def git_out(top: str, *args: str) -> bytes:
    """git -C top <args>'s stdout, whatever its exit code; b'' when git can't start."""
    try:
        return subprocess.run(["git", "-C", native(top)] + list(args), stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL).stdout
    except OSError:
        return b""


def absolute(path: str) -> bool:
    return path.startswith("/") or re.match(r"[A-Za-z]:", path) is not None


def rel(top: str, path: str) -> str:
    """A cited path as it sits inside the tree top, or the path itself when it is outside it. The forms Git Bash
    and Windows print for one file ("/c/Users/…", "c:/users/…", "C:/Users/…") all resolve."""
    if not absolute(path):
        return path
    if path.startswith(top + "/"):
        return path[len(top) + 1:]
    if re.match(r"[A-Za-z]:/", top):
        found = path
        drive = re.match(r"/([A-Za-z])/", found)
        if drive:
            found = drive.group(1) + ":" + found[2:]
        if found.startswith(top + "/"):
            return found[len(top) + 1:]
        if _lower(found).startswith(_lower(top) + "/"):
            return found[len(top) + 1:]
    return path


def _lower(text: str) -> str:
    return "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in text)


def run_cited(where: Scope, path: str, top: str) -> bool:
    """A relative path the code root has nothing by, that is a file of the run being checked — named the way the
    helper names them: gates/tests.txt, context/notes.md, verify-1.md."""
    if not where.run or absolute(path) or path == ".." or path.startswith("../") or "/../" in path \
            or path.endswith("/.."):
        return False
    return not os.path.exists(native(top + "/" + path)) and os.path.exists(native(where.run + "/" + path))


def line_count(path: str) -> int:
    try:
        return citations.count_lines(Path(native(path)).read_bytes())
    except OSError:
        return 0


def place(where: Scope, kind: str, path: str, listed: str) -> str:
    """One place: ok | deleted | no-line | missing-file | area | bad-line (…) | unreadable (…). A path that isn't
    on disk but is in the base (HEAD without one) was deleted by the change: its lines are checked against the
    base's copy. A file of the run itself is checked where it is."""
    if kind == "U":
        return "unreadable (%s — write it as path:line)" % path
    top, base = where.top, where.base or "HEAD"
    file = path if absolute(path) else top + "/" + path
    if run_cited(where, path, top):
        file = where.run + "/" + path
    if kind == "P" and os.path.exists(native(file)):
        return "no-line"
    if kind == "L" and os.path.isfile(native(file)):
        return citations.line_verdict(listed, line_count(file))
    if kind == "L" and os.path.isdir(native(file)):
        return "bad-line (a folder has no lines)"
    inside = rel(top, file)
    stem = inside[:-1] if inside.endswith("/") else inside
    if inside != file and git_ok(top, "cat-file", "-e", "%s:%s" % (base, stem)):
        if kind != "L":
            return "deleted"
        count = citations.count_lines(git_out(top, "show", "%s:%s" % (base, inside)))
        verdict = citations.line_verdict(listed, count)
        return "deleted" if verdict == "ok" else citations.line_verdict(listed, count, "deleted file had")
    if kind == "P" and where.area:
        return "area"
    return "missing-file"


class _Tally:
    def __init__(self) -> None:
        self.places = self.ok = self.deleted = self.bare = self.area = 0
        self.why = ""
        self.first = ("", "", "")          # the first failure: verdict, path, ":lines"
        self.missing = ("", "")            # the first bare path that is nowhere: verdict, path


def status(where: Scope, rows: list[tuple[str, ...]]) -> str:
    """The verdict on a citation field: ok | deleted (…) | no-line (…) | missing-file | bad-line (…) |
    unreadable (…) | no-citation (…) | n/a [(why)]. The first place that fails gives it, named when the field has
    several. A bare path that isn't there, beside a place that resolved, is a note, not the item's citation."""
    tally = _Tally()
    for row in rows:
        kind, path, listed = (tuple(row) + ("", "", ""))[:3]
        if kind == "N":
            tally.why = path
            continue
        if kind not in ("L", "P", "U"):
            continue
        tally.places += 1
        _count(tally, place(where, kind, path, listed), kind, path, listed)
    return _verdict(where, tally)


def _count(tally: _Tally, verdict: str, kind: str, path: str, listed: str) -> None:
    if verdict == "ok":
        tally.ok += 1
    elif verdict == "deleted":
        tally.deleted += 1
    elif verdict == "no-line":
        tally.bare += 1
    elif verdict == "area":
        tally.area += 1
    elif verdict == "missing-file" and kind == "P":
        if not tally.missing[0]:
            tally.missing = (verdict, path)
    elif not tally.first[0]:
        tally.first = (verdict, path, ":" + listed if listed else "")


def _verdict(where: Scope, tally: _Tally) -> str:
    verdict, path, listed = tally.first
    if not verdict and tally.missing[0] and tally.ok + tally.deleted + tally.bare == 0:
        verdict, path, listed = tally.missing[0], tally.missing[1], ""
    if verdict:
        if tally.places == 1:
            return verdict
        if verdict == "missing-file":
            return "missing-file (%s)" % path
        if verdict.startswith("bad-line ("):
            return "bad-line (%s%s — %s" % (path, listed, verdict[len("bad-line ("):])
        return verdict
    if tally.ok:
        return "ok"
    if tally.deleted:
        return "deleted (removed by this change — checked against the base)"
    if tally.bare:
        return "no-line (the path exists)"
    if tally.area:
        return "n/a (nothing on disk by that name — an area, or a file still to write)"
    if where.needs_place and tally.why in ("", "-", "no path"):
        return "no-citation (a review item needs a path:line)"
    if tally.why in ("", "-"):
        return "n/a"
    return "n/a (%s)" % tally.why
