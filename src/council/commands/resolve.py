"""The run a command acts on (the helper's resolve_run): --run (a path, or a folder name under runs/), then
$COUNCIL_RUN, then the one in-progress run on this working tree, then the one this session drives on any
tree. It never guesses between several and never picks a paused run on its own (D6). The one in-progress run
on this tree, when its session: line names another session than this one, is found only for a command that
reads (READS); a command that writes is refused, and the user decides whether this session takes it over
(council run resume --run <folder>). A sub-agent shares its Chair's session id, so its calls are this session's."""
from __future__ import annotations

import os
import re
from pathlib import Path

from council.commands import cli
from council.records import home as where
from council.records import paths, runs, state

READS = ("status", "run status", "run audit", "run events", "run events show", "run events check", "tree", "gates",
         "doctor", "context", "prior", "state", "cap")   # state and cap only with no word after: they print, no more
SESSION = re.compile(r"[A-Za-z0-9._-]+")


def run_folder(args: cli.Args) -> Path:
    """The run folder this command is for, or a refusal naming --run."""
    home = where.council_home()
    given = args.value("run")
    if given:
        folder = run_path(given, home)
        if not is_run(folder):
            raise cli.Refusal("not a run folder: %s" % folder)
        return Path(where.native(folder))
    named = os.environ.get("COUNCIL_RUN", "")
    if named and is_run(named):
        return Path(where.native(named))
    tree = where.this_tree()
    found = open_runs(home, tree, "in-progress")
    if len(found) == 1:
        _ours(Path(found[0]), args)
        return Path(found[0])
    if found:
        raise cli.Refusal("several runs are open on this working tree — pass --run <folder>: %s" % names(found))
    found = session_runs(home, os.environ.get("CLAUDE_CODE_SESSION_ID", ""))
    if len(found) == 1:
        return Path(found[0])
    if found:
        raise cli.Refusal("this session drives several open runs on other working trees — pass --run <folder>: %s"
                          % names(found))
    paused = open_runs(home, tree, "paused")
    if paused:
        one = "<folder>" if len(paused) > 1 else paused[0].split("/")[-1]
        raise cli.Refusal("no in-progress run on this working tree (paused: %s) — to carry on with it: council run "
                          "resume --run %s; to act on it while it stays paused, pass --run <folder>"
                          % (names(paused), one))
    last = newest_run(home, tree).split("/")[-1]
    if last:
        raise cli.Refusal("no open run on this working tree — the newest here, %s, is closed: to read it, pass --run "
                          "%s; for new work, open a run: council run open <mode>" % (last, last))
    raise cli.Refusal("no open run on this working tree — open one with: council run open <mode>   "
                      "(or pass --run <folder>)")


def _ours(run: Path, args: cli.Args) -> None:
    """Refuse a command that writes when the run names another session than this one; a reading command, a session
    with no id and a run with none go through."""
    mine, driver = os.environ.get("CLAUDE_CODE_SESSION_ID", ""), field(run, "session")
    if not mine or driver in ("", "-", mine) or reads(args.words):
        return
    raise cli.Refusal("run %s on this working tree is driven by another session (%s), and this command writes to it — "
                      "nothing was written. Ask the user whether this session takes it over: council run resume --run "
                      "%s (then run this again); to read it from here: council status --run %s"
                      % (run.name, driver, run.name, run.name))


def reads(words: list[str]) -> bool:
    """The command line names a command that only reads its run (READS); state and cap only with no word after."""
    key = " ".join(words[:3] if words[:2] == ["run", "events"] else words[:2] if words[:1] == ["run"] else words[:1])
    if key in ("state", "cap"):
        return len(words) == 1
    return key in READS


def session_id(args: cli.Args) -> str:
    """The session id a run records as its driver: --session, else this session's; '' when there is none. It goes
    into the state's header as written, so --session outside letters, digits, '.', '_' and '-' is refused, and such
    an id from the environment is not recorded (a run is never refused for what Claude Code set)."""
    given = args.value("session")
    if given and not SESSION.fullmatch(given):
        raise cli.Refusal("--session takes letters, digits, '.', '_' and '-' only, not %r — pass the id Claude Code "
                          "gave this session, or leave --session out" % given)
    found = given or os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    return found if SESSION.fullmatch(found) else ""


def field(run: Path, key: str) -> str:
    """A header field of the run's state, as the helper's state_field reads it ('' when it has none)."""
    return state.header(state.text(run)).get(key, "")


def run_path(value: str, home: str) -> str:
    """A --run value as a run folder (run_path): backslashes read as /, trailing separators dropped, a
    relative path made absolute, a bare name looked up under runs/. A relative .council/runs/<name> that
    isn't there — written from the main checkout, used in a linked worktree — is that name under this
    council home's runs/."""
    folder = value.replace("\\", "/")
    while folder.endswith("/") and folder.rstrip("/"):
        folder = folder[:-1]
    absolute = where.absolute(folder)
    if is_run(folder):
        if not absolute:
            folder = where.here(where.native(folder)) if os.path.isdir(where.native(folder)) else value
    elif is_run(home + "/runs/" + folder):
        folder = home + "/runs/" + folder
    elif not absolute and (folder.startswith("runs/") or "/runs/" in folder):
        name = folder.split("/")[-1]
        if is_run(home + "/runs/" + name):
            folder = home + "/runs/" + name
    return folder


def is_run(folder: str) -> bool:
    """The folder holds a run's state file."""
    return os.path.isfile(where.native(folder) + "/" + paths.STATE)


def open_runs(home: str, tree: str, status: str = "") -> list[str]:
    """The open runs on this working tree (runs_here), of this status when given; no code-root counts as here."""
    return [run.folder for run in runs.listing(home, 1000000, "open")
            if runs.here(run.code_root, tree) and status in ("", run.status)]


def newest_run(home: str, tree: str) -> str:
    """The newest run of any status on this working tree ('' when none): run audit's run when none is open."""
    return next((run.folder for run in runs.listing(home, 1000000, "all") if runs.here(run.code_root, tree)), "")


def session_runs(home: str, session: str) -> list[str]:
    """The in-progress runs this session drives (its session: line), on any working tree."""
    if not session:
        return []
    return [run.folder for run in runs.listing(home, 1000000, "open")
            if run.status == "in-progress" and (run.session or "-") == session]


def names(folders: list[str]) -> str:
    """Run folders as 'name, name'."""
    return ", ".join(folder.split("/")[-1] for folder in folders)
