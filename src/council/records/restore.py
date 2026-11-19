"""A run's restore point, `<run>/restore.md` (D57): the commit `council restore point` made of the code root's files
before the run changed anything, the HEAD and branch it stood on, and when. Written once, by council restore point;
read by council restore show."""
from __future__ import annotations

import os
from pathlib import Path
from typing import NamedTuple

NAME = "restore.md"
REF = "refs/council/restore/"      # + the run folder's name: the ref that keeps the point's commit
FIELDS = ("commit", "head", "branch", "taken")


class Point(NamedTuple):
    commit: str          # the commit of the files as they were (commit-tree; HEAD its parent when there was one)
    head: str            # HEAD's commit then, '' on a branch with no commit yet
    branch: str          # the branch then, or (detached)
    taken: str           # the local time it was taken


def read(run: Path) -> Point | None:
    """The run's restore point; None when there is none, or its file names no commit."""
    try:
        text = (Path(run) / NAME).read_bytes().decode("utf-8", "replace")
    except OSError:
        return None
    found = {}
    for line in text.replace("\r\n", "\n").split("\n"):
        key, colon, value = line.partition(":")
        if colon and key.strip() in FIELDS and key.strip() not in found:
            found[key.strip()] = value.strip()
    values = [found.get(key, "") if found.get(key, "") != "none" else "" for key in FIELDS]
    return Point(*values) if values[0] else None


def write(run: Path, point: Point) -> None:
    """restore.md, made new (O_EXCL: a point is never overwritten); OSError when it can't be, FileExistsError when
    the run has one."""
    lines = ["# Restore point — %s" % Path(run).name] + ["%s: %s" % (key, value or "none")
                                                         for key, value in zip(FIELDS, point)]
    handle = os.open(str(Path(run) / NAME), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(handle, "wb") as out:
        out.write(("\n".join(lines) + "\n").encode("utf-8", "surrogateescape"))
