"""The `- estimates:` line of council.config.md: the tokens an agent of each role is budgeted at.

`- estimates: review=100k, plan=90k, builder=450k, verifier=60k, converge=80k`, read as `- models:` is
(config.role_pairs). A role is the job an agent does in a mode: the review seat, the plan seat, the builder, a
verifier, and the converge check (the verifier of a build). A role the line leaves out, or gives a figure the
route cannot read, takes `- estimate per worker:`, so a config without the line budgets as it always did.
"""
from __future__ import annotations

import re

from council.records import config

KEY = "estimates"
ROLES = ("review", "plan", "builder", "verifier", "converge")
WORKERS = {"review": "review", "plan": "plan", "implement": "builder"}      # a mode's worker role


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
