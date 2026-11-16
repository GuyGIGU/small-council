"""council tree: the build's task tree, printed from its files and nothing else (docs/design/task-tree.md, section 1).
The request in the user's words (ask.md), then the plan's tasks grouped by the Serves quote each gives, in plan
order, each with the tasks it depends on, what it rests on, its proof gates, its saved rounds, the Converge table's
result and a seat's NEEDS: return (a stop build_seat reads as resolved shows as was stopped). After a
compaction the Chair resumes from this view, not from memory."""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from council.commands import build_seat, cli, resolve, task_slice
from council.records import converge, patches, paths, request, seats, tasks


class Records(NamedTuple):
    """What the run's files say of each task: its proof gates' results (by gate name), its saved rounds, the
    Converge table's result and its seats' NEEDS: returns."""

    proofs: dict
    rounds: dict
    converge: dict
    needs: dict


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "tree")
    cli.no_words("tree", words)
    run = resolve.run_folder(args)
    named, content = task_slice.plan(run, "tree")
    cli.say_all(lines(run, named, tasks.read(content)))
    return 0


def lines(run: Path, named: str, found: list[tasks.Task]) -> list[str]:
    out = ["tree: %s · run %s · %d task(s)" % (named, Path(run).name, len(found)), "",
           "Request (%s, in the user's words):" % request.ASK] + _request(run)
    needs, unclaimed = seat_needs(run, {task.number for task in found})
    rounds: dict[int, int] = {}
    for one in patches.rounds(run):
        rounds[one.task] = rounds.get(one.task, 0) + 1
    records = Records(build_seat.verdicts(run), rounds, _converge(run), needs)
    groups: dict[str, list[tasks.Task]] = {}
    for task in found:
        groups.setdefault(task.rows.get("serves", "(no Serves row)"), []).append(task)
    for serves, members in groups.items():
        out += ["", "Serves: %s" % serves]
        out += ["  " + _line(task, records) for task in members]
    if not found:
        out += ["", "The plan's ## Task Sequence lists no task."]
    if unclaimed:
        out += ["", "NEEDS: from seats whose slug names no task of the plan:"]
        out += ["  %s: %s" % pair for pair in unclaimed]
    return out


def _request(run: Path) -> list[str]:
    data = paths.contents(Path(run) / request.ASK)
    if data is None:
        return ["  (no %s in the run yet — the Chair writes the user's words there)" % request.ASK]
    words = request.ask_words(data).decode("utf-8", "surrogateescape").splitlines()
    while words and not words[-1].strip():
        words.pop()
    return ["  " + line for line in words] or ["  (nothing under ## In your words)"]


def _line(task: tasks.Task, records: Records) -> str:
    facts = tasks.facts(task.rows.get("rests on")) or []
    names = ["%s-%d" % (side, task.number) for side in ("before", "after")]
    proof = ", ".join("%s %s" % (name, records.proofs[name]) for name in names if name in records.proofs)
    depends = ", ".join("T%d" % number for number in tasks.depends(task.rows.get("depends on")))
    said = "T%d %s%s · rests on %d fact%s · proof: %s · rounds: %d · converge: %s" % (
        task.number, task.title, " · depends on " + depends if depends else "", len(facts),
        "" if len(facts) == 1 else "s", proof or "none", records.rounds.get(task.number, 0),
        records.converge.get(task.number, "none yet"))
    stopped = "was stopped: " if build_seat.resolved(records.proofs, task.number) else ""
    return said + "".join(" · " + stopped + note for note in records.needs.get(task.number, []))


def _converge(run: Path) -> dict[int, str]:
    """The Converge table's result for each task its Task cell names."""
    table = converge.read(run, resolve.field(run, "deliverable"))
    words = {"met": "met", "partly": "partly met", "not_met": "not met", "blocked": "blocked"}
    found = {}
    for row in table.get("rows", []):
        number = tasks.number(row["task"])
        if number is not None:
            found[number] = words.get(row["result"], "other")
    return found


def seat_needs(run: Path, numbers: set) -> tuple[dict[int, list[str]], list[tuple[str, str]]]:
    """The seats' NEEDS: returns: on the task a seat's slug names (task-3, T3), else listed apart. council context
    build shows a task's own as Stopped earlier."""
    claimed: dict[int, list[str]] = {}
    unclaimed = []
    for row in seats.rows(run):
        note = row.get("note", "")
        if not note.startswith("NEEDS:"):
            continue
        number = tasks.number(row.get("slug", ""))
        if number in numbers:
            claimed.setdefault(number, []).append(note)
        else:
            unclaimed.append((row.get("slug", ""), note))
    return claimed, unclaimed
