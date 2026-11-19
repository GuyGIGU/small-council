"""The permission rules council-init offers a project, kept here once: `council doctor permissions` prints them as the
block to paste into `.claude/settings.local.json`, and `council doctor` names the ones a project that has the
council's rules at all is missing (an older setup, before a command joined the list), so each of those stops on a
prompt no more.

Left off on purpose: `council gate`, `changed`, `cap` and `correct` (their prompts are the user's checkpoints).
`council patch` is on it whole: a builder saves, holds and takes up rounds in its own window, where a prompt would
stop the round, and the command moves only the diffs the run itself saved.
"""
from __future__ import annotations

import json
import os
import re

from council import git
from council.commands import cli
from council.commands.doctor import Doctor

FILES = (".claude/settings.local.json", ".claude/settings.json")
COMMANDS = ("run", "state", "seat", "index", "collect", "check", "ask", "prior", "memory", "ledger", "gates", "map",
            "doctor", "home", "fingerprint", "status", "evidence", "repair", "version", "context", "tree",
            "patch", "init", "book")
RULES = ("Edit(.council/**)",) + tuple("Bash(council %s:*)" % command for command in COMMANDS)
EVERY = re.compile(r"Bash\((bash \*bin/)?council(:\*| \*|\*)\)")      # one rule for every council command


def fallback(rule: str) -> str:
    """A rule in the form for a machine where `council` isn't on PATH: Bash(bash *bin/council run:*)."""
    return rule.replace("Bash(council ", "Bash(bash *bin/council ", 1)


def block() -> str:
    """The rules as the JSON block council-init offers."""
    return json.dumps({"permissions": {"allow": list(RULES)}}, indent=2)


def allowed(root: str) -> list[str] | None:
    """The project's allow rules from its Claude Code settings files; None when no file holds any council rule."""
    found: list[str] = []
    for name in FILES:
        try:
            with open(os.path.join(root, name), "rb") as handle:
                data = json.loads(handle.read().decode("utf-8-sig"))
        except (OSError, ValueError):
            continue
        allow = data.get("permissions", {}).get("allow", []) if isinstance(data, dict) else []
        found += [rule for rule in allow if isinstance(rule, str)] if isinstance(allow, list) else []
    return found if any("council" in rule for rule in found if rule.startswith("Bash(")) else None


def missing(rules: list[str]) -> list[str]:
    """Today's rules a project's allow list lacks, in the form the project uses (the fallback form when it has only
    that one)."""
    if any(EVERY.fullmatch(rule) for rule in rules):
        rules = rules + [rule for rule in RULES if rule.startswith("Bash(")]
    plain = any(rule.startswith("Bash(council ") for rule in rules)
    lacking = [rule for rule in RULES if rule not in rules and fallback(rule) not in rules]
    return lacking if plain else [fallback(rule) for rule in lacking]


def report(doc: Doctor) -> None:
    """A warning naming, as lines to paste, the council rules a project with some of them lacks."""
    root = git.text(".", "rev-parse", "--show-toplevel") or doc.root
    rules = allowed(root)
    lacking = missing(rules) if rules is not None else []
    if lacking:
        doc.warn("the project's Claude Code permission rules lack %d council rule(s) council-init offers today, so "
                 "each of those calls asks first: %s" % (len(lacking), ", ".join(lacking)),
                 "add to permissions.allow in .claude/settings.local.json: %s (council doctor permissions prints "
                 "the whole list)" % ", ".join('"%s"' % rule for rule in lacking))


def main(args: cli.Args, words: list[str]) -> int:
    """council doctor permissions: the whole list, as the block to paste."""
    cli.no_words("doctor permissions", words)
    cli.say(block())
    return 0
