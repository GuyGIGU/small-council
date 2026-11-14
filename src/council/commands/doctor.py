"""council doctor: what would stop the council working here, or make it work worse, each as ERROR or WARN with its
fix — the config and its roster, cards and gates; open runs left behind, run plans and event streams; the memory;
the map; the stack fingerprint; what .council/.gitignore keeps out; and, when sharing is just me, what still
shares it. Exit 1 when there is an error."""
from __future__ import annotations

import contextlib
import io
import os
import re
import subprocess
import time
from pathlib import Path

from council.commands import cli, fingerprint, plan, resolve
from council.records import bytewise, cells, config, events, ignores, map_file, paths, runs, sharing
from council.records import home as where
from council.records import plan as plan_file

PLUGIN = Path(__file__).resolve().parents[3].as_posix()
ACTIVE = "active-run"       # the 0.2 pointer to the open run; doctor only says it is left behind
CARD_LIMIT = 8192
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
    cli.takes_flags(args, "doctor")
    cli.no_words("doctor", words)
    home = where.council_home()
    doc = Doctor(home)
    if not os.path.isdir(where.native(home)):
        doc.error("no council home at %s" % home, "run council-init in this repo")
        cli.say("doctor: 1 error(s), 0 warning(s)")
        return 1
    native = where.native(home)
    has_config = os.path.isfile(where.native(home + "/" + config.NAME))
    if not has_config:
        doc.error("no %s" % config.NAME, "run council-init")
    else:
        if config.first(native, "last-verified:") is None:
            doc.warn("the config has no last-verified stamp (an older layout)",
                     "run council-init refresh to migrate it to the current template")
        roster(doc)
        from council.commands import doctor_gates
        doctor_gates.gates(doc)
    open_runs(doc)
    run_plans(doc)
    active_run(doc)
    from council.commands import doctor_memory
    doctor_memory.memory_file(doc)
    map_stamp(doc)
    if has_config and _git("rev-parse", "--git-dir")[0] == 0:
        stack(doc)
    kept_out(doc)
    cli.say("doctor: %d error(s), %d warning(s)" % (doc.errors, doc.warnings))
    return 0 if doc.errors == 0 else 1


def ref_path(ref: str, root: str) -> str:
    """A roster or card reference as a file path: references/… is in the plugin, anything else in the repo."""
    if ref.startswith("references/"):
        return PLUGIN + "/" + ref
    return ref if ref.startswith("/") or re.match(r"[A-Za-z]:", ref) else root + "/" + ref


def _isfile(path: str) -> bool:
    return os.path.isfile(where.native(path))


def roster(doc: Doctor) -> None:
    rows = [tuple(bytewise.shown(c) for c in row) for row in config.roster_rows(where.native(doc.home))]
    if not rows:
        doc.warn("couldn't read a Roster table in %s" % config.NAME,
                 "run council-init refresh (older configs list seats instead of a table)")
        return
    cards = doc.home + "/cards"
    has_cards = os.path.isdir(where.native(cards))
    if not has_cards:
        doc.warn("no seat cards yet (.council/cards/ is missing)",
                 "a council-init refresh writes one per seat — workers read them instead of the generic docs")
    for slug, seat, ref in rows:
        if ref not in ("none", "n/a", "-") and not _isfile(ref_path(ref, doc.root)):
            doc.error("seat '%s' points at a reference doc that doesn't exist: %s" % (seat, ref),
                      "restore the doc, or point the seat at another one in %s" % config.NAME)
        if slug == "-":
            doc.warn("seat '%s' has no slug" % seat,
                     "give it a lowercase slug in the roster — it names the seat's file and card")
        elif has_cards:
            card(doc, seat, slug, cards + "/" + slug + ".md")
    slugs = [slug for slug, _, _ in rows if slug != "-"]
    shared = sorted({s for s in slugs if slugs.count(s) > 1}, key=lambda s: s.encode("utf-8", "surrogateescape"))
    if shared:
        doc.error("the roster repeats a slug: %s" % " ".join(shared),
                  "give each row its own slug — a lens that covers two areas gets two (dodds-web, dodds-admin)")


def card(doc: Doctor, seat: str, slug: str, path: str) -> None:
    try:
        with open(where.native(path), "rb") as stream:
            data = stream.read()
    except OSError:
        doc.warn("seat '%s' has no card (cards/%s.md)" % (seat, slug),
                 "council-init refresh writes one from references/templates/seat-card.md")
        return
    source = cells.field(data.decode("utf-8", "surrogateescape"), "source")
    source = re.sub(r"[ \t\n\v\f\r]*·.*\Z", "", source, count=1, flags=re.S).replace("`", "")
    if source and not _isfile(ref_path(source, doc.root)):
        doc.error("the card for '%s' names a source doc that doesn't exist: %s" % (seat, source),
                  "point the card's source: line at the seat's reference doc")
    if len(data) > CARD_LIMIT:
        doc.warn("the card for '%s' is over 8 KB" % seat,
                 "cut it to one line per principle — the full doc holds the detail")


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
    return sorted((f for f in found if os.path.isfile(where.native(f))),
                  key=lambda f: f.encode("utf-8", "surrogateescape"))


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


def active_run(doc: Doctor) -> None:
    pointer = where.native(doc.home + "/" + ACTIVE)
    try:
        data = Path(pointer).read_bytes()
    except OSError:
        return
    if not data:
        return
    p = data.split(b"\n")[0].replace(b"\r", b"").decode("utf-8", "surrogateescape")
    p = p if p.startswith("/") or re.match(r"[A-Za-z]:", p) else doc.root + "/" + p
    if _isfile(p + "/" + paths.STATE):
        if _field(p, "status").startswith(("complete", "abandoned")):
            doc.warn("active-run still points at a closed run", "empty .council/active-run (0.3 doesn't use it)")
        else:
            doc.warn("an older run is still marked open: %s" % p,
                     "resume it, or: council run close --run \"%s\" --status abandoned" % p)
    else:
        doc.warn("active-run points at a folder that no longer exists: %s" % p, "empty .council/active-run")


def _git(*words: str) -> tuple[int, str]:
    try:
        done = subprocess.run(["git"] + list(words), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        return 127, ""
    return done.returncode, done.stdout.decode("utf-8", "surrogateescape").strip()


def map_stamp(doc: Doctor) -> None:
    if not _isfile(doc.home + "/" + map_file.NAME):
        doc.warn("no %s" % map_file.NAME, "council-init builds it")
        return
    sha = map_file.commit(where.native(doc.home))
    if not sha:
        doc.warn("%s has no map-commit stamp" % map_file.NAME, "refresh the map and stamp map-commit")
    elif _git("rev-parse", "--git-dir")[0] == 0 and _git("cat-file", "-e", sha + "^{commit}")[0] != 0:
        doc.warn("map-commit %s isn't in this repo's history (a rebase or squash removed it), so nobody can tell "
                 "what changed since" % sha[:9],
                 "rebuild the map with a council-init refresh, and stamp the new map-commit")
    else:
        code, behind = _git("rev-list", "--count", sha + "..HEAD")
        if code == 0 and re.fullmatch("[0-9]+", behind) and int(behind) > 50:
            doc.warn("the map is %s commits behind HEAD" % behind,
                     "refresh the changed areas (council map status lists them)")


def stack(doc: Doctor) -> None:
    said = fingerprint.check()[1]
    if said.startswith("fingerprint: the stack changed"):
        said = said[len("fingerprint: "):]
        at = said.rfind(". Suggest")
        doc.warn(said[:at] if at >= 0 else said,
                 "run a council-init refresh — it re-checks the roster, cards and gates against the new stack")
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
