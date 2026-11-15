"""The stages of a council run, in order: each one's rank and the next step `council state phase=` records
(bin/council's stage_name_ok, stage_rank, stage_next, required_stages and stages_skipped)."""
from __future__ import annotations

import re
from pathlib import Path

from council.records import plan, state

COUNCIL_NEXT_AT_OPEN = "size the run and ask for the go-ahead"   # a new run's next: — Convene's own step
STAGES = {  # name: (rank, next step); a build stands where council-implement's build loop does (3-7)
    "convene": (1, COUNCIL_NEXT_AT_OPEN),
    "prepare": (2, "Prepare: the change index, the checks and earlier findings (doctrine 02-prepare.md)"),
    "assign": (3, "Assign: fill the run plan, then council run plan check (doctrine 03-assign.md)"),
    "brief": (4, "Brief: write brief.md with the memory in scope (doctrine 04-brief.md)"),
    "work": (5, "Work: start the seats and record each one (doctrine 05-work.md)"),
    "build": (5, ""),                                     # task 1, set where the build loop's gates read it
    "collect": (6, "Collect: council collect until it is clean (doctrine 06-collect.md)"),
    "judge": (7, "Judge: weigh the findings into synthesis.md (doctrine 07-judge.md)"),
    "challenge": (8, "Challenge: verify what is kept (doctrine 08-challenge.md)"),
    "deliver": (9, "Deliver: write the deliverable and file the request (doctrine 09-deliver.md)"),
    "learn": (10, "Learn: memory proposals, then close the run (doctrine 10-learn.md)"),
}
SHORT = "convene prepare judge challenge deliver learn"
REQUIRED = {"council-implement": "convene prepare build challenge deliver learn", "council-postgame": SHORT}


def name_ok(stage: str, mode: str) -> bool:
    """A stage council state accepts; a council-init or test-architect run names its own, any lower-case word."""
    return stage in STAGES or (mode in ("council-init", "test-architect") and re.fullmatch("[a-z][a-z-]*", stage)
                               is not None)


def rank(stage: str) -> int:
    return STAGES.get(stage, (0, ""))[0]


def next_text(stage: str) -> str:
    return STAGES.get(stage, (0, ""))[1]


def required(run: Path) -> list[str]:
    """The stages a run must enter, in order: a review, plan or research run whose plan selects a worker seat
    (and is not Solo) enters all ten."""
    mode = state.field(state.text(run), "mode")
    if mode not in ("council-review", "council-plan", "council-research"):
        return REQUIRED.get(mode, "").split()
    rows = []                                             # (kind, id, field, value): the plan's rows, trimmed
    for line in plan.text(run).split("\n"):
        c = (line[:-1] if line.endswith("\r") else line).split("\t") + ["", "", "", ""]
        rows.append((c[0], c[1], c[2], c[3].strip(" ")))
    size = [key[3] for key in rows if key[:3] == ("run", "run", "size")]
    workers = {key[1] for key in rows if key[0] == "seat" and key[2:] == ("role", "worker")}
    picked = {key[1] for key in rows if key[0] == "seat" and key[2:] == ("disposition", "selected")}
    if size[-1:] != ["solo"] and workers & picked:
        return [stage for stage in STAGES if stage != "build"]
    return SHORT.split()


def skipped(run: Path, frm: str, to: str) -> list[str]:
    """The stages this run must enter that a move from frm to to passes over; none for a step back or a mode's
    own phase."""
    low, high = rank(frm), rank(to)
    if low == 0 or high <= low:
        return []
    return [stage for stage in required(run) if low < rank(stage) < high]
