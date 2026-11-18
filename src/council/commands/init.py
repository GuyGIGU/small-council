"""council init detect | init scaffold [--quick] [--run <folder>]: the mechanical part of setting up the council.
detect reads the project and prints, one fact per line, its stack fingerprint, its candidate checks (each with the
probe to run and its broken twin) and the catalog's seats with the surface the file list shows. scaffold writes the
setup files under the council home from the templates — council.config.md, conventions.md, map.md and .gitignore —
and never overwrites one: a file already there is kept and named. Its Gates rows come from the probes the open
council-init run holds; a candidate nobody probed is written ✗ not probed, so council gate --all skips it. --quick
writes the catalog's seats as a default roster, no map, and keeps the council on this machine (sharing: just me).
Nothing here runs a project command: the Chair probes each check with council gate probe-<name> -- '<fast form>'."""
from __future__ import annotations

import os
from pathlib import Path
from typing import NamedTuple

from council import clock, git
from council.commands import cli, fingerprint, init_checks, init_seats, init_write, resolve
from council.records import config, ignores, map_file, memory, paths, runs
from council.records import home as where

USAGE = "usage: council init detect | init scaffold [--quick] [--run <folder>]"
REFRESH = "a council-init refresh is the next step to bring it up to date"
HARD_RULES_LEFT = ("the ## Hard rules section of council.config.md — written empty: a `- ` line for each of the "
                   "project's non-negotiables, if it has any")


class Project(NamedTuple):
    """What setup reads of the project: this tree, the council home, the file list, the checks, the fingerprint."""

    tree: str
    home: str
    files: list[str]
    checks: list[init_checks.Check]
    summary: str
    fingerprint: str
    seen: str                   # the languages seen under three files each, when the summary lists none; else ''


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "init", "quick")
    verb = words[0] if words else ""
    if verb not in ("detect", "scaffold") or len(words) > 1:
        raise cli.Refusal(USAGE)
    if verb == "detect" and (args.value("quick") or args.value("run")):
        raise cli.Refusal("init detect only reads, and takes no flag — %s" % USAGE)
    if git.run(".", "rev-parse", "--git-dir")[0] != 0:
        raise cli.Refusal("council init needs a git repository: run it inside the project's git checkout (for a new "
                          "project, git init first)")
    project = read_project()
    return detect(project) if verb == "detect" else scaffold(project, args)


def read_project() -> Project:
    tree = where.this_tree()
    listed = git.run(where.native(tree), "ls-files", "-co", "--exclude-standard", names=True)[1]
    files = [f for f in listed.decode("utf-8", "surrogateescape").split("\n")
             if f and not f.startswith(".council/")]
    summary, seen = fingerprint.stack_read()
    return Project(tree, where.council_home(), files, init_checks.found(Path(where.native(tree)), files), summary,
                   "stack-fingerprint: %s — %s" % (fingerprint.digest(summary), summary), seen)


def _quoted(word: str) -> str:
    return "'%s'" % word.replace("'", "'\\''")


def detect(project: Project) -> int:
    has_config = os.path.isfile(where.native(project.home + "/" + config.NAME))
    cli.say("council init detect — reads the project, writes nothing")
    cli.say("project: " + project.tree)
    cli.say("council home: %s — %s" % (project.home, "council.config.md exists" if has_config else "no config yet"))
    cli.say(project.fingerprint)
    if project.seen:
        cli.say(project.seen)
    for check in project.checks:
        cli.say("check: %s · %s · from %s" % (check.name, check.kind, check.source))
        cli.say("  command: " + check.command)
        cli.say("  probe: council gate probe-%s -- %s" % (check.name, _quoted(check.probe)))
        cli.say("  broken: council gate probe-%s-broken -- %s" % (check.name, _quoted(check.broken)))
        cli.say("  needs: %s · side effects: %s" % (check.needs, check.side))
    cli.say("checks: %s — looked at %s" % ("%d found" % len(project.checks) if project.checks else "none found",
                                           ", ".join(init_checks.LOOKED_AT)))
    for seat in init_seats.default_roster(where.plugin_root(), project.files):
        cli.say("seat: %s · %s · %s · %s · surface: %s" % (
            seat.slug, seat.practitioner, seat.lens, seat.doc,
            ", ".join(seat.markers) if seat.markers else "nothing in the file list (the catalog's rule needs a look)"))
    if has_config:
        cli.say("next: council.config.md exists, so council init scaffold keeps it — " + REFRESH)
    else:
        cli.say("next: in an open council-init run (council run open council-init), probe each check you keep, then: "
                "council init scaffold")
        cli.say("next: or, for a quick setup with no probes and the catalog's seats: council init scaffold --quick")
    return 0


