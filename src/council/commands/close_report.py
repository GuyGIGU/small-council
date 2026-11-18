"""What a close says from the scripts that read the run back."""
from __future__ import annotations

import re
from pathlib import Path

from council.commands import cli, resolve, script
from council.records import audit_file, events, stages, usage


def claims_note(run: Path, status: str) -> None:
    """A complete close of a synthesis run builds its claim index itself (D44), so the audit reads it current; one
    that can't be built is one warning, naming the command that says why."""
    if status != "complete" or resolve.field(run, "mode") not in stages.SYNTHESISED:
        return
    if not (run / "synthesis.md").is_file():
        if (run / "claims.jsonl").is_file():
            cli.warn("council: claims.jsonl has no synthesis.md beside it to be built from — write %s/synthesis.md, "
                     "then council evidence check --run %s" % (run.as_posix(), run.name))
        return
    code, _, _ = script.captured("evidence", ["build", "--run", run.as_posix()])
    if code:
        cli.warn("council: the claim index could not be built — council evidence check --run %s names each problem"
                 % run.name)


def audit(run: Path) -> None:
    """The audit at the close, kept as audit.md: its verdict line and every FAIL line, on stdout."""
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
    """The Chair's own tokens from the session transcript, and beside them the method its mode loads through the
    stages the run enters (D13), as a run.chair_usage event and one line; else nothing."""
    code, out, _ = script.captured("chair_usage", ["--run", run.as_posix()])
    said = re.fullmatch("tokens=([0-9]+);calls=([0-9]+);basis=(complete|partial)", out.rstrip("\n"))
    if code or not said:
        return
    tokens, calls, basis = said.groups()
    mode, entered = resolve.field(run, "mode"), stages.required(run)
    method = stages.method_bytes(mode, entered)
    try:
        events.append(run, "run.chair_usage", "chair", tokens,
                      "calls=%s;basis=%s;method_bytes=%d" % (calls, basis, method))
    except events.EventError as failure:
        cli.warn("council: %s" % failure)
        return
    doctrine = sum(name.startswith("references/doctrine/") for name in stages.method_files(mode, entered))
    cli.say("the Chair's own work: %s%s tokens over %s model call%s (its context's growth, from the session "
            "transcript; not in the agents' figures) · method load: %s bytes (context-core, %s and the doctrine of "
            "the %d stage%s it enters)"
            % ("at least " * (basis == "partial"), usage.token_text(int(tokens)), calls, "s" * (calls != "1"),
               format(method, ","), mode, doctrine, "s" * (doctrine != 1)))
