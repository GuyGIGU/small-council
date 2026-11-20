"""council run open <mode> [--alongside] [--session=ID] [--code-root=DIR]: a new run folder; its path on stdout. The
mode is the skill's name (council-review), or the same without council- (review)."""
from __future__ import annotations

import os
import time
from pathlib import Path

from council import clock, git
from council.commands import cli, event_note, resolve
from council.records import config, events, hook_marks, ignores, memory, paths, request, run_files, seat_write, seats
from council.records import state_write
from council.records import plan as plan_file
from council.records import closing
from council.records import home as where

ASKED = closing.MODES                              # the modes that save the user's request first
MODES = ASKED + ("council-init", "test-architect", "context-core")
TEMPLATES = Path(__file__).resolve().parents[3] / "references" / "templates"
PLANS = {"council-init": "run-plan-init.tsv", "council-review": "run-plan-review.tsv",
         "council-implement": "run-plan-implement.tsv", "council-plan": "run-plan-design.tsv",
         "council-research": "run-plan-design.tsv", "council-health": "run-plan-health.tsv",
         "council-postgame": "run-plan-postgame.tsv", "test-architect": "run-plan-audit.tsv"}   # else run-plan.tsv
BRIEFS = {"council-review": "review-brief.md", "council-implement": "review-brief.md",   # the pair's role texts (D48)
          "council-plan": "design-brief.md", "council-research": "design-brief.md",     # the designer's (D60)
          "council-health": "review-brief.md", "council-postgame": "review-brief.md",   # the pair's again (D65, D71)
          "test-architect": "review-brief.md"}                                          # and a test audit's (D75)
LINES = {"council-implement": "build-brief.md",   # what a build's brief adds to the review's (D56), a health
         "council-health": "health-brief.md",     # pass's (D65), a post-game's (D71) and a test audit's (D75),
         "council-postgame": "postgame-brief.md",  # each block on its {{NAME}} line
         "test-architect": "audit-brief.md"}
BLOCKS = ("BUILD", "BUILD_RUNNER", "HEALTH", "POSTGAME", "AUDIT", "AUDIT_READERS")
LOOP = "council"   # /council: no run of its own (D64)
INIT_NEXT = ("follow council-init: detect the stack and ask each part's reason, propose its watch lists, dry-run the "
             "gates, map, then propose")
STATUS_HINT = "if the user asks how the run is going"   # an advisory line's lead


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "run open", "alongside", "session", "code-root")
    if len(words) > 1:
        raise cli.Refusal("run open takes one mode (got: %s)" % " ".join(words))
    mode = words[0] if words else ""
    if not mode:
        raise cli.Refusal("usage: council run open <mode> [--alongside] [--session=ID]   (the skill name, e.g. "
                          "council-review)")
    mode = "council-" + mode if mode not in MODES and "council-" + mode in MODES else mode   # review = council-review
    if mode == LOOP:
        raise cli.Refusal("/council has no run of its own: it opens a plan run first (council run open council-plan), "
                          "then a build run on the plan it writes (council run open council-implement) — follow "
                          "skills/council/SKILL.md, step 1")
    if mode not in MODES:
        raise cli.Refusal("unknown mode '%s' — use a skill name: %s" % (mode, ", ".join(MODES)))
    session = resolve.session_id(args)
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if sid and os.environ.get("COUNCIL_ALLOW_NO_HOOKS") != "1" and not hook_marks.ran(sid):
        raise cli.Refusal("no SessionStart mark for this session — the plugin was enabled or updated after it started, "
                          "so Small Council's hooks (the agent stop, the seat check) may not run in it. Restart the "
                          "session, then open the run again. Only if the user insists on going on without them: "
                          "COUNCIL_ALLOW_NO_HOOKS=1 council run open " + mode)
    home = where.council_home()
    if not os.path.isdir(where.native(home)):
        if mode not in ("council-init", "council-postgame"):   # init maps before a config; a post-game checks any work
            first = ("set up a quick one first: council init scaffold --quick" if mode == "council-review" else
                     "run /council-init first")
            raise cli.Refusal("no council home at %s — %s, then open the run again" % (home, first))
        _makedirs(home, home)
    said = ignores.keep_out(home)                  # before any words land in runs/ — older homes too
    if said:
        cli.warn("council: " + said)
    top = _code_root(args.value("code-root"))
    existing, paused = (resolve.names(resolve.open_runs(home, top, s)) for s in ("in-progress", "paused"))
    if existing and not args.value("alongside"):
        raise cli.Refusal("a run is already in progress on this working tree (%s) — resume it, close it (council run "
                          "close --run <folder> --status abandoned), or open this one with --alongside and pass --run "
                          "<folder> to every later command%s" % (existing, _theirs(home, top, session)))
    run = _folder(home, mode, top, session)
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
    cli.warn("council: %s: council status --run %s (with a show_widget tool, call its read_me, then pass it "
             "council status --widget --run %s)" % (STATUS_HINT, name, name))
    if mode in ASKED:
        cli.warn("council: save the user's request word for word in %s/%s before anything else" % (run, request.ASK))
    return 0


