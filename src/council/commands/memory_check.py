"""council memory check: the anchors the code no longer has, and the observed failures whose evidence no longer
supports them. One pass sees what each anchor names (records/memory_anchors.py), then one search finds every name at
once — a search per anchor costs minutes on a memory with hundreds of them. Exit 1 when anything is stale or
unsupported."""
from __future__ import annotations

import os
import re

from council.commands.memory import Memory, say_all
from council.commands.memory_tree import Tree, line_counts
from council.records import bytewise, citations, memory, memory_anchors
from council.records import home as where
from council.records.memory_entries import cells


def _words(text: str) -> list[str]:
    """A value split as bash splits ${x//[.:#]/ } unquoted: at dots, colons and hashes, and at blanks."""
    return re.sub("[.:#]", " ", text).split()


class Anchors:
    """Every anchor row with the file it resolves to, and what the one search must look for."""

    def __init__(self, tree: Tree, entries: list[str]) -> None:
        self.rows: list[str] = []
        self.names: set[str] = set()
        self.fsnames: set[str] = set()
        self.fsfiles: set[str] = set()
        self.files: set[str] = set()
        for line in memory_anchors.rows(entries):
            entry, item, kind, p, extra = memory_anchors.read_fields(line, 5)
            if entry:
                self.add(tree, entry, item, kind, p, extra)

    def add(self, tree: Tree, entry: str, item: str, kind: str, p: str, extra: str) -> None:
        f = tree.path(p) if kind in ("C", "F", "N", "X") else ""
        if kind == "X" and not f:
            self.names.add(p)
        elif kind == "S":
            self.names.update(_words(p))
        elif kind == "C" and f:
            self.files.add(f)
        elif kind == "N" and f:
            self.fsfiles.add(f)
            self.fsnames.update(_words(extra))
        self.rows.append("\t".join((entry, item, kind, f or "-", p, extra or "-")))


def check(found: Memory) -> int:
    lines, code = checked(found)
    say_all(lines)
    return code


def checked(found: Memory) -> tuple[list[str], int]:
    """What council memory check says, and its exit code (doctor counts the same lines)."""
    out = list(memory.unread(found.mem))
    tree = Tree(found.top)
    n = sum(1 for row in found.entries if cells(row)[4] in ("settled", "observed"))
    anchors = Anchors(tree, found.entries)
    named = tree.find(anchors.names)
    named_in = tree.find_in(anchors.fsnames, anchors.fsfiles)
    counts = line_counts(found.top, anchors.files)
    stale, last = 0, ""
    for line in anchors.rows:
        entry, item, kind, f, p, extra = memory_anchors.read_fields(line, 6)
        if not entry:
            continue
        why = stale_why(found.top, (item, kind, f, p, "" if extra == "-" else extra), named, named_in, counts)
        if why and entry + "\t" + item != last:
            stale, last = stale + 1, entry + "\t" + item
            out.append(bytewise.shown("STALE  %s %s %s" % (entry, bytewise.EM, why)))
    if stale:
        out.append("→ at the next Learn, propose re-anchoring or retiring each stale entry — the user decides")
    out.append("memory check: %d stale anchor(s) across %d entries" % (stale, n))
    problems = evidence(found.audit, out)
    observed = sum(1 for row in found.entries if cells(row)[4] == "observed")
    if observed:
        if problems[0]:
            out.append("→ at the next Learn, propose re-anchoring each one's evidence to a file that still shows it, "
                       "or retiring it — the user decides")
        out.append("memory check: %d evidence problem(s) across %d observed failure(s), %d no longer served"
                   % (problems[0], observed, problems[1]))
    return out, 0 if stale == 0 and problems[0] == 0 else 1


def stale_why(top: str, anchor: tuple[str, str, str, str, str], named: set[str], named_in: set[tuple[str, str]],
              counts: dict[str, int]) -> str:
    """Why one anchor is stale; '' when the code still has what it names."""
    item, kind, f, p, extra = anchor
    gone = "anchor %s no longer exists" % item
    if kind == "C":
        if f == "-":
            return gone
        if os.path.isdir(where.native(top + "/" + bytewise.shown(f))):
            return "anchor %s: bad-line (a folder has no lines)" % item
        ln = counts.get(f, 0)
        if citations.ranges(extra, ln) is None:
            return "anchor %s: %s" % (item, citations.line_verdict(extra, ln))
        return ""
    if kind == "F" or (kind == "N" and f == "-"):
        return gone if f == "-" else ""
    if kind == "X":
        return gone if f == "-" and p not in named else ""
    if kind == "N":
        if any((f, part) not in named_in for part in _words(extra)):
            return "nothing in %s is named %s any more" % (f, extra)
        return ""
    if kind == "S" and any(part not in named for part in _words(p)):
        return "nothing in the code is named %s any more" % p
    return ""


def evidence(audit: list[str], out: list[str]) -> tuple[int, int]:
    """The audit's lines, added to out (fatal ones as UNSUPPORTED); (how many, how many entries no brief gets)."""
    k, unsupported = 0, []
    for line in audit:
        entry, kind, why = memory_anchors.read_fields(line, 3)
        if not entry:
            continue
        if kind == "fatal":
            out.append(bytewise.shown("UNSUPPORTED  %s %s %s; no brief gets it until this is fixed or it is retired"
                                   % (entry, bytewise.EM, why)))
            if entry not in unsupported:
                unsupported.append(entry)
        else:
            out.append(bytewise.shown("EVIDENCE  %s %s %s" % (entry, bytewise.EM, why)))
        k += 1
    return k, len(unsupported)
