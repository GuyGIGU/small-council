"""council run plan check and council run plan show. bin/council's state, seat, context build and doctor
run this same check (plan_check there); its rules are in plan_check.py."""
from __future__ import annotations

import os
import re
from pathlib import Path

from council.commands import cli, plan_check, resolve
from council.records import cells, config, models, plan, seats
from council.records import home as where

USAGE = "usage: council run plan [check|show]"
Key = plan_check.Key


def main(args: cli.Args, sub: str, words: list[str]) -> int:
    """council run plan [check|show] [--run <folder>]: a legacy run needs no plan; any other needs one."""
    cli.takes_flags(args, "run plan")
    if len(words) > 1:
        raise cli.Refusal(USAGE)
    run = resolve.run_folder(args)
    if not plan.path(run).is_file():
        if not resolve.field(run, "plan-schema"):
            cli.say("plan: legacy run · no %s required · %s" % (plan.NAME, run.name))
            return 0
        raise cli.Refusal("%s is missing from %s — restore it from references/templates/%s"
                          % (plan.NAME, run.name, plan.NAME))
    word = words[0] if words and words[0] else "check"
    quiet = os.environ.get("QUIET", "") == "1"         # bash's callers keep only the problems
    if word == "check":
        return check(run, quiet)
    if word == "show":
        if check(run, quiet):
            return 1
        for line in shown(whole(run)) + models.shown(models.models(where.council_home())):
            cli.say(line)
        return 0
    raise cli.Refusal(USAGE)


def check(run: Path, quiet: bool) -> int:
    """Print each problem and their count (exit 1), else the valid line unless quiet (exit 0)."""
    verdict = plan_check.judge(whole(run), settings(run, where.council_home()))
    for line in verdict.problems:
        cli.say(line)
    if verdict.problems:
        cli.say("plan: %d error(s) · %s" % (len(verdict.problems), plan.NAME))
        return 1
    if not quiet:
        cli.say(verdict.valid)
    return 0


def whole(run: Path) -> str:
    """The plan as awk reads it: every byte (bytes that aren't UTF-8 kept for the way out), no size limit,
    a byte-order mark kept."""
    def read(path: Path) -> str | None:
        try:
            return path.read_bytes().decode("utf-8", "surrogateescape")
        except OSError:
            return None
    return plan.text(run, read)


def settings(run: Path, home: str) -> plan_check.Settings:
    """The run's settings for the check, from its state, its allowances and the project's config."""
    routing, full_go = config.seat_models(home), True
    if resolve.field(run, "status") in ("complete", "abandoned"):
        routing = "closed"
    else:
        from council.commands import rounds          # datetime: only an open run needs a decision read
        opened = resolve.field(run, "opened")
        since = opened[:-3] if re.search(r":[0-9][0-9]\Z", opened) else opened
        full_go = rounds.decisions_since(run, since) > 0
    return plan_check.Settings(run.name, resolve.field(run, "mode"), config.agent_cap(home), seats.allowed_until(run),
                    routing, full_go, models.models(home))


def shown(content: str) -> list[str]:
    """council run plan show's summary of a valid plan: its run, its budget and each considered seat. It reads
    the rows as written, untrimmed, the last of a repeated row winning."""
    v: dict[Key, str] = {}
    why: dict[Key, str] = {}
    order: list[str] = []
    routed = False
    for line in cells.lines_of(content):
        parts = line.split("\t")
        if line.startswith("#") or len(parts) != 5:
            continue
        key = (parts[0], parts[1], parts[2])
        v[key], why[key] = parts[3], parts[4]
        if parts[0] == "seat" and parts[2] == "disposition":
            order.append(parts[1])
        routed = routed or (parts[0] == "seat" and parts[2] == "model" and parts[3] != "inherit")

    def run(kind: str, field: str) -> str:
        return v.get((kind, "run", field), "")
    lines = ["Run plan — " + run("run", "id"),
             "  mode: %s · size: %s" % (run("run", "mode"), run("run", "size")),
             "  risk: %s · complexity: %s · uncertainty: %s"
             % (run("assessment", "risk"), run("assessment", "complexity"), run("assessment", "uncertainty")),
             "  budget: %s tokens · %s agents · verification: %s"
             % (run("budget", "estimated-tokens"), run("budget", "agent-cap"), run("verification", "level"))]
    if run("budget", "token-ceiling"):
        lines.append("  owner ceiling: %s tokens" % run("budget", "token-ceiling"))
    if run("budget", "chair-tokens"):
        lines.append("  the Chair's own share: %s tokens (agents are compared with the rest)"
                     % run("budget", "chair-tokens"))
    lines.append("  seats:")
    lines += [seat_line(ident, v, why, routed) for ident in order]
    return lines


def seat_line(ident: str, v: dict[Key, str], why: dict[Key, str], routed: bool) -> str:
    """'    selected — security (worker) · context focused · 12 tool calls — <why>'; the model only once
    some seat asks for another."""
    disposition = v.get(("seat", ident, "disposition"), "")
    line = "    %s — %s (%s)" % (disposition, ident, v.get(("seat", ident, "role"), ""))
    if disposition == "selected":
        line += " · context " + v.get(("context", ident, "level"), "")
        for key, words in ((("budget", ident, "tool-calls"), " · %s tool calls"),
                           (("budget", ident, "agent-runs"), " · %s agent runs"),
                           (("seat", ident, "purpose"), " · purpose %s")):
            if v.get(key, ""):
                line += words % v[key]
        if routed:
            line += " · model " + (v.get(("seat", ident, "model"), "") or "inherit")
    return line + " — " + why.get(("seat", ident, "disposition"), "")
