"""What a close says from the scripts that read the run back: the claim index's staleness, the method audit, the
Chair's own tokens, and the record's follow-up line (said once)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from council.commands import cli, script
from council.records import audit_file, closing, events, usage
from council.records import home as where


def claims_note(run: Path) -> None:
    """A synthesis run's claim index missing, or older than a source it was built from: one warning."""
    def checked() -> bool:
        _, out, err = script.captured("evidence", ["check", "--run", run.as_posix()])
        return "claims.jsonl is missing or stale" in out + err
    if closing.claims_stale(run, checked):
        cli.warn("council: the claim index is missing or out of date — council evidence build --run %s, then evidence "
                 "check" % run.name)


def audit(run: Path) -> None:
    """scripts/audit.py at the close, kept as audit.md: its verdict line and every FAIL line, on stdout."""
    if str(script.SCRIPTS) not in sys.path:               # audit.py imports audit_figures beside it (script.load
        sys.path.insert(0, str(script.SCRIPTS))           # should: see the close report's needs from others)
    code, out, err = script.captured("audit", ["--run", run.as_posix(), "--at-close", "--save"])
    lines = (out + err).split("\n")
    if code > 1:
        last = [line for line in lines if line.split()][-1:]
        cli.say("audit: could not read the run back (%s) — council run audit --run %s" % ("".join(last), run.name))
        return
    total = [line for line in lines if re.match("[0-9]+ failed, ", line)][-1:] or ["no verdict line"]
    fails = [line for line in lines if line.startswith("  FAIL  ")]
    lost = "".join([" (%s)" % line for line in lines if line.startswith("Not saved: ")][-1:])
    where = ("every item, kept: " + audit_file.path(run).as_posix() if any(line.startswith("Saved: ") for line in lines)
             else "every item: council run audit --run %s%s" % (run.name, lost))
    cli.say("audit: %s — %s%s" % (total[0], "tell the user each FAIL below, in plain words; " if fails else "", where))
    for line in fails:
        cli.say(line)


def chair(run: Path) -> None:
    """The Chair's own tokens from the session transcript, as a run.chair_usage event and one line; else nothing."""
    code, out, _ = script.captured("chair_usage", ["--run", run.as_posix()])
    said = re.fullmatch("tokens=([0-9]+);calls=([0-9]+);basis=(complete|partial)", out.rstrip("\n"))
    if code or not said:
        return
    tokens, calls, basis = said.groups()
    try:
        events.append(run, "run.chair_usage", "chair", tokens, "calls=%s;basis=%s" % (calls, basis))
    except events.EventError as failure:
        cli.warn("council: %s" % failure)
        return
    cli.say("the Chair's own work: %s%s tokens over %s model call%s (its context's growth, from the session "
            "transcript; not in the agents' figures)"
            % ("at least " * (basis == "partial"), usage.token_text(int(tokens)), calls, "s" * (calls != "1")))


def follow_up(home: str) -> str:
    """What the record has to say (tune, outcomes) as one line; '' when it said the same at the last close."""
    said = script.captured("tune", ["propose", "--home", home, "--brief"])[1] + script.captured(
        "outcomes", ["--home", home, "--repo", where.this_tree(), "--brief", "--recent", "20"])[1]
    follow = " · ".join(line for line in said.split("\n") if line.split())
    memory = Path(where.native(home)) / "runs" / ".follow-said"
    try:
        before = memory.read_bytes().decode("utf-8", "surrogateescape").rstrip("\n")
    except OSError:
        before = None
    try:
        if not follow:
            memory.unlink()
        elif before == follow:
            return ""
        else:
            memory.write_bytes((follow + "\n").encode("utf-8", "surrogateescape"))
    except OSError:
        pass
    return follow
