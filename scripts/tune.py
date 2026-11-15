#!/usr/bin/env python3
"""Conservative, inspectable self-tuning: proposals from the project's own record, a change only on
the user's words, every change logged and reversible.

`propose` reads the history (scripts/history.py) and the seat advice (scripts/ledger.py), and sorts
every knob into one of three kinds:
- **budget** — the estimate per worker that `council route recommend` budgets with. It is the only
  knob this command changes. It is proposed when five completed runs measure tokens per agent and
  the estimate is off by more than a quarter.
- **roster** — seats whose advice clears its bar. These change only through a council-init refresh,
  with the numbers shown.
- **held** — behaviour: run size, verification depth. None is ever proposed without a
  benchmark result showing the change helps, and no such result exists yet.

`apply budget <value>` writes the value the user was shown into council.config.md's ## Run
preferences — refusing if the record now proposes another — and `revert budget` puts back exactly
the bytes that were there before. Both require the user's words (`--said`, already redacted by the
helper) and append a dated entry, with the exact line it replaced, to .council/tuning.md. The log and
the config are written as a pair: if the config cannot be written, the log is put back.
"""

import argparse
import datetime
import json
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import history  # noqa: E402
import ledger   # noqa: E402
from council.records import config, estimates, paths  # noqa: E402
from council.records import ledger as ledger_file, usage_gaps  # noqa: E402
from council.records.tuning import TuningError as TuneError, log_entries, said_words, write_pair  # noqa: E402
from council.records.config import ESTIMATE_LINES as LINES, ESTIMATE_PARTS as PARTS  # noqa: E402
from council.records.config import estimate_line as configured, estimate_tokens as tokens  # noqa: E402

SCHEMA = "council.tune/2"
DEFAULT_PER_WORKER = 80000      # the route's no-history estimate
MAX_PER_WORKER = config.MAX_PER_WORKER   # the most either reader accepts; the route treats more as unset
OFF_BY = 0.25                   # a measured median this far from the estimate is worth a proposal
KNOB = "estimate per worker"
HELD = (
    ("run-size", "how large a council convenes for a task",
     "no benchmark compares council sizes on the same tasks"),
    ("verification", "how deep verification goes",
     "no benchmark compares verification depths on the same tasks"),
)


def k(value):
    return "{}k".format(round(value / 1000)) if value else "none"


def shown_before(value, line):
    return k(value) if value else ("unreadable" if line else "none")


def rounded(median):
    """A measured median as the figure to propose: the nearest 5k, from 5k to the most the route reads."""
    return min(MAX_PER_WORKER, max(5000, int(round(median / 5000.0)) * 5000))


def role_entry(role, text, costs, estimate):
    """One role's proposal, on the budget's rules: five runs measure it, and it is off by more than a quarter."""
    current, spread = estimates.figure(text, role), history.spread(costs.get(role, []))
    entry = {"id": "budget:" + role, "kind": "budget", "role": role, "current": current,
             "lines": len(estimates.LINES.findall(text))}
    if not spread["enough"]:
        return dict(entry, status="waiting", why="too few completed runs with a {} to measure it ({} of {} needed)".format(
            role, spread["n"], history.MIN_RUNS))
    median, base = spread["median"], current or estimate
    entry["evidence"] = "median {} per {} over {} completed runs (10–90%: {}–{})".format(
        k(median), "run" if role in ("verifier", "converge") else "agent", spread["n"], k(spread["p10"]), k(spread["p90"]))
    if abs(median - base) / base <= OFF_BY:
        return dict(entry, status="none", why="the estimate ({}) is within a quarter of what the {} measures".format(k(base), role))
    return dict(entry, status="proposed", value=rounded(median), why="the route budgets {} for the {}; this project's {} measures {}".format(
        k(base), role, role, k(median)))


def role_entries(home, text, estimate):
    """Each role's proposal, from what the ledger says it cost."""
    costs = estimates.measured(ledger_file.read(ledger_file.path(home))[0] or [])
    return {role: role_entry(role, text, costs, estimate) for role in estimates.ROLES}


