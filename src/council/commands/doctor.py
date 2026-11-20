"""council doctor: what would stop the council working here, or make it work worse, each as ERROR or WARN with its
fix — the config, the expert seats an older one still carries, and its gates; open runs left behind, run plans and
event streams; the memory;
the book; the map; the stack fingerprint; what .council/.gitignore keeps out; and, when sharing is just me, what still
shares it. Exit 1 when there is an error."""
from __future__ import annotations

import contextlib
import io
import os
import time
from pathlib import Path

from council import git
from council.commands import cli, fingerprint, plan, resolve
from council.records import bytewise, config, events, ignores, map_file, paths, runs, sharing
from council.records import home as where
from council.records import plan as plan_file

STALE_DAYS = 2              # find -mtime +2: open for three whole days or more


class Doctor:
    """The findings said so far, counted."""

    def __init__(self, home: str) -> None:
        self.home, self.root = home, os.path.dirname(home)
        self.errors = self.warnings = 0

    def finding(self, level: str, what: str, fix: str) -> None:
        cli.say("%s  %s\n       Fix: %s" % (level, what, fix))
        if level == "ERROR":
            self.errors += 1
        else:
            self.warnings += 1

    def error(self, what: str, fix: str) -> None:
        self.finding("ERROR", what, fix)

    def warn(self, what: str, fix: str) -> None:
        self.finding("WARN", what, fix)


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "doctor", "session", "line")
    if words[:1] == ["hooks"]:
        from council.commands import doctor_hooks
        return doctor_hooks.main(args, words[1:])
    if words[:1] == ["permissions"]:
        from council.commands import doctor_rules
        return doctor_rules.main(args, words[1:])
    cli.no_words("doctor", words)
    if args.value("line"):
        raise cli.Refusal("doctor takes --line only as: council doctor hooks --line")
    config.hush()                                    # doctor names each setting line it can't read itself
    home = where.council_home()
    doc = Doctor(home)
    if not os.path.isdir(where.native(home)):
        doc.error("no council home at %s" % home, where.NO_SETUP)
        cli.say("doctor: 1 error(s), 0 warning(s)")
        return 1
    native = where.native(home)
    has_config = os.path.isfile(where.native(home + "/" + config.NAME))
    if not has_config:
        doc.error("no %s" % config.NAME, where.NO_SETUP)
    else:
        if config.first(native, "last-verified:") is None:
            doc.warn("the config has no last-verified stamp (an older layout)",
                     "run council-init refresh to migrate it to the current template")
        from council.commands import doctor_config
        doctor_config.settings(doc)
        doctor_config.quick(doc)
        unused_seats(doc)
        from council.commands import doctor_gates
        doctor_gates.gates(doc)
    from council.commands import doctor_rules
    doctor_rules.report(doc)
    open_runs(doc)
    run_plans(doc)
    from council.commands import doctor_memory
    doctor_memory.memory_file(doc)
    if has_config:
        from council.commands import doctor_book
        doctor_book.report(doc)
    map_stamp(doc)
    if has_config and git.run(".", "rev-parse", "--git-dir")[0] == 0:
        stack(doc)
    kept_out(doc)
    from council.commands import doctor_hooks
    doctor_hooks.report(doc, doctor_hooks.session_id(args))
    cli.say("doctor: %d error(s), %d warning(s)" % (doc.errors, doc.warnings))
    return 0 if doc.errors == 0 else 1


def _isfile(path: str) -> bool:
    return os.path.isfile(where.native(path))


def unused_seats(doc: Doctor) -> None:
    """What an older config still carries of the expert seats (D72): its ## Roster section and its - cards: and
    - ledger: lines, which no run reads, the project's own pages the roster points at (watch lists now) and the
    seat cards on disk. One warning, and nothing at all for a config that carries none of them."""
    native = where.native(doc.home)
    rows = config.roster_table(native)
    written = rows or any(line.strip() for _, line in config.section(native, "roster"))
    carried = ["its ## Roster section (%d seat(s))" % len(rows)] if written else []
    for _, line in config.section(native, "memory"):
        found = config.pref_of(line)
        if found and found.key in ("cards", "ledger"):
            carried.append("its `- %s:` line" % found.key)
    if not carried:
        return
    pages = sorted({bytewise.shown(row.reference) for row in rows
                    if row.reference and not row.reference.startswith("references/")
                    and row.reference not in ("none", "n/a", "-")})
    cards = _cards(doc.home)
    said = "%s still carries the expert seats, which no run reads: %s" % (config.NAME, ", ".join(carried))
    if pages:
        said += "; the project's own page(s) it points at are watch lists now: %s" % ", ".join(pages)
    if cards:
        said += "; %d seat card(s) under .council/cards/ are unused too: %s" % (len(cards), ", ".join(cards))
    doc.warn(said, "run a council-init refresh — it names each of the project's own pages on the stack page as a watch "
                   "list, re-scopes the memory entries scoped to a seat, then removes the section and the lines on "
                   "your yes; the card files are yours to delete or keep, and it deletes none")


def _cards(home: str) -> list[str]:
    """The seat card files under the council home's cards/, by name."""
    try:
        names = os.listdir(where.native(home + "/cards"))
    except OSError:
        return []
    return sorted((name for name in names if name.endswith(".md")), key=bytewise.text)


