"""The `- estimates:` line of council.config.md: the tokens an agent of each role is budgeted at.

`- estimates: review=100k, plan=90k, builder=450k, verifier=60k, converge=80k`, read as `- models:` is
(config.role_pairs). A role is the job an agent does in a mode: the review seat, the plan seat, the builder, a
verifier, and the converge check (the verifier of a build). A role the line leaves out, or gives a figure the
route cannot read, takes `- estimate per worker:`, so a config without the line budgets as it always did.
"""
from __future__ import annotations

import re

from council.records import config, ledger

KEY = "estimates"
ROLES = ("review", "plan", "builder", "verifier", "converge")
WORKERS = {"review": "review", "plan": "plan", "implement": "builder"}      # a mode's worker role
LINES = re.compile(r"^[ \t]*-[ \t]*estimates:[^\r\n]*", re.MULTILINE)
PARTS = re.compile(r"([ \t]*-[ \t]*estimates:[ \t]*)(.*?)([ \t]*<!--.*)?$")


def mode_roles(mode: str) -> tuple[str, str]:
    """(worker role, verification role) of a mode: its workers' role ('' for a mode with none of its own) and
    the role its verifiers play: converge in a build, verifier in the rest."""
    mode = re.sub(r"^council-", "", mode)
    return WORKERS.get(mode, ""), "converge" if mode == "implement" else "verifier"


def figures(pieces: list[tuple[str, str, str]]) -> dict[str, int]:
    """The roles a line's pieces give a readable figure (1k-1M, as `estimate per worker` is read); the first
    piece for a role stands, and a role or figure it cannot read is left out."""
    found: dict[str, int] = {}
    for role, equals, value in pieces:
        tokens = config.estimate_tokens(value) if equals and role in ROLES else None
        if tokens:
            found.setdefault(role, tokens)
    return found


def read(home: object) -> dict[str, int]:
    """The role figures of the config's first `- estimates:` line; {} when it has none."""
    return figures(config.role_pairs(home, KEY)[1])


def figure(text: str, role: str) -> int | None:
    """One role's figure in a config's text, as read() reads it."""
    found = LINES.search(text)
    return figures(config.pairs(PARTS.match(found.group(0)).group(2))).get(role) if found else None


def with_role(text: str, role: str, shown: str) -> tuple[str, dict]:
    """The config text with the role's figure set to `shown` ('450k') and the record that undoes it: the first
    `- estimates:` line keeps its other pieces and its comment, and a config without one gets the line as the
    last item of ## Run preferences."""
    piece = "{}={}".format(role, shown)
    found = LINES.search(text)
    if not found:
        at, inserted = config.preferences_insertion(text, "- estimates: " + piece)
        after = "- estimates: " + piece
        return text[:at] + inserted + text[at:], {"before": None, "after": after, "inserted": inserted}
    head, body, comment = PARTS.match(found.group(0)).groups()
    pieces = [p.strip() for p in body.split(",") if p.strip()]
    same = [i for i, p in enumerate(pieces) if p.partition("=")[0].strip().lower() == role]
    if same:
        pieces[same[0]] = piece
    else:
        pieces.append(piece)
    after = head + ("" if head[-1] in " \t" else " ") + ", ".join(pieces) + (comment or "")
    record = {"before": found.group(0), "after": after, "inserted": None}
    return text[:found.start()] + after + text[found.end():], record


def measured(rows: list[dict]) -> dict[str, list[int]]:
    """What each role cost per run, from the ledger's rows: a worker role's tokens per agent (the mean over the
    run's seats of that role), a verifier role's tokens for the run (the `(verifiers)` row, all of that run's
    verifiers). A seat whose tokens are unknown is left out, never counted as zero; a mode with no role of its
    own (research, a post-game) adds none."""
    per_run: dict[tuple[str, str], list[int]] = {}
    for row in rows:
        worker, verifier = mode_roles(row["mode"])
        role = verifier if row["seat"] == ledger.VERIFIERS else worker
        if role and row["tokens"] is not None:
            per_run.setdefault((role, row["run"]), []).append(row["tokens"])
    found: dict[str, list[int]] = {}
    for (role, _), tokens in per_run.items():
        found.setdefault(role, []).append(sum(tokens) // len(tokens))
    return found
