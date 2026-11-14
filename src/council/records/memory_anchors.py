"""What each memory entry's **Anchor:** names, as rows `council memory check` works through in one pass (the
helper's anchor_rows):

    <id> <anchor> C <path> <lines>   a file and the lines it names
    <id> <anchor> F <path>           a file (it has a folder in it)
    <id> <anchor> X <name>           a file, or a name written with dots (process.env, request.json)
    <id> <anchor> N <path> <name>    a name inside that file
    <id> <anchor> S <name>           a name in the code

An **Anchor:** list is split at commas and semicolons, except that a piece which is only a line or a range ("3",
"40-55") belongs to the path:line before it, as it would in a citation. A link gives its target; res://, ./ and a
trailing . go; #L5 is line 5. "fetch() in a.py", "a.py::fetch", "a.py:5 (fetch)", "a.py:fetch", "a.py - fetch" and
"a.py fetch" all name a symbol in a file. Rows and text are C-locale (records/bytewise.py)."""
from __future__ import annotations

import re

from council.records.bytewise import ARROW, EM, EN, lower, trim
from council.records.memory_entries import cells

_EXT = re.compile(
    r"\.(py|pyi|pyx|js|jsx|mjs|cjs|ts|tsx|gd|gdshader|tscn|tres|godot|cs|java|kt|kts|go|rs|rb|php|swift|c|h|cc|cpp"
    r"|cxx|hpp|sh|bash|ps1|bat|cmd|sql|md|mdx|rst|txt|json|jsonc|yml|yaml|toml|ini|cfg|conf|xml|html|htm|css|scss"
    r"|sass|less|vue|svelte|lock|csv|ipynb|lua|dart|ex|exs|scala|tf|proto|graphql|gradle|env)\Z")
_NOTHING = re.compile(r"(none|n/a|na|tbd|-|" + EM + "|" + EN + r"|\(none\))\Z")
_NAMED = re.compile(r"[A-Za-z_][A-Za-z0-9_.:#-]*(\(\))?\Z")
_NOTE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*(\(\))?\Z")


def clean(p: str) -> str:
    p = re.sub(r"\A[Rr][Ee][Ss]://", "", trim(p).replace("\\", "/"), count=1)
    while p.startswith("./"):
        p = p[2:]
    return p


def nm(s: str) -> str:
    s = re.sub(r"\(.*\)\Z", "", trim(s), count=1, flags=re.S)
    return trim(re.sub("[`\"]", "", s))


def pathy(p: str) -> bool:
    return "/" in p or bool(_EXT.search(lower(p)))


