"""A failed gate, said: why it failed in a line, the lines of its output that show it, and — when the gate has a
baseline in this run — which failing tests are new, so a red the untouched code already had is not taken for the
change's."""
from __future__ import annotations

import os
import re
from pathlib import Path

from council.commands import cli, gate_output
from council.commands.gate_run import Call, Result, event, qname
from council.records import gates, verdicts


def said(call: Call, name: str, result: Result, secs: int, info: tuple, content: str) -> bool:
    """Say why the gate failed; True when it names only the tests that failed at the baseline. info is
    (limit, where the limit came from, timed out, cmd ran nothing, its baseline was kept by this run)."""
    most, why, timed_out, never, fresh = info
    code, out = result.code, Path(call.run, "gates", gates.slug(name) + ".txt").as_posix()
    if code == 97:
        cli.say("gate %s: could not enter the code root: %s" % (name, call.top))
    if timed_out:                              # a hang: what it was doing last, and no baseline to compare
        cli.say("gate %s: TIMED OUT after %ss — stopped at its time limit, %ss (%s), with every process it started. "
                "A hang is no pass and no proof; if it truly needs longer: council gate %s --timeout <seconds>, or a "
                'longer "- gate time limit:" under Run preferences in the config — full output: %s'
                % (name, secs, most, why, qname(name), out))
        kept = [line for line in gate_output.lines(content)
                if not line.startswith("council: TIMED OUT") and line.strip(gate_output.SPACE)]
        indent(kept[-8:], "    ")
        event(call.run, name, "failed", "exit=%d;seconds=%d;empty=0;timed_out=1" % (code, secs),
              "gate failed, and its event was not recorded")
        return False
    module = gate_output.missing_module(content) if code == 1 else ""
    if never:
        cli.say('gate %s: FAIL — cmd opened its prompt and ran nothing (%ss): write its switch as //c, e.g. cmd //c '
                '"<command>" — full output: %s' % (name, secs, out))
    elif code == 127:                          # the shell's "command not found": nothing was checked
        cli.say("gate %s: could not run (exit 127, %ss) — a command it calls was not found; install it, or fix the "
                "gate's command — full output: %s" % (name, secs, out))
    elif module:
        cli.say("gate %s: could not run (exit 1, %ss) — Python has no module %s; install it, or fix the gate's command "
                "— full output: %s" % (name, secs, module, out))
    else:
        cli.say("gate %s: FAIL (exit %d, %ss) — full output: %s" % (name, code, secs, out))
    hits = ["%d:%s" % (n, line) for n, line in enumerate(gate_output.lines(content), 1) if _HITS.search(line)][:12]
    indent(hits or gate_output.tail(content, 8), "    ")
    same = False
    baseline = Path(call.run, "gates", "baseline", gates.slug(name))
    if not fresh and Path(baseline.as_posix() + ".txt").is_file():
        same = compare(baseline, content)
    event(call.run, name, "failed", "exit=%d;seconds=%d;empty=0" % (code, secs),
          "gate failed, and its event was not recorded")
    return same


_HITS = re.compile(r"error|fail|exception|traceback|assert|panic|cannot|not found|undefined", re.IGNORECASE)


def indent(lines: list[str], pad: str) -> None:
    """Lines of the output, as the helper's clip (an awk) printed them: Git Bash's awk reads in text mode, so on
    Windows a line's closing CR is gone."""
    for line in lines:
        cli.say(pad + gate_output.clip(line[:-1] if os.name == "nt" and line.endswith("\r") else line, 220))


def compare(baseline: Path, content: str) -> bool:
    """It may have been red before the change too: say what is new. True when no new failing test is named."""
    shown = "gates/baseline/%s.txt" % baseline.name
    seen = gate_output.failure_ids(gate_output.text(baseline.as_posix() + ".txt"))
    now = gate_output.failure_ids(content)
    if verdicts.number(baseline.as_posix() + ".json", "exit") == "0":  # green at the baseline: nothing old to subtract
        cli.say("    this gate passed at the baseline (%s), so every failure here is new" % shown)
    elif now and seen:
        new = [test for test in now if test not in seen][:12]
        if not new:
            cli.say("    the same test(s) are failing as at the baseline (%s) — no new one is named" % shown)
            return True
        cli.say("    failing now and not at the baseline (%s):" % shown)
        indent(new, "      ")
    elif now:
        cli.say("    the baseline's output names no failing test, so nothing can be compared — read %s next to this "
                "one yourself" % shown)
    else:
        cli.say("    this output names no failing test, so nothing can be compared — read it next to %s yourself"
                % shown)
    return False
