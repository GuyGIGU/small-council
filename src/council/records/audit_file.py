"""audit.md: the run audit as `council run close` saw it, kept in the run folder, and the audit's report text.

The close writes it (scripts/audit.py --at-close --save), through the one atomic writer, whole each time: a
run closed again rewrites it. `council run audit` alone reads and prints the same report and writes nothing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from council.records import paths

NAME = "audit.md"
PASS, WARN, FAIL = "pass", "warn", "FAIL"
LATER = "later"                                   # at close: an item that can only happen after it
READ_ONLY = "Read-only: nothing was written."


def path(run: Path) -> Path:
    """The audit file of a run folder."""
    return Path(run) / NAME


def present(run: Path) -> bool:
    """Whether the run folder holds a saved audit (a link is not one)."""
    where = path(run)
    return where.is_file() and not where.is_symlink()


def mention(run: Path) -> str:
    """Where the saved audit is, as `runs/<run>/audit.md` under the council home, or '' when there is none."""
    return "runs/%s/%s" % (Path(run).name, NAME) if present(run) else ""


def card_line(run: Path) -> str:
    """The closing card's audit line: where the saved audit is, or that none was saved and how to read the run."""
    return mention(run) or "none saved: council run audit --run %s reads the run now" % Path(run).name


def said(run: str | Path) -> str:
    """The audit as `council run status` names it on a run's line, or '' when none is saved."""
    return "audit: " + mention(Path(run)) if present(Path(run)) else ""


def render(run: Any, items: list[tuple[str, str, str]], split: int, span: str, transcript: Path | None,
           found: bool, saving: bool) -> tuple[str, int]:
    """The audit report as text, and how many items failed. items are (verdict, label, words); the first
    `split` read the run's records and the rest the session transcript, whose window is span."""
    kept = "Saved as %s by council run close; closing again rewrites it." % NAME
    lines = ["Run audit: %s (%s, %s). %s" % (run.name, run.mode or "no mode", run.status or "no status",
                                              kept if saving else READ_ONLY)]
    if saving:
        lines.append("Taken at: " + datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    if transcript is not None:
        lines.append("Transcript: %s%s" % (transcript, " (found from the run's session id)" if found else ""))
    lines.append("\nFrom the run's records")
    for n, (verdict, label, words) in enumerate(items):
        if n == split:
            lines.append("\nFrom the session transcript (%s)" % span)
        lines.append("  %-4s  %s: %s" % (verdict, label, words))
    if span and split == len(items):
        lines.append("\nFrom the session transcript (%s): nothing to check" % span)
    if transcript is None:
        session = run.field("session")
        lines.append("\nNo transcript given: pass --transcript <session .jsonl> to check what the Chair showed and ran"
                     + (" (this run's session: %s)." % session if session else "."))
    counts = {v: sum(1 for item in items if item[0] == v) for v in (FAIL, WARN, PASS)}
    later = sum(1 for item in items if item[0] == LATER)
    lines.append("\n%d failed, %d warning(s), %d passed%s" % (counts[FAIL], counts[WARN], counts[PASS],
                                                           ", %d not checked yet" % later if later else ""))
    return "\n".join(lines), counts[FAIL]


def save(run: Path, text: str) -> str:
    """Write text as the run's audit.md, atomically; the line to print: 'Saved: <path>' or 'Not saved: <why>'."""
    where = path(run)
    try:
        paths.atomic_write(where, (text + "\n").encode("utf-8"), prefix=".council-audit-", keep_mode=True,
                           refuse_link=True)
    except (OSError, paths.RecordError) as exc:
        return "Not saved: %s could not be written (%s)" % (where, exc)
    return "Saved: %s" % where
