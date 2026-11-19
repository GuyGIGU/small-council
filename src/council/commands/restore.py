"""council restore point | restore show [--run <folder>]: a run's restore point (D57).

council restore point records, before a run changes the project, a commit of the code root's files as they are now —
committed, staged, unstaged and untracked alike; what .gitignore ignores and the council home left out — made with git
commit-tree, so no branch, index or file moves, and kept by a ref, refs/council/restore/<run>. It writes
<run>/restore.md and nothing else, and refuses a second point for the same run. council restore show prints the
point, what changed since, and the commands that put every file back as it was: printed, never run, since restoring
throws away what the run did and is the owner's call. The commands are git plumbing that never touches the council
home on disk, tracked or not: HEAD and the branch move by update-ref and symbolic-ref, the files come back from the
point's tree through read-tree and checkout-index, and the index ends as the point's HEAD."""
from __future__ import annotations

import shlex
from pathlib import Path

from council import clock, git
from council.commands import cli, resolve
from council.records import restore
from council.records import home as where

USAGE = "usage: council restore point | restore show [--run <folder>] — a run's restore point, and how to go back to it"
NAMED = {"GIT_AUTHOR_NAME": "Small Council", "GIT_AUTHOR_EMAIL": "small-council@localhost",
         "GIT_COMMITTER_NAME": "Small Council", "GIT_COMMITTER_EMAIL": "small-council@localhost"}
SHOWN = 12          # changed files named on the Since then line; the commands name every one
NOT_GIT = ("the code root is not a git repository, so no restore point can be taken — recommend `git init` to the "
           "owner; if they decline, record it with `council state restore=backup`, copy each file to "
           "%s/backup/<path> before its first change, and say so on the report's Undo line")


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "restore")
    if words not in (["point"], ["show"]):
        raise cli.Refusal(USAGE)
    run = resolve.run_folder(args)
    top = where.native(resolve.field(run, "code-root") or where.this_tree())
    if git.text(top, "rev-parse", "--is-inside-work-tree") != "true":
        raise cli.Refusal(NOT_GIT % run.as_posix())
    return point(run, top) if words == ["point"] else show(run, top)


def point(run: Path, top: str) -> int:
    held = restore.read(run)
    if held:
        raise cli.Refusal("this run's restore point is taken already (%s, %s) — council restore show prints how to "
                          "go back to it" % (held.commit[:12], held.taken))
    head = git.text(top, "rev-parse", "-q", "--verify", "HEAD^{commit}") or ""
    branch = git.text(top, "symbolic-ref", "-q", "--short", "HEAD") or "(detached)"
    tree = git.files_tree(top)
    commit = tree and git.text(top, "commit-tree", tree, *(["-p", head] if head else []), "-m",
                               "Small Council restore point — run %s" % run.name, extra=NAMED)
    if not commit or git.text(top, "update-ref", restore.REF + run.name, commit) is None:
        raise cli.Refusal("git could not record the code root's files as a restore point (git add, commit-tree or "
                          "update-ref failed) — check `git status` runs cleanly there, then run this again")
    # The council home is left out on both sides: a HEAD that tracks .council/ holds no uncommitted work for it.
    loose = bool(head) and bool(changes(top, git.text(top, "rev-parse", head + "^{tree}") or "", tree))
    try:
        restore.write(run, restore.Point(commit, head, branch, clock.now_sec()))
    except OSError as failure:
        raise cli.Refusal("cannot write %s/%s (%s) — make the run folder writable, then run this again"
                          % (run.as_posix(), restore.NAME, failure)) from None
    cli.say("Restore point: %s — the code root's files as they are now%s, kept as %s%s; nothing in the project moved. "
            "How to go back to it: council restore show" % (
                commit[:12], " (with the uncommitted work)" if loose else "", restore.REF, run.name))
    return 0


def changes(top: str, old_tree: str, new_tree: str) -> list[tuple[str, str]]:
    """(status, path) for each file that differs between two trees: A new, M changed, D deleted, T its type."""
    code, out = git.run(top, "diff", "--name-status", "--no-renames", "-z", old_tree, new_tree, *git.between(),
                        names=True)
    if code:
        raise cli.Refusal("git could not compare the files with the restore point (git diff exit %d) — run `git "
                          "status` in %s to see git's own error, put it right, then run this again"
                          % (code, Path(top).as_posix()))
    cells = out.decode("utf-8", "surrogateescape").split("\0")
    return [(cells[n][:1], cells[n + 1]) for n in range(0, len(cells) - 1, 2) if cells[n]]


