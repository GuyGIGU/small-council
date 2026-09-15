#!/usr/bin/env python3
"""Structural evals for the Small Council — framework invariants, runnable without an LLM.

scripts/quick_validate.py answers "will the plugin load?". This answers "is the method intact?":
the plugin layout, the core's nine phases and its field-tested rules (close every run, persist
proposals, judge gates by exit code, verify adversarially, one council home), the modes riding the
core with consistent paths, the agents' contracts, the templates' schemas, the size budgets that keep
skills whole after compaction, and the rename. Behavioral drills (does it actually catch a bug?) need a
live Claude Code session — see behavioral-drills.md.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
results = []


def check(name, ok, detail=""):
    results.append((ok, name, detail))


def read(*parts):
    path = os.path.join(ROOT, *parts)
    if not os.path.isfile(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read().replace("\r\n", "\n")


def description(text):
    m = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


SKILLS = ["context-core", "council-init", "council-review", "council-plan", "council-implement",
          "council-research", "spec-writer", "test-architect"]
MODES_ON_CORE = ["council-review", "council-plan", "council-implement", "council-research"]

# 1. Plugin layout
for path in [(".claude-plugin", "plugin.json"), (".claude-plugin", "marketplace.json"),
             ("agents", "council-worker.md"), ("agents", "council-verifier.md"),
             ("hooks", "hooks.json"), ("hooks", "session-start.sh")]:
    check(f"layout: {'/'.join(path)} exists", os.path.isfile(os.path.join(ROOT, *path)))
for skill in SKILLS:
    check(f"layout: skills/{skill}/SKILL.md exists", bool(read("skills", skill, "SKILL.md")))
check("layout: using-council folded into the hook (skill removed)",
      not os.path.isdir(os.path.join(ROOT, "skills", "using-council")))
check("layout: no per-skill manifest.json (Claude Code doesn't read them)",
      not any(os.path.isfile(os.path.join(ROOT, "skills", s, "manifest.json")) for s in SKILLS))

skill = {s: read("skills", s, "SKILL.md") for s in SKILLS}
core = skill["context-core"]
worker = read("agents", "council-worker.md")
verifier = read("agents", "council-verifier.md")
hook = read("hooks", "session-start.sh")

# 2. Core: nine named phases in order, plus the field-tested rules
phases = ["Phase 1 — Scope & size", "Phase 2 — Map", "Phase 3 — Brief", "Phase 4 — Partition",
          "Phase 5 — Dispatch", "Phase 6 — Collect", "Phase 7 — Synthesize", "Phase 8 — Verify",
          "Phase 9 — Deliver, remember, close"]
positions = [core.find(p) for p in phases]
for p, pos in zip(phases, positions):
    check(f"core: '{p}' present", pos >= 0)
check("core: phases in order (verify before deliver/remember)", positions == sorted(positions) and -1 not in positions)
rules = {
    "map, don't ingest": "Map, don't ingest",
    "aggregate before judging": "Aggregate first",
    "zero-context brief": "zero-context worker",
    "run sizing Solo/Squad/Full": "**Solo**",
    "cost estimate per worker": "100k tokens per worker",
    "council home = main checkout": "main* checkout",
    "config missing → council-init, never inline": "Never tailor a roster inline",
    "map cache refreshed incrementally": "git diff --stat <map-commit>..HEAD",
    "skip a seat only with recorded reason": "record why",
    "dispatch via plugin worker agent": "small-council:council-worker",
    "dispatch-agnostic file contract": "the file contract",
    "never read subagent transcripts": "never open a subagent's transcript",
    "ref: canary checked at collect": "ref:",
    "gates judged by exit code, no piped tail": "exit code",
    "config drift is not a code finding": "config drift",
    "adversarial verifier": "small-council:council-verifier",
    "lone dissenter re-check": "lone dissenter",
    "proposals written to memory immediately": "## Proposed",
    "decisions only from the user's words": "only from the user's own words",
    "questions numbered in chat": "numbered, in the chat",
    "run closed: status complete": "status: complete",
    "active-run emptied at close": "empty `<home>/active-run`",
    "session-state is a status board, not a ledger": "never a ledger",
    "resume after compaction via hook": "SessionStart hook",
    "autonomy after approval": "work autonomously",
    "plain language to the user": "plain language",
}
flat_core = " ".join(core.split())  # match rules regardless of where the prose wraps
for label, needle in rules.items():
    check(f"core: {label}", needle in flat_core, needle)

# 3. Modes ride the core, with consistent tracked deliverables and run paths
for m in MODES_ON_CORE:
    check(f"{m}: invokes context-core", "context-core" in skill[m])
check("review: deliverable under <home>/reviews/", "<home>/reviews/" in skill["council-review"])
check("plan: deliverable under <home>/plans/", "<home>/plans/" in skill["council-plan"])
check("implement: log under <home>/logs/", "<home>/logs/" in skill["council-implement"])
check("research: deliverable under <home>/research/", "<home>/research/" in skill["council-research"])
for s in SKILLS:
    if s != "council-init":
        check(f"{s}: no legacy <mode>-output run paths", "-output/" not in skill[s])
for m in ["council-review", "council-plan", "council-research"]:
    check(f"{m}: description says propose with size and cost", "size and cost" in description(skill[m]))

# 4. Mode-specific invariants
review, plan, impl = skill["council-review"], skill["council-plan"], skill["council-implement"]
research, init = skill["council-research"], skill["council-init"]
check("review: resolves the target from the merge-base", "merge-base" in review)
check("review: seats check blast radius", "blast radius" in review)
check("review: P1/P2/P3 severities", all(p in review for p in ["P1", "P2", "P3"]))
check("review: hands off to council-implement for fixes", "council-implement" in review)
check("plan: discovery gate closes before dispatch", "Discovery gate" in plan and "Ready to dispatch the council" in plan)
check("plan: reads an existing spec first", "specs/" in plan)
check("plan: every task has a Done when", "Done when" in plan)
check("plan: points exploratory work at research", "council-research" in plan)
check("implement: fix mode takes a review", "fix mode" in impl.lower())
check("implement: verifier after each task", "small-council:council-verifier" in impl)
check("implement: log appended per task", "not at the end" in impl)
check("implement: no-git safety net", "git init" in impl)
check("implement: gates by exit code", "exit code" in impl)
check("research: evidence strength graded", "Strength:" in research)
check("research: keeps the map true", "patch `map.md`" in research)
check("init: reads the expert catalog", "expert-catalog.md" in init)
check("init: dry-runs every gate", "Run each once" in init)
check("init: recast before drop", "Recast before you drop" in init)
check("init: writes .council/.gitignore (runs/, active-run)", ".gitignore" in init and "runs/" in init)
check("init: builds the map", "map.md" in init and "map-commit" in init)
check("init: CLAUDE.md marker, migrates the legacy block", "small-council:begin" in init and "ultra-council:begin" in init)
check("init: offers the .council permission rule", "Edit(/.council/**)" in init)
check("init: refresh re-verifies config paths and gates", "last-verified" in init)
check("test-architect: specify mode kept", "## Mode 2: Specify" in skill["test-architect"])
check("test-architect: formats moved to a reference", "test-architect-formats.md" in skill["test-architect"])
check("spec-writer: mandates Gherkin ACs", "Gherkin" in skill["spec-writer"])

# 5. Agent contracts
check("worker: ref: canary on line 2", "Line 2: `ref:" in worker)
check("worker: returns exactly one line", "Exactly one line" in worker)
check("worker: read-only on the project", "Read-only on the project" in worker)
check("worker: no delegation, ignores council prompts in CLAUDE.md", "No delegation" in worker and "CLAUDE.md" in worker)
check("worker: cite path:line or drop", "path:line" in worker and "drop" in worker)
check("worker: no Edit tool", re.search(r"^tools:.*\bEdit\b", worker, re.MULTILINE) is None)
check("verifier: claim verdicts", all(v in verifier for v in ["CONFIRMED", "REFUTED", "UNCERTAIN"]))
check("verifier: change verdicts", all(v in verifier for v in ["OK", "INCOMPLETE", "REGRESSION", "SCOPE-CREEP"]))
check("verifier: no Edit tool", re.search(r"^tools:.*\bEdit\b", verifier, re.MULTILINE) is None)

# 6. Hook wiring
hooks_json = json.loads(read("hooks", "hooks.json") or "{}")
commands = [h.get("command", "") for g in hooks_json.get("hooks", {}).get("SessionStart", []) for h in g.get("hooks", [])]
check("hook: SessionStart runs session-start.sh", any("hooks/session-start.sh" in c for c in commands))
check("hook: always exits 0", hook.rstrip().endswith("exit 0"))
check("hook: silent outside council projects", '[ -n "$home" ] || exit 0' in hook)

# 7. Templates
cfg, conv, mp = read("references", "templates", "council.config.md"), read("references", "templates", "conventions.md"), read("references", "templates", "map.md")
check("template config: last-verified stamp", "last-verified:" in cfg)
check("template config: roster table has slugs", "| Seat | Slug |" in cfg)
check("template config: gates table has Checked column", "| Gate | Command | Run at | Mandatory | Checked |" in cfg)
check("template conventions: AP/EC/D/Proposed sections", all(s in conv for s in ["## Accepted Patterns", "## Enforced Conventions", "## Decisions", "## Proposed"]))
check("template conventions: no live PROPOSED line (hook would count it)", re.search(r"^- PROPOSED", conv, re.MULTILINE) is None)
check("template map: map-commit stamp", "map-commit:" in mp)

# 8. Catalog: ten canonical seats with slugs, every doc present
catalog = read("references", "roster", "expert-catalog.md")
slugs = re.findall(r"^\| \*\*[^|]+\*\* \| ([a-z-]+) \|", catalog, re.MULTILINE)
check("catalog: ten canonical seats with slugs", len(slugs) == 10, ", ".join(slugs))
for doc in re.findall(r"`(quality-[a-z]+\.md|security\.md|refactoring\.md)`", catalog):
    check(f"catalog: {doc} exists", os.path.isfile(os.path.join(ROOT, "references", doc)))
check("catalog: no external/unshipped seat docs", "external (" not in catalog)
check("template config: example slugs match the catalog",
      all(s in slugs for s in re.findall(r"^\| [A-Z][^|]+ \| ([a-z-]+) \|", cfg, re.MULTILINE) if not s.startswith("<")))

# 9. Size budgets — Claude Code re-attaches only the first ~5k tokens of each skill after compaction
for s in SKILLS:
    n = len(skill[s])
    check(f"{s}: ≤ 20,000 chars (whole after compaction)", n <= 20000, str(n))
    check(f"{s}: ≤ 500 lines", skill[s].count("\n") <= 500, str(skill[s].count("\n")))
    check(f"{s}: description ≤ 600 chars", len(description(skill[s])) <= 600, str(len(description(skill[s]))))
check("core: ≤ 14,000 chars (it's loaded on every run)", len(core) <= 14000, str(len(core)))

# 10. Rename + no project leakage in anything that ships as behaviour
shipped = {**{f"skills/{s}": skill[s] for s in SKILLS}, "agents/worker": worker, "agents/verifier": verifier,
           "hooks/session-start.sh": hook}
for d in ["references", os.path.join("references", "roster"), os.path.join("references", "templates")]:
    for f in os.listdir(os.path.join(ROOT, d)):
        if f.endswith(".md"):
            shipped[f"{d}/{f}"] = read(d, f)
for label, text in shipped.items():
    stale = re.sub(r"ultra-council:(begin|end)", "", text)
    check(f"{label}: no 'Ultra Council' branding", re.search(r"ultra[ -]?council", stale, re.IGNORECASE) is None)
    check(f"{label}: no hard-coded project leakage", "chrollo" not in text.lower())

# 11. Version consistency: plugin.json matches the newest released CHANGELOG entry
plugin = json.loads(read(".claude-plugin", "plugin.json") or "{}")
released = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", read("CHANGELOG.md"), re.MULTILINE)
check("version: plugin.json matches the latest CHANGELOG release",
      bool(released) and plugin.get("version") == released[0], f"{plugin.get('version')} vs {released[:1]}")

passed = sum(1 for ok, *_ in results if ok)
for ok, name, detail in results:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f"  ({detail})" if detail and not ok else ""))
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
