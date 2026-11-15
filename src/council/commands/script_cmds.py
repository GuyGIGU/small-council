"""The commands that hand over to a scripts/ entry: evidence, tui, status, pet, history, outcomes and run audit. One
row each says the script, the words it starts with (a capital word is filled in below), the flags the command takes
and hands on as given, and why it refuses --run."""
from __future__ import annotations

import builtins
import os
import sys
from functools import reduce
from pathlib import Path

from council.commands import cli, nudges, resolve, script, shell
from council.records import home as where

TABLE = {
    "evidence": ("evidence", ("SUB", "--run", "RUN"), (), ""),
    "tui": ("cockpit", ("--run", "RUN", "--home", "HOME"), ("watch", "json"), ""),
    "status": ("status", ("--run", "RUN", "--home", "HOME", "TUI"), ("widget", "json", "line", "preview"), ""),
    "pet": ("pet", ("--project", "TREE", "--home", "HOME", "--council", "COUNCIL", "--bash", "BASH", "SESSION",
                    "LAUNCH"), ("stop", "demo", "still", "pose", "exit-after"),
            "pet follows this session's run on this working tree; it does not take --run"),
    "history": ("history", ("--home", "HOME"), ("json",),
                "history reads every run of this council home; it does not take --run"),
    "outcomes": ("outcomes", ("--home", "HOME", "--repo", "TREE"), ("json",),
                 "outcomes reads every run of this council home's record; it does not take --run"),
    "run audit": ("audit", ("--run", "RUN"), ("transcript",), ""),
}
FAULTS = {  # what each script's own __main__ prints as '<script>: <fault>' and exits 2 on
    "evidence": "EvidenceError paths.RecordError UnicodeError OSError ValueError",
    "history": "ledger.LedgerError OSError ValueError",
    "tune": "TuneError paths.RecordError OSError UnicodeError ValueError",
    "repair": "RepairError paths.RecordError OSError UnicodeError ValueError TypeError",
}
EVIDENCE = "usage: council evidence build|show|check [--run <folder>]"
ROOT = script.SCRIPTS.parent


def main(args: cli.Args, *given: list[str]) -> int:
    """`run audit` comes as (args, sub, words), the others as (args, words)."""
    command = "run audit" if args.words[0] == "run" else args.words[0]
    words = list(given[-1])
    sub = words.pop(0) if command == "evidence" and words else ""
    name, lead, takes, no_run = TABLE[command]
    label = command + (" " + sub if command == "evidence" else "")
    cli.takes_flags(args, label, *takes)
    cli.no_words(label, words)
    _refuse(command, sub, args, no_run)
    home = where.council_home()
    if command in ("history", "outcomes") and not os.path.isdir(where.native(home)):
        cli.say("no council here (no %s) — run council-init" % home)
        return 0
    run = (_audited(args, home) if command == "run audit" else resolve.run_folder(args).as_posix()) \
        if "RUN" in lead else ""
    session = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    fill = {"RUN": lambda: [run], "HOME": lambda: [home], "SUB": lambda: [sub], "TREE": lambda: [where.this_tree()],
            "TUI": lambda: tui_commands(Path(run)), "COUNCIL": lambda: [where.here(ROOT) + "/bin/council"],
            "BASH": lambda: [shell.bash_exe() or shell.helper_bash()],
            "SESSION": lambda: ["--session", session] if session else [],
            "LAUNCH": lambda: [] if args.value("stop") else ["--launch"]}
    words = [word for token in lead for word in (fill[token]() if token in fill else [token])]
    for flag, value in ((flag, args.value(flag)) for flag in takes if args.value(flag)):
        words += ["--" + flag] + ([] if flag in cli.SWITCHES else [_mixed(value) if flag == "transcript" else value])
    code = run_script(name, words)
    if command == "status" and code == 0 and not args.value("json"):
        nudges.clear_card(Path(run))                     # the status was read out: no card is owed
    return code


def run_script(name: str, words: list[str]) -> int:
    """scripts/<name>.py run here as its own process ran it: its folder first on the path (audit.py and cockpit.py
    import their siblings), no bytecode left beside it, its faults said as its __main__ says them."""
    sys.dont_write_bytecode = True
    if str(script.SCRIPTS) not in sys.path:
        sys.path.insert(0, str(script.SCRIPTS))
    module = script.load(name)
    faults = tuple(reduce(getattr, fault.split("."), builtins if hasattr(builtins, fault) else module)
                   for fault in FAULTS.get(name, "").split())
    return script.run(name, words, faults)


def _refuse(command: str, sub: str, args: cli.Args, no_run: str) -> None:
    if command == "evidence" and sub not in ("build", "show", "check"):
        raise cli.Refusal(EVIDENCE)
    if no_run and args.value("run"):
        raise cli.Refusal(no_run)
    if command == "tui" and args.value("watch") and args.value("json"):
        raise cli.Refusal("tui takes --watch or --json, not both")
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


def tui_commands(run: Path) -> list[str]:
    """The terminal-view command the status prints: for PowerShell and Git Bash where there is cygpath."""
    council, folder, exe = where.here(ROOT) + "/bin/council", where.here(run), shell.bash_exe()
    plain = "bash %s tui --watch --run %s" % (shell.sh_quote(council), shell.sh_quote(folder))
    if not exe:
        return ["--tui-command", plain]
    return ["--tui-command", "PowerShell: & %s %s tui --watch --run %s" % tuple(map(shell.ps_quote, (exe, council,
            folder))), "--tui-command", "Git Bash: " + plain]


def _mixed(path: str) -> str:
    """A path as cygpath -m writes it, where Git Bash has cygpath."""
    return where.native(path.replace("\\", "/")) if os.name == "nt" else path
