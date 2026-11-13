"""council cap check: the agent gate's decision (hooks/agent-gate.sh). Silent, exit 0, while agents may
start; the reason on stdout and exit 2 while a run this session may be driving is stopped. A fault of its
own never stops an agent: the hook lets through anything that is not exit 2 with "Small Council:" on stdout.

Only in-progress runs count: with a session id, the runs that session drives on any working tree, and
this tree's runs that recorded none; without one, every in-progress run on this tree. A run opened before
plans and agent limits (no plan-schema) is never stopped. Given the tool about to start, a pass also
counts one agent start for the run this session drives, when it drives exactly one — under that run's
lock, so agents started together cannot all take its last place. With type=, seat=, run= and file=, a
Small Council agent is first refused while the council home or the run is not writable from this session
(gate_writable), then held to the record (dispatch_refusal); with hunt=, a build's verifier sent past its
Done-when is refused; with workflow=verifier, a Workflow that starts council verifiers is held to the
hunt words and, as one more verifier, to the one-checker rule.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import NamedTuple

from council.commands import cap, cli, gate_writable, resolve
from council.records import home as where
from council.records import plan, runs, seats, usage

SLUG = re.compile(r"[A-Za-z0-9._-]+")
KINDS = {"small-council:council-worker": "council-worker", "small-council:council-verifier": "council-verifier"}


class Call(NamedTuple):
    """The agent about to start, as the hook read it from the call."""

    tool: str
    agent_type: str
    seat: str
    run: str
    file: str
    hunt: str
    workflow: bool


def read_call(words: list[str]) -> Call:
    """The tool and the details after it; a later detail of a kind wins, as the helper's loop reads them."""
    got = {"type": "", "seat": "", "run": "", "file": "", "hunt": ""}
    workflow = False
    for word in words[1:]:
        key, equals, value = word.partition("=")
        if equals and key in got:
            got[key] = value
        elif word == "workflow=verifier":
            workflow = True
    return Call(words[0] if words else "", got["type"], got["seat"], got["run"], got["file"], got["hunt"], workflow)


class Where(NamedTuple):
    """The council home, this working tree and this session."""

    home: str
    tree: str
    session: str


def check(session: str, words: list[str]) -> int:
    """The gate's decision for one agent start; exit 2 with the reason on stdout when it must wait."""
    call = read_call(words)
    home = where.council_home()
    has_runs = os.path.isdir(home + "/runs")
    here = Where(home, where.this_tree() if has_runs or call.agent_type else "", session)
    open_runs = cap.open_here(home, here.tree, session) if (call.hunt or call.workflow) and has_runs else []
    refusal = gate_writable.refusal(KINDS.get(call.agent_type), home, call.run) \
        or (hunting(call, here, open_runs) if has_runs else None) \
        or (dispatch_refusal(call, here) if call.agent_type else None) \
        or (workflow_refusal(open_runs, home) if call.workflow else None)
    if refusal:
        cli.say(refusal)
        return 2
    stopped = stops(call.tool, here) if has_runs else []
    if not stopped:
        return 0
    if len(stopped) == 1:
        name = stopped[0][0]
        cli.say("Small Council: %s. No new agents until the user says go. Tell them what it has used, and ask whether "
                "to continue and for how many more agent runs; every agent a Workflow starts counts. On their go: "
                "`council cap allow <n> --run %s --user-said \"<their words>\"`. If the run is finished: `council run "
                "close --run %s`. Alert the owner once: send what `council status --line --run %s` prints with a "
                "PushNotification tool (it may be a deferred tool: search the tools for it first)."
                % (stopped[0][1], name, name, name))
    else:
        said = ". ".join(words_of for _, words_of in stopped)
        cli.say("Small Council: %s. No new agents until the user says go. Tell them what each run has used, and ask "
                "whether to continue and for how many more agent runs; every agent a Workflow starts counts. On their "
                "go: `council cap allow <n> --run <folder> --user-said \"<their words>\"` for each run. If a run is "
                "finished: `council run close --run <folder>`. Alert the owner once: send what `council status --line "
                "--run <folder>` prints with a PushNotification tool (it may be a deferred tool: search the tools for "
                "it first)." % said)
    return 2


