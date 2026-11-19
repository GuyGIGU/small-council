"""council context build task-<n>: a build task's orders, generated from the run's files and printed — never
written (docs/design/task-tree.md, section 2). Six parts, in order: the task, its owner, the hard constraints and
memory in scope, the user's decisions and the standing rules, earlier tasks' changes to the same files, and what was
left out. The whole pack stays within CEILING bytes: while it is over, the last of parts 1-5 still in it is dropped
whole and named under Left out, which is never dropped. The Chair hands the printed text to the builder."""
from __future__ import annotations

import os
import re
from pathlib import Path

from council.commands import cli, gate_list, patch_checks, resolve, task_slice
from council.records import config, gate_table, map_file, patches, request, state, tasks
from council.records import home as where

CEILING = 8000     # bytes of the whole printed pack, UTF-8, its last line included
NAMES = ("The task", "Owner", "Hard constraints and memory", "Rulings and standing rules",
         "Earlier changes to these files")
USAGE = "usage: council context build task-<n> [--run <folder>] — a build task's orders, printed"
BUILDER_PAGE = "references/run/builder-rules.md"     # the builder's one page (D56)
PLUGIN_REF = re.compile(r"(?<![\w./-])references/[\w./-]*\w")    # a path in a Ref cell that may be the plugin's
NEVER = ("- Never in a pack: the plan's other tasks, the code itself, seat files, and the Chair's Ruling: lines "
         "(they sit in the build log, which nothing reads).")


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "context")
    if len(words) != 2 or words[0] != "build":
        raise cli.Refusal(USAGE)
    number = tasks.number(words[1])
    if number is None:
        raise cli.Refusal("context build takes task-<n> (task-3, T3 or 3), not '%s' — council context build "
                          "task-<n>" % words[1])
    run = resolve.run_folder(args)
    named, content = task_slice.plan(run, "context build")
    found = task_slice.cut(run, named, content, number)
    if found.task is None:
        listed = ", ".join("task-%d" % t.number for t in tasks.read(content))
        raise cli.Refusal("%s has no task %d — %s" % (
            named, number, "its tasks: %s; council context build <one of them>" % listed if listed else
            "its ## Task Sequence lists none; write the plan's tasks first"))
    held = patches.held(run, number)
    from council.commands import book    # the book's first three pages, read before anything else (D52)
    first = book.one_line(Path(run).parent.parent.as_posix())
    heading = ["# Task pack — task %d · %s" % (number, named), first] + _where(run) + [""] + [
        "Held: %s — the edits task %d's last builder left in no round, taken off the files; put them back before the "
        "first edit: council patch apply %d --held" % (held.as_posix(), number, number), ""] * held.is_file()
    cli.say_all(fit(heading, parts(run, found)))
    return 0


def _where(run: Path) -> list[str]:
    """Under the heading: the run folder as the helper prints a run, the code root, and what the task's next round
    is judged against — what council patch save diffs it from with no --base."""
    from council.commands import patch    # patch save's own start, once a pack is built
    last, start = patch.since(run, patches.rounds(run))
    if last:
        against = "the last saved round's tree, %s — task %d round %d (%s.patch)" % (
            start[:12], last.task, last.round, patches.name(last.task, last.round))
    else:
        against = ("the commit the run opened on, %s" % start[:12] if start else
                   "nothing yet: the run records no commit it opened on (start-head) — council patch save <task> "
                   "--base <rev> names one")
    return ["Run folder: %s" % Path(run).as_posix(), "Code root: %s" % (resolve.field(run, "code-root") or "here"),
            "Judged against: %s" % against]


def parts(run: Path, found: task_slice.Slice) -> list[list[str]]:
    """Parts 1-5, each its `## ` heading, its lines and a blank line."""
    return [task(run, found.task), owner(found), constraints(run, found), rulings(run, found.task.number),
            earlier(run, found)]


