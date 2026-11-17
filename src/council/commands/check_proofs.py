"""council check on a build (council-implement): every fix's own proof, its gates/ verdicts read rather than taken
on trust. A task proves itself as before-<n> then after-<n>; a review fix as regress-<n> (its new check, red on the
version the verifier saw) then after-<n>. The name says which, so after-2789 is never a task's."""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from council import git
from council.commands import cli, gate_output, proof_reach
from council.records import bytewise, config, patches, seat_files, verdicts

KINDS = ("change", "preserve")
FALSE_GREEN = '"note": "exit 0, but'


class Row(NamedTuple):
    """One proof's row: whose it is (task <n>, review fix <n>), its status and its note."""

    who: str
    status: str
    note: str


class Tally:
    """The proofs counted: rows, broken, preserved, tests left behind, proved only through run-folder scripts, the
    revert checks that could not be made (whose, and why) and the proofs whose after-check ran on other files than
    those on disk now; with the tree of those files (git.disk_tree), taken once, when a proof first asks."""

    def __init__(self, top: str = "") -> None:
        self.rows: list[Row] = []
        self.broke = self.saved = self.preserved = self.run_folder = 0
        self.unmade: list[str] = []
        self.other: list[str] = []
        self.top, self.tree = top, None

    def now(self) -> str:
        if self.tree is None:
            self.tree = git.disk_tree(self.top)
        return self.tree


def _named(gates: Path, pattern: str) -> list[Path]:
    return [gates / name for name in seat_files.listed(gates, pattern) if (gates / name).is_file()]


def _code(value: str, empty: int) -> int:
    return int(value) if value else empty


def void(verdict: Path) -> str:
    """Why a before-check's record proves nothing, in words; '' when its result may count. A red is proof only of
    what it checked: not one marked invalid, a hang stopped at its time limit, or a command that never ran."""
    why = verdicts.text(verdict, "invalid")
    if why:
        return "marked invalid (%s)" % why
    if verdicts.holds(verdict, '"timed_out": true'):
        return "timed out after %ss" % verdicts.number(verdict, "seconds")
    code = verdicts.number(verdict, "exit")
    if code == "127":
        return "never ran: a command it calls was not found (exit 127)"
    module = gate_output.missing_module(gate_output.text(_output(verdict))) if code == "1" else ""
    return "never ran: Python has no module %s" % module if module else ""


def _output(verdict: Path) -> Path:
    return verdict.with_name(verdict.name[:-len(".json")] + ".txt")


def _said_nothing(after: Path) -> bool:
    """A change proof's after that ran no test: its verdict's note, or an output with no file matched or 0 tests.
    An after that printed nothing is not read so here: `grep -q`, or a script that asserts, prints nothing when it
    passes (a test gate that printed nothing carries the note)."""
    return verdicts.holds(after, FALSE_GREEN) or bool(gate_output.zero_tests(gate_output.text(_output(after)))) or \
        any(line.startswith("changed: no files matched") for line in bytewise.file_lines(_output(after), fold=False))


def _ran_nothing(before: Path, after: Path) -> bool:
    """A preserve proof whose before or after ran no test: a false green, or an output that shows nothing ran."""
    return verdicts.holds(before, FALSE_GREEN) or verdicts.holds(after, FALSE_GREEN) \
        or any(nothing_ran(out) for out in (_output(before), _output(after)))


def nothing_ran(out: Path) -> bool:
    """A gate's saved output that shows it ran no test: no files matched, no output at all, or 0 tests."""
    return any(line.startswith("changed: no files matched") for line in bytewise.file_lines(out, fold=False)) \
        or gate_output.blank(gate_output.text(out)) or bool(gate_output.zero_tests(gate_output.text(out)))


def status(before: Path, after: Path, number: str) -> str:
    """A proof whose before and after are both on record: ok, preserved, or what is wrong with it."""
    kind = verdicts.text(before, "proof") or "change"
    after_kind = verdicts.text(after, "proof") or "change"
    was, now = verdicts.number(before, "exit"), verdicts.number(after, "exit")
    said, says = verdicts.command(before), verdicts.command(after)
    if kind not in KINDS or after_kind not in KINDS:
        return "INVALID-PROOF"
    if kind != after_kind:
        return "DIFFERENT-PROOF"
    keep = kind == "preserve"
    if keep and before.name != "before-%s.json" % number:
        return "INVALID-PROOF"
    if keep and _code(was, 1) != 0:
        return "BEFORE-FAILED"
    if not keep and _code(was, 0) == 0:
        return "BEFORE-PASSED"
    if _code(now, 1) != 0:
        return "AFTER-FAILED"
    if (says and said and says != said) or (keep and (not said or not says)):
        return "DIFFERENT-COMMAND"
    if keep and not (_output(before).is_file() and _output(after).is_file()):
        return "MISSING-OUTPUT"
    if keep and _ran_nothing(before, after):
        return "NOTHING-RAN"
    if not keep and _said_nothing(after):
        return "NOTHING-RAN"
    return "preserved" if keep else "ok"


