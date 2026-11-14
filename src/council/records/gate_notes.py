"""What a gate command's own text gives away before it runs: a backslash bash drops, a Windows switch Git Bash
turns into a path, and the ways its exit code stops being its check's (a pipe, a last step that always
succeeds, a runner's output judged by its text). `council gates` and `council gate` say each as a note."""
from __future__ import annotations

import re

SQ, DQ = "'", '"'
WORD = re.compile(r"[A-Za-z0-9_]")
BACKSLASH = ("has a backslash outside quotes, which bash drops (tools\\run.ps1 reaches the tool as toolsrun.ps1) — "
             "write paths with /, or put them in quotes")
WINSWITCH = ("has a Windows switch such as /p:… that Git Bash on Windows turns into a path "
             "(/p:Configuration=Release reaches the tool as p:Configuration=Release) — write -p:… where the tool "
             "takes it (msbuild and dotnet do), else //p:…")
SHAPES = {
    "pipe": "pipes its output, so its exit code is the last command's, not the check's — drop the pipe, or begin "
            "the command with set -o pipefail;",
    "masked": "ends with a step that always succeeds (; echo …, || true), so it passes whatever the check did — "
              "join the steps with && and drop the fallback",
    "capture": "keeps a runner's output in $( ) and judges it by its text, so a runner that is missing, or crashes "
               "without printing that text, passes — add || exit $? right after the $( )",
}
MASKED = re.compile(r"((echo|printf|true|:)([ \t;]|\Z)|exit[ \t]+0([ \t;]|\Z))")
KEEPS = re.compile(r"(^|[^A-Za-z0-9_])exit[ \t]+([1-9]|\$)")
ERREXIT = re.compile(r"set[ \t]+-[a-z]*e|errexit")
CAPTURED = re.compile(r'[A-Za-z_][A-Za-z0-9_]*="?\$\(')
JUDGED = re.compile(r"(^|[^A-Za-z0-9_])(case|grep)[ \t]")
CHECKED = re.compile(r"\$\?|\|\|[ \t]*exit")


def backslash(command: str) -> bool:
    """A backslash outside quotes before a letter, digit or _: bash drops it."""
    quote, i = "", 0
    while i < len(command):
        char = command[i]
        if quote == SQ:
            quote = "" if char == SQ else quote
        elif char == "\\":
            if quote == "" and WORD.fullmatch(command[i + 1:i + 2] or "#"):
                return True
            i += 1
        elif quote == DQ:
            quote = "" if char == DQ else quote
        elif char in (SQ, DQ):
            quote = char
        i += 1
    return False


def winswitch(command: str) -> bool:
    """A word that starts with one / and reads as a Windows switch (/p:Name=Value, /t:Build, /nologo): Git Bash
    turns it into a path before a Windows tool sees it, quoted or not."""
    prev = " "
    for i, char in enumerate(command):
        rest = command[i + 1:]
        if char == "/" and prev in " \t\"'=" and (re.match(r"[A-Za-z][A-Za-z0-9_-]*:([^/]|\Z)", rest)
                                                   or re.match(r"nologo([^A-Za-z0-9_-]|\Z)", rest)):
            return True
        prev = char
    return False


class _Scan:
    """The walk over the command, one character at a time (the helper's awk, state for state)."""

    def __init__(self, command: str) -> None:
        self.s, self.quote, self.word = command, "", ""
        self.case_word, self.pattern, self.cases, self.parens = False, False, 0, 0
        self.pipe, self.sep, self.step, self.stack, self.top = False, "", 0, "", ""

    def run(self) -> None:
        i, s = 0, self.s
        while i <= len(s):
            char = s[i] if i < len(s) else " "
            if "$" not in self.stack:
                self.top += char              # the text outside any $( ), for capture
            i = self.char(i, char)
            i += 1

    def char(self, i: int, char: str) -> int:
        """Read one character; returns the index of the last character it consumed."""
        if self.quote == SQ:
            self.quote = "" if char == SQ else SQ
            return i
        if self.quote == DQ:
            if char == "\\":
                return i + 1
            self.quote = "" if char == DQ else DQ
            return i
        if WORD.fullmatch(char):
            self.word += char
            return i
        self.end_word()
        return self.operator(i, char)

    def end_word(self) -> None:
        if self.word == "case":
            self.case_word = True
        elif self.word == "in" and self.case_word:
            self.case_word, self.pattern, self.cases = False, True, self.cases + 1
        elif self.word == "esac" and self.cases > 0:
            self.cases, self.pattern = self.cases - 1, False
        self.word = ""

    def operator(self, i: int, char: str) -> int:
        s, nxt = self.s, self.s[i + 1:i + 2]
        if char == "\\":
            return i + 1
        if char in (SQ, DQ):
            self.quote = char
        elif char == "(":
            self.parens += 1
            self.stack += "$" if i > 0 and s[i - 1] == "$" else "("
        elif char == ")":
            if self.pattern and self.cases > 0:
                self.pattern = False
            elif self.parens > 0:
                self.parens, self.stack = self.parens - 1, self.stack[:-1]
        elif char == ";" and nxt in (";", "&"):
            self.pattern = self.pattern or self.cases > 0
            return i + 1
        elif char + nxt in ("||", "&&"):
            self.separate(char + nxt, i + 2)
            return i + 1
        elif char == ";":
            self.separate(";", i + 1)
        elif char == "|" and not self.pattern and "$" not in self.stack:
            self.pipe = True                  # inside $( ) it is for capture to judge
        return i

    def separate(self, sep: str, step: int) -> None:
        if not self.parens and not self.cases:
            self.sep, self.step = sep, step


def shapes(command: str) -> list[str]:
    """The shapes: pipe, masked and capture, each when it holds, in that order."""
    scan = _Scan(command)
    scan.run()
    found = []
    if scan.pipe and not re.search("pipefail|PIPESTATUS", command):
        found.append("pipe")
    last = scan.s[scan.step:].lstrip(" \t")
    errexit = ERREXIT.search(command) is not None
    keeps = errexit or KEEPS.search(command) is not None
    if scan.sep in (";", "||") and not keeps and "|" not in last and MASKED.match(last):
        found.append("masked")
    if CAPTURED.search(command) and JUDGED.search(scan.top) and not CHECKED.search(command) and not errexit:
        found.append("capture")
    return found


def notes(command: str) -> list[str]:
    """One plain note per shape found, each finishing "the command …"."""
    return [SHAPES[shape] for shape in shapes(command)]
