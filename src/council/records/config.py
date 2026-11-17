"""council.config.md: one reader of a `- key: value` line for every setting (pref), each setting with its stated
default, and one rule for the headings the helper looks for (cells.heading).

A setting's line is the first `- key: value` (or `* key: value`) line anywhere in the file. Its key matches whatever
its capitals and spacing; its value loses the carriage return, an HTML comment, a trailing `# note` and a trailing
`(note)`, and is compared lower-cased. A value a setting can't read is never silently its default: the setting's
reader says once on stderr which line it read and what it used instead (unread), and `council doctor` reports the
line as an error with the values allowed (problems).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Callable, Iterator, NamedTuple

from council.records import bytewise, cells, paths
from council.records.cells import INTMAX

NAME = "council.config.md"
AGENT_CAP = 10
SPACE = "[ \t\n\r\f\v]"  # sed's [[:space:]]
MAX_PER_WORKER = 1000000
BOM = "﻿"


def path(home: str | Path) -> Path:
    return Path(home) / NAME


def _lines(home: str | Path | None) -> list[str]:
    """The config's lines: links followed, no size limit, a BOM off the first, each line's carriage return dropped
    (cells.lines_of)."""
    try:
        data = path(home).read_bytes()        # type: ignore[arg-type]
    except (OSError, TypeError):
        return []
    return cells.lines_of(data.decode("utf-8", errors="replace").lstrip(BOM))


def first(home: str | Path | None, pattern: str) -> re.Match | None:
    """The first config line the pattern matches from its start, as sed -n 's/…/p' | head -n 1 finds it."""
    rule = re.compile(pattern)
    for line in _lines(home):
        found = rule.match(line)
        if found:
            return found
    return None


class Pref(NamedTuple):
    """One `- key: value` line: its key (lower case, blanks folded), its value as written with the notes off (said),
    that value lower-cased (value), and its line number in the config."""

    key: str
    said: str
    value: str
    line: int


_PREF = re.compile(r"[ \t]*[-*][ \t]+([A-Za-z][A-Za-z \t]*?)[ \t]*:(.*)\Z", re.S)


def pref_of(text: str, number: int = 0) -> Pref | None:
    """One config line read as a `- key: value` line; None when it isn't one."""
    found = _PREF.match(text)
    if not found:
        return None
    said = re.sub(r"<!--.*\Z", "", found.group(2).replace("\r", ""), flags=re.S)
    said = re.sub(r"(\A|[ \t])#.*\Z", "", said, flags=re.S)
    said = re.sub(r"[ \t]+", " ", re.sub(r"[ \t]*\([^()]*\)[ \t]*\Z", "", said)).strip(" ")
    return Pref(bytewise.lower(re.sub(r"[ \t]+", " ", found.group(1))), said, bytewise.lower(said), number)


def section(home: str | Path | None, name: str) -> list[tuple[int, str]]:
    """(line number, line) for each line under every heading of this name (cells.heading: 'run preferences')."""
    under, found = False, []
    for number, line in enumerate(_lines(home), 1):
        head = cells.heading(line)
        if head is not None:
            under = head == name
        elif under:
            found.append((number, line))
    return found


def prefs(home: str | Path | None) -> Iterator[tuple[str | None, Pref]]:
    """Every `- key: value` line of the config, with the heading it is under (None above the first)."""
    under = None
    for number, line in enumerate(_lines(home), 1):
        name = cells.heading(line)
        if name is not None:
            under = name
            continue
        found = pref_of(line, number)
        if found:
            yield under, found


def pref(home: str | Path | None, key: str, empty: bool = False) -> Pref | None:
    """A setting's line: the first `- key: value` line with this key anywhere in the file; None with none, or with an
    empty value unless empty is asked for (an empty line is a missing one: the setting's default, said as one)."""
    found = next((found for _, found in prefs(home) if found.key == key), None)
    return found if found and (found.value or empty) else None


_SAID: set[str] = set()


def hush() -> None:
    """No unread notes from this process from now on (council doctor reports each such line itself)."""
    _SAID.add("*")


def speak() -> None:
    """Unread notes again, each once (after hush)."""
    _SAID.clear()


def unread(found: Pref, used: str) -> None:
    """Say once per setting, on stderr, that its line can't be read, what it takes and what is used instead."""
    if found.key in _SAID or "*" in _SAID:
        return
    _SAID.add(found.key)
    sys.stdout.flush()
    sys.stderr.write("council: %s line %d, `- %s: %s`, isn't %s — %s is used; council doctor lists such lines\n"
                     % (NAME, found.line, found.key, found.said, SETTINGS[found.key][0], used))


