"""Values read from a council file: lines, TSV rows, JSON lines and the numbers in their cells."""
from __future__ import annotations

import json
import re
from typing import Any

# Every C0 and C1 control (tab and newline included: a value is one cell), DEL, and the Unicode line
# and paragraph separators: none may reach a terminal or a page from a file.
CONTROL = re.compile("[" + chr(0) + "-" + chr(0x1F) + chr(0x7F) + "-" + chr(0x9F) + chr(0x2028) + chr(0x2029) + "]")
INTMAX = 2 ** 63 - 1     # the largest whole number bash's test reads; a larger one fails the test


def clean(value: Any) -> str:
    """The value as one line: controls become spaces, runs of spaces one, ends trimmed."""
    return re.sub(r" {2,}", " ", CONTROL.sub(" ", str(value))).strip()


def lines_of(text: str) -> list[str]:
    """Lines as the helper's awk splits them: on newline only, each line's carriage return dropped.
    str.splitlines() would also split on form feeds and Unicode breaks inside a cell, and invent rows."""
    return [line.rstrip("\r") for line in text.split("\n")]


def tab_rows(text: str) -> list[list[str]]:
    """A TSV file's lines (lines_of), each as its raw cells: split at tabs, nothing trimmed."""
    return [line.split("\t") for line in lines_of(text)]


def heading(line: str) -> str | None:
    """A `## ` heading's name as the helper compares it: lower-cased, blanks folded, a trailing `(…)` and colon off
    (`## Hard Rules (non-negotiable)` is 'hard rules'); None for any other line."""
    found = re.match(r"##[ \t]+(.*)", line, re.S)
    if not found:
        return None
    name = re.sub(r"[ \t]*\([^()]*\)\Z", "", found.group(1).rstrip(" \t\r"))
    return _lower(re.sub(r"[ \t]+", " ", name.rstrip(" \t:")))


def table_cells(line: str, raw: bool = False) -> list[str]:
    """A Markdown table row split at each '|' outside a code span, nothing trimmed (so '| a | b |' is
    ['', ' a ', ' b ', '']): '\\|' is a literal pipe anywhere, and a '|' between two backticks stays in its cell
    when the row's backticks pair up (an odd one quotes nothing). The one splitter of a council table row. raw keeps
    each cell as written ('\\|' as '\\|'), so '|'.join gives the row back byte for byte."""
    out, current, quoted, i = [], "", False, 0
    paired = line.replace("\\|", "").count("`") % 2 == 0
    while i < len(line):
        char = line[i]
        if char == "\\" and line[i + 1:i + 2] == "|":
            current, i = current + ("\\|" if raw else "|"), i + 2
            continue
        if char == "`" and paired:
            quoted = not quoted
        if char == "|" and not quoted:
            out.append(current)
            current = ""
        else:
            current += char
        i += 1
    return out + [current]


def field(text: str, key: str) -> str:
    """A `key:` line of a file that is not a run's state (ask.md, a seat card, the config), as the helper's field
    reads one: the first line anywhere that starts with the key, the blanks after the colon and every carriage
    return dropped, then a trailing '  # comment'. '' when no line has the key."""
    bom = "﻿"
    for at, line in enumerate(text.split("\n")):
        if at == 0 and line.startswith(bom):
            line = line[len(bom):]
        if line.startswith(key + ":"):
            value = re.sub(r"^[ \t\n\v\f\r]*", "", line[len(key) + 1:]).replace("\r", "")
            return re.sub(r"[ \t\n\v\f\r]{2,}#.*$", "", value, flags=re.S)
    return ""


def integer(value: Any) -> int | None:
    """An int from an int or a string of up to 12 digits, else None: never a list, a bool or a null."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if abs(value) < 10 ** 12 else None
    if isinstance(value, str) and re.fullmatch(r"-?[0-9]{1,12}", value.strip()):
        return int(value.strip())
    return None


def leading(cell: str) -> int:
    """A cell a sum adds: its number (optional_number), else 0."""
    found = optional_number(cell)
    return found if found is not None else 0


def optional_number(value: Any) -> int | None:
    """A count or figure: plain ASCII digits, 1 to 12 of them (no sign, exponent or decimal point), blanks at
    its ends aside. None for anything else, a blank cell too: unknown, never guessed as 0 (D26)."""
    value = str(value if value is not None else "").strip()
    return int(value) if re.fullmatch(r"[0-9]{1,12}", value) else None


def token_count(text: str) -> int | None:
    """A token figure as the helper's seat_tokens reads one: 74300, 74,300, 74 300, 74.3k, 1.2M, with an
    optional trailing 'tokens'. Anything else (two numbers, a sign, '74,3k') is None, never a guess."""
    s = text.strip(" \t")
    tail = re.search(r"[ \t]*tokens?\Z", s.lower())    # \Z, as awk's $: the end of the whole value
    if tail:
        s = s[:tail.start()]
    if re.fullmatch(r"[0-9][0-9]?[0-9]?([, ][0-9][0-9][0-9])+", s) or re.fullmatch(r"[0-9]+", s):
        digits = re.sub(r"[, ]", "", s).lstrip("0") or "0"
        return None if len(digits) > 12 else int(digits)
    if not re.fullmatch(r"[0-9]+(\.[0-9]+)?[ \t]*[kKmM]", s):
        return None
    scale = 1000 if s[-1] in "kK" else 1000000
    value = float(s[:-1].rstrip(" \t")) * scale + 0.5      # a float: past 308 digits it is inf, too big
    return None if value >= 10 ** 12 else int(value)


def parse_json(text: str) -> Any:
    """The JSON value of text, or None when it does not parse."""
    try:
        return json.loads(text)
    except (ValueError, RecursionError):
        return None


def tsv_rows(text: str) -> list[dict[str, str]]:
    """A TSV file's rows as dicts keyed by its first row. Blank and "#" lines are skipped, and a short
    row's missing cells read as empty."""
    rows = [row for row in tab_rows(text) if "".join(row).strip() and not row[0].startswith("#")]
    if not rows:
        return []
    head = rows[0]
    return [dict(zip(head, row + [""] * (len(head) - len(row)))) for row in rows[1:]]


def jsonl_rows(text: str) -> list[dict[str, Any]]:
    """The JSON objects of a JSON-lines file, one per line; a line that is not an object is skipped."""
    rows = []
    for line in lines_of(text):
        row = parse_json(line)
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _lower(s: str) -> str:
    """ASCII letters lower-cased, nothing else (awk's tolower in the C locale)."""
    return s.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"))
