"""council changed [--base <ref>] [--glob '<pattern>' …] [--each] [-- <command> …]: the files this change touches —
committed on this branch since its base, staged, unstaged, and new files git doesn't track yet. With no command it
lists them. With one it runs the command over them and passes when nothing matched, so a linter fitted to an old
project is green on day one and can only get stricter. --each runs the command once per file. Patterns are git
pathspecs, which know no {a,b}: '*.{js,jsx}' is read as '*.js' and '*.jsx'."""
from __future__ import annotations

import os
import subprocess

from council.commands import cli, shell
from council.records import home as where

USAGE = "usage: council changed [--base <ref>] [--glob '<pattern>'] [--each] -- <command> …"
LINE_BUDGET = 7000     # a Windows .cmd tool takes one command line of at most 8,191 characters


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "changed", "base", "code-root", "--")
    globs, each = options(words)
    top = args.value("code-root") or where.this_tree()
    try:
        os.chdir(where.native(top))
    except OSError:
        raise cli.Refusal("cannot enter the code root: %s" % top) from None
    if git("rev-parse", "--git-dir") is None:
        raise cli.Refusal("council changed needs a git repository")
    if globs and not any(git("ls-files", "--", g) or git("ls-files", "-o", "--exclude-standard", "--", g)
                         for g in globs):
        raise cli.Refusal(
            "the --glob pattern(s) %smatch no file in this project, so this check could never look at anything — fix "
            "the --glob (a git pathspec: case matters, and a pattern with a / in it is anchored at the repo root, so "
            "'src/*.py' covers every folder under a top-level src/ but not web/src/)" % "".join("'%s' " % g for g in globs))
    files = changed_files(base_of(args.value("base")), globs)
    if not files:
        cli.say("changed: no files matched — nothing to check (this is a pass, not a skip)")
        return 0
    if not args.after:
        for name in files:
            cli.say(name)
        return 0
    cli.warn("changed: %d file(s) to check" % len(files))
    if each:
        return max(shell.words(args.after + [name]) for name in files)
    return max(shell.words(args.after + batch) for batch in batches(files, len(" ".join(args.after))))


def options(words: list[str]) -> tuple[list[str], bool]:
    """The --glob patterns (each spelled out) and --each; any other word is a refusal."""
    globs, each, rest = [], False, list(words)
    while rest:
        word = rest.pop(0)
        if word == "--each":
            each = True
        elif word == "--glob":
            if not rest:
                raise cli.Refusal("--glob needs a pattern")
            globs += expand(rest.pop(0))
        elif word.startswith("--glob="):
            globs += expand(word[len("--glob="):])
        else:
            raise cli.Refusal(USAGE)
    return globs, each


def expand(pattern: str) -> list[str]:
    """glob_expand: one pattern per {a,b} choice, its first group (and those after it) spelled out; a nested
    group stays as written."""
    if not ("{" in pattern and "," in pattern.split("{", 1)[1] and "}" in pattern.split("{", 1)[1].split(",", 1)[1]):
        return [pattern]
    head, rest = pattern.split("{", 1)
    body, tail = rest.split("}", 1) if "}" in rest else (rest, rest)
    if "," not in body or "{" in body:
        return [pattern]
    found: list[str] = []
    while body:
        item, comma, body = body.partition(",")
        found += expand(head + item + tail)
        if comma and not body:
            found += expand(head + tail)
    return found


def git(*args: str) -> str | None:
    """git's stdout in this folder (names kept as they are: core.quotePath off), None when it fails."""
    try:
        done = subprocess.run(["git", "-c", "core.quotePath=false"] + list(args), stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    except OSError:
        return None
    return done.stdout.decode("utf-8", "surrogateescape") if done.returncode == 0 else None


def default_branch() -> str | None:
    """origin's HEAD when it is known, else the first of main, master, trunk and develop this repo has."""
    found = (git("symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD") or "").strip()
    if found:
        return found
    for name in ("main", "master", "trunk", "develop"):
        if git("rev-parse", "-q", "--verify", "refs/heads/" + name) is not None:
            return name
    return None


def base_of(given: str) -> str:
    """The commit the change is measured from — --base, else the run's recorded base when a gate runs this
    (COUNCIL_BASE), else where this branch left the default branch — said on stderr; '' when none is found."""
    recorded = os.environ.get("COUNCIL_BASE", "")
    if given or recorded:
        ref, said = (given, "--base " + given) if given else (recorded, "the run's recorded base")
        base = git("merge-base", "HEAD", ref) or git("rev-parse", "-q", "--verify", ref + "^{commit}")
        if base is None:
            raise cli.Refusal("council changed: '%s' (%s) is not a ref in this repository — the committed half of "
                              "the change would be skipped in silence" % (ref, said))
    else:
        ref = default_branch() or "HEAD"
        base, said = git("merge-base", "HEAD", ref) or "", "where this branch left " + ref
    base = base.strip()
    if not base:
        cli.warn("changed: uncommitted and new files only (no base found)")
    elif base == (git("rev-parse", "-q", "--verify", "HEAD") or "").strip():
        cli.warn("changed: uncommitted and new files only — the base, %s (%s), is the last commit; pass --base <ref> "
                 "to include commits" % (short(base), said))
    else:
        cli.warn("changed: files changed since %s (%s), plus uncommitted and new ones" % (short(base), said))
    return base


def short(commit: str) -> str:
    return (git("rev-parse", "--short", commit) or "").strip()


def changed_files(base: str, globs: list[str]) -> list[str]:
    """Committed since base, staged, unstaged and untracked (not ignored), once each in sorted order; the
    council's own files, deleted ones and anything that is no file left out. A name starting with - gets ./."""
    listed = git("diff", "--name-only", "--diff-filter=ACMR", base + "...HEAD", "--", *globs) or "" if base else ""
    listed += git("diff", "--name-only", "--diff-filter=ACMR", "HEAD", "--", *globs) or ""
    listed += git("ls-files", "-o", "--exclude-standard", "--", *globs) or ""
    files = []
    for name in sorted(set(listed.split("\n")), key=lambda n: n.encode("utf-8", "surrogateescape")):
        if name.startswith('"'):                  # git quotes an odd name
            name = name[1:-1] if name.endswith('"') and len(name) > 1 else name[1:]
        if not name or name.startswith(".council/") or not os.path.isfile(name):
            continue
        files.append("./" + name if name.startswith("-") else name)
    return files


def batches(files: list[str], command_length: int) -> list[list[str]]:
    """The files in runs that keep each command line well under Windows' 8,191 characters."""
    found, chunk, length, cap = [], [], 0, LINE_BUDGET - command_length
    for name in files:
        if chunk and length + len(name) + 3 > cap:
            found.append(chunk)
            chunk, length = [], 0
        chunk.append(name)
        length += len(name) + 3
    return found + [chunk]
