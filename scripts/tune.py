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
- **held** — behaviour: context packs, run size, verification depth. None is ever proposed without a
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
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import history  # noqa: E402
import ledger   # noqa: E402

SCHEMA = "council.tune/2"
DEFAULT_PER_WORKER = 80000      # the route's no-history estimate
MAX_PER_WORKER = 1000000        # the most either reader accepts; the route treats more as unset
OFF_BY = 0.25                   # a measured median this far from the estimate is worth a proposal
KNOB = "estimate per worker"
BOM = chr(0xFEFF)
LINES = re.compile(r"^[ \t]*-[ \t]*estimate per worker:[^\r\n]*", re.MULTILINE)
PARTS = re.compile(r"([ \t]*-[ \t]*estimate per worker:[ \t]*)([0-9][0-9.,]*[ \t]*[kKmM]?)?(.*)$")
ENTRY = re.compile(r"^## T-(\d+) · (\S+) · (applied|reverted T-\d+) · estimate per worker: (\S+) → (\S+)[ \t]*\r?$",
                   re.MULTILINE)
EXACT = re.compile(r"^- exact: (\{.*\})[ \t]*\r?$", re.MULTILINE)
CONTROL = re.compile("[" + chr(0) + "-" + chr(0x1F) + chr(0x7F) + "-" + chr(0x9F) + chr(0x2028) + chr(0x2029) + "]")
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
    """'150k', '150000', '1.2M' → an int; None when unreadable or outside 1k–1M, as the route reads it."""
    match = re.fullmatch(r"([0-9][0-9.,]*)[ \t]*([kKmM]?)", str(text).strip())
    if not match:
        return None
    try:
        value = float(match.group(1).replace(",", ""))
    except ValueError:
        return None
    value = int(round(value * {"k": 1000, "m": 1000000}.get(match.group(2).lower(), 1)))
    return value if 1000 <= value <= MAX_PER_WORKER else None


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
    return path, raw.decode("utf-8")


def configured(text):
    """(value, the exact line) of the first estimate line; value None when the line is unreadable."""
    found = LINES.search(text)
    if not found:
        return None, None
    value = PARTS.match(found.group(0)).group(2)
    return (tokens(value) if value else None), found.group(0)


def shown_before(value, line):
    return k(value) if value else ("unreadable" if line else "none")


def proposals(home):
    home = Path(home)
    _, text = read_config(home)
    data = history.history(home)
    current, line = configured(text)
    estimate = current or DEFAULT_PER_WORKER
    worker = data["cost"]["tokens_per_agent"]
    budget = {"id": "budget", "kind": "budget", "knob": KNOB, "current": current, "default": DEFAULT_PER_WORKER,
              "line": line, "lines": len(LINES.findall(text))}
    if not worker["enough"]:
        left = sum((data["cost"].get("left_out") or {}).values())
        budget.update(status="waiting", why="too few completed runs with agents to measure it ({} of {} needed{})".format(
            worker["n"], history.MIN_RUNS,
            "; {} more left out for incomplete records".format(left) if left else ""))
    else:
        median = worker["median"]
        proposed = min(MAX_PER_WORKER, max(5000, int(round(median / 5000.0)) * 5000))
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
            budget.update(status="proposed", value=proposed, evidence=evidence,
                          why="the route budgets {} per agent; this project's agents measure {}".format(
                              k(estimate), k(median)))
    seats = ledger.report(home / "ledger.tsv", 20)
    roster = [{"id": "roster:" + s["seat"], "kind": "roster", "seat": s["seat"], "status": "refresh",
               "advice": s["advice"], "why": s["reason"]}
              for s in seats["seats"] if s.get("weighed") and s["advice"] in ("lower", "narrow", "pair", "drop?")]
    held = [{"id": ident, "kind": "held", "knob": knob, "status": "held", "why": why} for ident, knob, why in HELD]
    return {"schema": SCHEMA, "home": str(home), "budget": budget, "roster": roster, "held": held,
            "log": [{"n": e["n"], "action": e["action"], "before": e["before"], "after": e["after"]}
                    for e in log_entries(home)]}


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
def read_log(home):
    path = Path(home) / "tuning.md"
    if path.is_symlink():
        raise TuneError("tuning.md is a link — refusing to read or write through it")
    return path, (path.read_bytes().decode("utf-8") if path.is_file() else None)


