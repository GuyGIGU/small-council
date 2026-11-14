"""council memory propose | accept | reject: the three ways the memory file is written. propose drafts an observed
failure from one verified record of a run — a claim a blind verifier REFUTED or MISCITED (claims.jsonl), or a build
task's failed gate trail (repairs.jsonl) — and files it under ## Proposed; it is refused unless, once the user says
yes, it would be served. accept files the user's answer under Observed Failures with the date and their words; reject
moves it to ## Rejected as one line. The drafts and moves are scripts/memory.py's, run in this process; the file is
replaced only through records/memory.py's guarded replace, and secret-looking strings are redacted first."""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import time
from pathlib import Path

from council.commands import cli, resolve, script
from council.commands.memory import Memory
from council.records import bytewise, events, memory, redact
from council.records import home as where
from council.records.memory_entries import cells


def main(args: cli.Args, found: Memory, sub: str, words: list[str]) -> int:
    if sub == "propose":
        return propose(args, found, words[0], words[1])
    return answer(args, found, sub, words[0])


def _faults() -> tuple[type[BaseException], ...]:
    module = script.load("memory")
    return (module.MemoryError_, module.evidence.EvidenceError, module.repair.RepairError, OSError, UnicodeError,
            ValueError)


def _script(words: list[str]) -> tuple[int, str]:
    """scripts/memory.py run here: its exit code and what it printed; what it said on stderr is shown."""
    code, said, errors = script.captured("memory", words, _faults())
    if errors:
        cli.warn(errors.rstrip("\n"))
    return code, said


class _Folder:
    """A temporary folder, removed on the way out."""

    def __enter__(self) -> str:
        try:
            self.path = Path(tempfile.mkdtemp()).as_posix()
        except OSError:
            raise cli.Refusal("cannot make a temporary folder") from None
        return self.path

    def __exit__(self, *_: object) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


def _redacted(source: bytes, target: str) -> int:
    shown, count = redact.redact(source)
    with open(target, "wb") as stream:
        stream.write(shown)
    return count


def propose(args: cli.Args, found: Memory, kind: str, source: str) -> int:
    if os.path.islink(where.native(found.mem)):
        raise cli.Refusal("the memory file is a link — write the proposal into the file it points to by hand")
    run = resolve.run_folder(args)
    with _Folder() as tmp:
        with open(tmp + "/scope", "w", encoding="utf-8", errors="surrogateescape", newline="\n") as stream:
            stream.write(args.value("scope") + "\n")
        code, raw = _script(["draft", kind, source, "--run", run.as_posix(), "--top", found.top, "--scope-file",
                             tmp + "/scope", "--today", time.strftime("%Y-%m-%d")])
        if code:
            return 2
        red = _redacted(raw.encode("utf-8", "surrogateescape"), tmp + "/draft")
        with open(tmp + "/draft", "rb") as stream:
            draft = stream.read()
        with open(tmp + "/probe", "wb") as stream:
            stream.write(b"# probe\n## Observed Failures (F)\n" + draft)
        why = memory.would_serve(tmp + "/probe", "F-0", found.home, found.top, found.mem)
        if why:
            raise cli.Refusal("nothing drafted — once accepted it would not be served: %s" % bytewise.shown(why))
        _copy(found.mem, tmp + "/before")
        code, said = _script(["insert", "--memory", tmp + "/before", "--block", tmp + "/draft", "--out",
                              tmp + "/after"])
        if code:
            return 2
        entry = bytewise.text(said.rstrip("\n"))
        refused = memory.replace(found.mem, tmp + "/before", tmp + "/after", entry, "proposed", found.home, found.top)
        if refused:
            cli.warn("council: " + refused)
            return 1
    _event(run, bytewise.shown(entry), kind, source)
    if red:
        cli.say("memory: %d secret-looking string(s) in the draft were redacted" % red)
    cli.say("memory: drafted %s under ## Proposed from %s %s of %s — no brief reads it until the user says yes"
            % (bytewise.shown(entry), kind, source, run.name))
    cli.say("→ show the user the entry, then record their answer in their words:")
    cli.say("   yes: council memory accept %s --user-said \"<their words>\"   no: council memory reject %s "
            "--user-said \"<their words>\"" % (bytewise.shown(entry), bytewise.shown(entry)))
    return 0


def _copy(mem: str, target: str) -> None:
    try:
        shutil.copyfile(where.native(mem), target)
    except OSError:
        raise cli.Refusal("cannot copy %s" % mem) from None


def _event(run: Path, entry: str, kind: str, source: str) -> None:
    try:
        events.append(run, "memory.proposed", entry, kind, "source=" + source)
    except events.EventError as fault:
        cli.warn("council: %s" % fault)
        cli.warn("council: %s is drafted, but its event could not be recorded" % entry)


def answer(args: cli.Args, found: Memory, sub: str, entry: str) -> int:
    if not re.fullmatch(r"F-[0-9]+", entry):
        raise cli.Refusal("memory %s takes an observed-failure id such as F-3" % sub)
    if os.path.islink(where.native(found.mem)):
        raise cli.Refusal("the memory file is a link — move the entry in the file it points to by hand")
    want = bytewise.text(entry)
    mine = [cells(row) for row in found.entries if cells(row)[0] == want]
    waiting = [c for c in mine if c[4] == "off" and re.match(r"[#* ]*propos", bytewise.lower(c[5]))]
    if len(mine) != 1 or len(waiting) != 1:
        raise cli.Refusal("%s is not one proposal awaiting the user's answer (none, or its id is shared) — council "
                          "memory shows where it is" % entry)
    with _Folder() as tmp:
        _copy(found.mem, tmp + "/before")
        said = re.sub(r"[\r\n\t]", " ", args.value("user-said")) + "\n"   # one line, so a split secret is still caught
        _redacted(said.encode("utf-8", "surrogateescape"), tmp + "/said")
        target, state = ("observed", "observed") if sub == "accept" else ("rejected", "gone")
        code, _ = _script(["move", entry, "--to", target, "--memory", tmp + "/before", "--said", tmp + "/said",
                           "--today", time.strftime("%Y-%m-%d"), "--out", tmp + "/after"])
        if code:
            return 2
        refused = memory.replace(found.mem, tmp + "/before", tmp + "/after", want, state, found.home, found.top)
        if refused:
            cli.warn("council: " + refused)
            return 1
    if sub == "accept":
        cli.say("memory: %s accepted with the user's words — runs whose files, seats or mode match its scope get it, "
                "as history to check, never as a rule" % entry)
    else:
        cli.say("memory: %s rejected — one line under ## Rejected keeps the user's words and its evidence, so it is "
                "never proposed again" % entry)
    return 0
