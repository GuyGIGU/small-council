"""The build seat (D42): `task-<n>` in a council-implement run, where a builder agent edits the project code of task
n. One builder at a time: a build seat does not start while another runs. Its `done` needs `report-<n>.md`, unless
it stopped with a `NEEDS:` line. When one starts, the files changed since the run's last saved round are named.
`council seat` and the agent gate ask it, as they ask `rounds` for a verifier. A Solo build records no build seat,
so nothing here fires for it."""
from __future__ import annotations

import re
from pathlib import Path

from council import git
from council.commands import cli, resolve
from council.records import home as where
from council.records import patches, report_head, seat_rows, seats

SEAT = re.compile(r"task-([0-9]+)")
STARTED = ("queued", "running")


def task_of(run: Path, slug: str) -> int | None:
    """The task a build seat builds; None for any other seat, and in any run that isn't a build."""
    found = SEAT.fullmatch(slug)
    if not found or resolve.field(run, "mode") != "council-implement":
        return None
    return int(found.group(1))


def start_refusal(run: Path, slug: str) -> str | None:
    """Why build seat <slug> can't start now: another build seat is running (one builder at a time); None when it
    may, or when <slug> is no build seat."""
    if task_of(run, slug) is None:
        return None
    other = next((row.get("slug", "") for row in seats.rows(run) if row.get("state") == "running"
                  and row.get("slug") != slug and SEAT.fullmatch(row.get("slug", ""))), "")
    if not other:
        return None
    return ("cannot start %s — %s is running, and one builder at a time edits project code (D42). Wait for its line "
            "and record it (council seat %s done tokens=<n> tools=<n>, or done note=\"NEEDS: …\"); if its agent is "
            "gone, record it: council seat %s failed note=\"…\"" % (slug, other, other, other))


def missing_report(run: Path, slug: str, note: str) -> str:
    """The report a done build seat still lacks (report-<n>.md, empty or not there); '' when it is there, when the
    builder stopped with a NEEDS: line (it writes no round), or when <slug> is no build seat."""
    task = task_of(run, slug)
    if task is None or note.startswith("NEEDS:"):
        return ""
    file = report_head.report(run, task)
    return "" if file.is_file() and file.stat().st_size > 0 else file.as_posix()


def starts(run: Path, slug: str, state: str) -> bool:
    """The call starts a build seat: queued, or running when it was neither queued nor running."""
    return state in STARTED and task_of(run, slug) is not None \
        and seat_rows.cell(run, slug, "state") not in STARTED


def outside_round(run: Path, slug: str) -> list[str]:
    """The files on disk that differ from what the next round is diffed from (the run's last saved round, else the
    commit it opened on), .council/ left out, each named: an edit outside a round, or a file a gate left. Nothing
    when there is no difference, or when either side can't be read."""
    from council.commands import patch       # patch save's own start
    last, start = patch.since(run, patches.rounds(run))
    top = resolve.field(run, "code-root") or where.this_tree()
    now = git.files_tree(top) if start else ""
    if not now:
        return []
    code, data = git.run(top, "diff", "--name-only", "--no-renames", "--no-ext-diff", start, now, "--", ":(top)",
                         ":(top,exclude).council", names=True)
    files = [name for name in data.decode("utf-8", "surrogateescape").split("\n") if name] if code == 0 else []
    if not files:
        return []
    since = ("the last saved round (task %d round %d)" % (last.task, last.round) if last else
             "the commit the run opened on (%s)" % start[:12])
    return ["council: %d file(s) changed since %s, outside any round — an edit made outside a round, or a file a "
            "gate left. council patch save puts them in task %d's round:" % (len(files), since, task_of(run, slug))] \
        + ["council:   " + name for name in files]


def say_outside(run: Path, slug: str) -> None:
    """The notice of outside_round, on stderr as the seat's other notices are; never a refusal."""
    try:
        lines = outside_round(run, slug)
    except (OSError, ValueError):
        lines = []
    for line in lines:
        cli.warn(line)
