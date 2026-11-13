"""The run a command acts on (the helper's resolve_run): --run (a path, or a folder name under runs/), then
$COUNCIL_RUN, then the one in-progress run on this working tree, then the one this session drives on any
tree. It never guesses between several, never picks another session's run, and never picks a paused run
on its own (D6)."""
from __future__ import annotations

import os
import re
from pathlib import Path

from council.commands import cli
from council.records import home as where
from council.records import paths, runs, state


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
    raise cli.Refusal("no open run on this working tree — open one with: council run open <mode>   "
                      "(or pass --run <folder>)")


def field(run: Path, key: str) -> str:
    """A header field of the run's state, as the helper's state_field reads it ('' when it has none)."""
    return state.header(state.text(run), exact_keys=True).get(key, "")


def run_path(value: str, home: str) -> str:
    """A --run value as a run folder (run_path): backslashes read as /, trailing separators dropped, a
    relative path made absolute, a bare name looked up under runs/. A relative .council/runs/<name> that
    isn't there — written from the main checkout, used in a linked worktree — is that name under this
    council home's runs/."""
    folder = value.replace("\\", "/")
    while folder.endswith("/") and folder.rstrip("/"):
        folder = folder[:-1]
    absolute = folder.startswith("/") or re.match(r"[A-Za-z]:/", folder) is not None
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


def open_runs(home: str, tree: str, status: str) -> list[str]:
    """The open runs on this working tree with this status (runs_here): a run with no code-root counts as
    this tree's."""
    return [run.folder for run in runs.listing(home, 1000000, "open")
            if run.code_root in (tree, "", "-") and run.status == status]


def session_runs(home: str, session: str) -> list[str]:
    """The in-progress runs this session drives (its session: line), on any working tree."""
    if not session:
        return []
    return [run.folder for run in runs.listing(home, 1000000, "open")
            if run.status == "in-progress" and _dash(run.session) == session]


def names(folders: list[str]) -> str:
    """Run folders as 'name, name'."""
    return ", ".join(folder.split("/")[-1] for folder in folders)


def _dash(value: str) -> str:
    """A listed value as list_runs prints it: '-' for an empty one."""
    return value or "-"