def _cap(value: str) -> int | None:
    """An agent cap: a whole number from 1 to INTMAX."""
    if not re.fullmatch(r"[0-9]+", value):
        return None
    number = int(value.lstrip("0")[:20] or "0")      # int() refuses 4,300 digits; 20 are past INTMAX anyway
    return number if 0 < number <= INTMAX else None


def agent_cap(home: str | Path | None) -> int:
    """`- agent cap: N`, else 10 (also, said once on stderr, for 0 or anything but a whole number)."""
    found = pref(home, "agent cap")
    value = _cap(found.value) if found else None
    if found and value is None:
        unread(found, str(AGENT_CAP))
    return value or AGENT_CAP


def _choice(home: str | Path | None, key: str, words: tuple[str, ...]) -> tuple[str, Pref | None]:
    """(the word of a setting's line if it is one of words, else ''; the line)."""
    found = pref(home, key)
    return (found.value if found and found.value in words else ""), found


def build_tier(home: str | Path) -> str:
    """'light (config)' or 'full (config)', else light as a default, said so."""
    tier, found = _choice(home, "build tier", ("light", "full"))
    if tier:
        return "{} (config)".format(tier)
    if not found:
        return "light (default)"
    unread(found, "light")
    return "light (default; '{}' is not a tier — light or full)".format(found.value)


CHECKING = ("one per batch", "per task")


def checking(home: str | Path | None) -> str:
    """'one per batch (config)' or 'per task (config)', else one per batch as a default, said so."""
    value, found = _choice(home, "checking", CHECKING)
    if value:
        return "{} (config)".format(value)
    if not found:
        return "one per batch (default)"
    unread(found, "one per batch")
    return "one per batch (default; '{}' is not a setting — one per batch or per task)".format(found.value)


def seat_models(home: str | Path) -> str:
    """'on' for `- seat models: on`; 'off' for off, no line, or (said once on stderr) a word it can't read."""
    value, found = _choice(home, "seat models", ("on", "off"))
    if found and not value:
        unread(found, "off")
    return value or "off"


def notifications_off(home: str | Path | None) -> bool:
    """`- notifications: off`; on with no line, or (said once on stderr) with a word it can't read."""
    value, found = _choice(home, "notifications", ("on", "off"))
    if found and not value:
        unread(found, "on")
    return value == "off"


def _in_range(raw: str) -> int | None:
    """An estimate figure as the helper reads it (seat_tokens), kept only inside 1k-1M."""
    value = cells.token_count(raw)
    return value if value is not None and 1000 <= value <= MAX_PER_WORKER else None


def worker_estimate(home: str | Path) -> int | None:
    """`- estimate per worker:` in tokens, or None when unset or (said once on stderr) not a figure inside 1k-1M:
    the route then keeps its no-history default."""
    found = pref(home, "estimate per worker")
    value = _in_range(found.said) if found else None
    if found and value is None:
        unread(found, "the route's own figure")
    return value


def role_pairs(home: str | Path | None, key: str) -> tuple[bool, list[tuple[str, str, str]]]:
    """The setting's `- key: role=value, ...` line as (written, [(role, equals, value)]): every word lower-cased
    and trimmed, an empty piece skipped. `- models:` and `- estimates:` read this way."""
    found = pref(home, key, empty=True)
    return (True, pairs(found.said)) if found else (False, [])


def pairs(text: str) -> list[tuple[str, str, str]]:
    """The text after a role line's key as (role, equals, value) pieces, as role_pairs reads them."""
    text = bytewise.lower(text.replace("\r", "").split("<!--", 1)[0].strip(" \t"))
    pieces = [piece.strip(" \t") for piece in text.split(",")]
    return [(w[0].strip(" \t"), w[1], w[2].strip(" \t")) for w in (p.partition("=") for p in pieces if p)]


