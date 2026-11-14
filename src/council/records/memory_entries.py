"""The memory file's entries, read as the helper's memory_entries awk reads them (bin/council keeps that awk for the
session-start hook and run open; tests/py/test_memory_entries.py holds the two to the same rows).

An entry is a heading (## to ####), a top-level bullet or a numbered item whose bold text starts with its id
("### AP-3: title", "- **AP-3 — title.** text …", "1. **AP-3 — title.**"), the id in any case, with or without its
dash. Its **Scope:** and **Anchor:** may sit anywhere in its body. Each entry is one row of ten tab-separated
columns — id, title, scope, anchor, state, section, meaning, origin, evidence, verdict ("-" when empty) — where state
is settled (Accepted Patterns, Enforced Conventions, Decisions… and the top of the file), observed (an F- entry
under Observed Failures with all an observed failure needs), off (Proposed, Rejected, Retired…, or marked retired)
or unknown (any other section, or an F- entry that lacks something; the reason in its section column). The rows are
the awk's printed lines, C-locale text (records/bytewise.py): a section name holding a tab shifts the columns there
too. skipped() names the lines that open like an entry but are not read."""
from __future__ import annotations

import re

from council.records import bytewise
from council.records.bytewise import EM, EN, lower, trim, upper

OFF = ["propos", "reject", "retire", "supersede", "deprecat", "withdraw", "obsolete", "archived", "pending", "draft",
       "declined", "revoked"]
SET = ["accepted", "enforced", "decision", "convention", "pattern", "adopted", "settled", "ruling"]
MARKS = ("retired", "superseded", "withdrawn")
MEANINGS = ("Pattern", "Rule", "Convention", "Decision", "Failure", "Observation")
VERDICTS = ("OBSERVED", "REPRODUCED", "CONFIRMED", "REFUTED", "MISCITED", "REGRESSION", "INCOMPLETE", "SCOPE-CREEP")
VERDICT_LIST = "OBSERVED, REPRODUCED, CONFIRMED, REFUTED, MISCITED, REGRESSION, INCOMPLETE or SCOPE-CREEP"
BOM = bytewise.read(b"\xef\xbb\xbf")
_DOT = bytewise.DOT
_ID = re.compile(r"(ap|ec|d|f)-?[0-9]+")
_ASIDE = re.compile(r"[ \t]*(" + EM + "|" + EN + r"|-[ \t]|\(|\[|;|:|,).*\Z", re.S)
_CAND_REST = re.compile(r"[*_~`]*([ \t]*([:.)]|" + EM + "|" + EN + r"|-[ \t])|[ \t]*\Z)")
_EVERY = re.compile(r"(all|all files|everywhere|every run|always|global|any|repo-wide|project-wide|whole repo|none|n/a"
                    r"|\(none\)|\*|\*\*|\*\*/\*|\*\*/\*\*|-|" + EM + "|" + EN + r")\Z")
_BLANK = re.compile(r"(-+|" + EM + "|" + EN + r"|none|n/a|na|tbd|todo|\?+|\.\.\.|" + bytewise.ELLIPSIS + r")\Z")
_FIELD = re.compile(r"\*\*[A-Za-z][^*]*(:\*\*|\*\*:)")
_NOT_RETIRED = re.compile(r"(no|none|n/a|-|false|never|not yet|" + EM + "|" + EN + r")\Z")
_RETIRED_TITLE = re.compile(r"\A[(\[](retired|superseded|withdrawn)|\A(retired|superseded|withdrawn)[ \t]*"
                            r"[-:.\xe2\x80\x94\x93]|[(\[](retired|superseded|withdrawn)[^)\]]*[)\]][ \t]*\Z")
_REST_OPEN = re.compile(r"[ \t]*(" + EM + "|" + EN + r"|-|:|\.|\))?[ \t]*")
_UNDASHED = re.compile(r"([*_~]|[:.)]|[ \t]+(" + EM + "|" + EN + r"|-|:)|[ \t]*\Z)")
_RULE = re.compile(r"[ \t]*(([-*_][ \t]*)([-*_][ \t]*)([-*_][ \t]*)+|=+[ \t]*)\Z")
_FIELD_OPENS = re.compile(r"[ \t]*(" + _DOT + r"[ \t]*)?\*\*[A-Za-z][^*]*(:\*\*|\*\*:)")


