"""The runs of a council home as the helper lists them (list_runs), a mode's skill (mode_skill), and the
one-line seat summary a listing shows beside a run (seat_summary).

A run's fields are its state's header (state.header): a `key: value` line below the first `## ` heading is
not a field, so a status line there never opens a run.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import NamedTuple

from council.records import bytewise, paths, state

OPEN = re.compile(r"[ \t\r\f\v]*(in-progress|paused)")       # an open run's status value


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
    """Runs, newest first: which='open' takes every run whose header's status is in-progress or paused,
    however old; 'all' the newest by name. At most limit. Folders are home + /runs/<name>."""
    listed: list[Listed] = []
    states = _states(home + "/runs", which)
    for file in states if which == "open" else states[:limit]:
        fields = listed_fields((paths.contents(file) or b"").decode("utf-8", "surrogateescape"))
        if fields is None or (which == "open" and not OPEN.match(fields.get("status", ""))):
            continue
        get = fields.get
        listed.append(Listed(file[:-len(paths.STATE) - 1], get("mode", ""), get("phase", ""),
                             get("code-root", ""), get("updated", ""), get("status", "").split(" ")[0],
                             get("actual", ""), get("session", "")))
        if len(listed) == limit:
            break
    return listed


def _states(runs: str, which: str) -> list[str]:
    """The state files to read, in list_runs' order: sort -r over the state paths (open), or over the
    folder names (all). Names starting with a dot are left out, as the shell's * and ls -1 leave them."""
    try:
        names = [name for name in os.listdir(runs) if not name.startswith(".")]
    except OSError:
        return []
    if which == "open":
        return sorted((runs + "/" + name + "/" + paths.STATE for name in names), reverse=True)
    states = [runs + "/" + name + "/" + paths.STATE for name in sorted(names, reverse=True)]
    return [file for file in states if os.path.isfile(file)]


def listed_fields(content: str) -> dict[str, str] | None:
    """The state's header fields as state.header reads them (exact keys); None for an empty file."""
    return state.header(content) if content else None


def here(code_root: str, tree: str) -> bool:
    """A run is on this tree when its code-root is this tree, blank or '-'. A helper-written code-root is an
    absolute path with forward slashes; blank is a run from before --code-root; '-' is never written."""
    return code_root in (tree, "", "-")


def skill(mode: str) -> str:
    """The skill that owns a run, from its mode: field (0.2 runs sometimes wrote the short name)."""
    if mode.startswith("council-") or mode in ("test-architect", "spec-writer", "context-core"):
        return mode
    if mode in ("review", "plan", "implement", "research", "postgame", "init"):
        return "council-" + mode
    return "context-core"


def seat_summary(run: str | Path, working: str = "still working") -> str:
    """'still working: a, b · done: c · failed: d' from seats.tsv, as Git Bash's awk reads it; '' for none."""
    groups: dict[str, list[str]] = {"working": [], "done": [], "failed": []}
    for line in bytewise.file_lines(Path(run) / "seats.tsv")[1:]:
        cell = line.split("\t") + [""] * 6
        if cell[1] in ("running", "queued"):
            groups["working"].append(cell[0] + (" (war-room round 2)" if "round 2" in cell[5] else ""))
        elif cell[1] == "done":
            groups["done"].append(cell[0])
        elif cell[1] in ("failed", "blocked"):
            groups["failed"].append(cell[0])
    labels = (("working", working), ("done", "done"), ("failed", "failed"))
    return " · ".join(label + ": " + ", ".join(groups[key]) for key, label in labels if groups[key])
