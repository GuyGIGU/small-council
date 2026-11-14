"""council.config.md: one reader per setting, each with its stated default.

The `configured_*` readers follow bin/council's functions of the same name line for line (sed reads every line,
its carriage return dropped as cells.lines_of drops it, and the first match wins). The others follow the Python
reader that already used them, and say where the helper reads the line differently.
"""
from __future__ import annotations

import re
from pathlib import Path

from council.records import bytewise, cells, paths

NAME = "council.config.md"
INTMAX = 2 ** 63 - 1     # the largest whole number bash's test reads; a larger one fails the test
AGENT_CAP = 10
SPACE = "[ \t\n\r\f\v]"  # sed's [[:space:]]
MAX_EDIT = 1024 * 1024
MAX_PER_WORKER = 1000000
ESTIMATE_LINES = re.compile(r"^[ \t]*-[ \t]*estimate per worker:[^\r\n]*", re.MULTILINE)
ESTIMATE_PARTS = re.compile(r"([ \t]*-[ \t]*estimate per worker:[ \t]*)([0-9][0-9.,]*[ \t]*[kKmM]?)?(.*)$")


class ConfigError(paths.RecordError):
    """The config can't be edited safely; the message says what to do instead."""


def path(home: str | Path) -> Path:
    """The config file of a council home."""
    return Path(home) / NAME


def _lines(home: str | Path | None) -> list[str]:
    """The config's lines as the helper's sed and awk read them (links followed, no size limit, each
    line's carriage return dropped: cells.lines_of)."""
    try:
        data = path(home).read_bytes()        # type: ignore[arg-type]
    except (OSError, TypeError):
        return []
    return cells.lines_of(data.decode("utf-8", errors="replace"))


def first(home: str | Path | None, pattern: str) -> re.Match | None:
    """The first config line the pattern matches from its start, as sed -n 's/…/p' | head -n 1 finds it."""
    rule = re.compile(pattern)
    for line in _lines(home):
        found = rule.match(line)
        if found:
            return found
    return None


def agent_cap(home: str | Path | None) -> int:
    """configured_agent_cap: the first `- agent cap: N`, else 10 (also for 0 or a number bash can't read)."""
    found = first(home, SPACE + "*-" + SPACE + "*agent cap:" + SPACE + "*([0-9]+)")
    if not found:
        return AGENT_CAP
    value = int(found.group(1).lstrip("0")[:20] or "0")      # int() refuses 4,300 digits; 20 are past INTMAX anyway
    return value if 0 < value <= INTMAX else AGENT_CAP


def build_tier(home: str | Path) -> str:
    """configured_build_tier: 'light (config)' or 'full (config)', else light as a default, said so."""
    found = first(home, SPACE + "*-" + SPACE + "*build tier:" + SPACE + "*([A-Za-z]*)")
    tier = found.group(1).lower() if found else ""
    if tier in ("light", "full"):
        return "{} (config)".format(tier)
    if not tier:
        return "light (default)"
    return "light (default; '{}' is not a tier — light or full)".format(tier)


CHECKING = ("one per batch", "per task")


def checking(home: str | Path | None) -> str:
    """configured_checking: 'one per batch (config)' or 'per task (config)', else one per batch as a
    default, said so (the first `- checking:` line, an HTML comment after it ignored, spaces folded)."""
    value = ""
    for line in _lines(home):
        found = re.match(r"[ \t]*-[ \t]*checking:[ \t]*", line)
        if found:
            value = re.sub(r"[ \t]*(<!--.*)?$", "", line[found.end():], count=1)
            value = re.sub(r"[ \t]+", " ", value).translate(ASCII_LOWER)
            break
    if value in CHECKING:
        return "{} (config)".format(value)
    if not value:
        return "one per batch (default)"
    return "one per batch (default; '{}' is not a setting — one per batch or per task)".format(value)


def _in_range(raw: str) -> int | None:
    """An estimate figure as the helper reads it (seat_tokens), kept only inside 1k-1M."""
    value = cells.token_count(raw)
    return value if value is not None and 1000 <= value <= MAX_PER_WORKER else None


def worker_estimate(home: str | Path) -> int | None:
    """configured_worker_estimate: `- estimate per worker:` in tokens, or None when unset or outside
    1k-1M (the route then keeps its no-history default)."""
    found = first(home, SPACE + "*-" + SPACE + "*estimate per worker:" + SPACE
                   + "*([0-9][0-9.,]*" + SPACE + "*[kKmM]?)")
    return _in_range(found.group(1)) if found else None


