"""Run one gate: its full output to <run>/gates/<name>.txt, its verdict to <name>.json, one gate.finished event.

In a baseline set a gate's first output is also kept as gates/baseline/<name>.txt, so a later failure can be told
apart from one the untouched code already had. Exit 0 with nothing behind it (no file matched, no test ran, a
test gate that printed nothing) is said, never a plain pass; a hang stopped at its time limit is no pass and no
proof."""
from __future__ import annotations

import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import NamedTuple

from council.commands import cli, gate_exec, gate_output, resolve
from council.records import config, events, gates

HITS = re.compile(r"error|fail|exception|traceback|assert|panic|cannot|not found|undefined", re.IGNORECASE)
CMD_SWITCH = re.compile(r"(^|[ \t\n\v\f\r;&|(])([cC][mM][dD](\.[eE][xX][eE])?)([ \t\n\v\f\r]+)/([cCkK])([ \t\n\v\f\r]|$)")
WINDOWS_BASH = os.name == "nt" or sys.platform.startswith(("cygwin", "msys"))


class Call(NamedTuple):
    """What one `council gate` call runs with."""

    run: str               # the run folder, written as the helper writes it (C:/… on Windows)
    home: str
    top: str               # the code root
    given: bool            # a command was given after --
    timeout: int | None    # --timeout, in seconds
    proof: str             # --proof change|preserve, or ''
    baseline: bool         # a baseline set: a gate's first output is kept


class Result(NamedTuple):
    code: int
    empty: int             # 1: 0 files matched · 2: its output says no test ran · 3: a test gate printed nothing
    same: bool             # it failed, naming only the tests that failed at the baseline


def qname(name: str) -> str:
    """A gate name as the user would type it back: quoted when it holds a space or anything unusual."""
    return '"%s"' % name if re.search(r"[^A-Za-z0-9._-]", name) else name


def json_esc(value: str) -> str:
    """The helper's json_esc: \\ and " escaped, tab, CR and newline as spaces."""
    return re.sub("[\t\r\n]", " ", value.replace("\\", "\\\\").replace('"', '\\"'))


def windows_command(command: str) -> str:
    """On Git Bash a lone /c is turned into a drive path before cmd sees it, so cmd opens a prompt and exits 0
    without running anything; written //c it survives as /c. Nothing else in the command is touched."""
    return CMD_SWITCH.sub(lambda m: m.group(1) + m.group(2) + m.group(4) + "//" + m.group(5) + m.group(6), command)


def recorded(path: str, key: str) -> str:
    """A verdict's number, as the helper's sed read it: the last `"key": N` on the first line that has one."""
    pattern = re.compile(r'.*"%s": *(%s)' % (key, "-?[0-9]+" if key == "exit" else "[0-9]+"))
    for line in gate_output.lines(gate_output.text(path)):
        found = pattern.match(line)
        if found:
            return found.group(1)
    return ""


def limit(call: Call, name: str) -> tuple[int, str]:
    """This gate's time limit in seconds and where it came from: --timeout; else the largest of three times its
    own green baseline in this run, the config's `- gate time limit:` and 120 s; with neither, 9 minutes for a
    check given its command and 30 for a configured gate."""
    if call.timeout is not None:
        return call.timeout, "set by --timeout"
    baseline = gates.files(Path(call.run), gates.slug(name), baseline=True)[0].as_posix()
    secs = recorded(baseline, "seconds") if recorded(baseline, "exit") == "0" else ""
    seconds, raw = config.gate_time_limit(call.home)
    bad = " (the config's gate time limit '%s' is not a time)" % raw if raw and seconds is None else ""
    if not secs and seconds is None:
        if call.given:
            return 540, "the default for a check given its command, with no green baseline of its own" + bad
        return 1800, "the default, with no green baseline to go by" + bad
    most, why = 120, "the 120s floor"
    if secs:
        why = "3× its %ss green baseline" % secs
        if int(secs) * 3 >= 120:
            most = int(secs) * 3
        else:
            why += ", raised to the 120s floor"
    if seconds is not None and seconds > most:
        most, why = seconds, "the config's gate time limit"
    return most, why + bad


