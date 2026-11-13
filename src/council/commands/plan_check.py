"""The run plan check's rules (references/run/run-plan.md): each row's own, then the plan's. The plan is
read as the helper's awk read it: every byte, its lines as `cells.lines_of` splits them, and a numeric value
with spaces around it compared as text (awk's rule, kept as it was)."""
from __future__ import annotations

import re
from typing import NamedTuple
from council.records import cells

HEADER = "kind\tid\tfield\tvalue\treason"
NUMBER = re.compile(r"[ \t\n\r\f\v]*[-+]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][-+]?[0-9]+)?")
DIGITS = re.compile(r"[0-9]+")
LEVELS = ("low", "medium", "high")
Key = tuple  # (kind, id, field)


class Settings(NamedTuple):
    """What the check judges a plan against, besides the plan."""

    run: str             # the run folder's name: the plan's run id
    mode: str            # session-state.md's mode
    cap: int             # the configured agent cap
    go: int | None       # the user's latest go past the cap (council cap allow), if any
    seat_models: str     # on, off, or closed: a closed run's plan was judged by the setting of its day
    full_go: bool        # a decision of the user's since the run opened (or the run is closed)


def number(text: str) -> float:
    """A value as awk reads it in arithmetic: its leading number, else 0."""
    found = NUMBER.match(text)
    return float(found.group(0)) if found else 0.0


def number_text(value: float) -> str:
    """A number as awk writes it into text: whole as an integer, else six significant digits."""
    return "%d" % value if value.is_integer() else "%.6g" % value


class Value(NamedTuple):
    """A trimmed value, and whether trimming took anything off: awk then compares it as text."""

    text: str
    padded: bool

    def below(self, n: float) -> bool:
        return self.text < number_text(n) if self.padded else number(self.text) < n

    def above(self, n: float) -> bool:
        return self.text > number_text(n) if self.padded else number(self.text) > n

    def whole(self) -> bool:
        return DIGITS.fullmatch(self.text) is not None


class Verdict(NamedTuple):
    """The plan's problems, each said once in the order found, and its valid line."""

    problems: list[str]
    valid: str


def judge(content: str, given: Settings) -> Verdict:
    """Every row's own rules, then the plan's: the rows it must have, its seats and its size."""
    judged = Check(given)
    for n, line in enumerate(cells.lines_of(content), 1):
        judged.line(n, line)
    return judged.finish()


