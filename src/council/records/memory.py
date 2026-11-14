"""The project's memory file: which file it is (the config's `- conventions:` path under ## Memory, else
.council/conventions.md, else a root one), what is wrong with how it reads (one id on two entries, ids that no entry
carries, lines that open like an entry but are not read), the entries a run is served (an observed failure only
while its evidence still supports it, records/memory_audit.py), and the one guarded way to rewrite it. bin/council
keeps memory_file and memory_entries for the session-start hook and run open (S8b)."""
from __future__ import annotations

import contextlib
import os
import re
from typing import NamedTuple

from council.records import bytewise, config, memory_audit
from council.records import home as where
from council.records import memory_entries as parsed

NAME = "conventions.md"
TEMPLATE = "Write each entry as a heading (### AP-1: title) or a bullet (- **AP-1 — title** …)"
_IDS = re.compile(r"(^|[^A-Za-z0-9_])(AP|EC|D|F)-[0-9]+([^A-Za-z0-9_]|\Z)"
                  r"|\A(#+|[-*+])[ \t]*[*_]*([Aa][Pp]|[Ee][Cc]|D|F)-?[0-9]+")


class Located(NamedTuple):
    """The memory file (path), the configured path when one is set (conf), a note when the configured file is
    missing and another is read instead, and a second memory file with entries the council never reads."""

    path: str
    conf: str
    note: str
    alt: str
    alt_n: int


def _isfile(path: str) -> bool:
    return bool(path) and os.path.isfile(where.native(path))


def absolute(root: str, p: str) -> str:
    """A configured memory path as a path under the repo: "/x" is the repo's root unless that absolute file
    exists, and a relative path hangs off the root."""
    p = p.replace("\\", "/")
    if p == "" or re.match(r"[A-Za-z]:", p):
        return p
    if p.startswith("/"):
        return root + p if not _isfile(p) and _isfile(root + p) else p
    return root + "/" + (p[2:] if p.startswith("./") else p)


def locate(home: str) -> Located:
    """The memory file of a council home, as the helper's memory_file finds it."""
    root = home[:home.rfind("/")] if "/" in home else home
    line = config.memory_line(where.native(home))
    full, first = (absolute(root, line[0]), absolute(root, line[1])) if line else ("", "")
    conf = first if not _isfile(full) and first and _isfile(first) else full
    path, note = conf, ""
    if not path or not _isfile(path):
        alt = next((p for p in (home + "/" + NAME, root + "/" + NAME) if _isfile(p)), "")
        if not conf:
            path = alt or home + "/" + NAME
        elif alt:
            path = alt
            note = "the config's memory path, %s, doesn't exist — reading %s instead" % (_rel(conf, root),
                                                                                          _rel(alt, root))
    for alt in (home + "/" + NAME, root + "/" + NAME):
        if _isfile(alt) and not memory_audit.same_file(alt, path):
            count = len(rows(alt))
            if count:
                return Located(path, conf, note, alt, count)
    return Located(path, conf, note, "", 0)


def _rel(path: str, root: str) -> str:
    return path[len(root) + 1:] if path.startswith(root + "/") else path


def rows(path: str) -> list[str]:
    """The entries of a memory file as rows (records/memory_entries.py)."""
    return parsed.rows(where.native(path))


def idlines(path: str) -> int:
    """How many lines (outside comments) name an entry id: a file with no entries yet, or one whose entries the
    council can't read."""
    try:
        with open(where.native(path), "rb") as stream:
            text = bytewise.read(stream.read())
    except OSError:
        return 0
    count, comment = 0, False
    for line in bytewise.records(text):
        if comment or re.match(r"[ \t]*<!--", line):
            comment = "-->" not in line
        elif _IDS.search(line):
            count += 1
    return count


def unread(path: str) -> list[str]:
    """The loud lines for a memory file whose entries the council can't read — the whole file, or single lines that
    open like an entry — and for an id two entries share; none when all of it reads."""
    found = rows(path)
    ids = sorted((parsed.cells(row)[0] for row in found), key=lambda i: i.encode("latin-1"))
    shared = sorted({i for i in ids if ids.count(i) > 1}, key=lambda i: i.encode("latin-1"))
    said, shown = [], path
    if shared:
        said.append("memory: WARNING — %s gives one id to more than one entry: %s — seats get both under one name, and "
                    "accept, reject and retire can't tell them apart; give each its own number."
                    % (shown, bytewise.shown(", ".join(i for i in shared if i))))
    if not found:
        if idlines(path) > 0:
            said.append("memory: WARNING — %s names entry ids, but no entry could be read, so nothing in it reaches a "
                        "seat or a builder. %s, as references/templates/conventions.md shows." % (shown, TEMPLATE))
        return said
    skipped = parsed.skipped(where.native(path))
    if skipped:
        said.append("memory: WARNING — %s has line(s) that open like an entry but are not read, so they reach no "
                    "seat: %s. %s, as references/templates/conventions.md shows."
                    % (shown, bytewise.shown(skipped), TEMPLATE))
    return said


