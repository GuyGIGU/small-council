"""The Gates table of council.config.md: the gates a project has, as bin/council's config_gates and gates_listed
read it — its header found by the column names, so an older table (no Side effects or Needs) still reads. Read
by `council gate`, `gate --all`, `council gates` and `council doctor`; bin/council keeps its config_gates awk for
`run close` until that is ported (S8b). An optional Covers column names the paths a gate checks (#47)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from council.records import bytewise, cells, config


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
    covers: tuple[str, ...] = ()    # the Covers cell's git pathspecs; () when empty or absent: the whole tree


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


def paths(cell: str) -> tuple[str, ...]:
    """A Covers cell as git pathspecs: comma separated, backticks dropped; empty, '-' or '—' is the whole tree."""
    found = tuple(part.strip(" `") for part in cell.split(","))
    return tuple(part for part in found if part not in ("", "-", "—", "–"))


def _columns(row: list[str]) -> list[int]:
    """The header row's columns (1-based, as awk counts): gate, command, run at, mandatory, checked,
    side effects, needs and covers (0 when the table has none)."""
    found = [2, 3, 4, 5, 6, 0, 0, 0]
    for i in range(2, len(row)):
        head = re.sub(r"[^a-z]", "", _trim(row[i - 1]).lower())
        if head in HEADS:
            found[HEADS[head]] = i
        elif head.startswith("sideeffect"):
            found[5] = i
        elif head.startswith("needs"):
            found[6] = i
        elif head.startswith("covers"):
            found[7] = i
    return found


def _row(row: list[str], columns: list[int], header_cells: int) -> Gate | None:
    def cell(column: int) -> str:
        return _trim(row[column - 1]) if 0 < column <= len(row) else ""
    name, command = cell(columns[0]), cell(columns[1]).replace("`", "")
    if name == "" or re.fullmatch(r":?-+:?", name) or name.startswith("<") or command.startswith("<"):
        return None
    at, mandatory, checked = cell(columns[2]), cell(columns[3]), cell(columns[4])
    return Gate(name, command or "-", at or "-", mandatory or "-", len(row), checked or "-", cell(columns[5]) or "-",
                cell(columns[6]) or "-", header_cells, columns[5] > 0, stages(at), must(mandatory), ran(checked),
                paths(cell(columns[7])))


def gates(home: str | Path) -> list[Gate]:
    """config_gates: every row of the Gates table, its header found by the column names, so an older table
    (no Side effects or Needs) still reads. A row with a name and an empty Command cell has '-' for a command."""
    found: list[Gate] = []
    inside, columns, header_cells = False, None, 0
    for line in bytewise.file_lines(config.path(home), fold=False):
        heading = cells.heading(line)
        if heading is not None:
            inside, columns = heading.startswith("gates"), None
            continue
        if not inside or not line.startswith("|"):
            continue
        row = cells.table_cells(line)
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
    for line in bytewise.file_lines(config.path(home), fold=False):
        heading = cells.heading(line)
        if heading is not None:
            inside, item = heading.startswith("gates"), False
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
