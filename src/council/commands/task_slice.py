"""A build task's slice: the plan the run records as input=, the task in it, and the paths its Owner and Touches
cells and the map row its Owner names give. council patch save holds a round's files to it; council context build
and council tree read the same plan, and refuse the same way when there is none."""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from council.commands import cli, patch_checks, resolve
from council.records import home as where
from council.records import map_file, paths, tasks


class Slice(NamedTuple):
    """What the plan says of one task: the input= it came from, the task (None when the plan has no such task),
    the map's one-way-per-job rows (None when the map has no table), the rows its Owner names, and the paths."""

    named: str
    task: tasks.Task | None
    ways: list | None
    owned: list
    paths: list


def plan_of(run: Path) -> tuple[str, Path | None]:
    """The plan the build records as input= (as written) and where it is: an absolute path as written, else the
    project's; ('', None) when the run records none."""
    named = resolve.field(run, "input")
    if not named:
        return "", None
    return named, Path(where.native(named)) if where.absolute(named) else Path(run).parent.parent.parent / named


def of(run: Path, number: int) -> Slice:
    """Task <number>'s slice, as council patch save judges a round against it; nothing is read when the run
    records no plan."""
    named, plan = plan_of(run)
    return cut(run, named, paths.text_of(plan) if plan else "", number)


def cut(run: Path, named: str, content: str, number: int) -> Slice:
    """Task <number>'s slice from the plan's text: its Owner and Touches, and the map row its Owner names."""
    entry = next((t for t in tasks.read(content) if t.number == number), None) if named else None
    if entry is None:
        return Slice(named, None, None, [], [])
    owner = entry.rows.get("owner", "")
    cells = [owner, entry.rows.get("touches", "")]
    from council.commands import plan_tasks     # the plan check's own match of an Owner to a row
    ways = map_file.read(Path(run).parent.parent)
    owned = [way for way in ways or [] if plan_tasks.names_a_job(owner, [way.job])]
    for way in owned:
        cells += [way.owner, way.anchor]
    return Slice(named, entry, ways, owned, patch_checks.slice_paths(cells))


def plan(run: Path, label: str) -> tuple[str, str]:
    """The plan's input= and its text, for a command that can't go on without it; a refusal naming the next step
    when the run records none or it can't be read."""
    named, found = plan_of(run)
    if found is None:
        raise cli.Refusal("%s reads the build's plan, and this run records none — name it: council state "
                          "input=<plan>" % label)
    content = paths.text_of(found)
    if not content.strip():
        raise cli.Refusal("the plan %s (the run's input=) can't be read: it is missing, empty, a link or over %s — "
                          "fix it, or name the right one: council state input=<plan>"
                          % (named, paths.megabytes(paths.MAX_FILE)))
    return named, content
