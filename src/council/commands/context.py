"""council context build|show <seat>: a run-local, seat-specific context pack (scripts/context.py) at the level the
validated run plan gives the selected seat. It only supplements brief.md and never edits project guidance."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from council.commands import cli, event_note, resolve, script
from council.commands import plan as run_plan
from council.records import home as where
from council.records import plan, run_files

USAGES = {"build": "usage: council context build <seat> [--run <folder>] [--expand PATH ...]",
          "show": "usage: council context show <seat> [--run <folder>]"}


def main(args: cli.Args, words: list[str]) -> int:
    sub = words[0] if words else ""
    if sub not in USAGES:
        raise cli.Refusal("usage: council context build <seat> [--expand PATH ...] | context show <seat>")
    cli.takes_flags(args, "context " + sub, *(("expand",) if sub == "build" else ()))
    if len(words) != 2:
        raise cli.Refusal(USAGES[sub])
    seat = words[1]
    if seat in (".", "..") or not re.fullmatch(r"[A-Za-z0-9._-]+", seat):
        raise cli.Refusal("context seat must be a single slug (letters, digits, dot, underscore or dash)")
    run = resolve.run_folder(args)
    output = "%s/contexts/%s.md" % (run.as_posix(), seat)
    return build(run, seat, output, args.lists["expand"]) if sub == "build" else show(run, seat, output)


def build(run: Path, seat: str, output: str, expands: list[str]) -> int:
    if not plan.path(run).is_file():
        raise cli.Refusal("context build needs a run-plan.tsv with a selected seat; legacy runs cannot infer a "
                          "context level")
    if run_plan.check(run, quiet=True):
        raise cli.Refusal("context build needs a valid run plan — run: council run plan check --run " + run.name)
    if not plan.selected(run, seat):
        raise cli.Refusal("context build needs a selected seat in run-plan.tsv: " + seat)
    if not (run / run_files.BRIEF).is_file():
        raise cli.Refusal("context build needs the authoritative brief first: %s/%s"
                          % (run.as_posix(), run_files.BRIEF))
    rows = ((line.split("\t") + [""] * 4) for line in plan.text(run).split("\n"))
    level = next((row[3] for row in rows if row[:3] == ["context", seat, "level"]), "").replace("\r", "")
    if not level:
        raise cli.Refusal("context level is missing for selected seat " + seat)
    top = resolve.field(run, "code-root") or where.this_tree()
    try:
        os.makedirs(str(run / "contexts"), exist_ok=True)
    except OSError:
        raise cli.Refusal("cannot create %s/contexts" % run.as_posix()) from None
    words = ["--root", where.native(top), "--run", run.as_posix(), "--seat", seat, "--level", level, "--output", output]
    if script.run("context", words + [w for path in expands for w in ("--expand", where.native(path))]):
        cli.warn("council: context build failed; brief.md remains authoritative; any prior pack may be stale and "
                 "must not be dispatched")
        return 1
    metrics = output + ".metrics.tsv"
    if not (os.path.isfile(output) and os.path.isfile(metrics)):
        raise cli.Refusal("context provider returned without the pack and metrics sidecar")
    event_note.need(run, "context.built", seat, level, "expands=%d;metrics=%s" % (len(expands), metrics),
                    "context built, but its event could not be recorded")
    cli.say("context: " + output)
    cli.say("metrics: " + metrics)
    return 0


def show(run: Path, seat: str, output: str) -> int:
    metrics = output + ".metrics.tsv"
    if any(os.path.islink(path) for path in (str(run / "contexts"), output, metrics)):
        raise cli.Refusal("context show refuses a symlink in the generated pack path")
    if not os.path.isfile(output):
        raise cli.Refusal("context pack is missing for %s — run: council context build %s --run %s"
                          % (seat, seat, run.name))
    cli.say("context: " + output)
    if not os.path.isfile(metrics):
        cli.say("metrics: missing (rebuild the context pack to refresh its accounting)")
        return 0
    cli.say("metrics: " + metrics)
    sys.stdout.flush()
    sys.stdout.buffer.write(Path(metrics).read_bytes())
    return 0
