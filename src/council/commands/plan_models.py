"""The run plan check's model rules (references/run/run-plan.md, D37): which seat may ask for which model, and
a verifier never on a weaker model than the builder it checks. plan_check.Check calls `judge` once every row
is read; the seat-models overrides (D30's mapping and survey rule) are judged here as they always were."""
from __future__ import annotations

from typing import TYPE_CHECKING

from council.records import models

if TYPE_CHECKING:                                   # plan_check imports this module
    from council.commands.plan_check import Check

BUILD = "council-implement"
ROUTED = ("mapping", "survey")                      # the purposes `- seat models: on` may route
LEGACY = ("sonnet", "haiku")                        # the only names `- seat models:` ever routed


def role_of(check: Check, ident: str) -> str:
    """The `- models:` role a seat's agent plays: a build's workers are builders, a review's workers are
    review seats, a verifier is a verifier; '' for the Chair, a diagnosis seat and other modes' workers.
    A mapping or survey worker stays under `- seat models:` alone."""
    role = check.role.get(ident, "")
    if role == "verifier":
        return "verifier"
    if role != "worker" or check.purpose.get(ident, "") in ROUTED:
        return ""
    return {BUILD: "builder", "council-review": "review"}.get(check.given.mode, "")


def judge(check: Check) -> None:
    """The config's line read; each selected seat's model allowed; each verifier against each builder."""
    found = check.given.models
    closed = check.given.seat_models == "closed"    # judged by the settings of its day: any role model stands
    if found.problem and not closed:
        check.problem(0, found.problem)
    for ident, model in check.model.items():
        line = check.at[("seat", ident, "model")]
        if check.disp.get(ident) != "selected":
            check.problem(line, "a model choice belongs only to a selected seat: " + ident)
        elif model != models.INHERIT:
            role = role_of(check, ident)
            if role and (closed or model == found.of(role)):
                continue
            seat_model(check, ident, model, role, found, line)
    verifiers(check)


def verifiers(check: Check) -> None:
    """Each selected verifier against each builder: a build's builder agents, and the Chair, which builds in its
    own window on the session's model (council-implement), whatever its row says."""
    selected = [i for i in check.disp if check.disp[i] == "selected"]
    builders = [(i, check.model.get(i, models.INHERIT)) for i in selected if role_of(check, i) == "builder"]
    if check.given.mode == BUILD:
        builders += [(i, models.INHERIT) for i in selected if check.role.get(i) == "chair"]
    for ident in (i for i in selected if role_of(check, i) == "verifier"):
        mine = check.model.get(ident, models.INHERIT)
        for builder, theirs in builders:
            if models.weaker(mine, theirs):
                who = "the Chair, which builds," if check.role.get(builder) == "chair" else "builder " + builder
                fix = "inherit, as its builder is" if theirs == models.INHERIT else theirs + " or stronger"
                check.problem(check.at.get(("seat", ident, "model"), 0),
                              "verifier %s on %s is weaker than %s on %s — put the verifier on %s "
                              "(seat/%s/model, and verifier= in council.config.md's - models:)"
                              % (ident, mine, who, theirs, fix, ident))


def seat_model(check: Check, ident: str, model: str, role: str, found: models.Models, line: int) -> None:
    """A named model that isn't its role's configured one: the Chair stays on the session's model; sonnet and
    haiku fall to the seat-models rules as before; fable and opus need `- models:`."""
    seat_role = check.role.get(ident, "")
    if model in LEGACY or model not in models.NAMES:   # an unknown name: refused by its row, judged as before
        if seat_role != "worker":
            check.problem(line, "only worker seats can use sonnet or haiku; %s has role %s" % (ident, seat_role))
        if check.given.seat_models == "off":
            check.problem(line, "seat model overrides are off; enable seat models: on in council.config.md")
        if check.purpose.get(ident, "") not in ROUTED:
            check.problem(line, "sonnet or haiku needs seat/%s/purpose = mapping or survey" % ident)
    elif seat_role == "chair":
        check.problem(line, "the Chair stays on the session's model — make seat/%s/model inherit" % ident)
    elif not role:
        check.problem(line, "%s for %s needs a role council.config.md's - models: line names (a build's builder, a "
                            "review's seat or a verifier) — make seat/%s/model inherit" % (model, ident, ident))
    else:                                           # a closed run's role models were judged on their day
        check.problem(line, "%s is not the %s model in council.config.md (- models: %s=%s) — set %s=%s there, "
                            "or make seat/%s/model %s" % (model, role, role, found.of(role), role, model, ident,
                                                          found.of(role)))