def show(run: Path, top: str) -> int:
    held = restore.read(run)
    if not held:
        raise cli.Refusal("no restore point for this run — council restore point takes one, before the run changes "
                          "the project")
    old_tree = git.text(top, "rev-parse", "-q", "--verify", held.commit + "^{tree}")
    if not old_tree:
        raise cli.Refusal("the restore point's commit %s is gone from this repository (was %s%s deleted?), so no "
                          "command can bring it back — tell the owner, and offer `git reflog` (the commits the run "
                          "made) and their own backup for the rest" % (held.commit[:12], restore.REF, run.name))
    now_tree = git.files_tree(top)
    if not now_tree:
        raise cli.Refusal("git could not read the code root's files as they are now (git add or write-tree failed), "
                          "so what changed since the point is unknown — check `git status` runs cleanly in %s, then "
                          "run council restore show again" % Path(top).as_posix())
    now_head = git.text(top, "rev-parse", "-q", "--verify", "HEAD^{commit}") or ""
    found, moves = changes(top, old_tree, now_tree), head_back(top, held, now_head)
    cli.say("Restore point: %s · taken %s · on %s at %s" % (held.commit[:12], held.taken, held.branch,
                                                           held.head[:12] or "no commit yet"))
    if not found and not moves:
        cli.say("Since then: nothing changed — the files and the branch are as they were, so there is nothing to undo")
        return 0
    cli.say_all(since(found, held.head, now_head) + [
        "Undo: these commands, run in order in %s, put HEAD and every file back as they were before this run (the "
        "council home and ignored files stay as they are) and throw away all it changed — run them only on the "
        "owner's word:" % Path(top).as_posix()] + ["  " + line for line in moves + files_back(held, found)])
    return 0


def since(found: list[tuple[str, str]], head: str, now_head: str) -> list[str]:
    counts = {kind: sum(status == kind for status, _ in found) for kind in "AD"}
    named = [path for _, path in found[:SHOWN]] + ["and %d more" % (len(found) - SHOWN)] * (len(found) > SHOWN)
    moved = "; the branch moved from %s to %s" % (head[:12] or "no commit", now_head[:12] or "no commit") \
        if now_head != head else ""
    return ["Since then: %d file(s) differ, %d new, %d deleted%s%s" % (
        len(found), counts["A"], counts["D"], moved, (": " + ", ".join(named)) if found else "")]


def head_back(top: str, held: restore.Point, now_head: str) -> list[str]:
    """The commands that put HEAD back and touch no file: detached at the point's head when it was taken detached
    (whatever branch is current stays where it is); else the point's branch at its head (deleted when the repository
    had no commit yet), and HEAD on it."""
    current = git.text(top, "symbolic-ref", "-q", "HEAD")
    if held.branch == "(detached)":
        return [] if current is None and now_head == held.head else ["git update-ref --no-deref HEAD %s" % held.head]
    ref = "refs/heads/" + held.branch
    tip = git.text(top, "rev-parse", "-q", "--verify", ref + "^{commit}") or ""
    out = []
    if tip != held.head:
        out.append("git update-ref %s %s" % (shlex.quote(ref), held.head) if held.head else
                   "git update-ref -d %s" % shlex.quote(ref))
    if current != ref:
        out.append("git symbolic-ref HEAD %s" % shlex.quote(ref))
    return out


def files_back(held: restore.Point, found: list[tuple[str, str]]) -> list[str]:
    """The commands that put the files back: the run's new files removed, every other changed one written from the
    point's tree (the index holds it for that one step), then the index set to the point's HEAD. None of them names
    a path under the council home, so its files stay as they are on disk, tracked or not."""
    added = [path for status, path in found if status == "A"]
    out = ["rm -f -- " + " ".join(shlex.quote(path) for path in added[n:n + 20]) for n in range(0, len(added), 20)]
    if any(status != "A" for status, _ in found):
        out += ["git read-tree --reset %s" % held.commit, "git checkout-index -a -f"]
    return out + ["git read-tree --reset %s" % held.head if held.head else "git read-tree --empty"]
