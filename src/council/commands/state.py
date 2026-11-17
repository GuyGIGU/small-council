"""council state [key=value ...]: the header, or every word checked and then written by state_write.change."""
from __future__ import annotations

import re
from pathlib import Path

from council.commands import cli, nudges, plan, resolve
from council.records import bytewise, stages, state, state_write, tasks

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
        note = _checked(run, words)
        changed = state_write.change(run, _scoped(run, words), phase_note=note)
    except state_write.StateError as failure:
        raise cli.Refusal(str(failure)) from None
    cli.say("state: phase %s · %s · %s" % (changed.phase, changed.status, run.name))
    if changed.waiting and changed.waiting != changed.waited:
        nudges.waiting_nudge(run, bool(args.value("run")))
    return 0


def _header(run: Path) -> None:
    """The lines above the first heading, from the file's own bytes (a BOM and a stray byte kept, a CR before a
    newline dropped); a state the guarded read leaves out (state.unread) is refused, never printed."""
    why = state.unread(run, "council state does not print it")
    if why:
        raise cli.Refusal(why)
    for line in bytewise.records(state.path(run).read_bytes().decode("utf-8", "surrogateescape")):
        if line.startswith("## "):
            return
        cli.say(line)


def _scoped(run: Path, words: list[str]) -> list[str]:
    """The words with a decision's task= as its number (task-3, T3 or 3), once it names a task of the build's plan;
    task= with no decision=, or more than once, is refused."""
    given = [word for word in words if word.startswith("task=")]
    if not given:
        return words
    how = "council state decision=\"<the user's words>\" task=<n>"
    if not any(word.startswith("decision=") for word in words):
        raise cli.Refusal("task= scopes the user's decision to one task, so it goes with decision=: " + how)
    if len(given) > 1:
        raise cli.Refusal("one task= per call: a decision is the whole run's or one task's — " + how)
    number = tasks.number(given[0][len("task="):])
    if number is None:
        raise cli.Refusal("task= takes a task of the build's plan (task-3, T3 or 3), not '%s': %s" % (
            given[0][len("task="):], how))
    from council.commands import task_slice      # the plan, only when a decision names a task
    named, content = task_slice.plan(run, "state decision= task=")
    listed = [entry.number for entry in tasks.read(content)]
    if number not in listed:
        raise cli.Refusal("%s has no task %d — its tasks: %s; record it for one of them, or for the whole run with no "
                          "task=" % (named, number, ", ".join("task-%d" % n for n in listed) or "none"))
    return [word for word in words if not word.startswith("task=")] + ["task=%d" % number]


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
