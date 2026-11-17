"""Whether `gate --all` takes a gate's last green in the run instead of running it again, and the words for it: a
green on the very files on disk now (#68), or one on other files when nothing under the paths its Covers cell names
has changed since (#47). One rule, asked by `gate --all` (gate_set) and the receipt (receipt). A green taken on
other files is never a fresh pass: the receipt names it `not rerun`, with this reason."""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from council import git
from council.commands import gate_run
from council.records import gate_table, gates, verdicts


class Taken(NamedTuple):
    """A green that stands for the files on disk now."""

    green: verdicts.Green
    same: bool          # on this very tree; else nothing under the row's Covers paths changed since
    seconds: int        # how long that green run took: the time not running it saves (0 when not recorded)


def taken(run: str | Path, row: gate_table.Gate, top: str, now: str | None = None) -> Taken | None:
    """The gate's last green, with the config's command, when it stands for the files on disk: `now`, top's
    git.files_tree (taken here when not given, only once there is a green). The same tree, or, for a row with a
    Covers cell, one whose files under those paths are the same. None (it runs) for anything else, and whenever
    git can't read either tree: never skipped on a guess."""
    verdict = gates.files(Path(run), gates.slug(row.name))[0].as_posix()
    green = verdicts.green(verdict, gate_run.json_esc(row.command))
    if green is None:
        return None
    now = git.files_tree(top) if now is None else now
    if not now:
        return None
    seconds = int(verdicts.number(verdict, "seconds") or 0)
    if green.tree == now:
        return Taken(green, True, seconds)
    if row.covers and git.unchanged_under(top, green.tree, now, row.covers):
        return Taken(green, False, seconds)
    return None


def not_rerun(row: gate_table.Gate, took: Taken) -> str:
    """The words for a green taken on other files, said by gate --all and the receipt alike."""
    return "not rerun — nothing under %s changed since its green run (%s, tree %s, %s)" % (
        ", ".join(row.covers), took.green.seat, took.green.tree[:12], took.green.when)


def span(seconds: int) -> str:
    """A run's time as gate --all says what not running it saves: 45s, 19m 30s, 1h 05m."""
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        return "%dm %02ds" % divmod(seconds, 60)
    return "%dh %02dm" % (seconds // 3600, seconds % 3600 // 60)
