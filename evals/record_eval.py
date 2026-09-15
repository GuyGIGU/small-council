#!/usr/bin/env python3
"""Record a `claude plugin eval` run in the suite's history, and compare it with the last comparable one.

    python evals/record_eval.py [<results dir or aggregate-result.json>] [--label <text>] [--force]

With no path it takes the newest run under evals/suite/results/. It writes a small summary to
evals/history/<run start>-<plugin version>.json — tracked, so every version keeps its behavioural score
next to its code — and compares each case's score with the newest earlier entry recorded the same way
(same --ablation mode, same --tag filters, clean), exiting 1 if any case dropped by more than 0.1. The
raw results stay untracked (evals/suite/results/ is in .gitignore).

It refuses (exit 2) to record a partial run, or one where a run errored: a session that couldn't sign in
or hit a usage limit still lets "must not" graders pass, so its score means nothing. A run that only hit
its turn or time cap was graded on what it produced, so it is recorded and counted as capped. --force
records a refused run anyway, with its error count; such an entry is never used as a baseline.
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "evals", "suite", "results")
HISTORY = os.path.join(ROOT, "evals", "history")
DROP = 0.10   # a case whose score falls by more than this is flagged
CAPPED = re.compile(r"max[ _-]?turns|turn (?:cap|limit)|timed out", re.IGNORECASE)   # graded, not broken
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")   # its refusals go to stderr


def fail(msg):
    print(f"record_eval: {msg}", file=sys.stderr)
    sys.exit(2)


args = sys.argv[1:]
force = "--force" in args
args = [a for a in args if a != "--force"]
label = ""
if "--label" in args:
    i = args.index("--label")
    if i + 1 >= len(args):
        fail("--label needs a value")
    label = args[i + 1]
    del args[i:i + 2]

if args:
    path = args[0]
    if os.path.isdir(path):
        path = os.path.join(path, "aggregate-result.json")
else:
    runs = sorted(glob.glob(os.path.join(RESULTS, "*", "aggregate-result.json")))
    if not runs:
        fail(f"no results under {RESULTS} — run: claude plugin eval . --json")
    path = runs[-1]
if not os.path.isfile(path):
    fail(f"not found: {path}")

with open(path, encoding="utf-8") as f:
    result = json.load(f)
suite = result.get("suite") or {}
# The version the run actually loaded, not whatever the manifest says now
version = next((p.get("version") for p in suite.get("plugins") or [] if p.get("version")), None)
if not version:
    with open(os.path.join(ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
        version = json.load(f).get("version", "unknown")

errored = [(c.get("name"), str(run.get("error")))
           for c in result.get("cases", [])
           for arm_runs in ((c.get("arms") or {}).values())
           for run in (arm_runs or []) if run.get("error")]
capped = [e for e in errored if CAPPED.search(e[1])]
broken = [e for e in errored if not CAPPED.search(e[1])]
if (result.get("partial") or broken) and not force:
    what = f"partial run ({result.get('partialReason')})" if result.get("partial") else "complete run"
    print(f"record_eval: not recording {os.path.relpath(path, ROOT)} — {what}, {len(broken)} run(s) errored:",
          file=sys.stderr)
    for name, err in broken[:6]:
        print(f"  {name}: {err[:160]}", file=sys.stderr)
    print("Fix the cause and run the suite again — e.g. the eval's child sessions need their own credentials "
          "(ANTHROPIC_API_KEY, or CLAUDE_CODE_OAUTH_TOKEN) — or pass --force to record it anyway.", file=sys.stderr)
    sys.exit(2)

agg = result.get("aggregates", {})
started = str(result.get("startedAt") or os.path.basename(os.path.dirname(path)) or "run")
summary = {
    "pluginVersion": version,
    "label": label,
    "source": os.path.relpath(path, ROOT).replace("\\", "/"),
    "startedAt": started,
    "claudeVersion": result.get("claudeVersion"),
    "ablation": suite.get("ablation"),
    "tagFilters": sorted(suite.get("tagFilters") or []),
    "partial": result.get("partial", False),
    "runErrors": len(broken),
    "cappedRuns": len(capped),
    "overallScore": agg.get("overallScore"),
    "meanDelta": agg.get("meanDelta"),
    "casesPassed": agg.get("casesPassed"),
    "casesTotal": agg.get("casesTotal"),
    "costUsd": result.get("costUsd"),
    "cases": {c.get("name"): {"score": (c.get("aggregates") or {}).get("score"),
                              "delta": (c.get("aggregates") or {}).get("delta"),
                              "runs": c.get("runsPerCase")}
              for c in result.get("cases", [])},
}

os.makedirs(HISTORY, exist_ok=True)
stamp = re.sub(r"[^0-9A-Za-z]+", "-", started).strip("-")   # sorts by time; one file per run
out = os.path.join(HISTORY, f"{stamp}-{version}.json")
with open(out, "w", encoding="utf-8", newline="\n") as f:
    json.dump(summary, f, indent=2, sort_keys=True)
    f.write("\n")


def pct(x):
    return "  -  " if x is None else f"{x:5.2f}"


extra = ("  (PARTIAL)" if summary["partial"] else "") + \
        (f", {len(capped)} run(s) hit a turn or time cap" if capped else "")
print(f"recorded {os.path.relpath(out, ROOT)} — plugin {version}, score {pct(summary['overallScore'])}, "
      f"Δ {pct(summary['meanDelta'])}, {summary['casesPassed']}/{summary['casesTotal']} cases, "
      f"${summary['costUsd'] or 0:.2f}{extra}")


def comparable(entry):
    # Only a clean earlier run of the same shape: a one-arm smoke and a two-arm run score differently
    return (entry.get("ablation") == summary["ablation"]
            and sorted(entry.get("tagFilters") or []) == summary["tagFilters"]
            and not entry.get("partial") and not entry.get("runErrors")
            and str(entry.get("startedAt") or "") < started)


earlier = []
for p in glob.glob(os.path.join(HISTORY, "*.json")):
    if os.path.abspath(p) == os.path.abspath(out):
        continue
    try:
        with open(p, encoding="utf-8") as f:
            entry = json.load(f)
    except (OSError, ValueError):
        continue
    if isinstance(entry, dict) and comparable(entry):
        earlier.append((str(entry.get("startedAt")), p, entry))
if not earlier:
    shape = f"ablation {summary['ablation']}, tags {', '.join(summary['tagFilters']) or 'all'}"
    print(f"no earlier clean entry of the same shape ({shape}) to compare with")
    sys.exit(0)
_, prev_path, before = max(earlier, key=lambda e: (e[0], e[1]))
print(f"\ncompared with {os.path.basename(prev_path)} (plugin {before.get('pluginVersion')}):")
drops = 0
for name in sorted(set(summary["cases"]) | set(before.get("cases", {}))):
    now = (summary["cases"].get(name) or {}).get("score")
    was = (before.get("cases", {}).get(name) or {}).get("score")
    flag = ""
    if now is not None and was is not None and was - now > DROP:
        flag, drops = "  ← dropped", drops + 1
    elif was is None:
        flag = "  (new)"
    elif now is None:
        flag = "  (gone)"
    print(f"  {name:32s} {pct(was)} → {pct(now)}{flag}")
print(f"  {'overall':32s} {pct(before.get('overallScore'))} → {pct(summary['overallScore'])}")
sys.exit(1 if drops else 0)