def seat_models(home: str | Path) -> str:
    """configured_seat_models: 'on' only for exactly `- seat models: on`; anything else is 'off'."""
    found = first(home, SPACE + "*-" + SPACE + "*seat models:" + SPACE + "*([A-Za-z]*)" + SPACE + r"*\Z")
    return "on" if found and found.group(1) == "on" else "off"


ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def limit_seconds(raw: str) -> int | None:
    """The helper's limit_seconds: '90', '15m', '2 hours' in seconds; None for anything else (or 0)."""
    value = re.sub(r"[ \t\r]", "", raw).translate(ASCII_LOWER)
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
    """`- gate time limit:` as (seconds, the words written); seconds is None when unset or not a time."""
    found = first(home, SPACE + "*-" + SPACE + "*gate time limit:" + SPACE + "*(.*)")
    raw = found.group(1).replace("\r", "") if found else ""
    return (limit_seconds(raw) if raw else None), raw


def notifications_off(home: str | Path | None) -> bool:
    """notifications_off: a `- notifications: off` line, a CRLF one included, in a config of any size."""
    rule = re.compile(r"[ \t]*-[ \t]*notifications:[ \t]*off[ \t]*(?:#.*)?", re.IGNORECASE)
    return any(rule.fullmatch(line) for line in _lines(home))


def field(home: str | Path, key: str) -> str:
    """A `key:` line of the config (stack-fingerprint, last-verified), as the helper's field reads it: cells.field."""
    try:
        data = path(home).read_bytes()
    except OSError:
        return ""
    return cells.field(data.decode("utf-8", "surrogateescape"), key)


def memory_line(home: str | Path) -> tuple[str, str] | None:
    """The `- conventions:` path under ## Memory as the helper's memory_file reads it: the value with CRs, quotes,
    a trailing (note) and a " — aside" taken off, and its first word (a path may hold a blank; a note may follow
    one); None when there is no such line. memory_path() is status.py's older reading of the same line."""
    try:
        text = path(home).read_bytes().decode("utf-8", "surrogateescape")
    except OSError:
        return None
    under = False
    for line in text.split("\n")[:-1] if text.endswith("\n") else text.split("\n"):
        if re.match(r"##[ \t]", line):
            under = bool(re.match(r"##[ \t]+[Mm][Ee][Mm][Oo][Rr][Yy]([^A-Za-z]|\Z)", line))
            continue
        if under and re.match(r"[ \t]*[-*][ \t]*conventions:", line):
            v = re.sub(r"[\r`\"']", "", re.sub(r"\A[ \t]*[-*][ \t]*conventions:[ \t]*", "", line, count=1))
            v = re.sub(r"[ \t]+\([^()]*\)[ \t]*\Z", "", v, count=1)
            v = re.sub(r"[ \t]+(—|–|-)[ \t].*\Z", "", v, count=1, flags=re.S)
            v = re.sub(r"[ \t]+\Z", "", v, count=1)
            return v, re.sub(r"[ \t].*\Z", "", v, count=1, flags=re.S)
    return None


def memory_path(home: str | Path) -> str:
    """The `- conventions:` path under the ## Memory heading, quotes and a trailing note taken off;
    '' when none is set (status.py's reading of what the helper's memory_file reads)."""
    in_memory = False
    for line in paths.text_of(path(home), home).splitlines():
        if re.match(r"^##[ \t]+", line):
            in_memory = bool(re.match(r"^##[ \t]+Memory(?:\W|$)", line, re.I))
        elif in_memory:
            match = re.match(r"^[ \t]*[-*][ \t]*conventions:[ \t]*(.*)$", line, re.I)
            if match:
                configured = match.group(1).strip().strip('`"\'')
                configured = re.sub(r"[ \t]+\([^()]*\)[ \t]*$", "", configured)
                return re.sub(r"[ \t]+[—–-][ \t].*$", "", configured).strip()
    return ""


def roster(home: str | Path) -> list[tuple[str, str, str]]:
    """The Roster table's (seat, slug, lens) rows, in order, from the first table whose header names
    Seat, Slug and Lens; a row missing any of the three is left out."""
    found, columns = [], None
    for line in cells.lines_of(paths.text_of(path(home), home)):
        if not line.lstrip().startswith("|"):
            columns = None
            continue
        row = [c.strip() for c in line.strip().strip("|").split("|")]
        lower = [c.lower() for c in row]
        if {"seat", "slug", "lens"} <= set(lower):
            columns = (lower.index("seat"), lower.index("slug"), lower.index("lens"))
        elif columns and len(row) > max(columns) and not set(row[0]) <= set("-: "):
            seat, slug, lens = (cells.clean(row[i]).strip("`") for i in columns)
            if slug and lens and seat:
                found.append((seat, slug, lens))
    return found


