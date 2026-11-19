"""council restore point | restore show [--run <folder>]: a run's restore point (D57).

council restore point records, before a run changes the project, a commit of the code root's files as they are now —
committed, staged, unstaged and untracked alike; what .gitignore ignores and the council home left out — made with git
commit-tree, so no branch, index or file moves, and kept by a ref, refs/council/restore/<run>. It writes
<run>/restore.md and nothing else, and refuses a second point for the same run. council restore show prints the
point, what changed since, and the commands that put every file back as it was: printed, never run, since restoring
throws away what the run did and is the owner's call."""
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


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "restore")
    if words not in (["point"], ["show"]):
        raise cli.Refusal(USAGE)
    run = resolve.run_folder(args)
    top = where.native(resolve.field(run, "code-root") or where.this_tree())
    if git.text(top, "rev-parse", "--is-inside-work-tree") != "true":
        raise cli.Refusal("the code root is not a git repository, so no restore point can be taken — recommend "
                          "`git init` to the owner; if they decline, copy each file to %s/backup/<path> before its "
                          "first change, and say so on the report's Undo line" % run.as_posix())
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
    try:
        restore.write(run, restore.Point(commit, head, branch, clock.now_sec()))
    except OSError as failure:
        raise cli.Refusal("cannot write %s/%s (%s)" % (run.as_posix(), restore.NAME, failure)) from None
    loose = bool(head) and git.text(top, "rev-parse", head + "^{tree}") != tree
    cli.say("Restore point: %s — the code root's files as they are now%s, kept as %s%s; nothing in the project moved. "
            "How to go back to it: council restore show" % (
                commit[:12], " (with the uncommitted work)" if loose else "", restore.REF, run.name))
    return 0


def changes(top: str, old_tree: str, new_tree: str) -> list[tuple[str, str]]:
    """(status, path) for each file that differs between two trees: A new, M changed, D deleted, T its type."""
    code, out = git.run(top, "diff", "--name-status", "--no-renames", "-z", old_tree, new_tree, *git.between(),
                        names=True)
    if code:
        raise cli.Refusal("git could not compare the files with the restore point (git diff exit %d)" % code)
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
                          "command can bring it back" % (held.commit[:12], restore.REF, run.name))
    now_head = git.text(top, "rev-parse", "-q", "--verify", "HEAD^{commit}") or ""
    found = changes(top, old_tree, git.files_tree(top) or old_tree)
    cli.say("Restore point: %s · taken %s · on %s at %s" % (held.commit[:12], held.taken, held.branch,
                                                           held.head[:12] or "no commit yet"))
    if not found and now_head == held.head:
        cli.say("Since then: nothing changed — the files and the branch are as they were, so there is nothing to undo")
        return 0
    cli.say_all(since(found, held.head, now_head) + [
        "Undo: these commands, run in %s, put every file back as it was before this run and throw away all it "
        "changed — run them only on the owner's word:" % Path(top).as_posix()] + [
        "  " + line for line in commands(top, held, old_tree, found, now_head)])
    return 0


def since(found: list[tuple[str, str]], head: str, now_head: str) -> list[str]:
    counts = {kind: sum(status == kind for status, _ in found) for kind in "AD"}
    named = [path for _, path in found[:SHOWN]] + ["and %d more" % (len(found) - SHOWN)] * (len(found) > SHOWN)
    moved = "; the branch moved from %s to %s" % (head[:12] or "no commit", now_head[:12] or "no commit") \
        if now_head != head else ""
    return ["Since then: %d file(s) differ, %d new, %d deleted%s%s" % (
        len(found), counts["A"], counts["D"], moved, (": " + ", ".join(named)) if found else "")]


def commands(top: str, held: restore.Point, old_tree: str, found: list[tuple[str, str]], now_head: str) -> list[str]:
    """The undo, in order: the branch and tracked files back to the point's HEAD, the point's own files back on top
    when it held uncommitted work, then the files the run added removed."""
    out = []
    branch = git.text(top, "symbolic-ref", "-q", "--short", "HEAD") or "(detached)"
    if branch != held.branch and held.branch != "(detached)":
        out.append("git switch %s" % shlex.quote(held.branch))
    if held.head or now_head:
        out.append("git reset -q --hard %s" % held.head if held.head else "git update-ref -d HEAD")
    if not held.head or git.text(top, "rev-parse", held.head + "^{tree}") != old_tree:
        out += ["git checkout %s -- :/" % held.commit, "git reset -q" if held.head else "git read-tree --empty"]
    added = [path for status, path in found if status == "A"]
    out += ["rm -f -- " + " ".join(shlex.quote(path) for path in added[n:n + 20]) for n in range(0, len(added), 20)]
    return out
