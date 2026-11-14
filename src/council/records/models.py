"""The `- models:` line of council.config.md (D37): the model each role's agents run on.

`- models: builder=opus, review=sonnet, verifier=opus`. A name is what the Agent tool's `model` parameter
takes: inherit (the session's model) or an alias, never a versioned id that goes stale. A role the line
leaves out, and every role without the line, is `inherit`, so nothing changes until a project opts in.
`- seat models:` (D30's mapping and survey overrides) is its own line and reads as it always has.
"""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from council.records import config

INHERIT = "inherit"
ORDER = ("haiku", "sonnet", "opus", "fable")      # weakest first: a verifier is never below its builder
NAMES = (INHERIT,) + ORDER[::-1]
SAID = ", ".join(NAMES[:-1]) + " or " + NAMES[-1]  # "inherit, fable, opus, sonnet or haiku", for refusals
ROLES = ("builder", "review", "verifier")
LINE = config.SPACE + "*-" + config.SPACE + "*models:" + config.SPACE + "*(.*)"


class Models(NamedTuple):
    """Each role's model, `written` when the config has the line, and `problem` when the line can't be read
    (the roles then stay inherit, and the plan check refuses until the line is fixed)."""

    builder: str = INHERIT
    review: str = INHERIT
    verifier: str = INHERIT
    written: bool = False
    problem: str = ""

    def of(self, role: str) -> str:
        """The model of a role ('' for a role the line has no word for: the Chair, a diagnosis seat)."""
        return getattr(self, role) if role in ROLES else ""


def models(home: str | Path | None) -> Models:
    """The first `- models:` line, read; Models() when there is none or it says nothing."""
    found = config.first(home, LINE)
    if not found:
        return Models()
    text = found.group(1).replace("\r", "")
    text = text.split("<!--", 1)[0].strip(" \t").translate(config.ASCII_LOWER)
    return parse(text)


def parse(text: str) -> Models:
    """'builder=opus, verifier=opus' as Models; the first word it can't take is its problem."""
    chosen: dict[str, str] = {}
    for part in (p.strip(" \t") for p in text.split(",")):
        if not part:
            continue
        role, equals, name = (w.strip(" \t") for w in part.partition("="))
        problem = refusal(role, equals, name, chosen)
        if problem:
            return Models(written=True, problem=problem)
        chosen[role] = name
    return Models(written=True, **chosen)


def refusal(role: str, equals: str, name: str, chosen: dict[str, str]) -> str:
    """Why one `role=name` can't be read, and what to write instead; '' when it can."""
    where = "council.config.md's `- models:` line"
    if not equals or not role:
        return "%s: '%s' is not role=model — write builder=, review= or verifier= with a model" % (where, role)
    if role not in ROLES:
        return "%s: '%s' is not a role — use builder, review or verifier" % (where, role)
    if role in chosen:
        return "%s names %s twice — keep one" % (where, role)
    if name not in NAMES:
        return "%s: '%s' is not a model for %s — use %s" % (where, name, role, SAID)
    return ""


def weaker(verifier: str, builder: str) -> bool:
    """A verifier on a weaker model than the builder it checks. Named models compare by ORDER. inherit is the
    session's model, which the helper can't see: a verifier on it is the Chair's own model, at least any
    builder the Chair dispatches, and a builder on it is outranked only by a verifier on fable."""
    if verifier in (INHERIT, builder) or verifier not in NAMES or builder not in NAMES:
        return False                                # an unknown name is refused on its own row
    if builder == INHERIT:
        return verifier != ORDER[-1]
    return ORDER.index(verifier) < ORDER.index(builder)


def shown(found: Models) -> list[str]:
    """['  models: builder=opus · review=sonnet · verifier=opus (council.config.md)'], or [] without the line."""
    if not found.written or found.problem:
        return []
    return ["  models: %s (council.config.md)" % " · ".join("%s=%s" % (r, found.of(r)) for r in ROLES)]
