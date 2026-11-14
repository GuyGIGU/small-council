"""The support behind each observed failure in the memory, as the helper's failure_audit judged it: lines
"<id> TAB note|fatal TAB <what is wrong>". It is fatal — the entry reaches no brief — when two entries share its id;
when its scope reaches every run as the scope matcher reads it; when its evidence names no file; when none of the
files it names can be read as cited; or when a verifier's verdict (CONFIRMED, REFUTED, MISCITED, REGRESSION,
INCOMPLETE, SCOPE-CREEP) is not on a cited line (or, for a file cited whole, on any line) as the verifier writes it: a
whole word, in capitals. OBSERVED and REPRODUCED name artifacts rather than a verdict line, so for them the files must
exist. A note is one piece that can't be used while another piece still carries the entry.

Each evidence path — a word with a folder in it or a record's extension, with or without lines (a.md:12,40-44,
a.md#L12) — is looked for from the repo root, then the council home. Rows and lines are C-locale text
(records/bytewise.py); the paths given are as the helper writes them."""
from __future__ import annotations

import os
import re

from council.records import bytewise, scope
from council.records import home as where
from council.records.bytewise import trim
from council.records.memory_entries import vword

VERIFIER = ("CONFIRMED", "REFUTED", "MISCITED", "REGRESSION", "INCOMPLETE", "SCOPE-CREEP")
_REC = re.compile(r"\.(md|txt|json|jsonl|tsv|csv|log|out|html|xml|yml|yaml)\Z")


def _cells(row: str) -> list[str]:
    found = row.split("\t")
    return found + [""] * (10 - len(found))


def rows_alone(found: list[str]) -> list[str]:
    """What the rows alone decide: an id two entries share, and a scope that reaches every run."""
    count: dict[str, int] = {}
    scopes: dict[str, str] = {}
    for row in found:
        cells = _cells(row)
        if cells[4] == "observed":
            count[cells[0]] = count.get(cells[0], 0) + 1
            scopes[cells[0]] = cells[2]
    out = []
    for entry, n in count.items():
        if n > 1:
            out.append(entry + "\tfatal\tits id is used by more than one entry; give each its own number")
            continue
        for item in scope.items(scopes[entry]):
            g = item.text
            if (scope.everyrun(g) or scope.covers("zz9-probe/zz9-probe.zz9probe", g, ".*", False)
                    or scope.covers("zz9-probe", g, ".*", False)):
                out.append(entry + "\tfatal\tits scope reaches every run; name the paths, seats or mode it concerns")
                break
    return out


class Piece:
    """A word of evidence read as a path: raw (as cited), path, lines ("-" for none)."""

    def __init__(self, t: str) -> None:
        t = re.sub(r"\A[(\[<\"'`]+", "", t, count=1)
        t = re.sub(r"[:,]+\Z", "", re.sub(r"[)\]>\"'`.;]+\Z", "", t, count=1), count=1)
        self.raw, self.path, self.lines = t, t, "-"
        found = re.search(r"#L?[0-9]+(-L?[0-9]+)?\Z", t)
        if found:
            self.lines, self.path = t[found.start() + 1:].replace("L", ""), t[:found.start()]
        else:
            found = re.search(r":[0-9][0-9,-]*\Z", t)
            if found:
                self.lines, self.path = t[found.start() + 1:], t[:found.start()]
        p = self.path
        self.ok = (p != "" and not re.match(r"[A-Za-z]+://", p)
                   and ("/" in p or bool(_REC.search(bytewise.lower(p)))
                        or (self.lines != "-" and bool(re.search(r"\.[A-Za-z0-9]+\Z", p)))))


