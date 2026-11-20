"""The stages of a council run, in order: each one's rank and the next step `council state phase=` records; what a
mode's Chair loads as method (method_files, method_bytes: a page's size budget's one definition); and what marks a run
opened on the path 2.1.0 removed (old_path, D77)."""
from __future__ import annotations

import contextlib
import re
from pathlib import Path

from council.records import events, paths, plan, state
from council.records.home import native, plugin_root

SYNTHESISED = ("council-review", "council-plan", "council-research")    # the modes whose seats end in a synthesis
COUNCIL_NEXT_AT_OPEN = "size the run and ask for the go-ahead"   # a new run's next: — Convene's own step
STAGES = {  # name: (rank, the next step when the mode's page names none); a build stands at Work's rank
    "convene": (1, COUNCIL_NEXT_AT_OPEN),
    "prepare": (2, "Prepare: the change index, the checks and earlier findings"),
    "work": (5, "Work: start the seats and record each one"),
    "build": (5, "task 1 — the first task of the plan"),  # where the build loop's gates count
    "judge": (7, "Judge: weigh the findings into synthesis.md"),
    "challenge": (8, "Challenge: verify what is kept"),
    "deliver": (9, "Deliver: write the deliverable and file the request"),
    "learn": (10, "Learn: memory proposals, then close the run"),
}
RETIRED = {"assign": 3, "brief": 4, "collect": 6}   # the old path's stages, ranked so an older run's record still
#                                     reads in order; no run enters one, so a run that shows one is an old one (D77)
SHORT = "convene prepare judge challenge deliver learn"          # a plan or research run with no worker (D60, D67)
PAIRED = "convene prepare work judge challenge deliver learn"    # fixed seats
REQUIRED = {"council-implement": "convene prepare build challenge deliver learn", "council-postgame": PAIRED,
            "council-review": PAIRED, "council-health": PAIRED}   # the reader and the runner (D50); D65's; D71's
ONE_PAGE = ("council-review", "council-implement", "council-plan", "council-research",   # every mode a run can have:
            "council-health", "council-postgame",   # its method is its own page alone (D47; D56; D60; D65; D71; a
            "test-architect", "council-init")       # test audit's, D75; setup's, D76)
FOLLOWS = {"council": ("council-plan", "council-implement")}   # /council: no run of its own, a plan run then a build
#                                     run, its page naming their pages' sections (D64)


def name_ok(stage: str, mode: str) -> bool:
    """A stage council state accepts; a council-init or test-architect run names its own, any lower-case word but a
    retired stage's (D77)."""
    return stage in STAGES or (mode in ("council-init", "test-architect") and stage not in RETIRED
                               and re.fullmatch("[a-z][a-z-]*", stage) is not None)


def rank(stage: str) -> int:
    return STAGES.get(stage, (RETIRED.get(stage, 0), ""))[0]


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
DESIGN_NEXT = {
    "prepare": "Prepare: memory select, the brief's <…> lines, a second designer or not, then the estimate "
               "(%s, section 2)",
    "work": "Work: the designer (both, in one message, for what is hard to undo), then record each one (%s, section 3)",
    "judge": "Judge: check each bug and claim, weigh the design into synthesis.md (%s, section 4)",
    "challenge": "Challenge: council check, then council evidence check until clean (%s, section 4)",
    "deliver": "Deliver: council ask save, the %s, the owner's decisions as consequences (%s, section 5)",
    "learn": "Learn: into the book, close the run, delete the scratch clones (%s, section 6)",
}


HEALTH_NEXT = {
    "prepare": "Prepare: memory select, the brief's <…> lines, then the estimate (council-health, section 1)",
    "work": "Work: the reader, then record it; the runner only for an item a run must show (council-health, "
            "section 2)",
    "judge": "Judge: check each proposal against the code, the worth bar, synthesis.md (council-health, section 4)",
    "challenge": "Challenge: council check until it is clean (council-health, section 4)",
    "deliver": "Deliver: council ask save, the health report, the rest into known problems (council-health, "
               "section 5)",
    "learn": "Learn: close the run, delete the scratch clones (council-health, section 6)",
}