def fit(heading: list[str], given: list[list[str]]) -> list[str]:
    """The pack's lines within CEILING: parts dropped whole from the end, each named under Left out (part 6, whose
    bytes come first), and the closing count. The heading and part 6 alone are the smallest pack."""
    kept = list(given)
    while True:
        dropped = list(NAMES[len(kept):len(given)])
        body = heading + [line for part in kept for line in part] + left_out(dropped)
        closing = count(body, dropped)
        if size(body + [closing]) <= CEILING or not kept:
            return body + [closing]
        kept.pop()


def left_out(dropped: list[str]) -> list[str]:
    out = ["## Left out"]
    out += ["- %s (part %d): over the %d-byte ceiling, dropped whole" % (name, NAMES.index(name) + 1, CEILING)
            for name in dropped]
    return out + [NEVER]


def size(lines: list[str]) -> int:
    """The bytes the lines take printed, each with its newline."""
    return sum(len(line.encode("utf-8", "surrogateescape")) + 1 for line in lines)


def count(body: list[str], dropped: list[str]) -> str:
    """The last line: the pack's own bytes, this line's included, and what was left out."""
    line, last = "", None
    while line != last:
        last = line
        line = "pack: %d bytes of %d; left out: %s" % (size(body + [line]), CEILING, ", ".join(dropped) or "nothing")
    return line


def task(run: Path, entry: tasks.Task) -> list[str]:
    rows = entry.rows
    out = ["## " + NAMES[0], "Task %d: %s" % (entry.number, entry.title),
           "Serves: %s" % rows.get("serves", "(the plan gives no Serves row)"),
           "Done when: %s" % rows.get("done when", "(the plan gives no Done when row)")]
    facts = tasks.facts(rows.get("rests on"))
    if facts is None:
        out.append("Rests on: (the plan gives no Rests on row)")
    elif not facts:
        out.append("Rests on: nothing")
    else:
        out.append("Rests on:")
        out += ["- %s (%s)" % (f.text, (f.state or "no evidence state") + (", outside" if f.outside else ""))
                for f in facts]
    from council.commands import tree     # council tree's own match of a seat to a task
    out += ["Stopped earlier: %s" % note for note in tree.seat_needs(run, {entry.number})[0].get(entry.number, [])]
    return out + [""]


def _way(way: map_file.Way) -> str:
    return "%s · %s · %s · %s" % (way.job, way.owner, way.way, way.anchor)


def owner(found: task_slice.Slice) -> list[str]:
    rows = found.task.rows
    out = ["## " + NAMES[1], "Owner: %s" % rows.get("owner", "(the plan gives no Owner row)")]
    if found.ways is None:
        out.append("The one way: the map has no one-way-per-job table")
    elif found.owned:
        out += ["The one way: %s" % _way(way) for way in found.owned]
    else:
        out.append("The one way: %s" % ("none — the task adds a New way, a ruling for the user"
                                        if tasks.kind(rows.get("owner")) == "new" else "the Owner names no map row"))
    out.append("Slice: %s" % (", ".join(found.paths) or "the Owner and Touches name no path"))
    called = _called(found)
    out += (["Other map rows inside Touches:"] + ["- " + _way(way) for way in called]) if called else []
    out.append("Must not touch: anything outside the slice — a change outside these paths is named at council "
               "patch save, for the verifier.")
    if rows.get("ref"):
        out.append("Ref: %s — read it there; it is not copied here" % plugin_paths(rows["ref"]))
    if rows.get("domain"):
        out.append("Domain: %s" % rows["domain"])
    return out + [""]


def plugin_paths(cell: str) -> str:
    """A Ref cell with each references/… path that names a file of the plugin's written whole."""
    root = where.plugin_root()
    def whole(found: re.Match) -> str:
        path = root + "/" + found.group(0)
        return path if os.path.isfile(where.native(path)) else found.group(0)
    return PLUGIN_REF.sub(whole, cell)


def _called(found: task_slice.Slice) -> list:
    """The map's other rows whose owner or anchor path lies inside the task's Touches."""
    touches = task_slice.paths_in([found.task.rows.get("touches", "")])
    if not touches:
        return []
    def inside(way: map_file.Way) -> bool:
        given = task_slice.paths_in([way.owner, way.anchor])
        return len(patch_checks.outside(given, touches)) < len(given)
    return [way for way in found.ways or [] if way not in found.owned and inside(way)]