def hunting(call: Call, here: Where, open_runs: list[str]) -> str | None:
    """A build's verifier whose brief sends it hunting past the Done-when. Only a build's verifier has a
    Done-when to hunt past: the run the brief names, else the in-progress runs this session may drive."""
    if not call.hunt or not (call.agent_type == "small-council:council-verifier" or call.workflow):
        return None
    targets = open_runs
    if SLUG.fullmatch(call.run) and not call.run.startswith(".") and resolve.is_run(here.home + "/runs/" + call.run):
        targets = [here.home + "/runs/" + call.run]
    if not any(resolve.field(Path(run), "mode") == "council-implement" for run in targets):
        return None
    return ("Small Council: this council-verifier's brief sends it hunting past the Done-when (\"%s\"). A verifier "
            "tries hard to show each Done-when is not met, and anything it notices beyond one is a line under "
            "## Noticed, never a verdict or a task (references/build-proof.md, Checking): a verifier told to name any "
            "route, however narrow, found a narrower gap every round. Take those words out of the brief and dispatch "
            "again." % call.hunt)


def workflow_refusal(open_runs: list[str], home: str) -> str | None:
    """A Workflow that starts council verifiers names no seat the hook can read: under one per batch it is
    held to every in-progress build this session may be driving, as one more verifier."""
    from council.commands import rounds          # the build loop's rules: only a verifier's start reads them
    for run in open_runs:
        why = rounds.batch_check(Path(run), "verify-workflow", home)
        if why:
            lead = "cannot start verify-workflow — "
            rest = why[len(lead):] if why.startswith(lead) else why
            return "Small Council: this Workflow starts council verifiers, and " + rest
    return None


def stops(tool: str, here: Where) -> list[tuple[str, str]]:
    """Each stopped run's name and words. The run a start counts for is judged under its lock, last."""
    kept, mine = [], []
    for run in runs.listing(here.home, 1000000, "open"):
        if run.status != "in-progress":
            continue
        session = run.session or "-"
        if here.session and session == here.session:
            own = True
        elif (not here.session or session == "-") and run.code_root in (here.tree, "", "-"):
            own = False
        else:
            continue
        if resolve.field(Path(run.folder), "plan-schema"):
            kept.append(run.folder)
            if own:
                mine.append(run.folder)
    counted = mine[0] if tool and len(mine) == 1 else ""
    stopped = []
    for run in kept:
        if run != counted:
            stand = usage.standing(Path(run), here.home)
            if stand.stopped:
                stopped.append((run.split("/")[-1], stand))
    if counted:
        stand = count_start(Path(counted), tool, here, bool(stopped))
        if stand.stopped:
            stopped.append((counted.split("/")[-1], stand))
    said = [cap.words(name, stand) for name, stand in stopped]
    return [(name, line if n == 0 else "R" + line[1:]) for n, ((name, _), line) in enumerate(zip(stopped, said))]


def count_start(run: Path, tool: str, here: Where, refused: bool) -> usage.Standing:
    """The run's standing before this start, which is counted in agent-starts.tsv unless the run is
    stopped or another run refuses the start; without the lock it is judged, not counted."""
    if refused:
        return usage.standing(run, here.home)
    from council.records import locks              # only a start that may be counted takes a lock
    file = seats.path(run, seats.STARTS)
    lock = Path(str(file) + ".lock")
    if not locks.acquire(lock, 50):
        return usage.standing(run, here.home)
    try:
        stand = usage.standing(run, here.home)
        if not stand.stopped:
            _append_start(file, stand.used - seats.workflow_extra(run), tool, here.session)
    finally:
        locks.release(lock)
    return stand


def _append_start(file: Path, seed: int, tool: str, session: str) -> None:
    """One start row; a new file first takes the agents recorded before any start was counted."""
    stamp = cap.stamp()
    if not _filled(file):
        _write(file, "wb", "at\ttool\tsession\n")
        if seed > 0:
            _write(file, "ab", "%s\tbefore:%d\t-\n" % (stamp, seed))
    if not _filled(file):
        _write(file, "wb", "at\ttool\tsession\n")
    if not _ends_line(file):
        _write(file, "ab", "\n")                              # never join a torn line
    _write(file, "ab", "%s\t%s\t%s\n" % (stamp, tool, session.replace("\t", " ")))


def _filled(file: Path) -> bool:
    try:
        return file.stat().st_size > 0
    except OSError:
        return False


def _ends_line(file: Path) -> bool:
    try:
        with open(str(file), "rb") as handle:
            handle.seek(-1, os.SEEK_END)
            return handle.read(1) == b"\n"
    except OSError:
        return True                                           # empty or unreadable: nothing to end


def _write(file: Path, mode: str, line: str) -> None:
    try:
        with open(str(file), mode) as handle:
            handle.write(line.encode("utf-8", "surrogateescape"))
    except OSError:
        pass


class Planned(NamedTuple):
    """How many of the runs select a seat, the last of them, and whether one predates run plans."""

    count: int
    run: str
    legacy: bool


