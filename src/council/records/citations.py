"""The citation reader: a citation field, as a model writes it in a seat file, read into the places it names.

One row per place: ("L", path, lines) a file and its lines as a clean list ("12", "7-9,40"); ("P", path) a path
with no line; ("U", text) a place whose line part can't be read ("a.py:5x"); ("N", why) nothing to check (a
command, a link, no path, or "-" for no citation at all). ("WL", path, lines) or ("WP", path) come first when
the whole field is one place whose path has blanks in it; `rows` keeps that one alone when the path exists.

Decoration goes first: a markdown link's [text](target) (both are read), bold, quotes. A backticked command is
evidence, not a place: it is dropped, and what follows it is read. Lines may be written 12, L12, #L12, 12-14,
12..14, 12–14 and 12:5 (a column), and listed with , ; / + — "a.py:5, :9" reuses the path. Only a word that
looks like a path counts (a folder, an extension, a Makefile), and after the first word a bare path needs a
folder too, so the prose around a citation stays prose."""
from __future__ import annotations

import os
import re
from typing import Tuple

from council.records.home import native

Row = Tuple[str, ...]

NOTHING = re.compile(r"(n/a|na|none|\(none\)|tbd|tba|-|—|–)")
JOINED = re.compile(r"[0-9][ \t]*,?[ \t]*(and|or|plus|lines?)[ \t]+:?[Ll]?[0-9]")
JOINED_NUMBER = re.compile(r"[0-9]+([ \t]*-[ \t]*[0-9]+)?")
WORD = re.compile(r"[^ ,;|()<>{}]+")
LINK = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^ ]*")
LINE_AT = re.compile(r"(:|#)[Ll]?[0-9]")
INT_MAX = 2 ** 63 - 1                       # what bash's test reads as a number


def _ext(path: str) -> bool:
    return re.search(r"\.[A-Za-z][A-Za-z0-9_-]*$", path) is not None \
        and re.search(r"(^|/)[A-Za-z]\.[A-Za-z]$", path) is None


def _pathy(path: str) -> bool:
    return "/" in path or _ext(path) or re.match(r"\.[A-Za-z]", path) is not None \
        or re.fullmatch(r"[A-Z][A-Za-z]*file", path) is not None


def _num(text: str) -> str:
    text = re.sub(r"^0+", "", re.sub(r"^[Ll]", "", text))
    return text or "0"


def lines(text: str) -> tuple[str, bool, int]:
    """The line part at the start of text, as a clean list; whether it reads oddly (a second range, or more
    letters or digits run on); and how much of text it used. ('', False, 0) when text starts with no line."""
    first = re.match(r"[Ll]?[0-9]+", text)
    if not first:
        return "", False, 0
    piece, rest, out, odd = _num(first.group(0)), text[first.end():], "", False
    while True:
        found = re.match(r"(-|\.\.)[Ll]?[0-9]+", rest)
        if found:
            if "-" in piece:
                odd = True
                break
            piece += "-" + _num(re.sub(r"^[^0-9]+", "", found.group(0)))
            rest = rest[found.end():]
            continue
        found = re.match(r":[0-9]+", rest)                                    # a column
        if found:
            rest = rest[found.end():]
            continue
        found = re.match(r" *[,;/+&] *:?[Ll]?[0-9]+", rest)                   # the next piece
        if found:
            out += ("," if out else "") + piece
            piece, rest = _num(re.sub(r"^[^0-9]+", "", found.group(0))), rest[found.end():]
            continue
        break
    if re.match(r"([A-Za-z0-9_]|-|\.\.|\.[0-9])", rest):
        odd = True
    return out + ("," if out else "") + piece, odd, len(text) - len(rest)


def _join_lines(text: str) -> str:
    """"10 and 9999", "10, line 9999", "10 or 12": a second line joined by a word becomes "10,9999", read like
    any list. A number followed by more prose ("5 and 9 callers") is prose, and stays as written."""
    done = ""
    while True:
        found = JOINED.search(text)
        if not found:
            return done + text
        tail = text[found.end() - 1:]                     # from the first digit of the next number
        number = JOINED_NUMBER.match(tail)
        if number and not re.match(r"[ \t]+[A-Za-z]", tail[number.end():]):
            done += text[:found.start() + 1] + ","
        else:
            done += text[:found.end() - 1]
        text = tail


def _undecorate(text: str) -> str:
    """Dashes, arrows and curly quotes out, a markdown link's text and target both kept, bold and quotes gone."""
    text = text.replace("–", "-").replace("—", "-")
    for arrow in ("→", "->", "=>"):
        text = text.replace(arrow, " ")
    for mark in ("‘", "’", "“", "”"):
        text = text.replace(mark, " ")
    while "](" in text:
        at = text.index("](")
        before, after = text[:at], text[at + 2:]
        close, bracket = after.find(")"), before.rfind("[")
        if close < 0 or bracket < 0:
            break
        text = (before[:bracket] + " " + before[bracket + 1:] + " " + after[:close] + " " + after[close + 1:])
    text = text.replace("*", "")
    return re.sub(r"[\"\[\]']", " ", text)


def _whole(text: str) -> Row | None:
    """The whole field as one place whose path has blanks in it (WL, WP), or None."""
    whole = re.sub(r"[ .,;]+$", "", text.replace("`", "").lstrip(" "))
    if re.match(r"[^:]* [^:]*:[Ll]?[0-9]", whole):
        place = whole[:whole.rfind(":")]
        found, odd, used = lines(whole[len(place) + 1:])
        if not odd and found and re.fullmatch(r"[ .,;:+]*", whole[len(place) + 1 + used:]):
            return ("WL", place, found)
        return None
    if " " in whole and ":" not in whole and _pathy(whole):
        return ("WP", whole)
    return None