def constraints(run: Path, found: task_slice.Slice) -> list[str]:
    home = Path(run).parent.parent
    rules = config.hard_rules(home)
    out = ["## " + NAMES[2]]
    out += (["Hard rules (the config's %s, word for word):" % config.HARD_RULES] + rules) if rules else \
        ["Hard rules: the config has none"]
    out.append("Constraints: %s" % (found.task.rows.get("constraints") or "the task gives none"))
    out.append("Memory in scope (council memory select over the slice):")
    return out + _memory(run, found.paths) + [""]


def _memory(run: Path, given: list[str]) -> list[str]:
    """council memory select's own lines for the slice's paths (a folder on disk keyed as one, as select keys
    it); what it leaves out goes on stderr, as select says it."""
    from council.commands import memory, memory_select
    try:
        found = memory.load()
    except cli.Refusal as refusal:
        return ["memory: none read — %s" % refusal]
    top = resolve.field(run, "code-root") or where.this_tree()
    keys = [k + "/" if not k.endswith("/") and os.path.isdir(where.native(top + "/" + k)) else k for k in given]
    out, said = memory_select.Selection(keys, top).lines(found.served)
    for line in said:
        cli.warn(line)
    return out


def rulings(run: Path, number: int) -> list[str]:
    home = Path(run).parent.parent
    out = ["## " + NAMES[3], "The user's decisions in this run (council state decision=), the whole run's and task "
           "%d's own:" % number]
    out += ["- " + entry for entry in state.decisions_for(state.text(run), number)] or ["- none yet"]
    asked = request.asked(run)
    later = asked.later if asked else []
    source = request.ASK + (" and the request it continues, %s" % asked.filed.name if asked and asked.filed else "")
    out += ["Later, in the user's words (%s, ## Later):" % source] + (later or ["- none"])
    rows = gate_table.gates(home)
    out += ["Gates (the config's Gates table):"] + (["- " + gate_list.line(row) for row in rows] or ["- none"])
    seconds, raw = config.gate_time_limit(home)
    out.append("Gate time limit: %s" % (
        "%s (the config's - gate time limit:)" % raw if seconds else
        "'%s' is not a time, so the defaults hold (council help, council gate … --timeout)" % raw if raw else
        "not set in the config: the defaults hold (council help, council gate … --timeout)"))
    root = where.plugin_root()
    out.append("Proof: council gate before-%d, then after-%d, one command in both — the builder's page, Proof" % (
        number, number))
    out.append("The builder's page: %s/%s — your steps, proof, report and stops on one page; read it before the "
               "first edit" % (root, BUILDER_PAGE))
    return out + [""]


def earlier(run: Path, found: task_slice.Slice) -> list[str]:
    """Other tasks' saved rounds on the slice's files, with their causes; first, on a fix round, where the task's own
    rounds are told (patches/T<n>.md) — a path, never the file's text."""
    every, number = patches.rounds(run), found.task.number
    own = sum(one.task == number for one in every)
    history = (patches.folder(run) / ("T%d.md" % number)).as_posix()
    out = ["## " + NAMES[4]] + ["- task %d's own history, %d saved round(s): %s — read it before the fix; it is not "
                                "copied here" % (number, own, history)] * bool(own)
    if not found.paths:
        return out + ["- none to compare: the slice names no path", ""]
    others = len(out)
    for one in every:
        met = [path for path in one.files if path not in patch_checks.outside(one.files, found.paths)]
        if one.task == number or not met:
            continue
        cause = one.head.get("cause", "")
        out.append("- task %d round %d (%s.patch): %s · Cause: %s" % (
            one.task, one.round, patches.name(one.task, one.round), ", ".join(met),
            "%s (%s)" % (cause, one.head["state"]) if one.head.get("state") else "none, a first build"))
    return out + ([] if len(out) > others else ["- none: no other task's saved round touched these paths"]) + [""]