def _theirs(home: str, top: str, session: str) -> str:
    """When an in-progress run here is driven by another session: which, and that resuming or abandoning it is the
    user's call; else ''."""
    drivers = sorted({resolve.field(Path(folder), "session") for folder in resolve.open_runs(home, top, "in-progress")}
                     - {"", "-", session})
    if not drivers:
        return ""
    return (". It is driven by another session (%s), which may still be working on it: ask the user before you resume "
            "it or abandon it" % ", ".join(drivers))


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
    template = TEMPLATES / PLANS.get(mode, plan_file.NAME)
    brief = TEMPLATES / BRIEFS[mode] if mode in BRIEFS else None
    for need, what in ((template, "run plan"), (brief, "brief")):
        if need is not None and not need.is_file():
            raise cli.Refusal("%s template is missing: %s" % (what, need.as_posix()))
    head = git.text(top, "rev-parse", "-q", "--verify", "HEAD") or ""
    _write(native / paths.STATE, "status: in-progress\nmode: %s\nphase: convene\nupdated: %s\nopened: %s\n"
           "code-root: %s\nsession: %s\nplan-schema: 1\nevents-schema: 1\nsize:\nbase:\nstart-head: %s\n"
           "deliverable:\nnext: %s\n%s\n" % (mode, clock.now_min(), clock.now_sec(), top, session, head, INIT_NEXT
                                             if init else state_write.COUNCIL_NEXT_AT_OPEN, state_write.DECISIONS))
    name = run.rsplit("/", 1)[1]
    _fill(template, native / plan_file.NAME, run, RUN=name, MODE=mode, AGENT_CAP=str(config.agent_cap(home)))
    if brief is not None:
        from council.commands import book    # the book's paths, as council book prints them (D52)
        _fill(brief, native / run_files.BRIEF, run, RUN=name, RUN_DIR=run, CODE_ROOT=top, HOME=home, MODE=mode,
              BOOK="\n".join(book.read_first(home)), KNOWN=book.known(home), **brief_lines(mode))
    _write(native / "log.md", "# Run log — %s · opened %s\n" % (mode, clock.now_sec()))
    _write(native / seats.SEATS, "\t".join(seat_write.HEADER) + "\n")
    return run


def brief_lines(mode: str) -> dict[str, str]:
    """The blocks a mode's lines template adds to the review's brief, by name ([BUILD], [BUILD_RUNNER] for a build,
    [HEALTH] for a health pass, [POSTGAME] for a post-game, [AUDIT], [AUDIT_READERS] for a test audit); a block the
    mode's file lacks is empty, and a brief has an empty one's line taken out (a review's, all of them)."""
    blocks = dict.fromkeys(BLOCKS, "")
    if mode not in LINES:
        return blocks
    try:
        text = (TEMPLATES / LINES[mode]).read_bytes().decode("utf-8", "surrogateescape").replace("\r\n", "\n")
    except OSError:
        raise cli.Refusal("brief template is missing: %s" % (TEMPLATES / LINES[mode]).as_posix()) from None
    name = ""
    for line in text.split("\n"):
        if line.startswith("[") and line.endswith("]") and line[1:-1] in blocks:
            name = line[1:-1]
        elif name:
            blocks[name] += line + "\n"
    return {key: value.rstrip("\n") for key, value in blocks.items()}


def _fill(template: Path, file: Path, run: str, **values: str) -> None:
    """A run file from its template, each {{KEY}} filled, written with LF line ends and a last newline; a line that is
    only a {{KEY}} whose value is empty is taken out whole."""
    text = template.read_bytes().decode("utf-8", "surrogateescape")
    text = text.replace("\r\n", "\n")         # a CR right before a newline is dropped on every OS, as bytewise.records
    for key, value in values.items():
        if not value:
            text = text.replace("\n{{%s}}\n" % key, "\n")
        text = text.replace("{{%s}}" % key, value)
    try:
        file.write_bytes((text if text.endswith("\n") or not text else text + "\n").encode("utf-8", "surrogateescape"))
    except OSError:
        raise cli.Refusal("cannot write %s/%s" % (run, file.name)) from None


def _makedirs(folder: str, said: str) -> None:
    try:
        os.makedirs(where.native(folder), exist_ok=True)
    except OSError as failure:
        raise cli.Refusal("cannot create %s (%s) — nothing was opened; free the path (a file in its way, no write "
                          "permission), or on Windows shorten the project's path or enable long paths, then open the "
                          "run again" % (said, failure.strerror or failure)) from None


def _write(file: Path, text: str) -> None:
    file.write_bytes(text.encode("utf-8", "surrogateescape"))
