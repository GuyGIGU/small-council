"""A build's saved rounds (`<run>/patches/`), written by council patch save (references/run/builder-report.md):
for task <n>, round <r>, the round's diff `T<n>-<r>.patch`, its record `T<n>-<r>.json` (the head, the trees it
runs between, its files and what the checks found) and the task's history `T<n>.md`, rewritten at each save."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import NamedTuple

FOLDER = "patches"
RECORD = re.compile(r"T([0-9]+)-([0-9]+)\.json")


class Round(NamedTuple):
    """One saved round, as its record holds it."""

    task: int
    round: int
    seq: int
    at: str
    base: str
    tree: str
    files: list
    added: int
    removed: int
    head: dict
    outside: list
    signs: list
    slice: str


def folder(run: str | Path) -> Path:
    return Path(run) / FOLDER


def name(task: int, number: int) -> str:
    """A round's file stem, T3-2."""
    return "T%d-%d" % (task, number)


def rounds(run: str | Path, task: int | None = None) -> list[Round]:
    """The saved rounds, oldest first (by their save order); one task's when given. A record that doesn't read
    is left out: a round is saved whole or not at all."""
    found = []
    try:
        names = sorted((Path(run) / FOLDER).iterdir())
    except OSError:
        return []
    for path in names:
        match = RECORD.fullmatch(path.name)
        if not match or (task is not None and int(match.group(1)) != task):
            continue
        try:
            data = json.loads(path.read_bytes().decode("utf-8"))
            found.append(Round(*(data[key] for key in Round._fields)))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return sorted(found, key=lambda one: one.seq)


def write(run: str | Path, one: Round, diff: bytes) -> Path:
    """Save a round: its diff first, then its record, so a record never names a patch that isn't there."""
    where = folder(run)
    where.mkdir(exist_ok=True)
    target = where / (name(one.task, one.round) + ".patch")
    target.write_bytes(diff)
    record = where / (name(one.task, one.round) + ".json")
    record.write_bytes((json.dumps(one._asdict(), indent=1) + "\n").encode("ascii"))
    return target


def write_history(run: str | Path, task: int, lines: list[str]) -> Path:
    path = folder(run) / ("T%d.md" % task)
    path.write_bytes("".join(line + "\n" for line in lines).encode("utf-8", "surrogateescape"))
    return path
