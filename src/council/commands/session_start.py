"""council run session-start: the SessionStart hook's words; any fault ends it quietly with exit 0 (D20)."""
from __future__ import annotations

import contextlib
import os
import re
import stat
import sys
import time

from council import git
from council.commands import cli, doctor_hooks
from council.records import hook_marks, memory, paths, runs, sharing, state
from council.records import home as where

MORE = "were running when that session ended (they are gone — re-dispatch each once if you resume)"
RUN_LINES = {   # one open run of this tree's or this session's, by what it is to this session
    "paused": ("- PAUSED COUNCIL RUN: {seen}. Resume it only when the user asks: council run resume --run {name}, then "
               "re-invoke the {skill} skill and read its session-state.md.{away}"),
    "driving": ("- CONTEXT WAS JUST COMPACTED DURING A COUNCIL RUN: {where}). Re-invoke the {skill} skill (it loads "
                "context-core), read {dir}/session-state.md (and ask.md, if present), {redo}, and continue from there."
                "{seats} Do not restart, do not re-dispatch seats that are running or done (wait for their "
                "notifications), do not skip the completeness check.{runflag}"),
    "alongside": ("- Also open {at}, opened alongside by this same session: {name} ({skill}, phase {phase}). It is "
                  "yours too — pass --run {name} to every council command meant for it."),
    "not mine": ("- Also open on this working tree, not this session's run: {name} ({skill}, phase {phase}). Leave it "
                 "unless the user asks."),
    "live after clear": (
        "- COUNCIL RUN OPEN, updated in the last 2 hours by another session id: {seen}.{seats} If this window was "
        "driving it before /clear, carry on: council run resume --run {name}, then re-invoke the {skill} skill and "
        "read its session-state.md; its workers died with the old session, so run council collect to see which files "
        "exist, mark the rest failed (council seat <slug> failed note=\"interrupted\") and re-dispatch each once. "
        "Otherwise it may still be live in another session: leave it, and don't resume it, re-dispatch its seats or "
        "close it unless the user says so.{runflag}"),
    "live": ("- COUNCIL RUN OPEN, updated in the last 2 hours by another session: {seen}. It may still be running in "
             "that session: leave it, and don't resume it, re-dispatch its seats or close it. If the user says that "
             "session has ended: council run resume --run {name}, then re-invoke the {skill} skill.{runflag}"),
    "unfinished": ("- UNFINISHED COUNCIL RUN: {seen}.{seats} Before new council work, ask the user whether to resume "
                   "it (council run resume --run {name}, then re-invoke the {skill} skill and read its "
                   "session-state.md) or close it (council run close --run {name} --status abandoned).{runflag}"),
}


def main(args: cli.Args, words: list[str]) -> int:
    cli.takes_flags(args, "run session-start")
    cli.no_words("run session-start", words)
    with contextlib.suppress(Exception):      # the hook lets the session through on its own fault
        _start(sys.stdin.buffer.read().replace(b"\0", b"").rstrip(b"\n").decode("utf-8", "surrogateescape"))
    return 0


def _json(raw: str, key: str) -> str:
    """The first line's `"key": "value"` (the last on that line), as the hook's sed took it: no unescaping."""
    for line in raw.split("\n"):
        found = re.match(r'.*"%s"[ \t\r\f\v]*:[ \t\r\f\v]*"([^"]*)"' % key, line)
        if found:
            return found.group(1)
    return ""


def _start(raw: str) -> None:
    event = next((e for e in ("compact", "clear") if '"source":"%s"' % e in raw or '"source": "%s"' % e in raw), "")
    sid = _json(raw, "session_id")
    scwd = _json(raw, "cwd").replace("\\/", "/").replace("\\\\", "\\")
    if re.match(r"[A-Za-z]:\\", scwd):
        scwd = scwd.replace("\\", "/")
    hook_marks.put(sid, "session-start")
    project = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if project:
        os.chdir(where.native(project))
        os.environ["PWD"] = os.path.normpath(os.path.join(os.environ.get("PWD", ""), project))   # as bash's cd sets it
    home = where.council_home()
    if not os.path.isdir(where.native(home)):
        return
    root, top = home[:home.rfind("/")], where.this_tree()
    listed = [runs.Listed(*(cell or "-" for cell in row)) for row in runs.listing(home, 100000, "open")]
    if listed and scwd and os.path.isdir(where.native(scwd)):
        _worktree(listed, scwd, root)
    _banner(home, sid)
    _map(home)
    _memory(home)
    if listed:
        _runs(listed, top, sid, event)