def proposals(home):
    home = Path(home)
    _, text = config.editable(home)
    data = history.history(home, outcomes=False)   # tune never reads finding outcomes: skip their Git work
    current, line = configured(text)
    estimate = current or DEFAULT_PER_WORKER
    worker = data["cost"]["tokens_per_agent"]
    budget = {"id": "budget", "kind": "budget", "knob": KNOB, "current": current, "default": DEFAULT_PER_WORKER,
              "line": line, "lines": len(LINES.findall(text)), "unfigured": data["cost"]["unfigured"]}
    if not worker["enough"]:
        left = sum((data["cost"].get("left_out") or {}).values())
        budget.update(status="waiting", why="too few completed runs with agents to measure it ({} of {} needed{})".format(
            worker["n"], history.MIN_RUNS,
            "; {} more left out for incomplete records".format(left) if left else ""))
    else:
        median = worker["median"]
        off = abs(median - estimate) / estimate
        evidence = ("median {} tokens per agent over {} completed runs (10–90%: {}–{}); {} runs make this "
                    "eligible, not reliable").format(k(median), worker["n"], k(worker["p10"]), k(worker["p90"]),
                                                     history.MIN_RUNS)
        left = data["cost"].get("left_out") or {}
        if left:
            evidence += "; {} completed run(s) left out for incomplete records".format(sum(left.values()))
        ratio = data["estimates"]["actual_over_estimate"]
        if ratio["enough"]:
            evidence += "; agents cost {:.2f}× their plan's estimate at the median".format(ratio["median"])
        if off <= OFF_BY and (current or not line):
            budget.update(status="none", evidence=evidence,
                          why="the estimate ({}) is within a quarter of what agents measure".format(k(estimate)))
        else:
            budget.update(status="proposed", value=rounded(median), evidence=evidence,
                          why="the route budgets {} per agent; this project's agents measure {}".format(
                              k(estimate), k(median)))
    roles = role_entries(home, text, estimate)
    seats = ledger.report(ledger_file.path(home), 20)
    roster = [{"id": "roster:" + s["seat"], "kind": "roster", "seat": s["seat"], "status": "refresh",
               "advice": s["advice"], "why": s["reason"]}
              for s in seats["seats"] if s.get("weighed") and s["advice"] in ("lower", "narrow", "pair", "drop?")]
    held = [{"id": ident, "kind": "held", "knob": knob, "status": "held", "why": why} for ident, knob, why in HELD]
    return {"schema": SCHEMA, "home": str(home), "budget": budget, "roles": roles, "roster": roster, "held": held,
            "log": [{"n": e["n"], "action": e["action"], "before": e["before"], "after": e["after"]}
                    for e in log_entries(home)]}


def brief(data):
    """The close's follow-up (council run close): one plain line when the record has a proposal for the user."""
    parts = []
    if data["budget"]["status"] == "proposed":
        parts.append("the estimate per worker can be tuned to {} (council tune shows the evidence)".format(k(data["budget"]["value"])))
    parts += ["the {} estimate can be tuned to {} (council tune shows the evidence)".format(r["role"], k(r["value"]))
              for r in data["roles"].values() if r["status"] == "proposed"]
    if data["roster"]:
        parts.append("{} seat(s) clear the bar for a roster change (council tune)".format(len(data["roster"])))
    return "; ".join(parts)


def render_roles(roles):
    """The per-role estimates: each role's figure and status, and a proposal with its evidence and the command."""
    lines = ["estimates — one per role (- estimates: in council.config.md); a role with none takes the estimate per worker:"]
    for r in roles.values():
        lines.append("  {}: {} — {}".format(r["role"], k(r["current"]) if r["current"] else "not set", r["status"]))
        if r["status"] == "proposed":
            lines.append("    PROPOSED: set it to {} — {}".format(k(r["value"]), r["why"]))
            lines.append("    evidence: " + r["evidence"])
            lines.append("    on the user's yes: council tune apply budget:{} {} --user-said \"<their words>\"".format(
                r["role"], k(r["value"])))
        elif r["status"] == "waiting":
            lines.append("    " + r["why"])
    return lines


