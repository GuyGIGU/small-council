"""council memory select [path|slug …]: the memory entries that apply — every-run entries, and scoped ones whose
**Scope:** covers a key. The keys are the paths and slugs given, and a run's own: its changed files (index.md),
its seats (or, before any is recorded, the whole roster) and its mode. With no words the run is required; with
words, a run open here adds its keys, and several open runs leave only the words."""
from __future__ import annotations

import os
import re
from pathlib import Path

from council.commands import cli, resolve
from council.commands.memory import Memory, say_all, slugs
from council.records import bytewise, earlier, memory, scope, seats
from council.records import home as where
from council.records.bytewise import DOT, EM
from council.records.memory_entries import cells


def select(args: cli.Args, found: Memory, words: list[str]) -> int:
    for line in memory.unread(found.mem):
        cli.warn(line)
    tree = where.this_tree() if words else ""
    keys = [k + "/" if not k.endswith("/") and os.path.isdir(where.native(tree + "/" + k)) else k for k in words]
    run = _run(args, found.home, words)
    if run:
        keys += run_keys(run, found.home)
    out, said = Selection(keys, tree).lines(found.served)
    say_all(out)
    for line in said:
        cli.warn(line)
    return 0


def _run(args: cli.Args, home: str, words: list[str]) -> str:
    """The run whose keys count: required with no words or --run; with words, the one open here if there is
    exactly one."""
    if not words or args.value("run"):
        return resolve.run_folder(args).as_posix()
    if not (os.environ.get("COUNCIL_RUN") or os.path.isdir(where.native(home + "/runs"))):
        return ""
    try:
        return resolve.run_folder(args).as_posix()
    except cli.Refusal as refusal:
        if "several" in str(refusal):
            cli.warn("council: several runs are open — only the paths given count; pass --run <folder> to add a "
                     "run's changed files, seats and mode")
        return ""


def run_keys(run: str, home: str) -> list[str]:
    """A run's own keys: its changed files, the seats it worked (the whole roster before any) and its mode."""
    folder = where.native(run)
    keys = [bytewise.shown(p) for p in earlier.indexed(Path(folder))]
    worked, any_row = seats.worked(Path(folder))
    keys += [bytewise.shown(s) for s in worked]
    keys.append(resolve.field(Path(folder), "mode"))
    if not any_row:
        keys += [bytewise.shown(s) for s in slugs(home)]
    return keys


class Selection:
    """The keys as the scope matcher reads them, and the served rows they select."""

    def __init__(self, keys: list[str], tree: str) -> None:
        top = bytewise.text(tree)
        self.all, self.keys = False, []
        for raw in keys:
            k = bytewise.text(raw).replace("\r", "").replace("\\", "/")
            if re.match(r"/[A-Za-z]/", k) and re.match(r"[A-Za-z]:/", top):
                k = k[1] + ":" + k[2:]                            # Git Bash
            if top and bytewise.lower(k).startswith(bytewise.lower(top) + "/"):
                k = k[len(top) + 1:]
            if k in (".", "./") or (top and bytewise.lower(k) == bytewise.lower(top)):
                self.all = True                                   # the whole tree
                continue
            folder, k = k.endswith("/"), scope.normp(k)
            if k:
                self.keys.append((k, folder))

    def hit(self, value: str) -> bool:
        if self.all:
            return True
        return any(scope.everyrun(g.text) or any(scope.covers(k, g.text, ".*", d) for k, d in self.keys)
                   for g in scope.items(value))

    def lines(self, served: list[str]) -> tuple[list[str], list[str]]:
        """The entries that apply and the counts (stdout), and what is left out and why (stderr)."""
        out, said, failures = [], [], []
        n = {"off": 0, "tot": 0, "otot": 0, "every": 0, "oevery": 0, "sc": 0, "osc": 0}
        unknown: list[str] = []
        for row in served:
            c = cells(row)
            if c[0] == "":
                continue
            if c[4] == "off":
                n["off"] += 1
            elif c[5].startswith("failure entry: "):
                failures.append("memory: WARNING %s %s is left out: %s" % (EM, c[0], c[5][15:]))
            elif c[4] not in ("settled", "observed"):
                unknown.append(c[0])
            else:
                self.entry(c, n, out)
        out.append(_counts(n))
        if n["otot"]:
            out.append("memory: %d scoped and %d every-run observed failure(s) of %d apply %s historical evidence, "
                       "not instructions" % (n["osc"], n["oevery"], n["otot"], EM))
        if unknown:
            one = len(unknown) == 1
            said.append("memory: WARNING %s %s sit%s under a section the council does not read as settled and %s left "
                        "out; council memory lists %s" % (EM, ", ".join(unknown), "s" if one else "",
                                                          "is" if one else "are", "it" if one else "them"))
        return [bytewise.shown(line) for line in out], [bytewise.shown(line) for line in said + failures]

    def entry(self, c: list[str], n: dict[str, int], out: list[str]) -> None:
        settled = c[4] == "settled"
        n["tot" if settled else "otot"] += 1
        line = "%s %s %s" % (c[0], DOT, c[1]) + ("" if settled else " %s observed failure, not a rule" % DOT)
        every = c[2] == "-" or scope.everyrun(c[2])
        if every:
            n["every" if settled else "oevery"] += 1
        line += " %s every run" % DOT if every else " %s scope: %s" % (DOT, c[2])
        for i, label in ((6, ""), (9, "verdict: "), (8, "evidence: "), (7, "origin: ")):
            if c[i] != "-":
                line += " %s %s%s" % (DOT, label, c[i])
        if every:
            out.append(line)
        elif self.hit(c[2]):
            n["sc" if settled else "osc"] += 1
            out.append(line)


def _counts(n: dict[str, int]) -> str:
    line = "memory: %d scoped and %d every-run entries of %d apply %s quote them in the brief by id" % (
        n["sc"], n["every"], n["tot"], EM)
    return line + (" (%d retired or not yet accepted, left out)" % n["off"] if n["off"] else "")