class Check:
    """One plan being judged: what its rows said so far, and the problems found."""

    def __init__(self, given: Settings) -> None:
        self.given = given
        self.problems: list[str] = []
        self.said: set[tuple[int, str]] = set()
        self.got_header = False
        self.val: dict[Key, str] = {}
        self.at: dict[Key, int] = {}
        self.seats: dict[str, str] = {}               # insertion-ordered sets: a seat once, as first named
        self.disp: dict[str, str] = {}
        self.role: dict[str, str] = {}
        self.model: dict[str, str] = {}
        self.purpose: dict[str, str] = {}
        self.ctx: dict[str, str] = {}
        self.calls: dict[str, str] = {}
        self.aruns: dict[str, float] = {}
        self.chair: tuple[float, int] | None = None   # the Chair's share of the estimate, and its line
        self.plan_cap = 0.0

    def problem(self, line: int, message: str) -> None:
        """A problem, once: two passes can find the same one."""
        if (line, message) in self.said:
            return
        self.said.add((line, message))
        self.problems.append("ERROR line %d: %s" % (line, message) if line > 0 else "ERROR: %s" % message)

    def under_go(self, n: float) -> bool:
        return self.given.go is not None and n <= self.given.go

    def go_words(self) -> str:
        if self.given.go is None:
            return ""
        return " or the user's go up to %d agent runs (council cap allow)" % self.given.go

    def line(self, n: int, line: str) -> None:
        """One line of the plan: a blank line and a # comment are passed over; the first other is the header."""
        if re.fullmatch(r"[ \t]*", line) or line.startswith("#"):
            return
        if not self.got_header:
            self.got_header = True
            if line != HEADER:
                self.problem(n, "header must be exactly: " + HEADER)
            return
        parts = line.split("\t")
        if len(parts) != 5:
            self.problem(n, "expected exactly 5 tab-separated columns, got %d" % len(parts))
            return
        kind, ident, field, raw, why = (re.sub(r"^[ \t]+|[ \t]+$", "", part) for part in parts)
        value = Value(raw, raw != parts[3])
        if not (kind and ident and field and raw and why):
            self.problem(n, "kind, id, field, value and reason must all be present")
            return
        if not re.fullmatch(r"[A-Za-z0-9._-]+", ident):
            self.problem(n, "id must use letters, digits, dot, underscore or dash: " + ident)
        if re.fullmatch(r"<.*>", raw, re.S) or raw == "pending":
            self.problem(n, "replace the placeholder value for %s/%s/%s" % (kind, ident, field))
        if re.fullmatch(r"<.*>", why, re.S):
            self.problem(n, "replace the placeholder reason for %s/%s/%s" % (kind, ident, field))
        key = (kind, ident, field)
        if key in self.val:
            self.problem(n, "duplicate row for %s/%s/%s" % key)
            return
        self.val[key], self.at[key] = raw, n
        self.row(n, kind, ident, field, value)

    def row(self, n: int, kind: str, ident: str, field: str, value: Value) -> None:
        """A row's own rules, by its kind."""
        v = value.text
        if kind == "schema":
            if ident != "plan" or field != "version":
                self.problem(n, "unknown schema row")
            elif v != "1":
                self.problem(n, "unsupported run-plan schema version: " + v)
        elif kind == "run":
            self.run_row(n, ident, field, v)
        elif kind == "assessment":
            if ident != "run" or field not in ("risk", "complexity", "uncertainty"):
                self.problem(n, "unknown assessment row")
            elif v not in LEVELS:
                self.problem(n, field + " must be low, medium or high")
        elif kind == "seat":
            self.seat_row(n, ident, field, v)
        elif kind == "context":
            if field != "level":
                self.problem(n, "unknown context field: " + field)
            elif v not in ("minimal", "focused", "full"):
                self.problem(n, "context level must be minimal, focused or full")
            self.ctx[ident] = v
        elif kind == "budget":
            self.budget_row(n, ident, field, value)
        elif kind == "verification":
            if ident != "run" or field != "level":
                self.problem(n, "unknown verification row")
            elif v not in ("self", "independent", "adversarial"):
                self.problem(n, "verification level must be self, independent or adversarial")
        else:
            self.problem(n, "unknown kind: " + kind)

    def run_row(self, n: int, ident: str, field: str, v: str) -> None:
        if ident != "run" or field not in ("id", "mode", "size"):
            self.problem(n, "unknown run row")
        elif field == "id" and v != self.given.run:
            self.problem(n, "run id must match its folder: " + self.given.run)
        elif field == "mode" and v != self.given.mode:
            self.problem(n, "run mode must match session-state.md: " + self.given.mode)
        elif field == "size" and v not in ("solo", "squad", "full"):
            self.problem(n, "run size must be solo, squad or full")

    def seat_row(self, n: int, ident: str, field: str, v: str) -> None:
        self.seats.setdefault(ident, "")
        if field == "disposition":
            if v not in ("selected", "skipped"):
                self.problem(n, "seat disposition must be selected or skipped")
            self.disp[ident] = v
        elif field == "role":
            if v not in ("chair", "worker", "verifier", "diagnosis"):
                self.problem(n, "seat role must be chair, worker or verifier (or diagnosis: a read-only worker "
                                "on a stuck task)")
            self.role[ident] = v
        elif field == "model":
            if v not in ("inherit", "sonnet", "haiku"):
                self.problem(n, "seat model must be inherit, sonnet or haiku")
            self.model[ident] = v
        elif field == "purpose":
            if v not in ("mapping", "survey", "other"):
                self.problem(n, "seat purpose must be mapping, survey or other")
            self.purpose[ident] = v
        else:
            self.problem(n, "unknown seat field: " + field)

    def budget_row(self, n: int, ident: str, field: str, value: Value) -> None:
        v = value.text
        if ident == "run":
            self.run_budget(n, field, value)
        elif field == "agent-runs":                  # a Workflow seat starts several agents
            if not value.whole() or value.below(1) or value.above(1000):
                self.problem(n, "agent-runs must be an integer from 1 to 1000")
            self.aruns[ident] = number(v)
        else:
            if field != "tool-calls":
                self.problem(n, "unknown seat budget field: " + field)
            elif not value.whole() or value.below(1) or value.above(200):
                self.problem(n, "tool-calls must be an integer from 1 to 200")
            self.calls[ident] = v

    def run_budget(self, n: int, field: str, value: Value) -> None:
        v = value.text
        if field == "agent-cap":
            if not value.whole() or value.below(1):
                self.problem(n, "agent-cap must be a positive integer")
            elif value.above(self.given.cap) and not self.under_go(number(v)):
                self.problem(n, "agent-cap %s exceeds the configured cap %d%s" % (v, self.given.cap, self.go_words()))
            self.plan_cap = number(v)
        elif field == "estimated-tokens":
            if not value.whole():
                self.problem(n, "estimated-tokens must be a non-negative integer")
        elif field == "token-ceiling":
            if not value.whole() or value.below(1):
                self.problem(n, "token-ceiling must be a positive integer")
        elif field == "chair-tokens":                # the Chair's own share: agents are compared with the rest
            if not value.whole():
                self.problem(n, "chair-tokens must be a non-negative integer — the Chair's own share of "
                                "estimated-tokens")
            else:
                self.chair = (number(v), n)
        else:
            self.problem(n, "unknown run budget field: " + field)

    def finish(self) -> Verdict:
        """The plan-wide rules, once every row is read."""
        if not self.got_header:
            self.problem(0, "missing header")
        for key, label in REQUIRED:
            if key not in self.val:
                self.problem(0, "missing %s row (%s)" % (label, "/".join(key)))
        tally = self.seat_rules()
        estimate = self.val.get(("budget", "run", "estimated-tokens"))
        if self.chair and estimate is not None and DIGITS.fullmatch(estimate) and self.chair[0] > number(estimate):
            self.problem(self.chair[1], "chair-tokens %s is more than the whole estimate (%s)"
                         % (number_text(self.chair[0]), estimate))
        if tally.selected + tally.skipped == 0:
            self.problem(0, "add at least one considered seat with a selected or skipped disposition")
        self.placement_rules()
        self.size_rules(tally)
        return Verdict(self.problems, self.valid_line(tally))

    def seat_rules(self) -> Tally:
        """Each considered seat's own rows, counting the selected, the skipped, the Chairs and the agent runs."""
        for ident in self.seats:
            if ident not in self.disp:
                self.problem(0, "seat %s has no disposition row" % ident)
            if ident not in self.role:
                self.problem(0, "seat %s has no role row" % ident)
        tally = Tally()
        for ident, disposition in self.disp.items():
            role = self.role.get(ident, "")
            if ident not in self.role:
                self.problem(0, "seat %s has no role row" % ident)
            if disposition != "selected":
                tally.skipped += 1
                if ident in self.ctx:
                    self.problem(self.at.get(("context", ident, "level"), 0),
                                 "skipped seat %s must not receive context" % ident)
                if ident in self.calls:
                    self.problem(self.at.get(("budget", ident, "tool-calls"), 0),
                                 "skipped seat %s must not receive a tool-call budget" % ident)
                continue
            tally.selected += 1
            if ident not in self.ctx:
                self.problem(0, "selected seat %s has no context/level row" % ident)
            if ident not in self.calls:
                self.problem(0, "selected %s %s has no budget/tool-calls row" % (role, ident))
            if role == "chair":
                tally.chairs += 1
                if ident in self.aruns:
                    self.problem(self.at[("budget", ident, "agent-runs")],
                                 "the Chair is not an agent run — remove budget/%s/agent-runs" % ident)
            else:
                tally.agents += 1
                tally.runs += self.aruns.get(ident, 1.0)
                tally.verifiers += role == "verifier"
        return tally

    def placement_rules(self) -> None:
        """Context, budgets, purposes and models belong only to the seats that may have them."""
        def selected(ident: str) -> bool:
            return self.disp.get(ident) == "selected"
        for ident in self.ctx:
            if not selected(ident):
                self.problem(self.at.get(("context", ident, "level"), 0),
                             "context belongs only to a selected seat: " + ident)
        for ident in self.calls:
            if not selected(ident):
                self.problem(self.at.get(("budget", ident, "tool-calls"), 0),
                             "a seat budget belongs only to a selected seat: " + ident)
        for ident in self.aruns:
            if not selected(ident):
                self.problem(self.at[("budget", ident, "agent-runs")],
                             "a seat budget belongs only to a selected seat: " + ident)
        for ident in self.purpose:
            if not selected(ident) or self.role.get(ident, "") != "worker":
                self.problem(self.at[("seat", ident, "purpose")],
                             "a purpose belongs only to a selected worker seat: " + ident)
        for ident, model in self.model.items():
            line = self.at[("seat", ident, "model")]
            if not selected(ident):
                self.problem(line, "a model choice belongs only to a selected seat: " + ident)
            elif model != "inherit":
                if self.role.get(ident, "") != "worker":
                    self.problem(line, "only worker seats can use sonnet or haiku; %s has role %s"
                                 % (ident, self.role.get(ident, "")))
                if self.given.seat_models == "off":
                    self.problem(line, "seat model overrides are off; enable seat models: on in council.config.md")
                if self.purpose.get(ident, "") not in ("mapping", "survey"):
                    self.problem(line, "sonnet or haiku needs seat/%s/purpose = mapping or survey" % ident)

    def size_rules(self, tally: Tally) -> None:
        """One Chair; the run size's agents; the verification level's verifier; the cap on agent runs."""
        if tally.chairs != 1:
            self.problem(0, "select exactly one Chair; found %d" % tally.chairs)
        size = self.val.get(("run", "run", "size"), "")
        verification = self.val.get(("verification", "run", "level"), "")
        if size == "solo" and tally.agents != 0:
            self.problem(0, "Solo must not select delegated agents")
        if size == "squad" and tally.agents < 1:
            self.problem(0, "Squad needs at least one selected agent")
        if size == "full" and tally.agents < 4:
            self.problem(0, "Full needs at least four selected agents")
        if size == "full" and not self.given.full_go:
            self.problem(0, "Full needs the user's explicit size-and-cost go: ask them, then record their words with "
                            "council state decision=\"…\"")
        if verification in ("independent", "adversarial") and tally.verifiers < 1:
            self.problem(0, verification + " verification needs a selected verifier")
        if verification == "self" and tally.verifiers > 0:
            self.problem(0, "self verification conflicts with a selected verifier")
        if self.plan_cap > 0 and tally.runs > self.plan_cap and not self.under_go(tally.runs):
            self.problem(0, "%s planned agent runs exceed the plan cap %s%s (a Workflow seat counts every agent it "
                            "starts: budget/<seat>/agent-runs)"
                         % (number_text(tally.runs), number_text(self.plan_cap), self.go_words()))

    def valid_line(self, tally: Tally) -> str:
        """'plan: valid · squad · 3 selected, 5 skipped · 2 agent run(s) of cap 10', and the user's go when used."""
        went = ""
        if self.plan_cap > 0 and (tally.runs > self.plan_cap or self.plan_cap > self.given.cap):
            went = " — past the cap under the user's go, up to %s (council cap allow)" % (
                "" if self.given.go is None else self.given.go)
        return "plan: valid · %s · %d selected, %d skipped · %d agent run(s) of cap %d%s" % (
            self.val.get(("run", "run", "size"), ""), tally.selected, tally.skipped, tally.runs, self.plan_cap, went)


class Tally:
    """The plan's seats counted: selected and skipped, and of the selected, Chairs, agents and verifiers."""

    def __init__(self) -> None:
        self.selected = self.skipped = self.chairs = self.agents = self.verifiers = 0
        self.runs = 0.0                               # agent runs: a Workflow seat counts each agent it starts


REQUIRED = ((("schema", "plan", "version"), "schema version"), (("run", "run", "id"), "run id"),
            (("run", "run", "mode"), "run mode"), (("run", "run", "size"), "run size"),
            (("assessment", "run", "risk"), "risk assessment"), (("assessment", "run", "complexity"),
            "complexity assessment"), (("assessment", "run", "uncertainty"), "uncertainty assessment"),
            (("budget", "run", "agent-cap"), "agent cap"), (("budget", "run", "estimated-tokens"), "token estimate"),
            (("verification", "run", "level"), "verification level"))
