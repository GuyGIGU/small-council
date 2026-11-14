"""council doctor's gate findings: no Gates table, or one in the older list layout; and for each row, shifted
columns, an empty command, the exit-code hazards a gate run names (records/gate_notes.py), Run at, Mandatory and
Checked values that mean nothing, and a slow gate at grounding that every review waits for."""
from __future__ import annotations

import glob
import os
import re

from council.commands.doctor import Doctor
from council.records import config, gate_notes, gate_table
from council.records import gates as gate_files
from council.records import home as where

SLOW = 300                  # seconds: a grounding gate slower than this holds up every review
_SECONDS = re.compile(r'.*"seconds": *([0-9][0-9]*)')


def gates(doc: Doctor) -> None:
    home = where.native(doc.home)
    rows = gate_table.gates(home)
    if not rows:
        none(doc, home)
        return
    for gate in rows:
        if gate.name:
            row(doc, gate)
    if not rows[0].has_side:
        doc.warn("the Gates table has no Side effects column (an older layout)",
                 "a council-init refresh adds Probe, Needs and Side effects — until then council gate --all runs "
                 "none of its gates unasked")


def none(doc: Doctor, home: str) -> None:
    if config.first(home, r"(?i)[-* \t\n\r\f\v]*guardrails: *declined") is not None:   # the user's own choice
        doc.warn("no gates in %s (guardrails declined) — every council report on this project says NOTHING WAS "
                 "CHECKED" % config.NAME,
                 "delete the 'guardrails: declined' line and run a council-init refresh whenever you want them fitted")
    elif gate_table.gates_listed(home):
        doc.error("the Gates section is in an older layout (a list, not a table), so no gate can run — every council "
                  "report on this project says NOTHING WAS CHECKED until it is migrated",
                  "run a council-init refresh — it moves the listed commands into the Gates table; there is nothing "
                  "to add by hand")
    else:
        doc.error("no gates in %s — every council report on this project says NOTHING WAS CHECKED" % config.NAME,
                  "add the project's real test / lint / build commands (a council-init refresh detects them, and "
                  "offers the ones you are missing)")


def row(doc: Doctor, gate: gate_table.Gate) -> None:
    g = gate.name
    shifted = gate.cells != gate.header_cells
    if shifted:
        doc.warn("gate '%s' has %d cells where the header has %d — the columns have shifted (an unescaped pipe?)"
                 % (g, gate.cells, gate.header_cells),
                 "wrap the command in backticks and escape any pipe as \\|, or remove it")
    if gate.command == "-":
        doc.warn("gate '%s' has an empty Command cell, so it never runs" % g,
                 "fill in its command in %s, or delete the row" % config.NAME)
        return
    for note in gate_notes.notes(gate.command):
        doc.warn("gate '%s' %s" % (g, note), "fix that command in %s" % config.NAME)
    if gate_notes.backslash(gate.command):
        doc.warn("gate '%s' %s" % (g, gate_notes.BACKSLASH),
                 "gate commands run under bash (Git Bash on Windows): write tools/run.ps1, or put the path in quotes")
    if gate_notes.winswitch(gate.command):
        doc.warn("gate '%s' %s" % (g, gate_notes.WINSWITCH),
                 "write the switch with a dash (-p:Configuration=Release), or as //p:… for a tool that only takes a "
                 "slash")
    if shifted:
        return                                # a shifted row's other cells mean nothing
    if "?" in gate.stages:
        doc.warn("gate '%s' has a Run at value that names no stage: '%s'" % (g, gate.at),
                 "write grounding, verify, both or manual — anything else is left out of council gate --all --at …")
    elif gate.stages == "-":
        doc.warn("gate '%s' has an empty Run at cell, so it runs in no set" % g,
                 "write grounding, verify, both or manual")
    if gate.must == "?":
        doc.warn("gate '%s' has a Mandatory value that isn't yes or no: '%s' — it counts as mandatory"
                 % (g, gate.mandatory), "write yes or no")
    if "g" in gate.stages:
        took = last_seconds(doc.home, g)
        if took is not None and took > SLOW:
            doc.warn("gate '%s' runs at grounding, and its last run took %d min — every review waits for it before "
                     "it starts" % (g, took // 60), "run it at verify (Run at: verify) unless a review needs its "
                     "result first")
    if gate.ran == "?":
        doc.warn("gate '%s' has a Checked value that isn't ✓ or ✗: '%s'" % (g, gate.checked),
                 "write ✓ <date> once it has run cleanly here, or ✗ <date>: <why it can't>")


def last_seconds(home: str, name: str) -> int | None:
    """How long the gate's newest recorded run took (ls -t over runs/*/gates/<slug>.json), None when unknown."""
    found = glob.glob(glob.escape(where.native(home)) + "/runs/*/" + gate_files.FOLDER + "/"
                      + glob.escape(gate_files.slug(name)) + ".json")
    stamped = []
    for path in found:
        try:
            stamped.append((-os.stat(path).st_mtime_ns, path.replace("\\", "/"), path))
        except OSError:
            continue
    if not stamped:
        return None
    try:
        with open(min(stamped)[2], "rb") as stream:
            text = stream.read().decode("utf-8", "surrogateescape")
    except OSError:
        return None
    for line in text.split("\n"):
        found_line = _SECONDS.match(line)
        if found_line:
            return int(found_line.group(1))
    return None
