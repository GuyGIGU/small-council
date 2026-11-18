"""council init scaffold's files, filled from the plugin's references/templates/: council.config.md (its stamps, the
fingerprint, a roster and the Gates rows the setup run's probes earned), conventions.md and map.md. Every line a
person reads stays as the template has it; only the placeholders a program can fill are filled."""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from council.commands import init_seats
from council.commands.init_checks import Check
from council.records import config, map_file, memory
from council.records import gates as gate_files
from council.records import verdicts

TEMPLATES = "references/templates/"
QUICK_LINE = (config.QUICK_SETUP + " %s — the default roster as the catalog names it, no recast, no seat cards, "
              "no map; /council-init does the full setup")
EARLY = ("lint", "type check")             # quick to run, and a review reads what they report: grounding too


class Probe(NamedTuple):
    """A probe's saved verdict: its exit, the command it ran, and why a pass proves nothing ('' when it counts)."""

    exit: int
    command: str
    why: str


def template(plugin: str, name: str) -> str:
    return Path(plugin, TEMPLATES + name).read_bytes().decode("utf-8", "surrogateescape").replace("\r\n", "\n")


def probes(run: Path | None) -> dict[str, Probe]:
    """The run's probe verdicts (gates/probe-*.json), by gate name: probe-pytest, probe-pytest-broken."""
    if run is None:
        return {}
    found = {}
    for result in gate_files.results(run):
        name = result["name"]
        if gate_files.kind(name) == "probe":
            command = verdicts.command(gate_files.files(run, gate_files.slug(name))[0]) or result["command"]
            code = result["exit"] if isinstance(result["exit"], int) else 1
            found[name] = Probe(code, command, result["void"] or result["note"])
    return found


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def gate_row(check: Check, probed: dict[str, Probe], today: str, unprobed: str) -> tuple[str, str]:
    """(the Gates row, what it says in one line): Checked ✓ only for a probe that passed and counts, Mandatory yes
    only when its broken twin also failed; a candidate with no probe is ✗ not probed, so gate --all skips it."""
    run, broken = probed.get("probe-" + check.name), probed.get("probe-%s-broken" % check.name)
    at = "grounding, verify" if check.kind in EARLY else "verify"
    must = "no"
    if run is None:
        checked, probe = "✗ not probed: " + unprobed.replace("<name>", check.name), "not run: `%s`" % _cell(check.probe)
    else:
        probe = "`%s`" % _cell(run.command)
        if broken is not None:
            probe += " · broken: %s, exit %d" % ("fail" if broken.exit else "passed", broken.exit)
        if run.exit or run.why:
            checked = "✗ %s: probe %s" % (today, run.why or "failed, exit %d" % run.exit)
        elif broken is not None and not broken.exit:
            checked = "✗ %s: passes with its tool broken — fix the command" % today
        else:
            checked, must = "✓ " + today, "yes" if broken is not None else "no"
    row = "| %s | `%s` | %s | %s | %s | %s | %s | %s |" % (check.name, _cell(check.command), at, must, checked, probe,
                                                         check.needs, check.side)
    return row, "%s · %s · mandatory %s" % (check.name, checked, must)


def _replace_rows(lines: list[str], heading: str, rows: list[str]) -> list[str]:
    """The lines with the table under `## <heading>` holding these rows below its header and rule rows."""
    at = lines.index("## " + heading)
    head = next(i for i in range(at + 1, len(lines)) if lines[i].startswith("|"))
    end = head + 2
    while end < len(lines) and lines[end].startswith("|"):
        end += 1
    return lines[:head + 2] + rows + lines[end:]


class Config(NamedTuple):
    """What the config is stamped and filled with."""

    project: str
    today: str
    short: str
    fingerprint: str
    summary: str
    roster: list[str]
    gates: list[str]
    memory: str
    quick: bool


def config_text(plugin: str, fill: Config) -> str:
    lines = template(plugin, config.NAME).split("\n")
    out = []
    for line in lines:
        if line.startswith("# Council config — "):
            line = "# Council config — " + fill.project
        elif line.startswith("last-verified: "):
            line = "last-verified: %s @ %s" % (fill.today, fill.short)
            if fill.quick:
                out.append(line)
                line = QUICK_LINE % fill.today
        elif line.startswith("stack-fingerprint: "):
            line = fill.fingerprint
        elif line.startswith("- conventions: "):
            line = "- conventions: " + fill.memory
        out.append(line)
    if fill.quick:
        at = out.index("## Stack") + 1
        end = next(i for i in range(at, len(out)) if not out[i].strip() or out[i].startswith("## "))
        out[at:end] = ["Detected by `council init scaffold --quick`, with no judgment: %s. /council-init writes "
                       "this section." % fill.summary]
    out = _replace_rows(out, "Roster", fill.roster)
    return "\n".join(_replace_rows(out, "Gates", fill.gates))


def roster_rows(plugin: str, files: list[str], quick: bool) -> list[str]:
    """Quick: every catalog seat. Full: Fowler and Beck (never dropped), then the template's row for the Chair."""
    seats = init_seats.default_roster(plugin, files)
    rows = []
    for seat in seats:
        if seat.slug in init_seats.ALWAYS:
            rows.append(init_seats.row(seat, "kept — never dropped"))
        elif quick:
            rows.append(init_seats.row(seat, "quick setup: as the catalog names it, not recast"))
    if not quick:
        rows.append(next(line for line in template(plugin, config.NAME).split("\n")
                         if line.startswith("| <Seat> |")))
    return rows


def conventions_text(plugin: str, project: str) -> str:
    return template(plugin, memory.NAME).replace("# Conventions — <project>", "# Conventions — " + project, 1)


def map_text(plugin: str, project: str, sha: str, today: str) -> str:
    text = template(plugin, map_file.NAME).replace("# Codebase map — <project>", "# Codebase map — " + project, 1)
    text = re.sub(r"(?m)^map-commit: <full sha>$", ("map-commit: " + sha).rstrip(), text, count=1)
    return re.sub(r"(?m)^updated: <YYYY-MM-DD>$", "updated: " + today, text, count=1)