def setup_run(args: cli.Args, home: str, tree: str) -> Path | None:
    """The open council-init run whose probes fill the Gates rows: --run, else the one on this tree; None for none."""
    given = args.value("run")
    if given:
        folder = resolve.run_path(given, home)
        mode = resolve.field(Path(where.native(folder)), "mode") if resolve.is_run(folder) else ""
        if runs.skill(mode) != "council-init":
            raise cli.Refusal("--run %s is not a council-init run — pass the setup run (council run status lists the "
                              "open ones)" % given)
        return Path(where.native(folder))
    found = [run.folder for run in runs.listing(home, 1000000, "open")
             if runs.skill(run.mode) == "council-init" and runs.here(run.code_root, tree)]
    if len(found) > 1:
        raise cli.Refusal("several council-init runs are open on this working tree — pass --run <folder>: %s"
                          % resolve.names(found))
    return Path(where.native(found[0])) if found else None


def scaffold(project: Project, args: cli.Args) -> int:
    quick, home = args.value("quick") == "1", project.home
    has_config = os.path.isfile(where.native(home + "/" + config.NAME))
    run = setup_run(args, home, project.tree)
    if not has_config and not quick and run is None:
        raise cli.Refusal("no open council-init run to read the probes from, so no Gates row could say ✓ — open one "
                          "(council run open council-init), probe the checks council init detect lists, then run "
                          "council init scaffold again; or, for a quick setup: council init scaffold --quick")
    try:
        os.makedirs(where.native(home), exist_ok=True)
    except OSError:
        raise cli.Refusal("cannot create %s — free the path, then run council init scaffold again" % home) from None
    _gitignore(home)
    plugin = where.plugin_root()
    left: list[str] = []
    quick_config = has_config and config.quick_setup(where.native(home))
    if quick_config and not quick:
        left += _from_quick(project, run)
    elif has_config:
        cli.say("Kept %s/%s — it exists, so nothing in it changed; %s" % (home, config.NAME, REFRESH))
    else:
        left += _config(project, plugin, init_write.probes(run), quick)
    left += _memory(project, plugin)
    if not quick:
        left += _map(project, plugin)
    if quick and not has_config:
        cli.say("This is a quick setup: every catalog seat as the catalog names it, with no recast, no seat cards and "
                "no map, and the council kept on this machine (sharing: just me). /council-init does the full setup.")
    left = list(dict.fromkeys(left))
    for line in left or ["nothing" if quick and not has_config else
                         "nothing from this command — its files were there already; " + REFRESH]:
        cli.say("Left for the Chair: " + line)
    return 0


def _from_quick(project: Project, run: Path | None) -> list[str]:
    """A quick setup made full: its `✗ not probed` Gates rows that the setup run probed, written as a first write
    would; nothing else in the config changes. The lines it leaves for the Chair."""
    path = project.home + "/" + config.NAME
    if run is None:
        cli.say("Kept %s — a quick setup's config: to fill its unprobed checks, open a council-init run (council run "
                "open council-init), probe them, then run council init scaffold again" % path)
        return []
    data = paths.contents(where.native(path)) or b""
    text, done = init_write.fill_unprobed(data.decode("utf-8", "surrogateescape"), project.checks,
                                          init_write.probes(run), clock.now_date())
    if done:
        paths.atomic_write(Path(where.native(path)), text.encode("utf-8", "surrogateescape"), ".config-",
                           keep_mode=True)
        cli.say("Updated %s — the Gates rows the setup run probed: %s; nothing else in it changed"
                % (path, ", ".join(done)))
    else:
        cli.say("Kept %s — no `✗ not probed` Gates row has a probe in the setup run, so nothing in it changed" % path)
    return ["the roster — tailor the quick setup's rows: recasts, drops and each seat's surface markers "
            "(council-init, Phase B)", "the ## Stack section of council.config.md", HARD_RULES_LEFT,
            "the map's prose — each section of map.md, the One way per job table too (council-init, Phase D)",
            "the `setup: quick` line in council.config.md: take it out once the setup is full"]


