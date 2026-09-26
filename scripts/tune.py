#!/usr/bin/env python3
"""Conservative, inspectable self-tuning: proposals from the project's own record, a change only on
the user's words, every change logged and reversible.

`propose` reads the history (scripts/history.py) and the seat advice (scripts/ledger.py), and sorts
every knob into one of three kinds:
- **budget** — the estimate per worker that `council route recommend` budgets with. It is the only
  knob this command changes. It is proposed when five completed runs measure tokens per worker and
  the estimate is off by more than a quarter.
- **roster** — seats whose advice clears its bar. These change only through a council-init refresh,
  with the numbers shown.
- **held** — behaviour: context packs, run size, verification depth. None is ever proposed without a
  benchmark result showing the change helps, and no such result exists yet.

`apply budget` writes the value into council.config.md's ## Run preferences, and `revert budget`
restores what was there before. Both require the user's words (`--said`, already redacted by the
helper) and append a dated entry to .council/tuning.md. Nothing else is ever written.
"""

import argparse
import datetime
import json
import os
from pathlib import Path
import re
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import history  # noqa: E402
import ledger   # noqa: E402

SCHEMA = "council.tune/1"
DEFAULT_PER_WORKER = 80000      # the route's no-history estimate
OFF_BY = 0.25                   # a measured median this far from the estimate is worth a proposal
KNOB = "estimate per worker"
LINE = re.compile(r"^([ \t]*-[ \t]*estimate per worker:[ \t]*)([0-9][0-9.,]*[ \t]*[kKmM]?)([^\r\n]*)$", re.MULTILINE)
ENTRY = re.compile(r"^## T-(\d+) · (\S+) · (applied|reverted T-\d+) · estimate per worker: (\S+) → (\S+)\s*$",
                   re.MULTILINE)
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
HELD = (
    ("context-packs", "context packs (off unless the config says on)",
     "no paired run shows packs change findings or tokens; the Phase 5.5 live comparison is deferred"),
    ("run-size", "how large a council convenes for a task",
     "no benchmark compares council sizes on the same tasks"),
    ("verification", "how deep verification goes",
     "no benchmark compares verification depths on the same tasks"),
)


class TuneError(Exception):
    """A tuning step that must not happen."""


def tokens(text):
    """'150k', '150000', '1.2M' → an int; None when unreadable or implausible."""
    match = re.fullmatch(r"([0-9][0-9.,]*)[ \t]*([kKmM]?)", text.strip())
    if not match:
        return None
    try:
        value = float(match.group(1).replace(",", ""))
    except ValueError:
        return None
    value *= {"k": 1000, "m": 1000000}.get(match.group(2).lower(), 1)
    value = int(round(value))
    return value if 1000 <= value <= 5000000 else None


def k(value):
    return "{}k".format(round(value / 1000)) if value else "none"


def read_config(home):
    path = Path(home) / "council.config.md"
    if path.is_symlink():
        raise TuneError("council.config.md is a link — change the file it points to by hand")
    if not path.is_file():
        raise TuneError("no council.config.md in {} — run council-init".format(home))
    raw = path.read_bytes()
    if len(raw) > 1024 * 1024:
        raise TuneError("council.config.md is over 1 MB; refusing to edit it")
    text = raw.decode("utf-8")
    return path, text


def configured(text):
    match = LINE.search(text.replace("\r\n", "\n"))
    return tokens(match.group(2)) if match else None