def render(data):
    b = data["budget"]
    lines = ["council tune · proposals from this project's own record; nothing changes without the user's words", ""]
    if b["current"]:
        now = k(b["current"])
    elif b["line"]:
        now = "set to something the route cannot read ({!r}), so it budgets {}".format(b["line"].strip()[:60], k(b["default"]))
    else:
        now = "not set"
    lines.append("budget — {}: {} (the route's default is {})".format(b["knob"], now, k(b["default"])))
    if b["lines"] > 1:
        lines.append("  note: council.config.md has {} estimate-per-worker lines; keep one".format(b["lines"]))
    if b["status"] == "proposed":
        lines.append("  PROPOSED: set it to {} — {}".format(k(b["value"]), b["why"]))
        lines.append("  evidence: " + b["evidence"])
        lines.append('  on the user\'s yes: council tune apply budget {} --user-said "<their words>"'.format(k(b["value"])))
    elif b["status"] == "none":
        lines.append("  no change: " + b["why"] + " · " + b["evidence"])
    else:
        lines.append("  waiting: " + b["why"])
    lines.extend("  note: " + note for note in usage_gaps.note(b["unfigured"]))
    lines.append("")
    lines.extend(render_roles(data["roles"]))
    lines.append("")
    if data["roster"]:
        lines.append("roster — changed only through a council-init refresh, with the numbers shown:")
        for r in data["roster"]:
            lines.append("  {}: {} — {}".format(r["seat"], r["advice"], r["why"]))
    else:
        lines.append("roster — no seat's record clears the bar for a change (council ledger advice)")
    lines.append("")
    lines.append("held — behaviour is never tuned without a benchmark that shows the change helps:")
    for h in data["held"]:
        lines.append("  {}: {}".format(h["knob"], h["why"]))
    if data["log"]:
        lines.extend(("", "changes so far (.council/tuning.md): " + " · ".join(
            "T-{} {} {} → {}".format(e["n"], e["action"], e["before"], e["after"]) for e in data["log"])))
    return "\n".join(lines)


def budget_edit(text, want):
    """The config text with the estimate per worker set to want, and the record that undoes it."""
    found = LINES.search(text)
    if found:
        prefix, old_value, rest = PARTS.match(found.group(0)).groups()
        after = prefix + k(want) + rest if old_value else prefix.rstrip() + " " + k(want)
        return text[:found.start()] + after + text[found.end():], {"before": found.group(0), "after": after, "inserted": None}
    after = "- {}: {}".format(KNOB, k(want))
    at, inserted = config.preferences_insertion(text, after)
    return text[:at] + inserted + text[at:], {"before": None, "after": after, "inserted": inserted}


def setting(role):
    """The knob `budget` (the estimate per worker) or `budget:<role>` names: its name in the log, how its line is
    called in a refusal, the pattern of its line, read(text) -> (value, line) and edit(text, want) -> (text, record)."""
    if role is None:
        return KNOB, "estimate-per-worker", LINES, configured, budget_edit
    return ("estimates " + role, "- estimates:", estimates.LINES, lambda text: (estimates.figure(text, role), None),
            lambda text, want: estimates.with_role(text, role, k(want)))


def apply(home, words, value_text, role=None):
    home = Path(home)
    name, label, pattern, read, edit = setting(role)
    want = tokens(value_text)
    if want is None:
        raise TuneError("give the value the user was shown, such as 150k (between 1k and {})".format(k(MAX_PER_WORKER)))
    data = proposals(home)
    found = data["budget"] if role is None else data["roles"][role]
    if found["status"] != "proposed":
        raise TuneError("nothing to apply: {}".format(found["why"]))
    if found["value"] != want:
        raise TuneError("the record now proposes {}, not the {} the user was shown — run council tune and ask "
                        "again".format(k(found["value"]), k(want)))
    path, text = config.editable(home)
    if len(pattern.findall(text)) > 1:
        raise TuneError("council.config.md has {} {} lines — keep one by hand first".format(len(pattern.findall(text)), label))
    before_value, before_line = read(text)
    changed, record = edit(text, want)
    if read(changed)[0] != want or len(pattern.findall(changed)) != 1:
        raise TuneError("the edited config would not read back as {} — nothing was written".format(k(want)))
    shown = shown_before(before_value, before_line)
    number = write_pair(home, ["## T-? · {} · applied · {}: {} → {}".format(
        datetime.date.today().isoformat(), name, shown, k(want)),
        "- evidence: {}".format(found["evidence"]), '- the user said: "{}"'.format(words),
        "- exact: " + json.dumps(record, sort_keys=True)], path, changed)
    return "tune: T-{} applied — {} is now {} (was {}); undo with council tune revert budget{}".format(
        number, name, k(want), shown, ":" + role if role else "")


