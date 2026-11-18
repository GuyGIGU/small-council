"""council patch apply|revert <task> [--round <r>]: a saved round's patch put back on, or taken off, the files in
the run's code root (the task's last saved round unless --round names another). Files change and no record does:
the round stays saved, and the next council patch save diffs from the last saved round's tree as before.

council patch hold <task>: the edits no round holds (what the next patch save would put in task n's round) written to
patches/T<n>-held.patch and taken off the files, all or nothing — a builder that stopped with NEEDS: leaves its
unfinished edits out of the next task's gates and round. council patch apply <task> --held puts them back and removes
the file, or refuses with nothing changed.

`undo` and `redo` are the one way a saved round's patch comes off or goes on the files of a folder: `git apply`,
all or nothing, naming the files that would not apply. Their callers are the two commands here and council check's
revert check (revert_check), which undoes a task's rounds in a scratch copy of the project."""
from __future__ import annotations

import os
import re
from pathlib import Path

from council import diff, git
from council.commands import cli, resolve
from council.records import home as where
from council.records import patches

FAILED = re.compile(r"error: patch failed: (.+):[0-9]+")
NAMED = re.compile(r"error: (.+?): .+")
GLOB = re.compile(r"([*?\[\\])")


def undo(folder: str | Path, patch: Path, keep: tuple[str, ...] = (), raw: bool = False) -> list[str]:
    """Take a saved round's patch off the files in folder, all or nothing, the paths in keep left as they are:
    [] when it came off; else the files that would not (git's own words when it names none). raw: the folder
    holds git's own bytes (a copy written from the tree's blobs), so no line end is converted either way."""
    return _apply(folder, patch, True, keep, raw)


def redo(folder: str | Path, patch: Path) -> list[str]:
    """Put a saved round's patch back on the files in folder, all or nothing; what would not apply, as undo."""
    return _apply(folder, patch, False, (), False)


def _apply(folder: str | Path, patch: Path, reverse: bool, keep: tuple[str, ...], raw: bool) -> list[str]:
    """git apply in folder, which need not be a repository: git looks for none above it, so a scratch copy in a
    folder under some other repository is patched as itself. A code root is patched under its own settings, so a
    file checked out with CRLF (core.autocrlf) takes a patch taken between git's LF trees."""
    args = (["-c", "core.autocrlf=false"] if raw else []) + ["apply", "--whitespace=nowarn"] \
        + (["-R"] if reverse else []) + ["--exclude=" + GLOB.sub(r"\\\1", path) for path in keep] + [str(patch)]
    ceiling = os.path.dirname(os.path.abspath(str(folder)))
    try:      # git's own English words: files_named reads them, whatever the user's locale
        git.output(folder, *args, extra={"GIT_CEILING_DIRECTORIES": ceiling, "LC_ALL": "C", "LANGUAGE": "C"})
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
    """patch apply|revert: the round chosen, put on or taken off the code root, or refused with nothing changed;
    patch hold, and apply --held."""
    if verb == "hold":
        return hold(run, task)
    if args.value("held"):
        if args.value("round") or args.value("base"):
            raise cli.Refusal("patch apply --held puts a task's held edits back as they were held — it takes no "
                              "--round or --base")
        return put_back(run, task)
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


def _named(patch: Path) -> list[str]:
    try:
        return [file.path for file in diff.files(patch.read_bytes().decode("utf-8", "surrogateescape"))]
    except OSError:
        return []


def hold(run: Path, task: int) -> int:
    """patch hold: the files' edits since the run's last saved round (else the commit it opened on) written to
    patches/T<n>-held.patch, then taken off the files through undo, all or nothing; nothing to hold says so."""
    from council.commands import patch     # patch save's own start and diff
    held = patches.held(run, task)
    top = resolve.field(run, "code-root") or where.this_tree()
    start = patch.start_of(run, top, "", patches.rounds(run))
    tree = git.files_tree(top)
    if not tree:
        raise cli.Refusal("can't read the files in %s as a git tree — patch hold needs the code root in git" % top)
    data = patch.round_diff(top, start, tree, "save the round first (council patch save %d --base <rev>)" % task)
    if not data.strip():
        cli.say("patch: nothing to hold for task %d — the files are as the last saved round left them%s" % (
            task, "; its held edits are in %s (council patch apply %d --held)" % (held.as_posix(), task)
            if held.is_file() else ""))
        return 0
    if held.exists():
        raise cli.Refusal("task %d already has held edits in %s — put them back first (council patch apply %d --held), "
                          "or move that file aside, then hold again" % (task, held.as_posix(), task))
    try:
        held.parent.mkdir(exist_ok=True)
        held.write_bytes(data)
    except OSError as failure:
        raise cli.Refusal("can't write %s (%s) — make the run folder writable, then hold again"
                          % (held.as_posix(), failure)) from None
    wrong = undo(top, held)
    if wrong:
        held.unlink()
        raise cli.Refusal("patch hold refused, nothing changed: the edits don't come off the files in %s cleanly: %s — "
                          "council patch save %d puts them in the task's round instead" % (top, ", ".join(wrong), task))
    files = _named(held)
    cli.say("patch: held task %d's edits in no round → %s · %d file(s): %s — taken off the files; council patch apply "
            "%d --held puts them back" % (task, held.as_posix(), len(files), ", ".join(files) or "none", task))
    return 0


def put_back(run: Path, task: int) -> int:
    """patch apply --held: the held edits put back on the files through redo, all or nothing, and their file removed;
    refused, nothing changed, when they don't go on cleanly."""
    held = patches.held(run, task)
    if not held.is_file():
        raise cli.Refusal("task %d has no held edits (%s isn't there) — council patch hold %d takes a stopped "
                          "builder's edits off the files into it" % (task, held.as_posix(), task))
    top = resolve.field(run, "code-root") or where.this_tree()
    wrong = redo(top, held)
    if wrong:
        raise cli.Refusal("patch apply --held refused, nothing changed: task %d's held edits don't go on the files in "
                          "%s cleanly: %s — those files changed since they were held. The edits stay in %s: put them "
                          "on by hand (git apply %s), or move the file aside to drop them"
                          % (task, top, ", ".join(wrong), held.as_posix(), held.as_posix()))
    files = _named(held)
    try:
        held.unlink()
    except OSError:
        cli.warn("council: the held edits are back on the files, but %s could not be removed — remove it by hand"
                 % held.as_posix())
    cli.say("patch: task %d's held edits put back on the files in %s · %d file(s): %s — the next council patch save %d "
            "puts them in the task's round" % (task, top, len(files), ", ".join(files) or "none", task))
    return 0