class Pieces:
    """Every observed failure's evidence as pieces: (id, verdict word, raw, path, lines, kind, group). A path may
    hold a blank, and nothing in the text says which: the whole piece is tried first ("whole"), and its words
    ("part") only when no file has that whole name."""

    def __init__(self) -> None:
        self.group = 0
        self.out: list[tuple[str, str, str, str, str, str, int]] = []

    def add(self, entry: str, w: str, piece: Piece, kind: str) -> None:
        self.out.append((entry, w, piece.raw, piece.path, piece.lines, kind, self.group))

    def emit(self, entry: str, w: str, text: str) -> bool:
        whole = Piece(text)
        if not re.search(r"[ \t]", text):
            if not whole.ok:
                return False
            self.group += 1
            self.add(entry, w, whole, "only")
            return True
        words = [Piece(t) for t in re.split(r"[ \t]+", text)]
        parts = sum(1 for p in words if p.ok)
        if not whole.ok:
            if not parts:
                return False
        else:
            self.group += 1
            self.add(entry, w, whole, "whole" if parts else "only")
        if not parts:
            return True
        if not whole.ok:
            self.group += 1
        for p in words:
            if p.ok:
                self.add(entry, w, p, "part")
        return True

    def entry(self, cells: list[str]) -> None:
        w = vword(cells[9])
        w = w if w in VERIFIER else "-"
        cur, k = "", 0
        for piece in re.split(r"[,;]", cells[8].replace("\\", "/")):
            p = trim(piece)
            if p == "":
                continue
            if re.search(r":[0-9]", cur) and re.fullmatch(r"[0-9]+(-[0-9]+)?", p):
                cur = cur + "," + p                           # a.md:12,14 is one piece
                continue
            if cur != "":
                k += self.emit(cells[0], w, cur)
            cur = p
        if cur != "":
            k += self.emit(cells[0], w, cur)
        if not k:
            self.out.append((cells[0], w, "-", "-", "-", "only", 0))


def _real(folder: str) -> str:
    try:
        return os.path.realpath(where.native(folder)) if os.path.isdir(where.native(folder)) else ""
    except OSError:
        return ""


def _inside(real: str, roots: tuple[str, str]) -> bool:
    """cd -P's answer under the root or the home (an unreadable root, '', is every absolute path, as in bash)."""
    return any((real + os.sep).startswith(root + os.sep) if root else True for root in roots)


def same_file(a: str, b: str) -> bool:
    """The same file, however it is written (C:/x, c:/x, /c/x)."""
    if a == b:
        return True
    try:
        return os.path.samefile(where.native(a), where.native(b))
    except (OSError, ValueError):
        return False


def place(p: str, home: str, top: str, mem: str, roots: tuple[str, str]) -> tuple[str, str]:
    """(the file a piece's path names, or '', and what is wrong with it, or '-'): from the repo root, then the
    council home; never a link, a place outside the project or the memory file itself."""
    shown = bytewise.shown(p)
    f, why = "", "-"
    if p == "-":
        return f, why
    if "/../" in "/" + shown + "/":
        return "", "climbs out of the project"
    if shown.startswith("/") or re.match(r"[A-Za-z]:", shown):
        if not (shown.startswith(top + "/") or shown.startswith(home + "/")):
            return "", "is outside this project"
        f = shown if os.path.isfile(where.native(shown)) else ""
    elif os.path.isfile(where.native(top + "/" + shown)):
        f = top + "/" + shown
    elif os.path.isfile(where.native(home + "/" + shown)):
        f = home + "/" + shown
    if not f:
        return f, why
    if os.path.islink(where.native(f)):
        return "", "is a link; cite the file it points to"
    if not _inside(_real(f[:f.rfind("/")]), roots):
        return "", "leads outside this project"
    if mem and same_file(f, mem):
        return "", "is the memory file itself"
    return f, why


def span(r: str) -> tuple[int, int] | None:
    """A line or a range ("12", "40-44"); None for 0, or for a number no file reaches (past nine digits)."""
    s, e = r, r
    j = r.find("-")
    if j >= 0:
        s, e = r[:j], r[j + 1:]
    if len(s) > 9 or len(e) > 9:
        return None
    first, last = _number(s), _number(e)
    if last < first:
        first, last = last, first
    return (first, last) if first >= 1 else None