class Rows:
    """The rows printed, and the path the last place() found (the awk's P)."""

    def __init__(self) -> None:
        self.out: list[str] = []
        self.p = ""

    def emit(self, *fields: str) -> None:
        self.out.append("\t".join(fields))

    def place(self, entry: str, raw: str, p: str) -> None:
        p = clean(p)
        found = re.search(r"#[Ll]?[0-9]+(-[Ll]?[0-9]+)?\Z", p)
        if found:
            self.p = p[:found.start()]
            self.emit(entry, raw, "C", self.p, re.sub("[Ll]", "", p[found.start() + 1:]))
            return
        p = re.sub(r"#.*\Z", "", p, count=1, flags=re.S)
        found = re.search(r":[0-9][0-9, \t-]*\Z", p)
        if found:
            self.p = p[:found.start()]
            self.emit(entry, raw, "C", self.p, re.sub("[ \t]", "", p[found.start() + 1:]))
            return
        self.p = p
        self.emit(entry, raw, "F" if "/" in p else "X", p)

    def named_in(self, entry: str, raw: str, where: str, name: str) -> None:
        """A name inside a file: the file's row, then the name's."""
        self.place(entry, raw, where)
        self.emit(entry, raw, "N", self.p, nm(name))

    def parse(self, entry: str, raw: str) -> None:
        a = _target(trim(raw.replace("\r", "")))
        a = trim(re.sub(r"[ \t.,;:]+\Z", "", re.sub("[`\"]", "", a), count=1))
        if a == "" or _NOTHING.match(lower(a)):
            return
        a = re.sub(EN + "|" + EM, "-", a).replace(ARROW, " ")
        a = re.sub(r"[ \t]->[ \t]|[ \t]=>[ \t]", " ", a)
        note = ""
        found = re.search(r"[ \t]+\([^()]*\)\Z", a)
        if found:
            note, a = trim(a[found.start():])[1:-1], trim(a[:found.start()])
        if self.split_name(entry, raw, a):
            return
        if "/" in a or re.search(r":[0-9]", a) or re.search(r"#[Ll]?[0-9]", a) or pathy(a) or a.startswith("res:"):
            self.place(entry, raw, a)
            if _NOTE_NAME.match(note):
                self.emit(entry, raw, "N", self.p, nm(note))
            return
        self.emit(entry, raw, "S", nm(a))

    def split_name(self, entry: str, raw: str, a: str) -> bool:
        """A symbol named in a file, in any of the ways the docstring lists; False when `a` is none of them."""
        found = re.search(r"[ \t]in[ \t]+[^ \t]+\Z", a)
        if found:
            p = re.sub(r"\Ain[ \t]+", "", a[found.start() + 1:], count=1)
            if pathy(clean(p)):
                self.emit(entry, raw, "N", clean(p), nm(a[:found.start()]))
                return True
        i = a.find("::")
        if i > 0 and pathy(clean(a[:i])):
            self.named_in(entry, raw, a[:i], a[i + 2:])
            return True
        if re.search("[ \t]", a):                               # "path - name", "path name"
            w = re.sub(r"[ \t]+-?[ \t]*[^ \t]+\Z", "", a, count=1)
            t = re.sub(r"\A.*[ \t]", "", a, count=1, flags=re.S)
            if (not re.search("[ \t]", w) and pathy(clean(w)) and not re.search(r":[0-9]", clean(w))
                    and _NAMED.match(t) and not pathy(t)):
                self.named_in(entry, raw, w, t)
                return True
        if re.match(r"[^ \t:]+:[A-Za-z_]", a) and pathy(clean(a[:a.find(":")])):
            i = a.find(":")                                     # "scripts/x.gd:_teardown_move"
            self.named_in(entry, raw, a[:i], a[i + 1:])
            return True
        return False


def _target(a: str) -> str:
    """A markdown link's target, when it is no web address (res:// is a file)."""
    found = re.search(r"\[[^\]]*\]\([^)]*\)", a)
    if not found:
        return a
    t = re.sub(r"\)\Z", "", re.sub(r"\A\[[^\]]*\]\(", "", found.group(0), count=1), count=1)
    return t if not re.match(r"[a-z]+://", t) or t.startswith("res:") else a


def rows(found: list[str]) -> list[str]:
    """The anchor rows of the memory rows `found`: every settled or observed entry that names an anchor."""
    out = Rows()
    for row in found:
        c = cells(row)
        if c[4] not in ("settled", "observed") or c[3] == "-":
            continue
        cur = ""
        for piece in c[3].replace(";", ",").split(","):
            p = trim(piece).replace(EN, "-")
            if p == "":
                continue
            if re.search(r":[0-9]", cur) and re.fullmatch(r"[0-9]+([ \t]*-[ \t]*[0-9]+)?", p):
                cur = cur + "," + piece                         # as written
                continue
            if trim(cur) != "":
                out.parse(c[0], trim(cur))
            cur = piece
        if trim(cur) != "":
            out.parse(c[0], trim(cur))
    return out.out


def read_fields(line: str, n: int) -> list[str]:
    """`IFS=<tab> read -r` into n names: leading and trailing tabs dropped, a run of tabs one break, the last name
    given the rest of the line."""
    rest = line.strip("\t")
    out = []
    while len(out) < n - 1 and rest:
        head, sep, tail = rest.partition("\t")
        out.append(head)
        rest = tail.lstrip("\t") if sep else ""
    out.append(rest.rstrip("\t") if len(out) < n else "")
    return out + [""] * (n - len(out))