def seat_runs(candidates: list[str], slug: str, kind: str) -> Planned:
    """How many runs select the seat (dispatch_seat_runs). For a verifier, a re-check's verify-6b or a
    Workflow part's verify-1-a also counts as its base seat."""
    also = ""
    if kind == "council-verifier":
        if re.fullmatch(r"verify-.+-[a-z]", slug):
            also = slug[:-2]
        elif re.fullmatch(r"verify-.+[b-z]", slug):
            also = slug[:-1]
    count, last, legacy = 0, "", False
    for run in candidates:
        if not resolve.field(Path(run), "plan-schema"):
            legacy = True
            continue
        if _selected(Path(run), slug) or (also and _selected(Path(run), also)):
            count, last = count + 1, run
    return Planned(count, last, legacy)


def _selected(run: Path, slug: str) -> bool:
    """The run's plan marks the seat selected (run_plan_has_selected)."""
    return any(row.get("kind") == "seat" and row.get("id") == slug and row.get("field") == "disposition"
               and row.get("value") == "selected" for row in plan.rows(run))


def _slug(value: str) -> str:
    return value if SLUG.fullmatch(value) else ""


def dispatch_refusal(call: Call, here: Where) -> str | None:
    """A Small Council agent goes out only for an open run, and only for a seat that run's plan selects
    (dispatch_refusal). A worker always works for a run; a verifier naming no run may be test-architect's
    own check outside any run. A paused or closed run named is refused only while no run is open for it:
    a re-review or a post-game cites an earlier run's files. Nothing is judged on what the hook couldn't
    read; a display name ("Security") is never refused as a seat."""
    kind = KINDS.get(call.agent_type)
    if kind is None or not os.path.isdir(here.home):
        return None
    named = _slug(call.run) if not call.run.startswith(".") else ""
    seat, file = _slug(call.seat), _slug(call.file)
    status, candidates = "", []
    if named and resolve.is_run(here.home + "/runs/" + named):
        status = resolve.field(Path(here.home + "/runs/" + named), "status").split(" ")[0] or "no status"
    if status == "in-progress":
        candidates = [here.home + "/runs/" + named]
    else:
        if not status and kind != "council-worker":
            return None
        candidates = cap.open_here(here.home, here.tree, here.session)
        if not candidates:
            return _no_run(kind, named, status, here.session)
    if not seat and not file:
        return None
    pick, found = "", Planned(0, "", False)
    if seat:
        found = seat_runs(candidates, seat, kind)
        pick = seat if found.count else ""
    if not pick and file and file != seat:
        found = seat_runs(candidates, file, kind)
        pick = file if found.count else ""
    if not pick:
        return None if found.legacy else _unplanned(kind, seat, file, candidates)
    if found.count != 1:
        return None                                    # which run it is for is unknown: the seat record judges
    from council.commands import rounds
    why = rounds.batch_check(Path(found.run), pick, here.home) or rounds.check_round(Path(found.run), pick)
    return "Small Council: " + why if why else None


def _no_run(kind: str, named: str, status: str, session: str) -> str | None:
    """No run is open for this agent: the run it names is paused or closed, or there is none."""
    if status == "paused":
        return ("Small Council: this %s is for run %s, which is paused — no agent starts for it while it is. If the "
                "user wants it carried on: council run resume --run %s, then dispatch again." % (kind, named, named))
    if status:
        return ("Small Council: this %s is for run %s, which is closed (%s) — its agents are done. For more work, open "
                "a new run (council run open <mode>), plan the seat there, then dispatch." % (kind, named, status))
    if not session:
        return None                                    # no session: its runs on other trees can't be seen
    return ("Small Council: no council run is open on this working tree or for this session, so a council-worker has "
            "no run to work for. Open the run first (council run open <mode>), or carry on with a paused one if the "
            "user wants it (council run resume --run <folder>); plan the seat, then dispatch. For work outside the "
            "council, use another agent type.")


def _unplanned(kind: str, seat: str, file: str, candidates: list[str]) -> str | None:
    """The seat has no selected row in any candidate run's plan: refused only when it reads as a slug, and the
    Seat: line and the file written agree ("Seat: Perf" writing seats/perf.md)."""
    pick = file or seat
    if seat and file and seat.lower() != file:
        return None
    if not re.fullmatch(r"[a-z0-9._-]+", pick):
        return None                                    # a display name, not a slug
    if len(candidates) > 1:
        place, run = "the open runs here (%s)" % resolve.names(candidates), "<folder>"
    else:
        place = run = candidates[0].split("/")[-1]
    return ("Small Council: seat %s has no selected row in the run plan of %s, so this %s would work off the record. "
            "Plan it first — its disposition (selected), role, context level and tool-call budget in run-plan.tsv — "
            "then council run plan check --run %s, then dispatch, and record it at once: council seat %s running "
            "agent=<id>." % (pick, place, kind, run, pick))
