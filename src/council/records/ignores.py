"""The council home's .gitignore: whether git ignores a path in the home, whether the user shares their requests
(`!asks/`), and the lines that keep run scratch and the user's own words out of git. bin/council keeps its copy
(home_ignores, asks_shared, ensure_ignored) for `council run open` until S8b."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

NAME = ".gitignore"
KEPT_OUT = ("runs/", "asks/", "active-run")
_SHARED = re.compile(rb"[ \t\n\v\f\r]*!/?asks/?[ \t\n\v\f\r]*")


def path(home: str | Path) -> Path:
    """The council home's .gitignore."""
    return Path(home) / NAME


def _bytes(file: Path) -> bytes | None:
    try:
        return file.read_bytes()
    except OSError:
        return None


def ignores(home: str | Path, inside: str) -> bool:
    """Does git ignore this path under the home? Patterns only, so a file already tracked doesn't change the
    answer. Outside git (check-ignore can't answer), the home's .gitignore has the line or not."""
    home = str(home)
    try:
        code = subprocess.run(["git", "-C", os.path.dirname(home), "check-ignore", "--no-index", "-q", "--",
                               os.path.basename(home) + "/" + inside], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode
    except OSError:
        code = 128
    if code <= 1:
        return code == 0
    first = re.escape(inside.split("/", 1)[0].encode("utf-8", "surrogateescape"))
    line = re.compile(rb"[ \t\n\v\f\r]*/?" + first + rb"/?[ \t\n\v\f\r]*")
    return any(line.fullmatch(found) for found in (_bytes(path(home)) or b"").split(b"\n"))


def asks_shared(home: str | Path) -> bool:
    """The user chose to share their requests with the team: a "!asks/" line in the home's .gitignore."""
    return any(_SHARED.fullmatch(line) for line in (_bytes(path(home)) or b"").split(b"\n"))


def keep_out(home: str | Path) -> bool:
    """Add runs/, asks/ and active-run to the home's .gitignore unless git already ignores them (asks/ also not when
    the user shares requests), in the file's own line endings, each on a line of its own. True when asks/ was added
    while requests are already in git: they stay tracked, and the caller says so."""
    file, added = path(home), False
    data = _bytes(file)
    cr = b"\r" if data and b"\r" in data else b""
    for want in KEPT_OUT:
        if ignores(home, want + "x" if want.endswith("/") else want):
            continue
        if want == "asks/" and asks_shared(home):
            continue
        data = _bytes(file)
        lead = cr + b"\n" if data and not data.endswith(b"\n") else b""
        try:
            with open(str(file), "ab") as stream:
                stream.write(lead + want.encode() + cr + b"\n")
        except OSError:
            continue
        added = added or want == "asks/"
    return added and _tracked_asks(home)


def _tracked_asks(home: str | Path) -> bool:
    home = str(home)
    try:
        listed = subprocess.run(["git", "-C", os.path.dirname(home), "ls-files", "--",
                                 os.path.basename(home) + "/asks"], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL).stdout
    except OSError:
        return False
    return bool(listed.strip())