def log_entries(home):
    """Each logged change: its number, action, shown values and exact record (None when absent or bad)."""
    _, text = read_log(home)
    entries = []
    heads = list(ENTRY.finditer(text or ""))
    for i, head in enumerate(heads):
        body = text[head.end():heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        exact = EXACT.search(body)
        try:
            record = json.loads(exact.group(1)) if exact else None
        except ValueError:
            record = None
        entries.append({"n": int(head.group(1)), "date": head.group(2), "action": head.group(3),
                        "before": head.group(4), "after": head.group(5), "exact": record})
    return entries


def said_words(path):
    words = CONTROL.sub(" ", Path(path).read_text(encoding="utf-8", errors="replace")).strip()
    words = re.sub(r"\s+", " ", words).replace('"', "'").replace("`", "'")
    if not words:
        raise TuneError("the user's words are empty — quote their answer")
    return words[:400]


def insertion(text, line):
    """(offset, exact text) to add line as the last item of ## Run preferences, outside HTML comments."""
    newline = "\r\n" if text.count("\r\n") * 2 > text.count("\n") else "\n"
    section = re.search("^(?:" + BOM + r")?## Run preferences[ \t]*\r?$", text, re.MULTILINE)
    if not section:
        raise TuneError("council.config.md has no ## Run preferences section — a council-init refresh adds one")
    rest = text[section.end():]
    end = re.search(r"^## ", rest, re.MULTILINE)
    body = rest[:end.start()] if end else rest
    comments = [(m.start(), m.end()) for m in re.finditer(r"<!--.*?(?:-->|\Z)", body, re.DOTALL)]
    items = [m for m in re.finditer(r"^[ \t]*-[^\r\n]*(?:\r?\n|\Z)", body, re.MULTILINE)
             if not any(a <= m.start() < b for a, b in comments)]
    if items:
        at = section.end() + items[-1].end()
    else:
        heading_end = re.match(r"\r?\n", rest)
        at = section.end() + (heading_end.end() if heading_end else 0)
    if at >= len(text) and not text.endswith("\n"):
        return at, newline + line
    return at, line + newline


def current_umask():
    mask = os.umask(0)
    os.umask(mask)
    return mask


def atomic_write(path, text):
    """Replace path with text, keeping the file's permissions (a new file gets the usual ones)."""
    mode = stat.S_IMODE(os.stat(str(path)).st_mode) if path.exists() else 0o666 & ~current_umask()
    fd, temp = tempfile.mkstemp(prefix=".council-tune-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.chmod(temp, mode)
        os.replace(temp, str(path))
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise


def write_pair(home, entry_lines, config_path, config_text):
    """Append the entry to tuning.md, then replace the config; if the config cannot be written, the log
    is put back as it was, so it never records a change that did not happen."""
    log_path, old = read_log(home)
    base = old if old is not None else (
        "# Tuning log\n\nEach change `council tune` made to council.config.md, with its evidence, the user's own\n"
        "words, and the exact line it replaced. Undo the last one with\n"
        "`council tune revert budget --user-said \"…\"`.\n")
    newline = "\r\n" if base.count("\r\n") * 2 > base.count("\n") else "\n"
    number = max([e["n"] for e in log_entries(home)] + [0]) + 1
    entry = ["", entry_lines[0].replace("T-?", "T-{}".format(number), 1)] + entry_lines[1:]
    text = base.rstrip("\r\n") + newline + newline.join(entry) + newline
    atomic_write(log_path, text)
    try:
        atomic_write(config_path, config_text)
    except BaseException:
        if old is None:
            try:
                log_path.unlink()
            except OSError:
                pass
        else:
            atomic_write(log_path, old)
        raise
    return number


def apply(home, words, value_text):
    home = Path(home)
    want = tokens(value_text)
    if want is None:
        raise TuneError("give the value the user was shown, such as 150k (between 1k and {})".format(k(MAX_PER_WORKER)))
    found = proposals(home)["budget"]
    if found["status"] != "proposed":
        raise TuneError("nothing to apply: {}".format(found["why"]))
    if found["value"] != want:
        raise TuneError("the record now proposes {}, not the {} the user was shown — run council tune and ask "
                        "again".format(k(found["value"]), k(want)))
    path, text = read_config(home)
    matches = list(LINES.finditer(text))
    if len(matches) > 1:
        raise TuneError("council.config.md has {} estimate-per-worker lines — keep one by hand first".format(len(matches)))
    before_value, before_line = configured(text)
    if matches:
        prefix, old_value, rest = PARTS.match(before_line).groups()
        after_line = prefix + k(want) + rest if old_value else prefix.rstrip() + " " + k(want)
        changed = text[:matches[0].start()] + after_line + text[matches[0].end():]
        record = {"before": before_line, "after": after_line, "inserted": None}
    else:
        after_line = "- {}: {}".format(KNOB, k(want))
        at, inserted = insertion(text, after_line)
        changed = text[:at] + inserted + text[at:]
        record = {"before": None, "after": after_line, "inserted": inserted}
    if configured(changed)[0] != want or len(LINES.findall(changed)) != 1:
        raise TuneError("the edited config would not read back as {} — nothing was written".format(k(want)))
    number = write_pair(home, ["## T-? · {} · applied · {}: {} → {}".format(
        datetime.date.today().isoformat(), KNOB, shown_before(before_value, before_line), k(want)),
        "- evidence: {}".format(found["evidence"]), '- the user said: "{}"'.format(words),
        "- exact: " + json.dumps(record, sort_keys=True)], path, changed)
    return "tune: T-{} applied — {} is now {} (was {}); undo with council tune revert budget".format(
        number, KNOB, k(want), shown_before(before_value, before_line))


def revert(home, words):
    home = Path(home)
    entries = log_entries(home)
    reverted = {int(e["action"].split("T-")[1]) for e in entries if e["action"].startswith("reverted")}
    live = [e for e in entries if e["action"] == "applied" and e["n"] not in reverted]
    if not live:
        raise TuneError("no applied change of the {} is left to revert (.council/tuning.md)".format(KNOB))
    entry = live[-1]
    record = entry["exact"]
    if not isinstance(record, dict) or not isinstance(record.get("after"), str) or \
            not LINES.fullmatch(record["after"]) or \
            (record.get("before") is not None and not (isinstance(record["before"], str) and LINES.fullmatch(record["before"]))) or \
            (record.get("inserted") is not None and not (isinstance(record["inserted"], str) and
                                                         record["inserted"].strip("\r\n") == record["after"])):
        raise TuneError("T-{}'s exact record in tuning.md is missing or was edited — change the config by hand".format(entry["n"]))
    path, text = read_config(home)
    matches = list(LINES.finditer(text))
    if len(matches) != 1 or matches[0].group(0) != record["after"]:
        raise TuneError("the config's estimate line is not the one T-{} wrote ({!r}) — it was edited since; change it "
                        "by hand".format(entry["n"], record["after"]))
    if record["inserted"] is not None:
        if text.count(record["inserted"]) != 1:
            raise TuneError("the line T-{} added is no longer where it was — change the config by hand".format(entry["n"]))
        restored = text.replace(record["inserted"], "", 1)
    else:
        restored = text[:matches[0].start()] + record["before"] + text[matches[0].end():]
    before_value, before_line = configured(restored)
    number = write_pair(home, ["## T-? · {} · reverted T-{} · {}: {} → {}".format(
        datetime.date.today().isoformat(), entry["n"], KNOB, entry["after"], shown_before(before_value, before_line)),
        '- the user said: "{}"'.format(words)], path, restored)
    return "tune: T-{} reverted T-{} — {} is {} again".format(
        number, entry["n"], KNOB, shown_before(before_value, before_line) if before_line else "not set")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("propose", "apply", "revert"))
    parser.add_argument("knob", nargs="?")
    parser.add_argument("--home", required=True, type=Path)
    parser.add_argument("--said", type=Path)
    parser.add_argument("--value")
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
    if args.action == "apply":
        if not args.value:
            raise TuneError("apply needs the value the user was shown: council tune apply budget <value>")
        print(apply(args.home, words, args.value))
    else:
        print(revert(args.home, words))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (TuneError, ledger.LedgerError, OSError, UnicodeError, ValueError) as exc:
        print("tune: " + str(exc), file=sys.stderr)
        sys.exit(2)
