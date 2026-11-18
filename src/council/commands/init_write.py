"""council init scaffold's files, filled from the plugin's references/templates/: council.config.md (its stamps, the
fingerprint, a roster and the Gates rows the setup run's probes earned), conventions.md and map.md. Every line a
person reads stays as the template has it; only the placeholders a program can fill are filled."""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from council.commands import gate_output, init_seats
from council.commands.init_checks import Check
from council.records import cells, config, map_file, memory, paths
from council.records import gates as gate_files
from council.records import verdicts

TEMPLATES = "references/templates/"
QUICK_LINE = (config.QUICK_SETUP + " %s — the default roster as the catalog names it, no recast, no seat cards, "
              "no map; /council-init does the full setup")
EARLY = ("lint", "type check")             # quick to run, and a review reads what they report: grounding too


class Probe(NamedTuple):
    """A probe's saved verdict: its exit, the command it ran, why a pass proves nothing ('' when it counts), and why
    its command could not run at all, as council gate reads it ('' when it ran)."""

    exit: int
    command: str
    why: str
    cannot: str = ""


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
            verdict, output = gate_files.files(run, gate_files.slug(name))
            command = verdicts.command(verdict) or result["command"]
            code = result["exit"] if isinstance(result["exit"], int) else 1
            content = (paths.contents(output) or b"").decode("utf-8", "surrogateescape")
            found[name] = Probe(code, command, result["void"] or result["note"],
                                gate_output.could_not_run(code, content) if code else "")
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
        if _fails_today(run, broken):
            checked = "✓ %s: runs, and fails today (probe exit %d)" % (today, run.exit)
        elif run.exit or run.why:
            checked = "✗ %s: probe %s" % (today, run.why or "failed, exit %d" % run.exit)
        elif broken is not None and not broken.exit:
            checked = "✗ %s: passes with its tool broken — fix the command" % today
        else:
            checked, must = "✓ " + today, "yes" if broken is not None else "no"
    row = "| %s | `%s` | %s | %s | %s | %s | %s | %s |" % (check.name, _cell(check.command), at, must, checked, probe,
                                                         check.needs, check.side)
    return row, "%s · %s · mandatory %s" % (check.name, checked, must)


def _fails_today(run: Probe, broken: Probe | None) -> bool:
    """A probe that ran and failed while its broken twin could not run at all: the check works, and the project has
    problems it finds today (a linter on a real lint error). A probe that could not run, timed out or was marked
    invalid, or one with no twin to tell, is no such check."""
    return bool(run.exit and not run.cannot and not run.why and broken is not None and broken.cannot)


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
    out = _replace_rows(_unfilled(_unfilled(out, "Hard rules"), "Notes"), "Roster", fill.roster)
    return "\n".join(_replace_rows(out, "Gates", fill.gates))


def _unfilled(lines: list[str], heading: str) -> list[str]:
    """The lines with the template's placeholder under `## <heading>` taken out (a `<…>` or `- <…>` line and the
    indented lines carrying it on). An empty section is what its readers take for none yet: config.hard_rules for a
    build's orders, and the Chair copying the hard rules into a brief word for word."""
    at = lines.index("## " + heading)
    out, placeholder = lines[:at + 1], False
    for i in range(at + 1, len(lines)):
        if lines[i].startswith("## "):
            return out + lines[i:]
        placeholder = re.match(r"(- )?<", lines[i]) is not None or (
            placeholder and re.match(r"[ \t]+[^ \t]", lines[i]) is not None)
        if not placeholder:
            out.append(lines[i])
    return out


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


def fill_unprobed(text: str, checks: list[Check], probed: dict[str, Probe], today: str) -> tuple[str, list[str]]:
    """A quick setup's config with each Gates row that still reads `✗ not probed` and has a probe in the setup run
    written again by gate_row, every other line as it was; and the names of the rows it wrote."""
    by_name = {check.name: check for check in checks}
    lines, inside, done = text.split("\n"), False, []
    for i, line in enumerate(lines):
        if line.startswith("## "):
            inside = cells.heading(line.rstrip("\r")) == "gates"
            continue
        cut = [cell.strip(" \t\r") for cell in cells.table_cells(line)] if inside and line.startswith("|") else []
        name = cut[1] if len(cut) > 6 else ""
        if name not in by_name or "probe-" + name not in probed or not cut[5].startswith("✗ not probed"):
            continue
        lines[i] = gate_row(by_name[name], probed, today, "")[0] + ("\r" if line.endswith("\r") else "")
        done.append(name)
    return "\n".join(lines), done
