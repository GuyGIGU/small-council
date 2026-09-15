#!/usr/bin/env python3
"""Structural evals for the Small Council (blocking) — framework invariants, no LLM.

scripts/quick_validate.py answers "will the plugin load?". This answers "is the design intact?":
  - the plugin layout, and the kernel's laws and stage index;
  - the ten stage doctrine files and their hand-offs;
  - every `council …` command a text mentions existing in the helper;
  - the modes' stage sections and deliverable paths, the agents' contracts, the hooks' wiring;
  - the templates' schemas, the catalog, the size budgets, bash portability, the rename, and version
    consistency.

Wording-level rule checks live in run_phrases.py and are advisory: a reworded rule shouldn't fail the
build, and a phrase being present doesn't prove behaviour. Behaviour belongs to the drills.
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


def flat(text):
    return " ".join(text.split())


def description(text):
    m = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


SKILLS = ["context-core", "council-init", "council-review", "council-plan", "council-implement",
          "council-research", "spec-writer", "test-architect"]
MODES = ["council-review", "council-plan", "council-implement", "council-research"]
STAGES = ["convene", "prepare", "assign", "brief", "work", "collect", "judge", "challenge", "deliver", "learn"]
DOCTRINE = [f"{i:02d}-{s}.md" for i, s in enumerate(STAGES, 1)]

# 1. Layout
for path in [(".claude-plugin", "plugin.json"), (".claude-plugin", "marketplace.json"), ("bin", "council"),
             ("agents", "council-worker.md"), ("agents", "council-verifier.md"),
             ("hooks", "hooks.json"), ("hooks", "session-start.sh"), ("hooks", "seat-gate.sh")]:
    check(f"layout: {'/'.join(path)} exists", os.path.isfile(os.path.join(ROOT, *path)))
for s in SKILLS:
    check(f"layout: skills/{s}/SKILL.md exists", bool(read("skills", s, "SKILL.md")))
for d in DOCTRINE:
    check(f"layout: references/doctrine/{d} exists", bool(read("references", "doctrine", d)))
check("layout: no using-council skill (the hook replaced it)", not os.path.isdir(os.path.join(ROOT, "skills", "using-council")))
check("layout: no per-skill manifest.json", not any(os.path.isfile(os.path.join(ROOT, "skills", s, "manifest.json")) for s in SKILLS))

skill = {s: read("skills", s, "SKILL.md") for s in SKILLS}
core = skill["context-core"]
doctrine = {d: read("references", "doctrine", d) for d in DOCTRINE}
worker, verifier = read("agents", "council-worker.md"), read("agents", "council-verifier.md")
hook, gate, cli = read("hooks", "session-start.sh"), read("hooks", "seat-gate.sh"), read("bin", "council")

# 2. Kernel
LAWS = ["One head", "Parallel readers, one writer", "Gather once, share with everyone", "The disk is the memory",
        "Scripts do the mechanics", "Read a stage's doctrine as you enter it", "Evidence or it didn't happen",
        "Aggregate, then judge", "The user rules; the council proposes",
        "Every run is sized, budgeted, reported and closed", "The council learns this project"]
for i, law in enumerate(LAWS, 1):
    check(f"kernel: law {i} — {law}", f"{i}. **{law}" in core)
pos = [core.find(f"`{d}`") for d in DOCTRINE]
check("kernel: the stage table lists all ten doctrine files, in order", -1 not in pos and pos == sorted(pos), str(pos))
check("kernel: points at the doctrine folder", "${CLAUDE_PLUGIN_ROOT}/references/doctrine/" in core)
check("kernel: agent cap of 10, verifiers included", re.search(r"\b10\b[^.]*verifiers included", flat(core)) is not None)
check("kernel: approval threshold from the config", "approve without asking" in core)

# 3. Stage doctrine
for i, (d, stage) in enumerate(zip(DOCTRINE, STAGES), 1):
    t = doctrine[d]
    check(f"{d}: titled '# Stage {i} — …'", t.startswith(f"# Stage {i} — "))
    if i < len(STAGES):
        check(f"{d}: hands off to {STAGES[i]}", f"council state phase={STAGES[i]}" in t)
    check(f"{d}: ≤ 6,000 chars", len(t) <= 6000, str(len(t)))
check("01-convene: opens the run with the helper", "council run open" in doctrine["01-convene.md"])
check("02-prepare: builds the change index", "council index" in doctrine["02-prepare.md"])
check("03-assign: records every seat's state", "council seat" in doctrine["03-assign.md"])
check("04-brief: seat blocks carry ref / out / cap for collect", all(k in doctrine["04-brief.md"] for k in ["### <slug>", "- ref:", "- out:", "- cap:"]))
check("05-work: records each worker with its agent id", "council seat <slug> running agent=" in doctrine["05-work.md"])
check("06-collect: runs council collect", "council collect" in doctrine["06-collect.md"])
check("07-judge: writes synthesis.md in the index-line format", "synthesis.md" in doctrine["07-judge.md"] and "1 · P1 ·" in doctrine["07-judge.md"])
check("08-challenge: mechanical pre-check first", "council check" in doctrine["08-challenge.md"])
check("08-challenge: one verify-<n>.md per verifier", "verify-<n>.md" in doctrine["08-challenge.md"])
check("10-learn: closes the run", "council run close" in doctrine["10-learn.md"])

# 4. Every `council …` command the texts mention exists in the helper
usage = cli[cli.find("usage() {"):cli.find("main() {")]
known = set(re.findall(r"^\s+council ([a-z]+)", usage, re.MULTILINE))
check("helper: usage lists its commands", {"run", "state", "seat", "index", "gate", "collect", "check", "map", "doctor"} <= known, ", ".join(sorted(known)))
for c in sorted(known):
    check(f"helper: '{c}' is dispatched in main", re.search(rf"^\s+{c}\)", cli, re.MULTILINE) is not None)
texts = {**{f"skills/{s}": skill[s] for s in SKILLS}, **{f"doctrine/{d}": doctrine[d] for d in DOCTRINE},
         "agents/worker": worker, "agents/verifier": verifier, "hooks/session-start.sh": hook}
flags = set(re.findall(r"^\s+(--[a-z][a-z-]*)(?:=\*)?\)", cli[cli.find("main() {"):], re.MULTILINE))
bad, bad_flags = [], []
for label, t in texts.items():
    for m in re.finditer(r"`council ([a-z]+)([^`]*)`", t):
        c, rest = m.group(1), m.group(2).replace("\\", " ").split()   # the hook escapes backticks: \`…\`
        bad_flags += [f"{label}: council {c} {f}" for f in re.findall(r"--[a-z][a-z-]*", " ".join(rest)) if f not in flags]
        if c not in known:
            bad.append(f"{label}: council {c}")
        elif c == "run" and (not rest or rest[0] not in {"open", "close", "status"}):
            bad.append(f"{label}: council run {' '.join(rest[:1])}")
        elif c == "map" and (not rest or rest[0] != "status"):
            bad.append(f"{label}: council map {' '.join(rest[:1])}")
check("every `council …` command mentioned exists in the helper", not bad, "; ".join(bad[:8]))
check("every --option those mentions use exists in the helper", bool(flags) and not bad_flags, "; ".join(bad_flags[:8]))

# 5. Modes
for m in MODES:
    heads = re.findall(r"^## At ([A-Za-z]+)", skill[m], re.MULTILINE)
    check(f"{m}: invokes context-core", "context-core" in skill[m])
    check(f"{m}: every '## At <Stage>' names a real stage", heads and all(h.lower() in STAGES for h in heads), ", ".join(heads))
WANT = {"council-review": ["Convene", "Prepare", "Brief", "Work", "Judge", "Deliver", "Learn"],
        "council-plan": ["Convene", "Prepare", "Brief", "Work", "Judge", "Challenge", "Deliver"],
        "council-research": ["Convene", "Prepare", "Assign", "Brief", "Work", "Judge", "Challenge", "Deliver", "Learn"],
        "council-implement": ["Convene", "Prepare", "Challenge", "Deliver"]}
for m, want in WANT.items():
    missing = [w for w in want if f"## At {w}" not in skill[m]]
    check(f"{m}: has its stage sections", not missing, ", ".join(missing))
for m in ["council-review", "council-plan", "council-research"]:
    check(f"{m}: per-item format has an index line", "Index line: `<n> ·" in skill[m])
    check(f"{m}: description says propose with its size and cost", "size and cost" in description(skill[m]))
for m, path in [("council-review", "<home>/reviews/"), ("council-plan", "<home>/plans/"),
                ("council-implement", "<home>/logs/"), ("council-research", "<home>/research/")]:
    check(f"{m}: deliverable under {path}", path in skill[m])
for s in SKILLS:
    if s != "council-init":
        check(f"{s}: no legacy <mode>-output run paths", "-output/" not in skill[s])
review, plan, impl, research, init = (skill[k] for k in ["council-review", "council-plan", "council-implement", "council-research", "council-init"])
for label, text, needles in [
    ("review", review, ["merge-base", "council index --base", "Origin:", "Basis:", "Refuted if:", "Not a finding", "council-implement"]),
    ("plan", plan, ["specs/", "Touches", "Done when", "council-research"]),
    ("implement", impl, ["fix mode", "Before-evidence", "After-evidence", "clean-context diagnosis", "converge", "council gate --all",
                         "small-council:council-verifier", "Notes for later tasks", "diagnose-<n>.md", "verify-<n>b.md"]),
    ("research", research, ["scout", "Strength:"]),
    ("init", init, ["expert-catalog.md", "Surface markers", ".gitignore", "small-council:begin", "ultra-council:begin",
                    "Edit(/.council/**)", "Bash(council *)", "last-verified", "council doctor", "council run open council-init"]),
    ("test-architect", skill["test-architect"], ["## Mode 2: Specify", "test-architect-formats.md", "small-council:council-verifier"]),
    ("spec-writer", skill["spec-writer"], ["Gherkin"])]:
    missing = [n for n in needles if n not in text]
    check(f"{label}: carries its mechanisms", not missing, ", ".join(missing))

# 6. Agents
check("worker: header with ref: on line 2 and an Index", "ref: <the first heading" in worker and "## Index" in worker)
check("worker: returns a Wrote line (the seat check reads it)", "`Wrote <output path>" in worker)
check("worker: read-only, no delegation, ignores council prompts in CLAUDE.md", all(k in worker for k in ["Read-only on the project", "No delegation", "CLAUDE.md"]))
check("worker: rulings capped, lanes kept", "## Needs a ruling" in worker and "## Outside my lane" in worker)
check("worker: BLOCKED instead of proceeding blind", "BLOCKED" in worker)
check("verifier: claim verdicts", all(v in verifier for v in ["CONFIRMED", "REFUTED", "UNCERTAIN", "MISCITED"]))
check("verifier: change verdicts", all(v in verifier for v in ["OK", "INCOMPLETE", "REGRESSION", "SCOPE-CREEP", "CANNOT VERIFY"]))
check("verifier: can open a research claim's URL", re.search(r"^tools:.*\bWebFetch\b", verifier, re.MULTILINE) is not None)
for label, t in [("worker", worker), ("verifier", verifier)]:
    check(f"{label}: no Edit tool", re.search(r"^tools:.*\bEdit\b", t, re.MULTILINE) is None)

# 7. Hooks
hooks_json = json.loads(read("hooks", "hooks.json") or "{}").get("hooks", {})
start_cmds = [h.get("command", "") for g in hooks_json.get("SessionStart", []) for h in g.get("hooks", [])]
stop_groups = hooks_json.get("SubagentStop", [])
check("hook: SessionStart runs session-start.sh", any("hooks/session-start.sh" in c for c in start_cmds))
check("hook: SubagentStop runs seat-gate.sh for council agents only",
      any(g.get("matcher") == "^small-council:council-(worker|verifier)$" and any("hooks/seat-gate.sh" in h.get("command", "") for h in g.get("hooks", []))
          for g in stop_groups))
check("hook: session-start shares the helper's resolver", '. "$ROOT/bin/council"' in hook)
check("hook: session-start always exits 0", hook.rstrip().endswith("exit 0"))
check("hook: silent outside council projects", '[ -d "$home" ] || exit 0' in hook)
check("hook: seat-gate never blocks twice", "stop_hook_active" in gate)
check("hook: seat-gate passes only a line that starts with BLOCKED", "grep -q '^BLOCKED'" in gate)
check("hook: session-start resumes only this session's run", "field session" in hook and "session_id" in hook)
check("helper: run open records Claude Code's session id", "CLAUDE_CODE_SESSION_ID" in cli)

# 8. Templates
cfg, conv, mp = read("references", "templates", "council.config.md"), read("references", "templates", "conventions.md"), read("references", "templates", "map.md")
check("template config: last-verified stamp", "last-verified:" in cfg)
check("template config: run preferences", "## Run preferences" in cfg and "approve without asking: up to squad" in cfg and "agent cap: 10" in cfg)
check("template config: roster has slugs and surface markers", "| Seat | Slug | Lens | Surface | Reference | Recast note |" in cfg)
check("template config: gates table", "| Gate | Command | Run at | Mandatory | Checked |" in cfg)
check("template conventions: AP / EC / D / Proposed / Rejected", all(s in conv for s in ["## Accepted Patterns", "## Enforced Conventions", "## Decisions", "## Proposed", "## Rejected"]))
check("template conventions: no live PROPOSED line (the hook would count it)", re.search(r"^- PROPOSED", conv, re.MULTILINE) is None)
check("template map: map-commit stamp", "map-commit:" in mp)
for label, rel in [("fixture", ("evals", "fixtures", ".council", "council.config.md")), ("example", ("examples", "chrollo", "council.config.md"))]:
    t = read(*rel)
    check(f"{label} config: current schema (surface markers, run preferences)", "| Surface |" in t and "## Run preferences" in t)

# 9. Catalog and seat docs
catalog = read("references", "roster", "expert-catalog.md")
slugs = re.findall(r"^\| \*\*[^|]+\*\* \| ([a-z-]+) \|", catalog, re.MULTILINE)
check("catalog: ten canonical seats with slugs", len(slugs) == 10, ", ".join(slugs))
for doc in re.findall(r"`(quality-[a-z]+\.md|security\.md|refactoring\.md)`", catalog):
    check(f"catalog: {doc} exists", os.path.isfile(os.path.join(ROOT, "references", doc)))
check("catalog: no external/unshipped seat docs", "external (" not in catalog)
check("template config: example slugs match the catalog",
      all(s in slugs for s in re.findall(r"^\| [A-Z][^|]+ \| ([a-z-]+) \|", cfg, re.MULTILINE)))

# 10. Size budgets — Claude Code re-attaches only the first ~5k tokens of each skill after compaction
for s in SKILLS:
    n = len(skill[s])
    check(f"{s}: ≤ 20,000 chars", n <= 20000, str(n))
    check(f"{s}: ≤ 500 lines", skill[s].count("\n") <= 500, str(skill[s].count("\n")))
    check(f"{s}: description ≤ 600 chars", len(description(skill[s])) <= 600, str(len(description(skill[s]))))
check("kernel: ≤ 14,000 chars (read on every run)", len(core) <= 14000, str(len(core)))
for label, t in [("worker", worker), ("verifier", verifier)]:
    check(f"{label}: ≤ 8,000 chars", len(t) <= 8000, str(len(t)))

# 11. Bash portability (macOS ships bash 3.2)
for label, t in [("bin/council", cli), ("hooks/session-start.sh", hook), ("hooks/seat-gate.sh", gate)]:
    code_only = "\n".join(l for l in t.split("\n") if not l.lstrip().startswith("#"))   # comments may name what's avoided
    hit = re.search(r"declare -A|\bmapfile\b|\breadarray\b|,,\}|\^\^\}", code_only)
    check(f"{label}: bash 3.2 portable (no declare -A, mapfile, readarray, case-conversion expansions)",
          hit is None, hit.group(0) if hit else "")

# 12. Rename, and no project leakage in anything that ships as behaviour
shipped = {**{f"skills/{s}": skill[s] for s in SKILLS}, **{f"doctrine/{d}": doctrine[d] for d in DOCTRINE},
           "agents/worker": worker, "agents/verifier": verifier, "hooks/session-start.sh": hook,
           "hooks/seat-gate.sh": gate, "bin/council": cli}
for d in ["references", os.path.join("references", "roster"), os.path.join("references", "templates")]:
    for f in os.listdir(os.path.join(ROOT, d)):
        if f.endswith(".md"):
            shipped[f"{d}/{f}"] = read(d, f)
for label, text in shipped.items():
    stale = re.sub(r"ultra-council:(begin|end)", "", text)
    check(f"{label}: no 'Ultra Council' branding", re.search(r"ultra[ -]?council", stale, re.IGNORECASE) is None)
    check(f"{label}: no hard-coded project leakage", "chrollo" not in text.lower())

# 13. Versions agree: plugin.json, the newest CHANGELOG release, and the helper
plugin = json.loads(read(".claude-plugin", "plugin.json") or "{}")
released = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", read("CHANGELOG.md"), re.MULTILINE)
helper_version = re.search(r'^COUNCIL_VERSION="([^"]+)"', cli, re.MULTILINE)
check("version: plugin.json matches the latest CHANGELOG release", bool(released) and plugin.get("version") == released[0], f"{plugin.get('version')} vs {released[:1]}")
check("version: the helper matches plugin.json", bool(helper_version) and helper_version.group(1) == plugin.get("version"),
      helper_version.group(1) if helper_version else "none")

passed = sum(1 for ok, *_ in results if ok)
for ok, name, detail in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail and not ok else ""))
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
