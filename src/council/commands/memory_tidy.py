"""council memory tidy: the consolidation operations the memory file shows by reading alone, numbered, for
the Chair to propose — `merge <id> into <id>` for two entries that serve the
same rule text (title and rule, the same once case, runs of blanks and trailing punctuation are set aside), and
`retire <id> — <why>` for an entry that names a retired id, or that carries a retired mark but still sits in a
section the council reads. It writes nothing: each operation is put to the user and applied on their yes, one at a
time. A rule now enforced by a hook is not looked for: nothing reads what the hooks enforce."""
from __future__ import annotations

import re

from council.commands import cli
from council.commands.memory import Memory
from council.records import bytewise, memory
from council.records.bytewise import EM
from council.records.memory_entries import MARKS, cells

MENTION = re.compile(r"(?<![A-Za-z0-9_])(?:AP|EC|D|F)-[0-9]+(?![A-Za-z0-9_])")
MARKED = re.compile(r"marked (%s)" % "|".join(MARKS))
HOOKS = "memory tidy: rules now enforced by a hook are not looked for — nothing reads what the hooks enforce"


def tidy(found: Memory) -> int:
    entries = memory.placed(found.mem)
    ops = merges(entries) + retirements(entries)
    name = found.mem.rsplit("/", 1)[-1]
    if ops:
        lines = ["%d. %s" % (n, bytewise.shown(op)) for n, op in enumerate(ops, 1)]
        lines.append("memory tidy: %d operation(s) for %s, nothing written — put each to the user and apply it on "
                     "their yes, one at a time" % (len(ops), name))
    else:
        lines = ["memory tidy: nothing to merge or retire in %s" % name]
    cli.say_all(lines + [HOOKS])
    return 0


def rule_text(c: list[str]) -> tuple[str, str]:
    """An entry's title and rule, with case, runs of blanks and trailing punctuation set aside."""
    def norm(text: str) -> str:
        text = "" if text == "-" else re.sub(r"[ \t]+", " ", bytewise.lower(text)).strip(" ")
        return re.sub(r"[ .,;:!?]+\Z", "", text)
    return norm(c[1]), norm(c[6])


def merges(entries: list[tuple[str, str]]) -> list[str]:
    """`merge <later> into <first>` for each entry whose rule text an earlier one already has (entries not
    retired, proposed or rejected; an id two entries share is memory's own warning, not a merge)."""
    first: dict[tuple[str, str], str] = {}
    ops = []
    for row, _ in entries:
        c = cells(row)
        key = rule_text(c)
        if c[4] == "off" or key == ("", ""):
            continue
        kept = first.setdefault(key, c[0])
        if kept != c[0]:
            ops.append("merge %s into %s" % (c[0], kept))
    return ops


def _retired_section(section: str) -> bool:
    return any(mark in bytewise.lower(section) for mark in MARKS)


def retirements(entries: list[tuple[str, str]]) -> list[str]:
    """`retire <id> — <why>` for an entry the council still reads whose title or rule names a retired id, and for
    one marked retired that still sits in a section other than ## Retired."""
    retired = {cells(row)[0] for row, section in entries if cells(row)[4] == "off"
               and (_retired_section(section) or MARKED.match(cells(row)[5]))}
    ops = []
    for row, section in entries:
        c = cells(row)
        if c[4] != "off":
            named = sorted({i for i in MENTION.findall(c[1] + " " + c[6]) if i in retired and i != c[0]})
            if named and c[0] not in retired:
                ops.append("retire %s %s it names %s, which is retired" % (c[0], EM, ", ".join(named)))
        elif MARKED.match(c[5]) and not _retired_section(section):
            ops.append("retire %s %s %s, but it still sits under %s; move it under ## Retired"
                       % (c[0], EM, c[5], bytewise.clip(section or "the top of the file", 60)))
    return ops
