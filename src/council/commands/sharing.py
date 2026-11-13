"""council sharing [just-me|team]: who sees the council — the team's, committed with the project, or the
user's alone, kept out of git and out of anything teammates read (D16)."""
from __future__ import annotations

import os
import re
from typing import Pattern

from council import git
from council.commands import cli
from council.records import config, home as where
from council.records import sharing as setting

# The marked blocks "just me" takes out or puts in: council-init's note in CLAUDE.md / AGENTS.md (under
# its older name too), and the council's lines in git's own exclude list.
NOTE_BEGIN = re.compile(rb"^[ \t]*<!-- (small|ultra)-council:begin -->")    # no end anchor: a CRLF line too
NOTE_END = re.compile(rb"^[ \t]*<!-- (small|ultra)-council:end -->")
EXCL_BEGIN = "# small-council:begin (just me: the council stays on this machine; council sharing team removes this)"
EXCL_END = "# small-council:end"
EXCL_BEGIN_LINE = re.compile(rb"^# small-council:begin")
EXCL_END_LINE = re.compile(rb"^# small-council:end")
NOTES = ("CLAUDE.md", "AGENTS.md")
CONFIG_FILE = ".council/" + config.NAME
# without_block's answers, as the helper's drop_block returned them.
REMOVED, NO_BLOCK, UNREADABLE, UNENDED, EMPTIED = 0, 1, 2, 3, 5


def main(args: cli.Args, words: list[str]) -> int:
    """council sharing shows the setting and what it needs; sharing just-me|team switches it."""
    cli.takes_flags(args, "sharing")
    if args.value("run"):
        raise cli.Refusal("sharing is the whole council's setting; it does not take --run")
    first = words[0] if words else ""
    if first == "":
        show(where.council_home())
    elif first in ("just-me", "team"):
        if len(words) != 1:
            cli.no_words("sharing " + first, words[1:])
        switch(where.council_home(), first)
    else:
        raise cli.Refusal("usage: council sharing [just-me|team]")
    return 0


def show(home: str) -> None:
    """The setting, and for just me each thing it needs, done or not yet with its fix."""
    root = os.path.dirname(home)
    if setting.sharing(home) == "just me":
        cli.say("sharing: just me — the council stays on this machine (council.config.md says so)")
        for done, what, fix in rows(home):
            if done:
                cli.say("- ok: " + what)
            else:
                cli.say("- NOT YET: " + what)
                cli.say("  Fix: " + fix)
        return
    why = "council.config.md says so"
    if not setting.has_sharing(home):
        why = "the default: council.config.md has no sharing line"
    cli.say("sharing: team (%s) — .council/ is committed with the project, and the Small Council note in "
            "CLAUDE.md points teammates' sessions at it" % why)
    source = ignored_by(root)
    if source:
        cli.say("- but git ignores .council/ (%s), so none of it is shared even so; if that is on purpose, "
                "say so: council sharing just-me" % source)
    cli.say("- To keep the council to yourself: council sharing just-me")


def rows(home: str) -> list[tuple[bool, str, str]]:
    """What "just me" needs, one (done, what, fix) each; bin/council's sharing_rows, which doctor reads."""
    root = os.path.dirname(home)
    found: list[tuple[bool, str, str]] = []
    if git.text(root, "rev-parse", "--git-dir") is None:
        found.append((True, "not a git repository, so nothing here is committed or shared", ""))
    else:
        if git.text(root, "check-ignore", "-q", "--no-index", "--", CONFIG_FILE) is not None:
            found.append((True, "git ignores .council/ on this machine", ""))
        else:
            found.append((False, "sharing is just me, but git doesn't ignore .council/, so its files can be "
                          "committed for the team", "council sharing just-me"))
        tracked = tracked_count(root)
        if tracked:
            found.append((False, "%d council file(s) are still in git, so teammates have them (git keeps tracking "
                          "a file even once it is ignored)" % tracked, "git rm -r --cached .council, then commit: "
                          "your copies stay, and teammates see them removed"))
        else:
            found.append((True, "no council files in git", ""))
    noted = [name if folder == root else folder + "/" + name for folder in note_folders(root) for name in NOTES
             if has_note(_bytes(folder + "/" + name))]
    if noted:
        found.append((False, "the Small Council note is still in %s, so teammates' AI sessions read it"
                      % " and ".join(noted), "council sharing just-me takes it out"))
    else:
        found.append((True, "no Small Council note in CLAUDE.md or AGENTS.md", ""))
    return found


