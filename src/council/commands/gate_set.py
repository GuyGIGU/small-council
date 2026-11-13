"""council gate --all [--at grounding|verify]: the project's configured gates, each one that may run unasked. A gate
left out is said, counted and named if it was required; a green report with nothing behind it is the worst outcome
there is, so a set that ran nothing exits 4 and says NOTHING WAS CHECKED."""
from __future__ import annotations

from council.commands import cli, gate_lock, gate_notes, gate_output, gate_repair, gate_run
from council.commands.gate import safe
from council.records import config, gates

STAGES = {"grounding": ("g", "grounding"), "verify": ("v", "verify"), "verification": ("v", "verify")}


class _Tally:
    """What the set did, for its summary line."""

    def __init__(self) -> None:
        self.ran = self.passed = self.skipped = self.required = self.empty = self.nothing = 0
        self.failed = 0
        self.old = False
        self.red: list[str] = []
        self.reds: list[str] = []
        self.none: list[str] = []
        self.unrun: list[str] = []
        self.files: dict[str, str] = {}

    def skip(self, name: str, mandatory: bool, why: str) -> None:
        cli.say("gate %s: skipped — %s" % (name, why))
        self.skipped += 1
        if mandatory:
            self.required += 1
            self.reds.append(name)


def run_all(call: gate_run.Call, at: str, mode: str, wait: tuple[bool, str]) -> int:
    """Run the set; 0 when every mandatory gate that ran passed, 1 when one failed, 4 when nothing ran."""
    stage, label = "", ""
    if at:
        if at.translate(gate_output.ASCII_LOWER) not in STAGES:
            raise cli.Refusal("--at takes grounding or verify (got '%s')" % at)
        stage, label = STAGES[at.translate(gate_output.ASCII_LOWER)]
    gate_lock.take(call.run, *wait)     # refuses, before anything is written, while another gate call runs
    call = call._replace(baseline=stage != "v")    # the untouched code: each gate's first output is its baseline
    cfg = call.home + "/council.config.md"
    rows = config.gates(call.home)
    if not rows:
        if config.gates_listed(call.home):
            cli.say("NOTHING WAS CHECKED — the Gates section of %s is in an older layout (a list, not a table), so no "
                    "gate could be read; a council-init refresh migrates it" % cfg)
        else:
            cli.say("NOTHING WAS CHECKED — this project has no automated check configured (no Gates row in %s)" % cfg)
        return 4
    tally = _Tally()
    for row in rows:
        trail = _runnable(call, row, stage, mode, tally)
        if trail is None:
            continue
        tally.ran += 1
        result = gate_run.run_gate(call, row.name, row.command)
        if result.code == 0:
            gate_repair.record(call.run, row.name, 0, trail, False)
            tally.passed += 1
            if result.empty == 1:
                tally.empty += 1
                tally.none.append(row.name)
            elif result.empty in (2, 3):
                tally.nothing += 1
                tally.unrun.append(row.name)
        else:                            # the set's failures are no attempts: a build counts its own gate runs
            tally.red.append(row.name)
            if row.must != "no":
                tally.failed = 1
    return _summary(tally, cfg, label)


