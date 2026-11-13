"""council.config.md: one reader per setting, each with its stated default.

The `configured_*` readers follow bin/council's functions of the same name line for line (sed reads every line,
its carriage return dropped as cells.lines_of drops it, and the first match wins). The others follow the Python
reader that already used them, and say where the helper reads the line differently.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

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


# --- the Gates table, as bin/council's config_gates and gates_listed read it ----------------------------------
class Gate(NamedTuple):
    """One Gates row: its cells as written ('-' for an empty one) and the three small vocabularies read once."""

    name: str
    command: str          # backticks dropped; '-' when the Command cell is empty
    at: str
    mandatory: str
    cells: int            # the row's cell count, to compare with the header's
    checked: str
    side: str
    needs: str
    header_cells: int
    has_side: bool        # the table has a Side effects column (an older one does not)
    stages: str           # g, v, gv; m = by name only; - = an empty cell; ? added for a word naming no stage
    must: str             # yes, no, ?
    ran: str              # ok, not, ?


YES_MARKS, NO_MARKS = re.compile("✓|✔|✅|☑"), re.compile("✗|✘|❌|×")
SEPARATORS = re.compile("·|→|›|»|–|—|" + chr(0xA0))
PUNCTUATION = re.compile(r"""[]*_`()[,;/+&:.!?"]""")
MUST_YES = ("yes", "y", "true", "mandatory", "required", "require", "must", "always", "blocking", "blocks",
            "blocker", "1")
MUST_NO = ("no", "n", "false", "not", "optional", "advisory", "never", "informational", "0")
NOT_MUST = re.compile(r"(non|not)-(blocking|blocker|mandatory|required|require|must|gating)")
RAN_OK = ("yes", "y", "true", "ok", "okay", "pass", "passed", "passes", "passing", "green", "probed", "checked",
          "verified", "runs", "ran", "works", "runnable")
RAN_NOT = ("no", "n", "false", "not", "never", "fails", "failed", "failing", "broken", "blocked", "skip", "skipped",
           "unrunnable", "unprobed")
HEADS = {"gate": 0, "name": 0, "command": 1, "runat": 2, "mandatory": 3, "checked": 4}


def _raw_lines(home: str | Path) -> list[str]:
    """The config's lines as awk reads them: split on newline only, a carriage return kept, bytes that are
    not UTF-8 kept as they came (surrogateescape)."""
    try:
        data = path(home).read_bytes()
    except OSError:
        return []
    lines = data.decode("utf-8", errors="surrogateescape").split("\n")
    return lines[:-1] if lines and lines[-1] == "" else lines


def table_cells(line: str) -> list[str]:
    """A table row split on '|' outside backticks; '\\|' is a literal pipe (config_gates' cells)."""
    out, current, quoted, i = [], "", False, 0
    while i < len(line):
        char = line[i]
        if char == "\\" and line[i + 1:i + 2] == "|":
            current, i = current + "|", i + 2
            continue
        if char == "`":
            quoted = not quoted
        if char == "|" and not quoted:
            out.append(current)
            current = ""
        else:
            current += char
        i += 1
    return out + [current]


def _trim(value: str) -> str:
    return value.replace("\t", " ").strip(" \r")


def _words(value: str) -> list[str]:
    value = YES_MARKS.sub(" yes ", value.lower())
    value = SEPARATORS.sub(" ", NO_MARKS.sub(" no ", value))
    return re.split(r"[ \t]+", PUNCTUATION.sub(" ", value))


def stages(cell: str) -> str:
    """A Run at cell as g, v, gv, m (by name only), - (empty), with ? for a word that names no stage."""
    found = set()
    for word in _words(re.sub(r"\([^)]*\)", " ", cell)):
        if word in ("", "and", "or", "only", "by", "on", "at", "stage", "stages", "-"):
            continue
        if word in ("grounding", "baseline"):
            found.add("g")
        elif word in ("verify", "verification"):
            found.add("v")
        elif word in ("both", "all", "always", "every"):
            found.update("gv")
        elif word in ("manual", "manually", "never", "none", "no", "name", "hand", "demand"):
            found.add("m")
        else:
            found.add("?")
    said = "".join(s for s in "gv" if s in found)
    said += "?" if "?" in found else ("m" if "m" in found and not said else "")
    return said or "-"


