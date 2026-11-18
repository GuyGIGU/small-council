"""A build log's '## Converge' table (council-implement writes it at Challenge): each task's final result, and
whether a fix came after the check found it short. The status's closing card reads it."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from council.records import cells
from council.records.cells import clean
from council.records.home import absolute, native
from council.records.paths import contained, linked, text_of

RESULT = re.compile(r"(not met|partly met|partly|blocked|met)\b")
KEYS = {"not met": "not_met", "partly met": "partly", "partly": "partly", "blocked": "blocked", "met": "met"}


def result_of(cell: str) -> str:
    """A Converge Result cell's verdict, read after its last arrow ("partly met → met" is met) by its first words:
    met, partly, not_met, blocked or other."""
    words = re.sub(r"[`*_]", "", re.split("→|->", cell)[-1]).strip().lower()
    found = RESULT.match(words)
    return KEYS[found.group(1)] if found else "other"


def fixed_after(cell: str) -> bool:
    """A met result that records the check finding it short first: an earlier verdict before an arrow ("partly met →
    met"), or one named after the leading "met" ("met (after 8cbfc45; verify-5 partly met)")."""
    parts = re.split("→|->", cell)
    if len(parts) > 1:
        return result_of(parts[0]) != "met"
    words = re.sub(r"[`*_]", "", cell).strip().lower()
    return re.search(r"\b(not met|partly met|partly|blocked)\b", words[3:]) is not None


def read(run: str | Path, deliverable: str) -> dict[str, Any]:
    """A build's final check, from its log's '## Converge' table (council-implement writes it at Challenge): each
    task's final result, and whether a fix came after the check found it short. {"missing": why} when no such
    table can be read: no deliverable, one outside the council home's logs folder, unreadable, or without one."""
    run = Path(run)
    if not deliverable:
        return {"missing": "no build log recorded"}
    home = run.parent.parent
    logs = home / "logs"
    path = Path(native(deliverable)) if absolute(deliverable) else home.parent / deliverable
    if run.parent.name != "runs" or linked(logs) or not contained(path, logs):
        return {"missing": "the build log isn't in the council's logs folder"}
    content = text_of(path, logs)
    if not content:
        return {"missing": "the build log can't be read"}
    rows = table(content)
    if not rows:
        return {"missing": "the build log has no Converge table"}
    return {"rows": rows}


def table(content: str) -> list[dict[str, Any]]:
    """The rows of the table under the log's '## Converge' heading, keyed by its Task, Done when and Result."""
    rows: list[dict[str, Any]] = []
    inside, columns = False, None
    for line in cells.lines_of(content):
        if line.startswith("## "):
            if inside:
                break
            inside = line[3:].strip().lower() == "converge"
            continue
        if not inside:
            continue
        if not line.lstrip().startswith("|"):
            if columns is not None:
                break                               # the table ended
            continue
        row = [clean(c) for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if columns is None:
            names = [c.lower() for c in row]
            if "result" not in names:
                break
            columns = {name: names.index(name) for name in ("task", "done when", "result") if name in names}
            continue
        if all(re.fullmatch(r":?-{3,}:?", c) for c in row if c):
            continue                                # the header's rule
        cell = {name: row[at] if at < len(row) else "" for name, at in columns.items()}
        result = cell.get("result", "")
        final = result_of(result)
        rows.append({"task": cell.get("task", "").replace("`", "")[:40] or str(len(rows) + 1),
                     "done_when": cell.get("done when", "").replace("`", "")[:200], "result": final,
                     "fixed_after": final == "met" and fixed_after(result)})
        if len(rows) >= 500:
            break
    return rows
