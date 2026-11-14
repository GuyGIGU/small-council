"""council collect: every seat file the brief names (and every other .md in seats/), held to the seat-file contract —
line 1, the proof of reading, an index that parses, within its cap and 16 KB, citations that resolve — and every
verify file to its shape. One row a seat; exit 1 when a row needs fixing, with what to do next."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Callable

from council.commands import cite_check, cli, event_note, gate_output, resolve
from council.records import citations, run_files, seat_files, seat_rows
from council.records import home as where

LIVE = ("running", "queued")
ROW = "%s %s %s %s %s %s %s%s"


def pad(text: str, width: int) -> str:
    """printf's %-<width>s: padded by bytes, as bash's printf counts them."""
    return text + " " * max(0, width - len(text.encode("utf-8", "surrogateescape")))


def row(slug: str, state: str, items: str, size: str, ref: str, cites: str, tokens: str, note: str) -> None:
    cli.say(ROW % (pad(slug, 16), pad(state, 8), pad(items, 7), pad(size, 4), pad(ref, 9), pad(cites, 7), tokens,
                   note))


class Flags:
    """What the rows found: any problem; a hard one (a seat not still working); a deep one (more than its
    citations); a not-in-brief file with a problem."""

    def __init__(self) -> None:
        self.bad = self.hard = self.deep = self.strays_bad = False

    def flag(self, stray: bool, live: bool, cite_only: bool = False) -> None:
        self.bad = True
        self.strays_bad |= stray
        if not live:
            self.hard = True
            self.deep |= not cite_only


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "collect")
    cli.no_words("collect", words)
    run = resolve.run_folder(args)
    folder = run.as_posix()
    top = resolve.field(run, "code-root") or where.this_tree()
    scope = cite_check.scope(top, resolve.field(run, "base"), folder, resolve.field(run, "mode"))
    brief = run / run_files.BRIEF
    if not brief.is_file():
        raise cli.Refusal("no brief.md in %s — write the brief first" % folder)
    seats = seat_files.brief_seats(brief)
    if not seats:
        raise cli.Refusal("brief.md has no seat blocks under '## Seats' (### <slug> — …)")
    if (run / run_files.DEBATE).is_file():
        seats += seat_files.brief_seats(run / run_files.DEBATE)       # a war room's round-2 files
    seats += strays(run, seats)
    row("seat", "file", "items", "KB", "ref", "cites", "tokens", "")
    flags, tally = Flags(), {"total": 0, "strays": 0, "sat": 0, "r2lost": []}
    for seat in seats:
        if seat.slug and not seat_rows.is_verifier(run, seat.slug):    # Challenge verifiers write no seat file
            one(run, scope, seat, seats, flags, tally)
    for name in seat_files.listed(run, "verify-*.md"):            # every verifier's file, a Workflow agent's too
        verify = run / name
        problems = seat_files.verify_problems(verify) if name != "verify-self.md" and verify.is_file() else ""
        if problems:
            cli.say("%s out of shape: %s — the seat-check hook never sees a Workflow's agents"
                    % (pad(name, 16), problems[:-2] if problems.endswith("; ") else problems))
            flags.bad = flags.hard = flags.deep = True
    return verdict(run, flags, tally)


def strays(run: Path, seats: list[seat_files.Seat]) -> list[seat_files.Seat]:
    """Every other .md in seats/, held to the same contract: the seat-check hook runs only for the council's own
    agent types, so a file a Workflow's agent wrote reaches nothing else before Judge. Its slug is its file name,
    its ref "?" (no brief block names a doc) and its cap "-" (none set)."""
    named = {re.sub(r"^.*\\", "", seat.out.rsplit("/", 1)[-1], flags=re.S) for seat in seats}
    return [seat_files.Seat(name, "?", "seats/" + name, "-") for name in seat_files.listed(run / "seats", "*.md")
            if (run / "seats" / name).is_file() and name not in named]


def tokens(run: Path, slug: str) -> tuple[str, str]:
    """The seat's tokens as the row shows them, and its state. Round 2 by the round-1 worker, resumed, has no row
    of its own; an older row's figure was never checked: "?"."""
    if slug.endswith("-r2") and not seat_rows.cell(run, slug, "state"):
        return "-", seat_rows.cell(run, slug[:-3], "state")
    count = citations.bash_int(seat_rows.cell(run, slug, "tokens") or "x")
    shown = "-"
    if count is not None and count > 0:
        shown = "~%dk" % ((count + 500) // 1000) if seat_rows.cell(run, slug, "reported") else "%s?" % (
            seat_rows.cell(run, slug, "tokens"))
    return shown, seat_rows.cell(run, slug, "state")


