"""council patch save <task> [<report>] [--base <rev>] · council patch show <task>: a build round's report and its
diff, checked against each other before the verifier sees either (references/run/builder-report.md).

save reads the round's report head (`<run>/report-<n>.md` unless another file is named), takes the round's diff
(from the run's last saved round, else the commit the run opened on, to the files on disk now) and refuses the
round — saving nothing — when the head can't be read, a fix gives no cause or one that hasn't earned a code
change, a test, assertion or document rule went with no word in Removed, or it is a third fix round in the same
files with no redesign. Otherwise it saves the patch, its record and the task's history, and names the files
outside the task's slice and the lines that look like a workaround, as questions for the verifier."""
from __future__ import annotations

import re
import time
from pathlib import Path

from council import diff, git
from council.commands import cli, gate_output, patch_checks, patch_history, resolve
from council.records import home as where
from council.records import map_file, paths, patches, report_head, tasks

USAGE = "usage: council patch save <task> [<report>] [--base <rev>] | patch show <task> [--run <folder>]"


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "patch", "base")
    if len(words) < 2 or words[0] not in ("save", "show") or len(words) > (3 if words[0] == "save" else 2):
        raise cli.Refusal(USAGE)
    found = re.fullmatch(r"(?:[Tt](?:ask-?)?)?([0-9]+)", words[1])
    if not found:
        raise cli.Refusal("patch %s takes a task number (3 or T3), not '%s'" % (words[0], words[1]))
    task, run = int(found.group(1)), resolve.run_folder(args)
    if words[0] == "show":
        lines = patch_history.lines(run, task)
        for line in lines or ["patch: task %d has no saved rounds — council patch save %d once its report is "
                              "written" % (task, task)]:
            cli.say(line)
        return 0
    report = Path(where.native(words[2])) if len(words) == 3 else report_head.report(run, task)
    return save(run, task, report, args.value("base"))


def _building(run: Path) -> None:
    mode, status = resolve.field(run, "mode"), resolve.field(run, "status")
    if mode != "council-implement":
        raise cli.Refusal("patch save is for a build's rounds (council-implement); this run is %s"
                          % (mode or "of no mode"))
    if status in ("complete", "abandoned"):
        raise cli.Refusal("this run is %s: a round is saved while the build is open — open a new run for more work"
                          % status)


def save(run: Path, task: int, report: Path, base: str) -> int:
    _building(run)
    head, wrong = report_head.read(report)
    if head is None:
        _refuse(task, ["the head of %s can't be read: %s" % (report.as_posix(), problem) for problem in wrong])
    top = resolve.field(run, "code-root") or where.this_tree()
    every, earlier = patches.rounds(run), patches.rounds(run, task)
    start = _start(run, top, base, every)
    tree = git.files_tree(top)
    if not tree:
        raise cli.Refusal("can't read the files in %s as a git tree — patch save needs the code root in git" % top)
    try:
        data = git.output(top, "diff", "--binary", "--no-color", "--no-ext-diff", "--no-textconv", "-M",
                          "--src-prefix=a/", "--dst-prefix=b/", start, tree, "--", ":(top)", ":(top,exclude).council")
    except git.GitError as failure:
        raise cli.Refusal("git can't diff %s against the files now (%s) — name a base: council patch save %d "
                          "--base <rev>" % (start[:12], failure, task)) from None
    found = diff.files(data.decode("utf-8", "surrogateescape"))
    files = [file.path for file in found]
    problems = _problems(run, task, head, earlier, found, files)
    if problems:
        _refuse(task, problems)
    out, cut = _slice(run, task, files)
    one = patches.Round(task, len(earlier) + 1, max([r.seq for r in every], default=0) + 1,
                        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), start, tree, files,
                        sum(len(f.added) for f in found), sum(len(f.removed) for f in found), head._asdict(),
                        out, [list(sign) for sign in patch_checks.signs(found)], cut)
    try:
        saved = patches.write(run, one, data)
        story = patches.write_history(run, task, patch_history.lines(run, task))
    except OSError as failure:
        raise cli.Refusal("can't write the round into %s (%s) — make the run folder writable, then save again"
                          % (patches.folder(run).as_posix(), failure)) from None
    patch_history.said(one, saved, story)
    return 0


