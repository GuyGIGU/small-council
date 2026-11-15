"""Text read as the helper's awk read it in the C locale: each byte one character (Latin-1 in, Latin-1 out), only
ASCII letters with a case, and blanks that are space and tab. A reader ported from that awk works on this text so
that it matches, counts and cuts what the awk did; it is turned back into the file's own bytes to be shown."""
from __future__ import annotations

from pathlib import Path

EM = "—".encode().decode("latin-1")          # the em dash's three bytes, as three characters
EN = "–".encode().decode("latin-1")
DOT = "·".encode().decode("latin-1")         # the middle dot fields are separated by
ELLIPSIS = "…".encode().decode("latin-1")
ARROW = "→".encode().decode("latin-1")
BOM = "\ufeff".encode().decode("latin-1")
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


def records(text: str, fold: bool = True) -> list[str]:
    """A file's lines: split at newlines, none after a final one. A CR right before a newline is dropped, on every
    OS (an unterminated last line keeps what it has); with fold False every CR stays."""
    if fold:
        text = text.replace("\r\n", "\n")
    lines = text.split("\n")
    if text.endswith("\n") or not text:
        lines.pop()
    return lines


def lines(text: str) -> list[str]:
    """A file's records as the memory's readers clean them: a line's last CR cut, the BOM off line 1."""
    found = [raw[:-1] if raw.endswith("\r") else raw for raw in records(text)]
    if found and found[0].startswith(BOM):
        found[0] = found[0][len(BOM):]
    return found


def file_lines(path: str | Path, fold: bool = True) -> list[str]:
    """A file's records (above), read as UTF-8 with a stray byte kept (surrogateescape); [] when it can't be read."""
    try:
        return records(Path(path).read_bytes().decode("utf-8", "surrogateescape"), fold)
    except OSError:
        return []


def lower(s: str) -> str:
    """awk's tolower in the C locale."""
    return s.translate(_LOWER)


def upper(s: str) -> str:
    """awk's toupper in the C locale."""
    return s.translate(_UPPER)


def clip(text: str, width: int, dots: str = ELLIPSIS) -> str:
    """The helper's clip: a line past width cut at its last space within it, then a space and the dots (C-locale
    text counts bytes and takes the ellipsis's three bytes; a command's own text passes its own "…")."""
    if len(text) <= width:
        return text
    cut = text[:width]
    space = cut.rfind(" ")
    return (cut[:space] if space >= 0 else cut) + " " + dots


def trim(s: str) -> str:
    """Spaces and tabs off both ends: gsub(/^[ \\t]+|[ \\t]+$/, "")."""
    return s.strip(" \t")