def kind(t: str, strict: bool = False) -> str:
    """A section name: off, settled, observed, or "" (says neither). What the section calls itself — the words
    before its first aside — decides; an aside only speaks when the name says nothing. A sub-heading or a bold
    label is read by its first word alone."""
    lo = re.sub(r"\A[^a-z0-9]+", "", re.sub(r"[*_~`#]", "", lower(t)))
    h = trim(_ASIDE.sub("", lo, count=1))
    if strict:
        w = re.sub(r"[ \t].*\Z", "", h, count=1, flags=re.S)
        if any(off in w for off in OFF):
            return "off"
        if w in ("observed", "failures"):
            return "observed"
        if re.fullmatch(r"(ap|ec|d)s?", w) or any(s in w for s in SET):
            return "settled"
        return ""
    if any(off in h for off in OFF):
        return "off"
    if re.match(r"(observed failures|failure history|failures)([ \t]|\Z)", h):
        return "observed"
    if re.fullmatch(r"(ap|ec|d)s?", h) or re.search(r"\((ap|ec|d)\)", lo) or any(s in h for s in SET):
        return "settled"
    if any(off in lo for off in OFF):
        return "off"
    return "settled" if any(s in lo for s in SET) else ""


def idnorm(s: str) -> str:
    """An id as one form: upper case, with its dash."""
    t = upper(s)
    return t if "-" in t else re.sub(r"([0-9]+)\Z", r"-\1", t, count=1)


def vword(v: str) -> str:
    """The first word of a verdict ("Refuted — see verify-2.md" is REFUTED; SCOPE-CREEP keeps its dash)."""
    found = re.match(r"[A-Z]+(-[A-Z]+)*", re.sub(r"\A[^A-Z]+", "", upper(v), count=1))
    return found.group(0) if found else ""


def wholescope(s: str) -> bool:
    """Does any item of a scope reach every run?"""
    for piece in re.split(r"[,;]", s):
        t = lower(trim(piece))
        if t == "":
            continue
        t = trim(re.sub(r"\A/+", "", re.sub(r"[.`\"']", "", t), count=1))
        if t == "" or _EVERY.match(t):
            return True
    return False


def blank(v: str) -> bool:
    """A field left as a placeholder ("-", "none", "tbd", "?") says nothing."""
    t = trim(re.sub(r"[`\"']", "", lower(trim(v))))
    return t == "" or bool(_BLANK.match(t))


def fieldval(line: str, name: str) -> str:
    """The value after **Name:** on a line, up to a following " · **Other:**"."""
    at = line.find("**" + name + ":**")
    if at < 0:
        return ""
    v = line[at + len(name) + 5:]
    v = re.sub(r"[ \t]+" + _DOT + r"[ \t]+\*\*.*\Z", "", v, count=1, flags=re.S)
    v = re.sub(r"\A[ \t]+|[ \t\r]+\Z", "", v)
    return v.replace("`", "").replace("\t", " ")


def cleantitle(t: str) -> str:
    t = trim(re.sub(r"[ \t]+", " ", t.replace("~~", "")))
    return re.sub(r"[.:]\Z", "", t, count=1)