def _worktree(listed: list[runs.Listed], scwd: str, root: str) -> None:
    """In a linked worktree, an in-progress run whose code is elsewhere can't be driven here: said first."""
    scwd = where.native(scwd)
    dirs = [git.text(scwd, "rev-parse", flag) for flag in ("--git-dir", "--git-common-dir")]
    if not all(dirs) or len({os.path.realpath(os.path.join(scwd, d)) for d in dirs}) < 2:
        return
    wt = git.text(scwd, "rev-parse", "--show-toplevel") or ""
    away = next((r for r in listed if r.status == "in-progress" and not runs.here(r.code_root, wt)
                 and os.path.isdir(where.native(r.code_root))), None)
    if away:
        cli.say("[Small Council] This session runs in a linked worktree (%s). Claude Code may refuse edits outside it, "
                "and run %s's code is in %s. To drive that run, start a session in %s with the worktree option off."
                % (wt, _name(away.folder), away.code_root, root))


def _banner(home: str, sid: str) -> None:
    if not os.path.isfile(where.native(home + "/council.config.md")):
        cli.say("[Small Council] %s holds council results, but the council isn't set up here (No council.config.md "
                "yet). council-init sets it up for reviews, plans, builds and research; a post-game needs none." % home)
        return
    cli.say("[Small Council] Council-enabled project. Council home: %s. %s"
            % (home, doctor_hooks.count_line(sid) if sid else ""))
    cli.say("- Substantial work? Check for a council mode first (council-review, council-plan, council-implement, "
            "council-research, council-postgame, spec-writer, test-architect). Propose it with its size and estimated "
            "cost, and wait for a go-ahead before any multi-agent run.")
    cli.say("- The `council` helper does the bookkeeping (`council run status`, `council doctor`). It is a bash "
            "script: run it in the Bash tool (Git Bash on Windows), never from PowerShell. Call it as a plain `council "
            "<command>`, never piped (a hook refuses `| head`, `| tail` and `| grep`: redirect it to a file and read "
            "that) and never through a shell variable or a full path: permission rules match the command text. Only if "
            "`command -v council` fails, write out bash \"%s/bin/council\" <command> each time."
            % os.environ.get("CLAUDE_PLUGIN_ROOT", ""))
    if sharing.sharing(home) == "just me":
        cli.say("- Just me: this council is the user's alone. Git ignores .council/ and no project file mentions the "
                "council, so teammates never meet it. Keep it that way: commit messages, PR text, code comments and "
                "shared docs never cite council runs, finding ids or .council/ paths (teammates can't open them) — say "
                "the reason in plain words.")


def _map(home: str) -> None:
    text = _text(home + "/map.md")
    if text is None:
        return
    sha = next((m.group(1) for m in (re.match(r"map-commit:[ \t\r\f\v]*([0-9a-fA-F]{7,40})", line)
                                     for line in text.split("\n")) if m), "")
    behind, lost = "", sha and git.text(".", "cat-file", "-e", sha + "^{commit}") is None
    if sha and not lost:
        behind = git.text(".", "rev-list", "--count", sha + "..HEAD") or ""
    lost = lost and git.text(".", "rev-parse", "--git-dir") is not None
    said = ("- Orientation: %s/map.md lists where things live, hot spots and vocabulary — check it before exploring "
            "unfamiliar code" % home)
    if lost:
        said += (" (it was built on a commit that is no longer in this repo's history: trust its structure, verify "
                 "details)")
    elif behind.isdigit() and int(behind) > 0:
        said += " (%s commits behind HEAD: trust its structure, verify details)" % behind
    cli.say(said + ".")


def _memory(home: str) -> None:
    """The memory file every council command reads, the config's `- conventions:` path included."""
    found = memory.locate(home)
    if not os.path.isfile(where.native(found.path)):
        return
    cli.say("- Settled decisions: %s (respect them; never re-litigate)." % found.path)
    if found.alt:
        cli.say("- A second memory file, %s, holds %d entries the council never reads: tell the user, and merge them "
                "or point the '- conventions:' line under ## Memory in council.config.md at the one to keep."
                % (found.alt, found.alt_n))
    pending = memory.proposals(home)
    if pending:
        cli.say("- %d memory proposal(s) in that file await the user's yes/no. Raise them at a natural pause."
                % pending)


def _runs(listed: list[runs.Listed], top: str, sid: str, event: str) -> str:
    """Every open run: this tree's and this session's described (at most 5), the rest summed up."""
    mine, others, gone, n_other, n_gone = [], [], [], 0, 0
    for r in listed:
        if runs.here(r.code_root, top):
            mine.append((r, "-"))
        elif os.path.isdir(where.native(r.code_root)) and sid and r.session == sid:
            mine.append((r, r.code_root))     # its code is in a linked worktree: still this session's own run
        elif os.path.isdir(where.native(r.code_root)):
            n_other += 1
            if n_other <= 5:
                others.append("%s (%s, phase %s, code root %s)" % (_name(r.folder), runs.skill(r.mode),
                                                                    "?" if r.phase == "-" else r.phase, r.code_root))
        else:
            n_gone += 1
            if n_gone <= 5:
                gone.append("%s (code root %s)" % (_name(r.folder), r.code_root))
    here_n = sum(1 for _, at in mine if at == "-")
    driving = _driving(mine, sid) if event == "compact" else ""
    ordered = sorted(mine, key=lambda m: 0 if m[0].folder == driving else 1 if m[0].status == "in-progress" else 2)
    for r, at in ordered[:5]:
        cli.say(_described(r, at, sid, event, driving, here_n))
    if ordered:
        cli.say("- If the user asks how a run is going: council status --run <name>. With a show_widget tool, call "
                "its read_me first, then pass the output of council status --widget --run <name> to it verbatim (a "
                "snapshot card, not live); otherwise relay the text.")
    more = ordered[5:]
    if more:
        listed_more = ", ".join("%s (%s)" % (_name(r.folder), r.status) for r, _ in more[:5])
        listed_more += ", …" if len(more) > 5 else ""
        cli.say("- And %d more open on this working tree: %s — council run status lists them all. Leave them unless "
                "the user asks." % (len(more), listed_more))
    _elsewhere(others, n_other, gone, n_gone)
    return driving