def proposals(home):
    home = Path(home)
    _, text = read_config(home)
    data = history.history(home)
    current = configured(text)
    estimate = current or DEFAULT_PER_WORKER
    worker = data["cost"]["tokens_per_worker"]
    budget = {"id": "budget", "kind": "budget", "knob": KNOB, "current": current, "default": DEFAULT_PER_WORKER}
    if not worker["enough"]:
        budget.update(status="waiting", why="too few completed runs with workers to measure it ({} of {} needed)".format(
            worker["n"], history.MIN_RUNS))
    else:
        median = worker["median"]
        proposed = max(5000, int(round(median / 5000.0)) * 5000)
        off = abs(median - estimate) / estimate
        evidence = "median {} tokens per worker over {} completed runs (10–90%: {}–{})".format(
            k(median), worker["n"], k(worker["p10"]), k(worker["p90"]))
        ratio = data["estimates"]["actual_over_estimate"]
        if ratio["enough"]:
            evidence += "; runs cost {:.2f}× their plan's estimate at the median".format(ratio["median"])
        if off <= OFF_BY:
            budget.update(status="none", evidence=evidence,
                          why="the estimate ({}) is within a quarter of what workers measure".format(k(estimate)))
        else:
            budget.update(status="proposed", value=proposed, evidence=evidence,
                          why="the route budgets {} per worker; this project's workers measure {}".format(
                              k(estimate), k(median)))
    seats = ledger.report(home / "ledger.tsv", 20)
    roster = [{"id": "roster:" + s["seat"], "kind": "roster", "seat": s["seat"], "status": "refresh",
               "advice": s["advice"], "why": s["reason"]}
              for s in seats["seats"] if s.get("weighed") and s["advice"] in ("lower", "narrow", "pair", "drop?")]
    held = [{"id": ident, "kind": "held", "knob": knob, "status": "held", "why": why} for ident, knob, why in HELD]
    return {"schema": SCHEMA, "home": str(home), "budget": budget, "roster": roster, "held": held,
            "log": [dict(zip(("n", "date", "action", "before", "after"), entry)) for entry in log_entries(home)]}


def render(data):
    b = data["budget"]
    lines = ["council tune · proposals from this project's own record; nothing changes without the user's words", ""]
    head = "budget — {}: {} (the route's default is {})".format(
        b["knob"], k(b["current"]) if b["current"] else "not set", k(b["default"]))
    lines.append(head)
    if b["status"] == "proposed":
        lines.append("  PROPOSED: set it to {} — {}".format(k(b["value"]), b["why"]))
        lines.append("  evidence: " + b["evidence"])
        lines.append('  on the user\'s yes: council tune apply budget --user-said "<their words>"')
    elif b["status"] == "none":
        lines.append("  no change: " + b["why"] + " · " + b["evidence"])
    else:
        lines.append("  waiting: " + b["why"])
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
        lines.append("")
        lines.append("changes so far (.council/tuning.md): " + " · ".join(
            "T-{} {} {} → {}".format(e["n"], e["action"], e["before"], e["after"]) for e in data["log"]))
    return "\n".join(lines)


# --- the one write path ---------------------------------------------------------------------------------------
def log_entries(home):
    path = Path(home) / "tuning.md"
    if not path.is_file() or path.is_symlink():
        return []
    return ENTRY.findall(path.read_text(encoding="utf-8", errors="replace"))


def said_words(path):
    words = CONTROL.sub(" ", Path(path).read_text(encoding="utf-8", errors="replace")).strip()
    words = re.sub(r"\s+", " ", words).replace('"', "'").replace("`", "'")
    if not words:
        raise TuneError("the user's words are empty — quote their answer")
    return words[:400]


def set_line(text, value):
    """The config with its estimate-per-worker line set to value (None removes it), in ## Run preferences."""
    newline = "\r\n" if text.count("\r\n") * 2 > text.count("\n") else "\n"
    existing = re.compile(r"^([ \t]*-[ \t]*estimate per worker:[ \t]*)([0-9][0-9.,]*[ \t]*[kKmM]?)([^\r\n]*?)(\r?)$",
                          re.MULTILINE)
    if existing.search(text):
        if value is None:
            return re.sub(r"^[ \t]*-[ \t]*estimate per worker:[^\r\n]*(?:\r?\n)?", "", text, count=1, flags=re.MULTILINE)
        return existing.sub(lambda m: m.group(1) + k(value) + m.group(3) + m.group(4), text, count=1)
    if value is None:
        return text
    section = re.search(r"^## Run preferences[ \t]*\r?$", text, re.MULTILINE)
    if not section:
        raise TuneError("council.config.md has no ## Run preferences section — a council-init refresh adds one")
    rest = text[section.end():]
    end = re.search(r"^## ", rest, re.MULTILINE)
    body = rest[:end.start()] if end else rest
    items = list(re.finditer(r"^[ \t]*-[^\r\n]*(?:\r?\n|\Z)", body, re.MULTILINE))
    if items:
        at = section.end() + items[-1].end()
    else:
        heading_end = re.match(r"\r?\n", rest)
        at = section.end() + (heading_end.end() if heading_end else 0)
    line = "- {}: {}".format(KNOB, k(value))
    if at >= len(text) and not text.endswith("\n"):
        return text + newline + line + newline
    return text[:at] + line + newline + text[at:]


