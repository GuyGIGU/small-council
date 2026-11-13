"""The build loop's limits on starting a verifier (council-implement): one checker per batch under
`- checking: one per batch` (D18), and no third check of a task without a diagnosis or the user's go.
The agent gate asks them before a council verifier starts; `council seat … running` (bash until seat is
ported) asks them again. Each returns why the start must wait, or None."""
from __future__ import annotations

import re
from pathlib import Path

from council import clock
from council.commands import resolve
from council.records import config, events, seats, state

RECHECK = re.compile(r"verify-.+[b-z]")


def _stream(run: Path) -> list[list[str]] | None:
    """events.tsv's rows after its header, split on tabs; None when the run keeps no stream."""
    if not events.path(run).is_file():
        return None
    return events.table(run).rows


def _cell(row: list[str], n: int) -> str:
    return row[n] if len(row) > n else ""


def _number(text: str) -> float:
    """A cell as awk reads it in arithmetic: its leading number, else 0."""
    found = re.match(r"[ \t]*[-+]?([0-9]+\.?[0-9]*|\.[0-9]+)", text)
    return float(found.group(0)) if found else 0.0


def local_minute(at: str) -> str:
    """An event's UTC time (2026-10-08T12:05:09Z) as this machine's local minute (utc_local_min), the form
    a decision carries; '' when it doesn't read."""
    when = clock.utc_moment(at)
    try:
        return when.astimezone().strftime("%Y-%m-%d %H:%M") if when else ""
    except (OverflowError, OSError):
        return ""


def decisions_since(run: Path, since: str) -> int:
    """The user's decisions on record from a local minute on ('' counts them all) (decisions_since)."""
    stamped = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}: ")
    return sum(1 for entry in state.decisions(state.text(run)) if stamped.match(entry) and entry[:16] >= since)


def _building(run: Path, slug: str) -> list[list[str]] | None:
    """The stream of a build run asked to start a verifier seat; None when the rules don't apply."""
    if not slug.startswith("verify-") or len(slug) == len("verify-"):
        return None
    if resolve.field(run, "mode") != "council-implement":
        return None
    return _stream(run)


def check_round(run: Path, slug: str) -> str | None:
    """A third check of a task after two verdicts waits on a diagnose-… seat recorded after the second (only
    after exactly two), or on a decision of the user's since the last verdict (check_round_refusal)."""
    stream = _building(run, slug)
    if stream is None:
        return None
    base = slug[:-1] if RECHECK.fullmatch(slug) and _recorded(run, slug[:-1]) else slug
    verdicts, seq, at, seen = 0, "", "", {}
    for row in stream:
        subject = _cell(row, 4)
        if _cell(row, 3) == "seat.updated" and _of(subject, base):
            if _cell(row, 5) == "done" and seen.get(subject) != "done":
                verdicts, seq, at = verdicts + 1, _cell(row, 1), _cell(row, 2)
            seen[subject] = _cell(row, 5)
    if verdicts < 2:
        return None
    if verdicts == 2 and any(_cell(row, 3) == "seat.updated" and _cell(row, 4).startswith("diagnose-")
                             and _number(_cell(row, 1)) > _number(seq) and _cell(row, 5) not in ("queued", "skipped")
                             for row in stream):
        return None
    if decisions_since(run, local_minute(at)) != 0:
        return None
    task = base[len("verify-"):]
    if verdicts == 2:
        return ("cannot start %s — it would be the third check of task %s, after two verdicts. After a second failed "
                "verification the build loop allows one clean-context diagnosis, then one more attempt: "
                "plan diagnose-%s "
                "(for a verifier of several tasks, the number of the task that failed) and record it (council seat "
                "diagnose-%s running agent=<id>) before this check — or, if the task already used its diagnosis, stop "
                "and report to the user. Without that, only the user's go starts it: ask them, then record their words "
                "with council state decision=\"…\"" % (slug, task, task, task))
    return ("cannot start %s — task %s has %d verdicts, and after the second the build loop allows one diagnosis and "
            "one more attempt: stop and report to the user. Another check needs their go: ask them, then record their "
            "words with council state decision=\"…\"" % (slug, task, verdicts))


def _recorded(run: Path, slug: str) -> bool:
    """The seat has a state in seats.tsv (the helper's seat_field … 2)."""
    return any(row.get("slug") == slug and row.get("state") for row in seats.rows(run))


def _of(subject: str, base: str) -> bool:
    """The seat is the task's check or one of its re-checks (verify-6, verify-6b …)."""
    return subject == base or (len(subject) == len(base) + 1 and subject.startswith(base)
                               and subject[-1] in "bcdefghijklmnopqrstuvwxyz")


def batch_check(run: Path, slug: str, home: str) -> str | None:
    """Under `- checking: one per batch` a build gets one verifier; each further start needs a decision of
    the user's from the last start's minute on, and one per start after the first (batch_check_refusal).
    A start is a verifier seat recorded running, or done without running first; the same seat recorded
    running again while it runs is the same start."""
    stream = _building(run, slug)
    if stream is None or not config.checking(home).startswith("one per batch"):
        return None
    starts, now = [], {}
    for row in stream:
        subject, value = _cell(row, 4), _cell(row, 5)
        if _cell(row, 3) == "seat.updated" and subject.startswith("verify-"):
            before = now.get(subject)
            if (value == "running" and before != "running") or (value == "done" and before not in ("running", "done")):
                starts.append((subject, _cell(row, 2)))
            now[subject] = value
    counted = [(who, at) for who, at in starts if not (who == slug and now.get(who) == "running")]
    if not counted:
        return None
    since, first = local_minute(counted[-1][1]), local_minute(counted[0][1])
    if decisions_since(run, since) > 0 and decisions_since(run, first) >= len(counted):
        return None
    return ("cannot start %s — this build already started %d verifier(s) (%s), and under checking: one per batch a "
            "build gets one checker, at converge (references/build-proof.md, Checking). Another needs the user's go: "
            "ask them once, with its cost, then record their words with council state decision=\"…\" and dispatch. A "
            "verifier stopped at its turn limit is resumed with SendMessage, never started again. To check task by "
            "task, the config says - checking: per task." % (slug, len(counted), ", ".join(who for who, _ in counted)))
