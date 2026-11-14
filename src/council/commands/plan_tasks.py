"""The plan check's task rules (references/run/run-plan.md, Plan tasks): once a council-plan run records its
deliverable, each task says what it serves (the request's words), who owns it (a row of the map's one-way-per-job
table, or New way: and why) and what it rests on; a task resting on an unchecked fact about something outside the
repo depends on a probe or research task first. `council run plan check` runs these with the run plan's own."""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from council.records import map_file, paths, request, state, tasks

SERVES_WHY = {"NO-QUOTE": "quotes nothing", "TOO-SHORT": "quotes under three words",
              "NOT-IN-THE-REQUEST": "quotes words the request never said"}
UNCHECKED = ("ASSUMED", "INFERRED")


class Verdict(NamedTuple):
    """The tasks' problems, and the lines said when the check is not quiet."""

    problems: list[str]
    notes: list[str]


def deliverable(run: Path) -> Path | None:
    """An open council-plan run's recorded deliverable; None for another mode, a closed run (its record is read
    as it was) or no deliverable yet. A relative path is the project's (the council home's parent)."""
    header = state.header(state.text(run), exact_keys=True)
    if header.get("mode") != "council-plan" or header.get("status") in ("complete", "abandoned"):
        return None
    name = header.get("deliverable", "")
    if not name:
        return None
    where = Path(name)
    return where if where.is_absolute() else Path(run).parent.parent.parent / where


def judge_run(run: Path) -> Verdict:
    """The task rules on a run's plan deliverable, the problems ending with their count line; nothing when there
    is no plan to judge."""
    plan = deliverable(run)
    if plan is None:
        return Verdict([], [])
    shown = plan.as_posix()
    content = paths.text_of(plan)
    if content:
        verdict = judge(tasks.read(content), request.words(run), map_file.read(Path(run).parent.parent), shown)
    else:
        verdict = Verdict(["ERROR: the recorded deliverable %s can't be read — write the plan there, or record "
                           "its path: council state deliverable=<path>" % shown], [])
    if verdict.problems:
        return Verdict(verdict.problems + ["tasks: %d error(s) · %s" % (len(verdict.problems), shown)], verdict.notes)
    return verdict


def judge(found: list[tasks.Task], words: str, ways: list[map_file.Way] | None, shown: str) -> Verdict:
    """Every task's own rows, then the probes the unchecked outside facts need."""
    problems: list[str] = []
    if not found:
        problems.append("ERROR: %s has no tasks under ## Task Sequence — write them as '### <n>. <title>' with "
                        "their table (references/run/run-plan.md, Plan tasks)" % shown)
    jobs = [way.job for way in ways or []]
    for task in found:
        problems += task_problems(task, words, jobs)
    problems += probe_problems(found)
    notes = []
    if not jobs:
        notes.append("tasks: owner check skipped — map.md has no %s table, or it has no rows yet"
                     % map_file.TABLE.lstrip("# "))
    if not problems and found:
        new = [str(t.number) for t in found if tasks.kind(t.rows.get("owner")) == "new"]
        notes.append("tasks: %d checked against the request · %s%s" % (
            len(found), shown, " · New way in task %s: put it to the user as a ruling" % ", ".join(new) if new else ""))
    return Verdict(problems, notes)


def task_problems(task: tasks.Task, words: str, jobs: list[str]) -> list[str]:
    """A task's Serves, Owner and Rests on rows."""
    say = "ERROR line %d: task %d" % (task.line, task.number)
    out = []
    serves = task.rows.get("serves")
    wrong = SERVES_WHY.get(request.verdict(serves, words)) if serves is not None else None
    if serves is None:
        out.append("%s has no Serves row — quote the part of the request it serves, word for word (a support "
                   "task quotes its parent's)" % say)
    elif wrong:
        out.append("%s's Serves %s — quote the request (ask.md, In your words) word for word, or ask the user "
                   "whether the task is in scope" % (say, wrong))
    owner = task.rows.get("owner")
    what = tasks.kind(owner)
    if owner is None or not owner.strip():
        out.append("%s has no Owner row — name the module and the way it extends, or New way: and why" % say)
    elif what == "new" and not owner.split(":", 1)[1].strip():
        out.append("%s says New way: but not why — say why no existing way fits" % say)
    elif what == "way" and jobs and not names_a_job(owner, jobs):
        out.append("%s's Owner names no row of map.md's One way per job table — name the job it extends (%s), "
                   "or write New way: and why, for the user's ruling" % (say, "; ".join(jobs)))
    facts = tasks.facts(task.rows.get("rests on"))
    if facts is None:
        out.append("%s has no Rests on row — list the facts it assumes, each with its evidence state, or —" % say)
    else:
        for fact in facts:
            if not fact.state:
                out.append("%s rests on '%s' with no evidence state — end it (OBSERVED), (ASSUMED, outside) …"
                           % (say, fact.text))
    return out


def names_a_job(owner: str, jobs: list[str]) -> bool:
    """The Owner cell holds one of the table's jobs, in any case and spacing."""
    def flat(text: str) -> str:
        return " ".join(text.replace("*", "").replace("`", "").lower().split())
    return any(flat(job) in flat(owner) for job in jobs)


def probe_problems(found: list[tasks.Task]) -> list[str]:
    """A task resting on an ASSUMED or INFERRED fact about something outside the repo depends, directly or through
    other tasks, on a probe or research task. A probe or research task needs none itself."""
    by_number = {task.number: task for task in found}

    def reaches_probe(number: int, seen: set) -> bool:
        if number in seen or number not in by_number:
            return False
        seen.add(number)
        task = by_number[number]
        if tasks.kind(task.rows.get("owner")) in ("probe", "research"):
            return True
        return any(reaches_probe(n, seen) for n in tasks.depends(task.rows.get("depends on")))
    out = []
    for task in found:
        if tasks.kind(task.rows.get("owner")) in ("probe", "research"):
            continue
        unchecked = [f for f in tasks.facts(task.rows.get("rests on")) or [] if f.outside and f.state in UNCHECKED]
        if unchecked and not any(reaches_probe(n, {task.number}) for n in tasks.depends(task.rows.get("depends on"))):
            out.append("ERROR line %d: task %d rests on '%s' (%s, outside) with no probe or research task before it "
                       "— add one (Owner: Probe: <the question>) and put it in Depends on"
                       % (task.line, task.number, unchecked[0].text, unchecked[0].state))
    return out