def event(run: str, name: str, value: str, detail: str, said: str) -> None:
    """One gate event; a failure to record it is said on stderr and never changes the gate's result."""
    try:
        events.append(Path(run), "gate." + ("invalidated" if value == "invalid" else "finished"), name, value, detail)
    except events.EventError as failure:
        cli.warn("council: " + str(failure).replace(str(events.path(Path(run))), run + "/events.tsv"))
        cli.warn("council: " + said)


def run_gate(call: Call, name: str, command: str) -> Result:
    """Run one gate and say its result; Result.code is its exit code."""
    base = Path(call.run, "gates", gates.slug(name))
    out, verdict = base.as_posix() + ".txt", base.as_posix() + ".json"
    os.makedirs(str(base.parent), exist_ok=True)
    most, why = limit(call, name)
    started = int(time.time())
    code, timed_out = gate_exec.execute(call.top, resolve.field(Path(call.run), "base"),
                                        windows_command(command) if WINDOWS_BASH else command, out, most)
    secs = int(time.time()) - started
    note, empty, zero = "", 0, ""
    if timed_out:                  # said in its own output and verdict, so no reader takes it for a check
        with open(out, "ab") as handle:
            handle.write(("\ncouncil: TIMED OUT after %ss — stopped at its time limit, %ss (%s), with every process it "
                          "started\n" % (secs, most, why)).encode("utf-8", "surrogateescape"))
        note = ', "note": "TIMED OUT after %ss (time limit %ss: %s)", "timed_out": true' % (secs, most, json_esc(why))
    content = gate_output.text(out)
    never = code == 0 and gate_output.never_ran(content)
    if never:
        code, note = 1, ', "note": "cmd opened its prompt and ran nothing"'
    if code == 0:
        empty, zero, note = _nothing(name, command, content)
    if call.proof:
        note += ', "proof": "%s"' % call.proof
    _write(verdict, '{"gate": "%s", "command": "%s", "exit": %d, "seconds": %d, "when": "%s", "limit": %d%s}\n'
           % (json_esc(name), json_esc(command), code, secs, time.strftime("%Y-%m-%d %H:%M:%S"), most, note))
    fresh = call.baseline and _keep_baseline(call.run, base, out, verdict)
    if code == 0:
        return _passed(call, name, secs, empty, zero)
    from council.commands import gate_failed
    same = gate_failed.said(call, name, Result(code, 0, False), secs, (most, why, timed_out, never, fresh), content)
    return Result(code, 0, same)


def _nothing(name: str, command: str, content: str) -> tuple[int, str, str]:
    """(empty, the no-test line, the verdict note) for a gate that exited 0."""
    if any(line.startswith("changed: no files matched") for line in gate_output.lines(content)):
        return 1, "", ""
    zero = gate_output.zero_tests(content)
    if zero:
        return 2, zero, ', "note": "exit 0, but its output says no test ran"'
    if gate_output.blank(content) and gate_output.is_test_gate(name, command):
        return 3, "", ', "note": "exit 0, but it printed nothing"'
    return 0, "", ""


def _write(path: str, line: str) -> None:
    with open(path, "wb") as handle:
        handle.write(line.encode("utf-8", "surrogateescape"))


def _keep_baseline(run: str, base: Path, out: str, verdict: str) -> bool:
    """The first output of this gate in a baseline set becomes its baseline; True when it was kept now."""
    kept = Path(run, "gates", "baseline", base.name)
    if Path(kept.as_posix() + ".txt").is_file():
        return False
    try:
        os.makedirs(str(kept.parent), exist_ok=True)
        shutil.copyfile(out, kept.as_posix() + ".txt")
        shutil.copyfile(verdict, kept.as_posix() + ".json")
    except OSError:
        return False
    return True


def _passed(call: Call, name: str, secs: int, empty: int, zero: str) -> Result:
    said = {1: "pass — but nothing to check (0 files matched)",
            2: 'pass — but nothing ran: its output says "%s" (exit 0, %ss)' % (zero, secs),
            3: "pass — but nothing ran that it shows: it printed nothing (exit 0, %ss)" % secs}
    cli.say("gate %s: %s" % (name, said.get(empty, "pass (exit 0, %ss)" % secs)))
    event(call.run, name, "passed", "exit=0;seconds=%d;empty=%d" % (secs, 1 if empty else 0),
          "gate passed, but its event was not recorded")
    return Result(0, empty, False)
