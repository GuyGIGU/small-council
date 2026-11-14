"""Text read as the helper's awk read it in the C locale: each byte one character (Latin-1 in, Latin-1 out), only
ASCII letters with a case, and blanks that are space and tab. A reader ported from that awk works on this text so
that it matches, counts and cuts what the awk did; it is turned back into the file's own bytes to be shown."""
from __future__ import annotations

import os

EM = "—".encode().decode("latin-1")          # the em dash's three bytes, as three characters
EN = "–".encode().decode("latin-1")
DOT = "·".encode().decode("latin-1")         # the middle dot fields are separated by
ELLIPSIS = "…".encode().decode("latin-1")
ARROW = "→".encode().decode("latin-1")
_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
_UPPER = str.maketrans("abcdefghijklmnopqrstuvwxyz", "ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def read(data: bytes) -> str:
    """A file's bytes as C-locale text."""
    return data.decode("latin-1")


def shown(text: str) -> str:
    """C-locale text as the str a command prints: its bytes again, read as UTF-8 (a stray byte kept as it was)."""
    return text.encode("latin-1").decode("utf-8", "surrogateescape")


def bytes_of(text: str) -> bytes:
    """C-locale text as the bytes it came from."""
    return text.encode("latin-1")


def text(value: str) -> str:
    """A str the command was given (UTF-8 read), as C-locale text."""
    return value.encode("utf-8", "surrogateescape").decode("latin-1")


def records(text: str) -> list[str]:
    """A file's lines as awk reads them: split at newlines, none after a final one. Git Bash's awk, sed and grep
    read a file in text mode, a CR LF as LF, so on Windows a line's own last CR is gone before the reader sees
    it; elsewhere it stays."""
    if os.name == "nt":
        text = text.replace("\r\n", "\n")
    lines = text.split("\n")
    if text.endswith("\n") or not text:
        lines.pop()
    return lines


def lower(s: str) -> str:
    """awk's tolower in the C locale."""
    return s.translate(_LOWER)


def upper(s: str) -> str:
    """awk's toupper in the C locale."""
    return s.translate(_UPPER)


def trim(s: str) -> str:
    """Spaces and tabs off both ends: gsub(/^[ \\t]+|[ \\t]+$/, "")."""
    return s.strip(" \t")
