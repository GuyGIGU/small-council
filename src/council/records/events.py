"""events.tsv: the run's append-only event stream (references/run/event-stream.md).

Seven tab-separated cells a row: schema, seq, at, type, subject, value, detail. `append` writes under
the stream's lock, so two writers never share a sequence number.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from council import clock
from council.records import bytewise, cells, locks, owners, paths, state

NAME = "events.tsv"
COLUMNS = ("schema", "seq", "at", "type", "subject", "value", "detail")
HEADER = "\t".join(COLUMNS)


class EventError(paths.RecordError):
    """An event that could not be recorded; the message says why."""


class Table(NamedTuple):
    """The stream as the run's snapshot reads it: every row after the header, split into cells."""
    present: bool
    header_ok: bool | None
    rows: list[list[str]]
    too_large: bool


def path(run: Path) -> Path:
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
    return cells.tsv_rows(paths.run_text(run, NAME, limit=limit))


def strict_rows(run: Path, read: paths.Reader) -> list[dict[str, object]]:
    """Every row, refusing a stream without the v1 header or with any row out of sequence (the repair
    loop trusts a gate's record only from a whole stream). `read` returns the file's text."""
    lines = cells.lines_of(re.sub(r"\n\Z", "", read(path(run)) or ""))   # on newline only: a cell may hold U+2028
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
    """A detail cell's key=value pairs ("exit=1;seconds=57"), the first of a repeated key winning (the helper's
    own keys come before any text a person gave)."""
    found: dict[str, str] = {}
    for part in (cell or "").split(";"):
        if "=" in part:
            key, value = part.split("=", 1)
            found.setdefault(key, value)
    return found


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
    return state.field(state.text(run), "events-schema")


def _unstamped(run: Path, file: str) -> str:
    """Why a run with an event file has no stamp to read: its state is not read (a link, a file outside the run or
    one over the size limit), or it has none. `file` is the event file as the message names it."""
    return (state.unread(run, "its events-schema stamp is not read and no event can be recorded")
            or "event file exists without an events-schema stamp: %s" % file)


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
    row = "1\t{}\t{}\t{}\t{}\t{}\t{}\n".format(seq, clock.now_utc(), cell(kind), cell(subject), cell(value),
                                              cell(detail))
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
            raise EventError(_unstamped(run, file.as_posix()))
        return False
    if schema != "1":
        raise EventError("unsupported events schema: {}".format(schema))
    lock = Path(str(file) + ".lock")
    if not locks.acquire(lock, tries):
        raise EventError(busy(lock))
    try:
        written = _write(file, kind, subject, value, detail, once)
    except OSError:
        written = None
    released = locks.release(lock)
    if written is None or not released:
        raise EventError("could not append a valid event to {}".format(file.as_posix()))
    return written


def busy(lock: Path) -> str:
    """lock_unavailable's words (owners.unavailable), the lock written as the helper writes paths."""
    return owners.unavailable(lock).replace(str(lock), lock.as_posix())


def ready(run: Path) -> tuple[int, str]:
    """event_ready: (0, '') when the stream takes a row; 1 and why for a torn last line; 2 and why otherwise."""
    if not _schema(Path(run)):
        return 0, ""
    try:
        data = path(run).read_bytes()
    except OSError:
        return 2, "events.tsv is missing"
    if data and not data.endswith(b"\n"):
        return 1, "its last line is torn"
    if data[:-1].rsplit(b"\n", 1)[-1].replace(b"\r", b"") == HEADER.encode():
        return 2, "it holds no events"
    return (0, "") if _next_seq(data) else (2, "its last row is not a numbered event")


def writable(run: Path) -> None:
    """events_writable: EventError, naming the next step, while the stream can't take the events of a write."""
    code, why = ready(run)
    if code == 1:
        raise EventError("the run's event stream is damaged (%s), so nothing was written — repair it: council run "
                         "events repair --run %s" % (why, Path(run).name))
    if code:
        raise EventError("the run's event stream is lost (%s), so nothing was written — it can't be rebuilt; close "
                         "the run: council run close --run %s" % (why, Path(run).name))


_AT = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")


def check(run: str) -> tuple[int, list[str]]:
    """event_check, as `council doctor` reads it: its exit code and every line it said, those on stderr with the
    helper's "council: " ahead of them. `run` is the folder as the helper writes it. A run from before the stream
    passes; else the stream must be whole, under the lock: the v1 header, then rows in sequence from 1, each with
    seven cells, a UTC time and no empty cell, the first a run.opened."""
    folder = Path(run)
    file = run + "/" + NAME
    schema = _schema(folder)
    if schema not in ("", "1"):
        return 1, ["council: unsupported events schema: %s" % schema]
    if schema == "" and not path(folder).is_file():
        return 0, ["events: legacy run · no event stream · %s" % run.rsplit("/", 1)[-1]]
    if schema == "":
        return 1, ["council: " + _unstamped(folder, file)]
    lock = Path(file + ".lock")
    if not locks.acquire(lock):
        return 1, ["council: " + busy(lock)]
    try:
        data = path(folder).read_bytes() if path(folder).is_file() else None
    except OSError:
        data = None
    held = locks.release(lock)
    if data is None:
        return 1, ["council: events.tsv is missing from %s" % run.rsplit("/", 1)[-1]]
    if data and not data.endswith(b"\n"):
        return 1, ["events: final line is incomplete"]
    said = _judged(bytewise.records(bytewise.read(data)))
    bad = any(not line.startswith("events: valid") for line in said)
    return (1 if bad or not held else 0), said


def _judged(lines: list[str]) -> list[str]:
    said = []
    for number, line in enumerate(lines, 1):
        line = re.sub(r"\r\Z", "", line)
        if number == 1:
            if line != HEADER:
                said.append("events: bad header")
            continue
        c = line.split("\t")
        if (len(c) != 7 or c[0] != "1" or not re.fullmatch("[0-9]+", c[1]) or int(c[1]) != number - 1
                or not _AT.fullmatch(c[2]) or "" in c[3:] or (number == 2 and c[3] != "run.opened")):
            said.append("events: invalid row %d" % number)
    if len(lines) < 2:
        said.append("events: no events")
    if not said:
        said.append("events: valid · %d event(s)" % (len(lines) - 1))
    return said
