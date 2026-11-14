"""The code tree as `council memory` searches it: the files under a root (tracked and untracked, outside .council/;
outside git, every file), an anchor's path as it is there, the names the code still has, and the scope items that
match no file, seat or mode. Paths and names are C-locale text (records/bytewise.py), as the helper's awk read them;
the searches are the helper's own git grep and grep, so a whole word means what it meant there."""
from __future__ import annotations

import contextlib
import os
import re
import shutil
import subprocess

from council.records import bytewise, scope
from council.records import home as where
from council.records.memory_entries import cells

MODES = ("council-review", "council-plan", "council-implement", "council-research", "council-postgame")
_WORD = re.compile(r"[A-Za-z0-9_]")


class Tree:
    """The files under `top` (a path as the helper writes it), and whether it is a git work tree."""

    def __init__(self, top: str) -> None:
        self.top = top
        native = where.native(top)
        self.git = _run(["git", "-C", native, "rev-parse", "--git-dir"])[0] == 0
        if self.git:
            listed = _run(["git", "-C", native, "-c", "core.quotepath=off", "ls-files", "-co", "--exclude-standard"])[1]
            self.files = [f for f in bytewise.records(bytewise.read(listed)) if not f.startswith(".council/")]
        else:
            self.files = _walk(native)
        self.blob = "\n" + "\n".join(self.files) + "\n"

    def path(self, p: str) -> str:
        """An anchor's path as it is under the root: itself, or the one file or folder whose path ends with it
        ("x.py", "services/risk.py" written short); '' when there is none."""
        if p == "":
            return ""
        if p.startswith("/") or re.match(r"[A-Za-z]:", p):
            if os.path.exists(where.native(bytewise.shown(p))):
                return p
            top = bytewise.text(self.top) + "/"
            p = p[len(top):] if p.startswith(top) else p
        if os.path.exists(where.native(self.top + "/" + bytewise.shown(p))):
            return p
        if "/" + p + "\n" not in self.blob and "/" + p + "/" not in self.blob:
            return ""
        for f in [""] + self.files:
            n = len(f) - len(p)
            if n > 0 and f[n - 1:] == "/" + p:
                return f
            i = f.find("/" + p + "/")
            if i >= 0:
                return f[:i + 1 + len(p)]
        return ""

    def find(self, names: set[str]) -> set[str]:
        """The names (one search for all of them) that are in the code as whole words."""
        if not names:
            return set()
        with _patterns(names) as pat:
            words = ["grep", "-h", "-o", "-w", "-F", "-f", pat]
            tail = ["--untracked", "--", ".", ":(exclude).council"] if self.git else \
                ["--no-index", "--", ".", ":(exclude).council", ":(exclude).git"]
            code, out = _run(["git"] + words + tail, cwd=where.native(self.top))
            if code > 1:
                out += _grep(["-r", "-h", "-o", "-w", "-F", "-f", pat, "--exclude-dir=.git", "--exclude-dir=.council",
                              "."], self.top)
        return set(bytewise.records(bytewise.read(out)))

    def find_in(self, names: set[str], files: set[str]) -> set[tuple[str, str]]:
        """(file, name) for every name that is in that file."""
        if not names or not files:
            return set()
        out = b""
        with _patterns(names) as pat:
            listed = sorted(files)
            for at in range(0, len(listed), 100):
                out += _grep(["-H", "-o", "-w", "-F", "-f", pat, "--"]
                             + [bytewise.shown(f) for f in listed[at:at + 100]], self.top)
        found = set()
        for line in bytewise.records(bytewise.read(out)):
            if ":" in line:
                head, _, name = line.rpartition(":")
                found.add((head, name))
        return found

    def orphans(self, found: list[str], slugs: list[str]) -> list[str]:
        """The lines for every scope item that matches no file, seat slug or mode."""
        known = [s for s in slugs + list(MODES) if s != ""]
        roster = bool(slugs)
        out, seen = [], set()
        for row in found:
            c = cells(row)
            if c[4] not in ("settled", "observed") or c[2] == "-" or scope.everyrun(c[2]):
                continue
            listed = scope.items(c[2])
            hit = [g.text in known for g in listed]
            for i, g in enumerate(listed):
                if hit[i]:
                    continue
                if not re.search(r"[/.*?{\[]", g.text) and not roster:
                    continue                                    # no roster to judge a word by
                hit[i] = any(scope.covers(f, g.text, ".*", False) for f in self.files)
            for i, g in enumerate(listed):
                if hit[i] or _bare(g.text, roster) or (g.piece_of and hit[g.piece_of - 1]):
                    continue
                if g.whole and _pieces_hit(i + 1, listed, hit):
                    continue
                if g.text not in seen:
                    seen.add(g.text)
                    out.append('memory: scope item "%s" (%s) matches no file, seat or mode — check its spelling, or '
                               "drop it when the folder is gone" % (bytewise.shown(g.text), bytewise.shown(c[0])))
        return out


