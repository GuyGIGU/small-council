"""A run's words made anonymous, for `council run export --anon`: absolute paths become placeholders, a session id a
stand-in, and free words (the user's request and decisions, the Chair's notes) neutral stand-ins of the same shape:
each letter x, each digit 0, spaces and punctuation kept. In a shell command only the words outside the helper's
own vocabulary are stood in for, so the command still reads as the same helper calls (audit_calls.invocations).
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Collection

PLACEHOLDERS = ("project", "home", "plugin", "path", "email", "user")
TAG = re.compile(r"(</?command-[a-z-]+>)")                     # a slash command's markup in a prompt, kept
LETTER = re.compile(r"[^\W\d_]")
DIGIT = re.compile(r"\d")
WORD = re.compile(r"(?<![\w])[^\W\d_][\w.-]*")
QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
ABSOLUTE = re.compile(r"(?<![\w.~$<>/\\-])(?:[A-Za-z]:[\\/]|/(?!dev/)(?=[\w.-]))[^\s'\"`|;&<>()]*")


def shape(words: str) -> str:
    """Free words as a stand-in of the same shape: letters x, digits 0, the rest (and a slash command's tags) kept."""
    return "".join(piece if TAG.fullmatch(piece) else DIGIT.sub("0", LETTER.sub("x", piece))
                   for piece in TAG.split(words))


def spellings(root: str) -> list[str]:
    """The ways a folder is written in a run's files: as given, with / or \\, and on a drive as Git Bash writes it."""
    forward = root.replace("\\", "/").rstrip("/")
    found = {forward, forward.replace("/", "\\")}
    drive = re.match(r"^([A-Za-z]):/(.*)$", forward)
    if drive:
        found.add("/%s/%s" % (drive.group(1).lower(), drive.group(2)))
    return sorted((s for s in found if len(s) > 3), key=len, reverse=True)


class Anon:
    """One export's stand-ins: the same folder or session is always given the same placeholder."""

    def __init__(self, roots: dict[str, str]) -> None:
        """roots maps a placeholder name (PLACEHOLDERS) to the absolute folder it stands for."""
        self.roots = sorted(((spelling, name) for name, root in roots.items() if root for spelling in spellings(root)),
                            key=lambda pair: len(pair[0]), reverse=True)
        self.sessions: dict[str, str] = {}
        names = {os.environ.get("USER", ""), os.environ.get("USERNAME", ""), Path.home().name}
        self.users = sorted((n for n in names if len(n) >= 3 and n not in PLACEHOLDERS), key=len, reverse=True)

    def session(self, ident: str) -> str:
        """A session id's stand-in, session-1 for the first met; '' and '-' stay as they are."""
        ident = ident.strip()
        if ident in ("", "-"):
            return ident
        return self.sessions.setdefault(ident, "session-%d" % (len(self.sessions) + 1))

    def paths(self, text: str) -> str:
        """Absolute paths as placeholders (<project>/…, a path to the helper as <path>/council), e-mail addresses as
        <email>, the user's login name as <user>."""
        for spelling, name in self.roots:
            text = re.sub(re.escape(spelling), "<%s>" % name, text, flags=re.IGNORECASE)
        text = ABSOLUTE.sub(lambda m: "<path>/council" if re.search(r"[/\\]council$", m.group(0)) else "<path>", text)
        text = EMAIL.sub("<email>", text)
        for user in self.users:
            text = re.sub(r"(?<![\w])%s(?![\w])" % re.escape(user), "<user>", text, flags=re.IGNORECASE)
        return text

    def command(self, text: str, keep: Collection[str]) -> str:
        """A shell command with paths as placeholders and every word outside keep stood in for. A quoted string
        holding no variable and no `council` is free words (a decision, a task's title) and is stood in for whole."""
        text = self.paths(text)
        out, last = [], 0
        for found in QUOTED.finditer(text):
            inner = found.group(0)[1:-1]
            key = re.match(r"^[A-Za-z][\w-]*=", inner)          # 'size=…' quoted whole: the key is the helper's
            lead, inner = (key.group(0), inner[key.end():]) if key else ("", inner)
            free = "$" not in inner and "council" not in inner
            mark = found.group(0)[0]
            out += [self._words(text[last:found.start()], keep),
                    mark + lead + (shape(inner) if free else self._words(inner, keep)) + mark]
            last = found.end()
        return "".join(out + [self._words(text[last:], keep)])

    @staticmethod
    def _words(text: str, keep: Collection[str]) -> str:
        def swap(found: re.Match[str]) -> str:
            word, at = found.group(0), found.start()
            before, after = text[max(at - 2, 0):at], text[found.end():found.end() + 1]
            if word in keep or after == "=" or before[-1:] in ("$", "-") or before == "${" \
                    or (before[-1:] == "<" and word in PLACEHOLDERS):
                return word
            return shape(word)
        return WORD.sub(swap, text)
