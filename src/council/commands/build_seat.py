"""The build seat (D42): `task-<n>` in a council-implement run, where a builder agent edits the project code of task
n. One builder at a time: a build seat does not start while another is queued or runs, nor while a `NEEDS: fix`
stop stands on its task or a task it depends on. Its `done` needs `report-<n>.md`, unless it stopped with a `NEEDS:`
line. When one starts, the files changed since the run's last saved round are named. It also holds the one reader
of a task's stop (stop_of), which council tree asks too. `council seat` and the agent gate ask it, as they ask
`rounds` for a verifier. A Solo build records no build seat, so nothing here fires for it."""
from __future__ import annotations

import re
from pathlib import Path

from council import git
from council.commands import cli, resolve, task_slice
from council.records import cells, events, gates, patches, paths, report_head, seat_rows, seats, tasks
from council.records import home as where

SEAT = re.compile(r"task-([0-9]+)")
STARTED = ("queued", "running")
STANDS, RELEASED, RESOLVED = "stands", "released", "resolved"
FIX = re.compile(r"NEEDS:\s*fix\s+(\S+)")


def task_of(run: Path, slug: str) -> int | None:
    """The task a build seat builds; None for any other seat, and in any run that isn't a build."""
    found = SEAT.fullmatch(slug)
    if not found or resolve.field(run, "mode") != "council-implement":
        return None
    return int(found.group(1))


def start_refusal(run: Path, slug: str) -> str | None:
    """Why build seat <slug> can't start now: another build seat is queued or running (one builder at a time; a seat
    is taken from its queued, so a second dispatch sent before the first is recorded running is refused), or a
    NEEDS: fix stop stands on its task or on a task it depends on; None when it may, or when <slug> is no build
    seat."""
    task = task_of(run, slug)
    if task is None:
        return None
    other, state = next(((row.get("slug", ""), row.get("state", "")) for row in seats.rows(run)
                         if row.get("state") in STARTED and row.get("slug") != slug
                         and SEAT.fullmatch(row.get("slug", ""))), ("", ""))
    if other:
        return ("cannot start %s — %s is %s, and one builder at a time edits project code (D42). Wait for its "
                "line and record it (council seat %s done tokens=<n> tools=<n>, or done note=\"NEEDS: …\"); if its "
                "agent is gone, record it: council seat %s failed note=\"…\"" % (slug, other, state, other, other))
    return _fix_refusal(run, slug, task)


def dispatch_refusal(run: Path, slug: str) -> str | None:
    """Why a council-builder for build seat <slug> can't go out: start_refusal, or its seat isn't on record queued.
    The rules above read the seat records, so a builder sent before its seat is queued would be held to an empty
    record; and the dispatch that goes out takes the seat (council seat's taken: queued to running), so a seat
    already running has its builder. None when it may go, or when <slug> is no build seat."""
    why = start_refusal(run, slug)
    state = seat_rows.cell(run, slug, "state")
    if why or task_of(run, slug) is None or state == "queued":
        return why
    if state == "running":
        agent = seat_rows.cell(run, slug, "agent")
        return ("cannot start a builder for %s — a builder went out for it already (its seat is running since %s, %s),"
                " and one builder at a time edits project code (D42). Wait for its line and record it (council seat %s"
                " done tokens=<n> tools=<n>). If that dispatch started no agent, record it: council seat %s failed "
                "note=\"dispatch failed\", then council seat %s queued, and dispatch again"
                % (slug, seat_rows.cell(run, slug, "updated") or "?",
                   "agent " + agent if agent else "no agent on record yet", slug, slug, slug))
    return ("cannot start a builder for %s — its seat isn't queued, so the helper can't hold it to one builder at a "
            "time (D42). Queue it first: council seat %s queued, then dispatch again" % (slug, slug))


def _fix_refusal(run: Path, slug: str, task: int) -> str | None:
    """A NEEDS: fix stop that stands on task <task> or on a task it depends on, all the way down."""
    under = depends_on(run, task)
    for row in seats.rows(run):
        number, note = tasks.number(row.get("slug", "")), row.get("note", "")
        if number not in under or row.get("state") != "done" or not FIX.match(note):
            continue
        if stop_of(run, row.get("slug", "")) != STANDS:
            continue
        where_ = FIX.match(note).group(1)
        how = "this is that task" if number == task else "task %d depends on it" % task
        return ("cannot start %s — task %d stopped with NEEDS: fix at %s (seat %s), and %s: the code under it is "
                "wrong. Tell the user what is wrong and what is stopped, record their decision in their words with "
                "council state decision=\"…\", and build the fix as its own task above the stopped one"
                % (slug, number, where_, row.get("slug", ""), how))
    return None


