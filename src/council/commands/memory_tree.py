"""The code tree as `council memory` searches it: the files under a root (tracked and untracked, outside .council/;
outside git, every file), an anchor's path as it is there, the names the code still has, and the scope items that
match no file, seat or mode. Paths and names are C-locale text (records/bytewise.py), as the helper's awk read them.
A name is in the code when it is a whole word (no [A-Za-z0-9_] just before or after it) in one of the tree's files;
a file with a NUL byte or over paths.MAX_FILE is not searched."""
from __future__ import annotations

import os
import re
from typing import Iterable, Iterator

from council import git
from council.records import bytewise, paths, scope
from council.records import home as where
from council.records.closing import MODES
from council.records.memory_entries import cells

WORD = re.compile(r"[A-Za-z0-9_]+")
WORD_IN = re.compile(rb"[A-Za-z0-9_]+")


class Tree:
    """The files under `top` (a path as the helper writes it), and whether it is a git work tree."""

    def __init__(self, top: str) -> None:
        self.top = top
        native = where.native(top)
        self.git = git.run(native, "rev-parse", "--git-dir")[0] == 0
        if self.git:
            listed = git.run(native, "ls-files", "-co", "--exclude-standard", names=True)[1]
            self.files = [f for f in bytewise.records(bytewise.read(listed)) if not f.startswith(".council/")]
        else:
            self.files = _walk(native)
        self.blob = "\n" + "\n".join(self.files) + "\n"

    def path(self, p: str) -> str:
        """An anchor's path as it is under the root: itself, or the one file or folder whose path ends with it
        ("x.py", "services/risk.py" written short); '' when there is none."""
        if p == "":
            return ""
        if where.absolute(p):
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
        found: set[str] = set()
        for _, hits in self._search(names, self.files):
            found |= hits
            if found == names:
                break
        return found

    def find_in(self, names: set[str], files: set[str]) -> set[tuple[str, str]]:
        """(file, name) for every name that is in that file."""
        return {(f, name) for f, hits in self._search(names, sorted(files)) for name in hits}

    def _search(self, names: set[str], files: Iterable[str]) -> Iterator[tuple[str, set[str]]]:
        """Each file searched, with the names that are whole words in it. A name made of word characters only
        is one of the file's words; any other is matched with the whole-word rule itself."""
        words = {bytewise.bytes_of(n): n for n in names if WORD.fullmatch(n)}
        others = [(bytewise.bytes_of(n), n) for n in names if n and not WORD.fullmatch(n)]
        rules = [(b, n, re.compile(rb"(?<![A-Za-z0-9_])" + re.escape(b) + rb"(?![A-Za-z0-9_])")) for b, n in others]
        top = where.native(self.top)
        for f in files if names else ():
            full = os.path.join(top, where.native(bytewise.shown(f)))
            data = None if paths.too_large(full) else paths.contents(full)
            if data is None or b"\0" in data:
                continue
            hits = {words[w] for w in words.keys() & set(WORD_IN.findall(data))} if words else set()
            hits.update(n for b, n, rule in rules if b in data and rule.search(data))
            yield f, hits

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
        full = name if where.absolute(name) else top + "/" + name
        count = len(bytewise.records(bytewise.read(paths.contents(where.native(full)) or b"")))
        if count:
            out[f] = count
    return out


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
