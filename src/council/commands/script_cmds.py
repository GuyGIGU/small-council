"""The commands that hand over to a tool or a view (commands/script.py), one TABLE row each."""
from __future__ import annotations

import os
from pathlib import Path

from council.commands import cli, nudges, resolve, script
from council.records import home as where

TABLE = {
    "evidence": ("evidence", ("SUB", "--run", "RUN"), ()),
    "status": ("status", ("--run", "RUN", "--home", "HOME"), ("widget", "json", "line", "preview")),
    "run audit": ("audit", ("--run", "RUN"), ("transcript",)),
}
EVIDENCE = "usage: council evidence build|check [--run <folder>]"


def main(args: cli.Args, words: list[str]) -> int:
    command = "run audit" if args.words[0] == "run" else args.words[0]
    words = list(words)
    sub = words.pop(0) if command == "evidence" and words else ""
    name, lead, takes = TABLE[command]
    label = command + (" " + sub if command == "evidence" else "")
    cli.takes_flags(args, label, *takes)
    cli.no_words(label, words)
    _refuse(command, sub, args)
    home = where.council_home()
    run = (_audited(args, home) if command == "run audit" else resolve.run_folder(args).as_posix()) \
        if "RUN" in lead else ""
    fill = {"RUN": lambda: [run], "HOME": lambda: [home], "SUB": lambda: [sub]}
    words = [word for token in lead for word in (fill[token]() if token in fill else [token])]
    for flag, value in ((flag, args.value(flag)) for flag in takes if args.value(flag)):
        words += ["--" + flag] + ([] if flag in cli.SWITCHES else [_mixed(value) if flag == "transcript" else value])
    code = script.run(name, words)
    if command == "status" and code == 0 and not args.value("json"):
        nudges.clear_card(Path(run))                     # the status was read out: no card is owed
    return code


def _refuse(command: str, sub: str, args: cli.Args) -> None:
    if command == "evidence" and sub not in ("build", "check"):
        raise cli.Refusal(EVIDENCE)
    if command == "status" and sum(bool(args.value(f)) for f in ("widget", "json", "line")) > 1:
        raise cli.Refusal("status takes --widget, --json or --line, not together")
    if command == "status" and args.value("preview") and not args.value("widget"):
        raise cli.Refusal("--preview labels a widget: use it with --widget")


def _audited(args: cli.Args, home: str) -> str:
    """The run named or in progress here, else this working tree's newest run: the one just closed."""
    tree = where.this_tree()
    if args.value("run") or os.environ.get("COUNCIL_RUN") or resolve.open_runs(home, tree, "in-progress"):
        return resolve.run_folder(args).as_posix()
    newest = resolve.newest_run(home, tree)
    if not newest:
        raise cli.Refusal("no run on this working tree to audit — pass --run <folder>")
    return newest


def _mixed(path: str) -> str:
    """A path as cygpath -m writes it, where Git Bash has cygpath."""
    return where.native(path.replace("\\", "/")) if os.name == "nt" else path