def _drop_commands(text: str) -> tuple[str, bool]:
    """`a command` is dropped (it is evidence, not a place); a backticked single word is kept."""
    command = False
    while "`" in text:
        at = text.index("`")
        rest = text[at + 1:]
        close = rest.find("`")
        if close < 0:
            return text[:at] + " " + rest, command
        inside = rest[:close]
        if " " in inside:
            command, inside = True, ""
        text = text[:at] + " " + inside + " " + rest[close + 1:]
    return text, command


def _line_text(suffix: str, tail: str) -> str:
    """What follows a path that may give its lines: "a.py:5" · "a.py#L5" · "a.py: 12" · "a.py: line 12" ·
    "a.py lines 10-12"; '' when nothing does."""
    if LINE_AT.match(suffix):
        return suffix[1:] + tail
    if suffix not in (":", ""):
        return ""
    lead = r"[ \t]+(lines?[ \t]+)?" if suffix == ":" else r"[ \t]*,?[ \t]*lines?[ \t]+"
    found = re.match(lead, tail)
    if found and re.match(r"[Ll]?[0-9]", tail[found.end():]):
        return tail[found.end():]
    return ""


def _places(text: str) -> list[Row]:
    found: list[Row] = []
    count = 0
    while True:
        word = WORD.search(text)
        if not word:
            return found
        whole, tail = word.group(0), text[word.end():]
        text, count = tail, count + 1
        skip = 2 if re.match(r"[A-Za-z]:[/\\]", whole) else 0               # a drive letter is not a line
        mark = re.search(r"[:#]", whole[skip:])
        path, suffix = (whole[:skip + mark.start()], whole[skip + mark.start():]) if mark else (whole, "")
        path = path.replace("\\", "/")
        if not suffix:
            path = re.sub(r"[.:]+$", "", path)
        if not path or not _pathy(path):
            continue
        given = _line_text(suffix, tail)
        if given:
            listed, odd, used = lines(given)
            text = given[used:]
            shown = whole if LINE_AT.match(suffix) else whole + " " + given.split(" ", 1)[0]
            row = ("U", shown) if odd else ("L", path, listed)
        elif path.endswith("/") or ("/" in path and _ext(path)) or (count == 1 and re.match(r" *($|\(|-)", tail)):
            row = ("P", path)
        else:
            continue
        if row not in found:
            found.append(row)


def parse(field: str) -> list[Row]:
    """The rows a citation field gives (see the module's doc), in the order the helper's reader printed them."""
    text = re.sub(r"[\r\t]", " ", field)
    bare = text.replace(" ", "")
    if bare in ("", "-") or NOTHING.fullmatch(re.sub(r"[.`*_\"]", "", _lower(bare))):
        return [("N", "-")]
    text = _join_lines(_undecorate(text))
    whole = _whole(text)
    text, command = _drop_commands(text)
    text, links = LINK.subn(" ", text)
    found = _places(text)
    if not found:
        found = [("N", "command" if command else "link" if links else "no path")]
    return ([whole] if whole else []) + found


def rows(top: str, field: str) -> list[Row]:
    """The rows parse gives; a whole-field place (WL/WP) is used alone when its path exists under top."""
    found = parse(field)
    if not found[0][0].startswith("W") or len(found) == 1:
        return found
    place = found[0][1]
    if not (place.startswith("/") or re.match(r"[A-Za-z]:", place)):
        place = top + "/" + place
    return [(found[0][0][1:],) + found[0][1:]] if os.path.exists(native(place)) else found[1:]


def bash_int(text: str) -> int | None:
    """A number as bash's test reads one: blanks around it are fine, inside it or a sign-less junk is not."""
    found = re.fullmatch(r"[ \t\n]*([+-]?[0-9]+)[ \t\n]*", text)
    if not found or abs(int(found.group(1))) > INT_MAX:
        return None
    return int(found.group(1))


def ranges(listed: str, count: int | None = None) -> list[tuple[int, int]] | None:
    """The line part of a citation — "12", "7-9", or a comma list of both — as (start, end) pairs; None for an
    empty or malformed piece and, given the file's line count, for any piece that runs past its end."""
    found: list[tuple[int, int]] = []
    for piece in listed.split(","):
        start, _, end = piece.partition("-")
        end = end if "-" in piece else start
        if re.search(r"[^0-9 \t]", start + end):
            return None
        first, last = bash_int(start), bash_int(end)
        if first is None or last is None or first < 1 or last < first:
            return None
        if count is not None and last > count:
            return None
        found.append((first, last))
    return found


def line_verdict(listed: str, count: int, what: str = "file has") -> str:
    """'ok', or 'bad-line (<why>)', for a clean line list against a file's line count; `what` names the file."""
    if ranges(listed, count) is not None:
        return "ok"
    for piece in listed.replace(",", " ").split():
        start, _, end = piece.partition("-")
        end = end if "-" in piece else start
        if start == "0" or end == "0":
            return "bad-line (there is no line 0)"
        first, last = bash_int(start), bash_int(end)
        if first is not None and last is not None and last < first:
            return "bad-line (%s runs backwards)" % piece
    return "bad-line (the %s %d lines)" % (what, count)


def _lower(text: str) -> str:
    """ASCII letters lowered, as awk does in the C locale."""
    return "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in text)


def count_lines(data: bytes | None) -> int:
    """awk's END { print NR }: newlines, and a last line without one."""
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)

