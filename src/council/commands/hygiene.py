"""Just-me hygiene (references/run/sharing.md): the council's ids in what teammates read. On a just-me council a real
build left "(ruling 1)" in a code comment. Only what the build itself added is read: the lines added since its base
(with none, only uncommitted edits), files git doesn't track that changed after the run opened, whole, the commit
messages since the base that no remote branch has yet (one already pushed can't be changed), and a PR body drafted
in the run (<run>/pr-body*). Lines are read as bytes, as the helper's awk read them under LC_ALL=C."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import NamedTuple

from council import clock, git
from council.commands import resolve
from council.records import home as where

MIB = 1048576
EXCLUDE = ":(exclude).council"
RULES = (
    ("line", re.compile(rb"(^|[^A-Za-z0-9_.])\.council/"), "a .council/ path"),
    ("line", re.compile(rb"(^|[^0-9])20[0-9][0-9]-[01][0-9]-[0-3][0-9]-[0-9]{6}-[a-z]"), "a council run folder"),
    ("low", re.compile(rb"(^|[^a-z])rulings? [0-9]"), "a council ruling"),
    ("line", re.compile(rb"(^|[^A-Za-z0-9_-])verify-[0-9]+[a-z]?([^A-Za-z0-9_]|$)"), "a council verifier file"),
    ("said", re.compile(rb"(^|[^A-Za-z0-9_-])(AP|EC|D|F)-[0-9]+([^A-Za-z0-9_]|$)"), "a council id (D-, F-, AP-, EC-)"),
    ("lsaid", re.compile(rb"\((see |per |from |in )?tasks? [0-9]+[a-z]?[),;& ]|(council|plan|build)('s)? tasks? [0-9]"),
     "a council task"),
)
PROSE = re.compile(rb".*\.(md|markdown|mdx|txt|rst|adoc|org)", re.S)


class Hit:
    """One council reference: where (path:line, commit <sha>:line, PR body <file>:line), what kind, the line."""

    def __init__(self, place: str, what: str, line: bytes) -> None:
        self.place, self.what, self.line = place, what, line


class Line(NamedTuple):
    place: bytes
    number: int
    text: bytes


def _commit(top: str, rev: str) -> bool:
    return bool(rev) and git.run(top, "rev-parse", "-q", "--verify", rev + "^{commit}", names=True)[0] == 0


def base(run: Path, top: str, given: str) -> str:
    """The commit a build's own work starts from: --base when given; else the run's index base, unless that
    reaches back past the commit HEAD was at when the run opened (the index base is the merge-base, so a branch's
    earlier work would be read as this run's) — then that commit. '' when neither is on record."""
    if given:
        return given
    indexed, start = resolve.field(run, "base"), resolve.field(run, "start-head")
    top = where.native(top)
    if not os.path.isdir(top):
        return ""
    indexed = indexed if _commit(top, indexed) else ""
    start = start if _commit(top, start) else ""
    if indexed and start and git.run(top, "merge-base", "--is-ancestor", indexed, start, names=True)[0] == 0:
        indexed = ""
    return indexed or start


def _records(data: bytes) -> list[bytes]:
    found = data.split(b"\n")
    return found[:-1] if found and found[-1] == b"" else found


def _file_lines(path: str) -> list[bytes]:
    try:
        data = Path(path).read_bytes()
    except OSError:
        return []
    return [line[:-1] if os.name == "nt" and line.endswith(b"\r") else line for line in _records(data)]


def added(top: str, since: str) -> list[Line]:
    """The lines a diff from `since` (HEAD when none) adds, numbered as they now stand."""
    found, place, head, number = [], b"", False, 0
    diff = git.run(top, "diff", "-M", "-U0", "--no-color", "--no-ext-diff", since, "--", ".", EXCLUDE, names=True)[1]
    for line in _records(diff):
        if line.startswith(b"diff --git "):
            head, place = True, b""
        elif head and line.startswith(b"+++ "):
            place = re.sub(rb'^"|"$', b"", line[4:])
            place = place[2:] if place.startswith(b"b/") else place
            place = b"" if place == b"/dev/null" else place
        elif line.startswith(b"@@"):
            head = False
            mark = re.search(rb"\+[0-9]+", line)
            number = int(mark.group(0)[1:]) if mark else number
        elif not head and line.startswith(b"+"):
            if place:
                found.append(Line(place, number, line[1:]))
            number += 1
    return found


def _text_file(path: str) -> bool:
    """grep -qI -e '': a file with something in it, up to 1 MiB, with no NUL in its first 32 KiB."""
    try:
        size = os.path.getsize(path)
        if not 0 < size <= MIB:
            return False
        with open(path, "rb") as handle:
            return b"\0" not in handle.read(32768)
    except OSError:
        return False


def untracked(top: str, since: float | None) -> list[Line]:
    """Files git doesn't track, changed after the run opened (with no opened: time, all of them), whole."""
    found = []
    for name in _records(git.run(top, "ls-files", "-o", "--exclude-standard", names=True)[1]):
        if name.startswith(b".council/") or name.endswith(b"/"):
            continue
        path = os.path.join(top, os.fsdecode(name))
        try:
            if since is not None and not os.stat(path).st_mtime > since:
                continue                    # there before the run: not its work
        except OSError:
            continue
        if _text_file(path):
            found += [Line(name, n, line) for n, line in enumerate(_file_lines(path), 1)]
    return found


def unpushed(top: str, since: str) -> list[Line]:
    """The commit messages since the base that no remote branch has yet."""
    branch = git.run(top, "symbolic-ref", "-q", "--short", "HEAD", names=True)[1].strip()
    pushed = git.run(top, "rev-parse", "-q", "--verify", "@{upstream}", names=True)[1].split()
    if branch:
        pushed += git.run(top, "rev-parse", "-q", "--verify", "refs/remotes/origin/" + os.fsdecode(branch),
                          names=True)[1].split()
    done = ["--not"] + [os.fsdecode(sha) for sha in pushed] if pushed else []
    found, sha, number = [], b"", 0
    log = git.run(top, "log", "--no-merges", "--format=@@commit %h%n%B", since + "..HEAD", *done, names=True)[1]
    for line in _records(log):
        if line.startswith(b"@@commit "):
            sha, number = (line.split() + [b""])[1], 0
            continue
        number += 1
        found.append(Line(b"commit " + sha, number, line))
    return found


def _bodies(run: Path) -> list[Line]:
    """A PR body drafted in the run (<run>/pr-body*), whole."""
    found = []
    try:
        names = sorted(name for name in os.listdir(run) if name.startswith("pr-body"))
    except OSError:
        return []
    for name in names:
        if os.path.isfile(os.path.join(run, name)):
            lines = _file_lines(os.path.join(run, name))
            found += [Line(b"PR body " + os.fsencode(name), n, line) for n, line in enumerate(lines, 1)]
    return found


def _read(run: Path, top: str, since: str, opened: str) -> list[Line]:
    top, found = where.native(top), []
    if os.path.isdir(top) and git.run(top, "rev-parse", "--git-dir", names=True)[0] == 0:
        since = since if _commit(top, since) else ""
        if _commit(top, since or "HEAD"):
            found += added(top, since or "HEAD")
        moment = clock.local_moment(opened)                  # the helper's local stamp, seconds or not
        found += untracked(top, moment.timestamp() if moment else None)
        if since:
            found += unpushed(top, since)
    return found + _bodies(run)


def _said(text: bytes) -> bytes:
    """The part of a code line that a comment holds; b'' when none does."""
    found = re.search(rb"(^|[^:])//", text)
    if found:
        return text[found.start():]
    for mark in (b"/*", b"<!--"):
        if mark in text:
            return text[text.index(mark):]
    bare = re.sub(rb"^[ \t]+", b"", text)
    if re.match(rb"(\*|#|--|;|%)", bare):
        return bare
    found = re.search(rb"[ \t]#[ \t]", text)
    return text[found.start():] if found else b""


def kind(place: bytes, text: bytes) -> str:
    """What council reference a line holds, the first rule that fits ('' for none). A decision, failure,
    anti-pattern or edge-case id and a task named as the council names it count only in comments and prose."""
    text = text.replace(b"\r", b"")
    prose = place.startswith((b"commit ", b"PR body ")) or PROSE.fullmatch(place.lower()) is not None
    said = text if prose else _said(text)
    forms = {"line": text, "low": text.lower(), "said": said, "lsaid": said.lower()}
    for form, rule, what in RULES:
        if rule.search(forms[form]):
            return what
    return ""


def hits(run: Path, top: str, since: str, opened: str) -> list[Hit]:
    """Every council reference in what the build added, in the order read: the diff, untracked files, commit
    messages, PR bodies. The line is cut at 120 bytes."""
    found = []
    for line in _read(run, top, since, opened):
        what = kind(line.place, line.text)
        if what:
            place = os.fsdecode(line.place) if os.name != "nt" else line.place.decode("utf-8", "surrogateescape")
            found.append(Hit("%s:%d" % (place, line.number), what, line.text.replace(b"\r", b"")[:120]))
    return found