def _runnable(call: gate_run.Call, row: config.Gate, stage: str, mode: str, tally: _Tally) -> str | None:
    """The gate's repair trail ('' outside a build) when it runs in this set; None (said) when it does not."""
    name, must = row.name, row.must != "no"
    if row.cells != row.header_cells:    # before the --at filter: a shifted row's Run-at cell means nothing
        tally.skip(name, False, "its row has %d cells where the header has %d (an unescaped | ?); fix the row"
                   % (row.cells, row.header_cells))
        return None
    by_name = "its Run at cell says '%s', so it runs only by name: council gate %s" % (row.at, gate_run.qname(name))
    if stage and stage not in row.stages:
        if row.stages == "-":            # no stage at all: it runs in no set, which must never be silent
            tally.skip(name, must, "its Run at cell is empty, so it runs only by name; fill it in (grounding, verify)")
        elif "?" in row.stages:
            tally.skip(name, must, "its Run at cell says '%s', which names no stage here; write grounding, verify, "
                       "both or manual" % row.at)
        elif row.stages == "m" and must:
            tally.skip(name, must, by_name)
        return None
    if not stage and row.stages == "m":
        if must:
            tally.skip(name, must, by_name)
        return None
    if row.command == "-":               # a cleared cell: named and counted, never a gate that quietly vanished
        tally.skip(name, must, "its Command cell is empty; fill it in, or run it by name with its command: council "
                   "gate %s -- '<command>'" % gate_run.qname(name))
        return None
    if row.must == "?":
        cli.say("note: gate %s — its Mandatory cell says '%s', which isn't yes or no, so it counts as mandatory; write "
                "yes or no" % (name, row.mandatory))
    if row.ran == "not":
        tally.skip(name, must, "the config marks it not runnable here (%s)" % row.checked)
        return None
    if row.ran == "?":
        cli.say("note: gate %s — its Checked cell says '%s', which isn't ✓ or ✗; running it anyway (write ✓ <date> "
                "once it runs cleanly here, or ✗ <why> if it can't)" % (name, row.checked))
    if not _allowed(row, tally) or not _own_file(row, call, tally):
        return None
    for note in ([gate_notes.BACKSLASH] if gate_notes.backslash(row.command) else []) \
            + ([gate_notes.WINSWITCH] if gate_notes.winswitch(row.command) else []) + gate_notes.notes(row.command):
        cli.say("note: gate %s — its command %s" % (name, note))
    trail = ""
    if mode == "council-implement":
        trail = gate_repair.trail(call.run, name)
        if trail.startswith("stop\t"):
            tally.skip(name, must, "stopped: it failed three repair attempts for task %s; only on the user's go: "
                       "council repair allow %s --user-said \"<their words>\"" % (trail.split("\t")[1],
                                                                                  gate_run.qname(name)))
            return None
    return trail


def _allowed(row: config.Gate, tally: _Tally) -> bool:
    """Safe to run unasked; else skipped, saying why."""
    if safe(row.side, row.needs, row.has_side):
        return True
    extra = "" if row.needs == "-" else " · needs: " + row.needs
    ask = "Run it by name once the user agrees: council gate %s" % gate_run.qname(row.name)
    if not row.has_side:
        tally.old = True
        tally.skip(row.name, row.must != "no", "the Gates table has no Side effects column (an older layout), so "
                   "nothing says it is safe to run unasked. " + ask)
    elif row.side == "-":
        tally.skip(row.name, row.must != "no", "side effects not recorded. Fill the cell, or run it by name once the "
                   "user agrees: council gate %s" % gate_run.qname(row.name))
    else:
        tally.skip(row.name, row.must != "no", "side effects: %s%s. %s" % (row.side, extra, ask))
    return False


def _own_file(row: config.Gate, call: gate_run.Call, tally: _Tally) -> bool:
    """Two names that differ only in punctuation (unit tests, unit_tests) save to one gates/ file, and the
    second would overwrite the first's record."""
    slug = gates.slug(row.name)
    if slug in tally.files:
        tally.skip(row.name, row.must != "no", "it would overwrite the record of gate %s (both save as gates/%s.txt); "
                   "rename one of them" % (tally.files[slug], slug))
        return False
    tally.files[slug] = row.name
    return True


def _summary(tally: _Tally, cfg: str, label: str) -> int:
    at = " at '%s'" % label if label else ""
    if tally.ran == 0:
        if tally.old:
            cli.say("NOTHING WAS CHECKED — the Gates table in %s has no Side effects column (an older layout), so no "
                    "gate runs unasked; a council-init refresh adds it, or run a gate by name once the user agrees"
                    % cfg)
        elif tally.skipped == 0:
            cli.say("NOTHING WAS CHECKED — no gate in %s runs%s" % (cfg, at))
        else:
            cli.say("NOTHING WAS CHECKED — %d gate(s) could not run here%s; see the reasons above"
                    % (tally.skipped, at))
        return 4
    tail = ""
    if tally.skipped:
        tail = " · %d skipped" % tally.skipped
        if tally.required:
            tail += " (%d of them required: %s — so this run proves less than it looks)" % (
                tally.required, ", ".join(tally.reds))
    if tally.empty:
        tail += " · %d had nothing to check (%s — 0 files matched)" % (tally.empty, ", ".join(tally.none))
    if tally.nothing:
        tail += " · %d passed with nothing run (%s — see above)" % (tally.nothing, ", ".join(tally.unrun))
    failing = tally.ran - tally.passed
    if failing == 0:
        cli.say("gates: %d ran — all pass%s" % (tally.ran, tail))
    else:
        cli.say("gates: %d ran — %d pass, %d FAIL (%s%s)%s" % (tally.ran, tally.passed, failing, ", ".join(tally.red),
                " — mandatory" if tally.failed else ", not mandatory", tail))
    if tally.failed:
        cli.say("a mandatory gate failed")
    return tally.failed
