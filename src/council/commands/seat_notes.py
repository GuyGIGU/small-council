"""What `council seat` says after the write."""
from __future__ import annotations

from pathlib import Path

from council.commands import cli
from council.records import bytewise, seat_rows, seat_write, seats, usage


def report(run: Path, slug: str, got: dict[str, str]) -> None:
    """The progress line (a seat over its tool budget on it), then the first ask for tools=."""
    budget, over = seat_rows.tool_budget(run, slug), ""
    if got["tools"]:
        used = seat_rows.tool_calls(run, slug)
        if budget and not (used and int(used) <= int(budget)):
            over = "%s used %s tool calls, over its plan budget of %s — say so in the log" % (slug, used, budget)
    cli.say(progress_line(run, over))
    tools = seats.path(run, seat_rows.TOOLS)
    if (not got["tools"] and got["tokens"] and not got["agents"] and budget
            and not (tools.is_file() and tools.stat().st_size)
            and sum(c[3] == "finished" for c in seat_write.table(seats.path(run, seats.USAGE))[1:]) <= 1):
        cli.warn("council: add tools=<the notification's tool_uses> to measure seat %s against its tool budget of %s"
                 % (slug, budget))


def progress_line(run: Path, note: str) -> str:
    """'seats: D of N done · still working: … · ~Xk tokens so far'; an older row's tokens are not added."""
    seated = done = tokens = 0
    older, named = False, {"running": [], "queued": [], "failed": []}
    for line in bytewise.file_lines(seats.path(run), fold=False)[1:]:
        c = line.split("\t")
        short, c = len(c) < 8, c + [""] * 8
        if c[1] == "skipped":
            continue
        seated, done = seated + 1, done + (c[1] == "done")
        named.get("failed" if c[1] == "blocked" else c[1], []).append(c[0])
        if short or c[7] == "":
            older = older or seat_write.number(c[3]) > 0
        else:
            tokens += seat_write.number(c[3])
    parts = ["seats: %d of %d done" % (done, seated)]
    parts += ["%s: %s" % (label, ", ".join(named[key])) for key, label in
              (("running", "still working"), ("queued", "queued"), ("failed", "failed")) if named[key]]
    parts += ["~%s tokens so far" % usage.token_text(tokens)] * (tokens > 0)
    parts += ["older rows' tokens not counted"] * older + [note] * bool(note)
    return " · ".join(parts)
