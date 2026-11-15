"""The one writer of a run's session-state.md (bin/council's cmd_state): `change` sets header fields and files
the user's decisions under the state lock, keeps next: and updated:, and records the run.* event a change of
phase, status or wait makes. clear_waiting (wait_over) is a thin caller."""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from council import clock
from council.records import bytewise, cells, events, locks, paths, redact, stages
from council.records.state import field, path, text

COUNCIL_NEXT_AT_OPEN = stages.COUNCIL_NEXT_AT_OPEN    # frozen name (architecture section 6)
AFTER_CLOSE = ("deliverable", "ask", "ask-saved", "decision")     # a ruling given after the close is still the user's
DECISIONS = "## Decisions so far"


class StateError(paths.RecordError):
    """A refused or failed state write: its lines joined so each prints with its own 'council: '."""

    def __init__(self, *lines: str) -> None:
        super().__init__("\ncouncil: ".join(lines))


class Changed(NamedTuple):
    """The header after a change, the wait before it, and what to say about an event a close let go."""
    phase: str
    status: str
    waited: str
    waiting: str
    warnings: list


def closed(run: Path) -> bool:
    """run_closed: complete or abandoned, its close recorded. A status set by hand is not a close."""
    content = text(run)
    return field(content, "status") in ("complete", "abandoned") and field(content, "closed") != ""


def closed_refusal(run: Path, why: str) -> str:
    """refuse_closed's words: 'run <name> is closed (<status> at <closed>) — <why>'."""
    content = text(run)
    return "run %s is closed (%s at %s) — %s" % (Path(run).name, field(content, "status"), field(content, "closed"),
                                                 why)


def change(run: Path, words: list, closing: bool = False, events_lost: bool = False, phase_note: str = "") -> Changed:
    """council state's write; closing lets a closed run change and its status event go; events_lost records none."""
    run = Path(run)
    lock = Path(str(path(run)) + ".lock")
    if not locks.acquire(lock):
        raise StateError(events.busy(lock), "state lock unavailable: " + lock.as_posix())
    try:
        changed = _locked(run, list(words), closing, events_lost, phase_note)
    except BaseException:
        locks.release(lock)
        raise
    if not locks.release(lock):
        raise StateError("state changed, but its lock could not be released: " + lock.as_posix())
    return changed


def _locked(run: Path, words: list, closing: bool, events_lost: bool, phase_note: str) -> Changed:
    keys = [word.split("=", 1)[0] for word in words]
    if not events_lost and set(keys) & {"phase", "status", "waiting"}:
        try:
            events.writable(run)
        except events.EventError as failure:
            raise StateError(str(failure)) from None
    if not closing and closed(run) and not set(keys) <= set(AFTER_CLOSE):
        raise StateError(closed_refusal(run, "it takes only deliverable=, decision= (and ask save) now; open a new "
                                             "run for more work"))
    before = text(run)
    if "waiting" not in keys and set(keys) & {"phase", "status", "decision"} and field(before, "waiting"):
        words.append("waiting=")                          # a stage or status change ends a wait, unless it names one
    try:
        lines = raw_lines(path(run))
        _rewrite(lines, words, field(before, "phase"))
        data = "".join(line + "\n" for line in lines).encode("utf-8", "surrogateescape")
        paths.atomic_write(path(run), data, ".state.", keep_mode=True)
    except OSError:
        raise StateError("cannot update " + path(run).as_posix()) from None
    after = text(run)
    old, new = (field(before, "phase"), field(before, "status")), (field(after, "phase"), field(after, "status"))
    said = []
    if not events_lost and old[0] != new[0]:
        _event(run, "phase", new[0], "from=" + old[0] + phase_note)
    if not events_lost and old[1] != new[1]:
        said = _event(run, "status", new[1], "from=" + old[1], closing)
    waited, waiting = field(before, "waiting"), field(after, "waiting")
    if bool(waited) != bool(waiting):
        try:
            _event(run, "waiting", "on" if waiting else "off", "from=on" if waited else "from=off")
        except StateError as failure:                     # what a close let go was said before this
            raise StateError(*said, str(failure)) from None
    return Changed(new[0], new[1], waited, waiting, said)


def _rewrite(lines: list, words: list, old_phase: str) -> None:
    """Each word into the lines as cmd_state's awk passes write it, then the next: rules and updated:."""
    for word in words:
        key, _, value = word.partition("=")
        if key == "decision":
            _decide(lines, value)
        elif key != "skip":                               # a skip's reason goes on the phase event, not the header
            flat = value.replace("\r", " ").replace("\n", " ")
            _put(lines, key + ":", key + ": " + flat, header_only=False, add=True)
    phase, named = cells.field("\n".join(lines), "phase"), "next" in [word.split("=", 1)[0] for word in words]
    if phase != old_phase and not named and stages.next_text(phase):
        _put(lines, "next:", "next: " + stages.next_text(phase), header_only=True, add=False)
    if phase not in ("", "convene") and field("\n".join(lines), "next") == COUNCIL_NEXT_AT_OPEN:
        _put(lines, "next:", "next:", header_only=True, add=False)
    _put(lines, "updated:", "updated: " + clock.now_min(), header_only=False, add=False)


def _decide(lines: list, words: str) -> None:
    """The user's words, redacted, under ## Decisions so far as a JSON string; every line loses its carriage return."""
    entry = '- %s: "%s"' % (clock.now_min(), redact.said(words).replace("\\", "\\\\").replace('"', '\\"'))
    out, inside, done = [], False, False
    for line in (line[:-1] if line.endswith("\r") else line for line in lines):
        if inside and line.startswith("## "):
            out.append(entry)
            inside, done = False, True
        inside = inside or line == DECISIONS
        out.append(line)
    lines[:] = out + ([entry] if inside else [] if done else [DECISIONS, entry])


def _event(run: Path, what: str, value: str, detail: str, closing: bool = False) -> list:
    """run.<what>_changed; [] when recorded. A close's lost status event is said, and the close goes on."""
    try:
        events.append(run, "run.%s_changed" % what, "run", value, detail)
        return []
    except events.EventError as failure:
        if not closing:
            raise StateError(str(failure), "state changed, but the %s event could not be recorded" % what) from None
        return [str(failure), "the status event could not be recorded; the close goes on — council run events check "
                "--run " + run.name]


def clear_waiting(run: Path) -> bool:
    """wait_over: the run moves on, so its wait is cleared silently; False when there was none or it failed."""
    if not field(text(run), "waiting") or closed(run):
        return False
    try:
        change(run, ["waiting="])
    except StateError:
        return False
    return True


def raw_lines(file: Path) -> list:
    """The state's lines as awk printed them: the BOM off line 1, a last line without a newline still a line. Git
    Bash's awk reads in text mode, so on Windows a line's carriage return is dropped; elsewhere it is kept."""
    content = file.read_bytes().decode("utf-8", "surrogateescape")
    return bytewise.records(content[len(paths.BOM):] if content.startswith(paths.BOM) else content)


def _put(lines: list, key: str, line: str, header_only: bool, add: bool) -> None:
    """The first line starting with key becomes line. With add, one goes above the first heading (or at the end)
    when there is none; with header_only, a line below the first heading never counts."""
    for at, found in enumerate(lines):
        if found.startswith("## ") and (header_only or add):
            if add:
                lines.insert(at, line)
            return
        if found.startswith(key):
            lines[at] = line
            return
    if add:
        lines.append(line)