def exact_ok(record, pattern):
    """Whether a log entry's exact record is intact: the line it wrote, and the one it replaced or inserted."""
    if not isinstance(record, dict) or not isinstance(record.get("after"), str) or not pattern.fullmatch(record["after"]):
        return False
    before, inserted = record.get("before"), record.get("inserted")
    if before is not None and not (isinstance(before, str) and pattern.fullmatch(before)):
        return False
    return inserted is None or (isinstance(inserted, str) and inserted.strip("\r\n") == record["after"])


def revert(home, words, role=None):
    home = Path(home)
    name, label, pattern, read, _ = setting(role)
    entries = log_entries(home)
    reverted = {int(e["action"].split("T-")[1]) for e in entries if e["action"].startswith("reverted")}
    live = [e for e in entries if e["action"] == "applied" and e["n"] not in reverted and e["knob"] == name]
    if not live:
        raise TuneError("no applied change of the {} is left to revert (.council/tuning.md)".format(name))
    entry = live[-1]
    record = entry["exact"]
    if not exact_ok(record, pattern):
        raise TuneError("T-{}'s exact record in tuning.md is missing or was edited — change the config by hand".format(entry["n"]))
    path, text = config.editable(home)
    matches = list(pattern.finditer(text))
    if len(matches) != 1 or matches[0].group(0) != record["after"]:
        raise TuneError("the config's estimate line is not the one T-{} wrote ({!r}) — it was edited since; change it "
                        "by hand".format(entry["n"], record["after"]))
    if record["inserted"] is not None:
        if text.count(record["inserted"]) != 1:
            raise TuneError("the line T-{} added is no longer where it was — change the config by hand".format(entry["n"]))
        restored = text.replace(record["inserted"], "", 1)
    else:
        restored = text[:matches[0].start()] + record["before"] + text[matches[0].end():]
    before_value, before_line = read(restored)
    shown = shown_before(before_value, before_line)
    number = write_pair(home, ["## T-? · {} · reverted T-{} · {}: {} → {}".format(
        datetime.date.today().isoformat(), entry["n"], name, entry["after"], shown),
        '- the user said: "{}"'.format(words)], path, restored)
    return "tune: T-{} reverted T-{} — {} is {} again".format(
        number, entry["n"], name, shown if before_line or before_value else "not set")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("propose", "apply", "revert"))
    parser.add_argument("knob", nargs="?")
    parser.add_argument("--home", required=True, type=Path)
    parser.add_argument("--said", type=Path)
    parser.add_argument("--value")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--brief", action="store_true", help="one plain line when there is a proposal, else nothing")
    args = parser.parse_args()
    if args.action == "propose":
        data = proposals(args.home)
        if args.brief:
            line = brief(data)
            if line:
                print(line)
            return 0
        print(json.dumps(data, indent=2, sort_keys=True) if args.json else render(data))
        return 0
    knob, _, role = (args.knob or "").partition(":")
    if knob != "budget":
        if args.knob and args.knob.startswith("roster"):
            raise TuneError("a roster change goes through a council-init refresh, with the numbers shown")
        if args.knob in {h[0] for h in HELD}:
            raise TuneError("{} is held: no benchmark shows that changing it helps".format(args.knob))
        raise TuneError("the only knob tune changes is budget (the estimate per worker)")
    if role and role not in estimates.ROLES:
        raise TuneError("a role's estimate is one of: " + ", ".join(estimates.ROLES))
    if not args.said:
        raise TuneError("the user's words are required")
    words = said_words(args.said)
    if args.action == "apply":
        if not args.value:
            raise TuneError("apply needs the value the user was shown: council tune apply budget <value>")
        print(apply(args.home, words, args.value, role or None))
    else:
        print(revert(args.home, words, role or None))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (TuneError, paths.RecordError, OSError, UnicodeError, ValueError) as exc:
        print("tune: " + str(exc), file=sys.stderr)
        sys.exit(2)
