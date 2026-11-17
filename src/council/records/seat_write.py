"""What `council seat` writes under seats.tsv.lock (references/run/run-accounting.md); add takes that lock itself."""
from __future__ import annotations

import os
import re
from pathlib import Path

from council.records import bytewise, locks, owners, paths, seat_files, seat_rows, seats
from council.records.cells import leading

HEADER = ["slug", "state", "agent", "tokens", "updated", "note", "agents", "reported"]
COUNT = re.compile("[0-9]*")
LEAD = " \t>*_"                                   # what may stand before a NEEDS: line's first word
NEEDS_FIX = re.compile(r"NEEDS:[*_]*\s*[*_`]*(?i:fix)\b[*_`:]*\s*(\S*)")


def needs(note: str) -> bool:
    """A NEEDS: line, as a builder writes it or the Chair records it: markdown marks before the word are allowed.
    The one reader of a seat's NEEDS: note: here, where the note ends, and build_seat, the builder's stop, the tree
    and the pack through it."""
    return note.lstrip(LEAD).startswith("NEEDS:")


def fix_at(note: str) -> str | None:
    """Where a NEEDS: fix line says the fault is (its file:line, '?' when it names none); None for any other note.
    Fix in any case, markdown marks allowed: the one pattern the builder's stop holds to the four-part form too."""
    found = NEEDS_FIX.match(note.lstrip(LEAD))
    return (found.group(1).strip("`*_") or "?") if found else None


def table(file: Path) -> list[list[str]]:
    """A TSV file's rows as awk splits them, each padded to eight cells; [] when it can't be read."""
    return [line.split("\t") + [""] * 8 for line in bytewise.file_lines(file, fold=False)]


def add(file: Path, rows: list[list[str]], header: str) -> None:
    """Append rows to a run's seat file (seats.tsv, usage.tsv, tools.tsv) under the run's seat lock, `seats.tsv.lock`
    beside it, taken here unless this process holds it already: a file with nothing in it gets the header first,
    and a row is never joined to a torn last line. OSError when it can't be written or the lock can't be taken."""
    lock = file.parent / (seats.SEATS + ".lock")
    mine = owners.first_line(lock / "owner") == str(os.getpid())
    if not mine and not locks.acquire(lock):
        raise OSError("seat lock unavailable: " + lock.as_posix())
    try:
        with open(str(file), "ab+") as stream:
            stream.seek(0, os.SEEK_END)
            empty = stream.tell() == 0
            if not empty:
                stream.seek(-1, os.SEEK_END)
            torn = not empty and stream.read(1) != b"\n"
            out = [header.split("\t")] if empty and header else []
            text = "".join("\t".join(row) + "\n" for row in out + rows)
            stream.write((("\n" if torn and text else "") + text).encode("utf-8", "surrogateescape"))
    finally:
        if not mine:
            locks.release(lock)


def missing_file(run: Path, slug: str) -> str:
    """The file a done seat still lacks: a verifier's, or a briefed seat's out:; '' when there or not briefed."""
    if slug.startswith("verify-"):
        names = [slug + ".md"] + seat_files.listed(run, slug + "[a-z].md") + seat_files.listed(run, slug + "-*.md")
        found, file = [run.as_posix() + "/" + name for name in names], run.as_posix() + "/" + slug + ".md"
    elif not any(seat.slug == slug for seat in seat_files.brief_seats(Path(run) / "brief.md")):
        return ""
    else:
        file = seat_files.out_path(run, slug)
        if "round 2" in seat_rows.cell(run, slug, "note"):
            file = (file[:-3] if file.endswith(".md") else file) + "-r2.md"
        found = [file]
    return "" if any(os.path.isfile(name) and os.path.getsize(name) > 0 for name in found) else file


def seat_usage(run: Path, slug: str) -> tuple[int, int, int, bool]:
    """(agent runs, runs with usage, tokens, agents=0 declared) from usage.tsv, per agent id its latest."""
    runs = reported = tokens = 0
    declared, ids = False, {}
    for at, kind, n, figure in ((c[2], c[3], c[4], c[5]) for c in table(seats.path(run, seats.USAGE))[1:]
                                if c[1] == slug):
        if not COUNT.fullmatch(n) or not COUNT.fullmatch(figure) or len(figure) > 12:
            continue
        declared = declared or (kind, n) == ("finished", "0")
        k = int(n) if n else 1
        if at == "":
            if kind == "finished":
                runs, reported, tokens = runs + k, reported + k * bool(figure), tokens + int(figure or 0)
            continue
        one = ids.setdefault(at, {"runs": 1, "tokens": None, "last": 0})
        if kind == "finished":
            one["runs"] = k
            if figure:
                f, last = int(figure), one["last"]   # a running total replaces the last; a smaller one is fresh
                one["tokens"] = f if one["tokens"] is None else one["tokens"] + (f - last if f >= last else f)
                one["last"] = f
    for one in ids.values():
        runs += one["runs"]
        if one["tokens"] is not None:
            reported, tokens = reported + one["runs"], tokens + one["tokens"]
    return runs, reported, tokens, declared


def rewrite(run: Path, slug: str, new: dict[str, str]) -> None:
    """The seat's row in seats.tsv: a lost header back, an older row under its old rules, a new seat last."""
    file, out, found = seats.path(run), [], False
    for at, line in enumerate(bytewise.file_lines(file, fold=False)):
        c = line.split("\t")
        if at == 0 and c[0] == "slug":
            out.append(c + HEADER[min(max(len(c), 6), 8):])
            continue
        if at == 0:
            out.append(HEADER)
        if c[0] == slug:
            found = True
            out.append(_row(c, new))
        else:
            out.append(c)
    if not found:
        out.append([slug, new["state"], new["agent"], new["total"], new["updated"], new["note"], new["agents"],
                    new["reported"]])
    data = "".join("\t".join(row) + "\n" for row in out).encode("utf-8", "surrogateescape")
    paths.atomic_write(file, data, ".seats.", keep_mode=True)


def _row(cells: list[str], new: dict[str, str]) -> list[str]:
    c = cells + [""] * 8
    head = [c[0], new["state"], new["agent"] or c[2]]
    note = new["note"] or ("" if _rerun_done(c, new) else c[5])
    if len(cells) >= 8 and c[7] != "":
        return head + [new["total"], new["updated"], note, new["agents"], new["reported"]]
    agents = (1 if c[6] == "" else leading(c[6])) + bool(new["agent"] and c[2] and new["agent"] != c[2])
    tokens = str(leading(c[3]) + int(new["tokens"])) if new["tokens"] else c[3]
    return head + [tokens, new["updated"], note, str(agents)]


def _rerun_done(c: list[str], new: dict[str, str]) -> bool:
    """A NEEDS: note ends when its seat, started again (queued or running), is recorded done with no note: the
    stop it named was the earlier run's. A late usage report on the stop itself (done to done) keeps it."""
    return new["state"] == "done" and c[1] in ("queued", "running") and needs(c[5])