def _stale_states(home: str) -> set[str]:
    """The run state files last written more than STALE_DAYS whole days ago (find -mtime +2)."""
    found, now = set(), time.time()
    for state_file in _state_files(home):
        try:
            age = now - os.stat(where.native(state_file)).st_mtime
        except OSError:
            continue
        if int(age // 86400) > STALE_DAYS:
            found.add(state_file)
    return found


def _state_files(home: str) -> list[str]:
    """runs/*/session-state.md, hidden folders too (find -mindepth 2 -maxdepth 2), in byte order."""
    folder = home + "/runs"
    try:
        names = os.listdir(where.native(folder))
    except OSError:
        return []
    found = [folder + "/" + name + "/" + paths.STATE for name in names]
    return sorted((f for f in found if os.path.isfile(where.native(f))), key=bytewise.text)


def open_runs(doc: Doctor) -> None:
    stale = _stale_states(doc.home)
    for run in runs.listing(doc.home, 1000000, "open"):
        if run.folder + "/" + paths.STATE in stale:
            name = run.folder.rsplit("/", 1)[-1]
            doc.warn("run %s (%s, phase %s) has been open since %s" % (name, runs.skill(run.mode), run.phase or "-",
                                                                     run.updated or "-"),
                     "resume it (council run resume --run %s), or: council run close --run \"%s\" --status abandoned"
                     % (name, run.folder))


def _field(folder: str, key: str) -> str:
    """A run state's header field, as the helper's state_field reads it."""
    return resolve.field(Path(where.native(folder)), key)


def run_plans(doc: Doctor) -> None:
    """Open runs' plans (a closed run's plan is its record of what was decided then), and every run's events."""
    for state_file in _state_files(doc.home):
        folder = state_file[:-len(paths.STATE) - 1]
        name = folder.rsplit("/", 1)[-1]
        phase, schema = _field(folder, "phase"), _field(folder, "plan-schema")
        if _field(folder, "status").startswith(("complete", "abandoned")):
            pass
        elif _isfile(folder + "/" + plan_file.NAME):
            code, said = _plan_check(folder)
            if code:
                last = said[-1] if said else ""
                if phase in ("convene", "prepare", "assign"):
                    doc.warn("run %s has a run plan that is not ready yet (%s)" % (name, last),
                             "complete it before Brief, then run: council run plan check --run %s" % name)
                else:
                    doc.error("run %s has an invalid run plan (%s)" % (name, last),
                              "fix it, then run: council run plan check --run %s" % name)
        elif schema:
            doc.error("run %s declares plan schema %s but %s is missing" % (name, schema, plan_file.NAME),
                      "restore it from references/templates/%s and complete it before dispatch" % plan_file.NAME)
        code, said = events.check(folder)
        if code:
            doc.error("run %s has an invalid event stream (%s)" % (name, "\n".join(said)),
                      "inspect %s/%s; a torn last line is mended by: council run events repair --run %s"
                      % (folder, events.NAME, name))


def _plan_check(folder: str) -> tuple[int, list[str]]:
    """council run plan check, quiet, as doctor reads it: the exit code, and every line it said."""
    said = io.StringIO()
    with contextlib.redirect_stdout(said), contextlib.redirect_stderr(said):
        code = plan.check(Path(where.native(folder)), True)
    return code, said.getvalue().splitlines()


def map_stamp(doc: Doctor) -> None:
    if not _isfile(doc.home + "/" + map_file.NAME):
        from council.commands.map_status import no_map
        doc.warn("no %s" % map_file.NAME, no_map(doc.home)[len("no map yet — "):])
        return
    if git.run(".", "rev-parse", "--git-dir")[0] != 0:
        found = map_file.Stale(map_file.commit(where.native(doc.home)), True, 0, [])
    else:
        found = map_file.stale(where.native(doc.home))            # the one reader, as council map status reads it
    if not found.sha:
        doc.warn("%s has no map-commit stamp" % map_file.NAME, "refresh the map and stamp map-commit")
    elif not found.known:
        doc.warn("map-commit %s isn't in this repo's history (a rebase or squash removed it), so nobody can tell "
                 "what changed since" % found.sha[:9],
                 "rebuild the map with a council-init refresh, and stamp the new map-commit")
    elif found.aside:
        doc.warn("the map is from another line of history: map-commit %s has %d commit(s) HEAD doesn't"
                 % (found.sha[:9], found.aside), "refresh the map on this branch (council map status lists the areas)")
    elif found.behind > 50:
        doc.warn("the map is %d commits behind HEAD" % found.behind,
                 "refresh the changed areas (council map status lists them)")
    from council.commands import doctor_config
    doctor_config.map_table(doc)


def stack(doc: Doctor) -> None:
    said = fingerprint.check()[1]
    if said.startswith("fingerprint: the stack changed"):
        said = said[len("fingerprint: "):]
        at = said.rfind(". Suggest")
        doc.warn(said[:at] if at >= 0 else said,
                 "run a council-init refresh — it re-checks the stack page, its watch lists and the gates against the new "
                 "stack")
    elif said.startswith("no stack-fingerprint"):
        doc.warn("the config has no stack-fingerprint",
                 "a council-init refresh records one, so a changed stack gets noticed")


def kept_out(doc: Doctor) -> None:
    home = where.native(doc.home)
    if not ignores.ignores(home, "runs/x"):
        doc.warn(".council/.gitignore doesn't ignore runs/", "add a line 'runs/' to .council/.gitignore")
    if not ignores.ignores(home, "asks/x") and not ignores.asks_shared(home):
        doc.warn(".council/.gitignore doesn't ignore asks/ — the user's own words would be committed",
                 "the next council run open adds 'asks/'; if the team shares requests on purpose, write '!asks/' "
                 "instead")
    if sharing.sharing(home) == "just me":
        from council.commands import sharing as shared
        for done, what, fix in shared.rows(doc.home):
            if not done:
                doc.warn(what, fix)
