"""Whether a builder (small-council:council-builder) may stop: the seat gate hands it the SubagentStop input
on stdin, as a worker's and a verifier's stops are judged in the hook itself.

    python src/council/commands/script.py builder_stop < <SubagentStop input>

Exit 0 lets it stop. Exit 1 sends it back once, with one line of reasons on stdout that the hook passes on.
It lets through a BLOCKED reply (records.seat_files.blocked, as the seat gate reads a worker's) and a one-line
NEEDS: reply whose NEEDS: fix form carries all four parts. Any other reply must be the one line naming
<run>/report-<n>.md: the report is there, records.report_head reads its head, and task n's last saved round was
saved from that head (council patch save ran on this report). Input it can't read, and any fault of its own, let
the builder stop: this must never trap an agent on a guess (D20)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from council.records import home as where
from council.records import patches, report_head, seat_files

ONE_LINE = "Wrote <absolute run folder>/report-<n>.md — task <n>, round <r> saved"
FINISH = ("finish by writing your report, <run>/report-<n>.md, its head first, and saving its round with council "
          "patch save <n>, then reply with exactly one line: %s. If the user must decide, reply NEEDS: <question>; "
          "if you couldn't do the task, reply BLOCKED: <reason> instead." % ONE_LINE)
FIX_FORM = "NEEDS: fix <file:line> · does: <…> · should: <…> · seen: <…>"
LEAD = " \t>*_"                                       # what may stand before a reply's first word
NEEDS_FIX = re.compile(r"NEEDS:[*_]*\s*fix\b", re.IGNORECASE)
FIX_PARTS = (("file:line", re.compile(r"[^\s:]+:[0-9]+")), ("does:", re.compile(r"\bdoes:\s*\S", re.I)),
             ("should:", re.compile(r"\bshould:\s*\S", re.I)), ("seen:", re.compile(r"\bseen:\s*\S", re.I)))
WROTE = re.compile(r"(?:^|[^a-z])wrote[*_:]*\s+(.*)", re.IGNORECASE)
REPORT = re.compile(r"(?<![A-Za-z0-9_.-])report-([0-9]+)\.md(?![A-Za-z0-9_/\\-]|\.[A-Za-z0-9]|\]\()")
MARKS = "[]`\"'*_(< \t"


def reason(raw: bytes) -> str:
    """Why the builder is sent back, as one line; '' to let it stop."""
    try:
        data = json.loads(raw)
    except ValueError:
        return ""
    reply = data.get("last_assistant_message") if isinstance(data, dict) else None
    if not isinstance(reply, str):
        return ""                                     # no reply field: the host's affair
    lines = [line.strip() for line in reply.split("\n") if line.strip()]
    if not lines:
        return "you stopped without a reply — " + FINISH   # a turn limit, before it answered
    if seat_files.blocked(lines):
        return ""
    if lines[0].lstrip(LEAD).startswith("NEEDS:"):
        return _needs(lines)
    cwd = data.get("cwd") if isinstance(data.get("cwd"), str) else ""
    return _wrote(lines, cwd)


def _needs(lines: list[str]) -> str:
    """A NEEDS: return: one line, and a NEEDS: fix names the fault in all four parts."""
    first = lines[0].lstrip(LEAD)
    if NEEDS_FIX.match(first):
        missing = [name for name, part in FIX_PARTS if not part.search(first)]
        if missing:
            return ("a NEEDS: fix line names the fault in the code under your task in four parts, and yours has no %s "
                    "— reply with exactly one line: %s" % (", ".join(missing), FIX_FORM))
    if len(lines) > 1:
        return ("a NEEDS: return is exactly one line, nothing else — NEEDS: <question>, or %s; put what you found "
                "in the line itself" % FIX_FORM)
    return ""


def _named(lines: list[str], cwd: str) -> tuple[Path | None, int | None, bool]:
    """The report the reply's Wrote line names: (its path, task n, whether a file is there). For each name, the
    whole text before report-<n>.md is tried, then the text from each space, quote or mark on, as the seat gate
    reads a worker's file; a relative name is joined to cwd. (None, None, False): the reply names no report."""
    for line in lines:
        wrote = WROTE.search(line)
        found = REPORT.search(wrote.group(1)) if wrote else None
        if not found:
            continue
        text = wrote.group(1)[:found.end()].split("](")[-1]
        named = None
        for start in range(len(text)):
            if start and text[start - 1] not in MARKS:
                continue
            name = where.native(text[start:].lstrip(MARKS))
            absolute = Path(name).is_absolute() or re.match(r"[A-Za-z]:[\\/]", name) is not None
            path = Path(name) if absolute or not cwd else Path(where.native(cwd)) / name
            if path.is_file():
                return path, int(found.group(1)), True
            named = named or (path if absolute else None)
        return named, int(found.group(1)), False
    return None, None, False


def _wrote(lines: list[str], cwd: str) -> str:
    """The Wrote line: its report is there with a head the helper reads, saved as task n's last round."""
    path, task, there = _named(lines, cwd)
    if task is None:
        return FINISH
    if path is None:
        return ("no file at the name you gave (looked in %s) — reply with the report's full path: %s"
                % (cwd or "the folder the session sent", ONE_LINE))
    shown = path.as_posix()
    if not there or path.stat().st_size == 0:
        return ("%s isn't there or is empty — write the round's report, its head first (%s), run council patch save "
                "%d, then reply again with your one line" % (shown, report_head.SHAPE, task))
    head, wrong = report_head.read(path)
    if head is None:
        return "%s — %s. Fix the head, run council patch save %d, then reply again with your one line." % (
            shown, "; ".join(wrong), task)
    saved = patches.rounds(path.parent, task)
    if not saved:
        return ("%s — task %d has no saved round: run council patch save %d (it checks this report against the "
                "round's diff), then reply again with your one line" % (shown, task, task))
    if saved[-1].head != head._asdict():
        return ("%s — its head is not the one task %d's last saved round (round %d) was saved from: the report "
                "changed after that save. Run council patch save %d, then reply again with your one line"
                % (shown, task, saved[-1].round, task))
    if len(lines) > 1:
        return ("%s is in order and task %d round %d is saved — now reply with exactly one line, nothing else: "
                "Wrote %s — task %d, round %d saved" % (shown, task, saved[-1].round, shown, task, saved[-1].round))
    return ""


def blocked(raw: bytes) -> bool:
    """Whether the stop's reply is a BLOCKED one (records.seat_files.blocked), for the seat gate's worker and verifier;
    input it can't read is no BLOCKED reply."""
    try:
        data = json.loads(raw)
    except ValueError:
        return False
    reply = data.get("last_assistant_message") if isinstance(data, dict) else None
    return isinstance(reply, str) and bool(seat_files.blocked(reply.split("\n")))


def main(words: list[str]) -> int:
    """Read the SubagentStop input on stdin; exit 1 with the reasons on stdout to send the builder back, else 0.
    With the word `blocked` (the seat gate, for a worker's or a verifier's stop): exit 1 when the reply is not a
    BLOCKED line, so the hook goes on to judge its file; 0 when it is, or on any fault."""
    try:
        if words[:1] == ["blocked"]:
            return 0 if blocked(sys.stdin.buffer.read()) else 1
        why = reason(sys.stdin.buffer.read())
    except Exception:  # noqa: BLE001 — any fault of its own lets the builder stop (D20)
        return 0
    if not why:
        return 0
    print(why)
    return 1