def _driving(mine: list, sid: str) -> str:
    """The run this session drove: by session id, else the first in progress touched in the last 12 hours."""
    fallback = ""
    for r, _ in mine:
        rsid = "" if r.session == "-" else r.session
        if r.status != "in-progress":
            continue
        if sid and rsid == sid:
            return r.folder
        if not fallback and (not rsid or not sid) and _recent(r.folder + "/" + state.NAME, 720):
            fallback = r.folder
    return fallback


def _described(r: runs.Listed, at: str, sid: str, event: str, driving: str, here_n: int) -> str:
    """The line for one of this tree's (or this session's) open runs: which of RUN_LINES, filled in."""
    phase, updated, rsid = ("" if v == "-" else v for v in (r.phase, r.updated, r.session))
    said = {"dir": r.folder, "name": _name(r.folder), "skill": runs.skill(r.mode), "phase": phase or "?",
            "where": "%s (%s, phase: %s" % (r.folder, runs.skill(r.mode), phase or "unknown"), "seats": ""}
    said["seen"] = said["where"] + ", updated: %s)" % (updated or "unknown")
    said["away"] = "" if at == "-" else (" Its code is in another working tree, %s: work there, and pass --run %s to "
                                         "every council command for it." % (at, said["name"]))
    said["runflag"] = said["away"] or (" Several runs are open on this tree: pass --run %s to every council command "
                                       "for this one." % said["name"] if here_n > 1 else "")
    said["at"] = "in another working tree (%s)" % at if said["away"] else "on this working tree"
    said["redo"] = ("re-read its build loop and the build log" if phase == "build"
                    else "re-read the doctrine for that phase")
    if r.status == "paused":
        kind = "paused"
    elif event == "compact":
        kind = "driving" if r.folder == driving else "alongside" if sid and rsid == sid else "not mine"
    elif rsid and rsid != sid and _recent(r.folder, 120):
        kind = "live after clear" if event == "clear" else "live"
    else:
        kind = "unfinished"
    if kind in ("driving", "live after clear", "unfinished"):
        working = MORE if kind == "unfinished" and event != "clear" else "still working"
        seats = runs.seat_summary(where.native(r.folder), working)
        said["seats"] = " Seats — %s." % seats if seats else ""
    return RUN_LINES[kind].format(**said)


def _elsewhere(others: list[str], n_other: int, gone: list[str], n_gone: int) -> None:
    """Other trees' runs, summed up, and runs whose working tree no longer exists."""
    said = "; ".join(others) + ("; and %d more" % (n_other - 5) if n_other > 5 else "")
    if n_other == 1:
        cli.say("- Another council run is open in a different working tree: %s. Leave it alone." % said)
    elif n_other > 1:
        cli.say("- %d council runs are open in different working trees: %s. Leave them alone (council run status lists "
                "them)." % (n_other, said))
    said = ", ".join(gone) + (", and %d more" % (n_gone - 5) if n_gone > 5 else "")
    if n_gone == 1:
        cli.say("- A council run was left open in a working tree that no longer exists: %s. Ask the user, then close "
                "it: council run close --run %s --status abandoned." % (said, said.split(" ")[0]))
    elif n_gone > 1:
        cli.say("- %d council runs were left open in a working tree that no longer exists: %s. Ask the user, then "
                "close each: council run close --run <name> --status abandoned." % (n_gone, said))


def _recent(path: str, minutes: int) -> bool:
    """The hook's find -mmin -<minutes>: the file changed that recently, or any regular file under the folder."""
    native, limit = where.native(path), time.time() - minutes * 60
    if not os.path.isdir(native):
        return os.path.lexists(native) and os.lstat(native).st_mtime > limit
    for top, _, names in os.walk(native):
        for name in names:
            info = os.lstat(os.path.join(top, name))
            if stat.S_ISREG(info.st_mode) and info.st_mtime > limit:
                return True
    return False


def _text(path: str) -> str | None:
    """A file's text (its bytes kept); None when it is missing or unreadable."""
    data = paths.contents(where.native(path))
    return None if data is None else data.decode("utf-8", "surrogateescape")


def _name(folder: str) -> str:
    return folder.rsplit("/", 1)[-1]