def switch(home: str, want: str) -> None:
    """council sharing just-me | team: switch who sees the council, and say what is left for the user."""
    root = os.path.dirname(home)
    label = "just me" if want == "just-me" else "team"
    if git.text(root, "rev-parse", "--git-dir") is not None:
        _exclude(root, want == "just-me")
    else:
        cli.say("not a git repository, so nothing here is committed or shared")
    if want == "just-me":
        for folder in note_folders(root):
            for name in NOTES:
                _take_note_out(root, folder, name)
    settings = config.path(home)
    if settings.is_file():
        try:
            data = settings.read_bytes()
            _write_in_place(str(settings), setting.with_sharing(data, label))
        except OSError:
            raise cli.Refusal("couldn't write %s/%s" % (home, config.NAME)) from None
        cli.say("council.config.md: - sharing: " + label)
    else:
        cli.say("no council.config.md yet: council-init writes '- sharing: %s' under ## Run preferences" % label)
    if want == "just-me":
        tracked = tracked_count(root)
        if tracked:
            cli.say("%d council file(s) are already in git, so teammates have them; git keeps tracking a file even "
                    "once it is ignored. To take them out of the shared project: git rm -r --cached .council, then "
                    "commit — your copies stay, and teammates see them removed." % tracked)
    else:
        cli.say("council-init adds the Small Council note to CLAUDE.md again (a refresh does it)")


def _exclude(root: str, just_me: bool) -> None:
    """Take the council's block out of git's own exclude list, and for just me write it again."""
    exclude = exclude_path(root)
    if not exclude:
        raise cli.Refusal("couldn't find git's exclude list for %s" % root)
    try:
        os.makedirs(os.path.dirname(exclude), exist_ok=True)
    except OSError:
        raise cli.Refusal("couldn't create %s" % os.path.dirname(exclude)) from None
    try:
        if not os.path.isfile(exclude):
            open(exclude, "wb").close()
    except OSError:
        raise cli.Refusal("couldn't write %s" % exclude) from None
    if drop(exclude, EXCL_BEGIN_LINE, EXCL_END_LINE) == UNENDED:
        raise cli.Refusal("%s has a '%s' line missing after its begin line: fix it by hand, then run this again"
                          % (exclude, EXCL_END))
    if just_me:
        _exclude_council(root, exclude)
        return
    source = ignored_by(root)
    if source:
        cli.say("the council's lines are gone from %s, but git still ignores .council/ (%s): take that line "
                "out to share it" % (exclude, source))
    else:
        cli.say("git sees .council/ again: commit it (git add .council) to share it with the team")


def _exclude_council(root: str, exclude: str) -> None:
    """Add the council's block to the exclude list, in the list's own line endings."""
    data = _bytes(exclude) or b""
    cr = "\r" if b"\r" in data else ""
    lines = [EXCL_BEGIN, "/.council/"]
    if git.text(root, "check-ignore", "-q", "--no-index", "--", ".claude/settings.local.json") is None:
        lines.append("/.claude/settings.local.json")
    text = (cr + "\n" if data and not data.endswith(b"\n") else "")
    text += "".join(line + cr + "\n" for line in lines + [EXCL_END])
    try:
        with open(exclude, "ab") as handle:
            handle.write(text.encode("utf-8"))
    except OSError:
        raise cli.Refusal("couldn't write %s" % exclude) from None
    cli.say("git now ignores .council/ (and your .claude/settings.local.json) on this machine only — %s is "
            "git's own list, never committed or pushed" % exclude)


