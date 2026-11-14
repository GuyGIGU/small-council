"""council doctor's memory findings: no memory file, or the config naming one that is missing; entries the council
can't read, or that never reach a brief; a second memory file it never reads; stale anchors and unsupported
observed failures (what council memory check says); scope items that match nothing (what council memory says); a
memory past what every run reads; and proposals awaiting the user's answer."""
from __future__ import annotations

import os
import re

from council.commands.doctor import Doctor
from council.records import bytewise, memory, memory_audit, memory_entries
from council.records import home as where
from council.records.memory_entries import cells

READ_EVERY_RUN = 25600       # bytes: about what every run reads of the memory
TEMPLATE = "the plugin's references/templates/conventions.md shows"


def memory_file(doc: Doctor) -> None:
    found = memory.locate(doc.home)
    if os.path.isfile(where.native(found.path)):
        entries(doc, found)
    elif found.conf:
        doc.warn("no memory file: the config names %s, which doesn't exist" % found.conf,
                 "if the memory lives elsewhere, point the '- conventions:' line under ## Memory at it; otherwise "
                 "council-init creates it")
    else:
        doc.warn("no memory file found", "council-init creates .council/" + memory.NAME)


def _count(rows: list[str], state: str, section: str | None = None) -> int:
    return sum(1 for row in rows if cells(row)[4] == state and (section is None or cells(row)[5] == section))


def entries(doc: Doctor, found: memory.Located) -> None:
    mem = found.path
    if found.note:
        doc.warn(found.note, "point the '- conventions:' line under ## Memory in council.config.md at %s"
                 % (mem[len(doc.root) + 1:] if mem.startswith(doc.root + "/") else mem))
    rows = memory.rows(mem)
    if not rows and memory.idlines(mem) > 0:
        doc.warn("memory (%s) names entry ids, but no entry could be read — nothing in it reaches a seat or a builder"
                 % mem, "write each entry as a heading (### AP-1: title) or a bullet (- **AP-1 — title** …), as "
                 + TEMPLATE)
    unknown = _count(rows, "unknown")
    if unknown:
        doc.warn("%d memory entr(ies) are unrecognized or incomplete, so they never reach a brief (council memory "
                 "lists them)" % unknown, "complete observed failures, move settled rules under their proper "
                 "section, or retire entries that no longer hold")
    skipped = bytewise.shown(memory_entries.skipped(where.native(mem)))
    if skipped:
        doc.warn("memory has line(s) that open like an entry but are not read, so they reach no brief: %s" % skipped,
                 "write each as a heading (### AP-1: title) or a bullet (- **AP-1 — title** …), as "
                 "references/templates/conventions.md shows")
    retired = _count(rows, "off", "marked retired")
    if retired:
        doc.warn("%d memory entr(ies) under a settled section are marked retired, so no brief sees them (council "
                 "memory lists them)" % retired,
                 "if they still hold, drop the retired mark; if not, move them under ## Retired")
    if found.alt:
        doc.warn("a second memory file, %s, holds %d entries the council never reads (it reads %s)"
                 % (found.alt, found.alt_n, mem), "merge the two, or point the '- conventions:' line under ## Memory "
                 "in council.config.md at the one to keep")
    said(doc, rows, mem)
    size(doc, rows, mem)


def said(doc: Doctor, rows: list[str], mem: str) -> None:
    """What council memory check and council memory say, counted."""
    from council.commands import memory as command
    from council.commands import memory_check
    top = doc.home[:doc.home.rfind("/")]
    audit = memory_audit.audit(rows, doc.home, top, mem)
    found = command.Memory(doc.home, top, mem, rows, audit, memory.served(rows, audit) if audit else rows)
    checked = memory_check.checked(found)[0]
    stale = sum(1 for line in checked if line.startswith("STALE"))
    unsupported = len({line.split()[1] for line in checked if line.startswith("UNSUPPORTED") and len(line.split()) > 1})
    evidence = sum(1 for line in checked if line.startswith("EVIDENCE"))
    if stale:
        doc.warn("%d memory anchor(s) point at code that moved or no longer exists" % stale,
                 "council memory check lists them; propose re-anchoring or retiring each at the next Learn")
    if unsupported:
        doc.warn("%d observed failure(s) in memory are no longer served: their evidence is gone or no longer shows "
                 "their verdict" % unsupported, "council memory check lists them; propose re-anchoring the evidence "
                 "or retiring each at the next Learn")
    if evidence:
        doc.warn("%d piece(s) of observed-failure evidence can't be found or cite lines their file doesn't have"
                 % evidence, "council memory check lists them; re-anchor them to files that still hold the evidence")
    orphans = sum(1 for line in command.indexed(found) if "matches no file, seat or mode" in line)
    if orphans:
        doc.warn("%d memory scope item(s) match no file, seat or mode (an entry still reaches a brief through its "
                 "other scope items, if it has any)" % orphans, "council memory lists them — correct each path or "
                 "slug, or drop the ones whose folder is gone")


def size(doc: Doctor, rows: list[str], mem: str) -> None:
    try:
        with open(where.native(mem), "rb") as stream:
            data = stream.read()
    except OSError:
        data = b""
    if len(data) > READ_EVERY_RUN:
        doc.warn("memory is %d KB — past the ~25 KB every run reads" % (len(data) // 1024),
                 "at the end of the next run, propose a consolidation (merge duplicates, retire superseded entries)")
    waiting = sum(1 for line in bytewise.records(bytewise.read(data)) if line.startswith("- PROPOSED"))
    waiting += sum(1 for row in rows
                   if cells(row)[4] == "off" and re.match(r"[#* ]*propos", bytewise.lower(cells(row)[5])))
    if waiting:
        doc.warn("%d memory proposal(s) await the user's yes/no" % waiting, "raise them at the next natural pause")
