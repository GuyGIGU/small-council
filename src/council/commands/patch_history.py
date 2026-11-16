"""A build task's history across its rounds (#60), from its saved patches and heads: what each round changed, its
cause, what it removed and assumed, what the checks found, and where it touched the same files as the round
before. council patch save writes it to `patches/T<n>.md` for the next round's brief and the verifier; council
patch show prints it."""
from __future__ import annotations

from pathlib import Path

from council.commands import cli, gate_output
from council.records import patches

# A sign's question for the verifier: a fix round's (its head names a cause), and a first build's (Cause: none).
SIGN_QUESTION = "does it remove the cause, or hide the symptom?"
BUILD_QUESTION = "does it make up for other code instead of doing the task? (build-proof.md, Making up for other code)"


def lines(run: str | Path, task: int) -> list[str]:
    """The history of a task's saved rounds; none when it has no saved round."""
    found = patches.rounds(run, task)
    if not found:
        return []
    out = ["# Task %d: its rounds" % task, "",
           "From the saved patches and report heads (council patch show %d). Signs are questions for the verifier, "
           "never verdicts." % task]
    before: list[str] = []
    for one in found:
        out += [""] + _round(one, before)
        before = one.files
    return out


def _round(one: patches.Round, before: list[str]) -> list[str]:
    head = one.head
    cause = head.get("cause", "")
    out = ["## Round %d · %s · %s" % (one.round, patches.name(one.task, one.round) + ".patch",
                                      one.at.replace("T", " ").replace("Z", " UTC")),
           "- changed: %d file(s), +%d −%d: %s" % (len(one.files), one.added, one.removed,
                                                   ", ".join(one.files) or "nothing"),
           "- cause: %s" % ("%s (%s)" % (cause, head.get("state")) if head.get("state") else "none, a first build"),
           "- owner: %s · removed: %s · assumed: %s" % (head.get("owner", ""), head.get("removed", ""),
                                                        head.get("assumed", ""))]
    if head.get("redesign"):
        out.append("- redesign: %s" % head["redesign"])
    same = [path for path in one.files if path in before]
    if same:
        out.append("- same files as the round before: %s" % ", ".join(same))
    if one.outside:
        out.append("- outside the task's slice (%s): %s" % (one.slice, ", ".join(one.outside)))
    elif one.slice.startswith("skipped"):
        out.append("- owner check %s" % one.slice)
    for kind, path, line, text in one.signs:
        out.append("- sign: %s · %s:%d · `%s`" % (kind, path, line, gate_output.clip(text, 80)))
    return out


def said(one: patches.Round, saved: Path, story: Path) -> None:
    """What council patch save prints once a round is saved."""
    cli.say("patch: task %d round %d saved → %s · %d file(s), +%d −%d · tree %s" % (
        one.task, one.round, saved.as_posix(), len(one.files), one.added, one.removed, one.tree[:12]))
    if one.outside:
        cli.say("patch: owner — %d file(s) outside task %d's slice (%s): %s — for the verifier: possible scope creep"
                % (len(one.outside), one.task, one.slice, ", ".join(one.outside)))
    elif one.slice.startswith("skipped"):
        cli.say("patch: owner check %s" % one.slice)
    question = SIGN_QUESTION if one.head.get("state") else BUILD_QUESTION      # no state: Cause: none, as _round reads
    for kind, path, line, text in one.signs[:10]:
        cli.say("patch: sign — %s · %s:%d · %s — for the verifier: %s" % (
            kind, path, line, gate_output.clip(text, 60), question))
    if len(one.signs) > 10:
        cli.say("patch: … and %d more signs in %s" % (len(one.signs) - 10, story.as_posix()))
    cli.say("patch: history → %s — the verifier gets the patch and this history, never the report's prose; a fix "
            "round's brief links it" % story.as_posix())