def _bare(g: str, roster: bool) -> bool:
    return not roster and not re.search(r"[/.*?{\[]", g)


def _pieces_hit(whole: int, listed: list[scope.Item], hit: list[bool]) -> bool:
    pieces = [hit[i] for i, g in enumerate(listed) if g.piece_of == whole]
    return bool(pieces) and all(pieces)


def line_counts(top: str, files: set[str]) -> dict[str, int]:
    """Each file's line count as awk counts records (none for an empty or unreadable file)."""
    out = {}
    for f in files:
        name = bytewise.shown(f)
        full = name if name.startswith("/") or re.match(r"[A-Za-z]:", name) else top + "/" + name
        try:
            with open(where.native(full), "rb") as stream:
                count = len(bytewise.records(bytewise.read(stream.read())))
        except OSError:
            continue
        if count:
            out[f] = count
    return out


def _run(words: list[str], cwd: str | None = None) -> tuple[int, bytes]:
    try:
        done = subprocess.run(words, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        return 127, b""
    return done.returncode, done.stdout


def _grep(words: list[str], top: str) -> bytes:
    """grep as the helper ran it; without one on PATH, the same whole-word search done here."""
    if shutil.which("grep"):
        return _run(["grep"] + words, cwd=where.native(top))[1]
    return _search(words, top)


def _search(words: list[str], top: str) -> bytes:
    pat = words[words.index("-f") + 1]
    with open(pat, "rb") as stream:
        names = [n for n in stream.read().split(b"\n") if n]
    named = "-H" in words
    files = words[words.index("--") + 1:] if named else _walk(where.native(top))
    out = []
    for f in files:
        try:
            with open(os.path.join(where.native(top), f), "rb") as stream:
                data = stream.read()
        except OSError:
            continue
        if b"\0" in data:
            continue
        for name in names:
            if re.search(rb"(?<![A-Za-z0-9_])" + re.escape(name) + rb"(?![A-Za-z0-9_])", data):
                out.append((f.encode("utf-8", "surrogateescape") + b":" if named else b"") + name)
    return b"".join(line + b"\n" for line in out)


def _walk(top: str) -> list[str]:
    """Every file under top, outside .git/ and .council/, as find lists them (./ taken off)."""
    out = []
    for folder, dirs, files in os.walk(top):
        rel = os.path.relpath(folder, top).replace("\\", "/")
        if rel in (".git", ".council") or rel.startswith((".git/", ".council/")):
            dirs[:] = []
            continue
        for name in files:
            p = name if rel == "." else rel + "/" + name
            out.append(bytewise.text(p))
    return out


class _patterns:
    """A pattern file for grep -f, one name a line, removed after."""

    def __init__(self, names: set[str]) -> None:
        self.names = names
        self.path = ""

    def __enter__(self) -> str:
        import tempfile                                 # only a search with names needs it (D34)
        handle, self.path = tempfile.mkstemp(prefix="council-names-")
        with os.fdopen(handle, "wb") as stream:
            stream.write(b"".join(bytewise.bytes_of(n) + b"\n" for n in sorted(self.names)))
        return self.path

    def __exit__(self, *_: object) -> None:
        with contextlib.suppress(OSError):
            os.remove(self.path)
