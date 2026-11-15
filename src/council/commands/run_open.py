"""council run open <mode> [--alongside] [--session=ID] [--code-root=DIR]: a new run folder; its path on stdout."""
from __future__ import annotations

import os
import time
from pathlib import Path

from council import clock, git
from council.commands import cli, event_note, resolve
from council.records import config, events, hook_marks, ignores, memory, paths, request, seat_write, seats, state_write
from council.records import plan as plan_file
from council.records import home as where

MODES = ("council-review", "council-plan", "council-implement", "council-research", "council-postgame",
         "council-init", "test-architect", "context-core")
ASKED = MODES[:5]                                  # the modes that save the user's request first
TEMPLATES = Path(__file__).resolve().parents[3] / "references" / "templates"
INIT_NEXT = "follow council-init: detect the stack, recruit, dry-run the gates, map, then propose"


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "run open", "alongside", "session", "code-root")
    if len(words) > 1:
        raise cli.Refusal("run open takes one mode (got: %s)" % " ".join(words))
    mode = words[0] if words else ""
    if not mode:
        raise cli.Refusal("usage: council run open <mode> [--alongside] [--session=ID]   (the skill name, e.g. "
                          "council-review)")
    if mode not in MODES:
        raise cli.Refusal("unknown mode '%s' — use a skill name: %s" % (mode, ", ".join(MODES)))
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if sid and os.environ.get("COUNCIL_ALLOW_NO_HOOKS") != "1" and not hook_marks.ran(sid):
        raise cli.Refusal("no SessionStart mark for this session — the plugin was enabled or updated after it started, "
                          "so Small Council's hooks (the agent stop, the seat check) may not run in it. Restart the "
                          "session, then open the run again. Only if the user insists on going on without them: "
                          "COUNCIL_ALLOW_NO_HOOKS=1 council run open " + mode)
    home = where.council_home()
    if not os.path.isdir(where.native(home)):
        if mode not in ("council-init", "council-postgame"):   # init maps before a config; a post-game checks any work
            raise cli.Refusal("no council home at %s — run council-init first" % home)
        _makedirs(home, home)
    said = ignores.keep_out(home)                  # before any words land in runs/ — older homes too
    if said:
        cli.warn("council: " + said)
    top = _code_root(args.value("code-root"))
    existing, paused = (resolve.names(resolve.open_runs(home, top, s)) for s in ("in-progress", "paused"))
    if existing and not args.value("alongside"):
        raise cli.Refusal("a run is already in progress on this working tree (%s) — resume it, close it (council run "
                          "close --run <folder> --status abandoned), or open this one with --alongside and pass --run "
                          "<folder> to every later command" % existing)
    run = _folder(home, mode, top, args.value("session") or sid)
    event_note.need(run, "run.opened", "run", mode, "phase=convene",
                    "run opened, but its first event could not be recorded: %s/%s" % (run, events.NAME))
    name, note = run.rsplit("/", 1)[1], memory.size_note(home)
    if note:
        cli.warn("council: " + note)
    if existing:
        cli.warn("council: another run is in progress on this working tree — pass --run %s to every command for this "
                 "one" % name)
    if paused:
        cli.warn("council: a paused run is also open here (%s) — it stays paused" % paused)
    cli.say(run)
    cli.warn("council: if the user asks how the run is going: council status --run %s (with a show_widget tool, call "
             "its read_me, then pass it council status --widget --run %s)" % (name, name))
    if mode in ASKED:
        cli.warn("council: save the user's request word for word in %s/%s before anything else" % (run, request.ASK))
    return 0


def _code_root(given: str) -> str:
    """--code-root stored absolute, links resolved (cd && pwd -P, cygpath -m); else this working tree."""
    if not given:
        return where.this_tree()
    folder = where.native(given)
    if not os.path.isdir(folder):
        raise cli.Refusal("--code-root: no such folder: " + given)
    if not os.access(folder, os.X_OK):
        raise cli.Refusal("cannot enter the code root: " + given)
    return os.path.realpath(folder).replace("\\", "/")


def _folder(home: str, mode: str, top: str, session: str) -> str:
    """<home>/runs/<local time>-<short mode>[-n] with seats/, gates/ and the run's first files."""
    short = "core" if mode == "context-core" else mode[len("council-"):] if mode.startswith("council-") else mode
    base = "%s/runs/%s-%s" % (home, time.strftime("%Y-%m-%d-%H%M%S"), short)
    run, n = base, 2
    while os.path.exists(where.native(run)):
        run, n = "%s-%d" % (base, n), n + 1
    _makedirs(run + "/seats", run)
    _makedirs(run + "/gates", run)
    native = Path(where.native(run))
    try:
        (native / ".write-check").write_bytes(b"")
        (native / ".write-check").unlink()
    except OSError:
        raise cli.Refusal("cannot write in " + run) from None
    init = mode == "council-init"
    template = TEMPLATES / ("run-plan-init.tsv" if init else plan_file.NAME)
    if not template.is_file():
        raise cli.Refusal("run plan template is missing: " + template.as_posix())
    head = git.text(top, "rev-parse", "-q", "--verify", "HEAD") or ""
    _write(native / paths.STATE, "status: in-progress\nmode: %s\nphase: convene\nupdated: %s\nopened: %s\n"
           "code-root: %s\nsession: %s\nplan-schema: 1\nevents-schema: 1\nsize:\nbase:\nstart-head: %s\n"
           "deliverable:\nnext: %s\n%s\n" % (mode, clock.now_min(), clock.now_sec(), top, session, head, INIT_NEXT
                                             if init else state_write.COUNCIL_NEXT_AT_OPEN, state_write.DECISIONS))
    plan = template.read_bytes().decode("utf-8", "surrogateescape")
    plan = plan.replace("\r\n", "\n") if os.name == "nt" else plan      # Git Bash's awk reads in text mode
    for key, value in (("RUN", run.rsplit("/", 1)[1]), ("MODE", mode), ("AGENT_CAP", str(config.agent_cap(home)))):
        plan = plan.replace("{{%s}}" % key, value)
    try:
        (native / plan_file.NAME).write_bytes((plan if plan.endswith("\n") or not plan else plan + "\n")
                                              .encode("utf-8", "surrogateescape"))
    except OSError:
        raise cli.Refusal("cannot write %s/%s" % (run, plan_file.NAME)) from None
    _write(native / "log.md", "# Run log — %s · opened %s\n" % (mode, clock.now_sec()))
    _write(native / seats.SEATS, "\t".join(seat_write.HEADER) + "\n")
    return run


def _makedirs(folder: str, said: str) -> None:
    try:
        os.makedirs(where.native(folder), exist_ok=True)
    except OSError:
        raise cli.Refusal("cannot create " + said) from None


def _write(file: Path, text: str) -> None:
    file.write_bytes(text.encode("utf-8", "surrogateescape"))
