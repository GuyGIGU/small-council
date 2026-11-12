"""council.config.md: one reader per setting, each with its stated default.

The `configured_*` readers follow bin/council's functions of the same name line for line (sed reads
every line, carriage return included, and the first match wins). The others follow the Python reader
that already used them, and say where the helper reads the line differently.
"""

from pathlib import Path
import re
from typing import List, Optional, Tuple, Union

from council.records import cells, paths

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


def path(home: Union[str, Path]) -> Path:
    """The config file of a council home."""
    return Path(home) / NAME


def _lines(home: Union[str, Path, None]) -> List[str]:
    """The config's lines as sed reads them (links followed, no size limit, carriage returns kept)."""
    try:
        data = path(home).read_bytes()        # type: ignore[arg-type]
    except (OSError, TypeError):
        return []
    return data.decode("utf-8", errors="replace").split("\n")


def _first(home: Union[str, Path, None], pattern: str) -> Optional["re.Match"]:
    rule = re.compile(pattern)
    for line in _lines(home):
        found = rule.match(line)
        if found:
            return found
    return None


def agent_cap(home: Union[str, Path, None]) -> int:
    """configured_agent_cap: the first `- agent cap: N`, else 10 (also for 0 or a number bash can't read)."""
    found = _first(home, SPACE + "*-" + SPACE + "*agent cap:" + SPACE + "*([0-9]+)")
    if not found:
        return AGENT_CAP
    value = int(found.group(1))
    return value if 0 < value <= INTMAX else AGENT_CAP


def build_tier(home: Union[str, Path]) -> str:
    """configured_build_tier: 'light (config)' or 'full (config)', else light as a default, said so."""
    found = _first(home, SPACE + "*-" + SPACE + "*build tier:" + SPACE + "*([A-Za-z]*)")
    tier = found.group(1).lower() if found else ""
    if tier in ("light", "full"):
        return "{} (config)".format(tier)
    if not tier:
        return "light (default)"
    return "light (default; '{}' is not a tier — light or full)".format(tier)


def worker_estimate(home: Union[str, Path]) -> Optional[int]:
    """configured_worker_estimate: `- estimate per worker:` in tokens, or None when unset or outside
    1k-1M (the route then keeps its no-history default)."""
    found = _first(home, SPACE + "*-" + SPACE + "*estimate per worker:" + SPACE
                   + "*([0-9][0-9.,]*" + SPACE + "*[kKmM]?)")
    if not found:
        return None
    value = cells.token_count(found.group(1))
    return value if value is not None and 1000 <= value <= MAX_PER_WORKER else None


def seat_models(home: Union[str, Path]) -> str:
    """configured_seat_models: 'on' only for exactly `- seat models: on`; anything else is 'off'."""
    found = _first(home, SPACE + "*-" + SPACE + "*seat models:" + SPACE + "*([A-Za-z]*)" + SPACE + r"*\Z")
    return "on" if found and found.group(1) == "on" else "off"


def sharing(home: Union[str, Path]) -> str:
    """configured_sharing: 'just me' for just me, just-me or private; 'team' for anything else or none."""
    found = _first(home, SPACE + "*-" + SPACE + "*sharing:" + SPACE + "*(.*)")
    value = found.group(1).replace("\r", "").translate(_ASCII_LOWER) if found else ""
    words = ("just me", "just-me", "private")
    if any(value == word or value.startswith(word + " ") for word in words):
        return "just me"
    return "team"


_ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def limit_seconds(raw: str) -> Optional[int]:
    """The helper's limit_seconds: '90', '15m', '2 hours' in seconds; None for anything else (or 0)."""
    value = re.sub(r"[ \t\r]", "", raw).translate(_ASCII_LOWER)
    digits = re.match(r"[0-9]*", value).group(0)
    unit = value[len(digits):]
    digits = digits.lstrip("0")
    if not digits or len(digits) >= 8:
        return None
    scale = {"": 1, "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
             "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
             "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600}.get(unit)
    return None if scale is None else int(digits) * scale


def gate_time_limit(home: Union[str, Path]) -> Tuple[Optional[int], str]:
    """`- gate time limit:` as (seconds, the words written); seconds is None when unset or not a time."""
    found = _first(home, SPACE + "*-" + SPACE + "*gate time limit:" + SPACE + "*(.*)")
    raw = found.group(1).replace("\r", "") if found else ""
    return (limit_seconds(raw) if raw else None), raw


def notifications_off(home: Union[str, Path, None]) -> bool:
    """`- notifications: off` (status.py's reading: a config over 64 KB, or a link, reads as on, and so
    does a line ending in a carriage return, which the helper's notifications_off strips first)."""
    if home is None:
        return False
    content = paths.text_of(path(home), home, limit=65536)
    return bool(re.search(r"(?im)^[ \t]*-[ \t]*notifications:[ \t]*off[ \t]*(?:#.*)?$", content))


def memory_path(home: Union[str, Path]) -> str:
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


def roster(home: Union[str, Path]) -> List[Tuple[str, str, str]]:
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


# --- the estimate per worker, as `council tune` reads and edits it ------------------------------------------
def editable(home: Union[str, Path]) -> Tuple[Path, str]:
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


def estimate_tokens(text: str) -> Optional[int]:
    """'150k', '150000', '1.2M' as tokens; None when unreadable or outside 1k-1M. Commas anywhere in the
    digits are dropped, so '1,50k' reads as 150k here and as unset in the helper's route."""
    match = re.fullmatch(r"([0-9][0-9.,]*)[ \t]*([kKmM]?)", str(text).strip())
    if not match:
        return None
    try:
        value = float(match.group(1).replace(",", ""))
    except ValueError:
        return None
    value = int(round(value * {"k": 1000, "m": 1000000}.get(match.group(2).lower(), 1)))
    return value if 1000 <= value <= MAX_PER_WORKER else None


def estimate_line(text: str) -> Tuple[Optional[int], Optional[str]]:
    """(value, the exact line) of the first estimate-per-worker line; value None when it is unreadable,
    both None when there is no such line."""
    found = ESTIMATE_LINES.search(text)
    if not found:
        return None, None
    value = ESTIMATE_PARTS.match(found.group(0)).group(2)
    return (estimate_tokens(value) if value else None), found.group(0)


def preferences_insertion(text: str, line: str) -> Tuple[int, str]:
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
