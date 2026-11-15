"""council state [key=value ...]: the header, or every word checked and then written by state_write.change."""
from __future__ import annotations

import re
from pathlib import Path

from council.commands import cli, nudges, plan, resolve
from council.records import bytewise, stages, state, state_write

STATUSES = ("in-progress", "paused", "complete", "abandoned")
PLANNED = ("brief", "build", "work", "collect", "judge", "challenge", "deliver", "learn")   # need a valid plan
BLANK = " \t\n\v\f\r"


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "state")
    run = resolve.run_folder(args)
    if not words:
        _header(run)
        return 0
    try:
        changed = state_write.change(run, words, phase_note=_checked(run, words))
    except state_write.StateError as failure:
        raise cli.Refusal(str(failure)) from None
    cli.say("state: phase %s · %s · %s" % (changed.phase, changed.status, run.name))
    if changed.waiting and changed.waiting != changed.waited:
        nudges.waiting_nudge(run, bool(args.value("run")))
    return 0


def _header(run: Path) -> None:
    """The lines above the first heading, as awk prints them (a BOM kept; on Windows a line's CR dropped)."""
    for line in bytewise.records(state.path(run).read_bytes().decode("utf-8", "surrogateescape")):
        if line.startswith("## "):
            return
        cli.say(line)


def _checked(run: Path, words: list[str]) -> str:
    """Refuse a word the change would not take; the phase event's skip note (';skipped=…;reason=…') or ''."""
    mode, to, skip, gave_skip = resolve.field(run, "mode"), "", "", False
    for word in words:
        key, equals, value = word.partition("=")
        if not equals:
            raise cli.Refusal("expected key=value, got: " + word)
        if not re.fullmatch("[a-z0-9-]+", key):
            raise cli.Refusal("bad key: %s (lowercase letters, digits, dashes)" % key)
        if key == "status" and value not in STATUSES:
            raise cli.Refusal("status must be in-progress, paused, complete or abandoned")
        if key == "status" and value == "complete":
            raise cli.Refusal("status=complete is the close's to set — close the run with: council run close")
        if key == "closed":
            raise cli.Refusal("closed= is the close's own stamp — close the run with: council run close")
        if key == "decision" and not value.strip(BLANK):
            raise cli.Refusal("decision= takes the user's words — their ruling or go-ahead, as they said it")
        if key == "skip" and not value.strip(BLANK):
            raise cli.Refusal('skip= takes why a stage is skipped, in words: council state phase=<stage> skip="<why>"')
        if key == "skip":
            gave_skip, skip = True, value.replace(";", ",").replace("\r", " ").replace("\n", " ")
        if key == "phase" and not stages.name_ok(value, mode):
            raise cli.Refusal("phase=%s is not a stage — use one of convene, prepare, assign, brief, work, collect, "
                              "judge, challenge, deliver, learn, or build in a build (lower case)" % value)
        to = value if key == "phase" else to
        if key == "phase" and value in PLANNED:
            plan.require(run, "advance to " + value)
    if not to:
        if gave_skip:
            raise cli.Refusal('skip= goes with the phase= it explains: council state phase=<stage> skip="<why>"')
        return ""
    skipped = stages.skipped(run, resolve.field(run, "phase"), to)
    if skipped and not gave_skip:
        how = ('A build stopped blocked skips it on purpose: council state phase=deliver skip="blocked: task <n>"'
               if (mode, skipped[0]) == ("council-implement", "challenge")
               else 'To skip on purpose, say why: council state phase=%s skip="<why>"' % to)
        raise cli.Refusal("phase=%s would skip %s, which a %s run enters in turn — next: council state phase=%s. %s"
                          % (to, ", ".join(skipped), mode, skipped[0], how))
    if gave_skip and not skipped:
        raise cli.Refusal("phase=%s skips no stage this run must enter, so there is nothing for skip= to explain — "
                          "drop it" % to)
    return ";skipped=%s;reason=%s" % (",".join(skipped), skip) if skipped else ""
