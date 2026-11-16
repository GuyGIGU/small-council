"""council patch apply|revert <task> [--round <r>]: a saved round's patch put back on, or taken off, the files in
the run's code root (the task's last saved round unless --round names another). Files change and no record does:
the round stays saved, and the next council patch save diffs from the last saved round's tree as before.

`undo` and `redo` are the one way a saved round's patch comes off or goes on the files of a folder: `git apply`,
all or nothing, naming the files that would not apply. Their callers are the two commands here and council check's
revert check (revert_check), which undoes a task's rounds in a scratch copy of the project."""
from __future__ import annotations

import os
import re
from pathlib import Path

from council import git
from council.commands import cli, resolve
from council.records import home as where
from council.records import patches

FAILED = re.compile(r"error: patch failed: (.+):[0-9]+")
NAMED = re.compile(r"error: (.+?): .+")
GLOB = re.compile(r"([*?\[\\])")


def undo(folder: str | Path, patch: Path, keep: tuple[str, ...] = ()) -> list[str]:
    """Take a saved round's patch off the files in folder, all or nothing, the paths in keep left as they are:
    [] when it came off; else the files that would not (git's own words when it names none)."""
    return _apply(folder, patch, True, keep)


def redo(folder: str | Path, patch: Path) -> list[str]:
    """Put a saved round's patch back on the files in folder, all or nothing; what would not apply, as undo."""
    return _apply(folder, patch, False, ())


def _apply(folder: str | Path, patch: Path, reverse: bool, keep: tuple[str, ...]) -> list[str]:
    """git apply in folder, which need not be a repository: git looks for none above it, so a scratch copy in a
    folder under some other repository is patched as itself."""
    args = ["apply", "--whitespace=nowarn"] + (["-R"] if reverse else []) \
        + ["--exclude=" + GLOB.sub(r"\\\1", path) for path in keep] + [str(patch)]
    ceiling = os.path.dirname(os.path.abspath(str(folder)))
    try:
        git.output(folder, *args, extra={"GIT_CEILING_DIRECTORIES": ceiling})
    except git.GitError as failure:
        return files_named(str(failure))
    return []


def files_named(said: str) -> list[str]:
    """The files git apply's errors name, once each in order; else its first line."""
    found: list[str] = []
    for line in said.splitlines():
        match = FAILED.fullmatch(line.strip()) or NAMED.fullmatch(line.strip())
        if match and match.group(1) not in found:
            found.append(match.group(1))
    return found or [said.splitlines()[0] if said else "git apply failed"]


def main(args: cli.Args, run: Path, verb: str, task: int) -> int:
    """patch apply|revert: the round chosen, put on or taken off the code root, or refused with nothing changed."""
    if args.value("base"):
        raise cli.Refusal("patch %s doesn't take --base — it puts a saved round on or off as it was saved; --round "
                          "<r> names which round" % verb)
    one = round_of(run, task, args.value("round"), verb)
    top = resolve.field(run, "code-root") or where.this_tree()
    patch = patches.folder(run) / (patches.name(task, one.round) + ".patch")
    if not patch.is_file():
        raise cli.Refusal("the patch of task %d round %d is not in %s — it can't be put on or taken off; council "
                          "patch show %d lists the rounds on record" % (task, one.round, patches.folder(run).as_posix(),
                                                                         task))
    wrong = undo(top, patch) if verb == "revert" else redo(top, patch)
    if wrong:
        hint = ("they changed since it was saved; a later round on them comes off first (council patch revert <its "
                "task> --round <r>)") if verb == "revert" else \
            "they already hold it, or changed since it started; council patch revert %d --round %d takes it off" % (
                task, one.round)
        raise cli.Refusal("patch %s refused, nothing changed: task %d round %d doesn't %s the files in %s cleanly: %s "
                          "— %s; council patch show %d lists its rounds"
                          % (verb, task, one.round, "come off" if verb == "revert" else "go on", top,
                             ", ".join(wrong), hint, task))
    cli.say("patch: task %d round %d %s the files in %s · %d file(s): %s — no record changed: the round stays saved, "
            "and the next council patch save diffs from the last saved round as before"
            % (task, one.round, "taken off" if verb == "revert" else "put back on", top, len(one.files),
               ", ".join(one.files) or "none"))
    return 0


def round_of(run: Path, task: int, wanted: str, verb: str) -> patches.Round:
    """The round --round names, else the task's last saved round; a refusal naming the rounds there are."""
    found = patches.rounds(run, task)
    if not found:
        raise cli.Refusal("patch %s: task %d has no saved rounds — council patch save %d once its report is written"
                          % (verb, task, task))
    if not wanted:
        return found[-1]
    one = next((each for each in found if str(each.round) == wanted), None)
    if one is None:
        raise cli.Refusal("task %d has no round '%s' — its saved rounds are %s (council patch show %d)"
                          % (task, wanted, ", ".join(str(each.round) for each in found), task))
    return one