POSTGAME_NEXT = {
    "prepare": "Prepare: the change index, the request's parts, the brief's <…> lines, then the estimate "
               "(council-postgame, section 2)",
    "work": "Work: both agents in one message, then record each one (council-postgame, section 3)",
    "judge": "Judge: each part's verdict checked against the code, verify-self.md (council-postgame, section 4)",
    "challenge": "Challenge: council check until the quotes are clean (council-postgame, section 5)",
    "deliver": "Deliver: council ask save, the post-game, its next tasks checked (council-postgame, section 6)",
    "learn": "Learn: close the run, delete the scratch clones, the next move (council-postgame, section 7)",
}


AUDIT_NEXT = {   # a large test audit's steps (D75), all in its page's Mode 1 Scope paragraph
    "prepare": "Prepare: the surface map, then the brief's <…> lines — the shares and the riskiest code "
               "(test-architect, Mode 1, Scope)",
    "work": "Work: the readers and the runner in one message, then record each one (test-architect, Mode 1, Scope)",
    "judge": "Judge: check each P1 against the test and the code yourself (test-architect, Mode 1, Scope)",
    "deliver": "Deliver: the audit report from their files (test-architect, Mode 1, Phase 3)",
}


def _design(mode: str, thing: str) -> dict[str, str]:
    """A design mode's steps, each naming its own page's section."""
    return {stage: text % ((thing, mode) if stage == "deliver" else (mode,)) for stage, text in DESIGN_NEXT.items()}


NEXT = {"council-review": REVIEW_NEXT, "council-implement": IMPLEMENT_NEXT,   # a one-page mode's own steps
        "council-plan": _design("council-plan", "plan"), "council-research": _design("council-research", "answer"),
        "council-health": HEALTH_NEXT, "council-postgame": POSTGAME_NEXT, "test-architect": AUDIT_NEXT}


def next_text(stage: str, mode: str = "") -> str:
    """A stage's next-step line: the mode's page's section for it (D47), else the stage's own words."""
    if stage in NEXT.get(mode, {}):
        return NEXT[mode][stage]
    return STAGES.get(stage, (0, ""))[1]


def required(run: Path) -> list[str]:
    """The stages a run must enter: a mode's own list (a review's always, D50); a plan's or research's with a worker,
    not Solo, the paired ones (the designer, D60; all ten until then); else the short path."""
    mode = state.field(state.text(run), "mode")
    if mode in REQUIRED or mode not in SYNTHESISED:
        return REQUIRED.get(mode, "").split()
    rows = plan.keyed(plan.text(run))                    # (kind, id, field): value, the first row of each
    workers = {key[1] for key, value in rows.items() if key[0] == "seat" and (key[2], value) == ("role", "worker")}
    picked = {key[1] for key, value in rows.items()
              if key[0] == "seat" and (key[2], value) == ("disposition", "selected")}
    if rows.get(("run", "run", "size")) != "solo" and workers & picked:
        return PAIRED.split()
    return SHORT.split()


def method_files(mode: str) -> list[str]:
    """What a mode's Chair loads as method, the one definition of a run's method load: the mode's own page alone
    (D47, D56, D76), whatever stages it enters; /council's page and the pages whose sections it follows (D64). Paths
    under the plugin's folder."""
    return ["skills/%s/SKILL.md" % name for name in (mode,) + FOLLOWS.get(mode, ())]


def method_bytes(mode: str, root: str | None = None) -> int:
    """The bytes of method_files under the plugin's folder (root, else the plugin's own), each file's CRLFs read as
    LF; a file that is not there adds nothing."""
    total = 0
    for name in method_files(mode):
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


def old_path(run: Path) -> str:
    """What marks a run as opened on the path 2.1.0 removed (D77), in words; '' for a run of today's. Its mode is not
    one a run can have (context-core, or a short name from before 0.3); or it entered assign, brief or collect, by its
    phase or its event stream; or it has no brief.md, which every mode but setup is given as its run opens."""
    content = state.text(run)
    mode = state.field(content, "mode")
    if mode not in ONE_PAGE:
        return "its mode, %s, is not one a run has now" % (mode or "(none)")
    entered = {state.field(content, "phase")}
    with contextlib.suppress(OSError, paths.RecordError):     # a stream that can't be read marks nothing
        entered |= {row.get("value", "") for row in events.records(run) if row.get("type") == "run.phase_changed"}
    old = [stage for stage in RETIRED if stage in entered]
    if old:
        return "it entered %s, %s the runs before 2.0 had" % (" and ".join(old), "stages" if old[1:] else "a stage")
    if mode != "council-init" and not (Path(run) / "brief.md").is_file():
        return "it has no brief.md, which a %s run is given as it opens" % mode
    return ""