def limit_seconds(raw: str) -> int | None:
    """The helper's limit_seconds: '90', '15m', '2 hours' in seconds; None for anything else (or 0)."""
    value = bytewise.lower(re.sub(r"[ \t\r]", "", raw))
    digits = re.match(r"[0-9]*", value).group(0)
    unit = value[len(digits):]
    digits = digits.lstrip("0")
    if not digits or len(digits) >= 8:
        return None
    scale = {"": 1, "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
             "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
             "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600}.get(unit)
    return None if scale is None else int(digits) * scale


def gate_time_limit(home: str | Path) -> tuple[int | None, str]:
    """`- gate time limit:` as (seconds, the words written); seconds is None when unset or not a time (the gate
    names the words it couldn't read)."""
    found = pref(home, "gate time limit")
    raw = found.said if found else ""
    return (limit_seconds(raw) if raw else None), raw


HARD_RULES = "## Hard rules"


def hard_rules(home: str | Path | None) -> list[str]:
    """The first `## Hard rules` section's lines (the heading in any capitals, a `(…)` after it allowed), word for
    word, up to the next `## ` heading: blank lines at either end and the template's `- <…>` placeholder (with the
    indented lines carrying it on) left out."""
    found: list[str] = []
    inside, seen, placeholder = False, False, False
    for line in _lines(home):
        if line.startswith("## "):
            seen = seen or inside
            inside = not seen and cells.heading(line) == "hard rules"
            continue
        if not inside:
            continue
        if re.match(r"[ \t]*[-*][ \t]+<", line) or (placeholder and re.match(r"[ \t]+[^ \t]", line)):
            placeholder = True
            continue
        placeholder = False
        found.append(line)
    while found and not found[-1].strip():
        found.pop()
    while found and not found[0].strip():
        found.pop(0)
    return found


def field(home: str | Path, key: str) -> str:
    """A `key:` line of the config (stack-fingerprint, last-verified), as the helper's field reads it: cells.field."""
    return cells.field((paths.contents(path(home)) or b"").decode("utf-8", "surrogateescape"), key)


def _memory_section(home: str | Path) -> Iterator[str]:
    """The config's lines under its ## Memory section, as the helper's memory_file reads them."""
    under = False
    for line in bytewise.file_lines(path(home), fold=False):
        if re.match(r"##[ \t]", line):
            under = bool(re.match(r"##[ \t]+[Mm][Ee][Mm][Oo][Rr][Yy]([^A-Za-z]|\Z)", line))
        elif under:
            yield line


def memory_line(home: str | Path) -> tuple[str, str] | None:
    """The `- conventions:` path under ## Memory as the helper's memory_file reads it: the value with CRs, quotes,
    a trailing (note) and a " — aside" taken off, and its first word (a path may hold a blank; a note may follow
    one); None when there is no such line."""
    for line in _memory_section(home):
        if re.match(r"[ \t]*[-*][ \t]*conventions:", line):
            v = re.sub(r"[\r`\"']", "", re.sub(r"\A[ \t]*[-*][ \t]*conventions:[ \t]*", "", line, count=1))
            v = re.sub(r"[ \t]+\([^()]*\)[ \t]*\Z", "", v, count=1)
            v = re.sub(r"[ \t]+(—|–|-)[ \t].*\Z", "", v, count=1, flags=re.S)
            v = re.sub(r"[ \t]+\Z", "", v, count=1)
            return v, re.sub(r"[ \t].*\Z", "", v, count=1, flags=re.S)
    return None


def memory_kb(raw: str) -> int | None:
    """A memory budget as written ("40 KB", "40kb", "40"): a whole number of KB from 1 to 1024; None for any
    other words."""
    found = re.fullmatch(r"([0-9]+)[ \t]*(?:[Kk][Bb])?", raw)
    kb = cells.optional_number(found.group(1)) if found else None
    return kb if kb is not None and 1 <= kb <= 1024 else None


def memory_budget(home: str | Path) -> tuple[int, str]:
    """The first `- memory budget: <n> KB` under ## Memory as (bytes, the words written, its notes off as pref_of
    takes them): n × 1024 bytes, or memory.COUNCIL_MEMORY_SIZE_LIMIT (25 KB) with no such line or with words
    memory_kb can't read."""
    from council.records.memory import COUNCIL_MEMORY_SIZE_LIMIT   # memory.py reads this module, so not at the top
    for line in _memory_section(home):
        found = pref_of(line)
        if found and found.key == "memory budget":
            kb = memory_kb(found.said)
            return (kb * 1024 if kb else COUNCIL_MEMORY_SIZE_LIMIT), found.said
    return COUNCIL_MEMORY_SIZE_LIMIT, ""


class Seat(NamedTuple):
    """One row of the config's Roster table, C-locale text (records/bytewise.py); '' for an empty cell."""

    seat: str
    slug: str
    lens: str
    reference: str


def roster_table(home: str | Path) -> list[Seat]:
    """The Roster table under ## Roster (cells.heading) as the helper's awk read it: cells split by cells.table_cells,
    its columns found by their header names (Seat, else the first; Slug; Lens; Reference), each cell trimmed of
    blanks, CRs, backticks and asterisks; a row with no seat, a rule row or a <placeholder> seat left out, and a
    <placeholder> slug or reference read as empty."""
    found, inside, columns = [], False, None
    for line in bytewise.records(bytewise.read(paths.contents(path(home)) or b"")):
        if line.startswith("## "):
            inside, columns = cells.heading(line) == "roster", None
            continue
        if not inside or not line.startswith("|"):
            continue
        cut = cells.table_cells(line)
        if columns is None:
            names = [bytewise.lower(_cell(c)) for c in cut]
            columns = tuple(max([i for i in range(1, len(cut) - 1) if names[i] == h] or [d])
                            for h, d in (("seat", 1), ("slug", 0), ("lens", 0), ("reference", 0)))
            continue
        seat, slug, lens, ref = (_cell(cut[i]) if i and i < len(cut) else "" for i in columns)
        if seat == "" or re.fullmatch(r":?-+:?", seat) or seat.startswith("<"):
            continue
        slug = "" if slug.startswith("<") else slug
        ref = "" if ref.startswith("<") or re.fullmatch(r":?-+:?", ref) else ref
        found.append(Seat(seat, slug, lens, ref))
    return found


def _cell(c: str) -> str:
    return re.sub("[`*]", "", re.sub(r"\A[ \t\r]+|[ \t\r]+\Z", "", c))


def estimate_tokens(text: str) -> int | None:
    """A figure for the estimate per worker ('150k', '150000', '150,000', '1.2M') as tokens, read by the
    route's rule (worker_estimate): None when unreadable, such as '1,50k', or outside 1k-1M."""
    if not re.fullmatch(r"[0-9][0-9.,]*[ \t]*[kKmM]?", str(text).strip(" \t")):
        return None
    return _in_range(str(text))


def _models_read(value: str) -> bool:
    from council.records import models          # models.py reads this module, so not at the top
    return not models.parse(pairs(value)).problem


def _estimates_read(value: str) -> bool:
    from council.records import estimates       # estimates.py reads this module, so not at the top
    return all(equals and role in estimates.ROLES and estimate_tokens(figure) for role, equals, figure in pairs(value))


def _pushes_read(value: str) -> bool:
    from council.records import pushes          # pushes.py reads this module, so not at the top
    return pushes.readable(value)


def _sharing_read(value: str) -> bool:
    from council.records import sharing         # sharing.py reads this module, so not at the top
    return sharing.word(value) != ""


def _one_of(*words: str) -> Callable[[str], bool]:
    return lambda value: value in words


# Every setting the helper or the Chair reads from a `- key:` line: the words it takes, and whether a value reads.
SETTINGS: dict[str, tuple[str, Callable[[str], bool]]] = {
    "approve without asking": ("solo, squad or full (as `up to squad`)",
                               lambda value: re.fullmatch(r"(up to )?(solo|squad|full)", value) is not None),
    "agent cap": ("a whole number of agents, such as 10", lambda value: _cap(value) is not None),
    "seat models": ("on or off", _one_of("on", "off")),
    "models": ("builder=, review= and verifier=, each inherit, fable, opus, sonnet or haiku", _models_read),
    "build tier": ("light or full", _one_of("light", "full")),
    "checking": ("one per batch or per task", _one_of(*CHECKING)),
    "open items": ("ask or fix now", _one_of("ask", "fix now")),
    "pushes": ("on, off or off until <YYYY-MM-DD>", _pushes_read),
    "sharing": ("team or just me", _sharing_read),
    "notifications": ("on or off", _one_of("on", "off")),
    "estimate per worker": ("a token figure from 1k to 1M, such as 150k", lambda value: _in_range(value) is not None),
    "estimates": ("review=, plan=, builder=, verifier= and converge=, each a token figure from 1k to 1M, such as "
                  "builder=450k", _estimates_read),
    "gate time limit": ("a time, such as 90, 15m or 2 hours", lambda value: limit_seconds(value) is not None),
    "guardrails": ("declined", _one_of("declined")),
    "memory budget": ("a size from 1 to 1024 KB, such as 25 KB", lambda value: memory_kb(value) is not None),
}
# Settings an older plugin read that this one doesn't: the key, and what became of it.
RETIRED = {"context packs": "context packs were removed (1.0); nothing replaced them, so the line does nothing"}


def problems(home: str | Path | None) -> list[Pref]:
    """Each setting whose line (its first, as the readers take it) has a value its setting can't read."""
    seen: set[str] = set()
    found = []
    for _, line in prefs(home):
        if line.key in SETTINGS and line.key not in seen:
            seen.add(line.key)
            if line.value and not SETTINGS[line.key][1](line.value):
                found.append(line)
    return found
