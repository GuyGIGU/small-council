"""Per-seat kept, cut and refuted counts of a run (the helper's synthesis_counts), for its ledger rows.

Provenance is an item's last "from:" field in synthesis.md's "## Kept" and "## Cut", read as seat#item tokens:
"hunt#1, #2", "beck#1,2", "hunt#3 and beck#3", "hunt#4/beck#4" and "hunt #1" each name every item, and an item
counts once however often it is named. A bare seat name counts as one item, only for a seat the run had, and
never inside brackets. A REFUTED row of a verify-*.md table refutes each seat whose kept item merged into it.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from council.records.seat_files import lines, listed, lower

ITEM = re.compile(r"[-+]? *_*C?[0-9]+[a-z]?_*\.? +(·|\|) ")
SEAT_ITEM = re.compile(r"[A-Za-z][A-Za-z0-9._-]*#C?[0-9]+[a-z]?")
NUMBER = re.compile(r"#?C?[0-9]+[a-z]?")
WORD = re.compile(r"[A-Za-z][A-Za-z0-9._-]*")


def provenance(line: str) -> str | None:
    """The line's from: field: the last one after " · ", else the last after a start or a non-alphanumeric."""
    lo, found, real = lower(line), None, False
    for hit in re.finditer("from:", lo):
        before = lo[:hit.start()].rstrip(" \t")
        if before.endswith("·"):
            found, real = hit.start(), True
        elif not real and not re.search("[a-z0-9]$", before):
            found = hit.start()
    return None if found is None else re.sub(r" +· .*$", "", line[found + 5:])


def named(field: str, n: str, known: Callable[[str], bool]) -> list[tuple[str, str]]:
    """The (seat, seat#item) pairs a from: field names, one per naming; a bare seat name is its item n."""
    found, carry, numbered, depth, token = [], "", False, 0, ""

    def flush() -> None:
        nonlocal carry, numbered
        if carry and not numbered and known(carry):
            found.append((carry, carry + "#" + n))
        carry, numbered = "", False

    for ch in field + " ":
        if ch not in "[](){} ,;&+/":
            token += ch
            continue
        word = re.sub(r"[.,:;]+$", "", token)
        if not token:
            pass
        elif SEAT_ITEM.fullmatch(word):
            flush()
            carry, numbered = word[:word.index("#")], True
            found.append((carry, word))
        elif NUMBER.fullmatch(word) and carry:
            numbered = True
            if known(carry):
                found.append((carry, carry + "#" + word.lstrip("#")))
        elif depth == 0 and WORD.fullmatch(word):
            flush()
            carry = word
        else:
            flush()
        token = ""
        depth += 1 if ch in "[({" else -1 if ch in "])}" and depth > 0 else 0
    flush()
    return found


def refuted(path: Path) -> set[str]:
    """The item numbers a verify file's table calls REFUTED, read by its "#" and "Verdict" columns."""
    found, verdict, number = set(), 0, 1
    for line in lines(path):
        if not line.startswith("|"):
            continue
        cells = line.split("|") + [""]
        if not verdict:
            for at in range(1, len(cells) - 2):
                head = lower(re.sub(r"[ \t\r*]", "", cells[at]))
                if head == "verdict":
                    verdict = at
                elif head == "#":
                    number = at
            continue
        word = re.match("[A-Za-z]*", re.sub("^[^A-Za-z]*", "", cells[min(verdict, len(cells) - 1)])).group()
        n = lower(re.sub(r"[ \t\r*#.]", "", cells[min(number, len(cells) - 1)]))
        if word.upper() == "REFUTED" and re.fullmatch("c?[0-9]+[a-z]?", n):
            found.add(n)
    return found


def counts(run: Path) -> dict[str, tuple[int, int, int]]:
    """Each credited seat's (kept, cut, refuted); {} when the run has no synthesis.md."""
    run = Path(run)
    if not (run / "synthesis.md").is_file():
        return {}
    slugs = set(" ".join(line.split("\t")[0] for line in lines(run / "seats.tsv")[1:]).split(" ")) - {""}
    tally, once, owners, section = {}, set(), {}, ""             # type: dict, set, dict, str
    for raw in lines(run / "synthesis.md"):
        if raw.startswith("## "):
            section = "k" if raw.startswith("## Kept") else "c" if raw.startswith("## Cut") else ""
            continue
        line = re.sub(r"[\r`*]", "", raw).replace("\t", " ")
        field = provenance(line) if section and ITEM.match(line) else None
        if field is None:
            continue
        n = lower(re.sub("[_.]", "", re.sub("^[-+]? *", "", line).split(" ")[0]))
        for seat, key in named(field, n, lambda word: not slugs or word in slugs):
            figures = tally.setdefault(seat, [0, 0])
            if (section, key) not in once:
                once.add((section, key))
                figures[section == "c"] += 1
            if section == "k":
                owners.setdefault(n, []).append(seat)
    against = {}                                                   # type: dict
    for n in set().union(*(refuted(run / name) for name in listed(run, "verify-*.md"))):
        for seat in owners.get(n, []):
            against[seat] = against.get(seat, 0) + 1
    return {seat: (kept, cut, against.get(seat, 0)) for seat, (kept, cut) in tally.items()}