def atomic_write(path, text):
    fd, temp = tempfile.mkstemp(prefix=".council-tune-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(temp, str(path))
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise


def record(home, action, before, after, words, evidence=""):
    path = Path(home) / "tuning.md"
    if path.is_symlink():
        raise TuneError("tuning.md is a link — refusing to write through it")
    text = path.read_text(encoding="utf-8") if path.is_file() else (
        "# Tuning log\n\nEach change `council tune` made to council.config.md, with its evidence and the user's own\n"
        "words. Undo one with `council tune revert budget --user-said \"…\"`.\n")
    number = max([int(e[0]) for e in ENTRY.findall(text)] + [0]) + 1
    entry = "\n## T-{} · {} · {} · {}: {} → {}\n".format(number, datetime.date.today().isoformat(), action, KNOB,
                                                      k(before), k(after))
    if evidence:
        entry += "- evidence: {}\n".format(evidence)
    entry += '- the user said: "{}"\n'.format(words)
    return path, text.rstrip("\n") + "\n" + entry, number


def apply(home, words):
    home = Path(home)
    found = proposals(home)["budget"]
    if found["status"] != "proposed":
        raise TuneError("nothing to apply: {}".format(found["why"]))
    path, text = read_config(home)
    before = configured(text)
    changed = set_line(text, found["value"])
    if configured(changed) != found["value"]:
        raise TuneError("the edited config would not read back as {} — nothing was written".format(k(found["value"])))
    log_path, log_text, number = record(home, "applied", before, found["value"], words, found["evidence"])
    atomic_write(log_path, log_text)
    atomic_write(path, changed)
    return "tune: T-{} applied — {} is now {} (was {}); undo with council tune revert budget".format(
        number, KNOB, k(found["value"]), k(before) if before else "not set")


def revert(home, words):
    home = Path(home)
    entries = log_entries(home)
    reverted = {int(a.split("T-")[1]) for _, _, a, _, _ in entries if a.startswith("reverted")}
    live = [e for e in entries if e[2] == "applied" and int(e[0]) not in reverted]
    if not live:
        raise TuneError("no applied change of the {} is left to revert (.council/tuning.md)".format(KNOB))
    number, _, _, before, after = live[-1]
    path, text = read_config(home)
    now = configured(text)
    if now != tokens(after):
        raise TuneError("the config says {} now, not the {} T-{} set — it was edited since; change it by hand".format(
            k(now) if now else "nothing", after, number))
    restored = tokens(before) if before != "none" else None
    changed = set_line(text, restored)
    if configured(changed) != restored:
        raise TuneError("the edited config would not read back as {} — nothing was written".format(before))
    log_path, log_text, n = record(home, "reverted T-{}".format(number), now, restored, words)
    atomic_write(log_path, log_text)
    atomic_write(path, changed)
    return "tune: T-{} reverted T-{} — {} is {} again".format(n, number, KNOB, before if restored else "not set")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("propose", "apply", "revert"))
    parser.add_argument("knob", nargs="?")
    parser.add_argument("--home", required=True, type=Path)
    parser.add_argument("--said", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.action == "propose":
        data = proposals(args.home)
        print(json.dumps(data, indent=2, sort_keys=True) if args.json else render(data))
        return 0
    if args.knob != "budget":
        if args.knob and args.knob.startswith("roster"):
            raise TuneError("a roster change goes through a council-init refresh, with the numbers shown")
        if args.knob in {h[0] for h in HELD}:
            raise TuneError("{} is held: no benchmark shows that changing it helps".format(args.knob))
        raise TuneError("the only knob tune changes is budget (the estimate per worker)")
    if not args.said:
        raise TuneError("the user's words are required")
    words = said_words(args.said)
    print(apply(args.home, words) if args.action == "apply" else revert(args.home, words))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (TuneError, ledger.LedgerError, OSError, UnicodeError, ValueError) as exc:
        print("tune: " + str(exc), file=sys.stderr)
        sys.exit(2)