def _take_note_out(root: str, folder: str, name: str) -> None:
    """Take council-init's note out of one CLAUDE.md or AGENTS.md, and say what happened."""
    shown = name if folder == root else folder + "/" + name
    committed = ""
    if git.text(folder, "cat-file", "-e", "HEAD:" + name) is not None \
            and has_note(git.output(folder, "show", "HEAD:" + name, allow_error=True)):
        committed = " — it was committed, so commit this change too (teammates see the note go)"
    answer = drop(folder + "/" + name, NOTE_BEGIN, NOTE_END)
    if answer == REMOVED:
        cli.say("took the Small Council note out of %s%s" % (shown, committed))
    elif answer == EMPTIED:
        try:
            os.remove(folder + "/" + name)
        except OSError:
            return
        cli.say("removed %s, which held only the Small Council note%s" % (shown, committed))
    elif answer == UNENDED:
        cli.say("%s has a Small Council begin line with no end line: nothing changed — take the note out by hand"
                % shown)
    elif answer == UNREADABLE:
        cli.say("couldn't rewrite %s: take the Small Council note out by hand" % shown)


def drop(file: str, begin: Pattern[bytes], end: Pattern[bytes]) -> int:
    """Take the marked block out of a file in place (so a CLAUDE.md that links to AGENTS.md stays a link);
    the answer is without_block's, or UNREADABLE when the file can't be read or written."""
    if not os.path.isfile(file):
        return NO_BLOCK
    try:
        with open(file, "rb") as handle:
            answer, data = without_block(handle.read(), begin, end)
        if answer in (REMOVED, EMPTIED):
            _write_in_place(file, data)
    except OSError:
        return UNREADABLE
    return answer


def without_block(data: bytes, begin: Pattern[bytes], end: Pattern[bytes]) -> tuple[int, bytes]:
    """The data with every block from a line matching begin to one matching end taken out, each other line
    kept as it was (its line ending too); where a cut leaves a blank line on both sides, one goes. The answer:
    REMOVED, NO_BLOCK, UNENDED (a begin with no end; nothing changed) or EMPTIED (only blank lines left)."""
    records = data.split(b"\n")
    if data.endswith(b"\n") or not data:
        records.pop()
    bare = [line[:-1] if line.endswith(b"\r") else line for line in records]
    blank = [re.fullmatch(rb"[ \t]*", line) is not None for line in bare]
    dropped: set[int] = set()
    cuts, start = [], -1
    for i, line in enumerate(bare):
        if start < 0 and begin.match(line):
            start = i
        if start >= 0:
            dropped.add(i)
            if end.match(line):
                cuts.append((start, i))
                start = -1
    if start >= 0:
        return UNENDED, data
    if not cuts:
        return NO_BLOCK, data
    for first, last in cuts:
        before = next((i for i in range(first - 1, -1, -1) if i not in dropped), None)
        after = next((i for i in range(last + 1, len(records)) if i not in dropped), None)
        if after is not None and blank[after] and (before is None or blank[before]):
            dropped.add(after)
        elif after is None and before is not None and blank[before]:
            dropped.add(before)
    kept = [i for i in range(len(records)) if i not in dropped]
    left = any(not blank[i] for i in kept)
    return (REMOVED if left else EMPTIED), b"".join(records[i] + b"\n" for i in kept)


def has_note(data: bytes | None) -> bool:
    """A line that opens council-init's note."""
    return any(NOTE_BEGIN.match(line) for line in (data or b"").split(b"\n"))


def note_folders(root: str) -> list[str]:
    """Where council-init may have written its note: the main checkout, and this working tree when the
    session sits in another one."""
    tree = where.this_tree()
    return [root] if tree == root else [root, tree]


def exclude_path(root: str) -> str:
    """git's own ignore list for this clone (info/exclude, one for every worktree): never committed, never
    pushed. '' outside git."""
    found = git.text(root, "rev-parse", "--git-path", "info/exclude") or ""
    if found and not (found.startswith("/") or re.match(r"[A-Za-z]:", found)):
        found = root + "/" + found
    return found


def ignored_by(root: str) -> str:
    """The ignore rule (source:line:pattern) that makes git ignore .council/, '' when none does."""
    found = git.text(root, "check-ignore", "-v", "--no-index", "--", CONFIG_FILE)
    return found.split("\t")[0] if found else ""


def tracked_count(root: str) -> int:
    """How many council files git tracks."""
    listed = git.text(root, "ls-files", "--", ".council")
    return len(listed.split("\n")) if listed else 0


def _bytes(file: str) -> bytes | None:
    try:
        with open(file, "rb") as handle:
            return handle.read()
    except OSError:
        return None


def _write_in_place(file: str, data: bytes) -> None:
    with open(file, "wb") as handle:
        handle.write(data)
