"""The stages of a council run, in order: each one's rank and the next step `council state phase=` records; and what a
mode's Chair loads as method through them (method_files, method_bytes: the D13 budget's one definition)."""
from __future__ import annotations

import re
from pathlib import Path

from council.records import plan, state
from council.records.home import native, plugin_root

SYNTHESISED = ("council-review", "council-plan", "council-research")    # the modes whose seats end in a synthesis
COUNCIL_NEXT_AT_OPEN = "size the run and ask for the go-ahead"   # a new run's next: — Convene's own step
STAGES = {  # name: (rank, next step); a build stands where council-implement's build loop does (3-7)
    "convene": (1, COUNCIL_NEXT_AT_OPEN),
    "prepare": (2, "Prepare: the change index, the checks and earlier findings (doctrine 02-prepare.md)"),
    "assign": (3, "Assign: fill the run plan, then council run plan check (doctrine 03-assign.md)"),
    "brief": (4, "Brief: write brief.md with the memory in scope (doctrine 04-brief.md)"),
    "work": (5, "Work: start the seats and record each one (doctrine 05-work.md)"),
    "build": (5, "task 1 — the first task of the plan"),  # where the build loop's gates count
    "collect": (6, "Collect: council collect until it is clean (doctrine 06-collect.md)"),
    "judge": (7, "Judge: weigh the findings into synthesis.md (doctrine 07-judge.md)"),
    "challenge": (8, "Challenge: verify what is kept (doctrine 08-challenge.md)"),
    "deliver": (9, "Deliver: write the deliverable and file the request (doctrine 09-deliver.md)"),
    "learn": (10, "Learn: memory proposals, then close the run (doctrine 10-learn.md)"),
}
SHORT = "convene prepare judge challenge deliver learn"
REQUIRED = {"council-implement": "convene prepare build challenge deliver learn", "council-postgame": SHORT,
            "council-review": "convene prepare work judge challenge deliver learn"}   # the reader and the runner (D50)
ONE_PAGE = ("council-review", "council-implement")   # a mode whose method is its own page alone, no context-core or
#                                                     doctrine (D47; a build's since D56)


def name_ok(stage: str, mode: str) -> bool:
    """A stage council state accepts; a council-init or test-architect run names its own, any lower-case word."""
    return stage in STAGES or (mode in ("council-init", "test-architect") and re.fullmatch("[a-z][a-z-]*", stage)
                               is not None)


def rank(stage: str) -> int:
    return STAGES.get(stage, (0, ""))[0]


REVIEW_NEXT = {
    "prepare": ("Prepare: the change index, memory select, the brief's <…> lines, then the estimate "
                "(council-review, section 1)"),
    "work": "Work: both agents in one message, then record each one (council-review, section 2)",
    "judge": "Judge: weigh both seat files into synthesis.md (council-review, section 4)",
    "challenge": "Challenge: council check, then council evidence check until clean (council-review, section 4)",
    "deliver": "Deliver: council ask save, the review file, the report (council-review, section 5)",
    "learn": "Learn: close the run, delete the scratch clones, the fix hand-off (council-review, section 6)",
}


IMPLEMENT_NEXT = {
    "prepare": "Prepare: the restore point, the checks before the first change, the plan's task rows "
               "(council-implement, section 2)",
    "build": "task 1 — one fresh builder, then the checks (council-implement, section 3)",   # "task <n>" first:
    #                                                     a gate's failure counts under that task (gate_repair)
    "challenge": "Prove: the reader and the runner on the whole change, then one fix round (council-implement, "
                 "section 5)",
    "deliver": "Deliver: council check, the log, the report with its Undo line (council-implement, section 6)",
    "learn": "Learn: into the book, close the run, delete the scratch clones (council-implement, section 7)",
}
NEXT = {"council-review": REVIEW_NEXT, "council-implement": IMPLEMENT_NEXT}   # a one-page mode's own steps


def next_text(stage: str, mode: str = "") -> str:
    """A stage's next-step line; a one-page mode's names its page's section, never a doctrine file (D47)."""
    if stage in NEXT.get(mode, {}):
        return NEXT[mode][stage]
    return STAGES.get(stage, (0, ""))[1]


def required(run: Path) -> list[str]:
    """The stages a run must enter: a mode's own list (a review's always, D50); all ten for a plan or research run
    with a worker, not Solo."""
    mode = state.field(state.text(run), "mode")
    if mode in REQUIRED or mode not in SYNTHESISED:
        return REQUIRED.get(mode, "").split()
    rows = plan.keyed(plan.text(run))                    # (kind, id, field): value, the first row of each
    workers = {key[1] for key, value in rows.items() if key[0] == "seat" and (key[2], value) == ("role", "worker")}
    picked = {key[1] for key, value in rows.items()
              if key[0] == "seat" and (key[2], value) == ("disposition", "selected")}
    if rows.get(("run", "run", "size")) != "solo" and workers & picked:
        return [stage for stage in STAGES if stage != "build"]
    return SHORT.split()


def method_files(mode: str, entered: list[str] | None = None) -> list[str]:
    """What a mode's Chair loads as method, the one definition of a run's method load (D13): context-core's skill,
    the mode's own, and the doctrine of each stage it enters (every stage's when none are given; a build's loop
    has no doctrine file), as paths under the plugin's folder; a one-page mode's own page alone (D47, D56)."""
    if mode in ONE_PAGE:
        return ["skills/%s/SKILL.md" % mode]
    named = [stage for stage in (STAGES if entered is None else entered) if stage in STAGES and stage != "build"]
    skills = ["context-core"] + [mode] * (mode != "context-core")
    return (["skills/%s/SKILL.md" % name for name in skills] +
            ["references/doctrine/%02d-%s.md" % (rank(stage), stage) for stage in sorted(set(named), key=rank)])


def method_bytes(mode: str, entered: list[str] | None = None, root: str | None = None) -> int:
    """The bytes of method_files under the plugin's folder (root, else the plugin's own), each file's CRLFs read as
    LF; a file that is not there adds nothing."""
    total = 0
    for name in method_files(mode, entered):
        try:
            total += len(Path(native("%s/%s" % (root or plugin_root(), name))).read_bytes().replace(b"\r\n", b"\n"))
        except OSError:
            continue
    return total


def skipped(run: Path, frm: str, to: str) -> list[str]:
    """The required stages a move from frm to to passes over; none for a step back or a mode's own phase."""
    low, high = rank(frm), rank(to)
    if low == 0 or high <= low:
        return []
    return [stage for stage in required(run) if low < rank(stage) < high]
