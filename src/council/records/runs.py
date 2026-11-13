"""The runs of a council home as the helper lists them (list_runs), a mode's skill (mode_skill), and the
one-line seat summary a listing shows beside a run (seat_summary).

list_runs reads every `key: value` line of a run's state, below the header too (state.header reads the
header only), so its rule lives here, apart from the header's.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import NamedTuple

from council.records import paths

OPEN = re.compile(rb"^(\xef\xbb\xbf)?status:[ \t\r\f\v]*(in-progress|paused)", re.MULTILINE)
KEY = re.compile(r"^[a-z][a-z0-9-]*:")


class Listed(NamedTuple):
    """One run as list_runs gives it; a field the state file lacks is ''."""

    folder: str
    mode: str
    phase: str
    code_root: str
    updated: str
    status: str
    actual: str
    session: str


def listing(home: str, limit: int = 30, which: str = "open") -> list[Listed]:
    """Runs, newest first: which='open' takes every run whose state has an in-progress or paused status
    line anywhere, however old; 'all' the newest by name. At most limit. Folders are home + /runs/<name>."""
    listed = []
    for state in _states(home + "/runs", which)[:limit]:
        fields = listed_fields((_raw(state) or b"").decode("utf-8", "surrogateescape"))
        if fields is not None:
            get = fields.get
            listed.append(Listed(state[:-len(paths.STATE) - 1], get("mode", ""), get("phase", ""),
                                 get("code-root", ""), get("updated", ""), get("status", "").split(" ")[0],
                                 get("actual", ""), get("session", "")))
    return listed


def _states(runs: str, which: str) -> list[str]:
    """The state files to read, in list_runs' order: sort -r over the state paths (open), or over the
    folder names (all). Names starting with a dot are left out, as the shell's * and ls -1 leave them."""
    try:
        names = [name for name in os.listdir(runs) if not name.startswith(".")]
    except OSError:
        return []
    if which == "open":
        states = sorted((runs + "/" + name + "/" + paths.STATE for name in names), reverse=True)
        return [state for state in states if OPEN.search(_raw(state) or b"")]
    states = [runs + "/" + name + "/" + paths.STATE for name in sorted(names, reverse=True)]
    return [state for state in states if os.path.isfile(state)]


def _raw(file: str | Path) -> bytes | None:
    try:
        with open(str(file), "rb") as handle:
            return handle.read()
    except OSError:
        return None


def _records(content: str) -> list[str]:
    """Lines as awk reads them: split on newline, no empty record after a final newline."""
    records = content.split("\n")
    if content.endswith("\n") or not content:
        records.pop()
    return records


def listed_fields(content: str) -> dict[str, str] | None:
    """Every `key: value` line of the file, the first of a key winning: carriage returns dropped, a
    trailing '  # comment' cut, tabs made spaces. None for an empty file."""
    if not content:
        return None
    fields: dict[str, str] = {}
    for number, line in enumerate(_records(content)):
        if number == 0 and line.startswith(paths.BOM):
            line = line[1:]
        line = line.replace("\r", "")
        key = KEY.match(line)
        if not key or line[:key.end() - 1] in fields:
            continue
        value = re.sub(r"[ \t][ \t]+#.*$", "", line[key.end():].lstrip(" \t"))
        fields[line[:key.end() - 1]] = value.replace("\t", " ")
    return fields


def skill(mode: str) -> str:
    """The skill that owns a run, from its mode: field (0.2 runs sometimes wrote the short name)."""
    if mode.startswith("council-") or mode in ("test-architect", "spec-writer", "context-core"):
        return mode
    if mode in ("review", "plan", "implement", "research", "postgame", "init"):
        return "council-" + mode
    return "context-core"


def seat_summary(run: str | Path, working: str = "still working") -> str:
    """'still working: a, b · done: c · failed: d' from the run's seats.tsv (every row after the header,
    split as awk splits it); '' when there is no file or nothing to say."""
    content = (_raw(Path(run) / "seats.tsv") or b"").decode("utf-8", "surrogateescape")
    groups: dict[str, list[str]] = {"working": [], "done": [], "failed": []}
    for line in _records(content)[1:]:
        cell = line.split("\t") + [""] * 6
        if cell[1] in ("running", "queued"):
            groups["working"].append(cell[0] + (" (war-room round 2)" if "round 2" in cell[5] else ""))
        elif cell[1] == "done":
            groups["done"].append(cell[0])
        elif cell[1] in ("failed", "blocked"):
            groups["failed"].append(cell[0])
    labels = (("working", working), ("done", "done"), ("failed", "failed"))
    return " · ".join(label + ": " + ", ".join(groups[key]) for key, label in labels if groups[key])
