"""council route recommend: advisory routing (references/run/adaptive-routing.md). The rows it prints are a
proposal, never a run plan or a dispatch instruction. The policy stays small and deterministic until
measured outcomes can support learning."""
from __future__ import annotations

import re
from typing import NamedTuple

from council.commands import cli
from council.records import config
from council.records import home as where

FLAGS = ("task", "risk", "complexity", "uncertainty", "surface", "agent-cap", "budget-tokens", "classic")
LENSES = ("security", "data", "frontend", "architecture", "performance")    # specialists, by priority
CANDIDATES = ("implementation", "testing") + LENSES + ("verification",)
CHAIR_TOKENS = 20000
NO_HISTORY = 80000
SPACE = " \t\n\r\v\f"                                  # tr's [:space:]
SIGNALS = {
    "security": ("auth", "authentication", "authorization", "authorize", "security", "secure", "crypto",
                 "cryptography", "secret", "secrets", "permission", "permissions", "credential", "credentials",
                 "access token", "access tokens", "refresh token", "refresh tokens", "bearer token",
                 "bearer tokens", "session token", "session tokens", "api key", "api keys"),
    "data": ("database", "schema", "migration", "migrate", "persistence", "persistent", "storage", "sql", "db"),
    "frontend": ("frontend", "browser", "accessibility", "accessible", "ui", "ux", "css", "webpage", "web"),
    "architecture": ("architecture", "architectural", "refactor", "refactoring", "api", "interface", "module",
                     "modules", "design"),
    "performance": ("performance", "latency", "throughput", "hot path", "optimize", "optimization"),
}
HIGH_RISK = ("destructive", "delete", "deletion", "production", "deploy", "deployment", "breaking", "public api")
BROAD = ("cross module", "multiple", "several", "end to end")


def main(args: cli.Args, words: list[str]) -> int:
    """council route recommend --task TEXT [routing flags]."""
    if not words or words[0] != "recommend":
        raise cli.Refusal("usage: council route recommend --task TEXT [routing flags]")
    cli.takes_flags(args, "route recommend", *FLAGS)
    if args.value("run"):
        raise cli.Refusal("route recommend does not take --run; it uses this project's config")
    cli.no_words("route recommend", words[1:])
    home = where.council_home()
    for row in recommend(read(args, config.agent_cap(home)), config.worker_estimate(home)):
        cli.say("\t".join(row))
    return 0


def cell(text: str) -> str:
    """A value as one TSV cell: tabs and line breaks become spaces."""
    return text.translate(str.maketrans("\t\r\n", "   "))


def blank(text: str) -> bool:
    return not cell(text).strip(SPACE)


def positive(flag: str, value: str) -> None:
    """Refuse a value that isn't a whole number from 1 to 9999999."""
    if not re.fullmatch(r"[0-9]+", value):
        raise cli.Refusal("--%s needs a positive integer" % flag)
    if len(value) > 7 or int(value) == 0:
        raise cli.Refusal("--%s must be between 1 and 9999999" % flag)


class Asked(NamedTuple):
    """The task and what the command line said about it, checked; '' for what it left out."""

    task: str
    risk: str
    complexity: str
    uncertainty: str
    surfaces: list[str]
    cap: str
    cap_reason: str
    budget: str
    classic: bool


def read(args: cli.Args, project_cap: int) -> Asked:
    """The flags, refused in the helper's order; the cap is the project's unless --agent-cap is lower."""
    if blank(args.value("task")):
        raise cli.Refusal("route recommend needs --task TEXT")
    positive("agent-cap", str(project_cap))
    cap, cap_reason = str(project_cap), "project's configured agent cap"
    if args.value("agent-cap"):
        positive("agent-cap", args.value("agent-cap"))
        if int(args.value("agent-cap")) > project_cap:
            raise cli.Refusal("--agent-cap cannot exceed the configured cap (%d)" % project_cap)
        cap, cap_reason = args.value("agent-cap"), "explicit cap within project's configured cap"
    if args.value("budget-tokens"):
        positive("budget-tokens", args.value("budget-tokens"))
    if args.value("risk") not in ("", "low", "medium", "high"):
        raise cli.Refusal("--risk must be low, medium or high")
    if args.value("uncertainty") not in ("", "low", "medium", "high"):
        raise cli.Refusal("--uncertainty must be low, medium or high")
    if args.value("complexity"):
        positive("complexity", args.value("complexity"))
        if int(args.value("complexity")) > 10:
            raise cli.Refusal("--complexity must be 1..10")
    for surface in args.lists["surface"]:
        if blank(surface):
            raise cli.Refusal("--surface needs a non-empty name")
    return Asked(cell(args.value("task")), args.value("risk"), args.value("complexity"), args.value("uncertainty"),
                 [cell(surface) for surface in args.lists["surface"]], cap, cap_reason, args.value("budget-tokens"),
                 bool(args.value("classic")))


