"""tuning.md: the log of what `council tune` changed in council.config.md, and the one way it writes a change.

An entry is `## T-<n> · <date> · applied | reverted T-<m> · <knob>: <before> → <after>`, then the evidence, the
user's words and `- exact:`, the JSON of the exact line it replaced (what a revert puts back). The knob is
`estimate per worker`, or `estimates <role>` for one role of the `- estimates:` line.
"""
from __future__ import annotations

import contextlib
import json
import re
from pathlib import Path
from typing import Any

from council.records import paths
from council.records.cells import CONTROL

NAME = "tuning.md"
ENTRY = re.compile(r"^## T-(\d+) · (\S+) · (applied|reverted T-\d+) · "
                   r"(estimate per worker|estimates \S+): (\S+) → (\S+)[ \t]*\r?$", re.MULTILINE)
EXACT = re.compile(r"^- exact: (\{.*\})[ \t]*\r?$", re.MULTILINE)
START = ("# Tuning log\n\nEach change `council tune` made to council.config.md, with its evidence, the user's own\n"
         "words, and the exact line it replaced. Undo the last one with\n"
         "`council tune revert budget --user-said \"…\"`.\n")


class TuningError(paths.RecordError):
    """A tuning step that must not happen."""


def read_log(home: str | Path) -> tuple[Path, str | None]:
    """The log's path and text (None when there is no log); refuses a link."""
    path = Path(home) / NAME
    if path.is_symlink():
        raise TuningError("tuning.md is a link — refusing to read or write through it")
    return path, (path.read_bytes().decode("utf-8") if path.is_file() else None)


def log_entries(home: str | Path) -> list[dict[str, Any]]:
    """Each logged change: its number, knob, action, shown values and exact record (None when absent or bad)."""
    _, text = read_log(home)
    entries = []
    heads = list(ENTRY.finditer(text or ""))
    for i, head in enumerate(heads):
        body = text[head.end():heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        exact = EXACT.search(body)
        try:
            record = json.loads(exact.group(1)) if exact else None
        except ValueError:
            record = None
        entries.append({"n": int(head.group(1)), "date": head.group(2), "action": head.group(3), "knob": head.group(4),
                        "before": head.group(5), "after": head.group(6), "exact": record})
    return entries


def said_words(path: str | Path) -> str:
    """The user's words from the redacted file the helper made: one line, quotes made single, at most 400 characters."""
    words = CONTROL.sub(" ", Path(path).read_text(encoding="utf-8", errors="replace")).strip()
    words = re.sub(r"\s+", " ", words).replace('"', "'").replace("`", "'")
    if not words:
        raise TuningError("the user's words are empty — quote their answer")
    return words[:400]


def write(path: Path, text: str) -> None:
    """Replace path with text, keeping the file's permissions (a new file gets the usual ones)."""
    paths.atomic_write(path, text.encode("utf-8"), prefix=".council-tune-", keep_mode=True)


def write_pair(home: str | Path, entry_lines: list[str], config_path: Path, config_text: str) -> int:
    """Append the entry to tuning.md, then replace the config; if the config cannot be written, the log
    is put back as it was, so it never records a change that did not happen. Returns the entry's number."""
    log_path, old = read_log(home)
    base = old if old is not None else START
    newline = "\r\n" if base.count("\r\n") * 2 > base.count("\n") else "\n"
    number = max([e["n"] for e in log_entries(home)] + [0]) + 1
    entry = ["", entry_lines[0].replace("T-?", "T-{}".format(number), 1)] + entry_lines[1:]
    text = base.rstrip("\r\n") + newline + newline.join(entry) + newline
    write(log_path, text)
    try:
        write(config_path, config_text)
    except BaseException:
        if old is None:
            with contextlib.suppress(OSError):
                log_path.unlink()
        else:
            write(log_path, old)
        raise
    return number
