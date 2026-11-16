"""The two lines of a build's receipt that come from the records, not from the Chair (references/build-proof.md,
The receipt lines). council check prints them just before its closing line and writes them into check.md; the
Chair copies them into its receipt and writes neither. Same records, same lines.

- `Checked by machine:` each gate's baseline result (gates/baseline/) and its result now (gates/); the proof pairs
  are council check's own rows, not gates here. With no gate on record, the helper's own NOTHING WAS CHECKED words.
- `Not proved:` what the records show nobody checked: a task with no proof pair, a side of its pair missing, or a
  pair that reads NO-PROOF-YET; a configured gate never run; a gate that timed out, never ran, was marked invalid or
  passed with nothing run; a gate whose recorded tree is not the files on disk now; a revert check that could not
  be made. Else `nothing`."""
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
    unproved = _tasks(run, tally) + _gates(top, home, found) + tally.unmade
    return ["Checked by machine: " + _checked(run, home, found), "Not proved: " + (" · ".join(unproved) or "nothing")]


def _of_the_work(name: str) -> bool:
    """A gate that checks the work: not a side of a proof pair (before-, regress-, after-) and not a probe."""
    return gates.kind(name) == "check" and not name.startswith("after-")


def _result(gate: dict[str, Any]) -> str:
    if gate["void"]:
        return gate["void"]
    if gate["exit"] != 0:
        return "FAIL"
    return "pass with nothing run" if gate["note"] else "pass"


def _checked(run: Path, home: str, found: list[dict[str, Any]]) -> str:
    if not found:
        if gate_table.gates(home):
            return NONE_RAN
        said = gates.OLDER_LAYOUT if gate_table.gates_listed(home) else gates.NO_GATE_ROW
        return said % config.path(home).as_posix()
    before = {gate["name"]: _result(gate) for gate in gates.results(run, baseline=True)}
    return " · ".join("%s: %s → %s" % (gate["name"], before.get(gate["name"], "no baseline"), _result(gate))
                      for gate in found)


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


def _gates(top: str, home: str, found: list[dict[str, Any]]) -> list[str]:
    """Configured gates with no record, gates whose result proves nothing, and gates run on other files."""
    names = {gate["name"] for gate in found}
    out = ["gate %s: not run" % row.name for row in gate_table.gates(home) if row.name not in names]
    out += ["gate %s: %s" % (gate["name"], _result(gate)) for gate in found
            if gate["void"] or (gate["exit"] == 0 and gate["note"])]
    trees = [gate for gate in found if gate["tree"]]
    now = git.files_tree(top) if trees else ""
    if trees and not now:
        return out + ["gates' trees: the files in %s can't be read as a git tree, so none was compared" % top]
    return out + ["gate %s: ran on other files than those on disk now (tree %s)" % (gate["name"], gate["tree"][:12])
                  for gate in trees if gate["tree"] != now]