def signals(asked: Asked) -> dict[str, bool]:
    """Which specialist lenses the task and the named surfaces call for. Punctuation and path separators
    are word boundaries, byte by byte as tr reads them: a substring match would read "author" as auth and
    "rapid" as API."""
    words = lower(asked.task + " " + ", ".join(asked.surfaces)).encode("utf-8", "surrogateescape")
    text = " " + re.sub(rb"[^a-z0-9]", b" ", words).decode("ascii") + " "
    found = {lens: any(" %s " % word in text for word in SIGNALS[lens]) for lens in LENSES}
    found["data"] = found["data"] or any(lower(surface) in ("data", "database", "db") for surface in asked.surfaces)
    found["high risk"] = any(" %s " % word in text for word in HIGH_RISK)
    found["broad"] = any(" %s " % word in text for word in BROAD)
    return found


def lower(text: str) -> str:
    """ASCII letters lower-cased, as tr does; every other character as it is."""
    return text.translate(config.ASCII_LOWER)


class Assessed(NamedTuple):
    """Risk, complexity and uncertainty, each given or inferred, with the reason said for it."""

    risk: str
    risk_reason: str
    complexity: str
    complexity_reason: str
    uncertainty: str
    uncertainty_reason: str


def assess(asked: Asked, found: dict[str, bool]) -> Assessed:
    risk, risk_reason = asked.risk, "explicit --risk override"
    if not risk:
        risk, risk_reason = "low", "inferred from task and named surfaces"
        if found["security"] or found["data"]:
            risk = "high"
        elif found["architecture"] or found["frontend"] or found["performance"]:
            risk = "medium"
        if found["high risk"]:
            risk = "high"
    complexity, complexity_reason = asked.complexity, "explicit --complexity override"
    if not complexity:
        score = 2 + len(asked.surfaces) + 2 * found["architecture"] + found["data"] + found["security"]
        score += 2 * found["broad"]
        complexity, complexity_reason = str(min(score, 10)), "estimated from named surfaces and task wording"
    uncertainty, uncertainty_reason = asked.uncertainty, "explicit --uncertainty override"
    if not uncertainty:
        uncertainty, uncertainty_reason = "medium", "conservative default; limited evidence from task wording"
    return Assessed(risk, risk_reason, complexity, complexity_reason, uncertainty, uncertainty_reason)


class Sized(NamedTuple):
    size: str
    reason: str
    status: str          # ready, constrained or needs-rescope
    level: str           # the verification level
    verification: str    # available, constrained or unavailable


def size_of(asked: Asked, found: dict[str, bool], judged: Assessed, per: int) -> Sized:
    """The run size and verification: the level the risk needs, never reduced to fit a cap; only a ceiling
    the user gave (--budget-tokens) can shrink a run, the estimate alone never does."""
    complexity, cap = int(judged.complexity), int(asked.cap)
    required = "self"
    if judged.risk == "high":
        required = "adversarial"
    elif judged.risk == "medium" or complexity >= 4 or judged.uncertainty == "high":
        required = "independent"
    status, size, reason = "ready", "solo", "one bounded chain can stay with the Chair"
    if asked.classic:
        size, reason = "squad", "classic fixed squad baseline, independent of inferred task signals"
    elif judged.risk == "high" or complexity >= 7 or judged.uncertainty == "high":
        size, reason = "full", "high risk, complexity or uncertainty warrants broader review"
    elif judged.risk == "medium" or complexity >= 4 or found["security"] or found["data"]:
        size, reason = "squad", "multiple useful lenses and independent verification"
    ceiling = int(asked.budget) if asked.budget else None
    if size == "full" and (cap < 4 or (ceiling is not None and ceiling < CHAIR_TOKENS + 4 * per)):
        size, reason, status = "squad", "full recommendation reduced by agent or token cap", "constrained"
    if size == "squad" and (cap < 3 or (ceiling is not None and ceiling < CHAIR_TOKENS + 3 * per)):
        size, status = "solo", "constrained"
        reason = "squad recommendation reduced by agent or token cap; independent verification unavailable"
    level = "independent" if size != "solo" and required == "self" else required
    verification = "available"
    if size == "solo" and required != "self":
        status, verification = "needs-rescope", "unavailable"
    elif status == "constrained":
        verification = "constrained"
    return Sized(size, reason, status, level, verification)