def depends_on(run: Path, task: int) -> set:
    """Task <task> and every task it depends on, through the input= plan's Depends on rows at every level; the task
    alone when the run names no plan, the plan can't be read or doesn't hold the task."""
    _, plan = task_slice.plan_of(run)
    found = {one.number: tasks.depends(one.rows.get("depends on")) for one in
             (tasks.read(paths.text_of(plan)) if plan else [])}
    seen, todo = {task}, list(found.get(task, []))
    while todo:
        number = todo.pop()
        if number not in seen:
            seen.add(number)
            todo += found.get(number, [])
    return seen


def verdicts(run: Path) -> dict[str, str]:
    """Each saved gate's last verdict: pass (exit 0) or fail."""
    return {gate["name"]: "pass" if gate["exit"] == 0 else "fail" for gate in gates.results(run)}


def resolved(run: Path, slug: str, task: int, proofs: dict) -> bool:
    """Seat <slug>'s stop on task <task> is resolved once the task's own after-<n> gate passed after the stop: a
    gate.finished `passed` event for after-<n> later in the stream (by seq) than the stop's own done. With no stream,
    or no stop in it, the gate's last verdict (proofs, as verdicts reads them) answers: what can't be read never
    refuses."""
    rows, at = _stop(run, slug)
    return _resolved(rows, at, task, proofs)


def resolved_tasks(run: Path, proofs: dict) -> set:
    """The tasks whose seats' NEEDS: stops are all resolved (council tree's `was stopped:`)."""
    found: dict = {}
    for row in seats.rows(run):
        slug, number = row.get("slug", ""), tasks.number(row.get("slug", ""))
        if number is not None and row.get("note", "").startswith("NEEDS:"):
            found[number] = found.get(number, True) and resolved(run, slug, number, proofs)
    return {number for number, done in found.items() if done}


def _resolved(rows: list[list[str]], at: int, task: int, proofs: dict) -> bool:
    gate = "after-%d" % task
    if at < 0:
        return proofs.get(gate) == "pass"
    stop = cells.leading(rows[at][1])
    return any(row[3] == "gate.finished" and row[4] == gate and row[5] == "passed" and cells.leading(row[1]) > stop
               for row in rows)


def stop_of(run: Path, slug: str) -> str:
    """The one reader of a stop: '' when seat <slug>'s row carries no NEEDS: note; else RESOLVED when the task its
    slug names (task-3, T3) has its after-<n> gate passed after the stop (resolved); RELEASED when a decision of the
    user's, the whole run's or that task's own, is on record from the stop's minute on (rounds.decisions_since, >=:
    a decision in that same minute counts); else STANDS. The stop's moment is the seat's first done in the event
    stream after its last start; a run with no stream, or no such done, has no moment, and the stop reads RELEASED
    unless the after gate's last verdict is a pass: what the helper can't read never refuses."""
    if not seat_rows.cell(run, slug, "note").startswith("NEEDS:"):
        return ""
    rows, at = _stop(run, slug)
    number = tasks.number(slug)
    if number is not None and _resolved(rows, at, number, verdicts(run) if at < 0 else {}):
        return RESOLVED
    from council.commands import rounds      # datetime, only once a stop is read (D34)
    when = rows[at][2] if at >= 0 else ""
    if not when or rounds.decisions_since(run, rounds.local_minute(when), number) > 0:
        return RELEASED
    return STANDS


def _stop(run: Path, slug: str) -> tuple[list[list[str]], int]:
    """The event stream's rows (each padded to seven cells) and the index of the seat's first done after its last
    start (queued or running); -1 when there is no stream or no such done."""
    if not events.path(run).is_file():
        return [], -1
    rows = [row + [""] * 7 for row in events.table(run).rows]
    at = -1
    for n, row in enumerate(rows):
        if row[3] != "seat.updated" or row[4] != slug:
            continue
        if row[5] in STARTED:
            at = -1
        elif row[5] == "done" and at < 0:
            at = n
    return rows, at


def missing_report(run: Path, slug: str, note: str) -> str:
    """The report a done build seat still lacks (report-<n>.md, empty or not there); '' when it is there, when the
    builder stopped with a NEEDS: line (it writes no round) — given now, or kept on a seat already done with it, so a
    late usage report on the stop needs no report — or when <slug> is no build seat."""
    task = task_of(run, slug)
    kept = seat_rows.cell(run, slug, "note") if seat_rows.cell(run, slug, "state") == "done" else ""
    if task is None or (note or kept).startswith("NEEDS:"):
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
