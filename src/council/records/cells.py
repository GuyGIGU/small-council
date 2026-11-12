"""Values read from a council file: lines, TSV rows, JSON lines and the numbers in their cells."""
from __future__ import annotations

import json
import re
from typing import Any

# Every C0 and C1 control (tab and newline included: a value is one cell), DEL, and the Unicode line
# and paragraph separators: none may reach a terminal or a page from a file.
CONTROL = re.compile("[" + chr(0) + "-" + chr(0x1F) + chr(0x7F) + "-" + chr(0x9F) + chr(0x2028) + chr(0x2029) + "]")


def clean(value: Any) -> str:
    """The value as one line: controls become spaces, runs of spaces one, ends trimmed."""
    return re.sub(r" {2,}", " ", CONTROL.sub(" ", str(value))).strip()


def lines_of(text: str) -> list[str]:
    """Lines as the helper's awk splits them: on newline only, each line's carriage return dropped.
    str.splitlines() would also split on form feeds and Unicode breaks inside a cell, and invent rows."""
    return [line.rstrip("\r") for line in text.split("\n")]


def integer(value: Any) -> int | None:
    """An int from an int or a string of up to 12 digits, else None: never a list, a bool or a null."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if abs(value) < 10 ** 12 else None
    if isinstance(value, str) and re.fullmatch(r"-?[0-9]{1,12}", value.strip()):
        return int(value.strip())
    return None


def number(value: Any) -> int:
    """A cell's whole number of up to 12 digits, else 0."""
    value = str(value or "").strip()
    return int(value) if re.fullmatch(r"[0-9]{1,12}", value) else 0


def optional_number(value: Any) -> int | None:
    """A recorded count, or None when the cell is blank or not a plain number (never guessed as 0)."""
    value = str(value if value is not None else "").strip()
    return int(value) if re.fullmatch(r"[0-9]{1,12}", value) else None


def token_count(text: str) -> int | None:
    """A token figure as the helper's seat_tokens reads one: 74300, 74,300, 74 300, 74.3k, 1.2M, with an
    optional trailing 'tokens'. Anything else (two numbers, a sign, '74,3k') is None, never a guess."""
    s = text.strip(" \t")
    tail = re.search(r"[ \t]*tokens?$", s.lower())
    if tail:
        s = s[:tail.start()]
    if re.fullmatch(r"[0-9][0-9]?[0-9]?([, ][0-9][0-9][0-9])+", s) or re.fullmatch(r"[0-9]+", s):
        digits = re.sub(r"[, ]", "", s).lstrip("0") or "0"
        return None if len(digits) > 12 else int(digits)
    if not re.fullmatch(r"[0-9]+(\.[0-9]+)?[ \t]*[kKmM]", s):
        return None
    scale = 1000 if s[-1] in "kK" else 1000000
    value = int(float(s[:-1].rstrip(" \t")) * scale + 0.5)
    return None if value >= 10 ** 12 else value


def parse_json(text: str) -> Any:
    """The JSON value of text, or None when it does not parse."""
    try:
        return json.loads(text)
    except (ValueError, RecursionError):
        return None


def tsv_rows(text: str) -> list[dict[str, str]]:
    """A TSV file's rows as dicts keyed by its first row. Blank and "#" lines are skipped, and a short
    row's missing cells read as empty."""
    rows = [line.split("\t") for line in lines_of(text) if line.strip() and not line.startswith("#")]
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