def roster_rows(home: str | Path) -> list[tuple[str, str, str]]:
    """The Roster table under ## Roster as the helper's awk read it, for memory and doctor: (slug, seat,
    reference), "-" for an empty value, its columns found by their header names (Seat, else the first; Slug;
    Reference), each cell trimmed of blanks, CRs, backticks and asterisks; a row with no seat, a rule row or a
    <placeholder> left out. C-locale text (records/bytewise.py). roster() is the older reading that needs a Lens."""
    try:
        text = bytewise.read(path(home).read_bytes())
    except OSError:
        return []
    found, inside, columns = [], False, None
    for line in bytewise.records(text):
        if line.startswith("## "):
            inside, columns = line.startswith("## Roster"), None
            continue
        if not inside or not line.startswith("|"):
            continue
        cut = line.split("|")
        if columns is None:
            names = [bytewise.lower(_cell(c)) for c in cut]
            columns = tuple(max([i for i in range(1, len(cut) - 1) if names[i] == h] or [d])
                            for h, d in (("seat", 1), ("slug", 0), ("reference", 0)))
            continue
        seat, slug, ref = (_cell(cut[i]) if i and i < len(cut) else "" for i in columns)
        if seat == "" or re.fullmatch(r":?-+:?", seat) or seat.startswith("<"):
            continue
        slug = "" if slug.startswith("<") else slug
        ref = "" if ref.startswith("<") or re.fullmatch(r":?-+:?", ref) else ref
        found.append((slug or "-", seat, ref or "-"))
    return found


def _cell(c: str) -> str:
    return re.sub("[`*]", "", re.sub(r"\A[ \t\r]+|[ \t\r]+\Z", "", c))


# --- the estimate per worker, as `council tune` reads and edits it ------------------------------------------
def editable(home: str | Path) -> tuple[Path, str]:
    """The config's path and text for an edit; refuses a link, a missing file and one over 1 MB."""
    where = path(home)
    if where.is_symlink():
        raise ConfigError("council.config.md is a link — change the file it points to by hand")
    if not where.is_file():
        raise ConfigError("no council.config.md in {} — run council-init".format(home))
    raw = where.read_bytes()
    if len(raw) > MAX_EDIT:
        raise ConfigError("council.config.md is over 1 MB; refusing to edit it")
    return where, raw.decode("utf-8")


def estimate_tokens(text: str) -> int | None:
    """A figure for the estimate per worker ('150k', '150000', '150,000', '1.2M') as tokens, read by the
    route's rule (worker_estimate): None when unreadable, such as '1,50k', or outside 1k-1M. `council tune`
    shows and applies only what the route would read, so the run is sized by the number it was shown."""
    if not re.fullmatch(r"[0-9][0-9.,]*[ \t]*[kKmM]?", str(text).strip(" \t")):
        return None
    return _in_range(str(text))


def estimate_line(text: str) -> tuple[int | None, str | None]:
    """(value, the exact line) of the first estimate-per-worker line; value None when it is unreadable,
    both None when there is no such line."""
    found = ESTIMATE_LINES.search(text)
    if not found:
        return None, None
    value = ESTIMATE_PARTS.match(found.group(0)).group(2)
    return (estimate_tokens(value) if value else None), found.group(0)


def preferences_insertion(text: str, line: str) -> tuple[int, str]:
    """(offset, exact text) that adds line as the last item of ## Run preferences, outside HTML comments."""
    newline = "\r\n" if text.count("\r\n") * 2 > text.count("\n") else "\n"
    section = re.search("^(?:" + paths.BOM + r")?## Run preferences[ \t]*\r?$", text, re.MULTILINE)
    if not section:
        raise ConfigError("council.config.md has no ## Run preferences section — a council-init refresh adds one")
    rest = text[section.end():]
    end = re.search(r"^## ", rest, re.MULTILINE)
    body = rest[:end.start()] if end else rest
    comments = [(m.start(), m.end()) for m in re.finditer(r"<!--.*?(?:-->|\Z)", body, re.DOTALL)]
    items = [m for m in re.finditer(r"^[ \t]*-[^\r\n]*(?:\r?\n|\Z)", body, re.MULTILINE)
             if not any(a <= m.start() < b for a, b in comments)]
    if items:
        at = section.end() + items[-1].end()
    else:
        heading_end = re.match(r"\r?\n", rest)
        at = section.end() + (heading_end.end() if heading_end else 0)
    if at >= len(text) and not text.endswith("\n"):
        return at, newline + line
    return at, line + newline