def _one(run: Path, top: str, before: Path, tally: Tally) -> None:
    name = before.name[:-len(".json")]
    number = name.split("-", 1)[1]
    who = ("task " if name.startswith("before-") else "review fix ") + number
    after = run / "gates" / ("after-%s.json" % number)
    gone, found, note = void(before), "", "-"
    if gone:                                # a red that proves nothing is no proof yet, whatever came after
        state, note = "NO-PROOF-YET", "%s %s — fix the check, run %s again" % (name, gone, name)
    elif not after.is_file():
        state = "NO-AFTER"
    else:
        state = status(before, after, number)
        found = proof_reach.test_path(top, verdicts.command(after) or verdicts.command(before))
        note = "test saved: " + found if found else "couldn't confirm a saved test"
    if state == "ok" and number.isdigit() and patches.rounds(run, int(number)):
        from council.commands import revert_check     # gate_run and tempfile, only when a rerun is due (D34)
        state, said, unmade = revert_check.check(run, top, number, verdicts.command(after) or verdicts.command(before),
                                                 (verdicts.text(after, "tree"), tally.now()))
        note += " · " + said
        tally.unmade += ["%s's revert check: %s" % (who, unmade)] if unmade else []
    elif state in ("ok", "preserved"):
        tally.other += _elsewhere(who, number, verdicts.text(after, "tree"), tally.now())
    if state in ("ok", "preserved"):
        tally.saved += bool(found)          # only a proof that held counts as a test kept
        tally.preserved += state == "preserved"
        said = verdicts.command(before)
        if proof_reach.run_folder_only(said) and proof_reach.run_folder_only(verdicts.command(after) or said):
            tally.run_folder += 1
            note += " · only run-folder scripts ran it, never the entry point a person runs"
    else:
        tally.broke += 1
    tally.rows.append(Row(who, state, note))
    cli.say("%s  proof  %s · %s" % (who, state, note))


def _elsewhere(who: str, number: str, tree: str, now: str) -> list[str]:
    """A proof with no revert check: its after-check's tree against the files on disk now, as the receipt says of a
    gate. [] when they are the same."""
    if not now:
        return ["%s: after-%s was not compared with the files on disk now — they can't be read as one git tree"
                % (who, number)]
    if tree == now:
        return []
    return ["%s: after-%s ran on other files than those on disk now (%s) — run council gate after-%s again"
            % (who, number, "tree " + tree[:12] if tree else "its record names none", number)]


def proofs(run: Path, top: str) -> Tally:
    """Each before-<n> and regress-<n> proof, then each after-<n> with nothing before it (NO-BEFORE)."""
    gates, tally = Path(run) / "gates", Tally(top)
    for before in _named(gates, "before-*.json") + _named(gates, "regress-*.json"):
        number = before.name[:-len(".json")].split("-", 1)[1]
        if before.name.startswith("regress-") and (gates / ("before-%s.json" % number)).is_file():
            continue                        # a task's own re-proof: its before-<n> stands
        _one(Path(run), top, before, tally)
    for after in _named(gates, "after-*.json"):
        number = after.name[len("after-"):-len(".json")]
        if (gates / ("before-%s.json" % number)).is_file() or (gates / ("regress-%s.json" % number)).is_file():
            continue
        tally.broke += 1
        tally.rows.append(Row("task " + number, "NO-BEFORE", "-"))
        cli.say("task %s  proof  NO-BEFORE · nothing showed the problem first" % number)
    return tally


def summary(tally: Tally, home: str) -> str:
    """The proofs' closing say lines; the build tier, which check.md records too."""
    tier, count = config.build_tier(home), len(tally.rows)
    if not count:
        cli.say("check: NO PROOF — this build recorded no before-and-after evidence (council gate before-<n> -- "
                "'<check>', then after-<n>) · build tier: " + tier)
        return tier
    if tally.preserved:
        cli.say("check: %d of %d task(s) checked · %d preserved behaviour · %d broken · %d left a test behind in the "
                "project · build tier: %s" % (count - tally.broke, count, tally.preserved, tally.broke, tally.saved,
                                               tier))
    else:
        cli.say("check: %d of %d fix(es) proved · %d broken · %d left a test behind in the project · build tier: %s"
                % (count - tally.broke, count, tally.broke, tally.saved, tier))
    if tally.run_folder:
        cli.say("check: %d proved only through scripts in the run folder — one proof of each task runs the command "
                "a person would run, named in the log (references/build-proof.md)" % tally.run_folder)
    return tier