def _write_new(path: str, text: str) -> bool:
    """Create the file with this text; False when it is already there (never overwritten)."""
    try:
        with open(where.native(path), "xb") as handle:
            handle.write(text.encode("utf-8", "surrogateescape"))
    except FileExistsError:
        return False
    except OSError:
        raise cli.Refusal("cannot write %s — free the path, then run council init scaffold again" % path) from None
    return True


def _gitignore(home: str) -> None:
    path = ignores.path(where.native(home))
    before = paths.contents(path)
    said = ignores.keep_out(where.native(home))
    after = paths.contents(path)
    if after != before:
        cli.say("Wrote %s/%s — runs/ and asks/ stay out of git" % (home, ignores.NAME))
    if said:
        cli.warn("council: " + said)


def _config(project: Project, plugin: str, probed: dict[str, init_write.Probe], quick: bool) -> list[str]:
    """Write council.config.md; the lines it leaves for the Chair."""
    today = clock.now_date()
    why = "quick setup, no probe ran" if quick and not probed else "no probe-<name> in the setup run"
    rows, said = [], []
    for check in project.checks:
        row, line = init_write.gate_row(check, probed, today, why)
        rows.append(row)
        said.append(line)
    found = memory.locate(project.home).path
    root = project.home.rsplit("/", 1)[0]
    mem = found[len(root) + 1:] if os.path.isfile(where.native(found)) and found.startswith(root + "/") \
        else ".council/" + memory.NAME
    fill = init_write.Config(os.path.basename(root), today, git.text(project.tree, "rev-parse", "--short", "HEAD")
                             or "no commit yet", project.fingerprint,
                             project.summary + (" (%s)" % project.seen if project.seen else ""),
                             init_write.roster_rows(plugin, project.files, quick), rows, mem, quick)
    text = init_write.config_text(plugin, fill)
    if quick:
        from council.records import sharing as setting
        text = setting.with_sharing(text.encode("utf-8", "surrogateescape"), "just me").decode("utf-8",
                                                                                               "surrogateescape")
    path = project.home + "/" + config.NAME
    _write_new(path, text)
    cli.say("Wrote %s — %s, last-verified %s, run preferences at the template's defaults%s, %d Gates row(s)"
            % (path, project.fingerprint.split(" — ")[0], today, " (sharing: just me)" if quick else "", len(rows)))
    cli.say_all("gate: " + line for line in said)
    if quick:
        from council.commands import sharing
        sharing.git_exclude(os.path.dirname(project.home), True)
    return _config_left(project, probed, quick)


def _config_left(project: Project, probed: dict[str, init_write.Probe], quick: bool) -> list[str]:
    names = {check.name for check in project.checks}
    stray = sorted(name for name in probed if name[len("probe-"):] not in names
                   and not (name.endswith("-broken") and name[len("probe-"):-len("-broken")] in names))
    left = [] if quick else ["the roster — a row per seat beyond Fowler and Beck, each with its surface markers, in "
                             "place of the <Seat> row (council-init, Phase B)",
                             "the ## Stack section of council.config.md", HARD_RULES_LEFT]
    left +=["%s ran, but no detected check is named %s, so it has no Gates row — add its row by hand"
             % (name, name[len("probe-"):]) for name in stray]
    return left


def _memory(project: Project, plugin: str) -> list[str]:
    found = memory.locate(project.home).path
    if os.path.isfile(where.native(found)):
        cli.say("Kept %s — the memory file exists, so nothing in it changed" % found)
        return []
    path = project.home + "/" + memory.NAME
    if _write_new(path, init_write.conventions_text(plugin, os.path.basename(os.path.dirname(project.home)))):
        cli.say("Wrote %s — from the template, with no entries" % path)
    return []


def _map(project: Project, plugin: str) -> list[str]:
    path = project.home + "/" + map_file.NAME
    sha = git.text(project.tree, "rev-parse", "HEAD") or ""
    text = init_write.map_text(plugin, os.path.basename(os.path.dirname(project.home)), sha, clock.now_date())
    if not _write_new(path, text):
        cli.say("Kept %s — it exists, so nothing in it changed; %s" % (path, REFRESH))
        return []
    cli.say("Wrote %s — map-commit %s, its sections still to write" % (path, sha[:12] or "(no commit yet)"))
    return ["the map's prose — each section of map.md, the One way per job table too (council-init, Phase D)"]
