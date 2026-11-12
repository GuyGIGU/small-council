"""events.tsv: the run's append-only event stream (references/event-stream.md).

Seven tab-separated cells a row: schema, seq, at, type, subject, value, detail. `append` is the helper's
event_append, under the same lock, so a Python writer and a bash writer never share a sequence number.
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Callable, NamedTuple, Optional

from council.records import cells, locks, paths, state

NAME = "events.tsv"
COLUMNS = ("schema", "seq", "at", "type", "subject", "value", "detail")
HEADER = "\t".join(COLUMNS)
Reader = Callable[[Path], Optional[str]]


class EventError(paths.RecordError):
    """An event that could not be recorded; the message says why."""


class Table(NamedTuple):
    """The stream as the cockpit reads it: every row after the header, split into cells."""
    present: bool
    header_ok: bool | None
    rows: list[list[str]]
    too_large: bool


def path(run: Path) -> Path:
    """The event stream of a run folder."""
    return Path(run) / NAME


def table(run: Path, limit: int = paths.MAX_FILE) -> Table:
    """The stream's non-blank lines after the header, split on tabs (malformed rows included: the
    caller counts them). A stream over limit is not read."""
    run = Path(run)
    if paths.too_large(path(run), limit):
        return Table(True, None, [], True)
    lines = [line for line in cells.lines_of(paths.text_of(path(run), run, limit)) if line.strip()]
    return Table(bool(lines), bool(lines) and lines[0] == HEADER, [line.split("\t") for line in lines[1:]], False)


def records(run: Path, limit: int = paths.MAX_FILE) -> list[dict[str, str]]:
    """The stream's rows as dicts keyed by its own header line ("#" and blank lines skipped)."""
    run = Path(run)
    return cells.tsv_rows(paths.text_of(path(run), run, limit))


def strict_rows(run: Path, read: Reader) -> list[dict[str, object]]:
    """Every row, refusing a stream without the v1 header or with any row out of sequence (the repair
    loop trusts a gate's record only from a whole stream). `read` returns the file's text."""
    lines = (read(path(run)) or "").splitlines()
    if not lines or lines[0] != HEADER:
        raise EventError("events.tsv has no v1 header")
    rows = []
    for expected, line in enumerate(lines[1:], 1):
        parts = line.split("\t")
        if len(parts) != 7 or parts[0] != "1" or parts[1] != str(expected):
            raise EventError("events.tsv is malformed; run council run events check")
        rows.append({"seq": expected, "type": parts[3], "subject": parts[4], "value": parts[5], "detail": parts[6]})
    return rows


def details(cell: str) -> dict[str, str]:
    """A detail cell's key=value pairs ("exit=1;seconds=57")."""
    return dict(part.split("=", 1) for part in (cell or "").split(";") if "=" in part)


# --- writing ------------------------------------------------------------------------------------------------
def cell(value: str) -> str:
    """event_cell: tabs and line breaks become spaces, and every other control byte goes."""
    data = value.encode("utf-8", "surrogateescape")
    data = data.replace(b"\t", b" ").replace(b"\r", b" ").replace(b"\n", b" ")
    return bytes(byte for byte in data if byte >= 0x20 and byte != 0x7F).decode("utf-8", "surrogateescape")


def _next_seq(data: bytes) -> int | None:
    """The next sequence number after the stream's last line, or None when the last line is torn,
    missing or not a numbered row."""
    if data and not data.endswith(b"\n"):
        return None                      # a torn final line must not be joined to the next event
    last = data[:-1].split(b"\n")[-1].replace(b"\r", b"").decode("utf-8", "replace") if data else ""
    if last == HEADER:
        return 1
    parts = last.split("\t")
    if len(parts) == 7 and parts[0] == "1" and re.fullmatch(r"[0-9]+", parts[1]):
        return int(parts[1]) + 1
    return None


def _schema(run: Path) -> str:
    try:
        content = state.path(run).read_bytes().decode("utf-8", "replace").lstrip(paths.BOM)
    except OSError:
        return ""
    return state.header(content, exact_keys=True).get("events-schema", "")


def _recorded(data: bytes, kind: str) -> bool:
    return any(len(parts) > 3 and parts[3] == kind
               for parts in (line.split("\t") for line in data.decode("utf-8", "replace").split("\n")[1:]))


def _write(file: Path, kind: str, subject: str, value: str, detail: str, once: bool) -> bool | None:
    """Under the lock: True when written, False when `once` found the type on record, None on a failure."""
    data = file.read_bytes() if file.is_file() else None
    if once and data is not None and _recorded(data, kind):
        return False
    if data is None:
        if kind != "run.opened":
            return None
        data = (HEADER + "\n").encode("ascii")
        file.write_bytes(data)
    seq = _next_seq(data)
    if seq is None:
        return None
    row = "1\t{}\t{}\t{}\t{}\t{}\t{}\n".format(seq, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                              cell(kind), cell(subject), cell(value), cell(detail))
    with open(str(file), "ab") as stream:
        stream.write(row.encode("utf-8", "surrogateescape"))
    return True


def append(run: Path, kind: str, subject: str, value: str, detail: str, once: bool = False,
           tries: int = locks.TRIES) -> bool:
    """event_append: one row under the run's event lock (waiting up to `tries` times 0.1 s). False when
    nothing was added (a run from before the stream, or `once` found the type on record); EventError
    when it failed."""
    run = Path(run)
    file = path(run)
    schema = _schema(run)
    if schema == "":
        if file.is_file():
            raise EventError("event file exists without an events-schema stamp: {}".format(file))
        return False
    if schema != "1":
        raise EventError("unsupported events schema: {}".format(schema))
    lock = Path(str(file) + ".lock")
    if not locks.acquire(lock, tries):
        raise EventError("event lock unavailable: {}".format(lock))
    try:
        written = _write(file, kind, subject, value, detail, once)
    except OSError:
        written = None
    released = locks.release(lock)
    if written is None or not released:
        raise EventError("could not append a valid event to {}".format(file))
    return written