def must(cell: str) -> str:
    """A Mandatory cell: yes, no, or ? — the first word that decides wins."""
    for word in _words(cell):
        if word in MUST_YES:
            return "yes"
        if word in MUST_NO or NOT_MUST.fullmatch(word):
            return "no"
    return "?"


def ran(cell: str) -> str:
    """A Checked cell: ok, not, or ? — the first word that decides wins; a bare date reads as ok."""
    dated = False
    for word in _words(cell):
        if word in RAN_OK:
            return "ok"
        if word in RAN_NOT:
            return "not"
        dated = dated or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", word) is not None
    return "ok" if dated else "?"


def _columns(row: list[str]) -> list[int]:
    """The header row's columns (1-based, as awk counts): gate, command, run at, mandatory, checked,
    side effects and needs (0 when the table has none)."""
    found = [2, 3, 4, 5, 6, 0, 0]
    for i in range(2, len(row)):
        head = re.sub(r"[^a-z]", "", _trim(row[i - 1]).lower())
        if head in HEADS:
            found[HEADS[head]] = i
        elif head.startswith("sideeffect"):
            found[5] = i
        elif head.startswith("needs"):
            found[6] = i
    return found


def _row(row: list[str], columns: list[int], header_cells: int) -> Gate | None:
    def cell(column: int) -> str:
        return _trim(row[column - 1]) if 0 < column <= len(row) else ""
    name, command = cell(columns[0]), cell(columns[1]).replace("`", "")
    if name == "" or re.fullmatch(r":?-+:?", name) or name.startswith("<") or command.startswith("<"):
        return None
    at, mandatory, checked = cell(columns[2]), cell(columns[3]), cell(columns[4])
    return Gate(name, command or "-", at or "-", mandatory or "-", len(row), checked or "-", cell(columns[5]) or "-",
                cell(columns[6]) or "-", header_cells, columns[5] > 0, stages(at), must(mandatory), ran(checked))


def gates(home: str | Path) -> list[Gate]:
    """config_gates: every row of the Gates table, its header found by the column names, so an older table
    (no Side effects or Needs) still reads. A row with a name and an empty Command cell has '-' for a command."""
    found: list[Gate] = []
    inside, columns, header_cells = False, None, 0
    for line in _raw_lines(home):
        if line.startswith("## "):
            inside, columns = line.startswith("## Gates"), None
            continue
        if not inside or not line.startswith("|"):
            continue
        row = table_cells(line)
        if columns is None:                       # the header row names the columns; it is never a gate
            columns, header_cells = _columns(row), len(row)
            continue
        gate = _row(row, columns, header_cells)
        if gate is not None:
            found.append(gate)
    return found


def _listed_command(line: str) -> bool:
    return re.search(r"`[^`]+`", line) is not None and re.search(r"`council[ -]", line) is None


def gates_listed(home: str | Path) -> bool:
    """gates_listed: a Gates section still written as a list (the layout before the table) — a backticked
    command in a list item or on an indented line under one, and no table. A backticked council command is
    a note, not a gate."""
    inside = item = comment = listed = table = False
    for line in _raw_lines(home):
        if line.startswith("## "):
            inside, item = line.startswith("## Gates"), False
            continue
        if not inside:
            continue
        if re.match(r"[ \t]*<!--", line):
            comment = True
        if comment:
            comment = "-->" not in line
            continue
        if line.startswith("|"):
            table, item = True, False
        elif re.match(r"[ \t]*([-*+]|[0-9]+[.)])[ \t]", line):
            item, listed = True, listed or _listed_command(line)
        elif re.fullmatch(r"[ \t]*", line):
            continue
        elif re.match(r"[ \t]", line):
            listed = listed or (item and _listed_command(line))
        else:
            item = False
    return listed and not table
