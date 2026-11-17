"""council doctor on the config's lines and its age: a setting whose value can't be read (an error: the helper uses
a default, or holds the push freeze, until it is fixed), and what a project set up by an older plugin is missing or
still carries — a setting no longer read, `build tier: full` without `checking:`, a map with no one-way table."""
from __future__ import annotations

from council.commands.doctor import Doctor
from council.records import config, map_file
from council.records import home as where

TEMPLATE = "references/templates/" + config.NAME


def settings(doc: Doctor) -> None:
    """Each setting line the helper can't read, each line it no longer reads, and the config's age."""
    home = where.native(doc.home)
    for found in config.problems(home):
        then = ("the push freeze holds (it counts as off)" if found.key == "pushes" else
                "the helper uses the setting's default")
        doc.error("%s line %d, `- %s: %s`: %s takes %s, so until it is fixed %s"
                  % (config.NAME, found.line, found.key, found.said, found.key, config.SETTINGS[found.key][0], then),
                  "write `- %s:` with one of those values (a `# note` or `(note)` after it is fine)" % found.key)
    _run_preferences(doc, home)
    tier, checks = config.pref(home, "build tier"), config.pref(home, "checking", empty=True)
    if tier and tier.value == "full" and checks is None:
        doc.warn("%s line %d says `- build tier: full` and has no `- checking:` line: full used to mean a verifier "
                 "per task, and now records a proof pair per task only — a build sends one verifier, at the end"
                 % (config.NAME, tier.line),
                 "add `- checking: per task` under ## Run preferences for a verifier per task (or `- checking: one "
                 "per batch` to keep one)")


def _run_preferences(doc: Doctor, home: str) -> None:
    """Under ## Run preferences: a line no longer read, a key no setting has, a setting written twice, and a list
    line that isn't `- key: value`."""
    seen: set[str] = set()
    for number, line in config.section(home, "run preferences"):
        found = config.pref_of(line, number)
        if found is None:
            if line.lstrip(" \t")[:2] in ("- ", "* "):
                doc.warn("%s line %d, `%s`, isn't a `- key: value` line, so nothing reads it"
                         % (config.NAME, number, line.strip()), "write it as `- <setting>: <value>`, as %s does"
                         % TEMPLATE)
            continue
        if found.key in config.RETIRED:
            doc.warn("%s line %d, `- %s:`, is no longer read: %s" % (config.NAME, number, found.key,
                                                                      config.RETIRED[found.key]),
                     "delete the line (a council-init refresh does it)")
        elif found.key not in config.SETTINGS:
            doc.warn("%s line %d, `- %s:`, is not a setting the council reads" % (config.NAME, number, found.key),
                     "check its spelling against %s, or move a note out of ## Run preferences" % TEMPLATE)
        elif found.key in seen:
            doc.warn("%s line %d writes `- %s:` again; only the first line counts" % (config.NAME, number, found.key),
                     "keep one `- %s:` line" % found.key)
        seen.add(found.key)


def map_table(doc: Doctor) -> None:
    """A map with no `## One way per job` table: the plan check can't check a task's Owner against it."""
    home = where.native(doc.home)
    if map_file.path(home).is_file() and map_file.read(home) is None:
        doc.warn("%s has no `%s` table: it names the one owner and the one way of each recurring job, which the plan "
                 "check holds a task's Owner to and a builder's orders cite; without it that check is skipped"
                 % (map_file.NAME, map_file.TABLE),
                 "a council-init refresh adds it (references/templates/%s shows its shape)" % map_file.NAME)