def wanted(lens: str, found: dict[str, bool], complexity: int) -> bool:
    """The task or its surfaces call for this specialist (architecture also for high complexity)."""
    return found[lens] or (lens == "architecture" and complexity >= 7)


def roster(asked: Asked, found: dict[str, bool], sized: Sized, judged: Assessed) -> list[str]:
    """The selected agents: implementation and testing, specialists by relevance while slots remain (one
    kept for the verifier), Full's generic fallbacks after them, and the verifier. Priority is fixed, so
    a capped recommendation is reproducible and explains each lens it left out."""
    if sized.size == "solo":
        return []
    chosen, cap, complexity = ["implementation", "testing"], int(asked.cap), int(judged.complexity)
    limit = 7 if sized.size == "full" else 4
    if cap <= limit:
        limit = cap - 1
    for lens in LENSES:
        if asked.classic or len(chosen) >= limit:
            break
        if wanted(lens, found, complexity):
            chosen.append(lens)
    if not asked.classic and sized.size == "full":
        for lens, when in (("security", judged.risk == "high"), ("architecture", True)):
            if when and len(chosen) < limit and lens not in chosen:
                chosen.append(lens)
    return chosen + ["verification"]


def recommend(asked: Asked, per_worker: int | None) -> list[tuple[str, ...]]:
    """The recommendation's rows: kind, id, field, value, reason."""
    found = signals(asked)
    judged = assess(asked, found)
    complexity = int(judged.complexity)
    per, per_reason = (per_worker, "configured estimate per worker (council.config.md)") if per_worker \
        else (NO_HISTORY, "no-history estimate")
    sized = size_of(asked, found, judged, per)
    chosen = roster(asked, found, sized, judged)
    status, verification = sized.status, sized.verification
    if not asked.classic and sized.size != "solo" and status == "ready" \
            and any(wanted(lens, found, complexity) and lens not in chosen for lens in LENSES):
        status = "constrained"
    workers = len(chosen) - 1 if chosen else 0
    worker_tokens, verifier_tokens = (workers * per, per) if chosen else (0, 0)
    budget = CHAIR_TOKENS + worker_tokens + verifier_tokens
    if asked.budget and budget > int(asked.budget):
        status, verification = "needs-rescope", "unavailable"
    rows = head(asked, judged, sized)
    rows.append(("budget", "route", "selected-agents", str(len(chosen)), "Chair is excluded; never exceeds agent cap"))
    reason = "%s: %dk per selected agent plus 20k Chair; not measured or enforced" % (per_reason, (per + 500) // 1000)
    rows += budget_rows(asked, status, verification, (budget, worker_tokens, verifier_tokens), reason)
    rows += [("seat", lens, "disposition") + disposition(lens, chosen, found, asked.classic, complexity)
             for lens in CANDIDATES]
    return rows


def head(asked: Asked, judged: Assessed, sized: Sized) -> list[tuple[str, ...]]:
    """The rows up to the Chair's: the input, the run's size and policy, the assessment, cap and level."""
    complexity = int(judged.complexity)
    band = "low" if complexity <= 3 else "medium" if complexity <= 6 else "high"
    chair = ("Solo stays with the Chair; the Chair does not count against agent cap" if sized.size == "solo"
             else "Chair coordinates and synthesizes; does not count against agent cap")
    return [
        ("kind", "id", "field", "value", "reason"),
        ("schema", "route", "version", "1", "versioned advisory recommendation"),
        ("input", "route", "task", asked.task, "explicit task description"),
        ("input", "route", "surfaces", ", ".join(asked.surfaces) or "-", "explicit surfaces only; '-' means none"),
        ("run", "route", "policy", "classic" if asked.classic else "adaptive",
         "classic keeps a fixed baseline; adaptive uses task signals"),
        ("run", "route", "size", sized.size, sized.reason),
        ("assessment", "route", "risk", judged.risk, judged.risk_reason),
        ("assessment", "route", "complexity", judged.complexity, judged.complexity_reason),
        ("assessment", "route", "complexity-band", band, "maps score 1-3 low, 4-6 medium, 7-10 high for run-plan v1"),
        ("assessment", "route", "uncertainty", judged.uncertainty, judged.uncertainty_reason),
        ("budget", "route", "agent-cap", asked.cap, asked.cap_reason),
        ("budget", "route", "ceiling-tokens", asked.budget or "-",
         "explicit advisory planning ceiling; '-' means no user ceiling; not runtime enforcement"),
        ("verification", "route", "level", sized.level,
         "minimum depth from risk, uncertainty and run size; never reduced to fit a cap"),
        ("seat", "chair", "disposition", "selected", chair),
    ]


def budget_rows(asked: Asked, status: str, verification: str, tokens: tuple[int, int, int],
                reason: str) -> list[tuple[str, ...]]:
    """The route's status, verification status, and the token estimate split between Chair, workers and verifier."""
    budget, workers, verifier = tokens
    rows = [("run", "route", "status", status, "constrained means reduced size or omitted relevant lens; "
             "needs-rescope means estimated need exceeds ceiling or required verification cannot fit"),
            ("verification", "route", "status", verification,
             "unavailable requires more budget or agents before proceeding"),
            ("budget", "route", "estimated-tokens", str(budget), reason)]
    if asked.budget:
        rows.append(("budget", "run", "token-ceiling", asked.budget,
                     "explicit ceiling from --budget-tokens; copy to run-plan.tsv"))
    return rows + [
        ("budget", "run", "chair-tokens", str(CHAIR_TOKENS),
         "the Chair's own share of the estimate; copy to run-plan.tsv — agents are compared with the rest"),
        ("budget", "workers", "estimated-tokens", str(workers),
         "shared across selected worker archetypes; not measured or enforced"),
        ("budget", "verification", "estimated-tokens", str(verifier), "advisory allocation; not measured or enforced")]


def disposition(lens: str, chosen: list[str], found: dict[str, bool], classic: bool,
                complexity: int) -> tuple[str, str]:
    """A candidate seat's disposition and why."""
    if lens in chosen:
        if lens in ("implementation", "testing", "verification"):
            return "selected", {"implementation": "bounded implementation or primary investigation lens",
                                "testing": "regression and test-design lens",
                                "verification": "independent challenge of worker claims"}[lens]
        if lens == "security" and not found["security"]:
            return "selected", "high-risk work merits a security challenge"
        if lens == "architecture":
            return "selected", ("task or surface indicates an architecture lens" if found["architecture"]
                                else "full council needs a structural lens")
        return "selected", "task or surface indicates a %s lens" % lens
    if not chosen:
        return "skipped", "Solo uses no delegated agents"
    if classic:
        return "skipped", "classic policy keeps a fixed implementation, testing and verification roster"
    if lens == "verification":
        return "skipped", "no agent slot available for independent verification"
    if lens in ("implementation", "testing"):
        return "skipped", "not selected by routing policy"
    if lens == "architecture" and not found["architecture"] and complexity < 7:
        return "skipped", "no architecture or high-complexity signal"
    if lens != "architecture" and not found[lens]:
        return "skipped", {"security": "no security signal in task or surfaces",
                           "data": "no persistent-data signal in task or surfaces",
                           "frontend": "no frontend signal in task or surfaces",
                           "performance": "no performance signal in task or surfaces"}[lens]
    return "skipped", "agent cap reserved for higher-priority lenses"
