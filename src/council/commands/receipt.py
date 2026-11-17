"""The two lines of a build's receipt that come from the records, not from the Chair (references/build-proof.md,
The receipt lines). council check prints them just before its closing line and writes them into check.md; the
Chair copies them into its receipt and writes neither. Same records, same lines.

- `Checked by machine:` each gate's baseline result (gates/baseline/) and its result now (gates/); the proof pairs
  are council check's own rows, not gates here. With no gate on record, the helper's own NOTHING WAS CHECKED words.
- `Not proved:` what the records show nobody checked: a task with no proof pair, a side of its pair missing, or a
  pair that reads NO-PROOF-YET; a configured gate never run; a gate that timed out, never ran, was marked invalid or
  passed with nothing run; a gate whose recorded tree is not the files on disk now — `not rerun`, with its reason,
  when gate --all took that green because nothing under the gate's Covers paths changed since (gate_reuse); a revert
  check that could not be made. Else `nothing`."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from council import git
from council.commands import check_proofs, task_slice
from council.records import config, gate_table, gates, patches, paths, tasks

NONE_RAN = "NOTHING WAS CHECKED — no gate ran in this run (council gate --all runs the configured ones)"
NO_PAIR = ("NO-PROOF-YET", "NO-BEFORE", "NO-AFTER")


def lines(run: Path, top: str, home: str, tally: check_proofs.Tally) -> list[str]:
    """The two lines, in the receipt's order."""
    found = [gate for gate in gates.results(run) if _of_the_work(gate["name"])]
    gate_lines, unrun = _gates(run, top, home, found)
    unproved = _tasks(run, tally) + gate_lines + tally.unmade
    return ["Checked by machine: " + _checked(run, home, found, unrun),
            "Not proved: " + (" · ".join(unproved) or "nothing")]


def _of_the_work(name: str) -> bool:
    """A gate that checks the work: not a side of a proof pair (before-, regress-, after-) and not a probe."""
    return gates.kind(name) == "check" and not name.startswith("after-")


def _result(gate: dict[str, Any]) -> str:
    if gate["void"]:
        return gate["void"]
    if gate["exit"] != 0:
        return "FAIL"
    return "pass with nothing run" if gate["note"] else "pass"


def _checked(run: Path, home: str, found: list[dict[str, Any]], unrun: set[str]) -> str:
    if not found:
        if gate_table.gates(home):
            return NONE_RAN
        said = gates.OLDER_LAYOUT if gate_table.gates_listed(home) else gates.NO_GATE_ROW
        return said % config.path(home).as_posix()
    before = {gate["name"]: _result(gate) for gate in gates.results(run, baseline=True)}
    return " · ".join("%s: %s → %s%s" % (gate["name"], before.get(gate["name"], "no baseline"), _result(gate),
                                          " (not rerun)" if gate["name"] in unrun else "") for gate in found)


def _tasks(run: Path, tally: check_proofs.Tally) -> list[str]:
    """The proofs that are missing or prove nothing yet, then each task of the plan (or with saved rounds) that
    has no proof row at all."""
    states = {row.who: row.status for row in tally.rows}
    out = ["%s: %s" % (who, state) for who, state in states.items() if state in NO_PAIR]
    named, plan = task_slice.plan_of(run)
    numbers = [task.number for task in tasks.read(paths.text_of(plan) if plan else "")] if named else []
    numbers += [one.task for one in patches.rounds(run)]
    for number in dict.fromkeys(numbers):
        if "task %d" % number not in states:
            out.append("task %d: no proof pair" % number)
    return out


def _gates(run: Path, top: str, home: str, found: list[dict[str, Any]]) -> tuple[list[str], set[str]]:
    """Configured gates with no record, gates whose result proves nothing, and gates run on other files: `not
    rerun` when their green stands for these files under their Covers paths. The lines, and the gates not rerun."""
    configured = gate_table.gates(home)
    rows = {row.name: row for row in reversed(configured)}      # a name written twice: its first row, as gate --all
    names = {gate["name"] for gate in found}
    out = ["gate %s: not run" % row.name for row in configured if row.name not in names]
    out += ["gate %s: %s" % (gate["name"], _result(gate)) for gate in found
            if gate["void"] or (gate["exit"] == 0 and gate["note"])]
    trees = [gate for gate in found if gate["tree"]]
    now = git.files_tree(top) if trees else ""
    if trees and not now:
        return out + ["gates' trees: the files in %s can't be read as a git tree, so none was compared" % top], set()
    others = [(gate, _not_rerun(run, top, now, rows.get(gate["name"]))) for gate in trees if gate["tree"] != now]
    return out + [why or "gate %s: ran on other files than those on disk now (tree %s)" % (gate["name"],
                  gate["tree"][:12]) for gate, why in others], {gate["name"] for gate, why in others if why}


def _not_rerun(run: Path, top: str, now: str, row: gate_table.Gate | None) -> str:
    """The receipt's line for a gate gate --all took on other files (gate_reuse), else ''."""
    if row is None or not row.covers:
        return ""
    from council.commands import gate_reuse      # gate_run, only when a gate names its paths (D34)
    took = gate_reuse.taken(run, row, top, now)
    return "gate %s: %s" % (row.name, gate_reuse.not_rerun(row, took)) if took else ""
