#!/usr/bin/env python3
"""Phrase checks for the Small Council — ADVISORY, never fails the build.

Looks for the wording of the field-tested rules in the kernel, the stage doctrine, the agents and the
modes, and prints a WARN for any it can't find. A missing phrase might be a harmless rewording or a
rule that was dropped — read the warning and decide. A present phrase proves nothing about behaviour;
that's what the drills are for. (Before 0.3 these needles sat in the blocking structural eval, where
they passed reversed rules and failed harmless edits.)
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def read(*parts):
    path = os.path.join(ROOT, *parts)
    return open(path, encoding="utf-8").read() if os.path.isfile(path) else ""


doctrine_dir = os.path.join(ROOT, "references", "doctrine")
TEXTS = {
    "kernel+doctrine": read("skills", "context-core", "SKILL.md") + "\n" + "\n".join(
        read("references", "doctrine", f) for f in sorted(os.listdir(doctrine_dir)) if f.endswith(".md")),
    "worker": read("agents", "council-worker.md"),
    "verifier": read("agents", "council-verifier.md"),
    "init": read("skills", "council-init", "SKILL.md"),
    "plan": read("skills", "council-plan", "SKILL.md"),
    "implement": read("skills", "council-implement", "SKILL.md"),
    "research": read("skills", "council-research", "SKILL.md"),
}
FLAT = {k: " ".join(v.split()) for k, v in TEXTS.items()}

RULES = [  # (where, the rule, the phrase that carries it)
    ("kernel+doctrine", "aggregate before judging", "Raw ledger first"),
    ("kernel+doctrine", "map, don't ingest", "Map, don't ingest"),
    ("kernel+doctrine", "brief written for a zero-context worker", "zero context"),
    ("kernel+doctrine", "gates judged by exit code", "exit code"),
    ("kernel+doctrine", "a gate that can't run is config drift", "config drift"),
    ("kernel+doctrine", "a lone dissenter may be right", "lone dissenter"),
    ("kernel+doctrine", "protected subjects never dropped on UNCERTAIN", "never dropped if its subject is protected"),
    ("kernel+doctrine", "never judge over a hole", "Never judge over a hole"),
    ("kernel+doctrine", "partial delivery on the user's word", "PARTIAL"),
    ("kernel+doctrine", "skipped seats carry their reason", "with its reason"),
    ("kernel+doctrine", "when in doubt, keep the seat", "When in doubt, keep the seat"),
    ("kernel+doctrine", "autonomy after the go-ahead", "without check-ins"),
    ("kernel+doctrine", "proposals written to memory immediately", "`## Proposed` section now"),
    ("kernel+doctrine", "rejected proposals never return", "never propose it again"),
    ("kernel+doctrine", "decisions only in the user's words", "user's own words"),
    ("kernel+doctrine", "consolidation by operations, not rewrites", "Never rewrite the file wholesale"),
    ("kernel+doctrine", "questions numbered, last", "numbered"),
    ("kernel+doctrine", "plain language to the user", "Plain language"),
    ("kernel+doctrine", "close every run", "Close every run you open"),
    ("kernel+doctrine", "wait for notifications, never poll", "Never poll"),
    ("kernel+doctrine", "Solo skips stages 3–6", "skips stages 3–6"),
    ("kernel+doctrine", "resume re-invokes the run's own mode", "Re-invoke the skill named by the run's `mode:`"),
    ("kernel+doctrine", "workers lost with an old session are re-dispatched once", "re-dispatch each once"),
    ("kernel+doctrine", "the council home is the main checkout", "*main* checkout"),
    ("kernel+doctrine", "the approval shows seats not going", "Seats not going"),
    ("kernel+doctrine", "never name a council agent call", "Never pass `name`"),
    ("kernel+doctrine", "the verifier is blind to the author's reasoning", "never the seat, principle, reasoning or fix"),
    ("kernel+doctrine", "verifier overflow: P1s and protected items first", "Over the cap?"),
    ("kernel+doctrine", "a seat's card is its ref", "Cards first"),
    ("kernel+doctrine", "memory is read by scope, never whole", "never the whole file"),
    ("kernel+doctrine", "the ledger counts exact from: lines and verdicts", "so keep those exact"),
    ("init", "roster changes proposed with the numbers shown", "with the numbers shown"),
    ("init", "a gate with side effects never runs unasked", "never runs a gate"),
    ("worker", "exactly one line back", "Exactly one line"),
    ("worker", "a paired seat proves every reference doc", "one `ref:` line for each"),
    ("verifier", "blind to the author", "You are not told"),
    ("verifier", "URL claims are fetched", "fetch the page"),
    ("init", "gates dry-run once", "Run each once"),
    ("init", "recast before dropping a seat", "Recast before you drop"),
    ("plan", "the plan gate", "Ready to dispatch the council"),
    ("plan", "walking skeleton first", "walking skeleton"),
    ("implement", "per-task commits offered", "One commit per task"),
    ("implement", "quote the whole gate command", "quote the whole command"),
    ("research", "rival hypotheses for why-questions", "rival hypotheses"),
    ("research", "research patches the map", "patch `map.md`"),
]

missing = 0
for where, label, needle in RULES:
    ok = needle in FLAT[where]
    missing += not ok
    print(f"[{'ok  ' if ok else 'WARN'}] {where}: {label}" + ("" if ok else f"  (no '{needle}')"))
print(f"\n{len(RULES) - missing}/{len(RULES)} rule phrases found (advisory — this never fails the build)")
sys.exit(0)
