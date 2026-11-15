"""What `council seat` writes under seats.tsv.lock: usage.tsv's rows, the seat's figures derived from them
(per agent id the latest report; references/run/run-accounting.md) and its seats.tsv row; and the seat file a
done seat must have."""
from __future__ import annotations

import os
import re
from pathlib import Path

from council.records import paths, seat_files, seat_rows, seats

HEADER = ["slug", "state", "agent", "tokens", "updated", "note", "agents", "reported"]
COUNT = re.compile("[0-9]*")


def number(cell: str) -> int:
    """A cell as awk reads `$n + 0`: its leading whole number, else 0."""
    found = re.match(r"[ \t]*([+-]?[0-9]+)", cell)
    return int(found.group(1)) if found else 0


def table(file: Path) -> list[list[str]]:
    """A TSV file's rows as awk splits them, each padded to eight cells; [] when it can't be read."""
    return [line.split("\t") + [""] * 8 for line in seat_files.lines(file)]


def add(file: Path, rows: list[list[str]], header: str) -> None:
    """Append rows; a file with nothing in it gets the header first. OSError when it can't be written."""
    empty = not file.is_file() or file.stat().st_size == 0
    with open(str(file), "wb" if empty else "ab") as stream:
        stream.write("".join("\t".join(row) + "\n" for row in ([header.split("\t")] if empty else []) + rows)
                     .encode("utf-8", "surrogateescape"))


def missing_file(run: Path, slug: str) -> str:
    """The file a done seat still lacks ('' when it is there, or no brief names the seat): a verifier's
    <slug>.md (or a re-check's <slug>b.md, a Workflow's <slug>-<letter>.md), a briefed seat's out: file."""
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
    """(agent runs, runs with usage, tokens, agents=0 declared) from usage.tsv: per agent id its latest runs and
    its tokens as a running total, an id never reported one run with no usage, an id-less report on its own."""
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
    """Put the seat's row (new: state agent tokens note updated, and the derived agents reported total) in seats.tsv:
    a lost header comes back, an older row (no reported cell) keeps its old rules, a new seat goes last."""
    file, out, found = seats.path(run), [], False
    for at, line in enumerate(seat_files.lines(file)):
        c = line.split("\t")
        if at == 0 and c[0] == "slug":
            out.append(c + HEADER[6 if len(c) < 7 else 7 if len(c) == 7 else 8:])
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
    if len(cells) >= 8 and c[7] != "":
        return head + [new["total"], new["updated"], new["note"] or c[5], new["agents"], new["reported"]]
    agents = (1 if c[6] == "" else number(c[6])) + bool(new["agent"] and c[2] and new["agent"] != c[2])
    tokens = str(number(c[3]) + int(new["tokens"])) if new["tokens"] else c[3]
    return head + [tokens, new["updated"], new["note"] or c[5], str(agents)]
