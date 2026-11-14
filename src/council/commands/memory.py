"""council memory [index | select [path|slug …] | check | propose claim|repair <id> | accept|reject F-<n>]: the
project's memory as the council serves it. index lists every entry and whether a brief gets it; select prints the
entries that apply to a run's files, seats and mode (or to the paths and slugs given); check finds anchors the code
no longer has and observed failures whose evidence no longer supports them; propose drafts an observed failure from
a run's verified record under ## Proposed, and accept or reject files the user's answer in their words. The memory
file and its entries are records/memory.py's; an observed failure is served only while its evidence still
supports it (records/memory_audit.py)."""
from __future__ import annotations

import os
import re
from typing import Iterable, NamedTuple

from council.commands import cli
from council.records import bytewise, config, memory, memory_audit, scope
from council.records import home as where
from council.records.bytewise import DOT, ELLIPSIS
from council.records.memory_entries import cells

USAGE = ("usage: council memory [index | select [path|slug …] | check | propose claim|repair <id> | accept|reject "
         "F-<n> --user-said \"…\"]")
SHORT = "usage: council memory [index | select [path|slug …] | check | propose … | accept … | reject …]"
PROPOSE = ("usage: council memory propose claim <id> [--scope <paths>] | memory propose repair <task> --scope "
           "<paths> [--run <folder>]")


class Memory(NamedTuple):
    """The memory as a command reads it: the council home, the repo root above it, the memory file, its entries
    (C-locale rows), the evidence audit of its observed failures, and the rows a brief is served."""

    home: str
    top: str
    mem: str
    entries: list[str]
    audit: list[str]
    served: list[str]


def main(args: cli.Args, words: list[str]) -> int:
    sub = words[0] if words else "index"
    _flags(args, sub, words)
    found = load()
    rest = words[1:]
    if sub == "index":
        return index(found)
    if sub == "select":
        from council.commands import memory_select
        return memory_select.select(args, found, rest)
    if sub == "check":
        from council.commands import memory_check
        return memory_check.check(found)
    if sub in ("propose", "accept", "reject"):
        from council.commands import memory_write
        return memory_write.main(args, found, sub, rest)
    raise cli.Refusal(USAGE)


def _flags(args: cli.Args, sub: str, words: list[str]) -> None:
    """What the helper's main() refused before the memory was read."""
    if sub == "select":
        cli.takes_flags(args, "memory select")
    elif sub == "propose":
        cli.takes_flags(args, "memory propose", "scope")
        if len(words) != 3 or words[1] not in ("claim", "repair"):
            raise cli.Refusal(PROPOSE)
    elif sub in ("accept", "reject"):
        cli.takes_flags(args, "memory " + sub, "user-said")
        if len(words) != 2:
            raise cli.Refusal("usage: council memory %s F-<n> --user-said \"<the user's words>\"" % sub)
        if not args.value("user-said"):
            raise cli.Refusal("memory %s needs --user-said \"<the user's own words>\" — their answer, not a summary "
                              "of it" % sub)
    else:
        cli.takes_flags(args, "memory")
        if len(words) > 1:
            raise cli.Refusal(SHORT)


def load() -> Memory:
    """The memory file and its entries, refusing when there is none; the config's missing path and a second
    memory file the council never reads are said on stderr."""
    home = where.council_home()
    top = home[:home.rfind("/")] if "/" in home else home
    found = memory.locate(home)
    mem = found.path
    if not os.path.isfile(where.native(mem)):
        if found.conf:
            raise cli.Refusal("no memory file: the config names %s, which doesn't exist — if the memory lives "
                              "elsewhere, point '- conventions:' under ## Memory at it; otherwise council-init "
                              "creates it" % mem)
        raise cli.Refusal("no memory file (%s) — council-init creates .council/%s" % (mem, memory.NAME))
    if found.note:
        cli.warn("council: %s — fix the - conventions: line under ## Memory in council.config.md" % found.note)
    if found.alt:
        cli.warn("council: WARNING — a second memory file, %s, holds %d entries the council never reads (it reads %s)"
                 " — merge them, or point the - conventions: line under ## Memory in council.config.md at the one "
                 "to keep" % (found.alt, found.alt_n, mem))
    entries = memory.rows(mem)
    audit = memory_audit.audit(entries, home, top, mem)
    return Memory(home, top, mem, entries, audit, memory.served(entries, audit) if audit else entries)


def slugs(home: str) -> list[str]:
    """The roster's slugs (C-locale text), as the scope matcher compares them."""
    return [slug for slug, _, _ in config.roster_rows(where.native(home)) if slug != "-"]


def say_all(lines: Iterable[str]) -> None:
    for line in lines:
        cli.say(line)


def index(found: Memory) -> int:
    say_all(indexed(found))
    return 0


def indexed(found: Memory) -> list[str]:
    """What council memory (index) says: every entry and whether a brief gets it, the scope items that match
    nothing, and what of the file goes unread (doctor counts the same lines)."""
    if not found.entries:
        return ["memory: no entries yet in %s" % found.mem] + memory.unread(found.mem)
    from council.commands import memory_tree
    return ([bytewise.shown(line) for line in index_lines(found.served)]
            + memory_tree.Tree(where.this_tree()).orphans(found.entries, slugs(found.home)) + memory.unread(found.mem))


def clip(t: str) -> str:
    if len(t) <= 60:
        return t
    return re.sub(r" [^ ]*\Z", "", t[:60], count=1) + " " + ELLIPSIS


def index_lines(served: list[str]) -> list[str]:
    """Every entry on one line, with whether a brief gets it; then a warning for the entries none does."""
    out, unserved = [], 0
    for row in served:
        c = cells(row)
        head = "%s %s %s" % (c[0], DOT, c[1])
        if c[4] == "settled":
            line = head + (" %s scope: %s" % (DOT, c[2]) if c[2] != "-" and not scope.everyrun(c[2])
                           else " %s every run" % DOT)
            line += " %s anchor: %s" % (DOT, c[3]) if c[3] != "-" else ""
            out.append(line + (" %s origin: %s" % (DOT, c[7]) if c[7] != "-" else ""))
            continue
        if c[4] == "observed":
            out.append("%s %s observed failure, not a rule %s scope: %s %s verdict: %s %s evidence: %s %s origin: %s"
                       % (head, DOT, DOT, c[2], DOT, c[9], DOT, c[8], DOT, c[7]))
            continue
        if c[4] == "off":
            out.append("%s %s not served (%s)" % (head, DOT, c[5] if c[5].startswith("marked") else "under "
                                                   + clip(c[5])))
            continue
        unserved += 1
        if c[5].startswith("failure entry: "):
            out.append("%s %s NOT SERVED as an observed failure %s %s" % (head, DOT, bytewise.EM, c[5][15:]))
        elif c[5].startswith("not a failure entry"):
            out.append("%s %s NOT SERVED %s only observed failures (F) belong under Observed Failures; move it to "
                       "its own section" % (head, DOT, bytewise.EM))
        else:
            out.append("%s %s NOT SERVED %s its section, %s, is not one the council reads as settled"
                       % (head, DOT, bytewise.EM, clip(c[5])))
    if unserved:
        one = unserved == 1
        out.append("memory: WARNING %s %d entr%s never reach%s a brief: move %s under a fitting settled section, "
                   "complete Observed Failures, or ## Retired" % (bytewise.EM, unserved, "y" if one else "ies",
                                                                  "es" if one else "", "it" if one else "them"))
    return out