class Parser:
    """One pass over a memory file's lines, as the awk keeps its state."""

    def __init__(self) -> None:
        self.rows: list[str] = []
        self.read: set[str] = set()
        self.cands: list[tuple[str, int]] = []
        self.sec, self.secname, self.sub_st, self.sublvl, self.subname, self.elvl = "settled", "", "", 0, "", 0
        self.id = self.title = self.scope = self.anchor = self.est = self.ewhere = ""
        self.meaning = self.failure = self.origin = self.evidence = self.verdict = self.para = self.fbefore = ""
        self.ptitle = self.after = ""
        self.bul = self.pend = self.incom = self.fence = self.anyhead = self.bodyline = False
        self.pn = 0
        self.n = 0

    # -- the awk's functions -------------------------------------------------------------------------------
    def cand(self, txt: str) -> bool:
        """A line that opens like an entry: recorded, so that it can be named if it is not read as one."""
        lo2 = re.sub(r"\A[*_~`]+", "", lower(txt), count=1)
        found = _ID.match(lo2)
        if not found or not _CAND_REST.match(lo2[found.end():]):
            return False
        self.cands.append((idnorm(found.group(0)), self.n))
        return True

    def flush(self) -> None:
        if self.id != "":
            self.read.add(self.id)
            if self.id.startswith("F-") and self.est != "off":
                why = self.failure_why()
                if why:
                    self.est, self.ewhere = "unknown", "failure entry: " + why
                self.meaning = self.failure                  # what was seen — never a rule written into it
            if not self.id.startswith("F-") and self.est == "observed":
                self.est, self.ewhere = "unknown", "not a failure entry, but under Observed Failures"
            self.rows.append("\t".join(v or "-" for v in (
                self.id, self.title, self.scope, self.anchor, self.est, self.ewhere, self.meaning, self.origin,
                self.evidence, self.verdict)))
        self.id, self.pend, self.bul = "", False, False
        self.meaning = self.failure = self.origin = self.evidence = self.verdict = self.para = ""

    def failure_why(self) -> str:
        if self.est != "observed":
            return "it sits outside Observed Failures"
        missing = [name for name, value in (("Failure", self.failure), ("Scope", self.scope), ("Origin", self.origin),
                                            ("Evidence", self.evidence), ("Verdict", self.verdict)) if blank(value)]
        if missing:
            return "it has no " + ", ".join(missing)
        if wholescope(self.scope):
            return "its scope reaches every run; name the paths, seats or mode it concerns"
        if vword(self.verdict) not in VERDICTS:
            return "its verdict, %s, does not establish a failure (%s)" % (self.verdict[:40], VERDICT_LIST)
        return ""

    def fields(self, line: str) -> None:
        """A field line of the entry: its scope, its anchor, what it means, or a line that retires it."""
        for name, attr in (("Scope", "scope"), ("Anchor", "anchor")):
            v = fieldval(line, name)
            if v:
                setattr(self, attr, v)
        v = next((v for v in (fieldval(line, m) for m in MEANINGS) if v), "")
        if v:
            self.meaning = v
        v = fieldval(line, "Failure")
        if v == "" and self.failure == "":
            v = fieldval(line, "Observation")
        if v:
            self.failure = v
        for name, attr in (("Origin", "origin"), ("Evidence", "evidence"), ("Verdict", "verdict")):
            v = fieldval(line, name)
            if v:
                setattr(self, attr, v)
        lo = lower(line)
        for mark in MARKS:
            found = re.search(r"\*\*" + mark + r"( by)?:?\*\*:?", lo)
            if not found:
                continue
            v = trim(re.sub(r"[ \t]+" + _DOT + r".*\Z", "", re.sub(r"[`*]", "", trim(lo[found.end():])), count=1,
                            flags=re.S))
            if not _NOT_RETIRED.match(v):
                self.est, self.ewhere = "off", "marked retired"
        v = fieldval(lo, "status")
        if v:
            w = re.sub(r"[^a-z]", "", re.sub(r"[ \t].*\Z", "", v, count=1, flags=re.S))
            if kind(w) == "off":
                self.est, self.ewhere = "off", "marked " + v

    def fline(self, line: str) -> None:
        """A line that may open a field; a field runs on, as a Markdown paragraph does."""
        self.para = line if _FIELD.search(line) else ""
        self.fbefore = self.failure
        self.fields(line)

    def runson(self) -> bool:
        """Does the field that ends the paragraph so far run on? A list (a scope, anchors, evidence) does only
        while it ends in a comma or a semicolon, or has no value yet."""
        s, f = self.para, ""
        found = _FIELD.search(s)
        while found:
            f, s = s[found.start() + 2:found.end() - 3], s[found.end():]
            found = _FIELD.search(s)
        f, v = lower(trim(f)), trim(s)
        return f not in ("scope", "anchor", "evidence") or v == "" or bool(re.search(r"[,;]\Z", v))

    def entry(self, s: str, bullet: bool) -> bool:
        """Is s (a heading's text, or a bullet after its dash) an entry? Sets its id, title and state."""
        lo, b = lower(s), 0
        while b < len(lo) and lo[b] in "*_~":
            b += 1
        found = _ID.match(lo[b:])
        if not found:
            return False
        idt, rest = found.group(0), s[b + found.end():]
        dashed = "-" in idt
        if re.match(r"[A-Za-z0-9_]|-[A-Za-z0-9]", rest) or (not dashed and not _UNDASHED.match(rest)):
            return False
        mark = lo[:b]
        bold = "**" in mark or "__" in mark
        if bullet and not bold:                              # a bullet entry has its id in bold
            return False
        self.flush()
        self.id = idnorm(idt)
        self.bul, self.pend, self.pn, self.bodyline = bullet, False, 0, False
        closed = bool(re.match(r"[*_~]", rest))
        rest = _REST_OPEN.sub("", re.sub(r"\A[*_~]+", "", rest, count=1), count=1)
        if re.match(r"\*\*|__", rest):
            closed, rest = True, re.sub(r"\A[*_]+[ \t]*", "", rest, count=1)
        self.after = ""
        if bold and not closed:                              # the bold opened before the id closes after the title
            j = rest.find("**")
            if j < 0:
                j = rest.find("__")
            if j >= 0:
                self.after, rest = rest[j + 2:], rest[:j]
            elif bullet:
                self.pend, self.ptitle = True, rest          # a bold title that runs on to the next lines
        self.title = cleantitle(rest)
        self.scope = self.anchor = self.meaning = self.failure = self.origin = self.evidence = self.verdict = ""
        self.est = self.sub_st or self.sec
        self.ewhere = self.subname if self.sub_st else self.secname
        if self.est != "off" and ("~~" in mark or _RETIRED_TITLE.search(lower(self.title))):
            self.est, self.ewhere = "off", "marked retired"
        if bullet:
            self.fline(self.after)
        return True

    # -- the awk's rules, one line at a time ---------------------------------------------------------------
    def line(self, line: str) -> None:
        if self.incom:
            self.incom = "-->" not in line
            return
        if re.match(r"[ \t]*<!--", line):
            self.incom, self.para = "-->" not in line, ""
            return
        if re.match(r"[ \t]*(```|~~~)", line):
            self.fence, self.para = not self.fence, ""
            return
        if self.fence:
            return
        if re.match(r"#+[ \t]", line):
            self.heading(line)
            return
        if re.match(r"[-*+][ \t]", line):
            self.bullet(line)
            return
        if re.match(r"[0-9]+[.)][ \t]", line):
            txt = re.sub(r"\A[0-9]+[.)][ \t]+", "", line, count=1)
            if (self.id == "" or self.bul) and self.entry(txt, True):
                return
            self.listed(txt, line)
            return
        if re.match(r"[ \t]+([-*+]|[0-9]+[.)])[ \t]", line):     # an indented bullet is never an entry: say so
            self.listed(re.sub(r"\A[ \t]+([-*+]|[0-9]+[.)])[ \t]+", "", line, count=1), line)
            return
        if re.match(r"[ \t]*\|", line) and self.table(line):
            return
        if re.match(r"(\*\*|__)[^*_]", line) and (self.id == "" or self.bul) and self.label(line):
            return
        if self.pend and self.pending(line):
            return
        if (self.id != "" and self.para != "" and re.search(r"[^ \t]", line) and not _FIELD_OPENS.match(line)
                and not _RULE.match(line) and self.runson()):
            self.para = self.para + " " + trim(line)
            self.failure = self.fbefore
            self.fields(self.para)
            self.bodyline = True
            return
        if self.id != "":
            self.fline(line)
            if re.search(r"[^ \t]", line):
                self.bodyline = True

    def heading(self, line: str) -> None:
        lvl = len(line) - len(line.lstrip("#"))
        txt = trim(line[lvl:])
        if 2 <= lvl <= 4 and self.entry(txt, False):
            self.elvl, self.anyhead = lvl, True
            return
        if lvl > 4 and self.cand(txt):                       # too deep to read: named, never folded in above
            self.flush()
            self.para = ""
            return
        if self.id != "" and not self.bul and lvl > self.elvl:   # a sub-heading inside an entry
            self.fields(line)
            self.bodyline, self.para = True, ""
            return
        self.flush()
        k, name = kind(txt, lvl > 2), line[:lvl] + " " + txt
        if lvl <= 2:
            self.sec = "settled" if lvl == 1 and not self.anyhead else (k or "unknown")   # the file title never retires
            self.secname, self.sub_st, self.sublvl = name, "", 0
        elif k:
            self.sub_st, self.sublvl, self.subname = k, lvl, name
        elif self.sub_st and lvl <= self.sublvl:
            self.sub_st = ""
        self.anyhead = True

    def bullet(self, line: str) -> None:
        """A top-level bullet: an entry, or a line of the entry above (once a heading entry has a body, its
        bullets are the rules it points at, not new entries)."""
        txt = re.sub(r"\A[-*+][ \t]+", "", line, count=1)
        if self.id != "" and not self.bul and self.bodyline:
            self.cand(txt)
            self.fline(line)
            return
        if self.entry(txt, True):
            return
        self.cand(txt)
        if self.bul:
            self.flush()
        elif self.id != "":
            self.fline(line)

    def listed(self, txt: str, line: str) -> None:
        self.cand(txt)
        if self.id != "":
            self.fline(line)

    def table(self, line: str) -> bool:
        """A table row is never an entry: one with an id is named."""
        txt = re.sub(r"[ \t]*\|.*\Z", "", re.sub(r"\A[ \t]*\|[ \t]*", "", line, count=1), count=1, flags=re.S)
        if not self.cand(txt):
            return False
        if self.id != "":
            self.fline(line)
        self.para = ""
        return True

    def label(self, line: str) -> bool:
        """A bold line used as a heading ("**Enforced conventions — always/never.**")."""
        t = re.sub(r"[ \t]+\Z", "", line, count=1)
        if not re.fullmatch(r"\*\*[^*]+\*\*[.:]?|__[^_]+__[.:]?", t, re.S) or re.search(r":(\*\*|__)[.:]?\Z", t):
            return False
        k = kind(re.sub(r"(\*\*|__)[.:]?\Z", "", t[2:], count=1), True)
        if not k:
            return False
        self.flush()
        self.sub_st, self.sublvl, self.subname = k, 5, t
        return True

    def pending(self, line: str) -> bool:
        """A bold bullet title that runs on: closed on this line, or given up after three lines or a blank."""
        j = line.find("**")
        if j < 0:
            j = line.find("__")
        if j >= 0:
            self.title, self.pend = cleantitle(self.ptitle + " " + line[:j]), False
            self.fline(line[j + 2:])
            return True
        self.pn += 1
        if self.pn >= 3 or re.fullmatch(r"[ \t]*", line):
            self.pend = False
        else:
            self.ptitle = self.ptitle + " " + line
        return False

    def unread(self) -> str:
        """The lines that open like an entry but were not read: "AP-3 (line 12), …"."""
        said, out = set(), []
        for cid, at in self.cands:
            if cid not in self.read and cid not in said:
                said.add(cid)
                out.append("%s (line %d)" % (cid, at))
        return ", ".join(out)


def parse(text: str) -> Parser:
    """A memory file's text (C-locale) read through."""
    parser = Parser()
    for n, raw in enumerate(bytewise.records(text), 1):
        line = raw[:-1] if raw.endswith("\r") else raw
        if n == 1 and line.startswith(BOM):
            line = line[len(BOM):]
        parser.n = n
        parser.line(line)
    parser.flush()
    return parser


def _text(path: str) -> str | None:
    try:
        with open(path, "rb") as stream:
            return bytewise.read(stream.read())
    except OSError:
        return None


def rows(path: str) -> list[str]:
    """The entries of a memory file (a native path) as rows; none when it can't be read."""
    text = _text(path)
    return parse(text).rows if text is not None else []


def skipped(path: str) -> str:
    """The ids of lines that look like entries but are not read, with their line numbers; '' when none."""
    text = _text(path)
    return parse(text).unread() if text is not None else ""


def cells(row: str) -> list[str]:
    """A row's columns, as awk -F'\\t' gives them (empty past the last)."""
    found = row.split("\t")
    return found + [""] * (10 - len(found))