def _refuse(task: int, problems: list[str]) -> None:
    for problem in problems:
        cli.warn("patch: " + problem)
    raise cli.Refusal("patch save refused, nothing saved: %d problem(s) above — fix the report or the change, then "
                      "council patch save %d" % (len(problems), task))


def _start(run: Path, top: str, base: str, every: list[patches.Round]) -> str:
    """The tree the round starts from: --base; else the run's last saved round; else the commit it opened on."""
    if base:
        return base
    if every:
        return every[-1].tree
    opened = resolve.field(run, "start-head")
    found = git.text(top, "rev-parse", "-q", "--verify", opened + "^{tree}") if opened else None
    if not found:
        raise cli.Refusal("this run has no commit it opened on (start-head), so the first round has no start — "
                          "name one: council patch save <task> --base <rev>")
    return found


def _problems(run: Path, task: int, head: report_head.Head, earlier: list[patches.Round],
              found: list[diff.File], files: list[str]) -> list[str]:
    """Why the round can't be saved, in order: its cause, what it removed unsaid, a third fix round."""
    out = []
    if earlier and not head.fix():
        out.append("round %d of task %d is a fix: name its cause — Cause: <what was wrong> · state: REPRODUCED "
                   "(or OBSERVED)" % (len(earlier) + 1, task))
    elif head.fix() and head.state not in report_head.EARNED and files:
        out.append("the cause is %s: it hasn't earned a code change. Measure it first — a probe whose output "
                   "settles it (references/run/repair-loop.md, Unknowns) — then write state: REPRODUCED or "
                   "OBSERVED; or take the change out and return NEEDS: <question>" % head.state)
    missing = patch_checks.unlisted(patch_checks.removals(found), head.removed, head.removed_none())
    for item in missing[:10]:
        out.append("%s removed, and the head's Removed line doesn't name it: %s:%d %s" % (
            item.kind, item.path, item.line, item.name or gate_output.clip(item.text, 70)))
    if missing:
        out.append("name each in Removed: (its file, a test by its name) with where it stands now, or put it back"
                   + (" — %d more not shown" % (len(missing) - 10) if len(missing) > 10 else ""))
    if len(earlier) >= 3:
        from council.commands import rounds    # datetime, only when a third fix round is possible (D34)
        refused = rounds.third_fix_round(run, task, [(r.files, r.head.get("redesign", ""), r.at) for r in earlier],
                                         files, head.redesign)
        out += [refused] if refused else []
    return out


def _slice(run: Path, task: int, files: list[str]) -> tuple[list[str], str]:
    """The changed files outside the task's slice, and where the slice came from (or why it was skipped): the
    plan the build records as input=, its task's Owner and Touches, and the map row its Owner names."""
    named = resolve.field(run, "input")
    if not named:
        return [], "skipped — the run records no input= plan (council state input=<plan>)"
    plan = Path(named) if Path(named).is_absolute() else Path(run).parent.parent.parent / named
    entry = next((t for t in tasks.read(paths.text_of(plan)) if t.number == task), None)
    if entry is None:
        return [], "skipped — %s has no task %d" % (named, task)
    owner = entry.rows.get("owner", "")
    cells = [owner, entry.rows.get("touches", "")]
    from council.commands import plan_tasks     # the plan check's own match of an Owner to a row
    for way in map_file.read(Path(run).parent.parent) or []:
        if plan_tasks.names_a_job(owner, [way.job]):
            cells += [way.owner, way.anchor]
    given = patch_checks.slice_paths(cells)
    if not given:
        return [], "skipped — task %d's Owner and Touches name no path" % task
    return patch_checks.outside(files, given), "%s, task %d: %s" % (named, task, ", ".join(given))