def _number(text: str) -> int:
    found = re.match(r"[ \t]*([+-]?[0-9]+)", text)
    return int(found.group(1)) if found else 0


def says(s: str, w: str) -> bool:
    """The verdict as the verifier writes it: a whole word, in capitals."""
    return bool(re.search(r"[^A-Za-z0-9_-]" + re.escape(w) + r"[^A-Za-z0-9_-]", " " + s + " "))


def lines_of(f: str) -> list[str]:
    try:
        with open(where.native(f), "rb") as stream:
            return bytewise.records(bytewise.read(stream.read()))
    except OSError:
        return []


def results(reqs: list[tuple[int, str, str, str]]) -> dict[int, tuple[str, str]]:
    """Per piece: what is wrong with its lines ('-' for nothing), and whether it shows its verdict (1, 0 or -)."""
    files = {f: lines_of(f) for _, f, _, _ in reqs}
    out = {}
    for q, f, lines, w in reqs:
        text = files[f]
        bad, shown = "-", "-" if w == "-" else "0"
        if lines != "-":
            for r in lines.split(","):
                found = span(r)
                if found is None or found[1] > len(text):
                    bad = "the file has %d line(s), not %s" % (len(text), r)
                    break
                if w != "-" and any(says(text[k - 1], w) for k in range(found[0], min(found[1], found[0] + 2000) + 1)
                                    if k <= len(text)):
                    shown = "1"
        elif w != "-":
            shown = "1" if any(says(line, w) for line in text) else "0"
        out[q] = (bad, shown)
    return out


def audit(found: list[str], home: str, top: str, mem: str) -> list[str]:
    """The audit's lines for the memory rows `found` (home, top and mem as the helper writes them)."""
    out = rows_alone(found)
    pieces = Pieces()
    for row in found:
        cells = _cells(row)
        if cells[4] == "observed":
            pieces.entry(cells)
    if not pieces.out:
        return out
    roots = (_real(top), _real(home))
    located: list[tuple[int, str, str, str, str, str]] = []
    reqs: list[tuple[int, str, str, str]] = []
    whole_found = None
    for entry, w, raw, p, lines, kind, group in pieces.out:
        if kind == "part" and group == whole_found:
            continue                                          # its whole piece was a file
        f, why = place(p, home, top, mem, roots)
        if kind == "whole":
            if not f:
                continue                                      # try its words instead
            whole_found = group
        q = len(located) + 1
        located.append((q, entry, w, raw, f or "-", why))
        if f:
            reqs.append((q, f, lines, w))
    return out + verdicts(located, results(reqs), found)


def verdicts(located: list[tuple[int, str, str, str, str, str]], checked: dict[int, tuple[str, str]],
             found: list[str]) -> list[str]:
    out, verdict, nopath, piece, good, shows = [], {}, set(), set(), {}, set()
    for q, entry, w, raw, f, why in located:
        verdict[entry] = w
        if raw == "-":
            nopath.add(entry)
            continue
        piece.add(entry)
        if f == "-":
            out.append("%s\tnote\tevidence %s %s"
                       % (entry, raw, why if why != "-" else "can't be found in this project"))
            continue
        bad, shown = checked.get(q, ("", ""))
        if bad != "-":
            out.append("%s\tnote\tevidence %s: %s" % (entry, raw, bad))
            continue
        good[entry] = good.get(entry, 0) + 1
        if shown == "1":
            shows.add(entry)
    listed: list[str] = []
    for row in found:
        cells = _cells(row)
        if cells[4] == "observed" and cells[0] not in listed:
            listed.append(cells[0])
    for entry in listed:
        if entry in nopath or entry not in piece:
            out.append(entry + "\tfatal\tits evidence names no file that can be checked")
        elif not good.get(entry):
            out.append(entry + "\tfatal\tnone of its evidence can be found and read as cited")
        elif verdict.get(entry, "-") != "-" and entry not in shows:
            out.append("%s\tfatal\tnone of the evidence it cites shows %s as the verifier writes it"
                       % (entry, verdict[entry]))
    return out