def served(found: list[str], audit: list[str]) -> list[str]:
    """The rows with each observed failure the audit found unsupported turned unknown, the reason in its section
    column — so the index and select serve only what check would stand behind."""
    why: dict[str, str] = {}
    for line in audit:
        cells = line.split("\t") + ["", ""]
        if cells[1] == "fatal" and cells[0] not in why:
            why[cells[0]] = cells[2]
    if not why:
        return found
    out = []
    for row in found:
        cells = row.split("\t")
        if len(cells) > 4 and cells[4] == "observed" and cells[0] in why:
            cells = cells + [""] * (6 - len(cells))
            cells[4], cells[5] = "unknown", "failure entry: " + why[cells[0]]
        out.append("\t".join(cells))
    return out


def would_serve(path: str, entry: str, home: str, top: str, mem: str) -> str:
    """Why entry `entry` of memory file `path` would not reach a brief as an observed failure — the parser's rules
    and the evidence audit both; '' when it would."""
    mine = [row for row in rows(path) if parsed.cells(row)[0] == entry]
    if not mine:
        return "it is not read as an entry"
    if len(mine) > 1:
        return "it appears more than once"
    cells = parsed.cells(mine[0])
    if cells[4] != "observed":
        return re.sub(r"\Afailure entry: ", "", cells[5], count=1)
    return next((line.split("\t")[2] for line in memory_audit.audit(mine, home, top, mem)
                 if line.split("\t")[1] == "fatal"), "")


def _others(found: list[str], entry: str) -> list[str]:
    return [row for row in found if parsed.cells(row)[0] != entry]


def replace(mem: str, before: str, after: str, entry: str, want: str, home: str, top: str) -> str:
    """Replace memory file `mem` with `after` — an edit of `before`, a copy of mem — only when the edit touched entry
    `entry` alone and left it `want`: proposed (off, under a Proposed section), observed (served, evidence and all) or
    gone. Every other entry must read exactly as before, no line may start or stop going unread, and mem must not
    have changed since the copy was taken. `entry` is C-locale text; the refusal ('' when it was written) is not."""
    had_rows, after_rows, shown = rows(before), rows(after), bytewise.shown(entry)
    had = sum(1 for row in had_rows if parsed.cells(row)[0] == entry)
    if (want, had) not in (("proposed", 0), ("observed", 1), ("gone", 1)):
        return "%s is used by %d entr(ies) before this edit — nothing written; give each its own number" % (shown, had)
    if _others(had_rows, entry) != _others(after_rows, entry):
        return "the edit would change other memory entries too — nothing written"
    unread_now = [re.sub(r" \(line [0-9]*\)", "", parsed.skipped(where.native(p))) for p in (before, after)]
    if unread_now[0] != unread_now[1]:
        return "the edit would change which memory lines go unread — nothing written"
    mine = [parsed.cells(row) for row in after_rows if parsed.cells(row)[0] == entry]
    if want == "gone" and mine:
        return "%s is still in the memory file — nothing written" % shown
    proposed = [c for c in mine if c[4] == "off" and re.match(r"[#* ]*propos", bytewise.lower(c[5]))]
    if want == "proposed" and len(proposed) != 1:
        return "%s did not land under ## Proposed — nothing written" % shown
    if want == "observed":
        why = would_serve(after, entry, home, top, mem)
        if why:
            return "%s would not be served (%s) — nothing written" % (shown, bytewise.shown(why))
    return _swap(mem, before, after)


def _swap(mem: str, before: str, after: str) -> str:
    """Written beside the file and moved over it, so the memory is never half-written; the copy keeps its mode."""
    try:
        with open(where.native(mem), "rb") as now, open(where.native(before), "rb") as then:
            same = now.read() == then.read()
    except OSError:
        same = False
    if not same:
        return "%s changed while this ran — nothing written; run it again" % mem
    import shutil                                   # only a write needs it (D34)
    new = where.native(mem + ".council-new")
    try:
        shutil.copyfile(where.native(mem), new)
        shutil.copymode(where.native(mem), new)
        with open(where.native(after), "rb") as src, open(new, "wb") as out:
            out.write(src.read())
        os.replace(new, where.native(mem))
    except OSError:
        with contextlib.suppress(OSError):
            os.remove(new)
        return "could not write %s" % mem
    return ""
