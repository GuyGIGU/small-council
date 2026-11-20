"""council state [key=value ...]: the header, or every word checked and then written by state_write.change."""
from __future__ import annotations

import re
import time
from pathlib import Path

from council.commands import cli, closed, nudges, plan, resolve
from council.records import bytewise, restore, stages, state, state_write, tasks

STATUSES = ("in-progress", "paused", "complete", "abandoned")
PLANNED = ("build", "work", "judge", "challenge", "deliver", "learn")   # need a valid plan
BLANK = " \t\n\v\f\r"
BACKUP = "backup"        # restore=: a build outside git (the owner declined git init) copies files instead


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
    if "phase=work" in words and changed.phase == "work":
        _unbriefed(run)
    return 0


def _unbriefed(run: Path) -> None:
    """On the step into Work, before any seat is dispatched: a warning on stderr for each of the user's decisions the
    brief does not carry (unbriefed). A brief it can't read says nothing."""
    from council.records import run_files         # only the step into Work reads the brief
    brief = run / run_files.BRIEF
    try:
        lines = unbriefed(run, brief) if brief.is_file() else []
    except OSError:
        lines = []
    for line in lines:
        cli.warn(line)


def unbriefed(run: Path, brief: Path) -> list[str]:
    """A line for each decision of the whole run's (a task's own goes to its task's orders) recorded in or before the
    minute brief.md was last written, whose words the brief does not carry. A decision keeps only its minute, so one
    in the brief's own minute counts: a warning costs a look, a miss a seat briefed without the user's word. Both
    sides as the quote check folds them (request.fold), every run of blanks and line breaks one space, lower case: a
    wrapped line, curly quotes or a capital still match; a paraphrase does not (D7)."""
    from council.commands import gate_output      # read only here, on the step into Work (D34)
    from council.records import paths, redact, request

    def plain(text: str) -> str:
        return re.sub(r"\s+", " ", request.fold(text)).strip().lower()

    written = time.strftime("%Y-%m-%d %H:%M", time.localtime(brief.stat().st_mtime))
    carried = plain(redact.said(paths.text_of(brief, run)))      # redacted as the decision's words were
    out = []
    for entry in state.decisions(state.text(run)):
        said = state.decision(entry)
        if said.task is not None or not said.minute or said.minute > written or not plain(said.words):
            continue
        if not request.found(carried, plain(said.words)):
            out.append("state: WARNING brief.md (written %s) does not carry the user's decision of %s, \"%s\" — the "
                       "seats would be briefed without it: quote it word for word in the brief before you dispatch"
                       % (written, said.minute, gate_output.clip(said.words, 100)))
    return out


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


def _undoable(run: Path, backup_now: bool) -> None:
    """A build starts only once it can be undone: its restore point (restore.md), or, outside git, the backup copy
    the build page names, recorded as restore=backup (now or before)."""
    if backup_now or restore.read(run) is not None or resolve.field(run, "restore") == BACKUP:
        return
    raise cli.Refusal("phase=build needs this run's restore point first, so the whole build can be undone — next: "
                      "council restore point (outside git, once the owner declines `git init`: council state "
                      "restore=backup, then copy each file to %s/backup/<path> before its first change)"
                      % run.as_posix())


def _outside_git(run: Path) -> None:
    """restore=backup stands in for the restore point only where git can't take one: a code root in git is refused."""
    from council.commands import restore as restoring     # only restore= asks git
    top = restoring.in_git(run)
    if top:
        raise cli.Refusal("restore=backup is for a code root outside git, and %s is in git, so its restore point can "
                          "be taken — next: council restore point" % Path(top).as_posix())


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
        if key in state_write.OWNED:
            raise cli.Refusal("%s= %s" % (key, state_write.OWNED[key].replace("<folder>", run.name)))
        if key == "decision" and not value.strip(BLANK):
            raise cli.Refusal("decision= takes the user's words — their ruling or go-ahead, as they said it")
        if key == "skip" and not value.strip(BLANK):
            raise cli.Refusal('skip= takes why a stage is skipped, in words: council state phase=<stage> skip="<why>"')
        if key == "skip":
            gave_skip, skip = True, value.replace(";", ",").replace("\r", " ").replace("\n", " ")
        if key == "phase":
            closed.refuse_old(run, "advanced")
        if key == "phase" and not stages.name_ok(value, mode):
            raise cli.Refusal("phase=%s is not a stage — use one of convene, prepare, work, judge, challenge, "
                              "deliver, learn, or build in a build (lower case)" % value)
        if key == "restore" and value != BACKUP:
            raise cli.Refusal("restore= takes backup only: council state restore=backup records that the code root "
                              "is not in git and the owner declined `git init` — otherwise: council restore point")
        if key == "restore":
            _outside_git(run)
        to = value if key == "phase" else to
        if key == "phase" and value in PLANNED:
            plan.require(run, "advance to " + value)
        if key == "phase" and value == "build" and mode == "council-implement":
            _undoable(run, "restore=" + BACKUP in words)
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