def state_of(run: Path, slug: str, state: str, seats: list[seat_files.Seat]) -> str:
    """A fresh round-2 worker (<slug>-r2) took over a lost round-1 worker: the round-1 row is judged by its file.
    A worker lost in a war room's round 2 fails the round-2 row; the round-1 file is done and judged by itself."""
    if not slug.endswith("-r2") and seat_rows.cell(run, slug + "-r2", "state"):
        return "done"
    if state in ("failed", "blocked") and not slug.endswith("-r2") and any(s.slug == slug + "-r2" for s in seats):
        return "done"
    return state


def one(run: Path, scope: cite_check.Scope, seat: seat_files.Seat, seats: list[seat_files.Seat], flags: Flags,
        tally: dict) -> None:
    """One seat's row."""
    stray = seat.ref == "?"
    note = " not-in-brief" if stray else ""
    tally["strays" if stray else "total"] += 1
    file = where.native(seat.out if cite_check.absolute(seat.out) else "%s/%s" % (run.as_posix(), seat.out))
    shown, state = tokens(run, seat.slug)
    state = state_of(run, seat.slug, state, seats)
    live = state in LIVE                                     # its file may simply not be done yet
    if state in ("failed", "blocked") + LIVE:
        note += " state:" + state
        flags.flag(stray, live)
    if seat.slug.endswith("-r2") and state in ("failed", "blocked"):
        tally["r2lost"].append(seat.slug)
    size = os.path.getsize(file) if os.path.isfile(file) else 0
    if not size and state == "skipped" and seat.slug.endswith("-r2"):       # sat round 2 out (war-room.md)
        why = seat_rows.cell(run, seat.slug, "note")
        row(seat.slug, "skipped", "-", "-", "-", "-", shown, " · " + why if why else "")
        tally["sat"] += 1
        return
    if not size:
        row(seat.slug, "missing", "-", "-", "-", "-", shown, note)
        flags.flag(stray, live)
        return
    head = seat_files.lines(file)[:9]
    blocked = [line for line in head[1:] if line.startswith("BLOCKED")]
    if blocked:
        said = gate_output.clip(blocked[0].replace("\r", ""), 140)
        cli.say("%s %s %s" % (pad(seat.slug, 16), pad("blocked", 8), said))
        flags.flag(stray, live)
        return
    checked = Checked(scope, seat, head, file, lambda cite_only=False: flags.flag(stray, live, cite_only))
    used, budget = seat_rows.tool_calls(run, seat.slug), seat_rows.tool_budget(run, seat.slug)
    note += checked.notes + (" tools %s/%s" % (used, budget or "?") if used else "")
    row(seat.slug, "ok", "%d/%s" % (checked.shape.parsed, seat.cap), str((size + 1023) // 1024), checked.ref,
        "%d/%d" % checked.cites, shown, " ·" + note if note else "")


class Checked:
    """A seat file that is there: its line 1, its proof of reading, its index's shape and size, its citations."""

    def __init__(self, scope: cite_check.Scope, seat: seat_files.Seat, head: list[str], file: str,
                 flag: Callable[..., None]) -> None:
        self.notes = ""
        first = head[0].replace("\r", "") if head else ""
        if not (first[1:] if first.startswith(seat_files.BOM) else first).startswith("# "):
            self._note(" no-heading", flag)
        self.ref = proof_of_reading(seat.ref, head[1:], flag)
        self.shape = seat_files.shape(file)
        if not any(line.startswith("## Index") for line in seat_files.lines(file)):
            self._note(" no-index", flag)
        if self.shape.unparsed:
            self._note(" unparsed-index(%d)" % self.shape.unparsed, flag)
        if not self.shape.parsed and not self.shape.none and not self.shape.unparsed:
            self._note(" empty-index", flag)
        most = citations.bash_int(seat.cap)
        if seat.cap != "-" and (most is None or self.shape.parsed > most):
            self._note(" over-cap", flag)
        if os.path.getsize(file) > 16 * 1024:
            self._note(" over-16KB", flag)
        self.cites = self._citations(scope, file, flag)

    def _note(self, note: str, flag: Callable[..., None]) -> None:
        self.notes += note
        flag()

    def _citations(self, scope: cite_check.Scope, file: str, flag: Callable[..., None]) -> tuple[int, int]:
        found = every = bare = unchecked = 0          # a path with no line counts as found; no path, as unchecked
        for item in seat_files.items(file):
            verdict = cite_check.status(scope, citations.rows(scope.top, item.cite))
            if verdict == "ok" or verdict.startswith(("deleted", "no-line")):
                found, every = found + 1, every + 1
                bare += verdict.startswith("no-line")
            elif verdict.startswith("n/a"):
                unchecked += 1
            else:
                every += 1
        if found != every:
            self.notes += " broken-cites"
            flag(cite_only=True)
        self.notes += (" no-line(%d)" % bare if bare else "") + (" unchecked(%d)" % unchecked if unchecked else "")
        return found, every


def proof_of_reading(ref: str, head: list[str], flag: Callable[..., None]) -> str:
    """ok | n/a | - | no-ref | no-doc | MISMATCH: the seat's ref: lines (lines 2 to 9) against its docs' titles. An
    empty title, or no ref: line, proves nothing. A file no brief block names has only its line checked."""
    said = [re.sub(r"^ref:[ \t\n\v\f\r]*", "", line) for line in head if line.startswith("ref:")]
    if ref == "none":
        return "n/a"
    if ref == "?":
        if said:
            return "-"
        flag()
        return "no-ref"
    got = [form for line in said for form in (seat_files.norm(line), seat_files.norm_wide(line))]
    verdict = "ok"
    for doc in (part for part in ref.split(" ;; ") if part):
        if not os.path.isfile(where.native(doc)):
            flag()
            return "no-doc"
        title = seat_files.ref_title(where.native(doc))
        if not title or title not in got:
            verdict = "MISMATCH"
            flag()
    return verdict


def verdict(run: Path, flags: Flags, tally: dict) -> int:
    """The closing line, the collect.finished event, and the exit code: 0 when every row is in order."""
    total = tally["total"]
    if not flags.bad:
        extra = " · %d sat out (skipped)" % tally["sat"] if tally["sat"] else ""
        extra += " · %d other file(s) in seats/ in order too" % tally["strays"] if tally["strays"] else ""
        cli.say("collect: all %d seats in order%s" % (total, extra))
        event_note.append(run, "collect.finished", "run", "passed", "seats=%d" % total,
                          "collection passed, but its event was not recorded")
        return 0
    event_note.append(run, "collect.finished", "run", "failed", "seats=%d" % total,
                      "collection failed, and its event was not recorded")
    if not flags.hard:
        cli.say("collect: seats still working — after a compaction, wait for their notifications; if the session "
                "that started them has ended they are gone: mark them failed and re-dispatch each once (a war-room "
                "round-2 seat gets a fresh <slug>-r2 worker)")
        return 1
    if not flags.deep:
        cli.say("collect: only citations are wrong — the seats' work is there. 'council check <seat file>' names "
                "each bad one: fix those lines in place (ask that worker, or correct an obvious one yourself), then "
                "collect again")
        return 1
    cli.say("collect: fix the rows above — resume that worker (message its agent id) or re-dispatch it once")
    if flags.strays_bad:
        cli.say("collect: a not-in-brief row is a file in seats/ no seat block names — likely a Workflow agent's, "
                "which the seat-check hook never checks. Fix it to the seat-file shape (line 1 '# <Seat> — <lane> "
                "(<mode>)', a ref: line, an ## Index of index lines, under 16 KB), or ask the agent that wrote it")
    if tally["r2lost"]:
        cli.say("collect: %s lost round 2 with its worker — dispatch a fresh round-2 worker for each and record it "
                "as 'council seat <slug>-r2 running'; round 1 is done, don't re-run it" % ", ".join(tally["r2lost"]))
    return 1
