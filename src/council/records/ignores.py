"""The council home's .gitignore: whether git ignores a path in the home, whether the user shares their requests
(`!asks/`), and the lines that keep run scratch and the user's own words out of git. bin/council keeps its copy
(home_ignores, asks_shared, ensure_ignored) for the bash that stays."""
from __future__ import annotations

import os
import re
from pathlib import Path

from council import git
from council.records import paths

NAME = ".gitignore"
KEPT_OUT = ("runs/", "asks/", "active-run")
_SHARED = re.compile(rb"[ \t\n\v\f\r]*!/?asks/?[ \t\n\v\f\r]*")


def path(home: str | Path) -> Path:
    """The council home's .gitignore."""
    return Path(home) / NAME


def ignores(home: str | Path, inside: str) -> bool:
    """Does git ignore this path under the home? Patterns only, so a file already tracked doesn't change the
    answer. Outside git (check-ignore can't answer), the home's .gitignore has the line or not."""
    home = str(home)
    code = git.run(os.path.dirname(home), "check-ignore", "--no-index", "-q", "--",
                   os.path.basename(home) + "/" + inside)[0]
    if code <= 1:
        return code == 0
    first = re.escape(inside.split("/", 1)[0].encode("utf-8", "surrogateescape"))
    line = re.compile(rb"[ \t\n\v\f\r]*/?" + first + rb"/?[ \t\n\v\f\r]*")
    return any(line.fullmatch(found) for found in (paths.contents(path(home)) or b"").split(b"\n"))


def asks_shared(home: str | Path) -> bool:
    """The user chose to share their requests with the team: a "!asks/" line in the home's .gitignore."""
    return any(_SHARED.fullmatch(line) for line in (paths.contents(path(home)) or b"").split(b"\n"))


def keep_out(home: str | Path) -> str:
    """Make git ignore runs/, asks/ and active-run in the home; the line to say when tracked asks/ became ignored."""
    file, added = path(home), False
    data = paths.contents(file)
    cr = b"\r" if data and b"\r" in data else b""
    for want in KEPT_OUT:
        if ignores(home, want + "x" if want.endswith("/") else want):
            continue
        if want == "asks/" and asks_shared(home):
            continue
        data = paths.contents(file)
        lead = cr + b"\n" if data and not data.endswith(b"\n") else b""
        try:
            with open(str(file), "ab") as stream:
                stream.write(lead + want.encode() + cr + b"\n")
        except OSError:
            continue
        added = added or want == "asks/"
    if not (added and _tracked_asks(home)):
        return ""
    return ("%s/.gitignore now ignores asks/, so new requests stay on this machine; the ones already in git stay "
            "tracked. To share requests with the team, write '!asks/' in place of that line." % os.path.basename(home))


def _tracked_asks(home: str | Path) -> bool:
    home = str(home)
    return bool(git.run(os.path.dirname(home), "ls-files", "--", os.path.basename(home) + "/asks")[1].strip())
