"""Whether a builder (small-council:council-builder) may stop: the seat gate hands it the SubagentStop input
on stdin, as a worker's and a verifier's stops are judged in the hook itself.

    python src/council/commands/script.py builder_stop < <SubagentStop input>

Exit 0 lets it stop. Exit 1 sends it back once, with one line of reasons on stdout that the hook passes on.
It lets through a BLOCKED reply (records.seat_files.blocked, as the seat gate reads a worker's) and a one-line
NEEDS: reply whose NEEDS: fix form carries all four parts (build_seat's one pattern), once the files hold no edit
outside a saved round (council patch hold takes them off). Any other reply must be the one line naming
<run>/report-<n>.md: the report of the build seat running for this session, when one is, in its run; the report is
there, records.report_head reads its head, task n's last saved round was saved from that head (council patch save
ran on this report), and the files are still that round's tree. Input it can't read, and any fault of its own, let
the builder stop: this must never trap an agent on a guess (D20)."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from council import git
from council.commands import build_seat, resolve
from council.records import home as where
from council.records import patches, report_head, seat_files, seats

ONE_LINE = "Wrote <absolute run folder>/report-<n>.md — task <n>, round <r> saved"
FINISH = ("finish by writing your report, <run>/report-<n>.md, its head first, and saving its round with council "
          "patch save <n>, then reply with exactly one line: %s. If the user must decide, reply NEEDS: <question>; "
          "if you couldn't do the task, reply BLOCKED: <reason> instead." % ONE_LINE)
FIX_FORM = "NEEDS: fix <file:line> · does: <…> · should: <…> · seen: <…>"
LEAD = build_seat.LEAD                                # what may stand before a reply's first word
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
    cwd = data.get("cwd") if isinstance(data.get("cwd"), str) else ""
    session = data.get("session_id") if isinstance(data.get("session_id"), str) else ""
    if build_seat.needs(lines[0]):
        return _needs(lines) or _unsaved(_building(cwd, session))
    return _wrote(lines, cwd, _building(cwd, session))


def _building(cwd: str, session: str) -> tuple[Path, int] | None:
    """The one build seat running for this session — its run and task — among the in-progress builds this session
    may drive (cap.open_here) from the folder the input names; None when there is none, or more than one, or the input
    names no folder (the seat records judge, not a guess)."""
    from council.commands import cap
    base = where.native(cwd) if cwd else ""
    if not base or not os.path.isdir(base):
        return None
    found = []
    for run in cap.open_here(where.council_home(base), where.this_tree(base), session):
        if resolve.field(Path(run), "mode") != "council-implement":
            continue
        found += [(Path(run), int(match.group(1))) for match in
                  (build_seat.SEAT.fullmatch(row.get("slug", "")) for row in seats.rows(Path(run))
                   if row.get("state") == "running") if match]
    return found[0] if len(found) == 1 else None


def _unsaved(seat: tuple[Path, int] | None) -> str:
    """A NEEDS: return that leaves edits outside a saved round on the files: they would leak into the next task's
    gates and round, so the builder holds them first (council patch hold)."""
    if seat is None:
        return ""
    run, task = seat
    _, _, files = build_seat.unsaved(run)
    if not files:
        return ""
    return ("you stop with edits in no saved round (%d file(s): %s) — take them off the files with council patch hold "
            "%d, which keeps them in %s for the task's next builder, then reply again with your NEEDS: line"
            % (len(files), ", ".join(files[:5]) + (" …" if len(files) > 5 else ""), task,
               (patches.folder(run) / ("T%d-held.patch" % task)).as_posix()))


def _needs(lines: list[str]) -> str:
    """A NEEDS: return: one line, and a NEEDS: fix names the fault in all four parts."""
    first = lines[0].lstrip(LEAD)
    if build_seat.fix_at(first) is not None:
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


def _wrote(lines: list[str], cwd: str, seat: tuple[Path, int] | None) -> str:
    """The Wrote line: the running build seat's report, there with a head the helper reads, saved as task n's last
    round, the files still that round's tree."""
    path, task, there = _named(lines, cwd)
    if task is None:
        return FINISH
    if seat and (task != seat[1] or path is None or not _same(path.parent, seat[0])):
        right = (seat[0] / ("report-%d.md" % seat[1])).as_posix()
        return ("you were sent for task %d (its build seat task-%d runs in %s), and your reply names %s — the report "
                "of your task is %s: write it, its head first (%s), run council patch save %d, then reply with exactly "
                "one line: Wrote %s — task %d, round <r> saved"
                % (seat[1], seat[1], seat[0].name, path.as_posix() if path else "report-%d.md" % task, right,
                   report_head.SHAPE, seat[1], right, seat[1]))
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
    top = resolve.field(path.parent, "code-root")      # the run's own: no guess at which tree the round was of
    now = git.files_tree(where.native(top)) if top else ""
    if now and now != saved[-1].tree:
        return ("%s — the files changed after task %d round %d was saved, so the round is not the change. Run council "
                "patch save %d again (while your seat runs it replaces round %d), then reply again with your one line"
                % (shown, task, saved[-1].round, task, saved[-1].round))
    if len(lines) > 1:
        return ("%s is in order and task %d round %d is saved — now reply with exactly one line, nothing else: "
                "Wrote %s — task %d, round %d saved" % (shown, task, saved[-1].round, shown, task, saved[-1].round))
    return ""


def _same(one: Path, other: Path) -> bool:
    """Two folders are one: compared resolved, case folded where the file system folds it."""
    return os.path.normcase(os.path.realpath(str(one))) == os.path.normcase(os.path.realpath(str(other)))


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
